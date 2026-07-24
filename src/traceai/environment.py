"""Environment detection and doctor report generation."""

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psutil

from traceai.settings import get_project_root, get_settings, load_profile_config


def _safe_run(cmd: list[str], timeout: int = 10) -> Optional[str]:
    """Run a command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def detect_python() -> dict[str, Any]:
    """Detect Python interpreter details."""
    return {
        "executable": sys.executable,
        "version": sys.version,
        "version_info": list(sys.version_info[:3]),
        "platform": sys.platform,
        "prefix": sys.prefix,
        "in_venv": sys.prefix != sys.base_prefix,
    }


def detect_system() -> dict[str, Any]:
    """Detect operating system and hardware."""
    info: dict[str, Any] = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "hostname_hash": hashlib.sha256(
            platform.node().encode()
        ).hexdigest()[:12],  # Redacted hostname
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "ram_available_gb": round(
            psutil.virtual_memory().available / (1024**3), 2
        ),
    }

    # Windows-specific
    if platform.system() == "Windows":
        edition = _safe_run(
            ["powershell", "-Command", "(Get-CimInstance Win32_OperatingSystem).Caption"]
        )
        if edition:
            info["windows_edition"] = edition

    return info


def detect_gpu() -> dict[str, Any]:
    """Detect GPU and CUDA status."""
    gpu_info: dict[str, Any] = {
        "available": False,
        "device_name": "N/A",
        "vram_total_mb": "N/A",
        "driver_version": "N/A",
        "cuda_version": "N/A",
        "torch_cuda_available": False,
        "torch_cuda_version": "N/A",
    }

    # Check nvidia-smi
    nvidia_smi = _safe_run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    if nvidia_smi:
        parts = nvidia_smi.split(",")
        if len(parts) >= 3:
            gpu_info["available"] = True
            gpu_info["device_name"] = parts[0].strip()
            gpu_info["vram_total_mb"] = int(parts[1].strip())
            gpu_info["driver_version"] = parts[2].strip()

    # Check CUDA via nvidia-smi
    cuda_ver = _safe_run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])

    # Check PyTorch CUDA
    try:
        import torch
        gpu_info["torch_cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            gpu_info["torch_cuda_version"] = torch.version.cuda or "N/A"
            gpu_info["device_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            total_mem = getattr(props, "total_memory", None) or getattr(props, "total_mem", None)
            if total_mem is not None:
                gpu_info["vram_total_mb"] = round(total_mem / (1024**2))
    except ImportError:
        gpu_info["torch_installed"] = False

    return gpu_info


def detect_tools() -> dict[str, Any]:
    """Detect external CLI tools."""
    tools = {}
    tool_checks = {
        "git": ["git", "--version"],
        "docker": ["docker", "--version"],
        "syft": ["syft", "version"],
        "grype": ["grype", "version"],
        "trivy": ["trivy", "--version"],
        "cosign": ["cosign", "version"],
        "kubectl": ["kubectl", "version", "--client", "--short"],
    }

    # Also check .tools/bin
    root = get_project_root()
    tools_bin = root / ".tools" / "bin"

    for tool_name, cmd in tool_checks.items():
        # Check system PATH first, then .tools/bin
        version = _safe_run(cmd)
        if version is None and tools_bin.exists():
            tool_path = tools_bin / (tool_name + (".exe" if os.name == "nt" else ""))
            if tool_path.exists():
                alt_cmd = [str(tool_path)] + cmd[1:]
                version = _safe_run(alt_cmd)

        tools[tool_name] = {
            "status": "available" if version else "missing",
            "version": version,
        }

    return tools


def detect_packages() -> dict[str, str]:
    """Detect installed Python package versions."""
    packages = {}
    check_packages = [
        "torch", "transformers", "tokenizers", "fastapi", "uvicorn",
        "pydantic", "pydantic_settings", "httpx", "pyyaml", "pandas",
        "numpy", "scipy", "matplotlib", "psutil", "jsonschema",
        "cryptography", "pytest", "ruff",
    ]

    for pkg in check_packages:
        try:
            mod = __import__(pkg.replace("-", "_"))
            version = getattr(mod, "__version__", "unknown")
            packages[pkg] = version
        except ImportError:
            packages[pkg] = "not installed"

    return packages


def detect_external_services(profile: str) -> dict[str, Any]:
    """Detect external service connectivity without exposing secrets."""
    services: dict[str, Any] = {}
    settings = get_settings()

    services["harbor"] = {
        "configured": bool(settings.harbor_url),
        "status": "not_required" if profile == "local" else "not_configured",
    }
    services["dependency_track"] = {
        "configured": bool(settings.dependency_track_url),
        "status": "not_required" if profile == "local" else "not_configured",
    }
    services["gitlab"] = {
        "configured": bool(settings.gitlab_url),
        "status": "not_required" if profile == "local" else "not_configured",
    }
    services["kubernetes"] = {
        "configured": bool(settings.kubeconfig),
        "status": "not_required" if profile != "industrial" else "not_configured",
    }

    return services


def generate_doctor_report(profile: str = "local") -> dict[str, Any]:
    """Generate complete doctor report."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "python": detect_python(),
        "system": detect_system(),
        "gpu": detect_gpu(),
        "tools": detect_tools(),
        "packages": detect_packages(),
        "external_services": detect_external_services(profile),
    }

    # Determine readiness
    readiness = determine_readiness(report, profile)
    report["readiness"] = readiness

    return report


