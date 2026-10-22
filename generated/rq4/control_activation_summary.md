# RQ4 Control Activation Summary

**Campaign:** rq4-stress-20260723-103231-90518de9
**Duration:** 107.7s
**Model:** sshleifer/tiny-gpt2@5f91d94b

## Per-Configuration Results

### C0: Baseline: permissive, no policy rejection
- Requests: 15
- Completed: 15
- Expected rejections: 0
- Unexpected failures: 0
- Timeouts: 0
- P50 latency: 316ms

### C1: Token limit + timeout, designed to complete
- Requests: 24
- Completed: 24
- Expected rejections: 0
- Unexpected failures: 0
- Timeouts: 0
- P50 latency: 309ms

### C2: Low rate-limit + tiny queue to trigger rejections
- Requests: 45
- Completed: 30
- Expected rejections: 15
- Unexpected failures: 0
- Timeouts: 0
- P50 latency: 11239ms

### C3: Circuit breaker: 500 tokens with 50ms timeout forces server-side timeout
- Requests: 45
- Completed: 0
- Expected rejections: 22
- Unexpected failures: 0
- Timeouts: 23

## Protocol Validation

- [PASS] **C0_completes_inference**: 15 requests completed
- [PASS] **C1_completes_inference**: 24 requests completed
- [PASS] **C2_control_activation**: 15 expected rejections (rate-limit or queue-full)
- [PASS] **C3_circuit_opens**: 22 circuit-breaker rejections observed
- [PASS] **C3_circuit_recovers**: Circuit recovered after cooldown
- [PASS] **unexpected_failures_reported**: 0 total unexpected failures across all configs