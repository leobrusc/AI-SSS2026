from pathlib import Path
import json,csv,hashlib,sys,copy
import numpy as np
from datetime import datetime,timezone
R=Path.cwd();A=R/'reviewer_analysis';sys.path.insert(0,str(R/'src'))
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(n,rows,fields=None):
 with (A/n).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
# Expand inventory to all campaign directories, even without manifests.
rows=[r for r in csv.DictReader((A/'campaign_inventory.csv').open()) if r['campaign_id'] not in ['phase4-cpu-diagnostic','test']]
seen={x['path'].replace('\\','/') for x in rows}
for row in rows:
 p=R/row['path'];m=load(p/'campaign_manifest.json') if (p/'campaign_manifest.json').exists() else {};row['timestamp']=m.get('timestamp',m.get('started_at','UNKNOWN'));row['trial_count']=m.get('trials',m.get('trial_count','UNKNOWN'))
 if 'availability-' in p.name:row.update(classification='UNKNOWN',mocked='True',notes='SYNTHETIC REQUESTS: availability.py _simulate_request; exclude from real CPU/GPU evidence. Taxonomy has no generic MOCK classification.')
 if 'security-' in p.name:row.update(mocked='False',notes='Real local policy/crypto calls on SYNTHETIC binary fixtures; not production-like artifacts.',device='CPU',fault_count=21 if str(m.get('trial_count'))=='3' else 210)
for base in ['results/rq1','results/rq3','results/rq4']:
 for p in (R/base).iterdir():
  if not p.is_dir() or str(p.relative_to(R)).replace('\\','/') in seen:continue
  sums=list(p.glob('*summary.json'));m=load(sums[0]) if sums else {};raw=[q for q in p.rglob('*') if q.is_file() and q.stat().st_size and q.suffix in {'.json','.csv','.jsonl'}]
  rows.append(dict(campaign_id=p.name,path=str(p.relative_to(R)),rq=base.split('/')[-1],timestamp=m.get('timestamp','UNKNOWN'),device='UNKNOWN',gpu='UNKNOWN',model='UNKNOWN',revision='UNKNOWN',trial_count='UNKNOWN',request_count='UNKNOWN',fault_count='UNKNOWN',raw_data_present=bool(raw),mocked='UNVERIFIED',classification='HISTORICAL_REAL' if base.endswith('rq3') and any(q.name=='trivy_scan_results.json' for q in raw) else 'UNKNOWN',notes='Scanner evidence on synthetic vulnerable fixture' if base.endswith('rq3') else 'No campaign manifest; do not infer hardware or effective configuration from directory name.'))
rows.append(dict(campaign_id='phase4-cpu-diagnostic',path='generated/rq4/phase4_cpu_diagnostic',rq='RQ4',timestamp=load(R/'generated/rq4/phase4_cpu_diagnostic/rq4_cpu_diagnostic.json')['timestamp_start'],device='cpu',gpu='NOT_APPLICABLE',model='sshleifer/tiny-gpt2',revision='NOT_RECORDED',trial_count=1,request_count=80,fault_count=0,raw_data_present=True,mocked=False,classification='CPU_DIAGNOSTIC',notes='Explicit device=cpu in diagnostic JSON; raw_observations.csv plus HTTP runner source. Not GPU evidence.'))
rows.append(dict(campaign_id='test',path='generated/gpu/quick_validation_report.json',rq='RQ4',timestamp=load(R/'generated/gpu/quick_validation_report.json')['timestamp'],device='MOCK',gpu='MOCK',model='UNKNOWN',revision='UNKNOWN',trial_count=0,request_count=240,fault_count='UNKNOWN',raw_data_present=False,mocked=True,classification='GPU_MOCK',notes='Unit test invokes report generator with campaign_id=test and handcrafted GPU samples; file alone is not GPU campaign evidence.'))
write('campaign_inventory.csv',rows);write('rq4_campaign_inventory.csv',[r for r in rows if str(r['rq']).lower().startswith('rq4')])
# Improve asset table without pretending naming establishes byte identity.
assets=list(csv.DictReader((A/'rq1_asset_inventory.csv').open()))
for r in assets:
 if r['node_id']=='tokenizer':r.update(represented='True',first_class_component='True',matched_components='generated/rq1/final_ml_bom.cdx.json#comp-tokenizer',implementation_gap='Different names gpt2-tokenizer/tokenizer.json; role mapping only, no digest binding')
 if r['node_id']=='runtime-policy':r.update(represented='True',first_class_component='True',matched_components='generated/rq1/final_obom.cdx.json#obom-policy',implementation_gap='Path/basename mapping; current final_obom lacks hash')
 if r['node_id']=='dataset-manifest':r['implementation_gap']='NOT VERIFIED: reference manifest path vs prompt-fixtures role; no digest proves same dataset'
 if r['node_id']=='traceai-app':r['matched_components']='generated/rq1/syft_direct.cdx.json#pkg:pypi/traceai@0.1.0';r['implementation_gap']='Do not collapse application package into inference-service identity'
 r['identity_validation']='name/role representation only; exact version/digest not certified'
