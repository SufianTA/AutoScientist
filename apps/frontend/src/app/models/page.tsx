"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { validateEnvVarName } from "@/lib/secrets";

type ModelTool = {
  id: string;
  name: string;
  description: string;
  provider: string;
  endpoint_url: string | null;
  api_key_env_var: string | null;
  tooluniverse_config: Record<string, unknown>;
  status: string;
};

export default function ModelsPage() {
  const [tools, setTools] = useState<ModelTool[]>([]);
  const [name, setName] = useState("custom_evidence_ranker");
  const [description, setDescription] = useState("Custom local or hosted model for ranking biomedical evidence.");
  const [provider, setProvider] = useState("local_http");
  const [endpointUrl, setEndpointUrl] = useState("http://localhost:9000/score");
  const [apiKeyEnvVar, setApiKeyEnvVar] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function loadTools() {
    const data = await apiGet<{ model_tools: ModelTool[] }>("/models");
    setTools(data.model_tools);
  }

  async function registerTool() {
    const envVarError = validateEnvVarName(apiKeyEnvVar);
    if (envVarError) {
      setError(envVarError);
      return;
    }
    setError(null);
    await apiPost("/models", {
      name,
      description,
      provider,
      endpoint_url: endpointUrl || null,
      api_key_env_var: apiKeyEnvVar || null
    });
    await loadTools();
  }

  useEffect(() => {
    loadTools();
  }, []);

  return (
    <main className="page">
      <div className="kicker">Model onboarding</div>
      <h1>Register custom model tools</h1>
      <section className="panel">
        <div className="configGrid">
          <label>
            <span className="label">Tool name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            <span className="label">Provider</span>
            <select value={provider} onChange={(event) => setProvider(event.target.value)}>
              <option value="mock">Mock local</option>
              <option value="local_http">Local HTTP</option>
              <option value="openai_compatible">OpenAI-compatible</option>
              <option value="huggingface">Hugging Face</option>
              <option value="custom_python">Custom Python</option>
            </select>
          </label>
          <label>
            <span className="label">Endpoint URL</span>
            <input value={endpointUrl} onChange={(event) => setEndpointUrl(event.target.value)} />
          </label>
          <label>
            <span className="label">API key env var</span>
            <input
              value={apiKeyEnvVar}
              placeholder="MODEL_API_KEY"
              onChange={(event) => {
                const nextValue = event.target.value.trim();
                const validation = validateEnvVarName(nextValue);
                if (validation) {
                  setError(validation);
                  setApiKeyEnvVar("");
                  return;
                }
                setError(null);
                setApiKeyEnvVar(nextValue);
              }}
            />
          </label>
        </div>
        <div style={{ height: 14 }} />
        <label>
          <span className="label">Description</span>
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <button type="button" onClick={registerTool}>Register model tool</button>
        {error && <p className="muted">{error}</p>}
      </section>
      <section className="panel" style={{ marginTop: 18 }}>
        <h2>Registered models</h2>
        <div className="grid">
          {tools.map((tool) => (
            <article className="card" key={tool.id}>
              <span className="badge">{tool.provider}</span>
              <h3>{tool.name}</h3>
              <p className="muted">{tool.description}</p>
              <pre>{JSON.stringify(tool.tooluniverse_config, null, 2)}</pre>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
