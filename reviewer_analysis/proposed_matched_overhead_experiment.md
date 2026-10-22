# Matched experiment proposal (not executed)
No existing experiment found with all required matching variables and only security treatment changed.
C0-C1 changes generation token cap; C1-C2 changes concurrency/queue/rate; these cannot isolate control cost.
DeploymentGate evaluates artifact/evidence at deployment/test time. service/app.py request handler does not
run ECDSA/attestation checks per request. Do not describe deployment verification as per-request overhead.

Deployment experiment: immutable artifact/evidence; randomized paired order of verification treatment;
report verification latency separately by digest/signature/attestation/policy, cold/warm cache and repeats.
Request-path experiment: same model/revision, exact prompt corpus/order, seed, temperature, max_new_tokens,
timeout, concurrency, queue, hardware and load schedule; only selected runtime-control code treatment differs.
Use independent paired trials, record tokens/outcomes and client/server monotonic times, warmup, CPU/GPU resources;
report paired differences and uncertainty intervals. Preserve rejected requests separately.
If treatment changes behavior, report that difference alongside timing instead of selecting successful requests silently.
No overhead result is presently supported.
