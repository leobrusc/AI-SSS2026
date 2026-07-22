"""BOM normalization for comparison between generators."""

import json
from pathlib import Path
from typing import Any

from traceai.logging_config import get_logger

logger = get_logger("bom.normalization")


def normalize_component(component: dict[str, Any]) -> dict[str, Any]:
    """Normalize a CycloneDX component for comparison.

    Strips volatile fields and standardizes format.
    """
    normalized = {
        "type": component.get("type", "unknown"),
        "name": component.get("name", "").lower().strip(),
        "version": component.get("version", "").strip(),
    }

    # Normalize purl
    purl = component.get("purl", "")
    if purl:
        normalized["purl"] = purl.lower()

    # Normalize hashes (keep only sha-256)
    hashes = component.get("hashes", [])
    for h in hashes:
        if h.get("alg", "").upper() in ("SHA-256", "SHA256"):
            normalized["sha256"] = h.get("content", "").lower()
            break

    return normalized


def normalize_bom(bom: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize all components in a BOM for comparison."""
    components = bom.get("components", [])
    return sorted(
        [normalize_component(c) for c in components],
        key=lambda x: (x["type"], x["name"], x["version"]),
    )


def compute_coverage_metrics(
    ground_truth_components: list[dict],
    generated_components: list[dict],
) -> dict[str, Any]:
    """Compute coverage metrics between ground truth and generated BOM.

    Returns:
        - node_coverage: fraction of ground-truth nodes found
        - edge_completeness: fraction of expected relationships captured
        - metadata_completeness: fraction of metadata fields populated
        - jaccard_similarity: Jaccard index of component sets
        - unmatched_components: list of ground-truth components not found
    """
    gt_names = {c["name"] for c in ground_truth_components}
    gen_names = {c["name"] for c in generated_components}

    intersection = gt_names & gen_names
    union = gt_names | gen_names

    node_coverage = len(intersection) / len(gt_names) if gt_names else 0.0
    jaccard = len(intersection) / len(union) if union else 0.0

    unmatched = gt_names - gen_names
    extra = gen_names - gt_names

    # Metadata completeness: check if version and hash are present
    metadata_fields = ["version", "sha256", "purl"]
    total_fields = 0
    populated_fields = 0
    for comp in generated_components:
        for field in metadata_fields:
            total_fields += 1
            if comp.get(field):
                populated_fields += 1

    metadata_completeness = populated_fields / total_fields if total_fields > 0 else 0.0

    return {
        "node_coverage": round(node_coverage, 4),
        "jaccard_similarity": round(jaccard, 4),
        "metadata_completeness": round(metadata_completeness, 4),
        "ground_truth_count": len(gt_names),
        "generated_count": len(gen_names),
        "matched_count": len(intersection),
        "unmatched_ground_truth": sorted(unmatched),
        "extra_generated": sorted(extra),
    }


def compare_scanners(
    scanner_a_bom: dict[str, Any],
    scanner_b_bom: dict[str, Any],
    scanner_a_name: str = "syft",
    scanner_b_name: str = "trivy",
) -> dict[str, Any]:
    """Compare component sets from two different scanners."""
    norm_a = normalize_bom(scanner_a_bom)
    norm_b = normalize_bom(scanner_b_bom)

    names_a = {c["name"] for c in norm_a}
    names_b = {c["name"] for c in norm_b}

    intersection = names_a & names_b
    union = names_a | names_b
    jaccard = len(intersection) / len(union) if union else 0.0

    return {
        f"{scanner_a_name}_count": len(names_a),
        f"{scanner_b_name}_count": len(names_b),
        "intersection_count": len(intersection),
        "union_count": len(union),
        "jaccard_similarity": round(jaccard, 4),
        f"unique_to_{scanner_a_name}": sorted(names_a - names_b),
        f"unique_to_{scanner_b_name}": sorted(names_b - names_a),
    }
