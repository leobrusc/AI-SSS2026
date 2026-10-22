"""Release contract tests; synthetic test inputs are never publication evidence."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/a100" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_reject_empty_results(tmp_path):
    report = module("benchmark").validate(tmp_path, {}, 0)
    assert report["status"] == "NOT_VALID_FOR_PUBLICATION"
    assert not report["gates"]["normal_240"]
    assert not report["gates"]["actual_parameter_device"]


@pytest.mark.parametrize("exit_code", [0, 1])
def test_failed_run_packaging(tmp_path, exit_code):
    output = tmp_path / "test-diagnostics"
    output.mkdir()
    (output / "failure.txt").write_text("Synthetic unit-test diagnostic")
    archive, checksum = module("package_results").package(output, exit_code)
    assert checksum.read_text().split()[0] == hashlib.sha256(archive.read_bytes()).hexdigest()
    with tarfile.open(archive) as tar:
        report = json.load(tar.extractfile("test-diagnostics/validation_report.json"))
        assert report["status"] == "NOT_VALID_FOR_PUBLICATION"
        for line in tar.extractfile("test-diagnostics/SHA256SUMS").read().decode().splitlines():
            digest, name = line.split("  ", 1)
            assert hashlib.sha256(tar.extractfile(f"test-diagnostics/{name}").read()).hexdigest() == digest


def test_exit_failure_downgrades_report(tmp_path):
    (tmp_path / "validation_report.json").write_text(json.dumps({"status": "VALID_FOR_PUBLICATION"}))
    module("package_results").package(tmp_path, 1)
    assert json.loads((tmp_path / "validation_report.json").read_text())["status"] == "NOT_VALID_FOR_PUBLICATION"


def test_source_manifest_detects_tampering(tmp_path, monkeypatch):
    runner = module("benchmark")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    (tmp_path / "benchmark-source-manifest.json").write_text(json.dumps({"uv.lock": "0" * 64}))
    (tmp_path / "uv.lock").write_text("changed")
    with pytest.raises(RuntimeError, match="integrity mismatch"):
        runner.verify_source()


def test_source_archive_fallback():
    assert module("benchmark").verify_source()
    assert json.loads((ROOT / "benchmark-release.json").read_text())["rq4_status"] == "PENDING_A100_EXECUTION"


def test_real_parameter_observation_and_no_revision_fallback():
    from traceai.service.inference import InferenceEngine
    engine = InferenceEngine(revision="requested-only", device="cpu")
    assert engine.resolved_revision is None
    assert engine.parameter_device == "unknown"
    assert engine.parameter_dtype == "unknown"


@pytest.mark.gpu
def test_actual_cuda_allocation():
    import torch
    if not torch.cuda.is_available():
        pytest.skip("Real CUDA hardware unavailable; RQ4 remains pending")
    assert torch.ones(1, device="cuda").item() == 1
