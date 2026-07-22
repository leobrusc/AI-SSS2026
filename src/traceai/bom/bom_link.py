"""BOM-Link relationship builder for connecting multiple BOMs."""

import json
from pathlib import Path
from typing import Any

from traceai.hashing import hash_file, hash_json
from traceai.logging_config import get_logger

logger = get_logger("bom.bom_link")


class BomLinkBuilder:
    """Builds BOM-Link relationships between AI/ML-BOM, SBOM, HBOM, and OBOM."""

    def __init__(self):
        self.links: list[dict[str, Any]] = []

    def add_link(
        self,
        source_bom_serial: str,
        source_bom_type: str,
        target_bom_serial: str,
        target_bom_type: str,
        relationship: str = "depends_on",
    ) -> None:
        """Add a BOM-Link between two BOMs."""
        self.links.append({
            "source": {
                "serialNumber": source_bom_serial,
                "type": source_bom_type,
            },
            "target": {
                "serialNumber": target_bom_serial,
                "type": target_bom_type,
            },
            "relationship": relationship,
        })

    def link_sbom_to_ml_bom(
        self, sbom_path: Path, ml_bom_path: Path
    ) -> None:
        """Link an SBOM to the AI/ML-BOM."""
        sbom = self._load_bom(sbom_path)
        ml_bom = self._load_bom(ml_bom_path)

        if sbom and ml_bom:
            self.add_link(
                source_bom_serial=ml_bom.get("serialNumber", ""),
                source_bom_type="ai-ml-bom",
                target_bom_serial=sbom.get("serialNumber", ""),
                target_bom_type="sbom",
                relationship="depends_on",
            )

    def link_hbom_to_ml_bom(
        self, hbom_data: dict[str, Any], ml_bom_path: Path
    ) -> None:
        """Link hardware/environment evidence to the AI/ML-BOM."""
        ml_bom = self._load_bom(ml_bom_path)
        if ml_bom:
            self.add_link(
                source_bom_serial=ml_bom.get("serialNumber", ""),
                source_bom_type="ai-ml-bom",
                target_bom_serial=hbom_data.get("serialNumber", f"urn:uuid:hbom-{hash_json(hbom_data)[:8]}"),
                target_bom_type="hbom",
                relationship="described_by",
            )

    def link_obom_snapshot(
        self, obom_data: dict[str, Any], ml_bom_path: Path
    ) -> None:
        """Link runtime operational snapshot to the AI/ML-BOM."""
        ml_bom = self._load_bom(ml_bom_path)
        if ml_bom:
            self.add_link(
                source_bom_serial=ml_bom.get("serialNumber", ""),
                source_bom_type="ai-ml-bom",
                target_bom_serial=obom_data.get("serialNumber", f"urn:uuid:obom-{hash_json(obom_data)[:8]}"),
                target_bom_type="obom",
                relationship="described_by",
            )

    def _load_bom(self, path: Path) -> dict[str, Any] | None:
        """Load a BOM JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Cannot load BOM from {path}: {e}")
            return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize all links."""
        return {
            "bomLinks": self.links,
            "linkCount": len(self.links),
        }

    def save(self, path: Path) -> None:
        """Save BOM links to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"BOM links saved: {path} ({len(self.links)} links)")
