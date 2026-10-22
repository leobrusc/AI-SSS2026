# VEX policy semantics from current implementation
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

Fresh direct parser/suppression diagnostics saved under results/camera_ready/vex_diagnostics: affected/fixed/under_investigation/unknown retained; not_affected suppressed despite wrong component; old metadata timestamp alone not expired; explicit traceai:expires expires only with metadata timestamp; conflicting duplicate first status wins.
