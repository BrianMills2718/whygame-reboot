"""Public web front door for the graph-adversary loop.

This is the real loop (``run_loop``: model proposal, deterministic conflict finding in code, model
revision, append-only replay) behind a small HTTP surface that a stranger can use from a browser.

It exists only in **public-hosting mode**: ``WHYGAME_PUBLIC=1`` is required to build the app, and the
surface is default-deny. The only routes are the ones listed in ``create_app``; every other path is a
404 and there are no generated docs. Visitors never choose a filesystem path, a model, or a budget:

* every visitor gets a random session cookie; a job is visible only to the session that started it;
* one running job per visitor and a small global concurrency limit;
* request bodies are capped, and the question/observations have small length and count caps;
* each job runs in its own temporary directory with spend ceilings per model call and per run;
* failures reach the visitor as one plain sentence; raw exception text stays in the server log.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from llm_client import ObservedRun, call_llm_structured
from pydantic import ValidationError

from whygame_reboot.cli import _attach_outer_custody, publish_terminal_record
from whygame_reboot.contracts import LoopRun, QuestionPacket
from whygame_reboot.runner import (
    REASONING_EFFORT,
    RunRoute,
    config_sha256,
    hold_run_directory,
    observed_outer_receipt,
    run_loop,
)

log = logging.getLogger("whygame.web")

_EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "evidence" / "runs"
# Finished live runs retained in this repository, served read-only under fixed ids so a visitor can see a
# real result instantly. The recording date is part of the claim the page makes about them.
SAMPLES = {
    "aes-mission-drift": ("2026-08-23-account-bound-live", "2026-08-23"),
    "recurring-lessons": ("2026-09-05-recurring-lessons-live", "2026-09-05"),
}
_PAGE = Path(__file__).resolve().parent / "web_static" / "index.html"

COOKIE = "why_sid"
MAX_BODY_BYTES = 8_000
QUESTION_CHARS = (20, 400)
OBSERVATION_CHARS = (10, 400)
OBSERVATION_COUNT = (2, 6)
IDLE_TTL_S = 2 * 60 * 60

STAGE_FOR_TASK = {"whygame_reboot.proposal": "proposing", "whygame_reboot.revision": "revising"}


class RefusedInput(ValueError):
    """The visitor's input was refused; the message is one plain sentence."""


@dataclass(frozen=True)
class PublicConfig:
    model: str
    stage_budget_usd: float
    run_budget_usd: float
    max_sessions: int
    max_concurrent_jobs: int
    work_dir: Path
    build_commit: str

    @classmethod
    def from_env(cls) -> PublicConfig:
        if os.environ.get("WHYGAME_PUBLIC") != "1":
            raise SystemExit("refusing to start: WHYGAME_PUBLIC=1 is required for public hosting")
        return cls(
            model=os.environ.get("WHYGAME_MODEL", "openrouter/openai/gpt-5.6-luna"),
            stage_budget_usd=float(os.environ.get("WHYGAME_STAGE_BUDGET_USD", "0.06")),
            run_budget_usd=float(os.environ.get("WHYGAME_RUN_BUDGET_USD", "0.12")),
            max_sessions=int(os.environ.get("WHYGAME_MAX_SESSIONS", "40")),
            max_concurrent_jobs=int(os.environ.get("WHYGAME_MAX_CONCURRENT_JOBS", "3")),
            work_dir=Path(os.environ.get("WHYGAME_WORK_DIR", tempfile.gettempdir())) / "whygame-jobs",
            build_commit=os.environ.get("WHYGAME_BUILD_COMMIT", "unknown"),
        )

    @property
    def route(self) -> RunRoute:
        if self.model.startswith("codex/"):
            raise SystemExit("public hosting never uses a Codex account route")
        return RunRoute(self.model, self.stage_budget_usd, self.run_budget_usd)


