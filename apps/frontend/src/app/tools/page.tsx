import { apiGet } from "@/lib/api";

type Tool = {
  name: string;
  description: string;
  source: string;
  status: string;
  notes: string;
};

export default async function ToolsPage() {
  const data = await apiGet<{ tools: Tool[] }>("/tools/inventory");
  return (
    <main className="page">
      <div className="kicker">Tool inventory</div>
      <h1>ToolUniverse and custom tools</h1>
      <table className="table">
        <thead>
          <tr><th>Name</th><th>Description</th><th>Source</th><th>Status</th></tr>
        </thead>
        <tbody>
          {data.tools.map((tool) => (
            <tr key={tool.name}>
              <td>{tool.name}</td>
              <td>{tool.description}<br /><span className="muted">{tool.notes}</span></td>
              <td>{tool.source}</td>
              <td><span className="badge">{tool.status}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}

