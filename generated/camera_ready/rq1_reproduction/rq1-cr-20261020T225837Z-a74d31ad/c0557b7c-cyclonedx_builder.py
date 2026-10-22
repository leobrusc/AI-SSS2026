"""CycloneDX AI/ML-BOM builder."""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from traceai.bom.ground_truth import GroundTruthGraph, build_ground_truth
from traceai.hashing import hash_json
from traceai.logging_config import get_logger
from traceai.settings import get_project_root, get_settings

logger = get_logger("bom.cyclonedx_builder")

CYCLONEDX_SPEC_VERSION = "1.6"
CYCLONEDX_SCHEMA_URL = "https://cyclonedx.org/schema/bom-1.6.schema.json"


def build_cyclonedx_bom(
    ground_truth: GroundTruthGraph,
    profile: str = "local",
    include_ml_extension: bool = True,
) -> dict[str, Any]:
    """Build a CycloneDX BOM from the ground-truth graph.

    Generates a CycloneDX 1.6 BOM with AI/ML-BOM extensions.
    """
    serial_number = f"urn:uuid:{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    bom: dict[str, Any] = {
        "$schema": CYCLONEDX_SCHEMA_URL,
        "bomFormat": "CycloneDX",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "serialNumber": serial_number,
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": "traceai",
                        "version": "0.1.0",
                        "bom-ref": "tool-traceai",
                    }
                ]
            },
            "component": {
                "type": "machine-learning-model",
                "name": "traceai-inference-pipeline",
                "version": "0.1.0",
                "bom-ref": "root-pipeline",
            },
            "properties": [
                {"name": "traceai:profile", "value": profile},
                {"name": "traceai:spec-version", "value": CYCLONEDX_SPEC_VERSION},
            ],
        },
        "components": [],
        "dependencies": [],
    }

    # Build components from ground truth
    for gt_component in ground_truth.components:
        cdx_component = _build_cdx_component(gt_component, include_ml_extension)
        bom["components"].append(cdx_component)

    # Build dependencies from edges
    dep_map: dict[str, list[str]] = {}
    for edge in ground_truth.edges:
        if edge.relationship == "depends_on":
            dep_map.setdefault(edge.source_ref, []).append(edge.target_ref)

    for ref, deps in dep_map.items():
        bom["dependencies"].append({"ref": ref, "dependsOn": deps})

    # Add root dependency
    root_deps = [c.bom_ref for c in ground_truth.components if c.component_type == "service"]
    if root_deps:
        bom["dependencies"].append({"ref": "root-pipeline", "dependsOn": root_deps})

    return bom


def _build_cdx_component(gt_component, include_ml: bool) -> dict[str, Any]:
    """Convert a ground-truth component to CycloneDX format."""
    type_mapping = {
        "model": "machine-learning-model",
        "tokenizer": "data",
        "dataset": "data",
        "library": "library",
        "runtime": "platform",
        "service": "application",
        "config": "file",
        "container": "container",
    }

    cdx_type = type_mapping.get(gt_component.component_type, "library")

    component: dict[str, Any] = {
        "type": cdx_type,
        "name": gt_component.name,
        "bom-ref": gt_component.bom_ref,
    }

    if gt_component.version:
        component["version"] = gt_component.version

    if gt_component.purl:
        component["purl"] = gt_component.purl

    if gt_component.hashes:
        component["hashes"] = [
            {"alg": alg.upper().replace("SHA256", "SHA-256"), "content": digest}
            for alg, digest in gt_component.hashes.items()
        ]

    if gt_component.license:
        component["licenses"] = [{"license": {"id": gt_component.license}}]

    if gt_component.metadata and include_ml:
        component["properties"] = [
            {"name": f"traceai:{k}", "value": str(v)}
            for k, v in gt_component.metadata.items()
        ]

    return component


def generate_bom(profile: str = "local", output_dir: Optional[Path] = None) -> int:
    """Generate CycloneDX BOM and save to output directory."""
    settings = get_settings()
    root = get_project_root()
    output_dir = output_dir or (root / "generated")
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    # Build ground truth
    ground_truth = build_ground_truth(
        model_id=settings.model_id,
        model_dir=settings.model_dir,
        profile=profile,
    )

    # Save ground truth
    gt_path = output_dir / "ground_truth.json"
    ground_truth.save(gt_path)

    # Generate CycloneDX BOM
    bom = build_cyclonedx_bom(ground_truth, profile)

    bom_path = output_dir / "ai_ml_bom.cdx.json"
    with open(bom_path, "w", encoding="utf-8") as f:
        json.dump(bom, f, indent=2)

    generation_time_ms = (time.time() - start_time) * 1000
    bom_size_bytes = bom_path.stat().st_size

    logger.info(
        f"BOM generated: {bom_path} "
        f"({len(bom['components'])} components, "
        f"{generation_time_ms:.1f}ms, {bom_size_bytes} bytes)"
    )

    # Save generation metadata
    meta = {
        "bom_path": str(bom_path),
        "ground_truth_path": str(gt_path),
        "generation_time_ms": generation_time_ms,
        "bom_size_bytes": bom_size_bytes,
        "component_count": len(bom["components"]),
        "dependency_count": len(bom["dependencies"]),
        "spec_version": CYCLONEDX_SPEC_VERSION,
        "profile": profile,
        "bom_hash": hash_json(bom),
    }
    meta_path = output_dir / "bom_generation_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return 0
