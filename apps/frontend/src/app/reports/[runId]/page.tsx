import { API_BASE_URL, apiGet } from "@/lib/api";

type Report = {
  hypothesis: { title: string; text: string; confidence: number | null; status: string | null };
  evidence: Array<{ source: string; text: string; support_label: string; support_score: number }>;
  guardrails: string[];
};

export default async function ReportPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const report = await apiGet<Report>(`/reports/${runId}`);
  return (
    <main className="page">
      <div className="kicker">Final report</div>
      <h1>{report.hypothesis.title}</h1>
      <p className="lede">{report.hypothesis.text}</p>
      <p><span className="badge">confidence {report.hypothesis.confidence ?? "n/a"}</span></p>
      <div className="actions">
        <a className="button" href={`${API_BASE_URL}/reports/${runId}/download?format=markdown`}>Download Markdown</a>
        <a className="button secondaryButton" href={`${API_BASE_URL}/reports/${runId}/download?format=json`}>Download JSON</a>
      </div>
      <div style={{ height: 18 }} />
      <section className="panel">
        <h2>Evidence</h2>
        <table className="table">
          <thead>
            <tr><th>Source</th><th>Evidence</th><th>Score</th></tr>
          </thead>
          <tbody>
            {report.evidence.map((item) => (
              <tr key={`${item.source}-${item.text}`}>
                <td>{item.source}</td>
                <td>{item.text}</td>
                <td>{item.support_label} / {item.support_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel" style={{ marginTop: 18 }}>
        <h2>Guardrails</h2>
        <ul>
          {report.guardrails.map((guardrail) => <li key={guardrail}>{guardrail}</li>)}
        </ul>
      </section>
    </main>
  );
}
