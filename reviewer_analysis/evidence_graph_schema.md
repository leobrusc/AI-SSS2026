# Actual graph versus proposed formal model
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

No saved BOM-Link artifact found in inspected evidence paths: builder capability is source-supported, not demonstrated cryptographically validated graph connectivity. Local validators perform minimal structural checks, not full CycloneDX schema certification. Decision/request nodes are extracted records; no fabricated causal edges connect them to every BOM.
