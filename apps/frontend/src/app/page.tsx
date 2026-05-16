import Link from "next/link";
import {
  Activity,
  BrainCircuit,
  ClipboardList,
  FlaskConical,
  KeyRound,
  Network,
  ShieldCheck,
  Terminal
} from "lucide-react";

export default function Home() {
  return (
    <main className="page">
      <section className="hero productHero">
        <div>
          <div className="kicker">Local autonomous biomedical research workbench</div>
          <h1>BioAutoScientist</h1>
          <p className="lede">
            Ask a biomedical question and watch specialist agents plan, call live public tools,
            use ToolUniverse/OpenTargets, score evidence with your chosen LLM, critique claims,
            and publish a reproducible report.
          </p>
          <div className="actions">
            <Link href="/objectives/new" className="button">
              <FlaskConical size={18} /> Launch workbench
            </Link>
            <Link href="/runs" className="secondaryButton buttonLike">
              <Activity size={18} /> View runs
            </Link>
          </div>
        </div>
        <div className="panel statusPanel">
          <div className="kicker">Setup path</div>
          <h2>Clone, set keys, run locally</h2>
          <p className="muted">
            Works with OpenAI, Anthropic, Gemini, OpenAI-compatible endpoints, or local HTTP models.
            Strict mode refuses mock LLMs and records every agent step, LLM call, tool call, and citation.
          </p>
          <div className="badgeGrid">
            <span className="badge"><KeyRound size={14} /> Provider keys</span>
            <span className="badge"><Terminal size={14} /> CLI stream</span>
            <span className="badge"><Network size={14} /> ToolUniverse</span>
            <span className="badge"><ShieldCheck size={14} /> Critic agent</span>
          </div>
        </div>
      </section>
      <section className="workflowBand">
        <div className="workflowStep">
          <BrainCircuit size={20} />
          <strong>Plan</strong>
          <span>PI agent extracts entities and builds an evidence plan.</span>
        </div>
        <div className="workflowStep">
          <Network size={20} />
          <strong>Call tools</strong>
          <span>Specialists query NCBI, PubMed, PubChem, and ToolUniverse.</span>
        </div>
        <div className="workflowStep">
          <ShieldCheck size={20} />
          <strong>Critique</strong>
          <span>Claims are scored, challenged, and bounded by guardrails.</span>
        </div>
        <div className="workflowStep">
          <ClipboardList size={20} />
          <strong>Publish</strong>
          <span>Reports, board posts, and provenance JSON are generated.</span>
        </div>
      </section>
    </main>
  );
}
