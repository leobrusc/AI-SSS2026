# Fresh RQ1 audit: 27/29 is NOT VERIFIED for current repository
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
configuration | 3 | 3 | 1.0
dataset | 1 | 0 | 0.0
hardware | 2 | 2 | 1.0
model | 2 | 2 | 1.0
other | 2 | 2 | 1.0
runtime | 2 | 2 | 1.0
software | 16 | 16 | 1.0
tokenizer | 1 | 1 | 1.0

Special nodes: os-platform -> obom-os; host-cpu -> obom-cpu; host-ram -> obom-ram; all first-class. host-gpu/cuda-runtime absent and inapplicable on CPU.
inventory representation coverage != security coverage.
