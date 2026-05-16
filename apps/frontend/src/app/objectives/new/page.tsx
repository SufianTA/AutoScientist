"use client";

import { useState } from "react";
import { Play } from "lucide-react";
import { apiPost } from "@/lib/api";

const preset = "Generate a therapeutic hypothesis for ACVR1-driven Fibrodysplasia Ossificans Progressiva and identify candidate small molecules or intervention strategies. Use ToolUniverse tools where available, collect evidence, critique the hypothesis, and propose validation experiments.";

export default function NewObjectivePage() {
  const [title, setTitle] = useState("ACVR1/FOP therapeutic hypothesis generation");
  const [objective, setObjective] = useState(preset);
  const [busy, setBusy] = useState(false);

  async function startRun() {
    setBusy(true);
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
    const run = await apiPost<{ id: string }>("/runs", { objective_id: created.id, execute_demo: true });
    window.location.href = `/runs/${run.id}`;
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
        <button onClick={startRun} disabled={busy}>
          <Play size={18} /> {busy ? "Running" : "Start demo run"}
        </button>
      </div>
    </main>
  );
}

