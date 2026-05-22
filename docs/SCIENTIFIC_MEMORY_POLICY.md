# AutoScientist Scientific Memory and Workflow Policy

AutoScientist is strongest when it is evaluated as persistent scientific infrastructure rather than as a one-shot chatbot. The core artifact is the loop:

1. run an evidence-grounded scientific workflow,
2. persist entities, hypotheses, causal links, experiments, tool traces, and replay bundles,
3. train the workflow policy model from those traces,
4. export a package with model, model card, benchmark report, replays, and scientific state graph.

## What To Show

- `GET /memory/summary`: counts of entities, hypotheses, experiments, replay bundles, tool benchmarks, and policy examples.
- `GET /memory/state-graph`: graph-shaped scientific state across all runs.
- `GET /memory/runs/{run_id}/state-graph`: graph for one run.
- `GET /memory/runs/{run_id}/replay`: replayable trace bundle.
- `POST /memory/policy/train`: train the Scientific Workflow Policy model.
- `POST /memory/policy/train-neural`: train the PyTorch neural workflow policy.
- `POST /memory/policy/predict`: rank next scientific actions for a state.

## Local Benchmark

```bash
python tools/run_benchmark_suite.py \
  --disable-qworld \
  --llm-provider mock \
  --output-dir outputs/benchmarks \
  --policy-artifact-dir outputs/models
```

This produces deterministic artifacts quickly and is useful for regression testing.

## Live Benchmark

```bash
DATABASE_URL=sqlite:////workspace/AutoScientist/bio_auto_scientist.sqlite3 \
/opt/autosci-venv/bin/python tools/run_benchmark_suite.py \
  --require-real-llm \
  --disable-qworld \
  --agent-count 2 \
  --max-runtime-minutes 5 \
  --tool-budget-usd 1 \
  --llm-provider anthropic \
  --llm-model claude-sonnet-4-6 \
  --llm-api-key-env-var ANTHROPIC_API_KEY \
  --llm-max-tokens 128 \
  --output-dir /workspace/AutoScientist/outputs/benchmarks \
  --policy-artifact-dir /workspace/AutoScientist/outputs/models
```

Use Qworld in smaller targeted runs until provider rate limits are raised:

```bash
python tools/run_integration_benchmark.py \
  --objective "Prioritize therapeutic target hypotheses for rheumatoid arthritis in CD4+ T cells using public biomedical evidence." \
  --require-real-llm \
  --llm-provider anthropic \
  --llm-api-key-env-var ANTHROPIC_API_KEY
```

## Package For Review

```bash
python tools/train_neural_workflow_policy.py \
  --artifact-dir outputs/models \
  --epochs 80 \
  --hidden-dim 128

python tools/package_policy_model.py \
  --output-dir outputs/packages \
  --replay-limit 10 \
  --graph-limit 500
```

The package contains:

- `model.json`: portable transparent workflow-policy model, or `neural_model/manifest.json` plus `neural_model/model.pt` for the PyTorch model.
- `MODEL_CARD.md`: intended use, limitations, train/holdout metrics.
- `manifest.json`: memory summary, tool benchmarks, replay index.
- `state_graph.json`: derived graph of scientific state and provenance.
- `replays/`: replay bundles for recent runs.

## Current Model Layer

The policy model is a transparent contextual action-ranking model. It uses:

- action priors from prior traces,
- state-specific action counts,
- context-token action associations,
- reward-weighted action quality,
- tool reliability and usefulness.

It should be judged by holdout top-k accuracy, MRR, replay quality, integration coverage, and whether it improves workflow decisions over time.

## Neural Policy Layer

The PyTorch neural policy is the shareable open-source model artifact. It uses:

- PyTorch MLP architecture,
- bag-of-context-token inputs from objective, state, run configuration, and tool context,
- softmax output over observed workflow actions,
- reward-weighted cross-entropy training,
- run-level holdout evaluation,
- majority-policy baseline comparison.

Train it after collecting real traces, then package the latest model:

```bash
python tools/train_neural_workflow_policy.py --artifact-dir outputs/models --epochs 120
python tools/package_policy_model.py --output-dir outputs/packages --replay-limit 10 --graph-limit 500
```

The neural model is still an orchestration model, not a biomedical foundation model; its value comes from learning how to operate AutoScientist across evidence tools, memory, replay, and experiment planning.
