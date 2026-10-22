#!/usr/bin/env bash
# D172: run one command inside a throwaway runner container (scripts/vm/Dockerfile). Only one host folder is mounted:
# the output folder, at /out (runs, the lesson library and reports are written there). The model and search keys are
# passed by name from this shell's environment, never as values, never written to a file. The container is removed
# when the command ends (--rm).
#
#     scripts/vm/run.sh <out-dir> "python -m scripts.preflight --mode inprocess"
#     scripts/vm/run.sh <out-dir> "python -m scripts.run_task --tasks tasks/stage1_dev.jsonl --runs-dir /out/runs \
#         --lessons-dir /out/lessons --local-tools on --local-tools-mode inprocess ..."
#
# Inside, AMOEBA_SANDBOX=1 is set by the image, and local tools must run with --local-tools-mode inprocess (the
# container is the sandbox), so Box 4's scoped round never falls back to single.
set -euo pipefail
out="${1:?usage: run.sh <out-dir> \"<command>\"}"
cmd="${2:-python -m scripts.preflight --mode inprocess}"
image="${AMOEBA_RUNNER_IMAGE:-amoeba-runner:local}"
mkdir -p "$out"
out_abs="$(cd "$out" && pwd)"
case "$cmd" in
  *"--local-tools on"*) [[ "$cmd" == *"--local-tools-mode inprocess"* ]] || {
      echo "run.sh: inside the runner, local tools run with --local-tools-mode inprocess" >&2; exit 2; } ;;
esac
exec docker run --rm --init \
  -e CLAUDE_API_KEY -e GEMINI_API_KEY -e TAVILY_API_KEY -e OPENROUTER_API_KEY \
  -e AMOEBA_RUN_DATE \
  -v "$out_abs:/out" \
  "$image" "$cmd"
