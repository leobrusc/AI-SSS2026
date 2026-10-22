import json,pathlib,hashlib,subprocess,ast
r=pathlib.Path('.')
for p in sorted(r.glob('results/rq1/*/ground_truth_graph.json')):
 d=json.loads(p.read_text());print(p.parent.name,'nodes',len(d['nodes']),'app',sum(n.get('applicability')!='NOT_APPLICABLE' for n in d['nodes']),'schema',hashlib.sha256(json.dumps(d['nodes'],sort_keys=True).encode()).hexdigest()[:12]);s=p.parent/'rq1_summary.json';print(' result:',json.loads(s.read_text()).get('metrics',{}) if s.exists() else 'MISSING')
print('SYFT NAMES',[(c.get('name'),c.get('version')) for c in json.loads((r/'generated/rq1/syft_direct.cdx.json').read_text()).get('components',[])])
for rev in ['469dc67','de0d67e','94c0b7e','c0557b7','fd9a60c','HEAD']:
 for f in ['src/traceai/campaigns/rq1.py','src/traceai/campaigns/rq1_finalizer.py','src/traceai/bom/ground_truth.py']:
  p=subprocess.run(['git','show',rev+':'+f],capture_output=True)
  if p.returncode==0:print(rev,f,hashlib.sha256(p.stdout).hexdigest()[:12])
