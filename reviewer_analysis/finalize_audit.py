from pathlib import Path
import csv,json,hashlib,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
R=Path.cwd();A=R/'reviewer_analysis';CID='cr-20261020T223734Z-ffdfff82';G=R/'generated/camera_ready'/CID;now=datetime.now(timezone.utc).isoformat()
def md(n,t):(A/n).write_text(t.strip()+'\n',encoding='utf-8')
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def table(n,rows,fields=None):
 with (A/n).open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
# Exact reviewer matrix: each actual request is its own row, no substituted reviewer text.
rows=[]
def add(reviewer,section,comments,evidence,finding,status='RESOLVED_WITH_CLARIFICATION',experiment='No',paper='Pending: manuscript absent; incorporate verified evidence and bounded wording'):
 for comment in comments.split(';'):
  rows.append(dict(Reviewer=reviewer,Comment=section+': '+comment.strip(),Evidence=evidence,Test_analysis='Fresh source/raw-file audit; see named report',Finding=finding,Paper_modification=paper,Experiment_required=experiment,Status=status,Source='Actual reviewer comments supplied by user; '+evidence))
add('1','Bounded scope','tiny GPT-2 proxy;one NVIDIA L4;one organization;project-defined asset universe;no production-scale claims;no semantic-backdoor claims;no tail-latency claims;preserve bounded conclusions','generalizability.md; rq4_summary.md','CPU evidence only; no L4 campaign established; fixed universe and fixture scope. Reviewer 1 remains OPEN until manuscript can be checked.')
add('2','A technical comparison','CycloneDX AI/ML-BOM;BOM-Link;VEX;in-toto','technical_comparison.md; reference_validation.md','Primary sources consulted; local envelope is not conformant DSSE; interoperability/security claims bounded.')
add('2','A architecture','evidence-graph schema;artifact identification rules;cross-document consistency validation','evidence_graph_schema.md; evidence_graph_nodes.csv; evidence_graph_edges.csv; security_invariants.md','Implemented graph extracted; supplied attestation not bound to signed payload; consistency partial.')
add('2','A trust','cryptographic trust anchors;signature-key management;key revocation','trust_model.md; rq2_camera_ready_extension.md','Local P256/SHA256; persisted unencrypted test key; caller trusted public key; allowlist removal not full revocation.')
add('2','A invariants','explicit deployment-gate security invariants;implemented and evaluated verification properties;conceptual architectural security claims','security_invariants.md','INV1–INV10 evaluated; partial/unimplemented properties labeled.')
add('2','B representation','complete reference asset inventory;numerator for 93.1%;denominator for 93.1%;software coverage;model-artifact coverage;dataset coverage;hardware coverage;runtime-configuration coverage','rq1_asset_inventory.csv; rq1_summary.md','29 applicable raw nodes; stale 27/29 versus current reported29/29; raw/finalizer universes differ; dataset identity unresolved.','NEW_LOCAL_TEST_REQUIRED','Reconcile versioned universe and artifact lineage; no silent methodological repair')
add('2','C historical outcomes','240 verification outcomes;class-stratified confusion matrix;modification categories;confidence intervals','rq2_outcomes.csv; rq2_confusion_matrix.csv; rq2_summary.md','Verified30×8; TP210 TN30 FP0 FN0; exact two-sided CP95; S9a authorization rejection does not test ECDSA.')
add('2','C additional attacks','rollback;replay;compromised signing-key scenario;metadata substitution','rq2_camera_ready_extension.md; rq2_extension_outcomes.csv; rq2_security_property_matrix.csv','42-case separate extension: CR-SIG30 rejected at ECDSA; fresh replay/rollback/metadata/compromised authorized signer accepted; report limitations.')
add('2','D scanner metadata','Trivy version;Grype version;scan timestamp;vulnerability database timestamps;vulnerability database versions;package matching criteria;deduplication procedure;PURL usage','rq3_summary.md; generated/camera_ready/'+CID+'/scanner_embedded_metadata.json','Trivy0.72.0, Grype0.86.1; GrypeDB built2026-03-09 schema5; TrivyDB metadata missing; exact package/version and explicit advisory aliases.','RESOLVED_WITH_CLARIFICATION','Historical Trivy DB snapshot cannot be recovered by running a current scan')
add('2','D scanner agreement','shared CVEs/advisories;intersection;union;Jaccard/IoU;component-specific discrepancies;canonical CVE/GHSA equivalents','rq3_scanner_agreement.csv; rq3_discrepancies_by_component.csv','Raw54/35 intersection4 union85 Jaccard.04706; canonical intersection35 union54 Jaccard.64815; canonical Trivy-only19.')
add('2','D VEX rules','VEX validity periods;evidence ownership;conflict-resolution rules;policy precedence;max_vex_age_hours enforcement','vex_policy_semantics.md; results/camera_ready/vex_diagnostics/observations.json','720h YAML unused; custom expiry plus metadata timestamp only; owner not enforced; first duplicate wins; wrong-component suppression possible if caller skips gate.')
add('2','D randomized tests','property-test generators;test oracle;random seeds;coverage criteria;500 reported executions;framework identity','property_tests.md; results/camera_ready/property_tests/'+CID+'/execution.json','random.Random42, Boolean truth table,500/500 agreement; not Hypothesis; unsigned rejection disabled in this run.')
add('2','E runtime per configuration','throughput;median latency;p95 latency;rejection rate;generated-token statistics;GPU memory;GPU utilization;resource utilization','rq4_metrics_by_config.csv; rq4_metrics_by_trial.csv; rq4_summary.md','CPU diagnostics only; L4 missing; derived throughput spans with explicit timestamp convention; no GPU values certified.','GPU_TEST_REQUIRED','Run NVIDIA_L4_CAMERA_READY_RUNBOOK.md then independently recompute')
add('2','E circuit breaker','circuit-breaker threshold;fault-detection latency;recovery duration;state-transition timestamps;dispersion estimates;uncertainty intervals','circuit_breaker_summary.md; circuit_breaker_timeline.csv; rq4_metrics_by_trial.csv','Config sources differ; actual events sparse; no certified HALF_OPEN transition; native zero fault-latency placeholders; CPU std/IQR only.','GPU_TEST_REQUIRED','Real L4 raw events/timers and independent trials; do not infer unavailable timing')
add('2','E controls and scale','parameter-matched controls;security-control overhead','proposed_matched_overhead_experiment.md','No matched experiment; deployment verification is separate from request-path control cost.','FUTURE_WORK','Matched paired experiment required for an overhead claim')
add('2','E controls and scale','larger models;heterogeneous accelerators','generalizability.md','No supported evidence; proposed follow-up only.','FUTURE_WORK','Larger models and heterogeneous hardware; not fabricated')
add('2','F editorial request','AI-detection rate below20%;specificity;technical precision;author review;traceability of statements;natural scientific writing','FINAL_AUDIT_REPORT.md; reference_validation.md','No detector run or evasion; editorial precision/author review pending source manuscript.','NOT_APPLICABLE','No AI-detection experiment','No detector optimization; author editorial review required')
add('3','Mutable state','prompts;LoRA/adapters;runtime settings;plug-ins/tools;retrieval indexes;guardrails','mutable_ai_state.md','Prompt/runtime configuration partial; adapters/RAG/tools/guardrails untracked; no automatic evidence regeneration/gate invalidation.')
add('3','Attack surface','uncovered artifacts can include important modern AI attack surfaces;inventory representation coverage is not security coverage','mutable_ai_state.md; rq1_summary.md','Explicit statement and limitations documented; fixed inventory not comprehensive attack coverage.')
add('3','Precision','model precision;model quantization;model compression','model_precision.md','Code CPUfloat32/CUDAfloat16; no quantization/compression pipeline; historical observed dtype unavailable; GPU runner captures actual parameter dtype.')
fields=['Reviewer','Comment','Evidence','Test_analysis','Finding','Paper_modification','Experiment_required','Status','Source']
table('reviewer_response_matrix.csv',rows,fields)
text='# Actual reviewer response matrix\n\nAll entries map the user-supplied reviewer comments; status describes audit disposition, NOT a completed manuscript revision. All reviewers remain OPEN while source manuscript is absent.\n\n'
text+='Reviewer | Comment | Evidence | Test/analysis | Finding | Paper modification | Experiment required | Status | Source\n'+'|'.join(['---']*9)+'\n'
for r in rows:text+=' | '.join(str(r[k]).replace('|','/').replace('\n',' ') for k in fields)+'\n'
md('reviewer_response_matrix.md',text)
# Add actual decision/runtime observation nodes, avoid invented graph edges.
nodes=list(csv.DictReader((A/'evidence_graph_nodes.csv').open()));edges=list(csv.DictReader((A/'evidence_graph_edges.csv').open()))
source='results/raw/security-20260722-140421-f4aee0f2/security_results.json'
for i,r in enumerate(load(R/source)):
 key=source+'#'+str(i);nodes.append(dict(id=key,node_class='decision',identity=r['trial_id']+':'+r['decision'],source=source))
