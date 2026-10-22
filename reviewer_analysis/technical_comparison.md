# Technical comparison for a future manuscript revision
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

BOM-Link specification URN syntax is urn:cdx:serialNumber/version#bom-ref (https://cyclonedx.org/capabilities/bomlink/). Local custom source/target dictionaries must not be equated automatically with complete conformant URN resolution. VEX capability source: https://cyclonedx.org/capabilities/vex/.
