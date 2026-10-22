"""Strict A100 release adapter around the authoritative RQ4 campaign."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import traceback

ROOT = Path(__file__).resolve().parents[2]
GPU = "NVIDIA A100-SXM4-80GB"
MODEL = "sshleifer/tiny-gpt2"
REVISION = "5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"


def dump(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def rows(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_source():
    manifest = json.loads((ROOT / "benchmark-source-manifest.json").read_text())
    for name, expected in manifest.items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Release source integrity mismatch: {name}")
    return manifest


def preflight(output):
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("Requires Linux x86_64")
    verify_source()
    import torch
    import pynvml
    smi = subprocess.check_output(["nvidia-smi"], text=True)
    (output / "nvidia-smi.txt").write_text(smi)
    names = subprocess.check_output([
        "nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], text=True).strip().splitlines()
    if names != [GPU] or torch.cuda.device_count() != 1:
        raise RuntimeError(f"Requires exactly one {GPU}; found {names}")
    if not torch.cuda.is_available() or torch.cuda.get_device_name(0) != GPU:
        raise RuntimeError("CUDA identity gate failed")
    if torch.__version__ != "2.9.1+cu129" or torch.version.cuda != "12.9":
        raise RuntimeError("Requires locked torch 2.9.1+cu129 / CUDA runtime 12.9")
    if os.environ.get("CUDA_VISIBLE_DEVICES") not in (None, "0"):
        raise RuntimeError("Unset CUDA_VISIBLE_DEVICES or use 0 to preserve NVML/CUDA identity")
    tensor = torch.ones(16, device="cuda", dtype=torch.float16)
    if tensor.sum().item() != 16:
        raise RuntimeError("Real CUDA tensor check failed")
    torch.cuda.synchronize()
    pynvml.nvmlInit()
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        name = name.decode() if isinstance(name, bytes) else name
        if name != GPU or pynvml.nvmlDeviceGetCount() != 1:
            raise RuntimeError("NVML identity mismatch")
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
    finally:
        pynvml.nvmlShutdown()
    environment = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "machine": platform.machine(), "python": sys.version,
        "uv": subprocess.check_output(["uv", "--version"], text=True).strip(),
        "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
        "cuda_available": True, "cuda_tensor_verified": True, "nvml_verified": True,
        "gpu_name": name, "gpu_memory_total_bytes": memory.total,
        "packages": sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()),
        "release": json.loads((ROOT / "benchmark-release.json").read_text()),
        "uv_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
    }
    dump(output / "environment.json", environment)
    return environment


class ResourceSampler:
    """Sample the runner and live service descendants throughout execution."""
    def __init__(self, path):
        self.path = path
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.error = None

    def run(self):
        import psutil
        runner = psutil.Process()
        try:
            with self.path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=[
                    "timestamp_utc", "cpu_percent", "runner_rss_bytes", "service_rss_bytes",
                    "service_pids", "system_ram_used_bytes", "system_ram_total_bytes"])
                writer.writeheader()
                while not self.stop_event.is_set():
                    children = runner.children(recursive=True)
                    service_rss = 0
                    live_pids = []
                    for child in children:
                        try:
                            service_rss += child.memory_info().rss
                            live_pids.append(child.pid)
                        except psutil.NoSuchProcess:
                            continue
                    memory = psutil.virtual_memory()
                    writer.writerow({
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "cpu_percent": psutil.cpu_percent(), "runner_rss_bytes": runner.memory_info().rss,
                        "service_rss_bytes": service_rss, "service_pids": ";".join(str(pid) for pid in live_pids),
                        "system_ram_used_bytes": memory.used, "system_ram_total_bytes": memory.total})
                    stream.flush()
                    self.stop_event.wait(0.2)
        except Exception:
            self.error = traceback.format_exc()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop_event.set()
        self.thread.join(timeout=5)


def validate(output, environment, runner_rc):
    from traceai.hashing import hash_json
    normal = rows(output / "raw_requests.csv")
    faults = rows(output / "fault_observations.csv")
    trials_path = output / "trial_manifest.json"
    trials = json.loads(trials_path.read_text()) if trials_path.exists() else []
    events_path = output / "service_events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines()] if events_path.exists() else []
    configs = [e["config"] for e in events if e.get("event") == "service_configuration_captured"]
    observed = configs[0] if len(configs) == 1 else {}
    native_path = output / "quick_validation_report.json"
    native = json.loads(native_path.read_text()) if native_path.exists() else {}
    campaign_path = output / "campaign_manifest.json"
    campaign = json.loads(campaign_path.read_text()) if campaign_path.exists() else {}
    gpu = rows(output / "gpu_timeseries.csv")
    resources = rows(output / "runtime_resource_timeseries.csv")
    phash_path = output / "prompt_corpus_hash.json"
    phash = json.loads(phash_path.read_text()) if phash_path.exists() else {}
    counts = Counter(r.get("configuration_id") for r in normal)
    def overlaps(samples):
        return any(t["start_utc"] <= sample.get("timestamp_utc", "") <= t["end_utc"]
                   for t in trials for sample in samples)
    gates = {
        "runner_success": runner_rc == 0,
        "gpu_exact": environment.get("gpu_name") == GPU,
        "real_cuda_tensor": environment.get("cuda_tensor_verified") is True,
        "nvml": environment.get("nvml_verified") is True,
        "model_id": observed.get("model_id") == MODEL,
        "requested_revision": observed.get("requested_revision") == REVISION,
        "revision": observed.get("resolved_revision") == REVISION,
        "actual_parameter_device": observed.get("parameter_device", "").startswith("cuda"),
        "actual_parameter_dtype": observed.get("parameter_dtype") == "torch.float16",
        "normal_240": len(normal) == 240,
        "fault_6": len(faults) == 6,
        "per_configuration_60": counts == Counter({c: 60 for c in ("C0", "C1", "C2", "C3")}),
        "unique_request_ids": len({r.get("request_id") for r in normal + faults}) == 246,
        "twelve_trials": len(trials) == 12 and all(t.get("observation_count") == 20 for t in trials),
        "three_trials_per_configuration": Counter(t.get("configuration_id") for t in trials) == Counter({c: 3 for c in ("C0", "C1", "C2", "C3")}),
        "twenty_rows_per_trial": len(trials) == 12 and all(
            sum(r.get("trial_id") == t["trial_id"] for r in normal) == 20 for t in trials),
        "native_real_http_no_mock": campaign.get("inference_type") == "REAL_HTTP" and campaign.get("mock_used") is False,
        "native_gates": native.get("status") == "PASS",
        "gpu_telemetry_overlaps_trials": bool(gpu) and overlaps(gpu),
        "resource_telemetry_overlaps_trials": bool(resources) and overlaps(resources),
        "gpu_telemetry_values": bool(gpu) and all(
            r.get(k) not in (None, "") for r in gpu for k in (
                "gpu_utilization_percent", "memory_used_mb", "memory_total_mb", "temperature_c")),
        "service_rss_observed": any(int(r["service_rss_bytes"]) > 0 for r in resources),
        "prompt_hash": phash.get("hash") == hash_json(phash.get("corpus", {})),
    }
    report = {"status": "VALID_FOR_PUBLICATION" if all(gates.values()) else "NOT_VALID_FOR_PUBLICATION",
              "gates": gates, "counts": dict(counts), "normal": len(normal), "fault": len(faults),
              "limitations": ["Native circuit_half_open event does not prove a distinct HALF_OPEN state.",
                              "A100 substitutes the previously planned L4; no cross-GPU equivalence is claimed."]}
    dump(output / "validation_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    os.chdir(ROOT)
    verify_source()
    if args.dry_run:
        from traceai.campaigns.rq4 import CONFIGURATIONS, SMOKE_MODEL, SMOKE_REVISION
        if list(CONFIGURATIONS) != ["C0", "C1", "C2", "C3"] or (SMOKE_MODEL, SMOKE_REVISION) != (MODEL, REVISION):
            raise RuntimeError("Scientific protocol mismatch")
        print("Source/protocol checks PASS; RQ4_STATUS=PENDING_A100_EXECUTION; no inference executed")
        return 0
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        environment = preflight(output)
        from huggingface_hub import snapshot_download
        snapshot = Path(snapshot_download(repo_id=MODEL, revision=REVISION,
            allow_patterns=["config.json", "pytorch_model.bin", "tokenizer_config.json",
                            "special_tokens_map.json", "vocab.json", "merges.txt"]))
        if snapshot.name != REVISION:
            raise RuntimeError("Downloaded model revision mismatch")
        model_lock = json.loads((ROOT / "model.lock.json").read_text())["models"]["rq4_a100"]
        if hashlib.sha256((snapshot / "config.json").read_bytes()).hexdigest() != model_lock["config_sha256"]:
            raise RuntimeError("Pinned model config hash mismatch")
        dump(output / "model_download.json", {"model": MODEL, "revision": snapshot.name,
            "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir() if p.is_file()}})
        os.environ.update(TRACEAI_DEVICE="cuda", TRACEAI_MODEL_ID=MODEL,
                          TRACEAI_MODEL_REVISION=REVISION, HF_HUB_OFFLINE="1")
        os.environ["TRACEAI_MODEL_DIR"] = ""
        from traceai.campaigns.rq4 import run_rq4_campaign
        with ResourceSampler(output / "runtime_resource_timeseries.csv") as sampler:
            rc = run_rq4_campaign(profile="gpu", quick=True, mode="publication",
                output_dir=output, campaign_id=output.name, a100_release=True)
        combined = output / "raw_requests.csv"
        observations = rows(combined)
        if observations:
            # Retain the original combined native output as provenance; split the publication denominators.
            combined.rename(output / "native_all_requests.csv")
            for filename, is_fault in [("raw_requests.csv", False), ("fault_observations.csv", True)]:
                with (output / filename).open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(observations[0]))
                    writer.writeheader()
                    writer.writerows(r for r in observations if ("fault" in r["trial_id"]) == is_fault)
        if sampler.error:
            raise RuntimeError(sampler.error)
        report = validate(output, environment, rc)
        return 0 if report["status"] == "VALID_FOR_PUBLICATION" else 1
    except Exception:
        (output / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        dump(output / "validation_report.json", {"status": "NOT_VALID_FOR_PUBLICATION", "error": traceback.format_exc()})
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