@dataclass
class Job:
    job_id: str
    session: str
    title: str
    stage: str = "queued"
    status: str = "running"  # running | accepted | blocked | error
    started: float = field(default_factory=time.time)
    finished: float | None = None
    run: dict[str, Any] | None = None
    report_html: str | None = None
    message: str | None = None  # one plain sentence for blocked/error

    def public(self) -> dict[str, Any]:
        end = self.finished or time.time()
        return {
            "job_id": self.job_id,
            "title": self.title,
            "stage": self.stage,
            "status": self.status,
            "elapsed_s": round(end - self.started, 1),
            "message": self.message,
            "run": self.run,
        }


# ---------------------------------------------------------------------------------------------
# Question packets: the two committed examples, or visitor-written text.
# ---------------------------------------------------------------------------------------------


def load_samples() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sample_id, (directory, recorded_on) in SAMPLES.items():
        run = LoopRun.model_validate_json((_EVIDENCE_DIR / directory / "run.json").read_text(encoding="utf-8"))
        if run.status != "accepted":
            raise ValueError(f"sample {sample_id} is not an accepted run")
        out[sample_id] = {"recorded_on": recorded_on, "run": run.model_dump(mode="json")}
    return out


def load_examples() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(_EXAMPLES_DIR.glob("*/question.yaml")):
        packet = QuestionPacket.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
        out[packet.id] = packet.model_dump(mode="json")
    return out


_FIELD_SENTENCES = {
    "question": f"Write the question in {QUESTION_CHARS[0]} to {QUESTION_CHARS[1]} characters.",
    "observations": f"Give {OBSERVATION_COUNT[0]} to {OBSERVATION_COUNT[1]} observations: short facts the answer must be checked against.",
}


def packet_from_visitor(question: Any, observations: Any) -> QuestionPacket:
    """Build a packet from visitor text, or raise ``RefusedInput`` with one plain sentence.

    Length and count caps are this front door's (they bound spend); the structural rules
    (at least two observations, non-empty text) are the real ``QuestionPacket`` contract's.
    """

    if not isinstance(question, str) or not isinstance(observations, list):
        raise RefusedInput("Send a question and a list of observations.")
    if any(not isinstance(item, str) for item in observations):
        raise RefusedInput("Each observation must be plain text.")
    question = question.strip()
    observations = [item.strip() for item in observations if item.strip()]
    if not QUESTION_CHARS[0] <= len(question) <= QUESTION_CHARS[1]:
        raise RefusedInput(_FIELD_SENTENCES["question"])
    if len(observations) > OBSERVATION_COUNT[1]:
        raise RefusedInput(_FIELD_SENTENCES["observations"])
    for text in observations:
        if not OBSERVATION_CHARS[0] <= len(text) <= OBSERVATION_CHARS[1]:
            raise RefusedInput(
                f"Each observation must be {OBSERVATION_CHARS[0]} to {OBSERVATION_CHARS[1]} characters."
            )
    try:
        return QuestionPacket.model_validate(
            {
                "id": f"visitor-{uuid.uuid4().hex[:12]}",
                "question": question,
                "observations": [
                    {
                        "id": f"obs-{index}",
                        "text": text,
                        "source_ref": "visitor-supplied",
                        "source_revision": "visitor-input",
                    }
                    for index, text in enumerate(observations, start=1)
                ],
            }
        )
    except ValidationError as exc:
        fields = {str(error["loc"][0]) for error in exc.errors() if error["loc"]}
        for name in ("observations", "question"):
            if name in fields:
                raise RefusedInput(_FIELD_SENTENCES[name]) from None
        raise RefusedInput("That input is not something the loop can check.") from None


# ---------------------------------------------------------------------------------------------
# Running a job.
# ---------------------------------------------------------------------------------------------


