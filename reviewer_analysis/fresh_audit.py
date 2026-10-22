"""Read-only historical audit plus isolated camera-ready verifier experiments.

Run from repository root: .venv/Scripts/python.exe reviewer_analysis/fresh_audit.py
Never changes historical inputs, source implementation, or manuscript.
"""
import base64
import copy
import csv
import hashlib
import importlib.util
import json
import platform
import re
import shutil
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
A = ROOT / 'reviewer_analysis'
NOW = datetime.now(timezone.utc).isoformat()
CID = 'cr-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
OUT = ROOT / 'results/camera_ready/rq2_extension' / CID
OUT.mkdir(parents=True, exist_ok=False)
GEN = ROOT / 'generated/camera_ready' / CID
GEN.mkdir(parents=True, exist_ok=False)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def dump(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, default=str), encoding='utf-8')

def table(p, rows, fields=None):
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else ['status'])
    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

def md(name, text):
    (A / name).write_text(text.strip() + '\n', encoding='utf-8')

# Preserve pre-existing analysis before replacing derived reports.
snapshot = GEN / 'prior_analysis'
snapshot.mkdir()
for p in A.iterdir():
    if p.is_file() and p.suffix in {'.md', '.csv'}:
        shutil.copy2(p, snapshot / p.name)

commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
historical_files = [p for directory in ['results','generated','workspace','config','src','tests','scripts','fixtures']
                    for p in (ROOT/directory).rglob('*') if p.is_file() and 'camera_ready' not in p.parts and '__pycache__' not in p.parts]
baseline = {str(p.relative_to(ROOT)): sha(p) for p in historical_files}
dump(GEN/'historical_hashes_before.json', baseline)
dump(GEN/'environment.json', {'timestamp':NOW,'commit':commit,'python':sys.version,
     'executable':sys.executable,'platform':platform.platform(),'campaign_id':CID})

# Exact historical RQ2, positive = invalid condition; do not use recorded FP/FN flags as oracle.
from scipy.stats import beta
histpath = ROOT/'results/raw/security-20260722-140421-f4aee0f2/security_results.json'
hist = read(histpath)
assert len(hist) == 240
assert Counter(x['scenario_id'] for x in hist) == Counter({s:30 for s in ['S0','S1','S2','S3','S9a','S9b','S9c','S9d']})
def label(invalid, rejected):
    return ('TP' if rejected else 'FN') if invalid else ('FP' if rejected else 'TN')
def cp(k,n):
    return [float(beta.ppf(.025,k,n-k+1)) if k else 0., float(beta.ppf(.975,k+1,n-k)) if k<n else 1.]
outcomes = [dict(x, positive_invalid=x['scenario_id']!='S0', classification=label(x['scenario_id']!='S0', x['decision']!='APPROVED')) for x in hist]
table(A/'rq2_outcomes.csv',outcomes)
conf=[]
for s in ['ALL']+sorted({x['scenario_id'] for x in hist}):
    rows=[x for x in outcomes if s=='ALL' or x['scenario_id']==s]
    c=Counter(x['classification'] for x in rows)
    row=dict(scenario=s,n=len(rows),**{k:c[k] for k in ['TP','TN','FP','FN']})
    for name,k,n in [('TPR',c['TP'],c['TP']+c['FN']),('TNR',c['TN'],c['TN']+c['FP']),('FPR',c['FP'],c['FP']+c['TN']),('FNR',c['FN'],c['FN']+c['TP'])]:
        row[name]=k/n if n else ''
        row[name+'_CP95']=json.dumps(cp(k,n)) if n else 'NOT_APPLICABLE'
    conf.append(row)
table(A/'rq2_confusion_matrix.csv',conf)
md('rq2_summary.md',f'''# Fresh historical RQ2 audit
Source: `{histpath.relative_to(ROOT)}`, SHA256 `{sha(histpath)}`.
Verified 30 trials × 8 scenarios = 240 outcomes, positive = invalid/tampered condition.
{json.dumps(conf[0], indent=2)}
Class-stratified exact two-sided Clopper–Pearson intervals are in rq2_confusion_matrix.csv.
Trials reuse a scenario construction; binomial intervals do not establish independent attack diversity.
S1 model weights; S2 tokenizer; S3 dataset manifest; S9a malformed signature plus unauthorized keyid;
S9b unauthorized signer; S9c missing model digest; S9d external model substitution.
SIGNATURE_AUTHENTICITY_NOT_TESTED_BY_S9A: source sets keyid=invalid; authorization precedes ECDSA.
Gate maps UNAUTHORIZED_SIGNER to its authorization failure. Historical decisions alone do not prove cryptographic execution.
New extensions are separate from these 240 outcomes.
''')

