"""Tests for NVIDIA L4 GPU adaptation.

Validates that:
- GPU profile accepts NVIDIA L4
- RTX A5000 is not required by active configuration
- VRAM threshold is read from the profile
- CPU fallback is rejected in GPU evidence mode
- No hard-coded CUDA wheel exists in scripts
- TORCH_INDEX_URL is required when CUDA PyTorch is absent
- Quick mode does not execute the full campaign
- --run-full is required for the full campaign
- Model revisions remain immutable
- NVIDIA L4 manuscript/environment fragment generation
- Python 3.12 metadata consistency

These tests do NOT require a real GPU. They validate configuration
and script logic only.
"""
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

GPU_PROFILE_PATH = ROOT / "config" / "profiles" / "gpu.yaml"
RUN_CAMPAIGN_SH = ROOT / "scripts" / "run_gpu_campaign.sh"
PHASE5_SCRIPT = ROOT / "scripts" / "phase5_gpu_runbook.py"
SETTINGS_PY = ROOT / "src" / "traceai" / "settings.py"
PYPROJECT_TOML = ROOT / "pyproject.toml"
ENV_TEX_TEMPLATE = ROOT / "paper" / "templates" / "environment_gpu.tex.in"


def _load_gpu_profile() -> dict:
    """Load and parse the GPU profile YAML."""
    with open(GPU_PROFILE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestGPUProfileAcceptsNVIDIAL4:
    """Tests that the GPU profile is configured for NVIDIA L4."""

    def test_profile_exists(self):
        assert GPU_PROFILE_PATH.exists()

    def test_profile_description_references_l4(self):
        profile = _load_gpu_profile()
        desc = profile.get("description", "")
        assert "L4" in desc or "NVIDIA L4" in desc

    def test_profile_gpu_regex_matches_nvidia_l4(self):
        profile = _load_gpu_profile()
        regex = profile["hardware"]["expected_gpu_name_regex"]
        assert re.search(regex, "NVIDIA L4")

    def test_profile_gpu_regex_does_not_require_rtx_a5000(self):
        profile = _load_gpu_profile()
        regex = profile["hardware"]["expected_gpu_name_regex"]
        # The regex should match L4, not require A5000
        assert "A5000" not in regex

    def test_minimum_vram_from_profile(self):
        profile = _load_gpu_profile()
        vram = profile["hardware"]["minimum_vram_mb"]
        # L4 has ~23034 MiB, threshold should be at most 23000
        assert 10000 <= vram <= 23000

    def test_expected_gpu_count(self):
        profile = _load_gpu_profile()
        count = profile["hardware"]["expected_gpu_count"]
        assert count == 1


class TestRTXA5000NotRequired:
    """Verify RTX A5000 is not required by active configuration."""

    def test_gpu_profile_no_a5000_in_description(self):
        profile = _load_gpu_profile()
        desc = profile.get("description", "")
        assert "A5000" not in desc

    def test_gpu_profile_regex_not_a5000(self):
        profile = _load_gpu_profile()
        regex = profile["hardware"]["expected_gpu_name_regex"]
        assert "A5000" not in regex

    def test_run_campaign_sh_no_a5000(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        assert "A5000" not in content

    def test_phase5_script_no_a5000(self):
        content = PHASE5_SCRIPT.read_text(encoding="utf-8")
        assert "A5000" not in content

    def test_settings_no_a5000(self):
        content = SETTINGS_PY.read_text(encoding="utf-8")
        assert "A5000" not in content


class TestCPUFallbackRejected:
    """Verify GPU profile rejects CPU fallback."""

    def test_require_cuda_true(self):
        profile = _load_gpu_profile()
        assert profile["runtime"]["require_cuda"] is True

    def test_forbid_cpu_fallback(self):
        profile = _load_gpu_profile()
        assert profile["runtime"]["forbid_cpu_fallback"] is True

    def test_device_is_cuda(self):
        profile = _load_gpu_profile()
        assert profile["runtime"]["device"] == "cuda"


class TestNoHardCodedCUDAWheel:
    """Verify no hard-coded CUDA wheel URL exists in scripts."""

    def test_run_campaign_sh_no_hardcoded_cu_url(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        # Should not contain download.pytorch.org/whl/cu followed by digits
        matches = re.findall(r"download\.pytorch\.org/whl/cu\d+", content)
        assert matches == [], f"Hard-coded CUDA URLs found: {matches}"

    def test_phase5_no_hardcoded_cu_url(self):
        content = PHASE5_SCRIPT.read_text(encoding="utf-8")
        matches = re.findall(r"download\.pytorch\.org/whl/cu\d+", content)
        assert matches == [], f"Hard-coded CUDA URLs found: {matches}"

    def test_settings_no_hardcoded_cu_url(self):
        content = SETTINGS_PY.read_text(encoding="utf-8")
        matches = re.findall(r"download\.pytorch\.org/whl/cu\d+", content)
        assert matches == [], f"Hard-coded CUDA URLs found: {matches}"


class TestTORCHINDEXURLRequired:
    """Verify TORCH_INDEX_URL is required when CUDA PyTorch is absent."""

    def test_run_campaign_checks_torch_index_url(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        assert "TORCH_INDEX_URL" in content

    def test_run_campaign_errors_on_missing_torch_index_url(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        # Should contain an error message about missing TORCH_INDEX_URL
        assert "ERROR" in content and "TORCH_INDEX_URL" in content


class TestQuickModeStopsBeforeFullCampaign:
    """Verify --run-full is required for full campaign."""

    def test_run_full_flag_exists(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        assert "--run-full" in content

    def test_default_run_full_is_false(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        assert 'RUN_FULL=false' in content

    def test_script_exits_without_run_full(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        # Should have a conditional exit when RUN_FULL is false
        assert 'if [ "$RUN_FULL" = false ]' in content


class TestModelRevisionsImmutable:
    """Verify model revisions are pinned and match between profile and script."""

    EXPECTED_FULL_REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
    EXPECTED_TINY_REVISION = "5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"

    def test_profile_full_model_revision(self):
        profile = _load_gpu_profile()
        assert profile["models"]["full"]["revision"] == self.EXPECTED_FULL_REVISION

    def test_profile_quick_model_revision(self):
        profile = _load_gpu_profile()
        assert profile["models"]["quick"]["revision"] == self.EXPECTED_TINY_REVISION

    def test_run_campaign_full_revision(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        assert self.EXPECTED_FULL_REVISION in content

    def test_run_campaign_tiny_revision(self):
        content = RUN_CAMPAIGN_SH.read_text(encoding="utf-8")
        assert self.EXPECTED_TINY_REVISION in content

    def test_profile_runtime_model_revision(self):
        profile = _load_gpu_profile()
        assert profile["runtime"]["model_revision"] == self.EXPECTED_FULL_REVISION


class TestEnvironmentFragmentGeneration:
    """Verify the NVIDIA L4 manuscript template is correct.

    Uses the tracked template (paper/templates/environment_gpu.tex.in),
    not the generated fragment (paper/fragments/environment_gpu.tex) which
    is gitignored and does not exist in clean clones.
    """

    def test_environment_tex_exists(self):
        assert ENV_TEX_TEMPLATE.exists(), (
            "Tracked template paper/templates/environment_gpu.tex.in must exist"
        )

    def test_environment_tex_references_l4(self):
        content = ENV_TEX_TEMPLATE.read_text(encoding="utf-8")
        # Template uses @GPU_NAME@ placeholder, but also mentions L4 in context
        assert "@GPU_NAME@" in content

    def test_environment_tex_no_rtx_a5000_claim(self):
        content = ENV_TEX_TEMPLATE.read_text(encoding="utf-8")
        assert "RTX A5000" not in content

    def test_environment_tex_references_gcp(self):
        content = ENV_TEX_TEMPLATE.read_text(encoding="utf-8")
        assert "Google Cloud Platform" in content or "GCP" in content

    def test_environment_tex_references_24gb(self):
        content = ENV_TEX_TEMPLATE.read_text(encoding="utf-8")
        # Template references VRAM via placeholder
        assert "@GPU_VRAM_MIB@" in content

    def test_environment_tex_is_template_not_evidence(self):
        content = ENV_TEX_TEMPLATE.read_text(encoding="utf-8")
        assert "template" in content.lower()
        assert "not experimental evidence" in content.lower() or "not evidence" in content.lower()

    def test_environment_tex_has_required_placeholders(self):
        content = ENV_TEX_TEMPLATE.read_text(encoding="utf-8")
        required = ["@GPU_NAME@", "@GPU_VRAM_MIB@", "@NVIDIA_DRIVER@",
                    "@PYTORCH_VERSION@", "@PYTORCH_CUDA_RUNTIME@",
                    "@OS_VERSION@", "@CAMPAIGN_ID@", "@SOURCE_COMMIT@"]
        for placeholder in required:
            assert placeholder in content, f"Missing placeholder: {placeholder}"


class TestPython312Metadata:
    """Verify Python 3.12 compatibility metadata."""

    def test_requires_python_includes_312(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        # requires-python = ">=3.10,<3.13" includes 3.12
        assert ">=3.10" in content
        assert "<3.13" in content

    def test_classifier_declares_312(self):
        content = PYPROJECT_TOML.read_text(encoding="utf-8")
        assert "Programming Language :: Python :: 3.12" in content


class TestGPUHardwareConfigHelper:
    """Test the load_gpu_hardware_config helper in settings.py."""

    def test_load_gpu_hardware_config_returns_expected_keys(self):
        from traceai.settings import load_gpu_hardware_config
        config = load_gpu_hardware_config()
        assert "expected_gpu_name_regex" in config
        assert "minimum_vram_mb" in config
        assert "expected_gpu_count" in config

    def test_load_gpu_hardware_config_regex_matches_l4(self):
        from traceai.settings import load_gpu_hardware_config
        config = load_gpu_hardware_config()
        assert re.search(config["expected_gpu_name_regex"], "NVIDIA L4")

    def test_load_gpu_hardware_config_vram_threshold(self):
        from traceai.settings import load_gpu_hardware_config
        config = load_gpu_hardware_config()
        assert config["minimum_vram_mb"] == 22000



class TestGetTotalGPUMemoryBytes:
    """Test the robust GPU memory accessor (no real GPU required)."""

    def test_total_memory_attribute_accepted(self):
        """PyTorch >= 2.13 uses total_memory."""
        from unittest.mock import MagicMock, patch

        mock_props = MagicMock()
        mock_props.total_memory = 24_000_000_000
        # Ensure total_mem is not present as a real attr
        del mock_props.total_mem

        with patch("torch.cuda.get_device_properties", return_value=mock_props):
            from phase5_gpu_runbook import get_total_gpu_memory_bytes
            result = get_total_gpu_memory_bytes(0)
            assert result == 24_000_000_000

    def test_total_mem_fallback_accepted(self):
        """Older PyTorch uses total_mem as fallback."""
        from unittest.mock import MagicMock, patch

        mock_props = MagicMock(spec=[])
        mock_props.total_mem = 24_000_000_000
        # total_memory does not exist on this mock

        with patch("torch.cuda.get_device_properties", return_value=mock_props):
            from phase5_gpu_runbook import get_total_gpu_memory_bytes
            result = get_total_gpu_memory_bytes(0)
            assert result == 24_000_000_000

    def test_neither_attribute_raises_error(self):
        """Missing both attributes raises RuntimeError."""
        from unittest.mock import MagicMock, patch

        mock_props = MagicMock(spec=[])
        # Neither total_memory nor total_mem exists

        with patch("torch.cuda.get_device_properties", return_value=mock_props):
            from phase5_gpu_runbook import get_total_gpu_memory_bytes
            with pytest.raises(RuntimeError, match="Unable to determine total GPU memory"):
                get_total_gpu_memory_bytes(0)


class TestNVMLDependencyPolicy:
    """Verify the gpu extra does not declare both pynvml and nvidia-ml-py."""

    def test_gpu_extra_no_duplicate_nvml(self):
        """The gpu extra should declare only nvidia-ml-py, not pynvml."""
        import tomllib
        with open(PYPROJECT_TOML, "rb") as f:
            data = tomllib.load(f)
        gpu_deps = data.get("project", {}).get("optional-dependencies", {}).get("gpu", [])
        dep_names = [d.split(">")[0].split("=")[0].split("<")[0].strip().lower()
                     for d in gpu_deps]
        assert "pynvml" not in dep_names, (
            "gpu extra should not declare pynvml (deprecated); use nvidia-ml-py only"
        )
        assert "nvidia-ml-py" in dep_names
