"""Deterministic static outcome report for one loop run."""

from __future__ import annotations

from html import escape

from whygame_reboot.contracts import CommittedClaim, LoopRun


def _claim_card(claim: CommittedClaim, *, state: str) -> str:
    relation = claim.relation.replace("_", " ")
    return f"""
      <article class="claim {escape(state)}">
        <div class="claim-meta"><span>{escape(state)}</span><code>{escape(claim.claim_id)}</code></div>
        <p class="edge"><strong>{escape(claim.subject)}</strong>
          <span class="relation">{escape(relation)}</span>
          <strong>{escape(claim.object)}</strong></p>
        <p>{escape(claim.rationale)}</p>
        <p class="evidence">Confidence: {escape(claim.confidence)} · observations:
          {escape(", ".join(claim.observation_ids))}</p>
      </article>"""


def _stage(label: str, complete: bool, note: str) -> str:
    state = "complete" if complete else "pending"
    return (
        f'<li class="stage {state}"><span class="dot"></span><div><strong>{escape(label)}</strong>'
        f"<p>{escape(note)}</p></div></li>"
    )


def render_report(run: LoopRun) -> str:
    """Render the decision surface; domain rules remain outside this projection."""

    accepted = run.status == "accepted"
    revised_answer = run.revision_plan.revised_answer if run.revision_plan else None
    lead = revised_answer or (run.proposal.answer if run.proposal else run.question)
    issue_text = "".join(f"<li>{escape(item)}</li>" for item in run.issues)
    observations = "".join(
        f"""<li><strong>{escape(item.id)}</strong> — {escape(item.text)}
        <small>{escape(item.source_ref)} @ {escape(item.source_revision)}</small></li>"""
        for item in run.observations
    )
    proposal_cards = ""
    if run.proposal:
        superseded = set(
            run.active_projection.superseded_claim_ids if run.active_projection else ()
        )
        proposal_cards = "".join(
            _claim_card(item, state="superseded" if item.claim_id in superseded else "retained")
            for item in run.proposal.claims
        )
    active_cards = ""
    if run.active_projection:
        original_ids = {item.claim_id for item in run.proposal.claims} if run.proposal else set()
        active_cards = "".join(
            _claim_card(item, state="retained" if item.claim_id in original_ids else "replacement")
            for item in run.active_projection.active_claims
        )
    finding = "<p class=empty>No deterministic finding was committed.</p>"
    if run.finding:
        finding = f"""<div class="finding">
          <span class="eyebrow">Direct causal conflict</span>
          <p>{escape(run.finding.explanation)}</p>
          <code>{escape(run.finding.left_claim_id)}</code>
          <span class="versus">versus</span>
          <code>{escape(run.finding.right_claim_id)}</code>
        </div>"""
    decisions = ""
    if run.revision_plan:
        decisions = "".join(
            f"""<li><strong>{escape(item.action.title())}</strong>
            <code>{escape(item.target_claim_id)}</code><p>{escape(item.rationale)}</p></li>"""
            for item in run.revision_plan.decisions
        )
    unresolved = ()
    if run.revision_plan:
        unresolved = run.revision_plan.unresolved_questions
    elif run.proposal:
        unresolved = run.proposal.unresolved_questions
    unresolved_html = "".join(f"<li>{escape(item)}</li>" for item in unresolved)
    receipts = "".join(
        f"""<tr><td>{escape(item.trace_id.rsplit('/', 1)[-1])}</td>
        <td><code>{escape(item.resolved_model)}</code></td><td>{item.total_tokens:,}</td>
        <td>{item.latency_s:.2f}s</td><td>${item.cost_usd:.4f}</td>
        <td>{item.retry_count}</td><td>{'yes' if item.fallback_used else 'no'}</td></tr>"""
        for item in run.receipts
    )
    timeline = "".join(
        [
            _stage("Plan", True, "Question and observations are revision-bound."),
            _stage("Execute", run.proposal is not None, "Luna proposed typed causal claims."),
            _stage("Observe", run.finding is not None, "The system selected an exact conflict."),
            _stage("Evaluate", run.revision_plan is not None, "Feedback became a digest-bound plan."),
            _stage("Replan + apply", run.active_projection is not None, "Append-only replay changed active state."),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WhyGame · Graph-adversary result</title>
  <style>
    :root {{ color-scheme: light; --ink:#17211b; --muted:#607067; --paper:#f4f1e8;
      --panel:#fffdf7; --line:#d7d2c4; --green:#246b4b; --red:#a43f35;
      --amber:#a46618; --blue:#315f78; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font:16px/1.55
      ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(1100px,calc(100% - 32px)); margin:32px auto 72px; }}
    header,.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; }}
    header {{ padding:clamp(24px,5vw,56px); box-shadow:0 18px 50px #372e1b12; }}
    .eyebrow {{ color:var(--green); font-size:.75rem; font-weight:800; letter-spacing:.12em;
      text-transform:uppercase; }}
    h1 {{ margin:.35rem 0 .75rem; font:700 clamp(2rem,5vw,4.4rem)/1.02 Georgia,serif;
      max-width:16ch; }}
    h2 {{ margin:0 0 1rem; font:700 1.55rem/1.2 Georgia,serif; }}
    h3 {{ font-size:.86rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}
    .answer {{ max-width:78ch; font-size:1.15rem; }}
    .status {{ display:inline-flex; margin-top:1rem; padding:.35rem .7rem; border-radius:99px;
      color:white; background:{'var(--green)' if accepted else 'var(--red)'}; font-weight:750; }}
    .grid {{ display:grid; grid-template-columns:minmax(0,1.5fr) minmax(260px,.7fr); gap:18px;
      margin-top:18px; }}
    .panel {{ padding:24px; min-width:0; }}
    .timeline {{ list-style:none; padding:0; margin:0; }}
    .stage {{ display:grid; grid-template-columns:18px 1fr; gap:10px; padding:0 0 15px; }}
    .stage p {{ margin:.15rem 0 0; color:var(--muted); font-size:.9rem; }}
    .dot {{ width:11px; height:11px; margin-top:6px; border-radius:50%; background:var(--line); }}
    .complete .dot {{ background:var(--green); box-shadow:0 0 0 4px #246b4b18; }}
    .claims {{ display:grid; gap:12px; }}
    .claim {{ border:1px solid var(--line); border-left:5px solid var(--blue); padding:16px;
      border-radius:12px; background:white; }}
    .claim.superseded {{ border-left-color:var(--red); opacity:.72; }}
    .claim.replacement {{ border-left-color:var(--green); }}
    .claim-meta {{ display:flex; justify-content:space-between; gap:12px; color:var(--muted);
      font-size:.76rem; text-transform:uppercase; letter-spacing:.07em; }}
    .edge {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; font-size:1.04rem; }}
    .relation {{ color:var(--blue); background:#315f7812; padding:.2rem .5rem; border-radius:6px; }}
    .evidence,small {{ display:block; color:var(--muted); font-size:.82rem; }}
    .finding {{ border:1px solid #a43f3544; background:#fff4f1; border-radius:12px; padding:18px; }}
    .versus {{ padding:0 .55rem; color:var(--red); font-weight:700; }}
    code {{ overflow-wrap:anywhere; font-size:.82em; }}
    .observations li,.decisions li,.issues li,.uncertainty li {{ margin:.65rem 0; }}
    .decisions p {{ margin:.2rem 0 .8rem; }}
    .table-wrap {{ overflow-x:auto; }}
    table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
    th,td {{ border-bottom:1px solid var(--line); padding:9px 7px; text-align:left; }}
    .nonclaim {{ color:var(--muted); border-left:3px solid var(--amber); padding-left:14px; }}
    @media (max-width:760px) {{ main {{ width:min(100% - 20px,1100px); margin-top:10px; }}
      .grid {{ grid-template-columns:1fr; }} header,.panel {{ border-radius:12px; }}
      .claim-meta {{ display:block; }} }}
  </style>
</head>
<body><main>
  <header>
    <span class="eyebrow">WhyGame · graph as adversary</span>
    <h1>{escape(run.question)}</h1>
    <p class="answer">{escape(lead)}</p>
    <span class="status">{escape(run.status)}</span>
  </header>
  <div class="grid">
    <section class="panel"><h2>What the loop did</h2><ol class="timeline">{timeline}</ol></section>
    <aside class="panel"><h2>Run identity</h2><p><code>{escape(run.run_id)}</code></p>
      <p class="evidence">Source {escape(run.producer_revision)}<br>Input {escape(run.input_sha256[:16])}…
      <br>Config {escape(run.config_sha256[:16])}…</p></aside>
    <section class="panel"><h2>1. Committed proposal</h2><div class="claims">{proposal_cards}</div></section>
    <section class="panel"><h2>2. Selected challenge</h2>{finding}</section>
    <section class="panel"><h2>3. Applied revision</h2><ol class="decisions">{decisions}</ol></section>
    <section class="panel"><h2>4. Active explanation</h2><div class="claims">{active_cards}</div></section>
    <section class="panel"><h2>Source observations</h2><ol class="observations">{observations}</ol></section>
    <section class="panel"><h2>Unresolved uncertainty</h2><ul class="uncertainty">{unresolved_html}</ul></section>
    <section class="panel"><h2>Execution receipts</h2><div class="table-wrap"><table>
      <thead><tr><th>Stage</th><th>Model</th><th>Tokens</th><th>Latency</th><th>Cost</th><th>Retries</th><th>Fallback</th></tr></thead>
      <tbody>{receipts}</tbody></table></div></section>
    <section class="panel"><h2>Issues / stopped state</h2><ul class="issues">{issue_text}</ul>
      <p class="nonclaim">This report shows a bounded model proposal challenged by a deterministic rule.
      It does not certify truth, a world model, independent criticism, or general contradiction detection.</p></section>
  </div>
</main></body></html>"""