# Real normal verifier, isolated local deterministic P-256 fixture key; not production credentials.
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from traceai.provenance.signer import LocalSigner
from traceai.provenance.verifier import LocalVerifier
from traceai.provenance.attestations import create_attestation, create_subject
from traceai.policy.decisions import DeploymentGate
from traceai.policy.engine import PolicyEngine
import traceai.provenance.verifier as verifier_module

signer=LocalSigner(OUT/'unused_key_directory')
signer._private_key=ec.derive_private_key(42,ec.SECP256R1())
signer._public_key=signer._private_key.public_key()
pem=signer.get_public_key_pem()
(OUT/'fixture_public_key.pem').write_text(pem,encoding='ascii')
fingerprint=signer.get_fingerprint()
verifier=LocalVerifier([fingerprint],24)
artifact=OUT/'artifact.bin'
artifact.write_bytes(b'camera-ready-fixed-artifact-v1\n')
digest=sha(artifact)
att=create_attestation([create_subject('approved-model',digest)],digest,source_revision='old-valid-revision',timestamp=NOW)
envelope=signer.sign_json(att)
assert verifier.verify_signature(envelope,pem).approved
gate=DeploymentGate(PolicyEngine({}),verifier)
def deploy(a=att,e=envelope,v=verifier):
    return DeploymentGate(PolicyEngine({}),v).evaluate_deployment(artifact_path=artifact,expected_digest=digest,
        signed_envelope=e,public_key_pem=pem,attestation=a,observed_model_digest=digest)

ext=[]
def record(scenario,trial,result,expected,scope,called='',note=''):
    ext.append(dict(campaign_id=CID,scenario=scenario,trial=trial,decision=result.decision.value,
        approved=result.approved,expected_property=expected,property_enforced=(not result.approved),
        scope=scope,ecdsa_verify_calls=called,note=note,timestamp=NOW))

real_load=serialization.load_pem_public_key
for trial in range(30):
    bad=copy.deepcopy(envelope)
    sig=bytearray.fromhex(bad['signatures'][0]['sig'])
    sig[-1] ^= 1
    bad['signatures'][0]['sig']=sig.hex()
    calls=[]
    class TracedPublicKey:
        def verify(self,*args,**kwargs):
            calls.append(True)
            return real_load(pem.encode()).verify(*args,**kwargs)
    with patch.object(verifier_module.serialization,'load_pem_public_key',return_value=TracedPublicKey()):
        result=verifier.verify_signature(bad,pem)
    assert result.decision.value=='INVALID_SIGNATURE' and len(calls)==1
    assert bad['signatures'][0]['keyid']==fingerprint
    record('CR-SIG',trial,result,'Reject invalid signature','normal LocalVerifier',len(calls),'Fixed mutation; ECDSA nonce is randomized by library, not deterministic.')
    dump(OUT/f'cr_sig_{trial:02d}.json',{'envelope':bad,'result':result.to_dict(),'verify_calls':len(calls)})

# Metadata substituted only in separately supplied attestation; signed payload remains unchanged.
for field in ['artifact_identity','model_identifier','source_revision','security_metadata']:
    a=copy.deepcopy(att)
    if field=='artifact_identity': a['subject'][0]['name']='substituted-artifact'
    elif field=='model_identifier': a['predicate']['traceai']['model_id']='substituted-model'
    elif field=='source_revision': a['predicate']['traceai']['source_revision']='substituted-revision'
    else: a['predicate']['traceai']['policy_version']='substituted-policy'
    r=deploy(a=a)
    record('CR-META-'+field,0,r,'Bind supplied metadata to signed payload','DeploymentGate',note='Artifact bytes and signed envelope unchanged; supplied attestation differs.')
    dump(OUT/f'metadata_{field}.json',{'attestation':a,'envelope':envelope,'result':r.to_dict()})
