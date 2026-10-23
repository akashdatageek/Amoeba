#!/bin/bash
# Part 2 Step 4: each Stage 1 stream task once, one at a time, in the runner container. Resumable: a task with a
# done_<id> marker is skipped.
cd /home/user/Amoeba
export AMOEBA_RUNNER_CA=/root/.ccr/ca-bundle.crt AMOEBA_RUNNER_NETWORK=host
for t in probe-h2-income probe-h1-freight probe-b4-fuel wordfreq-cli clickstream-pipeline db-choice soil-gateway-missing drone-field-a; do
  [ -f /home/user/stage1_out/done_$t ] && continue
  extra=""
  # db-choice's first attempt (killed by a container restart at $5.81) already wrote its verdicts and lesson L1 to the
  # library; the re-run is scored but does not write again, so the task counts once in the library
  [ $t = db-choice ] && extra="--lessons-write off"
  scripts/vm/run.sh /home/user/stage1_out "bash /out/stage1_one.sh $t tasks/stage1_dev.jsonl $extra" > /home/user/stage1_out/stage1_$t.log 2>&1
  echo "$(date -u +%T) $t: $(grep -E '^\[plan\]' /home/user/stage1_out/stage1_$t.log | cut -c1-200) | $(grep -oE 'est. cost \$[0-9.]+' /home/user/stage1_out/stage1_$t.log | tail -1) | $(grep -o 'rc=[0-9]*' /home/user/stage1_out/stage1_$t.log)" >> /home/user/stage1_out/step4_progress.txt
  touch /home/user/stage1_out/done_$t
done
echo "ALL DONE $(date -u +%T)" >> /home/user/stage1_out/step4_progress.txt
