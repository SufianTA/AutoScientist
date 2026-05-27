import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.models import BoardPost, EvidenceItem, Hypothesis, Run
from app.db.session import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


def ascii_safe(value: object) -> str:
    text = str(value)
    replacements = {
        "α": "alpha",
        "β": "beta",
        "γ": "gamma",
        "δ": "delta",
        "κ": "kappa",
        "μ": "mu",
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "’": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("ascii", errors="ignore").decode("ascii")


@router.get("/{run_id}")
def get_report(run_id: str, db: Session = Depends(get_db)) -> dict:
    return build_report(run_id, db)


@router.get("/{run_id}/download")
def download_report(run_id: str, format: str = "markdown", db: Session = Depends(get_db)) -> Response:
    report = build_report(run_id, db)
    if format == "json":
        return Response(
            content=json.dumps(report, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{run_id}_report.json"'},
        )
    if format not in {"markdown", "md"}:
        raise HTTPException(status_code=400, detail="format must be markdown or json")
    markdown = render_markdown_report(report)
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{run_id}_report.md"'},
    )


def build_report(run_id: str, db: Session) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    hypothesis = db.query(Hypothesis).filter(Hypothesis.run_id == run_id).first()
    evidence = db.query(EvidenceItem).filter(EvidenceItem.run_id == run_id).all()
    posts = db.query(BoardPost).filter(BoardPost.run_id == run_id).all()
    local_only = bool(evidence) and all(str(item.source).startswith("local_") for item in evidence)
    evidence_payload = [
        {
            "source": item.source,
            "text": item.evidence_text,
            "structured": item.structured_json,
            "support_label": item.support_label,
            "support_score": item.support_score,
        }
        for item in evidence
    ]
    hypothesis_post_content = next(
        (post.content_json for post in posts if post.post_type == "hypothesis"),
        {},
    )
    next_experiments = hypothesis_post_content.get("next_experiments", [])
    if local_only:
        guardrails = [
            "Candidate hypothesis only.",
            "Local planning mode only; no external evidence was retrieved, so this is not evidence-supported.",
            "Run strict real-data mode with a configured LLM before scientific interpretation.",
        ]
    else:
        guardrails = [
            "Candidate hypothesis only.",
            "Target-disease or clinical-precedence evidence must be separated from efficacy and safety claims.",
            "Requires experimental validation before clinical interpretation.",
        ]
    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "final_confidence": run.final_confidence,
        },
        "hypothesis": {
            "title": hypothesis.title if hypothesis else "No hypothesis generated",
            "text": hypothesis.hypothesis_text if hypothesis else "",
            "confidence": hypothesis.confidence if hypothesis else None,
            "status": hypothesis.status if hypothesis else None,
        },
        "evidence": evidence_payload,
        "board_posts": [
            {
                "post_type": post.post_type,
                "agent_author": post.agent_author,
                "content": post.content_json,
            }
            for post in posts
        ],
        "objective_classification": hypothesis_post_content.get("objective_classification", {}),
        "case_profile": hypothesis_post_content.get("case_profile", {}),
        "capability_plan": hypothesis_post_content.get("capability_plan", {}),
        "evaluation_criteria": hypothesis_post_content.get("evaluation_criteria", []),
        "report_evaluation": hypothesis_post_content.get("report_evaluation", {}),
        "claim_retrieval_plan": hypothesis_post_content.get("claim_retrieval_plan", {}),
        "claim_graph": hypothesis_post_content.get("claim_graph", {}),
        "claim_evidence_matrix": hypothesis_post_content.get("claim_evidence_matrix", {}),
        "evidence_coverage_matrix": hypothesis_post_content.get("evidence_coverage_matrix", {}),
        "experiment_gate_plan": hypothesis_post_content.get("experiment_gate_plan", {}),
        "quality_dashboard": hypothesis_post_content.get("quality_dashboard", {}),
        "critique_enforced_revision": hypothesis_post_content.get("critique_enforced_revision", {}),
        "critique_repair_lock": hypothesis_post_content.get("critique_repair_lock", {}),
        "abstention": hypothesis_post_content.get("abstention", {}),
        "abstention_policy": hypothesis_post_content.get("abstention_policy", {}),
        "actionability_profile": hypothesis_post_content.get("actionability_profile", {}),
        "adaptive_tool_plan": hypothesis_post_content.get("adaptive_tool_plan", {}),
        "biotruth_critic": hypothesis_post_content.get("biotruth_critic", {}),
        "contradiction_analysis": hypothesis_post_content.get("contradiction_analysis", {}),
        "evidence_hierarchy": hypothesis_post_content.get("evidence_hierarchy", {}),
        "scientific_strategy": hypothesis_post_content.get("scientific_strategy", {}),
        "next_experiments": next_experiments,
        "experiments": next_experiments,
        "key_claims": hypothesis_post_content.get("key_claims", []),
        "guardrails": guardrails,
    }


