from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_authority_surfaces_are_routed() -> None:
    roadmap = (ROOT / "roadmap" / "README.md").read_text()
    assert "docs/topics/graph-adversary.md" in roadmap
    assert "policy/current-claims.json" in roadmap
    assert "evidence/README.md" in roadmap

    relationships = yaml.safe_load((ROOT / "scripts" / "relationships.yaml").read_text())
    governed = {entry["source"] for entry in relationships["governance"]}
    assert "docs/topics/graph-adversary.md" in governed
    assert "docs/plans/1_graph-adversary-vertical.md" in governed


def test_bootstrap_claims_do_not_overstate_adoption() -> None:
    current = json.loads((ROOT / "policy" / "current-claims.json").read_text())
    statuses = {claim["id"]: claim["status"] for claim in current["claims"]}
    assert statuses == {
        "canonical-private-custody": "observed",
        "graph-adversary-product": "unobserved",
        "aes-external-adoption": "unobserved",
        "legacy-replacement": "unobserved",
    }


def test_local_work_unit_is_claimable_and_bound_to_upstream() -> None:
    graph = json.loads(
        (ROOT / "docs" / "plans" / "1_graph-adversary-vertical_work_graph.json").read_text()
    )
    assert len(graph["units"]) == 1
    unit = graph["units"][0]
    assert unit["id"] == "WGR-WU01"
    assert unit["status"] == "ready"
    assert unit["readiness"]["status"] == "ready"
    assert unit["authorization_mode"] == "registry_claim"
    assert {
        (item["id"], item["revision"])
        for item in unit["inputs"]
    } >= {("P246-WU30", "P246-WU30@2")}


def test_cross_project_dependencies_are_revision_pinned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    dependencies = "\n".join(project["dependencies"])
    governance = "\n".join(project["optional-dependencies"]["governance"])
    assert "llm_client.git@a695335e74e5ace1b207939720679c22a06dbc03" in dependencies
    assert "agentic-engineering-system.git@ce866efd2855318570034a39343dace73f243352" in governance
