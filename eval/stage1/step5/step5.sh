#!/bin/bash
# Part 2 Step 5: the small learning check. Tasks 1, 3 and 8, each twice with one injected fault from stage_e's list
# (capability, missing_input, tool_error), --lessons-write on, --lessons off, the same library as Step 4. One run at a
# time; resumable (done5_<label> markers).
cd /home/user/Amoeba
export AMOEBA_RUNNER_CA=/root/.ccr/ca-bundle.crt AMOEBA_RUNNER_NETWORK=host
for spec in probe-h2-income:tool_error:1 probe-h2-income:tool_error:2 probe-b4-fuel:capability:1 probe-b4-fuel:capability:2 \
            drone-field-a:missing_input:1 drone-field-a:missing_input:2; do
  IFS=: read t cause seed <<< "$spec"
  label=$t.$cause.s$seed
  [ -f /home/user/stage1_out/done5_$label ] && continue
  scripts/vm/run.sh /home/user/stage1_out "AMOEBA_TEST_FAULTS=1 bash /out/stage1_one.sh $t tasks/stage1_dev.jsonl \
    --inject-fault $cause:auto --seed $seed --runs-dir /out/step5/runs/$label" > /home/user/stage1_out/step5_$label.log 2>&1
  echo "$(date -u +%T) $label: $(grep -E '^\[plan\]' /home/user/stage1_out/step5_$label.log | cut -c1-200) | $(grep -oE 'est. cost \$[0-9.]+' /home/user/stage1_out/step5_$label.log | tail -1) | $(grep -o 'rc=[0-9]*' /home/user/stage1_out/step5_$label.log)" >> /home/user/stage1_out/step5_progress.txt
  touch /home/user/stage1_out/done5_$label
done
echo "ALL DONE $(date -u +%T)" >> /home/user/stage1_out/step5_progress.txt
