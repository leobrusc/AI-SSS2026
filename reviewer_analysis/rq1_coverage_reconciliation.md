# RQ1 coverage reconciliation

Campaign `rq1-cr-20261020T225954Z-db50e451`, source commit `bb2d9e4b4703b8f59dcd6ef563df374fcbe79720`.
Detailed universes: rq1_universe_lineage.csv (21 separately sourced records).
Identity crosswalk: rq1_identity_crosswalk.csv (32 semantic roles; not position-based).
All differences: `results\camera_ready\rq1_reproduction\rq1-cr-20261020T225954Z-db50e451\difference_classification.csv`.

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
Source universe file: `results\camera_ready\rq1\rq1-cr-20261020T225954Z-db50e451\frozen_universe_v1.json`.
Universe SHA256 `4eb3a04339e1f240399c7113c3cd53b3bb96683e3d9abc84bc488e36e819b2f9`.

Use unmodified current finalizer constructors (explicit unique output paths) plus a NEW local Syft1.18.1
scan of this interpreter's installed site-packages, selecting only python-installed-package-cataloger.
The new independent measurement requires exact package name/version/PURL, exact file SHA256,
model repository/revision, and typed/versioned resource roles. These stricter rules and the larger universe
are explicit methodology changes, not repairs retroactively applied to historical numbers.
Result: 20/30 = 66.666667%.
This is a census of this predeclared CPU deployment-reference inventory, not an operating model/service experiment,
scanner recall estimate over all installed software, statistical population estimate or security-coverage measurement.

Asset class | Reference | Represented | Coverage
---|---:|---:|---:
configuration | 3 | 1 | 33.3%
dataset | 1 | 0 | 0.0%
hardware | 2 | 0 | 0.0%
model | 2 | 0 | 0.0%
runtime | 3 | 1 | 33.3%
software | 18 | 18 | 100.0%
tokenizer | 1 | 0 | 0.0%

Covered:17 exact installed Python distributions (16 direct dependencies plus traceai), the declared service role,
SHA256-bound policy file and current-process snapshot role. Ten requirements are uncovered: model-gpt2, model-weights, tokenizer, model-config, generation-config, dataset-manifest, python-runtime, os-platform, host-cpu, host-ram.
No target GPT-2 was loaded. workspace/models artifact paths are declared required paths, currently absent;
no external cache model was substituted. Dataset manifest exists but generated descriptor lacks its digest.
The historical fixture manifest's internal entries are not validated as a real training/evaluation corpus by this experiment.
Inventory representation coverage != security coverage. The finite denominator has no sampling confidence interval.

## Reproduction commands and validation
Regenerate as a NEW campaign (CPU/scanner only):
`.venv/Scripts/python.exe reviewer_analysis/rq1_reconcile.py`
Replay saved inputs without any generation/scanner:
`.venv/Scripts/python.exe reviewer_analysis/rq1_verify_frozen.py --campaign rq1-cr-20261020T225954Z-db50e451`
Regression tests:
`.venv/Scripts/python.exe -m pytest reviewer_analysis/test_rq1_reconciliation.py -q`
Code hashes, scanner command/version, original inputs, outputs and environment are retained in campaign directories.
Fresh frozen replay gives20/30;9 regression tests pass. Package reference metadata hashes are unchanged in the original campaign import context. traceai resolves src/traceai.egg-info there, while Syft scans site-packages/dist-info. Both have name/version traceai0.1.0; the oracle asserts name/version/PURL identity only, not identical installed contents. The differing metadata sources and validation context are recorded in metadata_resolution_context.json.
Two failed new attempts are preserved separately (Windows stderr decoding, then invalid Syft selection flag).
Neither produced a coverage result or was pooled. Final command uses supported --override-default-catalogers.
No main.tex modification, GPU/model execution, historical-file edit, commit or push.
