"""RQ1 Traceability Coverage Campaign — Typed Domain Coverage.

Computes separate coverage for AI/ML-BOM, SBOM, HBOM, OBOM domains.
Uses canonical identities and typed ground-truth schema.
"""

import csv
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from traceai.hashing import hash_file, hash_json
from traceai.logging_config import get_logger
from traceai.settings import get_project_root, load_profile_config

logger = get_logger("campaigns.rq1")

NOT_APPLICABLE = "NOT_APPLICABLE"


def run_rq1_campaign(profile: str = "local", quick: bool = False,
                     output_dir: Path = Path("results")) -> int:
    """Run the RQ1 typed traceability coverage campaign."""
    root = get_project_root()
    campaign_id = f"rq1-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    result_dir = output_dir / "rq1" / campaign_id
    raw_dir = result_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  RQ1 Campaign: {campaign_id}")
    print(f"  Profile: {profile}, Quick: {quick}")

    # 1. Build typed ground-truth graph
    gt = _build_typed_ground_truth(root, profile)
    gt_path = result_dir / "ground_truth_graph.json"
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt, f, indent=2)

    # 2. Run Syft
    syft_result = _run_syft(root, result_dir)

    # 3. Run Trivy
    trivy_result = _run_trivy(root, result_dir)

    # 4. Generate TraceAI AI/ML-BOM
    ml_bom = _generate_ml_bom(root, profile, result_dir)

    # 5. Generate OBOM (operational snapshot)
    obom = _generate_obom(root, result_dir)

    # 6. Compute typed domain coverage
    metrics = _compute_typed_coverage(gt, syft_result, trivy_result, ml_bom, obom, profile)

    # 7. Build linked graph
    linked = _build_linked_graph(syft_result, trivy_result, ml_bom, obom)
    with open(result_dir / "linked_graph.json", "w", encoding="utf-8") as f:
        json.dump(linked, f, indent=2)

    # 8. Save results
    _save_results(metrics, result_dir, campaign_id, profile, quick)

    # 9. Generate LaTeX and CSV outputs
    gen_dir = root / "generated" / "rq1"
    gen_dir.mkdir(parents=True, exist_ok=True)
    _generate_outputs(metrics, gt, gen_dir, campaign_id, profile, quick,
                      syft_result, trivy_result)

    # Print summary
    print(f"\n  Ground-truth nodes: {gt['meta']['total_nodes']} "
          f"(applicable: {gt['meta']['applicable_nodes']})")
    print(f"  Syft: {metrics['syft']['component_count']} components")
    print(f"  Trivy: {metrics['trivy']['component_count']} components "
          f"(status: {metrics['trivy']['status']})")
    print(f"  --- Domain Coverage ---")
    for domain in ["mlbom", "sbom", "hbom", "obom"]:
        dc = metrics["domain_coverage"].get(domain, {})
        print(f"    {domain}: {dc.get('coverage', 'N/A')} "
              f"({dc.get('matched', 0)}/{dc.get('applicable', 0)})")
    print(f"  Composite coverage: {metrics['composite_coverage']}")
    print(f"  Syft/Trivy Jaccard (packages): {metrics['syft_trivy_jaccard']}")
    print(f"  Results: {result_dir}")

    return 0


