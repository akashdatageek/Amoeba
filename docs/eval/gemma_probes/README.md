# Gemma category probes (D156–D160)

These are eight small probes, one per test category. Each takes a few minutes and is not one of the real tests.
- `tasks.jsonl` holds the probe tasks.
- `expected.json` holds the known answers.
- `inputs/red.png` and `inputs/nir.png` are a synthetic 40×40 band pair. There are four 20×20 zones with known NDVI:
  A 0.6, B 0.2, C 0.0 and D −0.4.

Run (keys come from the environment only):

    python -m scripts.preflight --mode sandbox
    python -m scripts.run_task --tasks docs/eval/gemma_probes/tasks.jsonl --topology plan --llm openai \
        --profile gemma-api --protocol v2 --adapt on --local-tools on --local-tools-mode sandbox --web-tools

Probe 8 gives its files through the task's `files` list (D157).
