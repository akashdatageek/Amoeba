#!/bin/bash
# usage (inside the runner): bash /out/probe.sh <probe-id>
. /out/flags.sh
id=$1; mkdir -p /out/probes/one
grep "\"id\": \"$id\"" /out/probes/probes.jsonl > /out/probes/one/$id.jsonl
python -m scripts.run_task --tasks /out/probes/one/$id.jsonl "${FLAGS[@]}" --max-usd-per-run 1 \
  --lessons off --lessons-write off --runs-dir /out/probes/runs/$id
echo "== probe $id rc=$?"
