import { apiGet } from "@/lib/api";
import { RunTraceClient } from "./RunTraceClient";

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

  return <RunTraceClient runId={runId} initialRun={run} initialTrace={trace} />;
}
