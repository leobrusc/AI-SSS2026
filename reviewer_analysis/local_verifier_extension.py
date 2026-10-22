import sys,json,csv,copy,hashlib,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
sys.path.insert(0,str(Path.cwd()/'src'))
from traceai.provenance.signer import LocalSigner
from traceai.provenance.verifier import LocalVerifier
from traceai.provenance.attestations import create_attestation,create_subject
from traceai.policy.engine import PolicyEngine
from traceai.policy.decisions import DeploymentGate
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from traceai.campaigns.vex_property import run_vex_property_tests,save_vex_property_results
cid='cr-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
out=Path('results/camera_ready/rq2_extension')/cid;out.mkdir(parents=True)
s=LocalSigner(out/'unused');s._private_key=ec.derive_private_key(42,ec.SECP256R1());s._public_key=s._private_key.public_key()
pem=s.get_public_key_pem();fp=s.get_fingerprint();v=LocalVerifier([fp],24)
p=out/'artifact.bin';p.write_bytes(b'fixed camera-ready artifact');digest=hashlib.sha256(p.read_bytes()).hexdigest()
a=create_attestation([create_subject('model',digest)],digest,source_revision='old');e=s.sign_json(a)
rows=[]
def rec(name,r,calls='',note=''):
 rows.append(dict(campaign_id=cid,scenario=name,decision=r.decision.value,approved=r.approved,verify_calls=calls,note=note))
def gate(a=a,e=e):
 return DeploymentGate(PolicyEngine({}),v).evaluate_deployment(artifact_path=p,expected_digest=digest,signed_envelope=e,public_key_pem=pem,attestation=a,observed_model_digest=digest)
assert gate().approved
load=serialization.load_pem_public_key
for i in range(30):
 b=copy.deepcopy(e);sig=bytearray.fromhex(b['signatures'][0]['sig']);sig[-1]^=1;b['signatures'][0]['sig']=sig.hex();calls=[]
 class Proxy:
  def verify(self,*args,**kw):
   calls.append(True);return load(pem.encode()).verify(*args,**kw)
 with patch('traceai.provenance.verifier.serialization.load_pem_public_key',return_value=Proxy()):r=v.verify_signature(b,pem)
 assert r.decision.value=='INVALID_SIGNATURE' and len(calls)==1
 rec('CR-SIG',r,len(calls),str(i));(out/f'sig-{i}.json').write_text(json.dumps({'envelope':b,'result':r.to_dict(),'verify_calls':len(calls)},indent=2))
for field in ['artifact_identity','model_identifier','source_revision','security_metadata']:
 b=copy.deepcopy(a)
 if field=='artifact_identity':b['subject'][0]['name']='other'
 else:b['predicate']['traceai'][{'model_identifier':'model_id','source_revision':'source_revision','security_metadata':'policy_version'}[field]]='substituted'
 rec('CR-META-'+field,gate(a=b),note='Separate attestation changed; envelope and artifact unchanged')
 (out/f'meta-{field}.json').write_text(json.dumps({'attestation':b,'envelope':e},indent=2))
b=copy.deepcopy(e);b['signatures'][0]['timestamp']=(datetime.now(timezone.utc)-timedelta(hours=25)).isoformat();rec('CR-REPLAY-EXPIRED',v.verify_signature(b,pem),note='Unsigned envelope timestamp')
rec('CR-REPLAY-FRESH',v.verify_signature(e,pem),note='REPLAY_RESISTANCE_NOT_ENFORCED')
b=copy.deepcopy(a);b['predicate']['traceai']['source_revision']='new-approved';assert gate(a=b,e=s.sign_json(b)).approved
rec('CR-ROLLBACK',gate(),note='ROLLBACK_RESISTANCE_NOT_ENFORCED; gate has no current-revision registry')
rec('CR-ALLOWLIST-REMOVAL',LocalVerifier(['residual-other-key'],24).verify_signature(e,pem),note='Allowlist removal only; not full revocation')
rec('CR-EMPTY-ALLOWLIST',LocalVerifier([],24).verify_signature(e,pem),note='Empty set disables authorization')
b=copy.deepcopy(a);b['predicate']['traceai']['source_revision']='attacker';rec('CR-COMPROMISED-AUTHORIZED-KEY',gate(a=b,e=s.sign_json(b)))
s2=LocalSigner(out/'unused2');s2._private_key=ec.derive_private_key(43,ec.SECP256R1());s2._public_key=s2._private_key.public_key();b=s2.sign_json(a);b['signatures'][0]['keyid']=fp
rec('CR-KEYID-BINDING',v.verify_signature(b,s2.get_public_key_pem()),note='Claimed keyid not recomputed from supplied key')
b=copy.deepcopy(e);b['signatures'][0]['timestamp']=(datetime.now(timezone.utc)-timedelta(hours=25)).isoformat();assert not v.verify_signature(b,pem).approved;b['signatures'][0]['timestamp']=datetime.now(timezone.utc).isoformat();rec('CR-UNSIGNED-TIMESTAMP-REFRESH',v.verify_signature(b,pem),note='Timestamp refresh accepted without resigning')
for path in [out/'outcomes.csv',Path('reviewer_analysis/rq2_extension_outcomes.csv')]:
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(out/'baseline.json').write_text(json.dumps({'attestation':a,'envelope':e,'fingerprint':fp,'public_key':pem},indent=2))
(out/'campaign_manifest.json').write_text(json.dumps({'campaign_id':cid,'timestamp':datetime.now(timezone.utc).isoformat(),'n':len(rows),'key_fixture_scalar':42,'nonce':'library randomized','classification':'CAMERA_READY_EXTENSION'},indent=2))
pr=run_vex_property_tests(500,42,False);po=Path('results/camera_ready/property_tests')/cid;save_vex_property_results(pr,po);pr['oracle_sha256']=hashlib.sha256((po/'vex_decision_table.json').read_bytes()).hexdigest();(po/'execution.json').write_text(json.dumps(pr,indent=2))
print(json.dumps({'campaign_id':cid,'extension_n':len(rows),'outcomes':rows,'property_agreements':pr['agreements'],'counterexamples':pr['counterexample_count']},indent=2))
