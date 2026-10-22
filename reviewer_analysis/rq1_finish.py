"""Finish RQ1 reports using immutable completed campaign outputs; no experiment rerun."""
import csv,hashlib,importlib.metadata as im,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
R=Path.cwd();A=R/'reviewer_analysis';sys.path.insert(0,str(A))
from rq1_verify_frozen import verify
sys.path.insert(0,str(R/'src'))  # Match the campaign's recorded source import context
CID='rq1-cr-20261020T225954Z-db50e451';O=R/'results/camera_ready/rq1'/CID;G=R/'generated/camera_ready/rq1'/CID;P=R/'results/camera_ready/rq1_reproduction'/CID;PG=R/'generated/camera_ready/rq1_reproduction'/CID
load=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,indent=2,default=str),encoding='utf-8')
def table(p,rows):
 with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def md(n,t):(A/n).write_text(t.strip()+'\n',encoding='utf-8')
summary=load(G/'workflow_summary.json');result=summary['fresh'];replay=verify(R,CID);dump(O/'frozen_replay_validation.json',replay)
u=load(O/'frozen_universe_v1.json');receipt=load(O/'freeze_receipt.json')
assert all(load(G/n)['metadata']['timestamp']>=receipt['frozen_at'] for n in ['final_ml_bom.cdx.json','final_obom.cdx.json'])
for item in load(O/'package_reference_metadata.json'):
 text=im.distribution(item['distribution_name']).read_text('METADATA') or '';assert hashlib.sha256(text.encode()).hexdigest()==item['METADATA_SHA256']
dump(O/'metadata_resolution_context.json',dict(sys_path_prefix=[str(R/'src'),str(A)],reference_metadata_sources=[dict(name=i['distribution_name'],path=str(im.distribution(i['distribution_name'])._path),SHA256=i['METADATA_SHA256']) for i in load(O/'package_reference_metadata.json')],note='traceai has both src/traceai.egg-info and site-packages/traceai-0.1.0.dist-info. Campaign reference resolves source egg-info; Syft scans dist-info. Same name/version, not proof of identical package contents. Default sys.path selected different metadata; validation explicitly uses original campaign context.'))
# Additional scanner subsets are separate universes: never mix name-set and instance counts.
lineage=list(csv.DictReader((A/'rq1_universe_lineage.csv').open(encoding='utf-8')))
s=load(R/'generated/rq1/syft_direct.cdx.json');names=sorted({c['name'].lower() for c in s['components']});py={c['purl'].split('?',1)[0] for c in s['components'] if c.get('purl','').startswith('pkg:pypi/')}
extra=[('installed_python_comparison',R/'generated/rq1/environment_inventory_comparison.csv',[dict(id=p,name=p,version='',applicability='REQUIRED') for p in sorted(py)],'101 distinct PyPI name/version PURLs; scanner-observed subset, not independently complete environment inventory'),('scanner_unique_name_set',R/'generated/rq1/final_metrics.json',[dict(id=n,name=n,version='',applicability='REQUIRED') for n in names],'108 distinct case-folded names versus165 component records; name-set counting erases versions/instances')]
for uid,source,nodes,note in extra:
 p=PG/(uid+'.json');dump(p,dict(universe_id=uid,nodes=nodes,notes=note))
 row={k:'' for k in lineage[0]};row.update(universe_id=uid,source_file=str(source.relative_to(R)),generator_function='scripts/phase2_rq1_comparison.py or name-set projection',timestamp=s['metadata']['timestamp'],commit_if_known='NOT_RECORDED',node_count_total=len(nodes),node_count_applicable=len(nodes),node_identities=json.dumps(nodes),applicability_rules='All observed scanner entries retained; not an independent reference population',representation_rules='Distinct PURL name/version set' if 'python' in uid else 'Distinct case-folded name set',output_BOM_files='generated/rq1/syft_direct.cdx.json',coverage_value='NOT_COMPOSITE_COVERAGE',universe_snapshot=str(p.relative_to(R)),universe_SHA256=sha(p),authority='OBSERVED_OUTPUT_SUBSET',notes=note);lineage.append(row)
