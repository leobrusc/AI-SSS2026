"""RQ1 Traceability Coverage Campaign.

Generates ground-truth graph, runs external scanners (Syft, Trivy),
produces AI/ML-BOM, and computes coverage metrics.
"""

import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from traceai.hashing import hash_file, hash_json
from traceai.logging_config import get_logger
from traceai.settings import get_project_root, load_profile_config

logger = get_logger("campaigns.rq1")

NOT_APPLICABLE = "NOT_APPLICABLE_LOCAL_PROFILE"


def run_rq1_campaign(profile: str = "local", quick: bool = False, output_dir: Path = Path("results")) -> int:
    """Run the RQ1 traceability coverage campaign."""
    root = get_project_root()
    campaign_id = f"rq1-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    result_dir = output_dir / "rq1" / campaign_id
    raw_dir = result_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  RQ1 Campaign: {campaign_id}")
    print(f"  Profile: {profile}, Quick: {quick}")

    # 1. Build ground-truth graph
    gt = _build_ground_truth_graph(root, profile)
    gt_path = result_dir / "ground_truth_graph.json"
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(gt, f, indent=2)

    # 2. Run Syft
    syft_bom = _run_syft(root, result_dir)

    # 3. Run Trivy
    trivy_bom = _run_trivy(root, result_dir)

    # 4. Generate TraceAI AI/ML-BOM
    ml_bom = _generate_traceai_bom(root, profile, result_dir)

    # 5. Generate operational snapshot (OBOM-like)
    obom = _generate_obom(root, profile, result_dir)

    # 6. Build linked graph
    linked = _build_linked_graph(gt, syft_bom, trivy_bom, ml_bom, obom)
    linked_path = result_dir / "linked_graph.json"
    with open(linked_path, "w", encoding="utf-8") as f:
        json.dump(linked, f, indent=2)

    # 7. Compute metrics
    metrics = _compute_coverage_metrics(gt, syft_bom, trivy_bom, ml_bom, profile)

    # 8. Save results
    _save_results(metrics, gt, result_dir, campaign_id, profile, quick, root)

    # 9. Generate LaTeX
    _generate_latex(metrics, root / "generated", campaign_id, profile, quick)

    print(f"\n  Results: {result_dir}")
    print(f"  Nodes in ground truth: {gt['node_count']}")
    print(f"  Syft components: {metrics.get('syft_component_count', 'N/A')}")
    print(f"  Trivy components: {metrics.get('trivy_component_count', 'N/A')}")
    print(f"  TraceAI ML-BOM components: {metrics.get('traceai_component_count', 'N/A')}")
    print(f"  Node coverage (TraceAI/GT): {metrics.get('traceai_gt_coverage', 'N/A')}")
    print(f"  Syft/Trivy Jaccard: {metrics.get('syft_trivy_jaccard', 'N/A')}")

    return 0


