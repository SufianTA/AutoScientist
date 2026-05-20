# AutoScientist Neural Scientific Workflow Policy

## Intended Use

This PyTorch model ranks the next AutoScientist workflow action from scientific run context. It is an orchestration model, not a biomedical fact model or clinical model.

## Open-Source Stack

- Framework: `PyTorch 2.11.0+cu128`
- Inputs: bag-of-token representation of objective, state, run config, and tool context.
- Output: softmax distribution over workflow actions.

## Architecture

- Vocabulary size: `411`
- Hidden dimension: `160`
- Actions: `25`

## Training Data

- Examples: `2257`
- Training examples: `1867`
- Holdout examples: `390`
- Source: AutoScientist workflow traces, tool calls, rewards, replay bundles, and memory graph.

## Metrics

- Top-1 training accuracy: `0.9202`
- Top-3 training accuracy: `1.0`
- Training MRR: `0.9589`
- Top-1 holdout accuracy: `0.9205`
- Top-3 holdout accuracy: `1.0`
- Holdout MRR: `0.9603`
- Majority baseline top-3 holdout accuracy: `0.4718`

## Limitations

- Current dataset is still small; the model should be retrained after larger real biomedical benchmark runs.
- It predicts workflow actions, not scientific truth.
- Use replay/state-graph audits before making claims about discovery value.