expired=copy.deepcopy(envelope)
expired['signatures'][0]['timestamp']=(datetime.now(timezone.utc)-timedelta(hours=25)).isoformat()
record('CR-REPLAY-EXPIRED',0,verifier.verify_signature(expired,pem),'Reject evidence older than 24h','LocalVerifier',note='Age uses unsigned envelope timestamp, not signed payload timestamp.')
record('CR-REPLAY-FRESH',0,verifier.verify_signature(envelope,pem),'Reject duplicate evidence','LocalVerifier',note='REPLAY_RESISTANCE_NOT_ENFORCED; baseline verification already consumed identical envelope.')
newatt=copy.deepcopy(att)
newatt['predicate']['traceai']['source_revision']='new-approved-revision'
assert deploy(a=newatt,e=signer.sign_json(newatt)).approved
record('CR-ROLLBACK',0,deploy(),'Reject old revision after new approved','DeploymentGate',note='ROLLBACK_RESISTANCE_NOT_ENFORCED; no approved revision registry input exists.')
record('CR-ALLOWLIST-REMOVAL',0,LocalVerifier(['other-fingerprint'],24).verify_signature(envelope,pem),'Reject removed signer','LocalVerifier',note='Nonempty residual allowlist; demonstrates allowlist removal, not CRL/OCSP.')
record('CR-EMPTY-ALLOWLIST',0,LocalVerifier([],24).verify_signature(envelope,pem),'Reject when last signer removed','LocalVerifier',note='EMPTY_ALLOWLIST_DISABLES_AUTHORIZATION')
compromised=copy.deepcopy(att)
compromised['predicate']['traceai']['source_revision']='attacker-authorized-key'
record('CR-COMPROMISED-AUTHORIZED-KEY',0,deploy(a=compromised,e=signer.sign_json(compromised)),'Reject malicious but authorized signer','DeploymentGate',note='Possession of still-authorized key is outside protection.')
# Supplied public key not bound to asserted allowlisted keyid.
other=LocalSigner(OUT/'unused_other_key_directory')
other._private_key=ec.derive_private_key(43,ec.SECP256R1())
other._public_key=other._private_key.public_key()
forged=other.sign_json(att)
forged['signatures'][0]['keyid']=fingerprint
record('CR-KEYID-BINDING',0,verifier.verify_signature(forged,other.get_public_key_pem()),'Bind keyid to supplied public key','LocalVerifier',note='KEYID_PUBLIC_KEY_BINDING_NOT_ENFORCED; assumes trusted public-key input.')
refreshed=copy.deepcopy(expired)
refreshed['signatures'][0]['timestamp']=NOW
record('CR-UNSIGNED-TIMESTAMP-REFRESH',0,verifier.verify_signature(refreshed,pem),'Authenticate freshness timestamp','LocalVerifier',note='Freshness timestamp is outside signed payload.')
assert sha(artifact)==digest
dump(OUT/'baseline.json',{'attestation':att,'envelope':envelope,'fingerprint':fingerprint,'artifact_sha256':digest})
table(OUT/'outcomes.csv',ext)
table(A/'rq2_extension_outcomes.csv',ext)
ecount=Counter(label(True,not x['approved']) for x in ext)
table(A/'rq2_extension_confusion_matrix.csv',[dict(positive='attempted violation of requested property',n=len(ext),**{k:ecount[k] for k in ['TP','TN','FP','FN']},note='Heterogeneous diagnostic cases; no pooled effectiveness claim or CI.')])
table(A/'rq2_security_property_matrix.csv',[dict(scenario=x['scenario'],enforced=x['property_enforced'],scope=x['scope'],finding=x['note']) for x in ext if x['trial']==0])
md('rq2_camera_ready_extension.md',f'''# Camera-ready RQ2 extension
Campaign `{CID}`; timestamp {NOW}; commit `{commit}`; n={len(ext)}.
Reproduce: `.venv/Scripts/python.exe reviewer_analysis/fresh_audit.py` (creates a NEW campaign).
Historical 240 observations remain separate and unchanged. Raw envelopes/results in `{OUT.relative_to(ROOT)}`.
30 CR-SIG trials reach the normal ECDSA public_key.verify call once each and return INVALID_SIGNATURE.
Deterministic fixture key scalar 42 and fixed one-bit signature mutation; signature nonces are library-randomized.
Other scenarios are one diagnostic each; no population effectiveness inference.
Metadata substitution tests the separate attestation argument, not a modified signed payload. All four fields
are accepted when model_digest remains unchanged: gate does not compare supplied attestation to decoded payload.
Fresh replay and old-revision rollback accepted. Expired envelope rejected at verifier, but its timestamp is unsigned.
Removal from a nonempty allowlist rejects; an empty allowlist ACCEPTS. Not full revocation.
An attacker key with an allowlisted keyid is accepted when caller supplies its public key: fingerprint is not recomputed.
Compromised still-authorized signing key accepted. No production-key-compromise resistance established.
These are measured limitations, not silently repaired controls.
''')

