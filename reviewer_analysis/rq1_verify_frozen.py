"""Replay frozen RQ1 measurement only; no scanner, generator, GPU or model load."""
import argparse,csv,hashlib,json,sys
from pathlib import Path
from rq1_strict_identity import matches

def verify(root,campaign):
 out=root/'results/camera_ready/rq1'/campaign;gen=root/'generated/camera_ready/rq1'/campaign
 result=json.loads((out/'coverage_result.json').read_text(encoding='utf-8'));p=out/'frozen_universe_v1.json';u=json.loads(p.read_text(encoding='utf-8'))
 assert hashlib.sha256(p.read_bytes()).hexdigest()==result['universe_SHA256']
 components=[c for name in ['final_ml_bom.cdx.json','final_obom.cdx.json','installed_python_sbom.cdx.json'] for c in json.loads((gen/name).read_text(encoding='utf-8'))['components']]
 assets=[a for a in u['assets'] if a['applicability']=='REQUIRED'];covered=[a['asset_id'] for a in assets if any(matches(a['expected_representation'],c) for c in components)]
 assert len(covered)==result['N_represented'] and len(assets)==result['N_applicable']
 return dict(status='PASS',campaign_id=campaign,N_applicable=len(assets),N_represented=len(covered),coverage=len(covered)/len(assets),covered_asset_ids=covered)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--campaign',required=True);a=p.parse_args();print(json.dumps(verify(Path(__file__).resolve().parents[1],a.campaign),indent=2))
