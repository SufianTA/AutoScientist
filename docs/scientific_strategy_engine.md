# Scientific Strategy Engine

AutoScientist now includes a deterministic scientific strategy layer that sits between evidence collection, hypothesis generation, and experiment design.

## Purpose

The strategy engine is meant to make the runtime scientifically operational rather than just conversational. It asks:

- What evidence do we actually have?
- What important evidence is missing?
- Which gap blocks confidence the most?
- Which next experiment or tool pass would change the decision?
- Should the system remain hypothesis-only or move toward validation planning?

## Runtime Placement

1. Evidence is collected from local context, public biomedical tools, ToolUniverse/OpenTargets, and configured model tools.
2. Evidence is typed and scored.
3. The Scientific Strategy Engine builds a structured gap map.
4. In live-data mode, the runtime can run a small evidence-repair pass using the highest-priority follow-up queries.
5. Hypothesis generation receives the updated evidence state.
6. The final experiment plan is ranked by value-of-information and gap coverage.
7. The strategy object is exported into the report, board post, replay bundle, and benchmark artifacts.

## What It Stores

The strategy object has this shape:

```json
{
  "schema": "autosci.scientific_strategy.v0.1",
  "readiness": {
    "score": 49,
    "tier": "hypothesis_only",
    "rationale": "hypothesis_only: blocked mainly by missing_target_disease_association (high)."
  },
  "evidence_profile": {
    "evidence_count": 4,
    "pubmed_article_count": 0,
    "has_tooluniverse": false,
    "has_safety": false,
    "has_counterevidence": false
  },
  "gaps": [
    {
      "id": "missing_target_disease_association",
      "severity": "high",
      "needed_evidence": "target-disease association from OpenTargets or equivalent public knowledge graph"
    }
  ],
  "recommended_followups": [
    {
      "gap_id": "missing_target_disease_association",
      "query": "IL6 rheumatoid arthritis OpenTargets association",
      "priority": "high"
    }
  ],
  "next_action": {
    "action": "repair_high_severity_evidence_gaps",
    "first_gap": "missing_target_disease_association"
  }
}
```

## Gap Types

- `insufficient_literature_depth`
- `missing_target_disease_association`
- `missing_intervention_specific_evidence`
- `missing_safety_evidence`
- `missing_cell_context_evidence`
- `missing_falsification_search`
- `claim_graph_evidence_gap`

## Experiment Ranking

Experiments now get additional decision fields:

- `addresses_gaps`
- `priority_score`
- `decision_gate`
- `success_criteria`
- `failure_modes`
- `why_next`

This turns the experiment list from generic validation suggestions into an auditable value-of-information plan.

## Configuration

The live evidence-repair pass is enabled by default and can be controlled with:

- `strategy_repair_enabled`: boolean, default `true`
- `strategy_repair_max_queries`: integer, default `2`, maximum `5`

CLI flags:

```bash
python tools/run_autoscientist_bench.py --disable-strategy-repair
python tools/run_autoscientist_bench.py --strategy-repair-max-queries 3
```

## Why This Matters

Before this change, the system could collect evidence and propose experiments, but it did not explicitly reason over which missing evidence should drive the next action. The new layer makes the runtime more like a persistent scientific operator: it identifies weak links, repairs evidence when possible, and ranks experiments by expected decision value.
