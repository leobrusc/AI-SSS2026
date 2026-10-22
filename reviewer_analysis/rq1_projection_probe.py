import json,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from traceai.campaigns.rq1_finalizer import compute_final_coverage
r=Path.cwd();load=lambda p:json.loads((r/p).read_text(encoding='utf-8'))
g=load('results/rq1/rq1-20260722-140850-18433df2/ground_truth_graph.json');g['nodes']=[n for n in g['nodes'] if n['id'] not in ['cuda-runtime','traceai-app']]
for n in g['nodes']:
 if n['id']=='pytorch':n['id']='pkg-torch'
 if n['id']=='transformers-pkg':n['id']='pkg-transformers'
 if n['id']=='tokenizer':n['name']=n['canonical_identity']['name']='tokenizer.json'
 if n['id']=='dataset-manifest':n['name']=n['canonical_identity']['name']='prompt-fixtures'
 if n['id']=='python-runtime':n['name']=n['canonical_identity']['name']='cpython'
 if n['id']=='runtime-policy':n['name']=n['canonical_identity']['name']='policy.yaml'
g['nodes'].append(dict(id='runtime-snapshot',name='process-snapshot',type='operational_state',expected_bom=['obom'],applicability='REQUIRED',canonical_identity=dict(name='process-snapshot')));g['meta']['total_nodes']=len(g['nodes']);g['meta']['applicable_nodes']=sum(n['applicability']!='NOT_APPLICABLE' for n in g['nodes'])
ml=load('generated/rq1/final_ml_bom.cdx.json');ob=load('generated/rq1/final_obom.cdx.json');sy=load('generated/rq1/syft_direct.cdx.json')['components']
for mode in ['current','native-finalizer']:
 oo=ob if mode=='current' else {'components':[c for c in ob['components'] if c['bom-ref'] in ['obom-service','obom-policy','obom-snapshot']]}
 print(mode,json.dumps(compute_final_coverage(g,ml,oo,sy),indent=2))
