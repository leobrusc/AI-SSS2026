from pathlib import Path
import csv,json,hashlib,shutil,re,sys
from datetime import datetime,timezone
R=Path.cwd();A=R/'reviewer_analysis';cid='cr-20261020T223734Z-ffdfff82';G=R/'generated/camera_ready'/cid
NOW=datetime.now(timezone.utc).isoformat()
def md(n,t):(A/n).write_text(t.strip()+'\n',encoding='utf-8')
def table(n,rows,fields=None):
 with (A/n).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
md('trust_model.md','''# Implemented trust model and measured limitations
Source: src/traceai/provenance/{signer,verifier,attestations}.py and policy/decisions.py.

Property | Status | Evidence
---|---|---
ECDSA P-256 / SHA-256 | IMPLEMENTED | SECP256R1; ECDSA(hashes.SHA256())
SHA-256 public-key fingerprint | IMPLEMENTED | DER SubjectPublicKeyInfo hash truncated to 32 hex characters (128 bits)
Key generation | IMPLEMENTED | ec.generate_private_key; local persisted key reused unless force_new
Key persistence | IMPLEMENTED | workspace/keys/ephemeral.key.pem, unencrypted PKCS8; public SPKI PEM
Authorized signer set | PARTIAL | compares caller-provided keyid string; does not recompute public-key fingerprint; empty list allows all
Freshness | PARTIAL | optional unsigned envelope timestamp; missing/malformed timestamp bypasses expiry
Rotation | ASSUMED | operator must distribute new public key and nonempty allowlist; no lifecycle service
Allowlist removal | IMPLEMENTED WITH LIMITATION | measured removal from nonempty list rejects; removal of last key to empty list accepts
Full revocation / CRL / OCSP / PKI | NOT_IMPLEMENTED | no certificate-chain/revocation verification in LocalVerifier
KMS/HSM | NOT_IMPLEMENTED | local software keys only

Trust anchors are operator-provided public-key material and authorization configuration, assumed authentic and protected.
The verifier does not establish the binding between those two inputs itself. The trusted computing base includes
host, Python process, artifact access, policy configuration and evidence producer. Descriptive BOM records are not active controls.
Compromised but still-authorized signing key can sign malicious evidence that verifies: measured in camera-ready extension.
No identity-of-builder, semantic backdoor, hostile runtime, compromised-host, or tail-latency guarantee follows.
The separately supplied attestation is not compared to decoded signed payload; metadata substitution was accepted.
Unsigned timestamp modification can refresh old evidence. No anti-replay store or monotonic revision registry exists.
These limitations are not repaired by the audit. Historical real signature-verification outcomes are fixture tests, not production trust assurance.
''')
md('security_invariants.md','''# Deployment-gate invariants
YES/PARTIAL/NO refers to implemented enforcement at the named boundary, not architecture intent.

Invariant | Enforcement | Implemented | Tested | Source function | Experiment | Failure behavior and limits
---|---|---|---|---|---|---
INV-1 artifact identity | PARTIAL | digest equality | YES | DeploymentGate.evaluate_deployment | S1/S2/S3/S9d; CR-META | bytes rejected on expected-digest mismatch; subject name/model id not bound
INV-2 signature authenticity | YES | P-256 SHA256 payload verification | YES | LocalVerifier.verify_signature | 30 CR-SIG | INVALID_SIGNATURE; caller public key assumed trusted; payload type not signed
INV-3 signer authorization | PARTIAL | nonempty keyid allowlist | YES | LocalVerifier.verify_signature | S9a/S9b; CR-ALLOWLIST-REMOVAL; CR-KEYID-BINDING | UNAUTHORIZED_SIGNER; empty set permits all; supplied key not bound to keyid
INV-4 evidence completeness | PARTIAL | nonempty subject and model_digest | YES | verify_attestation_completeness | S9c | MISSING_ATTESTATION; not full predicate/schema validation
INV-5 freshness | PARTIAL | age of envelope timestamp | YES | verify_signature | CR-REPLAY-EXPIRED; CR-UNSIGNED-TIMESTAMP-REFRESH | STALE_EVIDENCE at verifier; gate collapses to INVALID_SIGNATURE; unsigned/missing timestamp bypass
INV-6 cross-document consistency | PARTIAL | model_digest equals supplied observed value | YES | evaluate_deployment | CR-META | ATTESTATION_DIGEST_MISMATCH; independent attestation not tied to signed payload; not universal graph validation
INV-7 VEX applicability | PARTIAL | supplied schema/expiry/component/signature flags | YES | PolicyEngine.evaluate_vex | randomized 500; test_vex | first failed flag denies; suppression function matches vulnerability ID without component check
INV-8 approved/effective configuration | PARTIAL | optional digest comparison | YES | check_configuration_drift; evaluate_deployment | test_policy_engine | CONFIGURATION_DRIFT if both digests supplied; no automatic gate revalidation on runtime update
INV-9 runtime attribution | PARTIAL | request/trial/configuration identifiers | PARTIAL | rq4._send_one_async; service telemetry | historical raw CSV | associations are not signed runtime proof; prompt content not automatically gated
INV-10 rollback/revision consistency | NO | no monotonic revision rule | YES | evaluate_deployment | CR-ROLLBACK | old approved after new; ROLLBACK_RESISTANCE_NOT_ENFORCED

Proposed stronger invariants: authenticate timestamp; derive authorized public key from trusted key registry;
parse attestation solely from authenticated payload; verify all evidence links/digests; enforce current revision;
revalidate mutable AI state. These are FORMAL MODEL PROPOSED FOR PAPER, not implemented properties.
''')
md('evidence_graph_schema.md','''# Actual graph versus proposed formal model
ACTUAL IMPLEMENTED GRAPH: CycloneDX component arrays with local bom-ref and dependency ref/dependsOn;
BomLinkBuilder stores source/target serialNumber/type and relationship; attestations store named SHA-256
subjects and traceai digest/revision/policy fields; VEX affects refs name components; requests carry trial/config IDs.
Identity rules include PURL where available, component name/version, document serialNumber/version and bom-ref,
model repository plus requested revision, and byte SHA-256. These have different scopes and are not interchangeable.
Verifier checks byte digests and selected model_digest; it does not validate every edge across all documents.
Evidence graph CSVs below extract actual component/dependency/attestation edges from files, with source paths.

FORMAL MODEL PROPOSED FOR PAPER: G=(V,E), V partitioned into artifact, evidence, decision, runtime-observation nodes.
An edge is a typed relation present in evidence; missing edges remain absent. A proposed approved decision would
require authenticated subject binding, authorized signer, fresh complete evidence, digest agreement and applicable policy.
The current gate only enforces a subset (security_invariants.md); G is an explanatory formalization, not a deployed graph database.
No signature or provenance edge is inferred from adjacency or BOM-Link alone.
''')
nodes=[];edges=[]
for path in [R/'generated/rq1/final_ml_bom.cdx.json',R/'generated/rq1/final_obom.cdx.json',R/'generated/rq1/syft_direct.cdx.json']:
 d=load(path);doc=str(path.relative_to(R));nodes.append(dict(id=doc,node_class='evidence',identity=d.get('serialNumber',''),source=doc))
 for c in d.get('components',[]):
  key=doc+'#'+c.get('bom-ref',c.get('name',''));nodes.append(dict(id=key,node_class='artifact',identity=json.dumps({k:c[k] for k in ['name','version','purl','hashes'] if k in c}),source=doc));edges.append(dict(source=doc,target=key,relation='contains',evidence=doc))
 for dep in d.get('dependencies',[]):
  for target in dep.get('dependsOn',[]):edges.append(dict(source=doc+'#'+dep['ref'],target=doc+'#'+target,relation='dependsOn',evidence=doc))
