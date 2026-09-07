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
        "graph-adversary-product": "observed",
        "aes-external-adoption": "observed",
        "legacy-replacement": "unobserved",
        "second-question-observed": "observed",
    }


def test_local_work_unit_lifecycle_is_bound_to_upstream() -> None:
    graph = json.loads(
        (ROOT / "docs" / "plans" / "1_graph-adversary-vertical_work_graph.json").read_text()
    )
    assert len(graph["units"]) == 1
    unit = graph["units"][0]
    assert unit["id"] == "WGR-WU01"
    assert (unit["status"], unit["claimability"]) in {
        ("ready", "ready_for_execution"),
        ("in_progress", "unavailable_active_claim"),
        ("accepted", "not_applicable"),
    }
    assert unit["readiness"]["status"] == "ready"
    assert unit["authorization_mode"] == "registry_claim"
    assert {
        (item["id"], item["revision"])
        for item in unit["inputs"]
    } >= {("P246-WU30", "P246-WU30@2")}


def test_cross_project_dependencies_are_revision_pinned() -> None:
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = manifest["project"]
    dependencies = "\n".join(project["dependencies"])
    dev = "\n".join(manifest["dependency-groups"]["dev"])
    assert "llm_client.git@c171d542658402f7de4d99a2d3f3bf085b7b3c00" in dependencies
    assert (
        "agentic-engineering-system.git@"
        "11507833b71af1d5331d3085723555bf24537541" in dev
    )


def test_aes_is_installed_by_a_plain_sync_not_an_opt_in_extra() -> None:
    """AES must sit where `uv sync` with no flags will install it.

    It sat in an optional `governance` extra instead, from the day it was first
    pinned. Nothing named that extra, so on 2026-09-06 the live virtualenvs of
    all three repositories pinning AES held no `aes` package: the pin was real
    and the controls were absent. `dependency-groups.dev` is installed by
    default, so a developer checkout gets them without remembering a flag.
    """
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text())
    extras = manifest["project"].get("optional-dependencies", {})
    for name, requirements in extras.items():
        for requirement in requirements:
            assert "agentic-engineering-system" not in requirement, (
                f"AES is back in the optional `{name}` extra; a plain "
                "`uv sync` will not install it and the controls stop arriving"
            )
    assert any(
        "agentic-engineering-system" in requirement
        for requirement in manifest["dependency-groups"]["dev"]
    )