from traceai.campaigns.vex_property import run_vex_property_tests,save_vex_property_results,DECISION_TABLE
prop=run_vex_property_tests(500,42,False)
propdir=ROOT/'results/camera_ready/property_tests'/CID
save_vex_property_results(prop,propdir)
prop.update(commit=commit,oracle_sha256=sha(propdir/'vex_decision_table.json'),generator='random.Random',framework='direct Python invocation')
dump(propdir/'execution.json',prop)
md('property_tests.md',f'''# Fresh randomized policy execution
{prop['agreements']}/500 agreements; {prop['counterexample_count']} counterexamples; seed 42;
timestamp {prop['timestamp']}; commit {commit}. Artifacts `{propdir.relative_to(ROOT)}`.
Generator: random.Random; independent draws schema-valid probability .85, expired .25,
component-match .80, signed .70. Not Hypothesis despite module header.
Oracle: explicit 16-row Boolean truth table; hash {prop['oracle_sha256']}.
Signing not required: unsigned branch cannot yield VEX_UNSIGNED in this 500-case execution.
Oracle and implementation share designed precedence; this is consistency testing, not independent security validation.
Inputs are supplied Boolean flags, not end-to-end VEX parsing or cryptographic verification.
''')

# RQ1 component audit: independently enumerate source nodes and current documents.
gtpath=ROOT/'results/rq1/rq1-20260722-140850-18433df2/ground_truth_graph.json'
gt=read(gtpath)
bompaths=[ROOT/'generated/rq1/final_ml_bom.cdx.json', ROOT/'generated/rq1/final_obom.cdx.json',ROOT/'generated/rq1/syft_direct.cdx.json']
components=[(str(p.relative_to(ROOT)),c) for p in bompaths for c in read(p).get('components',[])]
assets=[]
for n in gt['nodes']:
    nid=n['id']; name=n['name']
    cls={'package':'software','weight':'model','model':'model','tokenizer':'tokenizer','hardware':'hardware','runtime':'runtime'}.get(n['type'],'other')
    if 'config' in nid or 'policy' in nid: cls='configuration'
    elif 'dataset' in nid: cls='dataset'
    aliases={'os-platform':['windows'],'host-cpu':['cpu'],'host-ram':['ram','memory'],'python-runtime':['cpython','python'],'traceai-app':['traceai-inference'],'inference-service':['traceai-inference'],'policy-config':['policy.yaml'],'runtime-snapshot':['process-snapshot']}.get(nid,[])
    matches=[(p,c) for p,c in components if c.get('name','').lower() in [name.lower()]+aliases or c.get('bom-ref')==nid]
    applicable=n.get('applicability')!='NOT_APPLICABLE'
    assets.append(dict(node_id=nid,name=name,asset_class=cls,applicable=applicable,represented=bool(matches),first_class_component=bool(matches),property_only=False,cyclonedx_representable='yes',implementation_gap='no exact/explicit alias component match' if applicable and not matches else '',source=str(gtpath.relative_to(ROOT)),matched_components=';'.join(p+'#'+c.get('bom-ref',c.get('name','')) for p,c in matches),reference_type=n['type']))
table(A/'rq1_asset_inventory.csv',assets)
classrows=[]
for cls in sorted({x['asset_class'] for x in assets}):
    aa=[x for x in assets if x['asset_class']==cls and x['applicable']]
    classrows.append(dict(asset_class=cls,reference=len(aa),represented=sum(x['represented'] for x in aa),coverage=sum(x['represented'] for x in aa)/len(aa) if aa else 'N/A'))