for path in (R/'workspace').rglob('*.json'):
 try:d=load(path)
 except Exception:continue
 if isinstance(d,dict) and d.get('_type')=='https://in-toto.io/Statement/v1':
  doc=str(path.relative_to(R));nodes.append(dict(id=doc,node_class='evidence',identity=d.get('predicateType',''),source=doc))
  for s in d.get('subject',[]):
   ident='sha256:'+s.get('digest',{}).get('sha256','');nodes.append(dict(id=ident,node_class='artifact',identity=s.get('name',''),source=doc));edges.append(dict(source=doc,target=ident,relation='subject',evidence=doc))
table('evidence_graph_nodes.csv',nodes);table('evidence_graph_edges.csv',edges)
md('vex_policy_semantics.md','''# VEX policy semantics from current implementation
Sources: vulnerability/vex.py; policy/engine.py; config/policy.yaml; campaigns/vex_property.py.
Fields parsed: vulnerability id, analysis.state, justification/detail/response, affects[].ref.
Owner: not required or authenticated. issued_at: optional metadata timestamp. expires: custom traceai:expires property.
VexDocument.is_expired returns false without metadata.timestamp and only checks traceai:expires when present.
max_vex_age_hours=720 occurs in policy YAML but is not read by the implementation (repository search).
Signature: evaluate_vex takes a caller Boolean; does not itself cryptographically verify VEX.
Component matching: check_component_linkage matches refs; evaluate_vex takes a Boolean; apply_vex_to_findings
only matches advisory ID, not finding component. A separate applicability gate must be correctly invoked.

Input | Actual behavior
---|---
affected | finding retained
not_affected | matching vulnerability ID suppressed; component check is not performed by suppression function
fixed | retained (not auto-suppressed)
under_investigation | retained
unknown | retained; not automatically failure of evaluate_vex
expired | rejects only if caller passes vex_expired; parser uses custom expiry as above
unsigned | rejects only when require_signature=true
wrong-component | rejects if caller supplies mismatch and policy enabled
conflicting | get_status_for_vulnerability uses first matching statement; no owner/time-based conflict resolution

Policy precedence: malformed schema, expiry, component, signature. Default signing requirement false.
Full deployment gate first failure: artifact, digest, signature, authorization, attestation completeness,
attestation digest, freshness, configuration, optional VEX, vulnerability threshold. Gate currently sets
vulnerabilities_acceptable=true and does not establish scanner-to-threshold enforcement itself.
Existing focused unit tests exercised parsing/linkage/policy; randomized 500 test supplies flags and does not test ownership or real signatures.
Proposed owner, validity-period, alias-aware component applicability and conflict resolution rules must be labeled architectural.
''')
md('model_precision.md','''# Model precision: code configuration versus observed evidence
Full source/config/script search finds inference.py chooses torch.float32 on CPU and torch.float16 otherwise,
passed as torch_dtype to AutoModelForCausalLM.from_pretrained, then .to(device).eval().
No load_in_8bit/load_in_4bit, bitsandbytes, GPTQ, AWQ or quantization_config setup found.
No explicit quantization or compression pipeline is implemented in inspected loader.
This is CODE CONFIGURATION, not proof of the dtype of historical campaign tensors.
Historical CPU raw CSV does not record dtype; no real CUDA campaign tensor/dtype observation found.
The loader's resolved_revision falls back to requested revision when config._commit_hash missing;
a fallback value does not independently establish downloaded artifact provenance.
GPU run must capture parameter dtype, parameter device, config._commit_hash and requested revision directly.
''')
md('mutable_ai_state.md','''# Mutable AI state
State | Tracking | Change behavior | Source
---|---|---|---
Request prompts | PARTIALLY_TRACKED | prompt index/corpus hash in current rq4 runner; no automatic evidence regeneration or gate invalidation on arbitrary prompt change | rq4.PROMPTS and trial_manifest
System prompts | NOT_TRACKED | no separate attested system-prompt lifecycle | no implementation found
Prompt templates | NOT_TRACKED | no template version/digest gate | no implementation found
Temperature/sampling | PARTIALLY_TRACKED | inference generate accepts temperature/seed; not universal approved-config digest binding | service/inference.py
Generation configuration file | PARTIALLY_TRACKED | inventory includes generation_config.json; digest effects depend on explicit regeneration | BOM builder/finalizer
Runtime limits | PARTIALLY_TRACKED | configuration endpoint digest and update events; automatic re-attestation/gate invalidation absent | service/app.py; controls.py
LoRA/PEFT/adapters | NOT_TRACKED | no load/version/revalidation lifecycle | repository search
Retrieval indexes/RAG corpora | NOT_TRACKED | no corpus/index update gate | repository search
Guardrails | NOT_TRACKED | no separately attested guardrail lifecycle | repository search
Plugins/tools | NOT_TRACKED | no tool registry/digest gate | repository search

Changes can occur faster than static BOM regeneration. The architecture would need explicit immutable revisions,
artifact digests and revalidation hooks for each surface; the prototype does not provide them automatically.
Inventory representation coverage != security coverage. A high percentage over this fixed reference universe
says nothing about omitted prompts, adapters, retrieval sources, tools, guardrails or their security significance.
''')
md('proposed_matched_overhead_experiment.md','''# Matched experiment proposal (not executed)
No existing experiment found with all required matching variables and only security treatment changed.
C0-C1 changes generation token cap; C1-C2 changes concurrency/queue/rate; these cannot isolate control cost.
DeploymentGate evaluates artifact/evidence at deployment/test time. service/app.py request handler does not
run ECDSA/attestation checks per request. Do not describe deployment verification as per-request overhead.

Deployment experiment: immutable artifact/evidence; randomized paired order of verification treatment;
report verification latency separately by digest/signature/attestation/policy, cold/warm cache and repeats.
Request-path experiment: same model/revision, exact prompt corpus/order, seed, temperature, max_new_tokens,
timeout, concurrency, queue, hardware and load schedule; only selected runtime-control code treatment differs.
Use independent paired trials, record tokens/outcomes and client/server monotonic times, warmup, CPU/GPU resources;
report paired differences and uncertainty intervals. Preserve rejected requests separately.
If treatment changes behavior, report that difference alongside timing instead of selecting successful requests silently.
No overhead result is presently supported.
''')
md('generalizability.md','''# Generalizability boundary
Verified evidence consists of local synthetic artifact policy/signature tests, scanner output on a deliberately
vulnerable Python fixture, and CPU diagnostic/stress request files. The project-defined inventory is one organization/context.
No real NVIDIA L4 campaign bundle found. No empirical evidence established for larger models, alternate architectures,
AMD, heterogeneous accelerators, multi-GPU, Linux inference, containers or Kubernetes. Configuration files/docker
recipes and mocked GPU unit tests are CONFIG_ONLY or UNIT_TEST_OUTPUT, not evaluated deployment platforms.
No production-scale, semantic-backdoor resistance, broad security coverage, matched overhead or tail-latency guarantee.
Observed p95 over a small sample is descriptive and does not establish production tail behavior.
''')
md('reference_validation.md','''# Reference validation
No main.tex, bibliography (.bib), or complete manuscript was found recursively in this repository.
Cannot enumerate or verify every citation, authors, venue, DOI or year. Manual/source-manuscript verification required.
Primary technical sources consulted 2026-10-20:
- CycloneDX ML-BOM: https://www.cyclonedx.org/capabilities/mlbom/
- in-toto Envelope specification: https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md
These are documentation sources, not invented bibliographic entries. No citation keys added.
''')
md('technical_comparison.md','''# Technical comparison for a future manuscript revision
CycloneDX AI/ML-BOM represents model/dataset/configuration inventory and descriptive provenance;
it does not by itself execute an artifact admission policy. Repository final ML-BOM uses components and custom traceai properties.
Source: https://www.cyclonedx.org/capabilities/mlbom/ (consulted 2026-10-20).
BOM-Link cross-references inventories; local BomLinkBuilder stores serial-number source/target relationships.
VEX represents contextual vulnerability status; local parser and separate policy flags do not authenticate an owner's risk judgment.
in-toto Statement binds subjects/digests to a predicate; the local statement uses a custom traceai predicate.
The local envelope signs canonical JSON payload bytes, uses hex signatures and application/json payloadType;
it does not sign payloadType and must not be called conformant DSSE verification.
Source: https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md (consulted 2026-10-20).
An in-toto-style Statement is not evidence of full in-toto layout/step authorization or supply-chain verification.
The central contribution remains orchestration and operational association of evidence and controls, bounded by implemented checks.
''')
# Append exact embedded historical scanner metadata.
meta=load(G/'scanner_embedded_metadata.json');desc=meta['grype']['descriptor']
with (A/'rq3_summary.md').open('a',encoding='utf-8') as f:f.write('\nHistorical embedded tool/DB metadata: Trivy '+meta['trivy']['Trivy']['Version']+'; created '+meta['trivy']['CreatedAt']+'; Trivy DB timestamp/version NOT RECORDED in report. Grype '+desc['version']+'; '+json.dumps(desc.get('db',{}))+'; scan timestamp '+desc.get('timestamp','UNKNOWN')+'. Target: CycloneDX vulnerable-project fixture, not deployed production environment.\n')
# Replace stale circuit timeline with raw observed events only; never invent state transitions.
tl=[]
for p in (R/'results/rq4').rglob('service_events.jsonl'):
 for line in p.read_text(encoding='utf-8-sig').splitlines():
  try:e=json.loads(line)
  except Exception:continue
  tl.append(dict(campaign_id=p.parent.name,event=e.get('event','UNKNOWN'),timestamp=e.get('timestamp',e.get('time','UNKNOWN')),classification='OBSERVED',source=str(p.relative_to(R)),detail=json.dumps(e)))