def determine_readiness(report: dict, profile: str) -> dict[str, Any]:
    """Determine if the environment is ready for the given profile."""
    blockers = []
    warnings = []

    # All profiles need Python and venv
    if not report["python"]["in_venv"]:
        blockers.append("Not running in virtual environment")

    version_info = report["python"]["version_info"]
    if version_info[0] < 3 or (version_info[0] == 3 and version_info[1] < 10):
        blockers.append(f"Python >= 3.10 required, found {'.'.join(map(str, version_info))}")

    # Check core packages
    for pkg in ["torch", "transformers", "fastapi", "pydantic"]:
        if report["packages"].get(pkg, "not installed") == "not installed":
            blockers.append(f"Required package not installed: {pkg}")

    # GPU warnings
    if not report["gpu"]["torch_cuda_available"]:
        warnings.append("GPU not available; GPU metrics will be N/A")

    # Profile-specific checks
    if profile == "container":
        if report["tools"].get("docker", {}).get("status") != "available":
            blockers.append("Docker not available (required for container profile)")

    if profile == "industrial":
        for svc in ["harbor", "dependency_track", "gitlab", "kubernetes"]:
            if not report["external_services"].get(svc, {}).get("configured"):
                blockers.append(f"{svc} not configured (required for industrial profile)")

    return {
        "ready": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
    }


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters safely for LLNCS."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("_", r"\_"),
        ("%", r"\%"),
        ("&", r"\&"),
        ("#", r"\#"),
        ("$", r"\$"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def generate_environment_tex(report: dict, output_path: Path) -> None:
    """Generate LaTeX-safe environment summary."""
    lines = [
        r"\begin{table}[htbp]",
        r"\caption{Experiment Environment}",
        r"\label{tab:environment}",
        r"\centering",
        r"\begin{tabular}{ll}",
        r"\toprule",
        r"\textbf{Component} & \textbf{Value} \\",
        r"\midrule",
    ]

    entries = [
        ("OS", f"{report['system']['os']} {report['system']['os_release']}"),
        ("Python", report["python"]["version"].split()[0]),
        ("CPU Cores", f"{report['system']['cpu_physical_cores']}P / {report['system']['cpu_logical_cores']}L"),
        ("RAM", f"{report['system']['ram_total_gb']} GB"),
        ("GPU", str(report["gpu"]["device_name"])),
        ("VRAM", f"{report['gpu']['vram_total_mb']} MB" if report["gpu"]["vram_total_mb"] != "N/A" else "N/A"),
        ("CUDA", str(report["gpu"]["torch_cuda_version"])),
        ("PyTorch", report["packages"].get("torch", "N/A")),
        ("Transformers", report["packages"].get("transformers", "N/A")),
        ("Profile", report["profile"]),
    ]

    for key, value in entries:
        lines.append(f"  {escape_latex(key)} & {escape_latex(str(value))} \\\\")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_doctor(profile: str, output_dir: Path) -> int:
    """Run the doctor command and save reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    report = generate_doctor_report(profile)

    # Save JSON report
    json_path = output_dir / "doctor_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    # Save environment.json
    env_path = output_dir / "environment.json"
    with open(env_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": report["timestamp"],
            "profile": profile,
            "python": report["python"],
            "system": report["system"],
            "gpu": report["gpu"],
            "packages": report["packages"],
        }, f, indent=2, default=str)

    # Save LaTeX
    tex_path = output_dir / "environment.tex"
    generate_environment_tex(report, tex_path)

    # Save markdown report
    md_path = output_dir / "doctor_report.md"
    _write_markdown_report(report, md_path)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  TraceAI Doctor Report — Profile: {profile}")
    print(f"{'='*60}")
    print(f"  Python:  {report['python']['version'].split()[0]}")
    print(f"  venv:    {'Yes' if report['python']['in_venv'] else 'NO'}")
    print(f"  GPU:     {report['gpu']['device_name']}")
    print(f"  CUDA:    {report['gpu']['torch_cuda_version']}")
    print(f"  Ready:   {'YES' if report['readiness']['ready'] else 'NO'}")

    if report["readiness"]["blockers"]:
        print(f"\n  BLOCKERS:")
        for b in report["readiness"]["blockers"]:
            print(f"    [X] {b}")

    if report["readiness"]["warnings"]:
        print(f"\n  WARNINGS:")
        for w in report["readiness"]["warnings"]:
            print(f"    [!] {w}")

    print(f"\n  Reports saved to: {output_dir.resolve()}")
    print(f"{'='*60}\n")

    return 0 if report["readiness"]["ready"] else 1


def _write_markdown_report(report: dict, path: Path) -> None:
    """Write a human-readable markdown doctor report."""
    lines = [
        "# TraceAI Doctor Report",
        "",
        f"**Generated:** {report['timestamp']}",
        f"**Profile:** {report['profile']}",
        f"**Ready:** {'✓ Yes' if report['readiness']['ready'] else '✗ No'}",
        "",
        "## System",
        "",
        f"- OS: {report['system']['os']} {report['system']['os_release']}",
        f"- CPU: {report['system']['cpu_physical_cores']}P / {report['system']['cpu_logical_cores']}L cores",
        f"- RAM: {report['system']['ram_total_gb']} GB total, {report['system']['ram_available_gb']} GB available",
        "",
        "## Python",
        "",
        f"- Version: {report['python']['version']}",
        f"- Executable: {report['python']['executable']}",
        f"- Virtual env: {'Yes' if report['python']['in_venv'] else 'No'}",
        "",
        "## GPU",
        "",
        f"- Device: {report['gpu']['device_name']}",
        f"- VRAM: {report['gpu']['vram_total_mb']} MB",
        f"- CUDA (torch): {report['gpu']['torch_cuda_version']}",
        f"- torch.cuda.is_available(): {report['gpu']['torch_cuda_available']}",
        "",
        "## Tools",
        "",
    ]

    for tool, info in report["tools"].items():
        status = info["status"]
        version = info.get("version", "")
        lines.append(f"- {tool}: {status}" + (f" ({version})" if version else ""))

    lines.extend(["", "## Packages", ""])
    for pkg, ver in report["packages"].items():
        lines.append(f"- {pkg}: {ver}")

    if report["readiness"]["blockers"]:
        lines.extend(["", "## Blockers", ""])
        for b in report["readiness"]["blockers"]:
            lines.append(f"- ✗ {b}")

    if report["readiness"]["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for w in report["readiness"]["warnings"]:
            lines.append(f"- ⚠ {w}")

    path.write_text("\n".join(lines), encoding="utf-8")