def _build_ground_truth_graph(root: Path, profile: str) -> dict:
    """Build manually curated ground-truth graph for the local GPT-2 pipeline."""
    import platform
    import sys
    import torch
    import transformers

    has_gpu = torch.cuda.is_available()

    nodes = []
    edges = []

    def add_node(nid, ntype, name, version="", **kwargs):
        node = {"id": nid, "type": ntype, "name": name, "version": version}
        node.update(kwargs)
        nodes.append(node)
        return nid

    # Model identity
    add_node("model-gpt2", "model", "openai-community/gpt2", note="GPT-2 124M")
    add_node("model-revision", "revision", "main", note="HuggingFace model revision")
    add_node("model-weights", "artifact", "model.safetensors", note="Model weight file(s)")
    add_node("tokenizer-files", "artifact", "tokenizer.json",
             note="Includes vocab.json, merges.txt, tokenizer_config.json")
    add_node("model-config", "config", "config.json", note="Model architecture config")
    add_node("generation-config", "config", "generation_config.json",
             note="Default generation parameters")
    add_node("dataset-manifest", "dataset", "fixtures/datasets/manifest.json")

    # Runtime
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    add_node("python-runtime", "runtime", "python", version=py_ver)
    add_node("pytorch", "framework", "torch", version=torch.__version__)
    add_node("transformers", "framework", "transformers", version=transformers.__version__)
    add_node("traceai-app", "application", "traceai", version="0.1.0")

    # Python dependencies (direct)
    deps = ["fastapi", "uvicorn", "pydantic", "httpx", "cryptography",
            "psutil", "numpy", "scipy", "pandas", "matplotlib", "pyyaml",
            "jsonschema"]
    for dep in deps:
        try:
            mod = __import__(dep.replace("-", "_"))
            ver = getattr(mod, "__version__", "unknown")
        except ImportError:
            ver = "not_installed"
        add_node(f"dep-{dep}", "library", dep, version=ver)

    # Environment
    add_node("os-env", "environment", platform.system(), version=platform.version())
    add_node("inference-service", "service", "traceai-inference", version="0.1.0")
    add_node("runtime-policy", "policy", "config/policy.yaml")
    add_node("host-cpu", "hardware", "CPU",
             note=f"{os.cpu_count()} cores")
    import psutil
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
    add_node("host-ram", "hardware", "RAM", note=f"{ram_gb} GB")

    # GPU only if actually available
    if has_gpu:
        add_node("host-gpu", "hardware", "GPU", note=torch.cuda.get_device_name(0))
        add_node("cuda", "runtime", "CUDA", version=torch.version.cuda or "N/A")
    else:
        add_node("host-gpu", "hardware", "GPU",
                 status=NOT_APPLICABLE, note="No GPU on this host")
        add_node("cuda", "runtime", "CUDA",
                 status=NOT_APPLICABLE, note="No CUDA on this host")

    # Edges
    def add_edge(src, tgt, rel):
        edges.append({"source": src, "target": tgt, "relationship": rel})

    add_edge("inference-service", "traceai-app", "dependsOn")
    add_edge("traceai-app", "model-gpt2", "dependsOn")
    add_edge("model-gpt2", "tokenizer-files", "uses")
    add_edge("model-gpt2", "model-revision", "derivedFrom")
    add_edge("model-gpt2", "dataset-manifest", "evaluatedWith")
    add_edge("model-gpt2", "pytorch", "executedBy")
    add_edge("inference-service", "runtime-policy", "deployedWith")
    add_edge("pytorch", "python-runtime", "dependsOn")
    add_edge("transformers", "python-runtime", "dependsOn")
    add_edge("transformers", "pytorch", "dependsOn")
    for dep in deps:
        add_edge("traceai-app", f"dep-{dep}", "dependsOn")
    add_edge("python-runtime", "os-env", "runsOn")
    add_edge("inference-service", "host-cpu", "observes")
    add_edge("inference-service", "host-ram", "observes")
    if has_gpu:
        add_edge("pytorch", "cuda", "dependsOn")
        add_edge("inference-service", "host-gpu", "observes")
    add_edge("model-gpt2", "model-weights", "contains")
    add_edge("model-gpt2", "model-config", "describedBy")
    add_edge("model-gpt2", "generation-config", "describedBy")

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "profile": profile,
        "gpu_available": has_gpu,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _find_tool(name: str) -> Optional[str]:
    """Find tool in .tools/bin or PATH."""
    root = get_project_root()
    local = root / ".tools" / "bin" / f"{name}.exe"
    if local.exists():
        return str(local)
    return shutil.which(name)


