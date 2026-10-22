"""RQ1 lineage audit and a frozen CPU-only representation experiment.
Run from repository root: .venv/Scripts/python.exe reviewer_analysis/rq1_reconcile.py
No historical output changes; no model/GPU execution.
"""
import ast,copy,csv,hashlib,importlib.metadata as im,json,os,platform,re,subprocess,sys,sysconfig,uuid
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'src'));A=R/'reviewer_analysis'
from traceai.campaigns import rq1_finalizer as F
from traceai.campaigns.rq1 import _compute_typed_coverage
NOW=datetime.now(timezone.utc).isoformat();CID='rq1-cr-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
OUT=R/'results/camera_ready/rq1'/CID;GEN=R/'generated/camera_ready/rq1'/CID
REP=R/'results/camera_ready/rq1_reproduction'/CID;REPG=R/'generated/camera_ready/rq1_reproduction'/CID
for p in [OUT,GEN,REP,REPG]:p.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
def csvout(p,rows,fields=None):
 with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),extrasaction='ignore');w.writeheader();w.writerows(rows)
def git(*args):return subprocess.check_output(['git',*args],cwd=R,text=True,encoding='utf-8').strip()
def norm(n):return re.sub(r'[-_.]+','-',n.lower())
def applicable(n):return n.get('applicability',n.get('status','REQUIRED')) not in ['NOT_APPLICABLE','NOT_APPLICABLE_LOCAL_PROFILE']
commit=git('rev-parse','HEAD');assert commit=='bb2d9e4b4703b8f59dcd6ef563df374fcbe79720'
protected={str(p.relative_to(R)):sha(p) for d in ['results','generated','src','config','fixtures','scripts','workspace'] for p in (R/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
dump(OUT/'protected_input_hashes.json',protected)
sourcepaths=[R/'src/traceai/campaigns/rq1.py',R/'src/traceai/campaigns/rq1_finalizer.py',R/'src/traceai/bom/ground_truth.py',R/'src/traceai/bom/cyclonedx_builder.py',Path(__file__),A/'rq1_strict_identity.py']
csvout(OUT/'code_hashes.csv',[dict(file=str(p.relative_to(R)),SHA256=sha(p)) for p in sourcepaths])
dump(OUT/'environment.json',dict(timestamp=NOW,commit=commit,python=sys.version,executable=sys.executable,platform=platform.platform(),command='.venv/Scripts/python.exe reviewer_analysis/rq1_reconcile.py',gpu_execution=False,model_inference=False))
versions=[]
for rev in ['469dc674a81f5ef1c1bf7e6268c8ee7c8128d347','94c0b7ec5268f61d158e57377da71da2f4e057bd','c0557b7c7ac0c26a2be17d2e92b42276bec0dc1a',commit]:
 for p in sourcepaths[:4]:
  q=subprocess.run(['git','show',rev+':'+p.relative_to(R).as_posix()],cwd=R,capture_output=True)
  if q.returncode==0:
   t=REPG/(rev[:8]+'-'+p.name);t.write_bytes(q.stdout);versions.append(dict(commit=rev,file=str(p.relative_to(R)),SHA256=sha(t),saved_source=str(t.relative_to(R))))
csvout(REP/'source_versions.csv',versions)
lineage=[]
def universe(uid,source,generator,nodes,coverage,rule,boms='',authority='OBSERVED',note=''):
 path=REPG/(uid+'.json');dump(path,dict(universe_id=uid,nodes=nodes,authority=authority,notes=note));t='NOT_RECORDED'
 if isinstance(source,Path) and source.exists():
  try:d=read(source);t=d.get('meta',{}).get('timestamp',d.get('timestamp',d.get('metadata',{}).get('timestamp','NOT_RECORDED')))
  except Exception:pass
 lineage.append(dict(universe_id=uid,source_file=str(source.relative_to(R)) if isinstance(source,Path) else str(source),generator_function=generator,timestamp=t,commit_if_known=commit if authority=='CURRENT_CODE' else 'NOT_RECORDED',node_count_total=len(nodes),node_count_applicable=sum(applicable(n) for n in nodes),node_identities=json.dumps([dict(id=n.get('id',n.get('bom_ref','')),name=n.get('name',''),version=n.get('version','')) for n in nodes],ensure_ascii=False),applicability_rules='Exclude explicitly NOT_APPLICABLE/NOT_APPLICABLE_LOCAL_PROFILE; preserve missing required assets',representation_rules=rule,output_BOM_files=boms,coverage_value=str(coverage),universe_snapshot=str(path.relative_to(R)),universe_SHA256=sha(path),authority=authority,notes=note))
rawgraphs={};rawmatched={};rawscores=[]
for path in sorted((R/'results/rq1').glob('*/ground_truth_graph.json')):
 gt=read(path);rawgraphs[path.parent.name]=gt;sp=path.parent/'rq1_summary.json';summary=read(sp) if sp.exists() else {};m=summary.get('metrics',{});bs={}
 for name in ['syft.cdx.json','trivy.cdx.json','traceai_ml_bom.cdx.json','traceai_obom.cdx.json']:
  try:bs[name]=read(path.parent/name)
  except Exception:bs[name]={'components':[]}
 names={c.get('name','').lower() for b in bs.values() for c in b.get('components',[])}
 rawmatched[path.parent.name]=[n['id'] for n in gt['nodes'] if applicable(n) and n.get('canonical_identity',{}).get('name',n['name']).lower() in names]
 score=m.get('composite_coverage',m.get('traceai_gt_coverage','MISSING_SUMMARY'))
 if 'meta' in gt:
  def scan(name):
   b=bs[name+'.cdx.json'];meta=m.get(name,{});return dict(components=b.get('components',[]),component_count=len(b.get('components',[])),status=meta.get('status','UNKNOWN'),bom=b,limitation=meta.get('limitation'))
  ev=_compute_typed_coverage(gt,scan('syft'),scan('trivy'),bs['traceai_ml_bom.cdx.json'],bs['traceai_obom.cdx.json'],'local');dump(REP/(path.parent.name+'-reevaluation.json'),ev)
  rawscores.append(dict(campaign=path.parent.name,reported_numerator=m.get('composite_matched','MISSING'),computed_numerator=ev['composite_matched'],denominator=ev['composite_applicable'],reported_coverage=score,computed_coverage=ev['composite_coverage'],matches=rawmatched[path.parent.name]))
 universe(path.parent.name,path,'rq1._build_typed_ground_truth' if 'meta' in gt else 'legacy rq1._build_ground_truth_graph',gt['nodes'],score,'case-insensitive exact names; first legacy report ML-BOM-only/distinct-name denominator',';'.join(str((path.parent/n).relative_to(R)) for n in bs),note='Run commit NOT_RECORDED; compatible sources in Git are not proven run provenance.')
csvout(REP/'raw_metric_reevaluations.csv',rawscores)
rawid='rq1-20260722-140850-18433df2';raw=rawgraphs[rawid];rawnodes={n['id']:n for n in raw['nodes']}
fgt=copy.deepcopy(raw);fgt['nodes']=[n for n in fgt['nodes'] if n['id'] not in ['cuda-runtime','traceai-app']]
for n in fgt['nodes']:
 changes={'pytorch':('pkg-torch','torch'),'transformers-pkg':('pkg-transformers','transformers'),'tokenizer':('tokenizer','tokenizer.json'),'dataset-manifest':('dataset-manifest','prompt-fixtures'),'python-runtime':('python-runtime','cpython'),'host-cpu':('host-cpu','cpu'),'host-ram':('host-ram','ram'),'host-gpu':('host-gpu','gpu'),'runtime-policy':('runtime-policy','policy.yaml')}
 if n['id'] in changes:n['id'],n['name']=changes[n['id']];n['canonical_identity']['name']=n['name']
fgt['nodes'].append(dict(id='runtime-snapshot',type='operational_state',name='process-snapshot',version='',expected_bom=['obom'],applicability='REQUIRED',canonical_identity=dict(name='process-snapshot',version='')))
fgt['meta'].update(total_nodes=len(fgt['nodes']),applicable_nodes=sum(applicable(n) for n in fgt['nodes']))
# Only node coverage is evaluated here. One source-known edge avoids using stale raw IDs; edge statistics excluded.
fgt['edges']=[dict(source='inference-service',target='model-gpt2',relationship='dependsOn',domain='obom')];fgt['meta']['total_edges']=1
mlpath=R/'generated/rq1/final_ml_bom.cdx.json';obpath=R/'generated/rq1/final_obom.cdx.json';sypath=R/'generated/rq1/syft_direct.cdx.json'
ml=read(mlpath);ob=read(obpath);sy=read(sypath)
native_projection={'components':[c for c in ob['components'] if c.get('bom-ref') in ['obom-service','obom-policy','obom-snapshot']]}
source=(REPG/'c0557b7c-rq1_finalizer.py').read_text(encoding='utf-8');fun=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='compute_final_coverage')
ns={};exec(compile(ast.Module(body=[fun],type_ignores=[]),'c0557b7:compute_final_coverage','exec'),ns)
p27=ns['compute_final_coverage'](fgt,ml,native_projection,sy['components']);p29=ns['compute_final_coverage'](fgt,ml,ob,sy['components'])
for p in [p27,p29]:
 for key in ['edge_completeness','total_edges','edges_partially_matched']:p.pop(key,None)
dump(REP/'source_projection_27.json',dict(classification='NUMERIC_RECONSTRUCTION_NOT_FROZEN_HISTORICAL_REPRODUCTION',result=p27,universe=fgt,operational_component_projection=native_projection))
dump(REP/'current_BOM_projection_29.json',dict(classification='CURRENT_BOMS_ON_RECONSTRUCTED_FINALIZER_UNIVERSE',result=p29))
assert p27['composite_matched']==27 and p29['composite_matched']==29
repro=dict(classification='HISTORICAL_27_29_NOT_REPRODUCIBLE',numeric_metric_reconstruction_27_29=True,historical_frozen_run_reproduced=False,missing_exact_inputs=['Original finalizer ground-truth JSON not persisted','Original native three-component OBOM bytes overwritten by seven-component enriched file','No run manifest binding source revision, selected scanner file, inventory and BOM hashes'],warning='Only a labeled source-projection metric reconstruction; original full run NOT reproduced. RAM matches colorama by substring, a false semantic match.')
dump(REP/'reproduction_status.json',repro)
universe('finalizer_source_projection',R/'src/traceai/campaigns/rq1_finalizer.py','c0557b7 build_complete_ground_truth and compute_final_coverage',fgt['nodes'],'27/29 NUMERIC_RECONSTRUCTION_ONLY','exact/substring/shared-token matching; HBOM also searches software names','saved ML-BOM; source three-role OBOM projection; preserved Syft165',authority='SOURCE_RECONSTRUCTION',note='Not original frozen graph. Removes CUDA and app; adds snapshot; renames asset identities. Versions are not claimed recovered historical runtime observations.')
currentnodes=copy.deepcopy(fgt['nodes'])
for n in currentnodes:
 if n['id'] in ['python-runtime','os-platform']:n['expected_bom']=['obom']
universe('postprocessed_current_29',R/'generated/rq1/final_metrics.json','POST_PROCESSOR_NOT_FOUND',currentnodes,'29/29 reported; name metric reconstructed','Finalizer heuristic on expanded7-component OBOM; metrics HBOM2/OBOM5',';'.join(str(p.relative_to(R)) for p in [mlpath,obpath,sypath]),authority='INFERRED_MEMBERSHIP_NOT_ORIGINAL_GRAPH',note='Partition supported by metrics/reclassification CSV; original inventory and postprocessor not saved.')
from traceai.bom.ground_truth import build_ground_truth
small=build_ground_truth('openai-community/gpt2',profile='local').to_dict()
universe('generic_builder_8',R/'src/traceai/bom/ground_truth.py','build_ground_truth',[dict(n,id=n['bom_ref'],applicability='REQUIRED') for n in small['components']],'NOT_COVERAGE_RESULT','Serializer graph8 logical components','native ML-BOM8 components',authority='CURRENT_CODE',note='Called inside rq1._generate_ml_bom, distinct from external evaluation universe.')
for label,p in [('direct_pinned_manifest',R/'requirements-exact.txt'),('direct_declared_runtime',R/'requirements.txt')]:
 nodes=[]
 for line in p.read_text(encoding='utf-8').splitlines():
  if not line.strip() or line.startswith('#'):continue
  name=re.split(r'[<>=\[]',line.strip())[0];version=line.split('==',1)[1] if '==' in line else 'CONSTRAINT_ONLY';nodes.append(dict(id='package:'+norm(name),name=norm(name),version=version,applicability='REQUIRED'))
 universe(label,p,'phase2_rq1_comparison/rq1 direct dependencies',nodes,'SEPARATE_PACKAGE_COMPARISON','PEP503 name+exact pinned/installed version',note='Not composite29 denominator; constraints and pins are distinct identities.')
for p in sorted((R/'results/rq1').glob('*/syft.cdx.json'))+[sypath,R/'generated/rq1/trivy_probe_root.json']:
 try:d=read(p)
 except Exception:continue
 universe('scanner_'+p.parent.name+'_'+p.stem.replace('.','_'),p,'scanner output inventory',[dict(id=c.get('bom-ref',str(i)),name=c.get('name',''),version=c.get('version',''),applicability='REQUIRED',purl=c.get('purl','')) for i,c in enumerate(d.get('components',[]))],'NOT_REFERENCE_COVERAGE_DENOMINATOR','Scanner output components; repeats permitted',str(p.relative_to(R)),note='Observed output inventory, not complete environment ground truth.')
prior=A/'rq1_asset_inventory.csv'
universe('prior_role_audit_28',prior,'reviewer_analysis/refine_audit.py',raw['nodes'],'28/29 PRIOR_NAME_ROLE_AUDIT','Names plus aliases, no dataset digest correspondence',note='Raw reference reused; altered oracle, not independent historical campaign.')
# NEW union-of-roles reference inventory: raw31 PLUS runtime snapshot. No desired score used.
freeze=[];revision='607a30d783dfa663caf39e06633721c8d4cfcd7e'
classes={'model':'model','weight':'model','tokenizer':'tokenizer','package':'software','runtime':'runtime','hardware':'hardware','service':'software','policy':'configuration'}
for n in raw['nodes']:
 nid=n['id'];cls=classes.get(n['type'],'other');expected={};source='';present=True
 if nid in ['model-config','generation-config']:cls='configuration'
 if nid=='dataset-manifest':cls='dataset'
 if n['type']=='package' or nid=='traceai-app':
  name=n['name'];expected=dict(kind='python_distribution',name=norm(name),version=im.version(name));source='installed distribution METADATA: '+name
 elif nid=='model-gpt2':
  expected=dict(kind='model_revision',name='openai-community/gpt2',revision=revision);source='rq4.py FULL_MODEL/FULL_REVISION: declared target, NOT loaded'
 elif nid in ['model-weights','tokenizer','model-config','generation-config','dataset-manifest','runtime-policy']:
  if nid=='dataset-manifest':rel='fixtures/datasets/manifest.json';name='prompt-fixtures'
  elif nid=='runtime-policy':rel='config/policy.yaml';name='policy.yaml'
  else:
   name={'model-weights':'model.safetensors','tokenizer':'tokenizer.json','model-config':'config.json','generation-config':'generation_config.json'}[nid];rel='workspace/models/'+name
  pp=R/rel;source=rel;present=pp.is_file();expected=dict(kind='file_sha256',name=name,SHA256=sha(pp) if present else None,required_source_present=present)
 elif nid=='python-runtime':expected=dict(kind='typed_name_version',name='cpython',version=platform.python_version(),cdx_type='platform');source='current interpreter platform.python_version'
 elif nid=='os-platform':expected=dict(kind='typed_name_version',name=platform.system(),version=platform.release(),cdx_type='operating-system');source='platform.system/release'
 elif nid=='host-cpu':expected=dict(kind='typed_name_version',name='cpu',version=str(os.cpu_count()),cdx_type='device');source='host CPU role and os.cpu_count (not unique silicon ID)'
 elif nid=='host-ram':
  import psutil
  expected=dict(kind='typed_name_version',name='ram',version=str(round(psutil.virtual_memory().total/(1024**3),1))+'GB',cdx_type='device');source='host RAM role and observed capacity (not DIMM serial)'
 elif nid=='inference-service':expected=dict(kind='typed_name_version',name='traceai-inference',version='0.1.0',cdx_type='application');source='pyproject.toml and service role: declared, NOT running'
 else:expected=dict(kind='not_applicable_cpu_scope');source='CPU-only scope; no GPU detection/execution'
 canonical={'pytorch':'python-package:torch','transformers-pkg':'python-package:transformers','traceai-app':'python-package:traceai'}.get(nid,'python-package:'+norm(n['name']) if n['type']=='package' else nid)
 freeze.append(dict(asset_id=canonical,raw_id=nid,name=n['name'],role=n['type'],**{'class':cls},source=source,source_present=present,expected_representation=expected,applicability='NOT_APPLICABLE_CPU_SCOPE' if nid in ['host-gpu','cuda-runtime'] else 'REQUIRED',applicability_reason='CPU-scope exclusion, not measured hardware absence' if nid in ['host-gpu','cuda-runtime'] else 'Reference requirement retained even when artifact absent'))
freeze.append(dict(asset_id='runtime-snapshot',raw_id='',name='process-snapshot',role='operational_state',**{'class':'runtime'},source='current experiment process PID',source_present=True,expected_representation=dict(kind='typed_name_version',name='process-snapshot',version='pid='+str(os.getpid()),cdx_type='platform'),applicability='REQUIRED',applicability_reason='Finalizer-added role retained alongside raw traceai-app, NOT substituted for it'))
uf=OUT/'frozen_universe_v1.json';dump(uf,dict(label='CAMERA_READY_RQ1',version=1,campaign_id=CID,timestamp=NOW,commit=commit,definition='Union raw31 and finalizer-added runtime-snapshot; exclude GPU/CUDA by CPU scope only',scope='CPU-host deployment-reference representation benchmark; no loaded model/running deployment asserted',representation_rule='Predeclared exact predicates; first-class components, exact Python name/version/PURL, file hashes, model revision; no substrings',assets=freeze));frozenhash=sha(uf)
dump(OUT/'freeze_receipt.json',dict(universe_SHA256=frozenhash,frozen_at=datetime.now(timezone.utc).isoformat(),generation_started=False,N_total=len(freeze),N_applicable=sum(n['applicability']=='REQUIRED' for n in freeze)))
package_metadata=[]
for n in freeze:
 if n['expected_representation'].get('kind')!='python_distribution':continue
 dist=im.distribution(n['expected_representation']['name']);text=dist.read_text('METADATA') or ''
 package_metadata.append(dict(asset_id=n['asset_id'],distribution_name=dist.metadata['Name'],version=dist.version,METADATA_SHA256=hashlib.sha256(text.encode()).hexdigest()))
dump(OUT/'package_reference_metadata.json',package_metadata)
print('Frozen',len(freeze),'reference nodes; applicable',sum(n['applicability']=='REQUIRED' for n in freeze),'hash',frozenhash,flush=True)
# Native current finalizer constructors take explicit output directories. No hardcoded historical wrapper call.
F.generate_complete_ml_bom(R,'local',GEN);F.generate_observed_obom(R,GEN)
syft=R/'.tools/bin/syft.exe';target=Path(sysconfig.get_paths()['purelib']);sbom=GEN/'installed_python_sbom.cdx.json'
cmd=[str(syft),'scan','dir:'+str(target),'--override-default-catalogers','python-installed-package-cataloger','--output','cyclonedx-json='+str(sbom)]
env=os.environ.copy();env['SYFT_CHECK_FOR_APP_UPDATE']='false'
p=subprocess.run([str(syft),'version'],capture_output=True,text=True,env=env);(OUT/'syft_version.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
dump(OUT/'scanner_command.json',dict(command=cmd,target=str(target),network_required=False,selected_cataloger='python-installed-package-cataloger',freeze_hash_before_generation=frozenhash))
p=subprocess.run(cmd,capture_output=True,env=env,timeout=180)
(OUT/'syft_stdout.txt').write_bytes(p.stdout);(OUT/'syft_stderr.txt').write_bytes(p.stderr)
assert p.returncode==0 and sbom.exists(),('SCANNER_FAILED',p.returncode,p.stderr)
assert sha(uf)==frozenhash
outputs=[GEN/'final_ml_bom.cdx.json',GEN/'final_obom.cdx.json',sbom];observations=[]
for path in outputs:
 for c in read(path).get('components',[]):observations.append(dict(source=str(path.relative_to(R)),component=c))
from rq1_strict_identity import matches
outcomes=[]
for asset in freeze:
 hits=[o for o in observations if matches(asset['expected_representation'],o['component'])] if asset['applicability']=='REQUIRED' else []
 outcomes.append(dict(asset_id=asset['asset_id'],**{'class':asset['class']},source=asset['source'],expected_representation=json.dumps(asset['expected_representation']),applicability=asset['applicability'],actual_representation=json.dumps([o['component'] for o in hits]),representation_mechanism='first-class exact identity predicate' if hits else ('not_applicable_cpu_scope' if asset['applicability']!='REQUIRED' else 'UNMATCHED'),evidence_file=';'.join(o['source'] for o in hits),represented=bool(hits),source_present=asset['source_present']))
csvout(OUT/'asset_results.csv',outcomes);app=[r for r in outcomes if r['applicability']=='REQUIRED'];N=len(app);K=sum(x['represented'] for x in app)
result=dict(label='CAMERA_READY_RQ1',campaign_id=CID,universe_version=1,universe_SHA256=frozenhash,N_total=len(freeze),N_applicable=N,N_represented=K,coverage=K/N,coverage_percent=100*K/N,code_commit=commit,interpretation='First-class identity representation of fixed CPU deployment-reference inventory; NOT security coverage or proof of running model',historical_93_1=False)
dump(OUT/'coverage_result.json',result)
byclass=[]
for cls in sorted({a['class'] for a in app}):
 aa=[a for a in app if a['class']==cls];byclass.append(dict(asset_class=cls,reference=len(aa),represented=sum(a['represented'] for a in aa),coverage=sum(a['represented'] for a in aa)/len(aa)))
csvout(GEN/'coverage_by_class.csv',byclass)
universe('camera_ready_v1',uf,'current finalizer constructors + new Syft installed cataloger + independent measurement',[dict(id=n['asset_id'],name=n['name'],version=n['expected_representation'].get('version',''),applicability='REQUIRED' if n['applicability']=='REQUIRED' else 'NOT_APPLICABLE') for n in freeze],f'{K}/{N}={K/N}','Predeclared strict per-asset predicates; no name substring matches',';'.join(str(p.relative_to(R)) for p in outputs),authority='CURRENT_CODE',note='NEW result; changed universe and measurement rules are explicit, not retroactively applied.')
# Crosswalk matches IDs/roles and evidence, never row positions. current=pre-existing29/29 files.
fby={n['id']:n for n in fgt['nodes']};unmatched={r['id'] for r in csv.DictReader((R/'generated/rq1/unmatched_nodes_after.csv').open())};actualby={n['raw_id']:n for n in freeze if n['raw_id']};outby={o['asset_id']:o for o in outcomes};cross=[]
for rid in list(rawnodes)+['runtime-snapshot']:
 n=rawnodes.get(rid,dict(name='process-snapshot',type='operational_state'));fid={'pytorch':'pkg-torch','transformers-pkg':'pkg-transformers'}.get(rid,rid);exists=fid in fby
 asset=actualby.get(rid,freeze[-1] if rid=='runtime-snapshot' else None);semantic='YES_ROLE_ONLY';confidence='HIGH_ROLE_NOT_BYTE_IDENTITY';note='Stable role; historical byte/version identity not established'
 if rid=='dataset-manifest':semantic='UNVERIFIED';confidence='LOW';note='manifest path renamed prompt-fixtures; no digest proves same underlying corpus'
 if rid=='tokenizer':confidence='MEDIUM_ROLE_ONLY';note='gpt2-tokenizer -> tokenizer.json; same role, byte identity unproven'
 if rid=='traceai-app':semantic='NO_FINALIZER_EQUIVALENT';note='Removed distribution, not same asset as service or runtime-snapshot'
 if rid=='runtime-snapshot':semantic='NO_RAW_EQUIVALENT';note='New operational observation; not renamed application'
 if rid=='cuda-runtime':semantic='ABSENT_FROM_FINALIZER';note='Inapplicable raw CUDA node omitted entirely'
 cross.append(dict(canonical_asset_id=asset['asset_id'] if asset else rid,raw_campaign_id=(rawid+'#'+rid) if rid in rawnodes else '',finalizer_id=fid if exists else '',current_id=fid if exists else '',name=n['name'],role=n['type'],**{'class':asset['class'] if asset else 'runtime'},applicable_raw=applicable(n) if rid in rawnodes else 'ABSENT',applicable_finalizer=applicable(fby[fid]) if exists else 'ABSENT',applicable_current=applicable(fby[fid]) if exists else 'ABSENT',represented_raw=rid in rawmatched[rawid] if rid in rawnodes else 'ABSENT',represented_finalizer=('REPORTED_UNMATCHED' if rid in unmatched else ('REPORTED_MATCH_HEURISTIC' if applicable(fby[fid]) else 'NOT_APPLICABLE')) if exists else 'ABSENT',represented_current=('NAME_HEURISTIC_MATCH' if applicable(fby[fid]) else 'NOT_APPLICABLE') if exists else 'ABSENT',same_semantic_asset=semantic,identity_confidence=confidence,notes=note+('; fresh strict result='+str(outby[asset['asset_id']]['represented']) if asset else '')))
csvout(A/'rq1_identity_crosswalk.csv',cross,['canonical_asset_id','raw_campaign_id','finalizer_id','current_id','name','role','class','applicable_raw','applicable_finalizer','applicable_current','represented_raw','represented_finalizer','represented_current','same_semantic_asset','identity_confidence','notes'])
csvout(A/'rq1_universe_lineage.csv',lineage)
changed=[p for p,h in protected.items() if not (R/p).exists() or sha(R/p)!=h];assert not changed,changed
dump(OUT/'historical_integrity_check.json',dict(status='PASS',files_checked=len(protected),changed=changed,timestamp=datetime.now(timezone.utc).isoformat()))
inputs=[R/p for p in protected if p.startswith(('results/rq1','generated/rq1'))]+sourcepaths+[R/'requirements.txt',R/'requirements-exact.txt',R/'fixtures/datasets/manifest.json']
csvout(REP/'input_hashes.csv',[dict(file=str(p.relative_to(R)),SHA256=sha(p)) for p in inputs if p.exists()])
for base in [OUT,GEN,REP,REPG]:
 ps=[p for p in base.rglob('*') if p.is_file()];csvout(base/'SHA256SUMS.csv',[dict(file=str(p.relative_to(base)),SHA256=sha(p)) for p in ps],['file','SHA256'])
dump(GEN/'workflow_summary.json',dict(campaign_id=CID,paths=dict(results=str(OUT.relative_to(R)),generated=str(GEN.relative_to(R)),reproduction=str(REP.relative_to(R)),reproduction_generated=str(REPG.relative_to(R))),reproduction=repro,fresh=result,publication_decision='REPLACE_WITH_CAMERA_READY_RESULT',historical_unchanged=len(protected),missing_assets=[o['asset_id'] for o in app if not o['represented']]))
print(json.dumps(read(GEN/'workflow_summary.json'),indent=2),flush=True)