write('rq1_asset_inventory.csv',assets)
summary='''# Fresh RQ1 audit: 27/29 is NOT VERIFIED for current repository
Historical raw graph explicitly enumerates 31 nodes, 29 applicable (host-gpu and cuda-runtime NOT_APPLICABLE).
Historical raw campaign reports 5/29. Current final_metrics.json reports 29/29; stale final_rq1_summary.tex
reports 27/29 and stale unmatched_nodes_after.csv lists OS/CPU that CURRENT final_obom contains as first-class components.
Domain reclassification records OS moved to OBOM and CPU made first-class; these are distinct evidence generations.
Finalizer rebuilds universe, replacing traceai-app with runtime-snapshot; raw and finalizer universes cannot be mixed.
Independent raw-universe mapping finds 28 named/role representations and one unresolved dataset identity;
this is an audit matching result, NOT a replacement experiment or a security-coverage estimate.
Tokenizer role maps to comp-tokenizer (tokenizer.json); policy path maps to obom-policy (policy.yaml).
Dataset reference fixtures/datasets/manifest.json vs prompt-fixtures remains unresolved without byte binding.
Version/PURL/digest correspondence must be checked before using these descriptive counts as experimental evidence.
Current matches_any uses permissive substring/token overlap; edge-completeness uses OR (one endpoint), not both endpoints.
Do not silently repair either methodological rule. No rerun of finalizer (which would overwrite historical artifacts) was performed.

Asset class | Reference | Represented by name/role | Coverage (descriptive only)
---|---:|---:|---:
'''
for cls in sorted({r['asset_class'] for r in assets}):
 rr=[r for r in assets if r['asset_class']==cls and r['applicable']=='True'];n=len(rr);k=sum(r['represented']=='True' for r in rr);summary+=f'{cls} | {n} | {k} | {k/n if n else "N/A"}\n'