def _run_syft(root: Path, result_dir: Path) -> Optional[dict]:
    """Run Syft to generate CycloneDX SBOM."""
    syft = _find_tool("syft")
    if not syft:
        logger.warning("Syft not found")
        return None

    out_path = result_dir / "syft.cdx.json"
    try:
        cmd = [syft, f"dir:{root}", "-o", f"cyclonedx-json={out_path}"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(root))
        if out_path.exists() and out_path.stat().st_size > 0:
            with open(out_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            logger.warning(f"Syft produced no output. stderr: {proc.stderr[:200]}")
    except Exception as e:
        logger.warning(f"Syft failed: {e}")
    return None


def _run_trivy(root: Path, result_dir: Path) -> Optional[dict]:
    """Run Trivy to generate CycloneDX SBOM."""
    trivy = _find_tool("trivy")
    if not trivy:
        logger.warning("Trivy not found")
        return None

    out_path = result_dir / "trivy.cdx.json"
    try:
        cmd = [trivy, "fs", str(root), "--format", "cyclonedx", "--output", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(root))
        if out_path.exists() and out_path.stat().st_size > 0:
            with open(out_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            logger.warning(f"Trivy produced no output. stderr: {proc.stderr[:200]}")
    except Exception as e:
        logger.warning(f"Trivy failed: {e}")
    return None


def _generate_traceai_bom(root: Path, profile: str, result_dir: Path) -> dict:
    """Generate TraceAI AI/ML-BOM."""
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


def _generate_obom(root: Path, profile: str, result_dir: Path) -> dict:
    """Generate operational snapshot (OBOM-like)."""
    import platform
    import psutil

    obom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": {
                "type": "platform",
                "name": "traceai-runtime-snapshot",
                "version": "0.1.0",
            },
        },
        "components": [
            {"type": "platform", "name": "os", "version": platform.version(),
             "bom-ref": "obom-os"},
            {"type": "platform", "name": "cpu", "version": str(os.cpu_count()),
             "bom-ref": "obom-cpu"},
            {"type": "platform", "name": "ram",
             "version": f"{round(psutil.virtual_memory().total/(1024**3),1)}GB",
             "bom-ref": "obom-ram"},
        ],
    }
    out_path = result_dir / "traceai_obom.cdx.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(obom, f, indent=2)
    return obom


def _build_linked_graph(gt, syft_bom, trivy_bom, ml_bom, obom) -> dict:
    """Build BOM-Link graph joining all artifacts."""
    links = []
    ml_serial = ml_bom.get("serialNumber", "")
    obom_serial = obom.get("serialNumber", "")

    if syft_bom:
        links.append({
            "source": ml_serial, "source_type": "ai-ml-bom",
            "target": syft_bom.get("serialNumber", "syft-sbom"),
            "target_type": "sbom-syft", "relationship": "dependsOn",
        })
    if trivy_bom:
        links.append({
            "source": ml_serial, "source_type": "ai-ml-bom",
            "target": trivy_bom.get("serialNumber", "trivy-sbom"),
            "target_type": "sbom-trivy", "relationship": "dependsOn",
        })
    links.append({
        "source": ml_serial, "source_type": "ai-ml-bom",
        "target": obom_serial, "target_type": "obom",
        "relationship": "describedBy",
    })
    return {"links": links, "link_count": len(links)}


def _extract_component_names(bom: Optional[dict]) -> set[str]:
    """Extract normalized component names from a CycloneDX BOM."""
    if not bom:
        return set()
    components = bom.get("components", [])
    return {c.get("name", "").lower() for c in components if c.get("name")}


def _compute_coverage_metrics(gt, syft_bom, trivy_bom, ml_bom, profile) -> dict:
    """Compute all RQ1 coverage metrics."""
    gt_nodes = {n["name"].lower() for n in gt["nodes"]
                if n.get("status") != NOT_APPLICABLE}
    gt_node_count = len(gt_nodes)

    syft_names = _extract_component_names(syft_bom)
    trivy_names = _extract_component_names(trivy_bom)
    ml_names = _extract_component_names(ml_bom)

    # Syft/Trivy Jaccard
    if syft_names and trivy_names:
        intersection = syft_names & trivy_names
        union = syft_names | trivy_names
        syft_trivy_jaccard = round(len(intersection) / len(union), 4) if union else 0
    else:
        syft_trivy_jaccard = "N/A"

    # TraceAI vs ground truth coverage
    gt_names_lower = gt_nodes
    ml_matched = gt_names_lower & ml_names
    traceai_gt_coverage = round(len(ml_matched) / len(gt_names_lower), 4) if gt_names_lower else 0

    # Edge completeness - check how many GT edges are representable
    total_edges = gt["edge_count"]

    # Schema validation
    schema_failures = 0
    from traceai.bom.validators import validate_cyclonedx_bom
    for bom_name, bom_data in [("ml_bom", ml_bom), ("syft", syft_bom), ("trivy", trivy_bom)]:
        if bom_data:
            result = validate_cyclonedx_bom(bom_data)
            if not result.valid:
                schema_failures += 1

    # Duplicate / orphan rates
    def _dup_rate(bom):
        if not bom:
            return "N/A"
        names = [c.get("name", "") for c in bom.get("components", [])]
        if not names:
            return 0
        return round(1 - len(set(names)) / len(names), 4)

    metrics = {
        "ground_truth_nodes": gt_node_count,
        "ground_truth_edges": total_edges,
        "syft_component_count": len(syft_names) if syft_bom else "N/A",
        "trivy_component_count": len(trivy_names) if trivy_bom else "N/A",
        "traceai_component_count": len(ml_names),
        "syft_trivy_jaccard": syft_trivy_jaccard,
        "syft_trivy_intersection": len(syft_names & trivy_names) if (syft_names and trivy_names) else "N/A",
        "traceai_gt_coverage": traceai_gt_coverage,
        "traceai_gt_matched": len(ml_matched),
        "schema_validation_failures": schema_failures,
        "duplicate_rate_syft": _dup_rate(syft_bom),
        "duplicate_rate_trivy": _dup_rate(trivy_bom),
        "duplicate_rate_traceai": _dup_rate(ml_bom),
        "gpu_nodes_applicable": gt.get("gpu_available", False),
    }
    return metrics