def _execute(job: Job, packet: QuestionPacket, config: PublicConfig) -> None:
    """Run the real loop for one visitor job; never raises (the job records the outcome)."""

    job_dir = config.work_dir / job.job_id
    try:
        job_dir.mkdir(parents=True)
        route = config.route
        attempt = uuid.uuid4().hex
        product_run_id = f"whygame-reboot/{uuid.uuid4().hex}"
        os.environ["LLM_CLIENT_REQUIRE_OBSERVED_RUN"] = "1"
        observed = ObservedRun(
            project="whygame-reboot",
            operation="graph_adversary_loop",
            executable="whygame-reboot-web",
            run_id=f"whygame-reboot-attempt-{attempt}",
            root_trace_id=f"whygame-reboot:web:{attempt}",
            runtime_revision=config.build_commit,
            config_sha256=f"sha256:{config_sha256(route)}",
            requested_model=route.model,
            reasoning_effort=REASONING_EFFORT,
            max_budget=route.run_budget_usd,
        )

        def caller(*args: Any, **kwargs: Any) -> Any:
            job.stage = STAGE_FOR_TASK.get(kwargs.get("task", ""), job.stage)
            result = call_llm_structured(*args, **kwargs)
            job.stage = "checking" if job.stage == "proposing" else "finishing"
            return result

        output_dir = job_dir / "run"
        run: LoopRun | None = None
        with hold_run_directory(output_dir) as lock:
            try:
                with observed:
                    observed.set_phase("proposal_and_revision")
                    run = run_loop(
                        packet,
                        output_dir=output_dir,
                        producer_revision=config.build_commit,
                        observed_run=observed,
                        caller=caller,
                        run_id=product_run_id,
                        resume=False,
                        route=route,
                        run_lock=lock,
                    )
                    if run.status != "accepted":
                        raise RuntimeError(f"run ended with status {run.status}")
            except RuntimeError:
                if run is None:
                    raise
            assert run is not None
            run = _attach_outer_custody(run, observed_outer_receipt(observed.run_id)) if (
                run.status == "accepted"
            ) else run
            run = publish_terminal_record(output_dir, run)
        job.run = run.model_dump(mode="json")
        job.report_html = (output_dir / "report.html").read_text(encoding="utf-8")
        if run.status == "accepted":
            job.status = "accepted"
        elif run.status == "blocked":
            job.status = "blocked"
            job.message = (
                "The model's proposal did not contain a direct cause-versus-prevent conflict, "
                "so there was nothing for the code to stress-test. Nothing was revised."
            )
        else:
            raise RuntimeError("; ".join(run.issues) or "run failed")
    except Exception as exc:
        log.exception("job %s failed", job.job_id)
        job.status = "error"
        job.message = (
            "The model run did not finish, so there is no result to show. "
            f"({type(exc).__name__}). Please try again in a minute."
        )
        if job.run is not None:
            job.run = {**job.run, "issues": []}
    finally:
        job.finished = time.time()
        job.stage = "done"
        shutil.rmtree(job_dir, ignore_errors=True)


class Store:
    def __init__(self, config: PublicConfig) -> None:
        self.config = config
        self.lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        self.sessions: dict[str, float] = {}

    def _purge(self) -> None:
        now = time.time()
        for sid, seen in list(self.sessions.items()):
            if now - seen > IDLE_TTL_S and not self._running(sid):
                del self.sessions[sid]
        live = set(self.sessions)
        self.jobs = {k: v for k, v in self.jobs.items() if v.session in live}

    def _running(self, sid: str) -> bool:
        return any(j.session == sid and j.status == "running" for j in self.jobs.values())

    def touch(self, sid: str | None) -> tuple[str, bool]:
        """Return (session id, created). Unknown or missing ids get a fresh session."""
        with self.lock:
            self._purge()
            if sid and sid in self.sessions:
                self.sessions[sid] = time.time()
                return sid, False
            if len(self.sessions) >= self.config.max_sessions:
                oldest = min(self.sessions, key=self.sessions.__getitem__)
                if not self._running(oldest):
                    del self.sessions[oldest]
                    self.jobs = {k: v for k, v in self.jobs.items() if v.session != oldest}
                else:
                    raise RefusedInput("The demo is full right now. Please try again in a few minutes.")
            sid = secrets.token_urlsafe(24)
            self.sessions[sid] = time.time()
            return sid, True

    def start(self, sid: str, title: str, packet: QuestionPacket) -> Job:
        with self.lock:
            if self._running(sid):
                raise RefusedInput("You already have a run in progress. Wait for it to finish.")
            if sum(j.status == "running" for j in self.jobs.values()) >= self.config.max_concurrent_jobs:
                raise RefusedInput("Several people are using the demo right now. Try again in a minute.")
            job = Job(job_id=secrets.token_urlsafe(18), session=sid, title=title)
            self.jobs[job.job_id] = job
        threading.Thread(target=_execute, args=(job, packet, self.config), daemon=True).start()
        return job

    def get(self, sid: str | None, job_id: str) -> Job | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return job if job and sid and job.session == sid else None


