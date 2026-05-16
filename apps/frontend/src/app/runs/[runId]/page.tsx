import Link from "next/link";
import { apiGet } from "@/lib/api";

type Trace = {
  steps: Array<{ id: string; agent_name: string; state_name: string; output: unknown }>;
  tool_calls: Array<{ id: string; tool_name: string; status: string; latency_ms: number }>;
};

export default async function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const run = await apiGet<{
    status: string;
    current_state: string;
    final_confidence: number | null;
    estimated_cost_usd: number;
    agent_count: number;
    max_runtime_minutes: number;
    run_config: Record<string, unknown>;
  }>(`/runs/${runId}`);
  const trace = await apiGet<Trace>(`/runs/${runId}/trace`);

  return (
    <main className="page">
      <div className="kicker">Live run trace</div>
      <h1>{run.current_state}</h1>
      <p className="muted">
        Status: {run.status} / Confidence: {run.final_confidence ?? "pending"} /
        Agents: {run.agent_count} / Runtime: {run.max_runtime_minutes} min /
        Estimate: {run.estimated_cost_usd} resource units
      </p>
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
