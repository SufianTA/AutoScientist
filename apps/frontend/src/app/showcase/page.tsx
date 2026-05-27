import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  ClipboardCheck,
  Dna,
  FlaskConical,
  GitBranch,
  Microscope,
  Network,
  ShieldCheck,
  Workflow
} from "lucide-react";

const kpis = [
  ["Run mode", "Full system"],
  ["Case compiler", "Enabled"],
  ["Evidence matrix", "Enabled"],
  ["Claim graph", "Enabled"],
  ["Gate scoring", "Enabled"],
  ["Replay", "Enabled"]
];

const taskRuns = [
  ["Mechanism dossier", "Compiled case profile", "mechanism branches", "ranked resistance strategy"],
  ["Bypass graph", "Claim/evidence graph", "uncertainty links", "revision triggers"],
  ["Cohort validation", "Evidence coverage matrix", "biomarker gates", "missing modality flags"],
  ["Experiment plan", "Experiment gate scoring", "failure criteria", "decision-impact ranking"]
];

const capabilityFlow = [
  { name: "Evidence retrieval", progress: 95, detail: "PubMed, OpenTargets, ToolUniverse, clinical and safety context" },
  { name: "Mechanism graph", progress: 88, detail: "Genes, variants, fusions, pathways, cell states, and confidence updates" },
  { name: "Contradiction handling", progress: 74, detail: "Weak branches kept gated instead of collapsed into a single answer" },
  { name: "Experiment planning", progress: 82, detail: "Controls, failure gates, assays, and confidence-update criteria" }
];

const timeline = [
  ["1", "Compile case", "entities, branches, assays"],
  ["2", "Collect evidence", "public tools and provenance"],
  ["3", "Map claims", "support, gaps, contradictions"],
  ["4", "Score gates", "decision impact and failure criteria"],
  ["5", "Package review", "report, replay, trace"]
];

const insights = [
  {
    icon: Network,
    title: "Evidence orchestration",
    value: "Traceable",
    text: "The run links public evidence, target context, literature, and tool traces."
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
    value: "Replayable",
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
            ToolUniverse/OpenTargets, memory, replay, policy control, claim graphs, and experiment planning.
          </p>
          <div className="poweredBy">
            <Network size={16} />
            Powered by ToolUniverse and OpenTargets evidence retrieval
          </div>
          <div className="heroActions">
            <a href="#case" className="button"><Microscope size={18} /> Case insights</a>
            <a href="#evidence" className="secondaryButton buttonLike"><ClipboardCheck size={18} /> Capability trace</a>
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
            <strong>C797S / clone phasing</strong>
          </div>
          <div className="signalLane right">
            <span>Bypass</span>
            <strong>MET / ERBB2 / fusions</strong>
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
            <span>EGFR C797S, EGFR amplification, MET amplification, ERBB2 amplification, and emergent fusion bypass.</span>
          </article>
          <article>
            <Workflow size={22} />
            <strong>Lower-certainty branches</strong>
            <span>AXL/EMT plasticity, CNS sanctuary, pharmacologic exposure, and lineage transformation kept as gated hypotheses.</span>
          </article>
          <article>
            <FlaskConical size={22} />
            <strong>Next work</strong>
            <span>Validate ctDNA clone structure, paired-biopsy co-occurrence, safety, and matched combination experiments.</span>
          </article>
        </div>
      </section>

      <section id="evidence" className="splitInsight">
        <div className="sectionIntro">
          <div className="kicker">Capability trace</div>
          <h2>The page tells a single case story through the systems the run exercises.</h2>
        </div>
        <div className="capabilityBars">
          {capabilityFlow.map(({ name, progress, detail: note }) => (
            <div className="barRow" key={name}>
              <div>
                <strong>{name}</strong>
                <span>{note}</span>
              </div>
              <div className="barTrack">
                <span style={{ width: `${progress}%` }} />
              </div>
              <b><Dna size={18} /></b>
            </div>
          ))}
        </div>
      </section>

      <section className="taskStrip">
        <div className="sectionIntro">
          <div className="kicker">Trace packets</div>
          <h2>Four full-system artifacts the run is expected to produce.</h2>
        </div>
        <div className="taskStripGrid">
          {taskRuns.map(([task, run, calls, critic]) => (
            <article key={run}>
              <GitBranch size={18} />
              <h3>{task}</h3>
              <span>{run}</span>
              <strong>{calls} / {critic}</strong>
            </article>
          ))}
        </div>
      </section>

      <section id="runs" className="runStory">
        <div className="sectionIntro">
          <div className="kicker">System flow</div>
          <h2>From case intake to an auditable research package.</h2>
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
