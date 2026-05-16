"use client";

import { useState } from "react";
import { Play } from "lucide-react";
import { apiPost } from "@/lib/api";

const preset = "Generate a therapeutic hypothesis for ACVR1-driven Fibrodysplasia Ossificans Progressiva and identify candidate small molecules or intervention strategies. Use ToolUniverse tools where available, collect evidence, critique the hypothesis, and propose validation experiments.";

export default function NewObjectivePage() {
  const [title, setTitle] = useState("ACVR1/FOP therapeutic hypothesis generation");
  const [objective, setObjective] = useState(preset);
  const [agentCount, setAgentCount] = useState(6);
  const [maxRuntimeMinutes, setMaxRuntimeMinutes] = useState(30);
  const [toolBudgetUsd, setToolBudgetUsd] = useState(10);
  const [evidenceStrictness, setEvidenceStrictness] = useState("balanced");
  const [executionMode, setExecutionMode] = useState("background");
  const [estimate, setEstimate] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const runConfig = {
    agent_count: agentCount,
    max_runtime_minutes: maxRuntimeMinutes,
    tool_budget_usd: toolBudgetUsd,
    evidence_strictness: evidenceStrictness,
    human_review_required: true,
    execution_mode: executionMode,
    payment_mode: "internal_credits"
  };

  async function estimateRun() {
    const result = await apiPost<{ estimated_cost_usd: number }>("/runs/estimate", { run_config: runConfig });
    setEstimate(result.estimated_cost_usd);
  }

  async function startRun() {
    setBusy(true);
    setError(null);
    try {
      const created = await apiPost<{ id: string }>("/objectives", {
        title,
        objective,
        mode: "full_auto_with_human_review",
        constraints: {
          use_tooluniverse: true,
          allow_custom_tools: true,
          require_citations: true,
          require_critic: true
        }
      });
      const run = await apiPost<{ id: string }>("/runs", {
        objective_id: created.id,
        execute_demo: true,
        run_config: runConfig
      });
      window.location.href = `/runs/${run.id}`;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Run submission failed");
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <div className="kicker">New objective</div>
      <h1>Launch a research loop</h1>
      <div className="panel">
        <label className="label" htmlFor="title">Title</label>
        <input id="title" value={title} onChange={(event) => setTitle(event.target.value)} />
        <div style={{ height: 16 }} />
        <label className="label" htmlFor="objective">Scientific objective</label>
        <textarea id="objective" value={objective} onChange={(event) => setObjective(event.target.value)} />
        <div style={{ height: 16 }} />
        <div className="configGrid">
          <label>
            <span className="label">Agents</span>
            <input type="number" min={1} max={12} value={agentCount} onChange={(event) => setAgentCount(Number(event.target.value))} />
          </label>
          <label>
            <span className="label">Runtime limit</span>
            <input type="number" min={5} max={240} value={maxRuntimeMinutes} onChange={(event) => setMaxRuntimeMinutes(Number(event.target.value))} />
          </label>
          <label>
            <span className="label">Tool budget</span>
            <input type="number" min={0} max={500} value={toolBudgetUsd} onChange={(event) => setToolBudgetUsd(Number(event.target.value))} />
          </label>
          <label>
            <span className="label">Evidence strictness</span>
            <select value={evidenceStrictness} onChange={(event) => setEvidenceStrictness(event.target.value)}>
              <option value="balanced">Balanced</option>
              <option value="strict">Strict</option>
              <option value="exploratory">Exploratory</option>
            </select>
          </label>
          <label>
            <span className="label">Execution</span>
            <select value={executionMode} onChange={(event) => setExecutionMode(event.target.value)}>
              <option value="background">Background</option>
              <option value="queued">Queued worker</option>
              <option value="inline">Inline demo</option>
            </select>
          </label>
        </div>
        <div style={{ height: 16 }} />
        <div className="actions">
          <button type="button" onClick={estimateRun}>Estimate run</button>
          {estimate !== null && <span className="badge">${estimate.toFixed(2)} estimated</span>}
        </div>
        <div style={{ height: 16 }} />
        <button onClick={startRun} disabled={busy}>
          <Play size={18} /> {busy ? "Submitting" : "Submit research run"}
        </button>
        {error && <p className="muted">{error}</p>}
      </div>
    </main>
  );
}
