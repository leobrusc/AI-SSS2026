# Circuit-breaker evidence audit
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
