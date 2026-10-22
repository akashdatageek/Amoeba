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
  *"--local-tools on"*) [[ "$cmd" == *"--local-tools-mode inprocess"* || "$cmd" == *"preflight"*"--mode inprocess"* ]] || {
      echo "run.sh: inside the runner, local tools run with --local-tools-mode inprocess" >&2; exit 2; } ;;
esac
# Behind a TLS-inspecting proxy (a cloud session), set AMOEBA_RUNNER_CA to its CA file: the proxy variables are passed
# by name and that one file is mounted read-only (a file, not a folder) as the container's trust bundle.
proxy=()
if [[ -n "${AMOEBA_RUNNER_CA:-}" ]]; then
  proxy=(-e HTTPS_PROXY -e HTTP_PROXY -e NO_PROXY -e https_proxy -e http_proxy -e no_proxy
         -e SSL_CERT_FILE=/etc/runner-ca.crt -e REQUESTS_CA_BUNDLE=/etc/runner-ca.crt
         --mount "type=bind,src=$AMOEBA_RUNNER_CA,dst=/etc/runner-ca.crt,readonly")
fi
# A proxy on the host's loopback (127.0.0.1) is reachable only with AMOEBA_RUNNER_NETWORK=host (opt-in: it also lets the
# container reach other loopback services of the host; leave it unset on a VM with direct network access).
[[ -n "${AMOEBA_RUNNER_NETWORK:-}" ]] && proxy+=(--network "$AMOEBA_RUNNER_NETWORK")
exec docker run --rm --init \
  -e CLAUDE_API_KEY -e GEMINI_API_KEY -e TAVILY_API_KEY -e OPENROUTER_API_KEY \
  -e AMOEBA_RUN_DATE \
  "${proxy[@]}" \
  -v "$out_abs:/out" \
  "$image" "$cmd"