source='results/rq4/rq4-20260722-133959-e395d20d/raw_requests.csv'
for r in csv.DictReader((R/source).open()):nodes.append(dict(id=source+'#'+r['request_id'],node_class='runtime_observation',identity=r['trial_id']+'/'+r['configuration_id'],source=source))
for path in (R/'fixtures/vex').glob('*.json'):
 d=load(path);doc=str(path.relative_to(R));nodes.append(dict(id=doc,node_class='evidence',identity='VEX fixture',source=doc))
 for v in d.get('vulnerabilities',[]):
  for a in v.get('affects',[]):edges.append(dict(source=doc+'#'+v.get('id',''),target=a.get('ref',''),relation='affects_ref_as_written_not_globally_resolved',evidence=doc))
table('evidence_graph_nodes.csv',nodes);table('evidence_graph_edges.csv',edges)
with (A/'evidence_graph_schema.md').open('a',encoding='utf-8') as f:f.write('\nNo saved BOM-Link artifact found in inspected evidence paths: builder capability is source-supported, not demonstrated cryptographically validated graph connectivity. Local validators perform minimal structural checks, not full CycloneDX schema certification. Decision/request nodes are extracted records; no fabricated causal edges connect them to every BOM.\n')
with (A/'vex_policy_semantics.md').open('a',encoding='utf-8') as f:f.write('\nFresh direct parser/suppression diagnostics saved under results/camera_ready/vex_diagnostics: affected/fixed/under_investigation/unknown retained; not_affected suppressed despite wrong component; old metadata timestamp alone not expired; explicit traceai:expires expires only with metadata timestamp; conflicting duplicate first status wins.\n')
with (A/'reference_validation.md').open('a',encoding='utf-8') as f:f.write('\n- BOM-Link primary documentation: https://cyclonedx.org/capabilities/bomlink/\n- VEX primary documentation: https://cyclonedx.org/capabilities/vex/\n')
with (A/'technical_comparison.md').open('a',encoding='utf-8') as f:f.write('\nBOM-Link specification URN syntax is urn:cdx:serialNumber/version#bom-ref (https://cyclonedx.org/capabilities/bomlink/). Local custom source/target dictionaries must not be equated automatically with complete conformant URN resolution. VEX capability source: https://cyclonedx.org/capabilities/vex/.\n')
# Preserve original state and record extra execution environment metadata.
with (A/'current_repository_state.md').open('a',encoding='utf-8') as f:f.write('\nExecution metadata: '+str(G.relative_to(R))+'/environment.json. Original historical hashes captured before experiments; 356 files protected. Initial commands were read-only; first write created requested directories/state report. No AGENTS.md found in repository search. Original reviewer_analysis files were pre-existing/untracked and were copied before report replacement.\n')
md('FINAL_AUDIT_REPORT.md',f'''# Final evidence audit — STOP BEFORE MANUSCRIPT EDIT
Timestamp {now}; commit bb2d9e4b4703b8f59dcd6ef563df374fcbe79720; primary extension campaign {CID}.

SAFE_TO_INCLUDE
- Historical RQ2 30×8=240, TP210 TN30 FP0 FN0, scenario stratification and exact CP95 intervals.
- S9a is SIGNATURE_AUTHENTICITY_NOT_TESTED_BY_S9A; authorized-key CR-SIG30 reaches ECDSA and rejects all mutations.
- Trivy0.72.0/Grype0.86.1 raw findings54/35; raw intersection4 union85 Jaccard.0470588;
  explicit alias canonical intersection35 union54 Jaccard.6481481; component discrepancies in CSV.
- Existing generator random.Random42: 500 cases/500 agreements/0 counterexamples; Boolean policy flag testing, not Hypothesis.
- Explicitly measured extension limitations: fresh replay, rollback, metadata substitution accepted;
  compromised still-authorized signer accepted; missing keyid/public-key binding; empty allowlist permits all;
  unauthenticated timestamp can be refreshed. No implementation changes made to conceal these outcomes.

SAFE_WITH_LIMITATION
- 42 extension observations are diagnostic properties, separate from historical240. Primary campaign {CID}.
  Earlier independent smoke extension cr-20261020T223724Z-60cf801f also has42; do not pool into primary42 or historical240.
  Fixed fixture key scalar42 and one-bit mutation; signatures have library-randomized nonces. No security-effectiveness generalization.
- CPU240 diagnostic and separate CPU80 diagnostic metrics; successful-only latency stats and rejection denominators explicit.
  Throughput derived from timestamp spans, not measured steady-state throughput. Stress files lack complete hardware provenance.
- GrypeDB built2026-03-09T00:31:20Z schema5 and recorded checksum; historical TrivyDB timestamp/version unavailable.
- Code dtype CPUfloat32/CUDAfloat16; no observed historic tensor dtype established. No quantization/compression setup found.
- VEX custom expiry, caller Boolean trust, first-statement conflict behavior and advisory-only suppression require explicit limitations.
- G=(V,E) formalization and stronger invariants are architectural, only source-supported subset implemented/evaluated.

UNSUPPORTED
- Current 27/29=93.1% claim: files conflict (raw5/29; stale27/29 summary; current29/29 metrics; changed universe).
  Independent raw-universe name/role audit28/29 does not repair lineage or certify artifact identity.
- NVIDIA L4 runtime/VRAM/utilization/latency/throughput claims: PAPER_PRIMARY_GPU_CAMPAIGN_NOT_FOUND.
  generated/gpu/quick_validation_report.json has campaign_id=test and is GPU_MOCK/unit output, not failed real hardware evidence.
- Matched security-control overhead, larger-model or heterogeneous-accelerator results.
- Full cryptographic cross-document binding, anti-replay/rollback resistance, production signer revocation, semantic backdoor/production-scale security.
- Native HALF_OPEN event name as proof of observed HALF_OPEN state; zero placeholder fault latencies as measurements.

NEW_EXPERIMENT_REQUIRED
- Real L4 run following NVIDIA_L4_CAMERA_READY_RUNBOOK.md with exact tiny-GPT2 revision,240 normal+6 faults and actual tensors/NVML.
- Independent fault timing/state observations and repeated-trial uncertainty if those claims are retained.
- Matched paired controls only if overhead is claimed; larger models/heterogeneous accelerators remain future work.
- Reconcile/freeze RQ1 universe and historical-to-current identity mappings; capture a separately labeled experiment if needed.
- Recover historical TrivyDB metadata if possible; a fresh scan cannot retroactively supply it.

STOP GATE
No main.tex or .bib found recursively. No manuscript was edited, backed up, compiled or certified as six pages.
Phases21–24 manuscript operations are intentionally NOT EXECUTED because major claims remain unsupported and source is absent.
No commits/pushes; no GPU execution. All356 historical files are checked by hash in final integrity report.
Focused regression suite:30 passed,1 Pydantic deprecation warning; JUnit results/camera_ready/local_checks.xml.
Tests which write generated/gpu reports were not run in original checkout; historical evidence must remain immutable.
All reviewer requests mapped individually in reviewer_response_matrix.md/CSV ({len(rows)} rows).
''')
md('CAMERA_READY_CHANGELOG.md','''# Camera-ready audit changelog
No manuscript/source implementation changes. Existing pre-audit reports archived; historical evidence preserved.

Reviewer comment | Old manuscript issue | Evidence generated | Code/test change | New manuscript text/section | Status
---|---|---|---|---|---
R1 bounded claims | manuscript absent, cannot verify scope | generalizability.md; final audit | none | pending author source | OPEN
R2 A trust/architecture | implemented vs conceptual could be conflated | trust model; graph; invariants; security extension | isolated fixture harness only | pending architecture/threat model | OPEN
R2 B RQ1 | stale27/29 conflicts with current files | all reference nodes; name/role mapping; lineage conflicts | read-only reconciliation analysis | pending RQ1; no silent denominator repair | OPEN
R2 C RQ2 | S9a does not establish ECDSA path | original240 matrix/CP95; separate42 extension | normal verifier traced with real cryptographic call | pending RQ2 and limitations | OPEN
R2 D scanners/VEX | raw aliases/expiry/ownership need clarification | exact sets54/35; canonical35/54; direct VEX diagnostics;500 randomized | isolated local checks | pending RQ3 | OPEN
R2 E runtime | no supported L4; unmatched treatment and placeholder timing | CPU240+80 recomputed; L4 runbook/runner | prepared GPU script, syntax-checked only | pending real L4 evidence and RQ4 | OPEN
R2 F editorial | no detector evasion authorized | traceable evidence and precise limitations | no AI detector run | pending author editorial review | NOT_APPLICABLE detector target
R3 state/precision | mutable attack surfaces not comprehensively covered | mutable_ai_state.md; model_precision.md | source search and audit | pending limitations/precision | OPEN

The complete per-comment mapping is reviewer_response_matrix.md. Old manuscript wording and final section/line changes
cannot be supplied without the manuscript. No main_pre_camera_ready.tex created because no main.tex exists.
''')
md('CAMERA_READY_CHECKLIST.md','''# Camera-ready checklist — blocked at evidence freeze
- [ ] <= 6 pages (manuscript absent; no compile)
- [ ] author names verified
- [ ] affiliations verified
- [ ] funding verified
- [x] all reviewer comments mapped (audit dispositions; manuscript changes pending)
- [ ] all quantitative manuscript claims traceable (RQ1 lineage and GPU unresolved)
- [x] no mock data presented as real in new audit outputs
- [ ] GPU evidence real or GPU claims removed (no manuscript available)
- [ ] PDF ready for IEEE PDF eXpress
- [ ] eCF completed (status unknown; pending author)
- [ ] final EasyChair upload completed (pending; not authorized)
- [x] historical raw evidence preserved by hash comparison
- [x] original240 and extension42 kept separate
- [x] local focused tests passed
- [x] L4 runbook and output-bundling script prepared; no local GPU execution
''')
# Check historical immutability after all experiments/tests.
baseline=load(G/'historical_hashes_before.json');changed=[p for p,h in baseline.items() if not (R/p).exists() or hashlib.sha256((R/p).read_bytes()).hexdigest()!=h]
assert not changed,changed
(G/'final_historical_integrity_check.json').write_text(json.dumps({'timestamp':now,'files_checked':len(baseline),'changed':changed,'status':'PASS'},indent=2))
# Evidence manifest binds all historical inputs, all analysis artifacts and all new result files.
paths={R/p for p in baseline}
for root in [A,R/'results/camera_ready',R/'generated/camera_ready']:
 paths.update(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
manifest=A/'camera_ready_evidence_manifest.csv';paths.discard(manifest)
entries=[]
for p in sorted(paths):
 rel=str(p.relative_to(R));name=p.name.lower();rq=next((q.upper() for q in ['rq1','rq2','rq3','rq4'] if q in rel.lower()),'CROSS_CUTTING')
 entries.append(dict(artifact=rel,SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),timestamp=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),campaign_id=CID if CID in rel else ('HISTORICAL' if rel in baseline else 'AUDIT'),RQ=rq,purpose='historical input' if rel in baseline else 'audit analysis or isolated local execution',reviewer_comment='Reviewer 2 '+rq+'; Reviewer 1 bounded scope; Reviewer 3 where applicable',status='UNCHANGED_HISTORICAL' if rel in baseline else 'AUDIT_OUTPUT_NOT_MANUSCRIPT_CERTIFICATION'))