def render_markdown_report(report: dict) -> str:
    hypothesis = report["hypothesis"]
    hypothesis_post = next(
        (post["content"] for post in report["board_posts"] if post["post_type"] == "hypothesis"),
        {},
    )
    lines = [
        f"# {ascii_safe(hypothesis['title'])}",
        "",
        f"Run: `{report['run']['id']}`",
        f"Status: `{report['run']['status']}`",
        f"Confidence: `{hypothesis['confidence']}`",
        f"Confidence interpretation: `{hypothesis_post.get('confidence_interpretation', 'not available')}`",
        "",
        "## Candidate Hypothesis",
        "",
        ascii_safe(hypothesis["text"]) or "No hypothesis text generated.",
        "",
        "## Scientific Assessment",
        "",
    ]
    for item in hypothesis_post.get("scientific_assessment", []):
        lines.append(f"- {ascii_safe(item)}")
    # Key claims from final LLM synthesis (present when LLM path ran with rich_mode)
    key_claims = report.get("key_claims") or []
    if key_claims:
        lines.extend(["", "## Key Scientific Claims", ""])
        for claim in key_claims:
            lines.append(f"- {ascii_safe(claim)}")
    classification = report.get("objective_classification", {})
    if classification:
        lines.extend(["", "## Objective Classification", ""])
        lines.append(f"- Primary task: `{classification.get('primary_task', 'unknown')}`")
        lines.append(f"- Domain: `{classification.get('domain', 'unknown')}`")
        lines.append(f"- Risk level: `{classification.get('risk_level', 'unknown')}`")
        if classification.get("required_capabilities"):
            lines.append(f"- Capabilities: {', '.join(classification['required_capabilities'])}")
    case_profile = report.get("case_profile", {})
    if case_profile:
        lines.extend(["", "## Case Capability Plan", ""])
        branches = case_profile.get("mechanism_branches", [])
        assays = case_profile.get("validation_assays", [])
        capabilities = case_profile.get("capability_demonstrations", [])
        if branches:
            lines.append("**Mechanism branches to resolve:**")
            for branch in branches[:10]:
                lines.append(f"- `{branch.get('id', 'branch')}`: {ascii_safe(branch.get('label', ''))}")
        if assays:
            lines.append("")
            lines.append("**Validation assays requested by the case:**")
            for assay in assays[:8]:
                lines.append(f"- {ascii_safe(assay)}")
        if capabilities:
            lines.append("")
            lines.append(f"**Capabilities exercised:** {', '.join(capabilities)}")
    evaluation = report.get("report_evaluation", {})
    if evaluation:
        lines.extend(["", "## Evaluation Criteria", ""])
        lines.append(
            f"Score: `{evaluation.get('score')}` "
            f"({evaluation.get('earned_points')}/{evaluation.get('total_points')} points)"
        )
        for criterion in evaluation.get("criteria", [])[:8]:
            mark = "met" if criterion.get("satisfied") else "gap"
            lines.append(f"- [{mark}] {ascii_safe(criterion.get('criterion', ''))}")
    abstention = report.get("abstention", {})
    if abstention:
        lines.extend(["", "## Abstention Assessment", ""])
        lines.append(f"- Required: `{abstention.get('abstention_required')}`")
        lines.append(f"- Allowed output: {ascii_safe(abstention.get('allowed_output', 'not recorded'))}")
        for reason in abstention.get("reasons", []):
            lines.append(f"- Reason: {ascii_safe(reason)}")
    abstention_policy = report.get("abstention_policy", {})
    biotruth_critic = report.get("biotruth_critic", {})
    evidence_hierarchy = report.get("evidence_hierarchy", {})
    contradiction_analysis = report.get("contradiction_analysis", {})
    actionability_profile = report.get("actionability_profile", {})
    adaptive_tool_plan = report.get("adaptive_tool_plan", {})
    if any((abstention_policy, biotruth_critic, evidence_hierarchy, contradiction_analysis, actionability_profile, adaptive_tool_plan)):
        lines.extend(["", "## Biomedical Validation Controls", ""])
        if biotruth_critic:
            lines.append(
                f"- BioTruth critic: `{biotruth_critic.get('verdict', 'not recorded')}` "
                f"(score: `{biotruth_critic.get('weighted_score', 'n/a')}`)"
            )
        if evidence_hierarchy:
            lines.append(
                f"- Evidence hierarchy: `{evidence_hierarchy.get('evidence_count', 0)}` evidence items; "
                f"`{evidence_hierarchy.get('high_tier_evidence_count', 0)}` high-tier items; "
                f"score `{evidence_hierarchy.get('hierarchy_score', 'n/a')}`"
            )
        if contradiction_analysis:
            lines.append(
                f"- Contradiction search attempted: "
                f"`{contradiction_analysis.get('contradiction_search_attempted', False)}`; "
                f"findings `{contradiction_analysis.get('finding_count', contradiction_analysis.get('contradiction_count', 0))}`"
            )
        if abstention_policy:
            lines.append(
                f"- Abstention policy decision: `{abstention_policy.get('decision', 'not recorded')}` "
                f"with required flag `{abstention_policy.get('abstention_required', 'n/a')}`"
            )
        if actionability_profile:
            lines.append(
                f"- Actionability profile: `{actionability_profile.get('level', 'not recorded')}` "
                f"with recommended decision `{actionability_profile.get('recommended_decision', 'n/a')}`"
            )
        for recommendation in adaptive_tool_plan.get("recommendations", [])[:6]:
            lines.append(
                f"- Recommended follow-up tool: `{recommendation.get('tool_name', 'not recorded')}` "
                f"for `{recommendation.get('gap_id', 'unclassified_gap')}`"
            )
    # ── Scientific Strategy ──────────────────────────────────────────────────────
    strategy = report.get("scientific_strategy", {})
    if strategy:
        readiness = strategy.get("readiness", {})
        lines.extend(["", "## Scientific Strategy", ""])
        tier = readiness.get("tier", "not recorded")
        score = readiness.get("score", "n/a")
        tier_label = {
            # values emitted by scientific_strategy.py
            "validation_ready": "**Validation ready**",
            "experiment_ready_with_gaps": "**Experiment ready (with gaps)**",
            "hypothesis_only": "**Hypothesis only**",
            # legacy / alternate names kept for compatibility
            "ready_for_validation": "**Ready for validation**",
            "evidence_building": "**Evidence building**",
            "early_planning": "**Early planning**",
            "insufficient": "**Insufficient evidence**",
        }.get(str(tier), f"`{tier}`")
        lines.append(f"**Readiness tier:** {tier_label} ({score}/100)")
        if readiness.get("rationale"):
            lines.append(f"> {ascii_safe(readiness.get('rationale'))}")
        next_action = strategy.get("next_action", {})
        if next_action:
            lines.append(f"\n**Recommended next action:** `{next_action.get('action', 'not recorded')}`")
            # strategy emits "reason"; guard against both "rationale" and "reason"
            na_rationale = next_action.get("rationale") or next_action.get("reason", "")
            if na_rationale:
                lines.append(f"> {ascii_safe(na_rationale)}")
        gaps = strategy.get("gaps", [])
        if gaps:
            lines.append("\n**Evidence gaps identified:**\n")
            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
            for gap in gaps[:8]:
                icon = severity_icon.get(str(gap.get("severity", "")), "•")
                lines.append(
                    f"- {icon} **{gap.get('id', '?')}** ({gap.get('severity', '?')}): "
                    f"{ascii_safe(gap.get('rationale', ''))}"
                )
                if gap.get("recommended_tool"):
                    lines.append(f"  - Recommended tool: `{gap.get('recommended_tool')}`")

    # ── Claim Graph ──────────────────────────────────────────────────────────────
    claim_graph = report.get("claim_graph", {})
    if claim_graph and claim_graph.get("claims"):
        lines.extend(["", "## Claim Graph", ""])
        lines.append(
            f"*{len(claim_graph.get('claims', []))} claims mapped across "
            f"{claim_graph.get('evidence_count', 0)} evidence items.*"
        )
        lines.append("")
        for claim in claim_graph.get("claims", []):
            boundary = claim.get("claim_boundary", "unknown")
            boundary_badge = {
                "computational_prioritization": "`computational`",
                "preclinical_hypothesis": "`preclinical`",
                "clinical_efficacy_forbidden": "`⚠ no efficacy claim`",
                "safety_claim_forbidden": "`⚠ no safety claim`",
                "abstain": "`abstain`",
            }.get(boundary, f"`{boundary}`")
            lines.append(f"### Claim {claim.get('id', '?')} — {boundary_badge}")
            lines.append(f"> {ascii_safe(claim.get('text', ''))}")
            support_srcs = claim.get("supporting_evidence_sources", [])
            contra_srcs = claim.get("contradictory_evidence_sources", [])
            gap_srcs = claim.get("evidence_gaps", [])
            if support_srcs:
                lines.append(f"- ✅ **Supporting:** {', '.join(support_srcs[:6])}")
            if contra_srcs:
                lines.append(f"- ❌ **Contradicting:** {', '.join(contra_srcs[:4])}")
            if gap_srcs:
                lines.append(f"- ⬜ **Gaps / irrelevant:** {', '.join(gap_srcs[:4])}")
            lines.append("")

    coverage = report.get("evidence_coverage_matrix", {})
    if coverage and coverage.get("requirements"):
        lines.extend(["", "## Evidence Coverage Matrix", ""])
        lines.append(
            f"Coverage score: `{coverage.get('coverage_score')}` "
            f"({coverage.get('covered_count', 0)} covered, "
            f"{coverage.get('partial_count', 0)} partial, "
            f"{coverage.get('missing_count', 0)} missing)"
        )
        lines.extend(["", "| Requirement | Status | Matched sources |", "| --- | --- | --- |"])
        for row in coverage.get("requirements", [])[:12]:
            sources = ", ".join(row.get("matched_sources", [])[:6]) or "none"
            lines.append(
                f"| {ascii_safe(row.get('label', row.get('id', '')))} | "
                f"`{row.get('status')}` | {ascii_safe(sources)} |"
            )

    # ── Candidate Intervention Summary ───────────────────────────────────────────
    lines.extend(
        [
            "",
            "## Candidate Intervention Summary",
            "",
            ascii_safe(
                hypothesis_post.get(
                    "candidate_intervention_summary",
                    "No candidate intervention summary generated.",
                )
            ),
        ]
    )

    # ── Evidence with article highlights ────────────────────────────────────────
    lines.extend(["", "## Evidence", ""])
    # Collect PubMed article titles for highlights
    article_titles: list[tuple[str, str, str]] = []  # (title, pmid, source_label)
    for item in report["evidence"]:
        structured = item.get("structured") or {}
        if isinstance(structured, dict):
            for article in structured.get("articles", []):
                t = article.get("title", "")
                pmid = article.get("pmid", "")
                if t:
                    article_titles.append((t, pmid, item.get("source", "")))
    if article_titles:
        lines.append("### Retrieved Literature Highlights\n")
        for title, pmid, src in article_titles[:10]:
            pmid_link = f" (PMID [{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/))" if pmid else ""
            lines.append(f"- {ascii_safe(title)}{pmid_link}")
        lines.append("")

    lines.extend(
        [
            "### Evidence Summary Table",
            "",
            "| Source | Label | Score | Evidence |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in report["evidence"]:
        text = ascii_safe(item["text"]).replace("|", "\\|").replace("\n", " ")[:300]
        lines.append(
            f"| {item['source']} | {item['support_label']} | {item['support_score']} | {text} |"
        )

    # ── Citations ────────────────────────────────────────────────────────────────
    citations = hypothesis_post.get("citations", [])
    if citations:
        lines.extend(["", "## Citations and Retrieved Records", ""])
        for citation in citations:
            label = ascii_safe(citation.get("title") or citation.get("source"))
            url = citation.get("url", "")
            details = []
            for key in ("pmid", "cid", "gene_id", "journal", "pubdate"):
                if citation.get(key):
                    details.append(f"{key}: {citation[key]}")
            suffix = f" ({'; '.join(details)})" if details else ""
            lines.append(f"- [{label}]({url}){suffix}")

    # ── Limitations ──────────────────────────────────────────────────────────────
    limitations = hypothesis_post.get("limitations", [])
    if limitations:
        lines.extend(["", "## Limitations", ""])
        for limitation in limitations:
            lines.append(f"- {ascii_safe(limitation)}")

    # ── Agent Debate ─────────────────────────────────────────────────────────────
    debate = hypothesis_post.get("agent_debate", {})
    if debate:
        lines.extend(["", "## Scientist Panel Debate", ""])
        collab = debate.get("collaboration_model", "not recorded")
        lines.append(f"*Collaboration model: `{collab}`*\n")
        vote_icon = {
            "support": "✅ support",
            "support_with_limits": "✅ support with limits",
            "revise": "🔄 revise",
            "abstain": "⛔ abstain",
        }
        for position in debate.get("scientist_positions", []):
            vote = position.get("vote", "review")
            icon = vote_icon.get(vote, f"◻ {vote}")
            lines.append(f"### {position.get('agent_name', 'agent')} — {icon}")
            if position.get("discipline"):
                lines.append(f"*Discipline: {position.get('discipline')}*\n")
            if position.get("position"):
                lines.append(f"{ascii_safe(position.get('position', ''))}\n")
            concerns = position.get("concerns", [])
            if concerns:
                lines.append("**Concerns:**")
                for concern in concerns[:4]:
                    lines.append(f"- {ascii_safe(concern)}")
                lines.append("")
            followups = position.get("requested_followups", [])
            if followups:
                lines.append("**Requested follow-ups:**")
                for f in followups[:3]:
                    lines.append(f"- {ascii_safe(f)}")
                lines.append("")
        adjudication = debate.get("pi_adjudication", {})
        if adjudication:
            lines.append("### PI Adjudication\n")
            if adjudication.get("final_confidence") is not None:
                lines.append(f"**Final confidence:** `{adjudication.get('final_confidence')}`\n")
            if adjudication.get("rationale"):
                lines.append(f"{ascii_safe(adjudication.get('rationale'))}\n")
            for item in adjudication.get("softened_or_rejected_claims", []):
                lines.append(f"- ⚠ Softened/rejected: {ascii_safe(item)}")

    # ── Proposed Experiments ─────────────────────────────────────────────────────
    experiments = hypothesis_post.get("next_experiments", [])
    if experiments:
        lines.extend(["", "## Proposed Next Experiments", ""])
        for idx, experiment in enumerate(experiments, start=1):
            exp_type = experiment.get("type", "unknown")
            feasibility = experiment.get("feasibility", "?")
            gain = experiment.get("expected_information_gain", "?")
            cost = experiment.get("cost", "?")
            lines.append(f"### Experiment {idx}: {ascii_safe(experiment.get('name', '—'))}")
            lines.append(f"**Type:** `{exp_type}` | **Cost:** `{cost}` | "
                         f"**Feasibility:** `{feasibility}` | **Expected information gain:** `{gain}`\n")
            decision_gate = experiment.get("decision_gate")
            if decision_gate:
                lines.append(f"**Decision gate:** {ascii_safe(decision_gate)}\n")
            success_criteria = experiment.get("success_criteria", [])
            if success_criteria:
                lines.append("**Success criteria:**")
                for criterion in success_criteria:
                    lines.append(f"- {ascii_safe(criterion)}")
                lines.append("")
            failure_modes = experiment.get("failure_modes", [])
            if failure_modes:
                lines.append("**Failure modes to watch:**")
                for mode in failure_modes:
                    lines.append(f"- {ascii_safe(mode)}")
                lines.append("")
            if experiment.get("decision_impact_score") is not None:
                lines.append(
                    f"**Gate score:** `{experiment.get('decision_impact_score')}` "
                    f"({experiment.get('gate_quality', 'not scored')})\n"
                )
            gate_reasons = experiment.get("gate_reasons", [])
            if gate_reasons:
                lines.append("**Gate improvements:**")
                for reason in gate_reasons:
                    lines.append(f"- {ascii_safe(reason)}")
                lines.append("")

    # ── Critique ─────────────────────────────────────────────────────────────────
    critique_post = next(
        (post for post in report["board_posts"] if post.get("post_type") == "critique"), None
    )
    if critique_post:
        content = critique_post.get("content", {})
        critique_text = content.get("critique") if isinstance(content, dict) else str(content)
        severity = content.get("severity") if isinstance(content, dict) else None
        if critique_text:
            lines.extend(["", "## Critique and Refinement", ""])
            if severity:
                lines.append(f"**Severity:** `{severity}`\n")
            lines.append(ascii_safe(str(critique_text)))
            recommended_fix = content.get("recommended_fix") if isinstance(content, dict) else None
            if recommended_fix:
                lines.append(f"\n**Recommended fix:** {ascii_safe(recommended_fix)}")

    # ── Guardrails ───────────────────────────────────────────────────────────────
    lines.extend(["", "## Guardrails", ""])
    for guardrail in report["guardrails"]:
        lines.append(f"- {guardrail}")
    lines.append("")
    lines.append("---")
    lines.append("*Generated by AutoScientist. Candidate hypothesis only. Requires experimental validation.*")
    return "\n".join(lines) + "\n"