summary+='\nSpecial nodes: os-platform -> obom-os; host-cpu -> obom-cpu; host-ram -> obom-ram; all first-class. host-gpu/cuda-runtime absent and inapplicable on CPU.\ninventory representation coverage != security coverage.\n'
(A/'rq1_summary.md').write_text(summary,encoding='utf-8')
# Add real explicitly labeled 80-request CPU diagnostic; successful-latency stats separate from rejections.
metrics=list(csv.DictReader((A/'rq4_metrics_by_config.csv').open()));trials=list(csv.DictReader((A/'rq4_metrics_by_trial.csv').open()))
p=R/'generated/rq4/phase4_cpu_diagnostic/raw_observations.csv';raw=list(csv.DictReader(p.open()))
for cfg in sorted({r['configuration_id'] for r in raw}):
 rr=[r for r in raw if r['configuration_id']==cfg];good=[r for r in rr if r['status_code']=='200'];lat=[float(r['latency_ms']) for r in good];tokens=[int(r['tokens_generated']) for r in good];reject=sum(r['outcome'] in ['EXPECTED_RATE_LIMIT','EXPECTED_QUEUE_REJECTION','EXPECTED_CIRCUIT_BREAKER'] for r in rr)
 ts=[datetime.fromisoformat(r['timestamp']).timestamp() for r in rr];start=[datetime.fromisoformat(r['timestamp']).timestamp()-float(r['latency_ms'])/1000 for r in rr];duration=max(ts)-min(start)
 row=dict(campaign_id='phase4-cpu-diagnostic',configuration=cfg,count=len(rr),success=len(good),rejection=reject,rejection_rate=reject/len(rr),throughput_success_per_s=len(good)/duration,throughput_basis='DERIVED completion timestamps minus measured latency; includes client gaps',median_ms=np.median(lat) if lat else '',p95_ms=np.percentile(lat,95) if lat else '',mean_ms=np.mean(lat) if lat else '',std_ms=np.std(lat,ddof=1) if len(lat)>1 else '',iqr_ms=np.percentile(lat,75)-np.percentile(lat,25) if lat else '',tokens_mean=np.mean(tokens) if tokens else '',tokens_min=min(tokens) if tokens else '',tokens_max=max(tokens) if tokens else '',tokens_total=sum(tokens),cpu_percent_mean='',evidence='CPU EVIDENCE',source=str(p.relative_to(R)))
 metrics=[r for r in metrics if not (r['campaign_id']=='phase4-cpu-diagnostic' and r['configuration']==cfg)];trials=[r for r in trials if not (r['campaign_id']=='phase4-cpu-diagnostic' and r['configuration']==cfg)];metrics.append(row);trials.append(dict(row,trial='single diagnostic run; no independent repeated trials'))
write('rq4_metrics_by_config.csv',metrics);write('rq4_metrics_by_trial.csv',trials)
with (A/'rq4_summary.md').open('a',encoding='utf-8') as f:f.write('\nAlso recomputed explicitly labeled 80-request CPU diagnostic in generated/rq4/phase4_cpu_diagnostic (20/config; one run). Stress raw CSVs without manifests remain hardware UNVERIFIED; not pooled. Older availability-20260722-115011 campaign is synthetic (_simulate_request), not CPU evidence. Existing GPU report campaign_id=test is GPU_MOCK/unit output; do not diagnose it as a failed real GPU run.\n')
# Actual VEX parser/status diagnostics.
from traceai.vulnerability.vex import VexDocument,apply_vex_to_findings
from traceai.models import VulnerabilityFinding
p=R/'results/camera_ready/vex_diagnostics';p.mkdir(exist_ok=True)
results=[]
for status in ['affected','not_affected','fixed','under_investigation','unknown']:
 d={'bomFormat':'CycloneDX','metadata':{'timestamp':'2000-01-01T00:00:00+00:00'},'vulnerabilities':[{'id':'CVE-FIXTURE','analysis':{'state':status},'affects':[{'ref':'WRONG-COMPONENT'}]}]}
 doc=VexDocument(d);finding=VulnerabilityFinding(scanner='fixture',vulnerability_id='CVE-FIXTURE',severity='HIGH',package_name='other',installed_version='1')
 remaining,stats=apply_vex_to_findings([finding],doc);results.append(dict(status=status,remaining=len(remaining),suppressed=stats['suppressed'],expired=doc.is_expired,wrong_component=True))
base={'bomFormat':'CycloneDX','metadata':{'timestamp':'2000-01-01T00:00:00+00:00','properties':[{'name':'traceai:expires','value':'2000-01-02T00:00:00+00:00'}]}}
results.append(dict(case='explicit_expiry',expired=VexDocument(base).is_expired));base['metadata'].pop('timestamp');results.append(dict(case='explicit_expiry_without_timestamp',expired=VexDocument(base).is_expired))
conflict={'bomFormat':'CycloneDX','vulnerabilities':[{'id':'CVE-FIXTURE','analysis':{'state':'not_affected'}},{'id':'CVE-FIXTURE','analysis':{'state':'affected'}}]};results.append(dict(case='conflicting_first_statement_wins',status=VexDocument(conflict).get_status_for_vulnerability('CVE-FIXTURE')))
(p/'observations.json').write_text(json.dumps({'timestamp':datetime.now(timezone.utc).isoformat(),'observations':results},indent=2));print('VEX diagnostic observations',results)


