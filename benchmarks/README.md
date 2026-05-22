# AutoScientist-Bench

AutoScientist-Bench is a CPU-first benchmark scaffold for preparing larger GPU or cloud runs.
It is designed to answer one question before spending on H100 time: does the persistent runtime
produce better auditable scientific workflows than a no-memory or no-tool baseline?

Start locally with:

```bash
python tools/run_autoscientist_bench.py --limit 3 --ablations full no_memory no_public_tools --offline-public-context
```

Then move to a rented GPU only after the local run produces valid tasks, traces, reports, memory
exports, and package manifests:

```bash
python tools/run_autoscientist_bench.py --limit 100 --replicates-per-case 3 --ablations full no_memory no_public_tools no_sciflow
python tools/train_neural_workflow_policy.py --artifact-dir outputs/models --epochs 120
python tools/package_policy_model.py --output-dir outputs/packages --replay-limit 50 --graph-limit 2000
```

The default manifest is `autoscientist_bench_v0_1.json`.
