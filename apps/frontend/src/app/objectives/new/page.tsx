"use client";

import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

const preset = "Generate a therapeutic hypothesis for ACVR1-driven Fibrodysplasia Ossificans Progressiva and identify candidate small molecules or intervention strategies. Use ToolUniverse tools where available, collect evidence, critique the hypothesis, and propose validation experiments.";

type ModelTool = {
  name: string;
  description: string;
  provider: string;
  status: string;
};

export default function NewObjectivePage() {
  const [title, setTitle] = useState("ACVR1/FOP therapeutic hypothesis generation");
  const [objective, setObjective] = useState(preset);
  const [agentCount, setAgentCount] = useState(6);
  const [maxRuntimeMinutes, setMaxRuntimeMinutes] = useState(30);
  const [toolBudgetUsd, setToolBudgetUsd] = useState(10);
  const [evidenceStrictness, setEvidenceStrictness] = useState("balanced");
  const [executionMode, setExecutionMode] = useState("background");
  const [agentFramework, setAgentFramework] = useState("langgraph");
  const [llmProvider, setLlmProvider] = useState("mock");
  const [llmModel, setLlmModel] = useState("mock-scientist");
  const [llmApiKeyEnvVar, setLlmApiKeyEnvVar] = useState("");
  const [modelTools, setModelTools] = useState<ModelTool[]>([]);
  const [selectedModelTools, setSelectedModelTools] = useState<string[]>([]);
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
    execution_backend: "local_process",
    agent_framework: agentFramework,
    openclaw_enabled: agentFramework === "openclaw",
    llm_provider: llmProvider,
    llm_model: llmModel,
    llm_api_key_env_var: llmApiKeyEnvVar,
    model_tool_names: selectedModelTools
  };

  useEffect(() => {
    apiGet<{ model_tools: ModelTool[] }>("/models")
      .then((data) => setModelTools(data.model_tools))
      .catch(() => setModelTools([]));
  }, []);

  function toggleModelTool(name: string) {
    setSelectedModelTools((current) => (
      current.includes(name) ? current.filter((item) => item !== name) : [...current, name]
    ));
  }

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
            <span className="label">Tool budget units</span>
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
            <span className="label">Agent framework</span>
            <select value={agentFramework} onChange={(event) => setAgentFramework(event.target.value)}>
              <option value="langgraph">LangGraph</option>
              <option value="custom_state_machine">Built-in state machine</option>
              <option value="openclaw">OpenClaw optional adapter</option>
            </select>
          </label>
          <label>
            <span className="label">LLM provider</span>
            <select value={llmProvider} onChange={(event) => setLlmProvider(event.target.value)}>
              <option value="mock">Mock local</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="gemini">Gemini</option>
              <option value="openai_compatible">OpenAI-compatible local</option>
              <option value="local_http">Local HTTP</option>
            </select>
          </label>
          <label>
            <span className="label">LLM model</span>
            <input value={llmModel} onChange={(event) => setLlmModel(event.target.value)} />
          </label>
          <label>
            <span className="label">API key env var</span>
            <input value={llmApiKeyEnvVar} placeholder="OPENAI_API_KEY" onChange={(event) => setLlmApiKeyEnvVar(event.target.value)} />
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
        {modelTools.length > 0 && (
          <>
            <div style={{ height: 16 }} />
            <div className="label">Custom model tools</div>
            <div className="grid compactGrid">
              {modelTools.map((tool) => (
                <label className="selectCard" key={tool.name}>
                  <input
                    type="checkbox"
                    checked={selectedModelTools.includes(tool.name)}
                    onChange={() => toggleModelTool(tool.name)}
                  />
                  <span>
                    <strong>{tool.name}</strong>
                    <small>{tool.provider} · {tool.status}</small>
                  </span>
                </label>
              ))}
            </div>
          </>
        )}
        <div style={{ height: 16 }} />
        <div className="actions">
          <button type="button" onClick={estimateRun}>Estimate run</button>
          {estimate !== null && <span className="badge">{estimate.toFixed(2)} resource units</span>}
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