# ---------------------------------------------------------------------------------------------
# The app.
# ---------------------------------------------------------------------------------------------


def create_app(config: PublicConfig | None = None) -> FastAPI:
    config = config or PublicConfig.from_env()
    store = Store(config)
    examples = load_examples()
    samples = load_samples()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def refuse(message: str, status: int = 400) -> JSONResponse:
        return JSONResponse({"detail": message}, status_code=status)

    def with_cookie(request: Request, response: Response, sid: str, created: bool) -> Response:
        if created:
            response.set_cookie(
                COOKIE,
                sid,
                max_age=IDLE_TTL_S,
                httponly=True,
                samesite="lax",
                secure=request.headers.get("x-forwarded-proto", request.url.scheme) == "https",
            )
        return response

    @app.get("/", response_class=HTMLResponse)
    def page() -> HTMLResponse:
        return HTMLResponse(
            _PAGE.read_text(encoding="utf-8"),
            headers={
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                    "connect-src 'self'; img-src data:; base-uri 'none'; form-action 'none'"
                ),
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            },
        )

    @app.get("/api/examples")
    def list_examples() -> dict[str, Any]:
        return {"examples": list(examples.values()), "model": config.model}

    @app.get("/api/samples/{sample_id}")
    def sample(sample_id: str) -> Response:
        found = samples.get(sample_id)
        if found is None:
            return refuse("No such recorded run.", 404)
        return JSONResponse(found)

    @app.post("/api/runs")
    async def start_run(request: Request) -> Response:
        declared = request.headers.get("content-length")
        if declared is None or not declared.isdigit() or int(declared) > MAX_BODY_BYTES:
            return refuse("That request is too large.", 413)
        raw = b""
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > MAX_BODY_BYTES:
                return refuse("That request is too large.", 413)
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise TypeError
        except (ValueError, TypeError):
            return refuse("Send a JSON object with a question and observations.")
        try:
            sid, created = store.touch(request.cookies.get(COOKIE))
            if "example" in body:
                example = examples.get(body["example"]) if isinstance(body["example"], str) else None
                if example is None:
                    return refuse("Unknown example.")
                packet = QuestionPacket.model_validate(example)
                title = example["question"]
            else:
                packet = packet_from_visitor(body.get("question"), body.get("observations"))
                title = packet.question
            job = store.start(sid, title, packet)
        except RefusedInput as exc:
            return refuse(str(exc), 422)
        return with_cookie(request, JSONResponse({"job_id": job.job_id}, status_code=202), sid, created)

    @app.get("/api/runs/{job_id}")
    def run_status(job_id: str, request: Request) -> Response:
        job = store.get(request.cookies.get(COOKIE), job_id)
        if job is None:
            return refuse("No such run.", 404)
        return JSONResponse(job.public())

    @app.get("/api/runs/{job_id}/run.json")
    def run_json(job_id: str, request: Request) -> Response:
        job = store.get(request.cookies.get(COOKIE), job_id)
        if job is None or job.run is None:
            return refuse("No such run.", 404)
        return Response(
            json.dumps(job.run, indent=2, sort_keys=True) + "\n",
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="run.json"'},
        )

    @app.get("/api/runs/{job_id}/report.html")
    def run_report(job_id: str, request: Request) -> Response:
        job = store.get(request.cookies.get(COOKIE), job_id)
        if job is None or job.report_html is None:
            return refuse("No such run.", 404)
        return HTMLResponse(
            job.report_html,
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
        )

    return app


def get_app() -> FastAPI:
    return create_app()