def _build_typed_ground_truth(root: Path, profile: str) -> dict:
    """Build typed ground-truth graph with domain assignments."""
    import platform
    import torch
    import transformers
    import psutil

    has_gpu = torch.cuda.is_available()
    nodes = []
    edges = []

    def node(nid, ntype, name, version="", expected_bom=None,
             applicability="REQUIRED", purl="", sha256="", **kw):
        n = {
            "id": nid, "type": ntype, "name": name, "version": version,
            "expected_bom": expected_bom or [],
            "applicability": applicability,
            "canonical_identity": {"purl": purl, "sha256": sha256,
                                   "name": name, "version": version},
        }
        n.update(kw)
        nodes.append(n)

    def edge(src, tgt, rel, domain=""):
        edges.append({"source": src, "target": tgt, "relationship": rel, "domain": domain})

    # --- Model domain (mlbom) ---
    node("model-gpt2", "model", "openai-community/gpt2",
         expected_bom=["mlbom"], purl="pkg:huggingface/openai-community/gpt2")
    node("model-weights", "weight", "model.safetensors",
         expected_bom=["mlbom"])
    node("tokenizer", "tokenizer", "gpt2-tokenizer",
         expected_bom=["mlbom"])
    node("model-config", "dataset", "config.json",
         expected_bom=["mlbom"], note="architecture configuration")
    node("generation-config", "dataset", "generation_config.json",
         expected_bom=["mlbom"])
    node("dataset-manifest", "dataset", "fixtures/datasets/manifest.json",
         expected_bom=["mlbom"])

    # --- Package domain (sbom) ---
    node("pytorch", "package", "torch", version=torch.__version__,
         expected_bom=["sbom"], purl=f"pkg:pypi/torch@{torch.__version__}")
    node("transformers-pkg", "package", "transformers", version=transformers.__version__,
         expected_bom=["sbom"], purl=f"pkg:pypi/transformers@{transformers.__version__}")

    # Direct deps from requirements.txt
    direct_deps = _get_direct_deps(root)
    for dep_name, dep_ver in direct_deps.items():
        if dep_name in ("torch", "transformers"):
            continue  # Already added
        node(f"pkg-{dep_name}", "package", dep_name, version=dep_ver,
             expected_bom=["sbom"], purl=f"pkg:pypi/{dep_name}@{dep_ver}")

    # --- Runtime/hardware domain (hbom) ---
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    node("python-runtime", "runtime", "python", version=py_ver,
         expected_bom=["hbom"], purl=f"pkg:generic/python@{py_ver}")
    node("os-platform", "runtime", platform.system(), version=platform.release(),
         expected_bom=["hbom"])
    node("host-cpu", "hardware", "CPU", version=str(os.cpu_count()),
         expected_bom=["hbom"])
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    node("host-ram", "hardware", "RAM", version=f"{ram_gb}GB",
         expected_bom=["hbom"])

    # GPU — NOT_APPLICABLE if no GPU
    gpu_app = "REQUIRED" if has_gpu else NOT_APPLICABLE
    node("host-gpu", "hardware", "GPU",
         expected_bom=["hbom"], applicability=gpu_app,
         note="N/A" if not has_gpu else torch.cuda.get_device_name(0))
    node("cuda-runtime", "runtime", "CUDA",
         expected_bom=["hbom"], applicability=gpu_app,
         version=torch.version.cuda or "N/A" if has_gpu else "N/A")

    # --- Operational domain (obom) ---
    node("inference-service", "service", "traceai-inference", version="0.1.0",
         expected_bom=["obom"])
    node("runtime-policy", "policy", "config/policy.yaml",
         expected_bom=["obom"])
    node("traceai-app", "service", "traceai", version="0.1.0",
         expected_bom=["obom", "sbom"])

    # --- Edges ---
    edge("inference-service", "traceai-app", "dependsOn", "obom")
    edge("traceai-app", "model-gpt2", "dependsOn", "mlbom")
    edge("model-gpt2", "tokenizer", "uses", "mlbom")
    edge("model-gpt2", "model-weights", "contains", "mlbom")
    edge("model-gpt2", "model-config", "describedBy", "mlbom")
    edge("model-gpt2", "generation-config", "describedBy", "mlbom")
    edge("model-gpt2", "dataset-manifest", "evaluatedWith", "mlbom")
    edge("traceai-app", "pytorch", "dependsOn", "sbom")
    edge("traceai-app", "transformers-pkg", "dependsOn", "sbom")
    for dep_name in direct_deps:
        if dep_name not in ("torch", "transformers"):
            edge("traceai-app", f"pkg-{dep_name}", "dependsOn", "sbom")
    edge("pytorch", "python-runtime", "dependsOn", "hbom")
    edge("python-runtime", "os-platform", "runsOn", "hbom")
    edge("inference-service", "runtime-policy", "governedBy", "obom")
    edge("inference-service", "host-cpu", "deployedOn", "hbom")
    edge("inference-service", "host-ram", "uses", "hbom")
    if has_gpu:
        edge("pytorch", "cuda-runtime", "dependsOn", "hbom")
        edge("inference-service", "host-gpu", "deployedOn", "hbom")

    applicable = [n for n in nodes if n["applicability"] != NOT_APPLICABLE]

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "total_nodes": len(nodes),
            "applicable_nodes": len(applicable),
            "total_edges": len(edges),
            "profile": profile,
            "gpu_available": has_gpu,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


def _get_direct_deps(root: Path) -> dict[str, str]:
    """Get installed versions of direct dependencies."""
    deps = {}
    req_path = root / "requirements.txt"
    if not req_path.exists():
        return deps
    import importlib.metadata
    for line in req_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg_name = line.split(">=")[0].split("==")[0].split("[")[0].strip()
        try:
            ver = importlib.metadata.version(pkg_name)
            deps[pkg_name] = ver
        except importlib.metadata.PackageNotFoundError:
            deps[pkg_name] = "not_installed"
    return deps