def _save_results(metrics, gt, result_dir, campaign_id, profile, quick, root):
    """Save RQ1 results."""
    # CSV
    import csv
    csv_path = result_dir / "rq1_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for k, v in metrics.items():
            writer.writerow([k, v])

    # Summary JSON
    summary = {
        "campaign_id": campaign_id,
        "profile": profile,
        "quick": quick,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "ground_truth_node_count": gt["node_count"],
        "ground_truth_edge_count": gt["edge_count"],
    }
    sum_path = result_dir / "rq1_summary.json"
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def _generate_latex(metrics, gen_dir, campaign_id, profile, quick):
    """Generate LaTeX table for RQ1."""
    gen_dir.mkdir(parents=True, exist_ok=True)
    from traceai.environment import escape_latex

    lines = [
        r"\begin{table}[htbp]",
        r"\caption{RQ1 Traceability Coverage (Quick Campaign -- Diagnostic)}",
        r"\label{tab:rq1-coverage}",
        r"\centering\small",
        r"\begin{tabular}{lr}",
        r"\toprule",
        r"\textbf{Metric} & \textbf{Value} \\",
        r"\midrule",
    ]
    display = [
        ("Ground-truth nodes", metrics["ground_truth_nodes"]),
        ("Ground-truth edges", metrics["ground_truth_edges"]),
        ("Syft components", metrics["syft_component_count"]),
        ("Trivy components", metrics["trivy_component_count"]),
        ("TraceAI ML-BOM components", metrics["traceai_component_count"]),
        ("Syft/Trivy Jaccard", metrics["syft_trivy_jaccard"]),
        ("TraceAI/GT node coverage", metrics["traceai_gt_coverage"]),
        ("Schema validation failures", metrics["schema_validation_failures"]),
    ]
    for label, val in display:
        lines.append(f"  {escape_latex(label)} & {escape_latex(str(val))} \\\\")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    (gen_dir / "results_rq1_table.tex").write_text("\n".join(lines), encoding="utf-8")

    # Summary tex
    summary_lines = [
        "% RQ1 Summary (quick/diagnostic)",
        f"% Campaign: {campaign_id}, Profile: {profile}",
        r"\paragraph{RQ1 Traceability Coverage}",
        f"The ground-truth graph contains {metrics['ground_truth_nodes']} nodes and "
        f"{metrics['ground_truth_edges']} edges. ",
    ]
    if metrics["syft_component_count"] != "N/A":
        summary_lines.append(
            f"Syft identified {metrics['syft_component_count']} components; "
            f"Trivy identified {metrics['trivy_component_count']} components "
            f"(Jaccard similarity: {metrics['syft_trivy_jaccard']}). "
        )
    summary_lines.append(
        f"The TraceAI AI/ML-BOM covers {metrics['traceai_gt_coverage']} of "
        f"ground-truth nodes ({metrics['traceai_gt_matched']} matched)."
    )
    (gen_dir / "results_rq1_summary.tex").write_text("\n".join(summary_lines), encoding="utf-8")