table(GEN/'rq1_component_match_summary.csv',classrows)
metrics=read(ROOT/'generated/rq1/final_metrics.json')
md('rq1_summary.md',f'''# Fresh RQ1 audit: BLOCKED BY CONFLICTING LINEAGE
Enumerated {len(gt['nodes'])} historical reference nodes; applicable {sum(x['applicable'] for x in assets)}.
No numerator derived from a percentage. Independent conservative component matching table is rq1_asset_inventory.csv.
Current final_metrics.json reports {metrics.get('composite_matched')}/{metrics.get('composite_applicable')} = {metrics.get('composite_coverage')}.
final_rq1_summary.tex reports 27/29; unmatched_nodes_after.csv lists os-platform and host-cpu.
Both are first-class components in CURRENT final_obom.cdx.json (obom-os and obom-cpu).
Do not certify 27/29 as the current result or silently replace it with 29/29: reconcile the campaign/finalizer universe first.
Ground-truth universe, finalizer reclassification, and regenerated documents need explicit methodological review.
host-gpu and cuda-runtime are NOT_APPLICABLE in this CPU reference graph; host-ram must be matched from actual component records.

Asset class | Reference | Represented | Coverage
---|---:|---:|---:
'''+'\n'.join(f"{r['asset_class']} | {r['reference']} | {r['represented']} | {r['coverage']}" for r in classrows)+'''

inventory representation coverage != security coverage.
Missing reference assets can include attack surfaces; the project-defined universe does not prove completeness for modern AI systems.
''')

# Exact historical scanner set operations; explicit aliases only, no external database refresh.
rp=ROOT/'results/rq3/rq3-20260722-140819-082e9531/raw'
t=read(rp/'trivy_scan_results.json'); g=read(rp/'grype_scan_results.json')
parent={}
def find(x):
    parent.setdefault(x,x)
    if parent[x]!=x: parent[x]=find(parent[x])
    return parent[x]
def union(a,b):
    parent[find(b)]=find(a)
T=[]; G=[]
norm=lambda s: re.sub(r'[-_.]+','-',s.lower())
for result in t.get('Results',[]):
    for v in result.get('Vulnerabilities') or []:
        vid=v['VulnerabilityID']; find(vid)
        for alias in v.get('VendorIDs') or []: union(vid,alias)
        T.append((norm(v['PkgName']),v.get('InstalledVersion',''),vid))
for m in g.get('matches',[]):
    vid=m['vulnerability']['id'];find(vid)
    for alias in m.get('relatedVulnerabilities',[]): union(vid,alias['id'])
    G.append((norm(m['artifact']['name']),m['artifact'].get('version',''),vid))
classes=defaultdict(list)
for vid in parent: classes[find(vid)].append(vid)
canonical={root:sorted(members,key=lambda s:(not s.startswith('CVE-'),not s.startswith('GHSA-'),s))[0] for root,members in classes.items()}
def canon(rows):return {(p,v,canonical[find(i)]) for p,v,i in rows}
def agreement(a,b):return dict(trivy=len(a),grype=len(b),intersection=len(a&b),union=len(a|b),trivy_only=len(a-b),grype_only=len(b-a),jaccard=len(a&b)/len(a|b) if a|b else None)
sets=[dict(basis='raw_package_version_advisory',**agreement(set(T),set(G))),dict(basis='canonical_package_version_advisory',**agreement(canon(T),canon(G))),dict(basis='raw_advisory_only',**agreement({i for _,_,i in T},{i for _,_,i in G}))]
table(A/'rq3_scanner_agreement.csv',sets)
table(A/'rq3_discrepancies_by_component.csv',[dict(component=p,**agreement({x for x in canon(T) if x[0]==p},{x for x in canon(G) if x[0]==p})) for p in sorted({x[0] for x in T+G})])
table(GEN/'scanner_finding_sets.csv',[dict(scanner=s,package=p,version=v,advisory=i,canonical=canonical[find(i)]) for s,rows in [('trivy',T),('grype',G)] for p,v,i in rows])
dump(GEN/'scanner_embedded_metadata.json',{'trivy':{k:v for k,v in t.items() if k!='Results'},'grype':{k:v for k,v in g.items() if k!='matches'}})
md('rq3_summary.md',f'''# Fresh historical scanner recomputation
Raw source: `{rp.relative_to(ROOT)}`. Raw finding records: Trivy {len(T)}, Grype {len(G)}.
{json.dumps(sets,indent=2)}
Deduplication: set of (PEP503 normalized Python package name, exact installed version, advisory id).
Alias normalization: union-find using ONLY Trivy VendorIDs and Grype relatedVulnerabilities.
Each equivalence class counted once per package/version. Canonical ID prefers CVE then GHSA.
PURLs retained in raw scanner files; this matching rule uses package/version, not claimed universal PURL equivalence.
Embedded scanner metadata copied to generated/camera_ready/{CID}/scanner_embedded_metadata.json.
Exact historical tool and DB metadata absent from embedded fields must be marked unavailable; current versions cannot replace historical versions.
Do not infer agreement from record totals or inflate intersection by counting both GHSA and CVE aliases.
''')

