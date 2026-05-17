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
  steps: Array<{
    id: string;
    agent_name: string;
    state_name: string;
    output: Record<string, unknown>;
    completed_at?: string;
    error?: string | null;
  }>;
  tool_calls: Array<{ id: string; tool_name: string; status: string; latency_ms: number }>;
};

const activeStatuses = new Set(["queued", "running", "dispatching"]);
const liveEventStates = new Set([
  "TOOL_CALL_STARTED",
  "TOOL_CALL_COMPLETED",
  "LLM_CALL_STARTED",
  "LLM_CALL_COMPLETED",
  "LLM_CALL_FAILED",
  "AGENT_PANEL_STARTED",
  "AGENT_POSITION_COMPLETED"
]);

function summarizeStep(step: Trace["steps"][number]) {
  const output = step.output ?? {};
  if (step.error) return step.error;
  if (step.state_name === "TOOL_CALL_STARTED") return `Started ${String(output.tool_name ?? "tool call")}`;
  if (step.state_name === "TOOL_CALL_COMPLETED") {
    return `${String(output.tool_name ?? "tool call")} finished with ${String(output.status ?? "unknown")} in ${String(output.latency_ms ?? "n/a")} ms`;
  }
  if (step.state_name === "LLM_CALL_STARTED") return `Started ${String(output.task ?? "LLM task")}`;
  if (step.state_name === "LLM_CALL_COMPLETED") return `${String(output.task ?? "LLM task")} completed in ${String(output.latency_ms ?? "n/a")} ms`;
  if (step.state_name === "AGENT_PANEL_STARTED") {
    const roles = Array.isArray(output.roles) ? output.roles.length : 0;
    return `Launched ${roles} debate agents with ${String(output.parallel_workers ?? "n/a")} parallel workers`;
  }
  if (step.state_name === "AGENT_POSITION_COMPLETED") {
    return `${String(output.vote ?? "review")} vote: ${String(output.position ?? "").slice(0, 180)}`;
  }
  if (Array.isArray(output.plan)) return `${output.plan.length} plan steps generated`;
  if (Array.isArray(output.selected_tools)) return `${output.selected_tools.length} tools selected`;
  if (typeof output.tool_output_count === "number") return `${output.tool_output_count} tool calls completed`;
  if (Array.isArray(output.scored_evidence)) return `${output.scored_evidence.length} evidence items scored`;
  if (output.hypothesis_card && typeof output.hypothesis_card === "object") {
    return String((output.hypothesis_card as Record<string, unknown>).title ?? "Hypothesis generated");
  }
  if (output.report && typeof output.report === "object") {
    return `Report confidence ${(output.report as Record<string, unknown>).confidence ?? "pending"}`;
  }
  return "Completed";
}

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
  const liveEvents = trace.steps.filter((step) => liveEventStates.has(step.state_name));
  const majorSteps = trace.steps.filter((step) => !liveEventStates.has(step.state_name));
  const agentGroups = trace.steps.reduce<Record<string, Trace["steps"]>>((groups, step) => {
    groups[step.agent_name] = [...(groups[step.agent_name] ?? []), step];
    return groups;
  }, {});

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
      <div className="eventGrid">
        <section className="panel">
          <div className="sectionHeader">
            <div>
              <div className="kicker">Timeline</div>
              <h2>Agent and tool activity</h2>
            </div>
            <span className="badge">{liveEvents.length} live events</span>
          </div>
          <div className="timeline">
            {[...trace.steps].reverse().slice(0, 36).map((step) => (
              <div className="eventRow" key={step.id}>
                <div className="eventMeta">
                  <span className={`badge status-${step.error ? "failed" : step.state_name.includes("COMPLETED") ? "success" : "running"}`}>
                    {step.state_name.replaceAll("_", " ")}
                  </span>
                  <strong>{step.agent_name}</strong>
                  <span>{step.completed_at ? new Date(step.completed_at).toLocaleTimeString() : "pending"}</span>
                </div>
                <div className="eventBody">
                  <h3>{summarizeStep(step)}</h3>
                  {step.state_name === "LLM_CALL_COMPLETED" && typeof step.output.response_excerpt === "string" && (
                    <p>{String(step.output.response_excerpt).slice(0, 240)}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
        <aside className="panel">
          <div className="sectionHeader">
            <div>
              <div className="kicker">Parallel lanes</div>
              <h2>Agent lanes</h2>
            </div>
          </div>
          <div className="agentLaneGrid">
            {Object.entries(agentGroups).map(([agent, steps]) => (
              <div className="agentLane" key={agent}>
                <div className="agentLaneHeader">
                  <strong>{agent}</strong>
                  <span className="badge">{steps.length}</span>
                </div>
                <div className="miniEvents">
                  {steps.slice(-8).map((step) => (
                    <span className="miniEvent" key={step.id}>{step.state_name.replaceAll("_", " ")}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="divider" />
          <h2>Tool calls</h2>
          <table className="table">
            <thead>
              <tr><th>Tool</th><th>Status</th><th>Latency</th></tr>
            </thead>
            <tbody>
              {trace.tool_calls.slice(-12).map((call) => (
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
        </aside>
      </div>
      <div style={{ height: 18 }} />
      <section className="panel">
        <details>
          <summary><strong>Raw major state outputs</strong> <span className="muted">for audit and debugging</span></summary>
          <div style={{ height: 14 }} />
          {majorSteps.map((step) => (
            <div className="card" key={step.id} style={{ marginBottom: 12 }}>
              <span className="badge">{step.agent_name}</span>
              <h3>{step.state_name}</h3>
              <pre>{JSON.stringify(step.output, null, 2)}</pre>
            </div>
          ))}
        </details>
      </section>
    </main>
  );
}
