"""CycloneDX BOM schema validation."""

import json
from pathlib import Path
from typing import Any

import jsonschema

from traceai.logging_config import get_logger

logger = get_logger("bom.validators")

# CycloneDX 1.6 minimal schema for validation
# In production, download the full schema from cyclonedx.org
CYCLONEDX_REQUIRED_FIELDS = {
    "bomFormat": "CycloneDX",
    "specVersion": str,
    "components": list,
}


class BomValidationResult:
    """Result of BOM validation."""

    def __init__(self):
        self.valid = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.component_count = 0
        self.dependency_count = 0

    def add_error(self, msg: str) -> None:
        self.valid = False
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "component_count": self.component_count,
            "dependency_count": self.dependency_count,
        }


def validate_cyclonedx_bom(bom: dict[str, Any]) -> BomValidationResult:
    """Validate a CycloneDX BOM document.

    Performs structural validation including:
    - Required fields presence
    - Component structure
    - Dependency reference integrity
    - BOM-ref uniqueness
    """
    result = BomValidationResult()

    # Check format
    if bom.get("bomFormat") != "CycloneDX":
        result.add_error("Missing or invalid bomFormat (expected 'CycloneDX')")

    # Check spec version
    spec_version = bom.get("specVersion")
    if not spec_version:
        result.add_error("Missing specVersion")
    elif spec_version not in ("1.4", "1.5", "1.6"):
        result.add_warning(f"Unusual specVersion: {spec_version}")

    # Check components
    components = bom.get("components", [])
    if not isinstance(components, list):
        result.add_error("'components' must be a list")
        return result

    result.component_count = len(components)

    # Validate bom-ref uniqueness
    bom_refs = set()
    for i, comp in enumerate(components):
        if not isinstance(comp, dict):
            result.add_error(f"Component {i} is not a dict")
            continue

        if "type" not in comp:
            result.add_error(f"Component {i} missing 'type'")

        if "name" not in comp:
            result.add_error(f"Component {i} missing 'name'")

        bom_ref = comp.get("bom-ref")
        if bom_ref:
            if bom_ref in bom_refs:
                result.add_error(f"Duplicate bom-ref: {bom_ref}")
            bom_refs.add(bom_ref)

        # Validate hashes if present
        hashes = comp.get("hashes", [])
        for h in hashes:
            if "alg" not in h or "content" not in h:
                result.add_error(
                    f"Component '{comp.get('name', i)}' has invalid hash entry"
                )

    # Validate dependencies
    dependencies = bom.get("dependencies", [])
    result.dependency_count = len(dependencies)

    for dep in dependencies:
        ref = dep.get("ref")
        if ref and ref not in bom_refs and ref != "root-pipeline":
            result.add_warning(f"Dependency ref '{ref}' not found in components")

        depends_on = dep.get("dependsOn", [])
        for target in depends_on:
            if target not in bom_refs:
                result.add_warning(
                    f"Dependency target '{target}' not found in components"
                )

    return result


def validate_bom_file(path: Path) -> BomValidationResult:
    """Validate a CycloneDX BOM from a file path."""
    result = BomValidationResult()

    if not path.exists():
        result.add_error(f"File not found: {path}")
        return result

    try:
        with open(path, "r", encoding="utf-8") as f:
            bom = json.load(f)
    except json.JSONDecodeError as e:
        result.add_error(f"Invalid JSON: {e}")
        return result

    return validate_cyclonedx_bom(bom)