# CPU raw data: no simulation, aggregation is a separate derivative.
import numpy as np
metricsrows=[];trialrows=[]
for path in sorted((ROOT/'results/rq4').rglob('raw_requests.csv')):
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
    if not rows:continue
    manifestpath=path.parent/'campaign_manifest.json'
    manifest=read(manifestpath) if manifestpath.exists() else {}
    gpu=manifest.get('gpu','UNKNOWN')
    if gpu!='NOT_APPLICABLE':continue
    def aggregate(rr):
        good=[r for r in rr if str(r.get('status_code'))=='200' and r.get('rejected','').lower()!='true']
        lat=np.array([float(r['latency_ms']) for r in good]); tokens=[float(r['tokens_generated']) for r in good if r.get('tokens_generated')]
        stamps=[datetime.fromisoformat(r['timestamp']).timestamp() for r in rr]
        ends=[datetime.fromisoformat(r['timestamp']).timestamp()+float(r['latency_ms'])/1000 for r in rr]
        duration=max(ends)-min(stamps) if stamps else 0
        return dict(count=len(rr),success=len(good),rejection=sum(r.get('rejected','').lower()=='true' for r in rr),rejection_rate=sum(r.get('rejected','').lower()=='true' for r in rr)/len(rr),
            throughput_success_per_s=len(good)/duration if duration else '',throughput_basis='derived span: timestamp to timestamp+latency; includes trial gaps; timestamp convention unverified',
            median_ms=float(np.median(lat)) if len(lat) else '',p95_ms=float(np.percentile(lat,95)) if len(lat) else '',mean_ms=float(np.mean(lat)) if len(lat) else '',std_ms=float(np.std(lat,ddof=1)) if len(lat)>1 else '',iqr_ms=float(np.percentile(lat,75)-np.percentile(lat,25)) if len(lat) else '',
            tokens_mean=float(np.mean(tokens)) if tokens else '',tokens_min=min(tokens) if tokens else '',tokens_max=max(tokens) if tokens else '',tokens_total=sum(tokens),
            cpu_percent_mean=float(np.mean([float(r['cpu_percent']) for r in rr if r.get('cpu_percent')])) if any(r.get('cpu_percent') for r in rr) else '',evidence='CPU EVIDENCE',source=str(path.relative_to(ROOT)))
    for cfg in sorted({r['configuration_id'] for r in rows}):
        rr=[r for r in rows if r['configuration_id']==cfg]
        metricsrows.append(dict(campaign_id=path.parent.name,configuration=cfg,**aggregate(rr)))
        for trial in sorted({r['trial_id'] for r in rr}):
            trialrows.append(dict(campaign_id=path.parent.name,configuration=cfg,trial=trial,**aggregate([r for r in rr if r['trial_id']==trial])))
table(A/'rq4_metrics_by_config.csv',metricsrows)
table(A/'rq4_metrics_by_trial.csv',trialrows)
md('rq4_summary.md',f'''# Fresh RQ4 audit
CPU EVIDENCE: recomputed {len(metricsrows)} campaign/configuration rows from manifest-confirmed NOT_APPLICABLE GPU campaigns.
Latency statistics use successful status-200, nonrejected requests; np.percentile default linear interpolation.
Throughput is explicitly DERIVED from timestamp/latency spans; not a measured campaign wall-clock throughput.
Requests rejected by controls are separate from completed inference. Trial-level metrics retained.
PAPER_PRIMARY_GPU_CAMPAIGN_NOT_FOUND: generated/gpu contains a validation report, not raw L4 campaign observations.
No real L4 campaign has been established by this audit. GPU test still required.
Do not reuse prior report's config/experiment.yaml table for rq4.py campaigns: rq4.py C3 threshold=3, cooldown=5s;
config/experiment.yaml is a separate configuration source. Historical effective config requires per-campaign logs.
No parameter-matched overhead estimate established: C0 and C1 change max_new_tokens (50 vs 20 in rq4.py).
''')

