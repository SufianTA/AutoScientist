# Draft Email To Marinka

Subject: AutoScientist update: SciState Graph, public-data benchmarks, and SciFlow Policy model

Hi Marinka,

I wanted to share a substantial new version of AutoScientist that I built and tested today. The direction has shifted from "another autonomous research agent" toward a persistent scientific execution system: memory, provenance, real tool execution, replayable traces, and a learned workflow-control layer.

The two main new components are **SciState Graph** and **SciFlow Policy**. SciState Graph is the persistent scientific memory/provenance layer that stores hypotheses, evidence, entities, experiments, tool traces, failed or partial paths, confidence signals, and causal/evidence relationships across runs. SciFlow Policy is a PyTorch controller model trained on AutoScientist execution traces to predict the next scientific action, tool, or workflow state; it is not meant to replace a foundation model, but to make the scientific runtime operate more coherently around foundation models, biomedical tools, and long-running memory.

I trained and packaged SciFlow Policy on a RunPod machine with a single NVIDIA H100 PCIe GPU with 80 GB VRAM. After the latest harvest, the model trained on 2,257 trace examples and achieved holdout top-1 accuracy of 0.9205, top-3 accuracy of 1.0, and MRR of 0.9603. I am treating these as prototype controller metrics, not final biomedical-discovery claims, because the next benchmark needs more live frontier/open-source model runs and expert-scored biomedical outputs.

I also connected public biomedical tools plus ToolUniverse/OpenTargets paths where available. I ran a 50-task benchmark harvest; all 50 runs completed, exercising public biomedical tools, local board/replay logging, SciState memory capture, and SciFlow training traces. The exported SciState Graph now contains 1,106 nodes, 2,795 edges, 69 hypotheses, 615 entities, and 207 proposed experiments.

Resources you can inspect:

- Artifact index: [artifacts/2026-05-20-autoscientist-runtime/README.md](../artifacts/2026-05-20-autoscientist-runtime/README.md)
- Full sanitized output archive: [autoscientist_all_run_outputs_1779257902.tar.gz](../artifacts/2026-05-20-autoscientist-runtime/autoscientist_all_run_outputs_1779257902.tar.gz)
- Final SciFlow Policy package: [sciflow_policy_package_20260520065055.zip](../artifacts/2026-05-20-autoscientist-runtime/sciflow_policy_package_20260520065055.zip)
- SciFlow Policy manifest: [sciflow_policy_manifest_20260520065055.json](../artifacts/2026-05-20-autoscientist-runtime/sciflow_policy_manifest_20260520065055.json)
- 50-task benchmark summary: [fifty_task_harvest_1779257902.md](../artifacts/2026-05-20-autoscientist-runtime/fifty_task_harvest_1779257902.md)
- SciState Graph report: [scistate_graph_1779259857.md](../artifacts/2026-05-20-autoscientist-runtime/scistate_graph_1779259857.md)
- Live Anthropic smoke run: [live_anthropic_smoke_run_5e48621eb8f0.json](../artifacts/2026-05-20-autoscientist-runtime/live_anthropic_smoke_run_5e48621eb8f0.json)

The next steps I think matter most are: run a stronger benchmark suite with live frontier and open-source reasoning models, add expert or rubric-based biomedical scoring, compare against no-memory, no-public-tools, and no-policy ablations, expand ToolUniverse/OpenTargets coverage, and train SciFlow Policy on higher-quality traces to test whether it improves real autonomous-science workflows.

I would really value your feedback on whether this direction is scientifically interesting, what benchmark tasks would make it credible, and what would make the system useful to your group rather than just impressive as infrastructure.

Best,

[Your Name]