def _find_tool(name: str) -> Optional[str]:
    root = get_project_root()
    local = root / ".tools" / "bin" / f"{name}.exe"
    if local.exists():
        return str(local)
    return shutil.which(name)


def _run_syft(root: Path, result_dir: Path) -> dict:
    """Run Syft and return result metadata."""
    syft = _find_tool("syft")
    result = {"tool": "syft", "available": bool(syft), "component_count": 0,
              "components": [], "status": "not_available", "bom": None}
    if not syft:
        return result

    out_path = result_dir / "syft.cdx.json"
    try:
        cmd = [syft, f"dir:{root}", "-o", f"cyclonedx-json={out_path}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if out_path.exists() and out_path.stat().st_size > 100:
            with open(out_path, "r", encoding="utf-8") as f:
                bom = json.load(f)
            components = bom.get("components", [])
            result["component_count"] = len(components)
            result["components"] = [
                {"name": c.get("name", ""), "version": c.get("version", ""),
                 "purl": c.get("purl", ""), "type": c.get("type", "")}
                for c in components
            ]
            result["status"] = "success"
            result["bom"] = bom
        else:
            result["status"] = "empty_output"
            result["stderr"] = (proc.stderr or "")[:500]
    except Exception as e:
        result["status"] = f"error: {e}"
    return result


def _run_trivy(root: Path, result_dir: Path) -> dict:
    """Run Trivy and return result metadata."""
    trivy = _find_tool("trivy")
    result = {"tool": "trivy", "available": bool(trivy), "component_count": 0,
              "components": [], "status": "not_available", "bom": None,
              "limitation": None}
    if not trivy:
        return result

    out_path = result_dir / "trivy.cdx.json"
    try:
        # Scan with explicit lockfile targets
        cmd = [trivy, "fs", str(root), "--format", "cyclonedx", "--output", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if out_path.exists() and out_path.stat().st_size > 100:
            with open(out_path, "r", encoding="utf-8") as f:
                bom = json.load(f)
            components = bom.get("components", [])
            result["component_count"] = len(components)
            result["components"] = [
                {"name": c.get("name", ""), "version": c.get("version", ""),
                 "purl": c.get("purl", ""), "type": c.get("type", "")}
                for c in components
            ]
            if len(components) == 0:
                result["status"] = "TOOL_LIMITATION"
                result["limitation"] = (
                    "Trivy fs scan found 0 components. This occurs when Trivy "
                    "does not detect a supported lockfile format in the project root. "
                    "The project uses requirements.lock (pip freeze format) which may "
                    "not be recognized by this Trivy version. This is a tool limitation, "
                    "not evidence of absence."
                )
            else:
                result["status"] = "success"
            result["bom"] = bom
        else:
            result["status"] = "empty_output"
            result["stderr"] = (proc.stderr or "")[:500]
    except Exception as e:
        result["status"] = f"error: {e}"
    return result


def _generate_ml_bom(root: Path, profile: str, result_dir: Path) -> dict:
    """Generate AI/ML-BOM from ground truth."""
    from traceai.bom.cyclonedx_builder import build_cyclonedx_bom
    from traceai.bom.ground_truth import build_ground_truth
    from traceai.settings import get_settings
    settings = get_settings()
    gt = build_ground_truth(settings.model_id, settings.model_dir, profile)
    bom = build_cyclonedx_bom(gt, profile)
    out_path = result_dir / "traceai_ml_bom.cdx.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bom, f, indent=2)
    return bom


def _generate_obom(root: Path, result_dir: Path) -> dict:
    """Generate operational BOM snapshot."""
    import platform, psutil
    obom = {
        "bomFormat": "CycloneDX", "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}", "version": 1,
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat()},
        "components": [
            {"type": "platform", "name": platform.system(),
             "version": platform.release(), "bom-ref": "obom-os"},
            {"type": "platform", "name": "cpu",
             "version": str(os.cpu_count()), "bom-ref": "obom-cpu"},
            {"type": "platform", "name": "ram",
             "version": f"{round(psutil.virtual_memory().total/(1024**3),1)}GB",
             "bom-ref": "obom-ram"},
            {"type": "application", "name": "traceai-inference",
             "version": "0.1.0", "bom-ref": "obom-service"},
        ],
    }
    with open(result_dir / "traceai_obom.cdx.json", "w", encoding="utf-8") as f:
        json.dump(obom, f, indent=2)
    return obom


def _compute_typed_coverage(gt, syft_result, trivy_result, ml_bom, obom, profile) -> dict:
    """Compute typed domain coverage metrics."""
    nodes = gt["nodes"]
    applicable = [n for n in nodes if n["applicability"] != NOT_APPLICABLE]

    # Build sets of names found in each BOM
    syft_names = {c["name"].lower() for c in syft_result["components"]}
    trivy_names = {c["name"].lower() for c in trivy_result["components"]}
    ml_names = {c.get("name", "").lower() for c in ml_bom.get("components", [])}
    obom_names = {c.get("name", "").lower() for c in obom.get("components", [])}

    # Domain coverage
    domain_coverage = {}
    for domain in ["mlbom", "sbom", "hbom", "obom"]:
        domain_nodes = [n for n in applicable if domain in n["expected_bom"]]
        if not domain_nodes:
            domain_coverage[domain] = {"applicable": 0, "matched": 0, "coverage": "N/A"}
            continue

        # Which BOM source covers this domain?
        if domain == "mlbom":
            source_names = ml_names
        elif domain == "sbom":
            source_names = syft_names | trivy_names
        elif domain == "hbom":
            source_names = obom_names  # HBOM captured in operational snapshot
        elif domain == "obom":
            source_names = obom_names | ml_names

        matched = sum(1 for n in domain_nodes
                      if n["canonical_identity"]["name"].lower() in source_names)
        cov = round(matched / len(domain_nodes), 4) if domain_nodes else 0
        domain_coverage[domain] = {
            "applicable": len(domain_nodes),
            "matched": matched,
            "coverage": cov,
        }

    # Composite coverage (all applicable nodes matched by any BOM)
    all_bom_names = syft_names | trivy_names | ml_names | obom_names
    composite_matched = sum(1 for n in applicable
                           if n["canonical_identity"]["name"].lower() in all_bom_names)
    composite_coverage = round(composite_matched / len(applicable), 4) if applicable else 0

    # Syft/Trivy Jaccard on package universe only
    package_nodes = [n for n in applicable if n["type"] == "package"]
    pkg_universe = {n["canonical_identity"]["name"].lower() for n in package_nodes}
    syft_pkg = syft_names & pkg_universe
    trivy_pkg = trivy_names & pkg_universe
    pkg_union = syft_pkg | trivy_pkg
    syft_trivy_jaccard = round(len(syft_pkg & trivy_pkg) / len(pkg_union), 4) if pkg_union else "N/A"

    # Schema validation
    from traceai.bom.validators import validate_cyclonedx_bom
    schema_failures = 0
    for bom_data in [ml_bom, syft_result.get("bom"), trivy_result.get("bom"), obom]:
        if bom_data:
            r = validate_cyclonedx_bom(bom_data)
            if not r.valid:
                schema_failures += 1

    # Orphan/duplicate rates
    def dup_rate(components):
        if not components:
            return 0
        names = [c.get("name", "") for c in components]
        return round(1 - len(set(names)) / len(names), 4) if names else 0

    syft_bom_data = syft_result.get("bom") or {}
    trivy_bom_data = trivy_result.get("bom") or {}

    return {
        "domain_coverage": domain_coverage,
        "composite_coverage": composite_coverage,
        "composite_matched": composite_matched,
        "composite_applicable": len(applicable),
        "syft": {
            "component_count": syft_result["component_count"],
            "status": syft_result["status"],
        },
        "trivy": {
            "component_count": trivy_result["component_count"],
            "status": trivy_result["status"],
            "limitation": trivy_result.get("limitation"),
        },
        "syft_trivy_jaccard": syft_trivy_jaccard,
        "schema_validation_failures": schema_failures,
        "duplicate_rate_syft": dup_rate(syft_bom_data.get("components", [])),
        "duplicate_rate_traceai": dup_rate(ml_bom.get("components", [])),
        "ground_truth_total": gt["meta"]["total_nodes"],
        "ground_truth_applicable": gt["meta"]["applicable_nodes"],
        "ground_truth_edges": gt["meta"]["total_edges"],
    }


def _build_linked_graph(syft_r, trivy_r, ml_bom, obom) -> dict:
    links = []
    ml_serial = ml_bom.get("serialNumber", "")
    if syft_r.get("bom"):
        links.append({"source": ml_serial, "target": syft_r["bom"].get("serialNumber", ""),
                      "type": "sbom-syft", "rel": "dependsOn"})
    if trivy_r.get("bom"):
        links.append({"source": ml_serial, "target": trivy_r["bom"].get("serialNumber", ""),
                      "type": "sbom-trivy", "rel": "dependsOn"})
    links.append({"source": ml_serial, "target": obom.get("serialNumber", ""),
                  "type": "obom", "rel": "describedBy"})
    return {"links": links, "count": len(links)}


def _save_results(metrics, result_dir, campaign_id, profile, quick):
    csv_path = result_dir / "rq1_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["campaign_id", campaign_id])
        w.writerow(["composite_coverage", metrics["composite_coverage"]])
        for domain, dc in metrics["domain_coverage"].items():
            w.writerow([f"{domain}_coverage", dc.get("coverage", "N/A")])
        w.writerow(["syft_trivy_jaccard", metrics["syft_trivy_jaccard"]])
        w.writerow(["schema_failures", metrics["schema_validation_failures"]])
        w.writerow(["trivy_status", metrics["trivy"]["status"]])

    summary = {"campaign_id": campaign_id, "profile": profile, "quick": quick,
               "timestamp": datetime.now(timezone.utc).isoformat(), "metrics": metrics}
    with open(result_dir / "rq1_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)


def _generate_outputs(metrics, gt, gen_dir, campaign_id, profile, quick,
                      syft_result, trivy_result):
    """Generate LaTeX tables and CSV outputs."""
    from traceai.environment import escape_latex

    # Domain coverage table
    lines = [
        r"\begin{table}[htbp]",
        r"\caption{RQ1 Typed Domain Coverage (Diagnostic)}",
        r"\label{tab:rq1-domain-coverage}",
        r"\centering\small",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"\textbf{Domain} & \textbf{Applicable} & \textbf{Matched} & \textbf{Coverage} \\",
        r"\midrule",
    ]
    for domain in ["mlbom", "sbom", "hbom", "obom"]:
        dc = metrics["domain_coverage"].get(domain, {})
        lines.append(f"  {domain.upper()} & {dc.get('applicable', 0)} & "
                     f"{dc.get('matched', 0)} & {dc.get('coverage', 'N/A')} \\\\")
    lines.extend([
        r"\midrule",
        f"  Composite & {metrics['composite_applicable']} & "
        f"{metrics['composite_matched']} & {metrics['composite_coverage']} \\\\",
        r"\bottomrule", r"\end{tabular}", r"\end{table}",
    ])
    (gen_dir / "domain_coverage_table.tex").write_text("\n".join(lines), encoding="utf-8")

    # Coverage by type CSV
    with open(gen_dir / "coverage_by_type.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["domain", "applicable", "matched", "coverage"])
        for domain in ["mlbom", "sbom", "hbom", "obom"]:
            dc = metrics["domain_coverage"].get(domain, {})
            w.writerow([domain, dc.get("applicable", 0), dc.get("matched", 0),
                        dc.get("coverage", "N/A")])

    # Tool limitations
    lim_lines = ["# RQ1 Tool Limitations\n"]
    if metrics["trivy"]["status"] == "TOOL_LIMITATION":
        lim_lines.append(f"## Trivy\n\n{metrics['trivy']['limitation']}\n")
    else:
        lim_lines.append("No tool limitations detected.\n")
    (gen_dir / "tool_limitations.md").write_text("\n".join(lim_lines), encoding="utf-8")

    # Identity mapping CSV
    ml_bom_names = set()
    # We don't have ml_bom here, use gen_dir parent to find it
    with open(gen_dir / "identity_mapping.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "name", "type", "expected_bom", "applicability",
                    "found_in_syft", "found_in_trivy"])
        syft_n = {c["name"].lower() for c in syft_result["components"]}
        trivy_n = {c["name"].lower() for c in trivy_result["components"]}
        for node in gt["nodes"]:
            nm = node["canonical_identity"]["name"].lower()
            w.writerow([
                node["id"], node["name"], node["type"],
                "|".join(node["expected_bom"]), node["applicability"],
                nm in syft_n, nm in trivy_n,
            ])

    # Composite table
    comp_lines = [
        f"% RQ1 Composite: campaign={campaign_id} profile={profile}",
        r"\paragraph{RQ1 Coverage Summary}",
        f"Composite linked-graph coverage: {metrics['composite_coverage']} "
        f"({metrics['composite_matched']}/{metrics['composite_applicable']} applicable nodes). "
        f"Syft/Trivy package Jaccard: {metrics['syft_trivy_jaccard']}. "
        f"Schema failures: {metrics['schema_validation_failures']}.",
    ]
    if metrics["trivy"]["status"] == "TOOL_LIMITATION":
        comp_lines.append(r"\textit{Note: Trivy reported 0 components (tool limitation).}")
    (gen_dir / "composite_coverage_table.tex").write_text(
        "\n".join(comp_lines), encoding="utf-8")
