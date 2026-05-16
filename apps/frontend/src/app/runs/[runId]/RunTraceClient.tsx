"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BrainCircuit, Clock, DatabaseZap, FileText, ShieldCheck, Zap } from "lucide-react";
import { apiGet } from "@/lib/api";

type Run = {
  status: string;
  current_state: string;
  final_confidence: number | null;
  estimated_cost_usd: number;
  agent_count: number;
  max_runtime_minutes: number;
  run_config: Record<string, unknown>;
};

type Trace = {
  steps: Array<{ id: string; agent_name: string; state_name: string; output: Record<string, unknown> }>;
  tool_calls: Array<{ id: string; tool_name: string; status: string; latency_ms: number }>;
};

const activeStatuses = new Set(["queued", "running", "dispatching"]);

export function RunTraceClient({
  runId,
  initialRun,
  initialTrace
}: {
  runId: string;
  initialRun: Run;
  initialTrace: Trace;
}) {
  const [run, setRun] = useState(initialRun);
  const [trace, setTrace] = useState(initialTrace);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const latestStep = trace.steps[trace.steps.length - 1];
  const llmCalls = latestStep?.output?.llm_calls as Array<Record<string, unknown>> | undefined;
  const toolSuccess = trace.tool_calls.filter((call) => call.status === "success").length;
  const toolPartial = trace.tool_calls.filter((call) => call.status === "partial").length;

  useEffect(() => {
    if (!activeStatuses.has(run.status)) return;
    const timer = window.setInterval(async () => {
      const [nextRun, nextTrace] = await Promise.all([
        apiGet<Run>(`/runs/${runId}`),
        apiGet<Trace>(`/runs/${runId}/trace`)
      ]);
      setRun(nextRun);
      setTrace(nextTrace);
      setLastUpdated(new Date());
    }, 1500);
    return () => window.clearInterval(timer);
  }, [run.status, runId]);

  return (
    <main className="page">
      <div className="kicker">Live run trace</div>
      <h1>{run.current_state}</h1>
      <div className="metricGrid">
        <div className="metric"><Zap size={18} /><span>Status</span><strong>{run.status}</strong></div>
        <div className="metric"><BrainCircuit size={18} /><span>Agents</span><strong>{run.agent_count}</strong></div>
        <div className="metric"><DatabaseZap size={18} /><span>Tools</span><strong>{toolSuccess} success / {toolPartial} partial</strong></div>
        <div className="metric"><ShieldCheck size={18} /><span>Confidence</span><strong>{run.final_confidence ?? "pending"}</strong></div>
      </div>
      <div className="actions">
        <span className={`badge status-${run.status}`}>
          {activeStatuses.has(run.status) ? "Auto-refreshing" : "Completed snapshot"}
        </span>
        <span className="muted"><Clock size={14} /> Last updated {lastUpdated.toLocaleTimeString()}</span>
      </div>
      <div style={{ height: 18 }} />
      {llmCalls && llmCalls.length > 0 && (
        <>
          <section className="panel">
            <div className="sectionHeader">
              <div>
                <div className="kicker">LLM activity</div>
                <h2>{llmCalls.length} recorded model calls</h2>
              </div>
            </div>
            <table className="table">
              <thead><tr><th>Agent</th><th>Task</th><th>Provider</th><th>Latency</th></tr></thead>
              <tbody>
                {llmCalls.slice(-8).map((call, index) => (
                  <tr key={`${call.task}-${index}`}>
                    <td>{String(call.agent_name)}</td>
                    <td>{String(call.task)}</td>
                    <td>{String(call.provider)} / {String(call.model)}</td>
                    <td>{String(call.latency_ms)} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <div style={{ height: 18 }} />
        </>
      )}
      <div className="grid">
        <section className="panel">
          <h2>Agent states</h2>
          {trace.steps.map((step) => (
            <div className="card" key={step.id} style={{ marginBottom: 12 }}>
              <span className="badge">{step.agent_name}</span>
              <h3>{step.state_name}</h3>
              <pre>{JSON.stringify(step.output, null, 2)}</pre>
            </div>
          ))}
        </section>
        <section className="panel">
          <h2>Tool calls</h2>
          <table className="table">
            <thead>
              <tr><th>Tool</th><th>Status</th><th>Latency</th></tr>
            </thead>
            <tbody>
              {trace.tool_calls.map((call) => (
                <tr key={call.id}>
                  <td>{call.tool_name}</td>
                  <td><span className={`badge status-${call.status}`}>{call.status}</span></td>
                  <td>{call.latency_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ height: 16 }} />
          <Link className="button" href={`/reports/${runId}`}><FileText size={18} /> Open report</Link>
        </section>
      </div>
    </main>
  );
}
