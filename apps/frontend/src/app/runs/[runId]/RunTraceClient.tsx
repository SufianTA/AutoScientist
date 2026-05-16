"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
  steps: Array<{ id: string; agent_name: string; state_name: string; output: unknown }>;
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
      <p className="muted">
        Status: {run.status} / Confidence: {run.final_confidence ?? "pending"} /
        Agents: {run.agent_count} / Runtime: {run.max_runtime_minutes} min /
        Estimate: {run.estimated_cost_usd} resource units
      </p>
      <div className="actions">
        <span className="badge">
          {activeStatuses.has(run.status) ? "Auto-refreshing" : "Completed snapshot"}
        </span>
        <span className="muted">Last updated {lastUpdated.toLocaleTimeString()}</span>
      </div>
      <div style={{ height: 18 }} />
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
                  <td>{call.status}</td>
                  <td>{call.latency_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ height: 16 }} />
          <Link className="button" href={`/reports/${runId}`}>Open report</Link>
        </section>
      </div>
    </main>
  );
}
