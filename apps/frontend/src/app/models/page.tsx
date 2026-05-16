"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

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

  async function loadTools() {
    const data = await apiGet<{ model_tools: ModelTool[] }>("/models");
    setTools(data.model_tools);
  }

  async function registerTool() {
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
            <input value={apiKeyEnvVar} onChange={(event) => setApiKeyEnvVar(event.target.value)} />
          </label>
        </div>
        <div style={{ height: 14 }} />
        <label>
          <span className="label">Description</span>
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <button type="button" onClick={registerTool}>Register model tool</button>
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
