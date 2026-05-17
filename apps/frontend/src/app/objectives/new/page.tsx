"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, DatabaseZap, KeyRound, Play, ShieldCheck, Sparkles } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

const presets = [
  {
    title: "ACVR1/FOP therapeutic hypothesis",
    objective: "Generate a scientist-grade therapeutic hypothesis analysis for ACVR1-driven Fibrodysplasia Ossificans Progressiva. Use live public evidence, identify disease-target mechanism, candidate interventions, safety concerns, citations, and validation experiments. Do not claim clinical efficacy."
  },
  {
    title: "PCSK9 familial hypercholesterolemia",
    objective: "Generate a scientist-grade therapeutic hypothesis analysis for PCSK9-driven familial hypercholesterolemia and elevated LDL cholesterol. Use live public evidence, identify disease-target mechanism, approved and investigational intervention classes, safety concerns, citations, and validation experiments. Do not claim efficacy beyond retrieved evidence."
  },
  {
    title: "CFTR F508del cystic fibrosis",
    objective: "Generate a scientist-grade therapeutic hypothesis analysis for CFTR F508del cystic fibrosis. Use live public evidence, identify disease-target mechanism, modulator intervention classes, safety concerns, citations, and validation experiments. Do not claim efficacy beyond retrieved evidence."
  }
];

const providerDefaults: Record<string, { model: string; key: string }> = {
  openai: { model: "gpt-4.1", key: "OPENAI_API_KEY" },
  anthropic: { model: "claude-sonnet-4-6", key: "ANTHROPIC_API_KEY" },
  gemini: { model: "gemini-1.5-pro", key: "GEMINI_API_KEY" },
  openai_compatible: { model: "local-model", key: "OPENAI_COMPATIBLE_API_KEY" },
  local_http: { model: "local-http-model", key: "" },
  mock: { model: "mock-scientist", key: "" }
};

type ModelTool = {
  name: string;
  description: string;
  provider: string;
  status: string;
};

function optimizedAgentCount(text: string) {
  const lower = text.toLowerCase();
  const terms = [
    "compound",
    "molecule",
    "omics",
    "pathway",
    "literature",
    "safety",
    "clinical",
    "experiment",
    "drug",
    "therapeutic"
  ];
  const hits = terms.filter((term) => lower.includes(term)).length;
  const lengthBonus = text.length > 300 ? 1 : 0;
  return Math.max(3, Math.min(8, 4 + Math.floor(hits / 2) + lengthBonus));
}

