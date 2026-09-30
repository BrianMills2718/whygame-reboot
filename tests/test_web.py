"""Public web front door: default-deny surface, caps, refusals, and one end-to-end job with a fake model."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whygame_reboot import web
from whygame_reboot.contracts import ProposalResponse

OBS = ["Test count went from 400 to 2,000 in a year.", "All tests run in one serial job."]
Q = "Why did our pipeline get slower after adding more tests?"


def _config(tmp_path: Path) -> web.PublicConfig:
    return web.PublicConfig(
        model="openrouter/openai/gpt-5.6-luna", stage_budget_usd=0.06, run_budget_usd=0.12,
        max_sessions=3, max_concurrent_jobs=1, work_dir=tmp_path / "jobs", build_commit="testcommit",
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(web.create_app(_config(tmp_path)))


def test_refuses_to_build_without_public_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WHYGAME_PUBLIC", raising=False)
    with pytest.raises(SystemExit):
        web.PublicConfig.from_env()


def test_codex_route_is_never_public(tmp_path: Path) -> None:
    cfg = web.PublicConfig(**{**_config(tmp_path).__dict__, "model": "codex/gpt-5.6-luna"})
    with pytest.raises(SystemExit):
        cfg.route  # noqa: B018


def test_default_deny_and_no_docs(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json", "/etc/passwd", "/api", "/api/runs", "/run.json", "/../x"):
        assert client.get(path).status_code in (404, 405), path
    assert client.get("/").status_code == 200
    assert client.get("/api/examples").status_code == 200
    assert client.get("/api/samples/nope").status_code == 404


def test_samples_are_real_accepted_runs(client: TestClient) -> None:
    body = client.get("/api/samples/aes-mission-drift").json()
    assert body["run"]["status"] == "accepted" and len(body["run"]["receipts"]) == 2


def test_one_observation_is_refused_in_plain_words(client: TestClient) -> None:
    res = client.post("/api/runs", json={"question": Q, "observations": ["Only a single observation here."]})
    assert res.status_code == 422
    assert "observations" in res.json()["detail"] and "Traceback" not in res.text


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "short", "observations": OBS},
        {"question": Q, "observations": OBS + ["extra observation text"] * 6},
        {"question": Q, "observations": ["x", "y"]},
        {"question": Q, "observations": [1, 2]},
        {"question": 5, "observations": OBS},
        {"example": "../../etc/passwd"},
        {"example": {"a": 1}},
    ],
)
def test_bad_input_refused(client: TestClient, payload: dict[str, Any]) -> None:
    assert client.post("/api/runs", json=payload).status_code in (400, 422)


def test_body_caps(client: TestClient) -> None:
    assert client.post("/api/runs", content=b"x" * 9000, headers={"content-type": "application/json"}).status_code == 413
    assert client.post("/api/runs", content=b"[1]", headers={"content-type": "application/json"}).status_code == 400


def test_job_is_private_to_its_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "_execute", lambda job, packet, config: setattr(job, "status", "accepted"))
    a = TestClient(web.create_app(_config(tmp_path)))
    job_id = a.post("/api/runs", json={"question": Q, "observations": OBS}).json()["job_id"]
    assert a.get(f"/api/runs/{job_id}").status_code == 200
    app_b = TestClient(a.app)
    assert app_b.get(f"/api/runs/{job_id}").status_code == 404
    assert "set-cookie" not in a.get("/api/examples").headers


def test_one_running_job_per_visitor_and_global_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "_execute", lambda job, packet, config: time.sleep(30))
    a = TestClient(web.create_app(_config(tmp_path)))
    assert a.post("/api/runs", json={"question": Q, "observations": OBS}).status_code == 202
    second = a.post("/api/runs", json={"question": Q, "observations": OBS})
    assert second.status_code == 422 and "in progress" in second.json()["detail"]
    other = TestClient(a.app)
    third = other.post("/api/runs", json={"question": Q, "observations": OBS})
    assert third.status_code == 422 and "right now" in third.json()["detail"]


def _fake_call(model: str, messages: list[dict[str, Any]], response_model: type, **kwargs: Any):
    import json as _json
    from types import SimpleNamespace

    assert model == "openrouter/openai/gpt-5.6-luna" and "codex_home" not in kwargs
    assert kwargs["max_budget"] == 0.06
    if response_model is ProposalResponse:
        claim = lambda i, rel: {
            "local_id": f"c{i}", "subject": "more tests", "relation": rel, "object": "slower pipeline",
            "rationale": "Stated in the supplied observations, which it cites.", "observation_ids": ["obs-1"],
            "confidence": "provisional",
        }
        out = response_model.model_validate({
            "answer": "More tests make the pipeline slower, unless something offsets it; uncertain.",
            "claims": [claim(1, "causes"), claim(2, "prevents")],
            "competing_pair": {"left_local_id": "c1", "right_local_id": "c2", "disagreement": "Opposed direct causal claims."},
            "unresolved_questions": ["What offsets the added tests?"],
        })
    else:
        proposal = _json.loads(messages[1]["content"])["committed_proposal"]["claims"]
        ids = sorted(c["claim_id"] for c in proposal)
        out = response_model.model_validate({
            "revised_answer": "More tests probably contribute to slowness, limited by the one serial job.",
            "decisions": [
                {"target_claim_id": ids[0], "action": "retain", "rationale": "Kept: best supported by the evidence."},
                {"target_claim_id": ids[1], "action": "supersede", "rationale": "Too strong; qualified instead.",
                 "replacement": {"subject": "more tests", "relation": "contributes_to", "object": "slower pipeline",
                                 "rationale": "Serial execution makes added tests add to runtime.",
                                 "observation_ids": ["obs-2"], "confidence": "provisional"}},
            ],
            "unresolved_questions": ["Is the serial job the only factor?"],
        })
    return out, SimpleNamespace(usage={"prompt_tokens": 10, "completion_tokens": 5}, cost=0.001, model=model)


def test_end_to_end_job_with_fake_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web, "call_llm_structured", _fake_call)
    monkeypatch.setattr("whygame_reboot.runner.get_llm_call_receipts", lambda trace_id: [])
    monkeypatch.setattr(web, "observed_outer_receipt", lambda run_id: _outer(run_id))
    c = TestClient(web.create_app(_config(tmp_path)))
    job_id = c.post("/api/runs", json={"question": Q, "observations": OBS}).json()["job_id"]
    for _ in range(100):
        body = c.get(f"/api/runs/{job_id}").json()
        if body["status"] != "running":
            break
        time.sleep(0.2)
    assert body["status"] == "accepted", body
    run = body["run"]
    assert run["finding"]["left_claim_id"] and len(run["active_projection"]["active_claims"]) == 2
    assert run["observations"][0]["source_ref"] == "visitor-supplied"
    assert c.get(f"/api/runs/{job_id}/run.json").status_code == 200
    assert "<html" in c.get(f"/api/runs/{job_id}/report.html").text
    assert not list((tmp_path / "jobs").glob("*"))  # job directory removed


def _outer(run_id: str):
    from whygame_reboot.contracts import OuterRunReceipt

    return OuterRunReceipt(run_id=run_id, root_trace_id="whygame-reboot:web:" + run_id.removeprefix("whygame-reboot-attempt-"), status="completed", linked_call_count=2,
                           runtime_revision="testcommit", config_sha256=None, requested_model=None,
                           reasoning_effort=None, max_budget=None, error_type=None, error_phase=None)


def test_model_failure_is_one_plain_sentence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any):
        raise RuntimeError("secret provider detail sk-or-XYZ")

    monkeypatch.setattr(web, "call_llm_structured", boom)
    c = TestClient(web.create_app(_config(tmp_path)))
    job_id = c.post("/api/runs", json={"question": Q, "observations": OBS}).json()["job_id"]
    for _ in range(100):
        body = c.get(f"/api/runs/{job_id}").json()
        if body["status"] != "running":
            break
        time.sleep(0.2)
    assert body["status"] == "error"
    assert "sk-or" not in str(body) and "try again" in body["message"].lower()
