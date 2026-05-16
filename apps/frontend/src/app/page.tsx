import Link from "next/link";
import { Activity, ClipboardList, FlaskConical, ShieldCheck } from "lucide-react";

export default function Home() {
  return (
    <main className="page">
      <section className="hero">
        <div>
          <div className="kicker">ToolUniverse-native research loop</div>
          <h1>BioAutoScientist</h1>
          <p className="lede">
            A workbench for auditable biomedical hypothesis generation: agents plan, call tools,
            score evidence, critique claims, publish to a research board, and produce reproducible reports.
          </p>
          <Link href="/objectives/new" className="button">
            <FlaskConical size={18} /> Start ACVR1/FOP Demo
          </Link>
        </div>
        <div className="panel">
          <div className="kicker">Active prototype</div>
          <h2>ACVR1 / FOP case study</h2>
          <p className="muted">
            The first demo uses mock scientific tools with provenance-compatible outputs.
            Replace adapters with live ToolUniverse calls as each integration is validated.
          </p>
          <div className="grid">
            <span className="badge"><ClipboardList size={14} /> Board</span>
            <span className="badge"><Activity size={14} /> Trace</span>
            <span className="badge"><ShieldCheck size={14} /> Critique</span>
          </div>
        </div>
      </section>
    </main>
  );
}