table('camera_ready_evidence_manifest.csv',entries,['artifact','SHA256','timestamp','campaign_id','RQ','purpose','reviewer_comment','status'])
# Manifest itself is authenticated by separate checksum rather than circular self-hash.
(G/'evidence_manifest.sha256').write_text(hashlib.sha256(manifest.read_bytes()).hexdigest()+'  reviewer_analysis/camera_ready_evidence_manifest.csv\n')
print('CAMERA-READY STATUS\n\nReviewer 1: OPEN (bounded claims documented; manuscript absent)\nReviewer 2: OPEN\nremaining items = RQ1 lineage; real L4; missing Trivy DB metadata; manuscript revision; fault timing/uncertainty; matched overhead and scale only if claimed\nReviewer 3: OPEN\nremaining items = incorporate mutable-state and precision limitations into missing manuscript\n\nRQ1: BLOCKED; applicable reference29; 27/29 not verified; current metrics29/29 conflict with historical sources\nRQ2: VERIFIED WITH LIMITATIONS; original n=240; TP210 TN30 FP0 FN0; primary extension n=42\nremaining limitations = metadata binding, fresh replay, rollback, keyid binding, empty allowlist, unsigned timestamp, compromised authorized signer\nRQ3: VERIFIED WITH LIMITATIONS; raw Jaccard4/85=.0470588; canonical35/54=.6481481; Trivy DB unknown; VEX expiry/component/conflict limitations\nRQ4: CPU240 + separate CPU80 recomputed; GPU=NOT FOUND; matched overhead=NOT FOUND\nPaper: page count UNKNOWN; compile NOT RUN (main.tex/.bib absent; evidence stop gate)\n\nUNSUPPORTED CLAIMS REMAINING:\n93.1% lineage; NVIDIA L4 quantitative results; matched overhead; full replay/rollback/revocation/cross-document guarantees\n\nNEW EXPERIMENTS STILL REQUIRED:\nReal L4 tiny-GPT2 240+6; independent fault timing if retained; RQ1 evidence reconciliation; matched controls/scale only if claimed\n\nFILES GENERATED:\nreviewer_analysis/ reports, CSVs, scripts, response matrix, manifest, checklist/changelog\nresults/camera_ready/ isolated verifier/property/VEX diagnostics and JUnit\ngenerated/camera_ready/ inventories, environment, prior-report copies, hash checks\n\nSTOP.')