# Full file inventory (hashes, no secrets read into reports).
table(GEN/'file_inventory.csv',[dict(path=k,bytes=(ROOT/k).stat().st_size,SHA256=v) for k,v in sorted(baseline.items())])
md('file_inventory.md',f'''# Fresh file audit
Recursive audit roots: results/, generated/, workspace/, config/, src/, tests/, scripts/, fixtures/.
{len(baseline)} historical files hashed; full inventory generated/camera_ready/{CID}/file_inventory.csv.
Fixtures are synthetic by construction; tests with monkeypatch/mock are not device measurements.
Configuration and generated tables are not raw observations. Existing reviewer_analysis reports predate this audit;
copies preserved under generated/camera_ready/{CID}/prior_analysis/.
No main.tex or .bib found in repository recursive search (excluding .git and virtual environments).
''')
campaigns=[]
for p in sorted((ROOT/'results').rglob('*manifest.json')):
    if 'camera_ready' in p.parts:continue
    try:m=read(p)
    except Exception:continue
    rawpaths=[q for q in p.parent.rglob('*') if q.is_file() and (q.suffix=='.csv' or q.name.endswith('results.json'))]
    classification='UNKNOWN'
    gpu=m.get('gpu',m.get('gpu_name','UNKNOWN'))
    device=m.get('device','UNKNOWN')
    if m.get('inference_type')=='REAL_HTTP' and gpu=='NOT_APPLICABLE':classification='CPU_DIAGNOSTIC'
    if classification=='CPU_DIAGNOSTIC' and 'stress' in str(p):classification='CPU_STRESS'
    if 'security-' in str(p) and rawpaths:classification='HISTORICAL_REAL'
    campaigns.append(dict(campaign_id=m.get('campaign_id',p.parent.name),path=str(p.parent.relative_to(ROOT)),rq=m.get('campaign_type','UNKNOWN'),timestamp=m.get('timestamp','UNKNOWN'),device=device,gpu=gpu,model=m.get('model_id','UNKNOWN'),revision=m.get('model_revision',m.get('revision','UNKNOWN')),trial_count=m.get('trials','UNKNOWN'),request_count=m.get('total_observations','UNKNOWN'),fault_count=m.get('fault_count','UNKNOWN'),raw_data_present=bool(rawpaths),mocked='UNVERIFIED',classification=classification,notes='Manifest declarations require raw-observation corroboration; not certified GPU evidence.'))
table(A/'campaign_inventory.csv',campaigns,['campaign_id','path','rq','timestamp','device','gpu','model','revision','trial_count','request_count','fault_count','raw_data_present','mocked','classification','notes'])
table(A/'rq4_campaign_inventory.csv',[r for r in campaigns if 'rq4' in r['path']])

changed=[k for k,v in baseline.items() if sha(ROOT/k)!=v]
assert not changed, changed
dump(GEN/'historical_integrity_check.json',{'timestamp':datetime.now(timezone.utc).isoformat(),'files_checked':len(baseline),'changed':changed,'status':'PASS'})
dump(OUT/'campaign_manifest.json',{'campaign_id':CID,'timestamp':NOW,'commit':commit,'n':len(ext),'historical_n':240,'classification':'CAMERA_READY_EXTENSION','deterministic_fixture_key_scalar':42,'signature_nonce':'library-randomized','property_tests':str(propdir.relative_to(ROOT))})
dump(GEN/'audit_summary.json',{'campaign_id':CID,'commit':commit,'rq2_original':conf[0],'extension_n':len(ext),'extension_counts':dict(ecount),'property_agreements':prop['agreements'],'rq3':sets,'historical_files_unchanged':len(baseline),'main_tex_found':False})
print(json.dumps(read(GEN/'audit_summary.json'),indent=2))
