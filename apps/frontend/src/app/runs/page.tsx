import Link from "next/link";
import { apiGet } from "@/lib/api";

type Run = {
  id: string;
  status: string;
  current_state: string;
  estimated_cost_usd: number;
  agent_count: number;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export default async function RunsPage() {
  const data = await apiGet<{ runs: Run[] }>("/runs");
  return (
    <main className="page">
      <div className="kicker">Run queue</div>
      <h1>Submitted research runs</h1>
      <table className="table">
        <thead>
          <tr><th>Run</th><th>Status</th><th>State</th><th>Agents</th><th>Estimate</th></tr>
        </thead>
        <tbody>
          {data.runs.map((run) => (
            <tr key={run.id}>
              <td><Link href={`/runs/${run.id}`}>{run.id}</Link></td>
              <td><span className="badge">{run.status}</span></td>
              <td>{run.current_state}</td>
              <td>{run.agent_count}</td>
              <td>{run.estimated_cost_usd} units</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
