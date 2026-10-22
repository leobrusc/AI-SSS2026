"""Run only on one real NVIDIA L4. Does not install dependencies or commit/push.
Uses current rq4.py workload; output routing preserves historical generated/gpu reports.
"""
import argparse,builtins,csv,hashlib,json,os,shutil,subprocess,sys,uuid,zipfile
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--repo',required=True,type=Path);args=parser.parse_args();root=args.repo.resolve()
 smi=subprocess.check_output(['nvidia-smi'],text=True)
 names=subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True).strip().splitlines()
 if names!=['NVIDIA L4']:raise SystemExit('Requires exactly one NVIDIA L4; no CPU/mock fallback.')
 import torch
 assert torch.cuda.is_available() and torch.cuda.device_count()==1 and 'L4' in torch.cuda.get_device_name(0)
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip(),'Use a clean source checkout; keep this runner outside it.'
 sys.path.insert(0,str(root/'src'));os.chdir(root)
 from traceai.campaigns import rq4
 cid='camera-ready-l4-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
 bundle=root/'results/camera_ready/l4'/cid;bundle.mkdir(parents=True,exist_ok=False)
 (bundle/'nvidia-smi.txt').write_text(smi)
 (bundle/'gpu-details.csv').write_text(subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total,utilization.gpu','--format=csv'],text=True))
 env={'timestamp':datetime.now(timezone.utc).isoformat(),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'torch':torch.__version__,'torch_cuda':torch.version.cuda,'cuda_available':torch.cuda.is_available(),'gpu_name':names[0],'python':sys.version,'configurations':rq4.CONFIGURATIONS,'model':rq4.SMOKE_MODEL,'requested_revision':rq4.SMOKE_REVISION,'instrumentation':'post-load dtype/device observation; validation-output routing only'}
 (bundle/'environment.json').write_text(json.dumps(env,indent=2));shutil.copy2(__file__,bundle/'l4_runner.py')
 hooks=bundle/'hooks';hooks.mkdir()
 hook='''import os,json
from pathlib import Path
from traceai.service.inference import InferenceEngine
original=InferenceEngine._load_sync
def observed_load(self):
 original(self)
 p=next(self._model.parameters())
 data={'requested_revision':self.revision,'config_commit_hash':getattr(self._model.config,'_commit_hash',None),'resolved_revision':self.resolved_revision,'parameter_dtype':str(p.dtype),'parameter_device':str(p.device),'model_id':self.model_id,'quantization_config':str(getattr(self._model.config,'quantization_config',None))}
 Path(os.environ['CR_MODEL_OBSERVATION']).write_text(json.dumps(data,indent=2))
InferenceEngine._load_sync=observed_load
'''
 (hooks/'sitecustomize.py').write_text(hook)
 os.environ['CR_MODEL_OBSERVATION']=str(bundle/'observed-model.json')
 os.environ['PYTHONPATH']=os.pathsep.join([str(hooks),str(root/'src'),os.environ.get('PYTHONPATH','')])
 os.environ['TRACEAI_DEVICE']='cuda';os.environ['TRACEAI_MODEL_ID']=rq4.SMOKE_MODEL;os.environ['TRACEAI_MODEL_REVISION']=rq4.SMOKE_REVISION
 os.environ.pop('TRACEAI_MODEL_DIR',None)
 # Native generator otherwise overwrites historical generated/gpu reports. Redirect exactly those two files.
 original_report=rq4._generate_quick_validation_report
 def report(*a,**kw):
  real_open=builtins.open;real_write=Path.write_text
  def routed_open(file,*aa,**kk):
   pp=Path(file) if isinstance(file,(str,os.PathLike)) else None
   if pp is not None and pp.resolve()==(root/'generated/gpu/quick_validation_report.json').resolve():file=bundle/'native_validation_report.json'
   return real_open(file,*aa,**kk)
  def routed_write(path,text,*aa,**kk):
   if path.resolve()==(root/'generated/gpu/quick_validation_report.md').resolve():path=bundle/'native_validation_report.md'
   return real_write(path,text,*aa,**kk)
  with patch('builtins.open',routed_open),patch.object(Path,'write_text',routed_write):return original_report(*a,**kw)
 rq4._generate_quick_validation_report=report
 rc=rq4.run_rq4_campaign(profile='gpu',quick=True,mode='publication',output_dir=bundle.relative_to(root)/'campaign')
 paths=list((bundle/'campaign').rglob('raw_requests.csv'));checks={'runner_exit_zero':rc==0,'raw_requests_present':len(paths)==1}
 if len(paths)==1:
  rows=list(csv.DictReader(paths[0].open()));normal=[r for r in rows if 'fault' not in r.get('trial_id','')];fault=[r for r in rows if 'fault' in r.get('trial_id','')]
  checks.update(normal_exact_240=len(normal)==240,fault_exact_6=len(fault)==6,per_config_60=all(sum(r['configuration_id']==c for r in normal)==60 for c in ['C0','C1','C2','C3']))
  campaign=paths[0].parent
  for filename in ['gpu_timeseries.csv','resource_timeseries.csv','trial_manifest.json','campaign_manifest.json','prompt_corpus_hash.json','configuration_events.jsonl','service_events.jsonl']:
   checks[filename+'_present']=(campaign/filename).exists()
 observation=bundle/'observed-model.json'
 checks['observed_model_present']=observation.exists()
 if observation.exists():
  obs=json.loads(observation.read_text());checks['actual_cuda_placement']=obs['parameter_device'].startswith('cuda');checks['actual_float16']=obs['parameter_dtype']=='torch.float16';checks['actual_config_revision']=obs['config_commit_hash']==rq4.SMOKE_REVISION
 # Native half-open gate is NOT accepted as proof: its code maps observed CLOSED to half-open.
 checks['native_half_open_not_security_proof']=True
 validation={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'normal_design':240,'fault_design':6,'limitations':['Native recovery/OPEN-confirm latency_ms=0 values are placeholders, not timing measurements.','circuit_half_open event can mean observed CLOSED; do not claim native HALF_OPEN observation.','This reproduces workload; it is not a parameter-matched overhead experiment.']}
 (bundle/'validation_report.json').write_text(json.dumps(validation,indent=2))
 files=[p for p in bundle.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 with (bundle/'SHA256SUMS.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['artifact','SHA256']);w.writerows((str(p.relative_to(bundle)),hashlib.sha256(p.read_bytes()).hexdigest()) for p in files)
 archive=bundle.parent/(cid+'-camera_ready_l4_campaign_bundle.zip')
 with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
  for p in bundle.rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(bundle))
 # Exact requested basename inside this unique campaign directory's parent packaging directory.
 package=bundle.parent/(cid+'-package');package.mkdir();final=package/'camera_ready_l4_campaign_bundle.zip';shutil.move(str(archive),final)
 (package/'camera_ready_l4_campaign_bundle.zip.sha256').write_text(hashlib.sha256(final.read_bytes()).hexdigest()+'  '+final.name+'\n')
 print(final);print(json.dumps(validation,indent=2));return 0 if validation['status']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
