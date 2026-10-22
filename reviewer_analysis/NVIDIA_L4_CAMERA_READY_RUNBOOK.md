# NVIDIA L4 camera-ready runbook

Status: PAPER_PRIMARY_GPU_CAMPAIGN_NOT_FOUND. This is a proposed executable campaign, not results.
Do not execute on the current Windows host unless exactly one real NVIDIA L4 is present. No GPU run was executed in this audit.
First run: sshleifer/tiny-gpt2, revision 5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be; C0–C3;
3 trials/config × 20 requests = 60/config, 240 normal requests, six separate fault observations expected.
Current rq4.py is the configuration source, not config/experiment.yaml. Preserve exact source commit and runner hash.
No expected performance numbers are supplied. Larger models/heterogeneous accelerators are follow-up work.

Use a clean checkout and an already provisioned CUDA-compatible environment with this project's dependencies,
nvidia-ml-py and the pinned Hugging Face snapshot available. Keep this runner outside the checkout.
Inspect native code's known limitations before interpretation: resolved revision falls back to requested if missing;
runner requires actual model config commit hash. Native HALF_OPEN reporting maps CLOSED to HALF_OPEN;
report only the observed state. Native fault OPEN-confirm/recovery latencies are zero placeholders; not measured durations.
The run captures direct dtype/device observations after model load; hook does not alter inference or controls.

PowerShell on the L4 host (replace the two absolute paths with actual locations):
```powershell
$env:TRACEAI_DEVICE = 'cuda'
$env:PYTHONPATH = 'C:\traceai-clean\src'
& 'C:\traceai-env\Scripts\python.exe' 'C:\audit-tools\l4_camera_ready_runner.py' --repo 'C:\traceai-clean'
```
Bash on the L4 host:
```bash
export TRACEAI_DEVICE=cuda
export PYTHONPATH=/opt/traceai-clean/src
/opt/traceai-env/bin/python /opt/audit-tools/l4_camera_ready_runner.py --repo /opt/traceai-clean
```
Prepare the clean checkout without altering the original repository (example Bash):
```bash
git clone --no-hardlinks /opt/traceai-source /opt/traceai-clean
git -C /opt/traceai-clean checkout --detach bb2d9e4b4703b8f59dcd6ef563df374fcbe79720
```
PowerShell preparation:
```powershell
git clone --no-hardlinks 'C:\traceai-source' 'C:\traceai-clean'
git -C 'C:\traceai-clean' checkout --detach bb2d9e4b4703b8f59dcd6ef563df374fcbe79720
```
Copy reviewer_analysis/l4_camera_ready_runner.py to the audit-tools directory before running.
Do not reuse scripts/run_gpu_campaign.sh here: it writes historical generated/gpu outputs and has additional behavior.
The new runner redirects only native validation report outputs into its unique camera-ready directory.

Required retained evidence: nvidia-smi full output, GPU name/driver/CUDA capability, torch/CUDA runtime version,
CUDA availability, requested model revision, actual config commit hash, tensor dtype/device, VRAM/GPU utilization
and resource timeseries, raw requests/tokens, configuration events, service events, 12 trial manifests,
campaign manifest, prompt corpus hash, native and supplemental validation reports, source commit, instrumentation source.
Output: unique results/camera_ready/l4/<campaign>/ plus <campaign>-package/camera_ready_l4_campaign_bundle.zip.
SHA256SUMS.csv hashes all payload files except itself; detached ZIP SHA-256 authenticates manifest and archive together.

Validation: exactly 240 normal and 6 fault rows; 60 normal/config, 12 trial records ×20; all actual placements CUDA;
model config commit hash exactly pinned revision; dtype float16; populated genuine NVML telemetry; no mocks.
Inspect both validation reports: a nonzero exit or any failed check prevents publication use. Archive FAIL runs as diagnostics.
Do not fix counts by deleting, filtering or synthesizing rows. Do not treat a native PASS as proof of half-open state or fault timing.
If exact fault timing is required, add independently reviewed timer instrumentation in a separate extension campaign.
Then recompute all configuration/trial metrics and uncertainty intervals from raw data before editing the paper.
This runner has been syntax-checked locally; it has not been validated on an L4 and may expose platform/runtime failures.