export default function NewObjectivePage() {
  const [title, setTitle] = useState(presets[0].title);
  const [objective, setObjective] = useState(presets[0].objective);
  const [agentCount, setAgentCount] = useState(7);
  const [maxRuntimeMinutes, setMaxRuntimeMinutes] = useState(30);
  const [toolBudgetUsd, setToolBudgetUsd] = useState(10);
  const [evidenceStrictness, setEvidenceStrictness] = useState("strict");
  const [executionMode, setExecutionMode] = useState("background");
  const [agentFramework, setAgentFramework] = useState("langgraph");
  const [llmProvider, setLlmProvider] = useState("anthropic");
  const [llmModel, setLlmModel] = useState("claude-sonnet-4-6");
  const [llmApiKeyEnvVar, setLlmApiKeyEnvVar] = useState("ANTHROPIC_API_KEY");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [requireRealLlm, setRequireRealLlm] = useState(true);
  const [realDataEnabled, setRealDataEnabled] = useState(true);
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
    llm_base_url: llmBaseUrl,
    require_real_llm: requireRealLlm,
    real_data_enabled: realDataEnabled,
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

  function choosePreset(nextTitle: string, nextObjective: string) {
    setTitle(nextTitle);
    setObjective(nextObjective);
    setAgentCount(optimizedAgentCount(nextObjective));
  }

  function chooseProvider(provider: string) {
    setLlmProvider(provider);
    const defaults = providerDefaults[provider];
    setLlmModel(defaults.model);
    setLlmApiKeyEnvVar(defaults.key);
    setRequireRealLlm(provider !== "mock");
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
      <h1>Launch an auditable scientist run</h1>
      <p className="lede compact">
        Pick a provider, paste a biomedical question, choose agent count, and watch the run produce a trace,
        evidence table, critique, research board posts, and final report.
      </p>
      <section className="workflowBand compactBand">
        <div className="workflowStep"><BrainCircuit size={20} /><strong>Agents</strong><span>PI, finder, literature, tool, molecule, critic, publisher.</span></div>
        <div className="workflowStep"><DatabaseZap size={20} /><strong>Live tools</strong><span>NCBI, PubMed, PubChem, ToolUniverse/OpenTargets.</span></div>
        <div className="workflowStep"><ShieldCheck size={20} /><strong>Guardrails</strong><span>No efficacy or safety claims without direct evidence.</span></div>
        <div className="workflowStep"><KeyRound size={20} /><strong>Keys</strong><span>Use env vars from your local settings file.</span></div>
      </section>
      <div className="panel">
        <div className="sectionHeader">
          <div>
            <div className="kicker">Examples</div>
            <h2>Start from a known biomedical benchmark</h2>
          </div>
        </div>
        <div className="presetGrid">
          {presets.map((item) => (
            <button
              className="presetButton"
              type="button"
              key={item.title}
              onClick={() => choosePreset(item.title, item.objective)}
            >
              <Sparkles size={16} />
              <span>{item.title}</span>
            </button>
          ))}
        </div>
        <div className="divider" />
        <label className="label" htmlFor="title">Title</label>
        <input id="title" value={title} onChange={(event) => setTitle(event.target.value)} />
        <div style={{ height: 16 }} />
        <label className="label" htmlFor="objective">Scientific objective</label>
        <textarea id="objective" value={objective} onChange={(event) => setObjective(event.target.value)} />
        <div style={{ height: 16 }} />
        <div className="configGrid">
          <label>
            <span className="label">Agents</span>
            <div className="inlineControl">
              <input type="number" min={1} max={12} value={agentCount} onChange={(event) => setAgentCount(Number(event.target.value))} />
              <button
                className="secondaryButton"
                type="button"
                onClick={() => setAgentCount(optimizedAgentCount(objective))}
              >
                Optimized
              </button>
            </div>
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
            <select value={llmProvider} onChange={(event) => chooseProvider(event.target.value)}>
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
            <input value={llmApiKeyEnvVar} placeholder="ANTHROPIC_API_KEY" onChange={(event) => setLlmApiKeyEnvVar(event.target.value)} />
          </label>
          <label>
            <span className="label">Provider base URL</span>
            <input value={llmBaseUrl} placeholder="Only for local/OpenAI-compatible" onChange={(event) => setLlmBaseUrl(event.target.value)} />
          </label>
          <label>
            <span className="label">Execution</span>
            <select value={executionMode} onChange={(event) => setExecutionMode(event.target.value)}>
              <option value="background">Background</option>
              <option value="queued">Queued worker</option>
              <option value="inline">Run now</option>
            </select>
          </label>
          <label className="selectCard">
            <input
              type="checkbox"
              checked={realDataEnabled}
              onChange={(event) => setRealDataEnabled(event.target.checked)}
            />
            <span>
              <strong>Live public data</strong>
              <small>NCBI, PubMed, PubChem</small>
            </span>
          </label>
          <label className="selectCard">
            <input
              type="checkbox"
              checked={requireRealLlm}
              onChange={(event) => setRequireRealLlm(event.target.checked)}
            />
            <span>
              <strong>Strict real LLM</strong>
              <small>Fail fast if provider key is missing</small>
            </span>
          </label>
        </div>
        <p className="helpText">
          Put keys in `.env` at the repo root, for example `ANTHROPIC_API_KEY=...`,
          then restart the API. The web app references env var names only; it does not store raw keys.
        </p>
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
                    <small>{tool.provider} / {tool.status}</small>
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
