# Mutable AI state
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
