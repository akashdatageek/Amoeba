#!/bin/bash
# Part 2 Step 4 (inside the runner): one Stage 1 stream task, learning on, lessons not shown.
# usage: bash /out/stage1_one.sh <task-id> [tasks-file] [extra run_task args...]
. /out/flags.sh
id=$1; file=${2:-tasks/stage1_dev.jsonl}; shift 2 2>/dev/null || shift
mkdir -p /out/stage1/one
grep "\"id\": \"$id\"" "$file" > /out/stage1/one/$id.jsonl
python -m scripts.run_task --tasks /out/stage1/one/$id.jsonl "${FLAGS[@]}" --max-usd-per-run 6 --seed 0 \
  --lessons off --lessons-write on --lessons-dir /out/lessons --runs-dir /out/stage1/runs/$id "$@"
echo "== stage1 $id rc=$?"
