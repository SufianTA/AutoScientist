import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  DatabaseZap,
  FlaskConical,
  GitBranch,
  Microscope,
  Network,
  ShieldCheck,
  Workflow
} from "lucide-react";

const kpis = [
  ["Status", "Completed"],
  ["Agent steps", "593"],
  ["Tool calls", "251"],
  ["Evidence", "140"],
  ["Full score", "100"],
  ["BioTruth mean", "88.0"]
];

const taskRuns = [
  ["Mechanism dossier", "run_ab460d57712c", "62 calls", "93.0 critic"],
  ["Bypass graph", "run_7b4f4c405a93", "65 calls", "92.4 critic"],
  ["Cohort validation", "run_f8a1c9d37675", "62 calls", "94.4 critic"],
  ["Experiment plan", "run_a2672e1f7e40", "62 calls", "91.0 critic"]
];

const ablations = [
  { name: "Full system", score: 100, evidence: "35 evidence/run", note: "All integrations on" },
  { name: "No memory", score: 95, evidence: "34.5 evidence/run", note: "Replay removed" },
  { name: "No SciFlow", score: 95, evidence: "33.75 evidence/run", note: "Controller removed" },
  { name: "Plain LLM", score: 54, evidence: "2 evidence/run", note: "No tools" },
  { name: "No public tools", score: 54, evidence: "2 evidence/run", note: "Grounding removed" }
];

const timeline = [
  ["May 23", "100-task campaign", "100 artifacts"],
  ["May 24", "20-case salvage", "26 complete"],
  ["May 24", "Strict canary", "16/16 complete"],
  ["May 25", "Value rerun", "20 artifacts"],
  ["May 26", "EGFR deep case", "251 calls"]
];

const insights = [
  {
    icon: Network,
    title: "Public tools mattered",
    value: "+46 quality",
    text: "Removing public grounding dropped scientific quality from 100 to 54."
  },
  {
    icon: ShieldCheck,
    title: "Claims stayed bounded",
    value: "0 clinical claims",
    text: "The output framed hypotheses and experiments, not treatment advice."
  },
  {
    icon: BrainCircuit,
    title: "Memory became an artifact",
    value: "7,544 nodes",
    text: "SciState retained hypotheses, entities, tools, and experiments."
  }
];

export default function ShowcasePage() {
  return (
    <main className="showcaseV2">
      <section className="showcaseV2Hero">
        <div className="heroCopy">
          <div className="kicker">Deep cancer-resistance case</div>
          <h1>EGFR osimertinib resistance, traced by agents.</h1>
          <p>
            AutoScientist ran a strict real oncology workflow: live public evidence,
            ToolUniverse/OpenTargets, memory, replay, policy control, scoring, and ablations.
          </p>
          <div className="poweredBy">
            <Network size={16} />
            Powered by ToolUniverse and OpenTargets evidence retrieval
          </div>
          <div className="heroActions">
            <a href="#case" className="button"><Microscope size={18} /> Case insights</a>
            <a href="#evidence" className="secondaryButton buttonLike"><DatabaseZap size={18} /> Evidence lift</a>
          </div>
        </div>

        <div className="signalBoard" aria-label="EGFR resistance signal board">
        <div className="signalHeader">
          <span>Mechanism map</span>
          <strong>Powered by ToolUniverse</strong>
        </div>
          <div className="signalCore">EGFR-mutant NSCLC<br /><strong>osimertinib resistance</strong></div>
          <div className="signalLane left">
            <span>On-target</span>
            <strong>C797S / EGFR amp</strong>
          </div>
          <div className="signalLane right">
            <span>Bypass</span>
            <strong>MET / ERBB2</strong>
          </div>
          <div className="signalLane lowerLeft">
            <span>State change</span>
            <strong>AXL / EMT</strong>
          </div>
          <div className="signalLane lowerRight">
            <span>Transformation</span>
            <strong>SCLC / squamous</strong>
          </div>
        </div>
      </section>

      <section className="kpiDock" aria-label="Run metrics">
        {kpis.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </section>

      <section id="case" className="insightDeck">
        <div className="sectionIntro">
          <div className="kicker">Case result</div>
          <h2>The useful output was not a cure claim. It was a ranked resistance strategy.</h2>
        </div>
        <div className="findingRail">
          <article>
            <CheckCircle2 size={22} />
            <strong>Strong branches</strong>
            <span>EGFR C797S, EGFR amplification, MET amplification, ERBB2 amplification.</span>
          </article>
          <article>
            <Workflow size={22} />
            <strong>Lower-certainty branches</strong>
            <span>AXL/EMT state plasticity and lineage transformation kept as gated hypotheses.</span>
          </article>
          <article>
            <FlaskConical size={22} />
            <strong>Next work</strong>
            <span>Validate prevalence, co-occurrence, safety, and matched combination experiments.</span>
          </article>
        </div>
      </section>

      <section id="evidence" className="splitInsight">
        <div className="sectionIntro">
          <div className="kicker">Evidence lift</div>
          <h2>Grounded runs beat ungrounded baselines where it matters.</h2>
        </div>
        <div className="ablationBars">
          {ablations.map(({ name, score, evidence, note }) => (
            <div className="barRow" key={name}>
              <div>
                <strong>{name}</strong>
                <span>{note} · {evidence}</span>
              </div>
              <div className="barTrack">
                <span style={{ width: `${score}%` }} />
              </div>
              <b>{score}</b>
            </div>
          ))}
        </div>
      </section>

      <section className="taskStrip">
        <div className="sectionIntro">
          <div className="kicker">Trace packets</div>
          <h2>Four completed full-system artifacts.</h2>
        </div>
        <div className="taskStripGrid">
          {taskRuns.map(([task, run, calls, critic]) => (
            <article key={run}>
              <GitBranch size={18} />
              <h3>{task}</h3>
              <span>{run}</span>
              <strong>{calls} · {critic}</strong>
            </article>
          ))}
        </div>
      </section>

      <section id="runs" className="runStory">
        <div className="sectionIntro">
          <div className="kicker">Run history</div>
          <h2>From infrastructure proof to focused cancer case.</h2>
        </div>
        <div className="runTimeline">
          {timeline.map(([date, title, metric]) => (
            <article key={title}>
              <span>{date}</span>
              <strong>{title}</strong>
              <em>{metric}</em>
            </article>
          ))}
        </div>
      </section>

      <section className="valueCards">
        {insights.map((item) => {
          const Icon = item.icon;
          return (
            <article key={item.title}>
              <Icon size={24} />
              <span>{item.title}</span>
              <strong>{item.value}</strong>
              <p>{item.text}</p>
            </article>
          );
        })}
      </section>

      <section className="showcaseCta">
        <div>
          <div className="kicker">Boundary</div>
          <h2>Auditable hypothesis workflow. Not clinical guidance.</h2>
          <p className="muted">Powered by ToolUniverse/OpenTargets, live public biomedical tools, and replayable agent traces.</p>
        </div>
        <Link href="/runs" className="secondaryButton buttonLike">
          <Activity size={18} /> Runtime queue <ArrowUpRight size={16} />
        </Link>
      </section>
    </main>
  );
}
