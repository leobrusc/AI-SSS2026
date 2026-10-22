"""Ground-truth dependency graph for RQ1 evaluation."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from traceai.hashing import hash_file, hash_json, generate_bom_ref
from traceai.logging_config import get_logger
from traceai.settings import get_project_root

logger = get_logger("bom.ground_truth")


@dataclass
class GroundTruthComponent:
    """A component in the ground-truth dependency graph."""
    component_type: str  # model | tokenizer | dataset | library | runtime | container | config
    name: str
    version: str = ""
    bom_ref: str = ""
    hashes: dict[str, str] = field(default_factory=dict)
    purl: Optional[str] = None
    license: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.bom_ref:
            self.bom_ref = generate_bom_ref(self.component_type, self.name, self.version)


@dataclass
class GroundTruthEdge:
    """A relationship in the ground-truth dependency graph."""
    source_ref: str
    target_ref: str
    relationship: str  # depends_on | variant_of | generates | described_by


class GroundTruthGraph:
    """Complete ground-truth dependency graph for the LLM pipeline."""

    def __init__(self):
        self.components: list[GroundTruthComponent] = []
        self.edges: list[GroundTruthEdge] = []
        self._ref_index: dict[str, GroundTruthComponent] = {}

    def add_component(self, component: GroundTruthComponent) -> str:
        """Add a component and return its bom-ref."""
        self.components.append(component)
        self._ref_index[component.bom_ref] = component
        return component.bom_ref

    def add_edge(self, source_ref: str, target_ref: str, relationship: str) -> None:
        """Add a dependency edge between components."""
        self.edges.append(GroundTruthEdge(source_ref, target_ref, relationship))

    def node_count(self) -> int:
        """Total number of nodes."""
        return len(self.components)

    def edge_count(self) -> int:
        """Total number of edges."""
        return len(self.edges)

    def component_types(self) -> dict[str, int]:
        """Count components by type."""
        counts: dict[str, int] = {}
        for c in self.components:
            counts[c.component_type] = counts.get(c.component_type, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "node_count": self.node_count(),
            "edge_count": self.edge_count(),
            "component_types": self.component_types(),
            "components": [
                {
                    "bom_ref": c.bom_ref,
                    "type": c.component_type,
                    "name": c.name,
                    "version": c.version,
                    "hashes": c.hashes,
                    "purl": c.purl,
                    "license": c.license,
                }
                for c in self.components
            ],
            "edges": [
                {
                    "source": e.source_ref,
                    "target": e.target_ref,
                    "relationship": e.relationship,
                }
                for e in self.edges
            ],
        }

    def save(self, path: Path) -> None:
        """Save ground truth to JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Ground truth saved: {path} ({self.node_count()} nodes, {self.edge_count()} edges)")


def build_ground_truth(
    model_id: str,
    model_dir: Optional[str] = None,
    profile: str = "local",
) -> GroundTruthGraph:
    """Build the ground-truth dependency graph for the pipeline.

    This captures all known components that should appear in a complete
    AI/ML-BOM for the inference pipeline.
    """
    graph = GroundTruthGraph()
    root = get_project_root()

    # 1. Model component
    model_ref = graph.add_component(GroundTruthComponent(
        component_type="model",
        name=model_id,
        version="",  # Filled from model.lock.json
        metadata={"type": "causal-lm", "architecture": "GPT-2"},
    ))

    # 2. Tokenizer component
    tokenizer_ref = graph.add_component(GroundTruthComponent(
        component_type="tokenizer",
        name=f"{model_id}-tokenizer",
        metadata={"type": "BPE"},
    ))
    graph.add_edge(model_ref, tokenizer_ref, "depends_on")

    # 3. Model configuration
    config_ref = graph.add_component(GroundTruthComponent(
        component_type="config",
        name=f"{model_id}-config",
        metadata={"file": "config.json"},
    ))
    graph.add_edge(model_ref, config_ref, "described_by")

    # 4. Dataset manifest fixture
    dataset_ref = graph.add_component(GroundTruthComponent(
        component_type="dataset",
        name="prompt-fixtures",
        metadata={"manifest": "fixtures/datasets/manifest.json"},
    ))

    # 5. Python dependencies from requirements.lock
    lock_path = root / "requirements.lock"
    if lock_path.exists():
        dep_ref = graph.add_component(GroundTruthComponent(
            component_type="library",
            name="python-dependencies",
            metadata={"lock_file": "requirements.lock"},
            hashes={"sha256": hash_file(lock_path)},
        ))
        graph.add_edge(model_ref, dep_ref, "depends_on")

    # 6. Runtime environment
    import platform
    import sys
    runtime_ref = graph.add_component(GroundTruthComponent(
        component_type="runtime",
        name="python-runtime",
        version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        metadata={
            "os": platform.system(),
            "arch": platform.machine(),
        },
    ))
    graph.add_edge(model_ref, runtime_ref, "depends_on")

    # 7. Inference service
    service_ref = graph.add_component(GroundTruthComponent(
        component_type="service",
        name="traceai-inference",
        version="0.1.0",
    ))
    graph.add_edge(service_ref, model_ref, "depends_on")
    graph.add_edge(service_ref, tokenizer_ref, "depends_on")

    # 8. Policy and VEX
    policy_ref = graph.add_component(GroundTruthComponent(
        component_type="config",
        name="deployment-policy",
        metadata={"file": "config/policy.yaml"},
    ))
    graph.add_edge(service_ref, policy_ref, "described_by")

    logger.info(
        f"Ground truth built: {graph.node_count()} nodes, "
        f"{graph.edge_count()} edges, types: {graph.component_types()}"
    )
    return graph