table(A/'rq1_universe_lineage.csv',lineage)
# Explain every changed counting mechanism separately.
diffs=[('legacy first campaign -> typed campaigns','CODE_CHANGE','469dc67 vs94c0b7e','ML-only distinct-name evaluation became typed composite evaluation'),('legacy30-node universe -> typed31-node universe','UNIVERSE_CHANGE','Saved ground_truth_graph files','Node membership/schema change; applicability rules and names differ'),('5/29 final raw vs earlier23/29','SYFT_FAILURE','Raw timeout120s and zero-byte Syft file','Software components unavailable to final raw run'),('raw -> finalizer','UNIVERSE_CHANGE','rq1.py vs rq1_finalizer.py','Remove traceai-app and CUDA; add runtime-snapshot; several names/IDs changed;29 applicable is not same membership'),('raw sparse ML -> six-role final ML','FINALIZER_ENRICHMENT','generate_complete_ml_bom','Hardcoded logical model/artifact declarations added without artifact discovery'),('raw exact names -> finalizer heuristic','REPRESENTATION_RULE_CHANGE','compute_final_coverage.matches_any','RAM falsely matches colorama; Python runtime may match different interpreter versions'),('dataset manifest -> prompt-fixtures','UNKNOWN','Source rename; no correspondence digest','Possible DATASET_CHANGE cannot be established from files; no invented claim of changed dataset bytes'),('27/29 ->29/29 files','POST_PROCESSING','Saved OBOM7 components vs native finalizer3','OS/Python/CPU/RAM components present in expanded file; two unmatched names now found'),('HBOM4/OBOM3 -> HBOM2/OBOM5','POST_PROCESSING','final_metrics.json and domain_reclassification_audit.csv','Domain reassignment; cannot itself increase composite matched count'),('27/29 tex/unmatched vs29/29 metrics','STALE_OUTPUT','Existing generated summaries disagree','Outputs from different processing states coexist'),('exact postprocessor/source manifest','UNKNOWN','No source generator for enriched OBOM found','Do not invent command or precise input provenance'),('prior28/29 audit','REPRESENTATION_RULE_CHANGE','reviewer_analysis/refine_audit.py','Raw-universe role aliases; dataset byte identity remains unresolved'),('new20/30','UNIVERSE_CHANGE','Frozen explicit union32 with GPU/CUDA scope exclusions','Keep app and snapshot simultaneously; missing required assets stay in denominator'),('new exact identity criteria','REPRESENTATION_RULE_CHANGE','frozen_universe_v1.json and matcher code hash','Package version/PURL, required file SHA256, model revision, typed/versioned roles; no substring matches')]
table(P/'difference_classification.csv',[dict(difference=a,classification=b,evidence=c,explanation=d) for a,b,c,d in diffs])
# Explicit procedural deviation; exclude diagnostic from historical proof.
dump(P/'procedure_deviation.json',dict(issue='Historical pure metric function was executed on reconstructed source-derived inputs before exact-input availability was established',disposition='EXPLORATORY_DIAGNOSTIC_ONLY; excluded from exact historical reproduction',historical_reproduction_status='HISTORICAL_27_29_NOT_REPRODUCIBLE',reason='Frozen finalizer inventory, original native OBOM bytes and source/input-binding manifest unavailable',preservation='Diagnostic inputs/results retained, not silently removed'))
missing=summary['missing_assets'];classes=list(csv.DictReader((G/'coverage_by_class.csv').open()))
text=f'''# RQ1 coverage reconciliation

Campaign `{CID}`, source commit `bb2d9e4b4703b8f59dcd6ef563df374fcbe79720`.
Detailed universes: rq1_universe_lineage.csv ({len(lineage)} separately sourced records).
Identity crosswalk: rq1_identity_crosswalk.csv (32 semantic roles; not position-based).
All differences: `{str((P/'difference_classification.csv').relative_to(R))}`.

## What did 5/29 measure?
The last raw typed campaign had31 reference nodes and29 applicable nodes, excluding GPU/CUDA.
Case-insensitive exact-name composite matching covered model-gpt2, os-platform, host-cpu, host-ram,
inference-service. It combined native ML-BOM/OBOM and scanner output. Syft timed out after120s
and left a zero-byte output; Trivy produced zero packages. This is NOT unaided scanner recall or security coverage.
Earlier typed campaigns with the same saved node identities report23/29 when Syft succeeds.
Saved raw-input reevaluations reproduce the numerical results without rerunning scanner failures.
The first older campaign instead used30 nodes,28 applicable and an ML-only distinct-name metric (2/28), a different experiment.

## What did 27/29 measure?
The source-defined finalizer has30 nodes,29 applicable. It omits raw CUDA, removes traceai-app,
adds runtime-snapshot, and renames tokenizer/dataset/Python/package identifiers. It generates a six-role
ML-BOM and a three-role native operational BOM, loading a prior successful Syft scan.
The matcher accepts exact names, substrings and significant overlapping tokens rather than artifact identities.
Source-derived diagnostic inputs yield27/29 and the same two unmatched IDs (os-platform, host-cpu).
Crucially, RAM is counted because RAM -> colorama is a substring match; this is a semantic false positive.
The logical model-artifact declarations are not proof that files existed or were discovered.

Exact historical frozen-run reproduction: NO. Classification: HISTORICAL_27_29_NOT_REPRODUCIBLE.
No persisted finalizer ground-truth JSON, original three-component OBOM bytes or run manifest binding
source and all input hashes was found. Numerical reconstruction: YES, but it does not establish original-run lineage.
The full historical finalizer was not run. Procedural deviation: its pure metric function WAS run on
reconstructed inputs to investigate the discrepancy despite the exact-input-only restriction. Those diagnostics
are preserved as exploratory and excluded from historical reproduction evidence; see procedure_deviation.json.
Can93.1% be reproduced from a verified frozen historical state? No such state is available.

## What does current29/29 measure?
Existing final_metrics.json reports29/29 with HBOM2 and OBOM5. Its saved expanded OBOM has7 components,
whereas checked-in finalizer source emits only3. Added OS/Python/CPU/RAM declarations allow all names
in the reconstructed finalizer universe to match. The exact postprocessing command and frozen original graph
are unavailable; these parts remain UNKNOWN. OS/Python domain reassignment is supported by metrics and
reclassification notes, but does not by itself change the composite numerator. The retained27/29 LaTeX and
unmatched files are stale relative to the expanded files.
The Syft file has165 component records,108 distinct names and101 distinct PyPI name/version PURLs.
These are different counting units; the108 in final_metrics is numerically consistent with a unique-name
count but its generating command is not recorded. Do not describe it as108 raw component records.

## Same universe? Directly comparable?
No:5/29 and27/29 differ in node membership, names, scanner availability, generated declarations and matcher.
The two29-node denominators are not identical sets. The27-to29 source projections isolate the expanded-OBOM
name effect, but are sensitivity diagnostics rather than verified archival reruns. Prior28/29 is a name/role
crosswalk over raw rows, not a campaign, and lacks dataset digest correspondence. A dataset rename alone
cannot prove a DATASET_CHANGE; underlying dataset equivalence remains UNKNOWN.
The lineage CSV also separates the native8-node serializer graph,16 direct dependencies, scanner output
inventories,101 installed-Python comparison entries and108 unique names. No denominator is selected by target percentage.

## New frozen experiment: CAMERA_READY_RQ1
Before native BOM generation, freeze the union of raw31 and finalizer-added runtime-snapshot:32 roles.
Both traceai-app AND runtime-snapshot are retained. GPU/CUDA excluded solely by explicit CPU scope,
not a claim of newly measured hardware absence. Missing required model artifacts remain applicable.
Source universe file: `{str((O/'frozen_universe_v1.json').relative_to(R))}`.
Universe SHA256 `{result['universe_SHA256']}`.

Use unmodified current finalizer constructors (explicit unique output paths) plus a NEW local Syft1.18.1
scan of this interpreter's installed site-packages, selecting only python-installed-package-cataloger.
The new independent measurement requires exact package name/version/PURL, exact file SHA256,
model repository/revision, and typed/versioned resource roles. These stricter rules and the larger universe
are explicit methodology changes, not repairs retroactively applied to historical numbers.
Result: {result['N_represented']}/{result['N_applicable']} = {result['coverage_percent']:.6f}%.
This is a census of this predeclared CPU deployment-reference inventory, not an operating model/service experiment,
scanner recall estimate over all installed software, statistical population estimate or security-coverage measurement.

Asset class | Reference | Represented | Coverage
---|---:|---:|---:
'''
for row in classes:text+=f"{row['asset_class']} | {row['reference']} | {row['represented']} | {float(row['coverage'])*100:.1f}%\n"
text+=f'''
Covered:17 exact installed Python distributions (16 direct dependencies plus traceai), the declared service role,
SHA256-bound policy file and current-process snapshot role. Ten requirements are uncovered: {', '.join(missing)}.
No target GPT-2 was loaded. workspace/models artifact paths are declared required paths, currently absent;
no external cache model was substituted. Dataset manifest exists but generated descriptor lacks its digest.
The historical fixture manifest's internal entries are not validated as a real training/evaluation corpus by this experiment.
Inventory representation coverage != security coverage. The finite denominator has no sampling confidence interval.

## Reproduction commands and validation
Regenerate as a NEW campaign (CPU/scanner only):
`.venv/Scripts/python.exe reviewer_analysis/rq1_reconcile.py`
Replay saved inputs without any generation/scanner:
`.venv/Scripts/python.exe reviewer_analysis/rq1_verify_frozen.py --campaign {CID}`
Regression tests:
`.venv/Scripts/python.exe -m pytest reviewer_analysis/test_rq1_reconciliation.py -q`
Code hashes, scanner command/version, original inputs, outputs and environment are retained in campaign directories.
Fresh frozen replay gives20/30;9 regression tests pass. Package reference metadata hashes are unchanged in the original campaign import context. traceai resolves src/traceai.egg-info there, while Syft scans site-packages/dist-info. Both have name/version traceai0.1.0; the oracle asserts name/version/PURL identity only, not identical installed contents. The differing metadata sources and validation context are recorded in metadata_resolution_context.json.
Two failed new attempts are preserved separately (Windows stderr decoding, then invalid Syft selection flag).
Neither produced a coverage result or was pooled. Final command uses supported --override-default-catalogers.
No main.tex modification, GPU/model execution, historical-file edit, commit or push.
'''
md('rq1_coverage_reconciliation.md',text)
md('rq1_publication_decision.md',f'''# RQ1 publication decision

REPLACE_WITH_CAMERA_READY_RESULT

Historical93.1% is not supported by a verified frozen-run lineage. Its arithmetic can be reconstructed,
but the RAM/colorama false positive prevents interpreting it as27 semantically identified assets.
The original finalizer graph/native operational BOM/source-input binding are unavailable.
The exploratory reconstruction does not satisfy HISTORICAL_27_29_REPRODUCED.

A clean new experiment is now available: CAMERA_READY_RQ1,20/30 applicable assets represented (66.7%).
The universe was frozen before generation:32 roles, GPU/CUDA excluded by CPU scope, missing required files
retained. Both original application and added runtime snapshot are retained. Exact identity criteria and all
unmatched assets are explicit. The generators are unchanged; only the independent measurement protocol is new.
This is inventory identity representation on a deployment-reference benchmark, not security coverage or evidence
of a running model. Its denominator and oracle differ from historical experiments and must be described anew.

Suggested paper wording for author review (main.tex remains untouched):
"A new camera-ready CPU inventory experiment represented20 of30 applicable reference assets (66.7%) under
predeclared first-class identity criteria. The32-role reference inventory excluded GPU/CUDA by scope and
retained missing required artifacts as uncovered. This result supersedes the unreconciled historical93.1%
figure. Inventory representation coverage is not security coverage."

Traceability: `{str((O/'coverage_result.json').relative_to(R))}`;
frozen inventory and per-asset results in the same directory; class table and native outputs under `{str(G.relative_to(R))}`.
Replay validation PASS;9 regression tests PASS. Remaining limitations: reference universe is project-defined,
several model artifacts absent, runtime resource identities role-level, no full-schema interoperability or security claim.
No global manuscript-readiness decision is implied. Prior overall audit reports remain preserved; this decision
supersedes only their unresolved RQ1 disposition.
''')
# Verify historical integrity again after tests and report generation.
protected=load(O/'protected_input_hashes.json');changed=[p for p,h in protected.items() if not (R/p).exists() or sha(R/p)!=h];assert not changed,changed
xml=ET.parse(O/'identity_regression_tests.xml').getroot();suites=list(xml.iter('testsuite'));test_count=sum(int(s.get('tests',0)) for s in suites);assert test_count==9 and not sum(int(s.get('failures',0))+int(s.get('errors',0)) for s in suites)
dump(O/'final_validation.json',dict(status='PASS',timestamp=datetime.now(timezone.utc).isoformat(),historical_files_checked=len(protected),historical_changes=changed,frozen_replay=replay,regression_tests_passed=test_count,package_metadata_unchanged=True,freeze_precedes_generation=True,no_gpu_or_model_execution=True))
allfiles=[]
for root in [O,G,P,PG]:allfiles.extend(p for p in root.rglob('*') if p.is_file())
allfiles.extend([A/n for n in ['rq1_universe_lineage.csv','rq1_identity_crosswalk.csv','rq1_coverage_reconciliation.md','rq1_publication_decision.md','rq1_reconcile.py','rq1_strict_identity.py','rq1_verify_frozen.py','test_rq1_reconciliation.py']])
table(G/'final_evidence_manifest.csv',[dict(artifact=str(p.relative_to(R)),SHA256=sha(p),purpose='RQ1 frozen evidence or reviewer analysis') for p in allfiles]);(G/'final_evidence_manifest.sha256').write_text(sha(G/'final_evidence_manifest.csv')+'  final_evidence_manifest.csv\n',encoding='utf-8')
print('RQ1 CAMERA-READY DECISION\n\nHistorical 5/29:\nmeaning = exact-name composite representation in raw31-node/29-applicable universe with Syft timeout\n\nHistorical 27/29:\nreproduced = NO (verified frozen historical state); source-derived numerical diagnostic gives27/29\nmeaning = finalizer-enriched, altered universe with permissive heuristic; RAM falsely matches colorama\n\nCurrent 29/29:\nmeaning = name-heuristic result using enriched7-component OBOM; original postprocessor/graph provenance unavailable\n\nFresh camera-ready result:\nN_applicable =30\nN_represented =20\ncoverage =20/30 =66.6667%\n\nPaper recommendation:\nREPLACE_WITH_CAMERA_READY_RESULT\n\nSTOP.')

