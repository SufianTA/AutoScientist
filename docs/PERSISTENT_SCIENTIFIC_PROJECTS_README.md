# Persistent Scientific Projects

This document describes the next product direction for AutoScientist and ClawInstitute: move from one-shot runs to persistent scientific projects where agents, tools, and humans collaborate over time.

## Core Idea

AutoScientist should not be optimized only for fast report generation. Hard scientific problems, such as complex cancer resistance, require iterative exploration, many tool calls, interruptions, restarts, expert review, and accumulated project memory.

The desired model is:

```text
project -> many runs -> shared evidence -> human review -> versioned consensus
```

Instead of:

```text
run -> report -> done
```

## Local Implementation

The first implementation uses the existing local SQLite database as the ClawInstitute
project database. It is intentionally domain-generic: projects store objectives,
runs, checkpoints, queued tasks, reviews, versions, evidence, hypotheses, and tool
calls without assuming a specific disease, target, drug, or benchmark.

Command-line entry point:

```bash
claw-project create --title "Project title" --objective "Scientific question" --mode deep_investigation
```

```bash
claw-project run --project project-slug --mode campaign
```

```bash
claw-project resume --project project-slug
```

```bash
claw-project pause --project project-slug --reason "waiting for expert review"
```

```bash
claw-project snapshot --project project-slug --summary "Reviewed state after exploration wave"
```

```bash
claw-project export --project project-slug --output outputs/projects/project-slug/export.json
```

API entry points:

- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id_or_slug}`
- `POST /projects/{project_id_or_slug}/pause`
- `POST /projects/{project_id_or_slug}/resume`
- `POST /projects/{project_id_or_slug}/versions`
- `POST /projects/{project_id_or_slug}/reviews`
- `POST /projects/{project_id_or_slug}/export`

## ClawInstitute Project Workspace

A ClawInstitute project is a long-lived workspace for one scientific question or research program.

Each project should contain:

- Objective and scope
- Current scientific claims
- Evidence store
- Tool-call cache
- Agent traces
- Open questions
- Critiques and reviewer notes
- Experiment plans
- Versioned project snapshots
- Final dossiers and reports
- Human expert review history

Multiple AutoScientist runs should be able to join the same project, continue from the existing state, and add new evidence without starting from zero.

## Investigation Modes

AutoScientist should support different execution modes based on depth, time, cost, and scientific risk.

### Quick Triage

Purpose: rapid orientation.

Expected scale:

- Minutes
- Tens of tool calls
- Initial entity extraction
- Initial claim map
- First evidence scan
- Early limitations

Output:

- Short summary
- Known/unknown list
- Initial claim graph
- Recommended next exploration steps

### Deep Investigation

Purpose: serious analysis of a specific scientific problem.

Expected scale:

- Hours
- Hundreds to thousands of tool calls
- Iterative retrieval and scoring
- Citation following
- Variant and pathway expansion
- Safety, clinical trial, and contradiction checks
- Repeated claim revision

Output:

- Evidence-backed dossier
- Claim-by-claim support matrix
- Contradiction and uncertainty analysis
- Experiment plan with decision gates
- Full provenance

### Campaign Mode

Purpose: broad systematic exploration across many hypotheses or cases.

Expected scale:

- Overnight or multi-day
- Thousands to tens of thousands of tool calls
- Multiple targets, diseases, mechanisms, interventions, datasets, and experiments
- Shared project memory
- Periodic checkpoints

Output:

- Ranked research program
- Cross-case evidence map
- Candidate hypotheses
- Project-level state graph
- Policy/model training traces
- Expert-review queue

### Cloud Campaign Mode

Purpose: run long investigations continuously in cloud infrastructure without depending on a local laptop or a single interactive session.

Expected scale:

- Multi-hour, overnight, or multi-day execution
- Hundreds to tens of thousands of tool calls
- Scheduled pause/resume windows
- Cloud-hosted project database
- Persistent artifact storage
- Budget and quota monitoring
- Human review checkpoints

Cloud campaign mode should allow a user to start an AutoScientist project on a cloud machine or pod, disconnect, and return later without losing progress. The agent should continue working while the user is offline, but it should not run without limits.

Required cloud behavior:

- Start from a project workspace and run configuration.
- Persist every checkpoint to cloud storage or a managed database.
- Use a durable task queue for pending tool calls and agent actions.
- Save all tool outputs, traces, and intermediate conclusions immediately.
- Detect provider quota, rate limits, and cloud shutdown warnings.
- Pause automatically when budget, quota, relevance, or failure thresholds are hit.
- Resume cleanly after pod restart, machine replacement, or process crash.
- Produce periodic progress summaries for humans.

Cloud campaign agents should be able to take breaks. A break is a controlled pause, not a crash.

Break policies may include:

- Pause after each exploration wave.
- Pause after a maximum number of tool calls.
- Pause when cost reaches a threshold.
- Pause when irrelevant evidence exceeds a threshold.
- Pause when an expert review is required.
- Pause during API provider cooldown or rate-limit windows.
- Pause on a schedule, such as every night or every N hours.

When paused, the project should show:

- Last completed phase
- Current evidence and claims
- Pending task queue
- Failed or deferred tool calls
- Cost and token usage
- Next recommended action
- Whether human approval is needed

Example cloud commands:

```bash
autosci cloud start --project egfr-resistance --mode campaign --budget-usd 200 --max-tool-calls 10000
```

```bash
autosci cloud status --project egfr-resistance
```

```bash
autosci cloud pause --project egfr-resistance
```

```bash
autosci cloud resume --project egfr-resistance
```

```bash
autosci cloud export --project egfr-resistance --version latest
```

Cloud campaign mode should make long-running scientific exploration operationally safe: durable state, explicit budgets, resumable queues, human checkpoints, and clear audit trails.

## Tool Exploration And Expansion

The system does not need thousands of different tools. It needs a controlled registry of tools and the ability to generate thousands of useful tool calls.

Examples of tool types:

- PubMed search
- ClinicalTrials search
- OpenTargets queries
- Reactome/pathway search
- PubChem lookup
- Drug/safety/adverse-event tools
- Variant annotation tools
- Omics and public dataset search
- Citation expansion
- Guideline and label search
- Contradiction/failure search

The expansion engine should generate tool calls by combining:

- Genes
- Variants
- Diseases
- Drugs
- Pathways
- Mechanisms
- Resistance modes
- Safety concerns
- Trial phases
- Cohort filters
- Assay types
- Citations and related entities

For example, a deep EGFR resistance project may expand into calls for:

- EGFR C797S and osimertinib resistance
- T790M/C797S cis/trans phasing
- MET amplification bypass
- ERBB2 amplification bypass
- RET or ALK fusion emergence
- BRAF V600E resistance
- AXL/EMT cell-state transition
- Small-cell transformation
- CNS sanctuary progression
- Fourth-generation EGFR inhibitors
- Combination safety and clinical trial status

## Iterative Exploration Loop

Deep mode should use an iterative loop:

1. Generate or update claims.
2. Identify required evidence for each claim.
3. Plan tool calls.
4. Execute a bounded batch of calls.
5. Store outputs and provenance.
6. Score relevance and quality.
7. Map evidence to claims.
8. Detect gaps and contradictions.
9. Spawn follow-up searches.
10. Ask what would falsify the current claim.
11. Search for falsification.
12. Stop only when budget, convergence, or quality gates are met.

This loop should continue until the project reaches a defined stopping condition, not just until a single report is generated.

## Budgets And Stopping Conditions

Every project run should have explicit budgets:

- Maximum wall time
- Maximum tool calls
- Maximum cost
- Maximum failed calls
- Maximum irrelevant evidence rate
- Maximum API retries
- Minimum claim coverage
- Minimum contradiction-search coverage
- Minimum evidence relevance

The system should stop or ask for human approval when:

- Budget is exhausted
- Tool failures exceed threshold
- Evidence relevance remains low
- New evidence stops changing conclusions
- Claims remain unsupported after repeated search
- Human review is required

## Resumability

Long-running scientific work must be stop-safe and resumable.

Users should be able to turn off a machine or stop a pod without losing progress.

Required state:

- Project ID
- Run ID
- Current phase
- Completed tool calls
- Pending tool calls
- Tool-call cache
- Evidence collected
- Claim graph
- Open gaps
- Failed calls
- Agent decisions
- Cost/time counters
- Next planned actions

Example resume command:

```bash
python tools/run_deep_case.py --resume run_abc123
```

or:

```bash
autosci resume run_abc123
```

The executor should checkpoint after every meaningful step:

- Entity extraction
- Claim generation
- Tool-plan generation
- Each retrieval batch
- Evidence scoring
- Claim mapping
- Critique
- Experiment planning
- Report generation

## Idempotent Tool Calls

Before executing any tool call, the system should check:

- Was this exact call already executed?
- Is there a valid cached result?
- Did it fail before?
- Should it be retried?
- Has the tool output expired?

This prevents wasting money and repeating work across restarts or multiple agents.

## Shared Project Database

Each ClawInstitute project should have a database or persistent store with:

- `projects`
- `runs`
- `agents`
- `tool_calls`
- `tool_results`
- `evidence_items`
- `claims`
- `claim_evidence_links`
- `critiques`
- `experiments`
- `human_reviews`
- `versions`
- `reports`

Every record should include:

- Creator: human, agent, or tool
- Timestamp
- Source run
- Version
- Confidence or quality score where appropriate
- Provenance
- Status: active, superseded, rejected, accepted

## Versioning

Projects should be versioned over time.

A version should capture:

- Current claims
- Current evidence set
- Current critique state
- Current experiment plan
- Human review decisions
- Generated report

Example versions:

- `v0.1`: initial triage
- `v0.2`: deep retrieval completed
- `v0.3`: expert corrections applied
- `v1.0`: report-ready consensus

Agents should never overwrite prior scientific state without preserving history.

## Human Expert In The Loop

Human experts should be able to join a project and:

- Correct entity extraction
- Mark evidence as relevant or irrelevant
- Approve or reject claims
- Add private context
- Request more exploration
- Redirect the agent to a new hypothesis
- Freeze a version
- Approve final report language

Human review should become part of the project state, not an external comment lost in chat.

## Multi-Agent Collaboration

Agents should be able to come online and join an existing project.

Possible roles:

- Planner agent
- Retrieval agent
- Literature agent
- ToolUniverse agent
- Mechanism agent
- Safety agent
- Contradiction agent
- Experiment designer
- Critic agent
- Publisher agent
- Human-review coordinator

Each agent should add traces and outputs to the same project workspace.

## Project Handoff

Another user or machine should be able to resume the project:

1. Clone or open the ClawInstitute project.
2. Load the database and artifact store.
3. Inspect current state.
4. Start a new AutoScientist run in the same project.
5. Continue from pending questions and unresolved claims.

This makes the system collaborative across days, machines, pods, and people.

## Reporting Model

Reports should be generated from the project state, not only from a single run.

A good project report should include:

- Current conclusion
- Claims and evidence links
- What changed since the last version
- Open uncertainties
- Contradictions
- Tool coverage
- Failed searches
- Expert review status
- Recommended next experiments
- Full audit trail link

The public report should be concise. The full traces should remain available behind an audit/provenance view.

## Product Principle

The goal is not to make AutoScientist look fast.

The goal is to make it:

- Persistent
- Auditable
- Resumable
- Tool-grounded
- Collaborative
- Honest about uncertainty
- Useful for real scientific work over time

For difficult biomedical questions, a good system should be willing to explore deeply, stop safely, resume later, and improve the shared project state with every run.