table('circuit_breaker_timeline.csv',tl,['campaign_id','event','timestamp','classification','source','detail'])
md('circuit_breaker_summary.md','''# Circuit-breaker evidence audit
Timeline extracts actual JSONL event records only; a successful recovery request is not an observed CLOSED transition.
Historical stress service_events.jsonl logs circuit_recovery_test with outcome COMPLETED; no native HALF_OPEN/CLOSED state event established.
Exact fault-detection latency and state recovery duration cannot be certified from sparse request-only logs.
Current rq4.py config C3 threshold=3 cooldown=5s; config/experiment.yaml threshold=5 cooldown=30s is a different source.
scripts/phase3_rq4_controls.py explicitly overrides timeout to 3s for recovery; it does not establish historical threshold via request count.
Prior timeline's 'failure 1/5' annotations and inferred transitions are not verified and have been replaced.
Current rq4.py labels an event circuit_half_open when metrics observed_state == CLOSED. That is a derived interpretation,
not an observed HALF_OPEN state. Do not use the validation gate name to claim a transition the service did not expose.
_run_c3_fault_injection hardcodes latency_ms=0 on OPEN confirmation and recovery observations; zeros are placeholders,
not measured response latencies. The six-observation GPU design can be counted but fault latency claims require separate timing instrumentation.
''')
# Property coverage, without changing the historical 500-case generator.
prop=load(R/'results/camera_ready/property_tests'/cid/'execution.json')
combinations={tuple(c[k] for k in ['schema_valid','expired','component_match','signed']) for c in prop['cases']}
with (A/'property_tests.md').open('a',encoding='utf-8') as f:f.write(f'\nObserved generated Boolean combinations: {len(combinations)}/16 across schema_valid, expired, component_match, signed. This does not make unsigned rejection reachable when require_signing=false.\n')
print('Supplemental trust, graph, invariants, VEX, precision, mutable-state and limitations reports written.')
