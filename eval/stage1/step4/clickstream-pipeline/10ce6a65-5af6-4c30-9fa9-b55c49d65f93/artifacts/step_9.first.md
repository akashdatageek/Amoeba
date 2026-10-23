Verdict: FAIL
I read "cloud warehouse" as Snowflake; if you meant Google BigQuery or Amazon Redshift or Databricks / Azure Synapse, the answer below may not apply. I read "duplicate events" as Events sharing the same event_id, from Kafka at-least-once redelivery; if you meant Events identical on a composite key (user, timestamp, type, etc.) or Fully identical rows across all fields, the answer below may not apply. I read "finishes more than 30 minutes late" as Later than 30 minutes after the scheduled completion deadline or SLA time; if you meant Runtime exceeding the expected duration by 30 minutes or More than 30 minutes after the scheduled start time, the answer below may not apply. I read "one year of raw events" as 365 days × 30M × 2 KB, about 22 TB uncompressed; if you meant Compressed columnar storage in the warehouse, a fraction of 22 TB or Includes duplicates and replicas or retention overhead, the answer below may not apply.

# Verification memo, part 2 (step 9): watchdog, runbook consistency, merged verdict

## Re-checks I ran in this step
- **Watchdog rerun.** I ran `python3 sim_watchdog.py` and counted the result rows. 15 rows read `| PASS |` and 0 rows contain FAIL [S75]. This matches the 15 of 15 checks in watchdog_report.md [S49]. The rows I could see were 7b, 8, 8b, 10 and 11, and they match the report: never started at SLA+30 min 1 s gives a page; still running at SLA+30 gives no page and at SLA+31 gives a page [S75]. An earlier rerun showed scenarios 1 to 6 in the same way [S70].
- **Rule measured from the SLA deadline.** The code is `limit = sla_deadline + grace; if now <= limit: return False` [S48]. The test scenarios are all offsets from the SLA deadline. +29 min gives no page, exactly +30 gives no page, and +31 gives a page [S49, S75]. It is not measured from the job start. This matches the settled interpretation.
- **Payload NOT SENT markers.** I ran a grep on `payloads/*.json` for STATUS [S73]. The output was cut off in my view. The report says both files carry `"NOT SENT - simulation only; routing_key is a placeholder"` [S49]. I did not see the file text myself, so this is **UNCONFIRMED by me**. Treat it as reported only.
- **Storage maths (step 8 item, recomputed independently).**
  - `calc 30e6*2000*365/1e12` = 21.9 TB, so the "about 22 TB" headline is correct.
  - 30e6 × 2000 B = 60 GB/day.
  - 30e6 / 86,400 s = 347 events/s.
  - Sensitivity rows at $23 per TB-month: 21.9 × 23 = 503.70; 7.30 × 23 = 167.90; 4.38 × 23 = 100.74; 2.7375 × 23 = 62.96; 8.76 × 23 = 201.48; 8.856 × 23 = 203.69; 8.952 × 23 = 205.90; 14.92 × 23 = 343.16; and 8.76 × 40 = 350.40. All agree with step 8's list.
- **Test rerun (step 8 item).** The workspace result file for the test run ends with `mismatches 0 fails []` and shows rows in 21,750, rows out 21,000 and 750 duplicates [S76]. 21,750 − 21,000 = 750, and 750 / 21,750 = 3.45%. I did not rerun `test_dedup_dau.py` myself in this step. I rely on step 8's rerun [S59], which was run in the same workspace. This is **second-hand, not a rerun by me in step 9**.

## Findings table
| # | Item | Check | Result | Fix needed |
|---|---|---|---|---|
| 1 | Storage headline and rates (step 8) | 30e6×2000×365/1e12 = 21.9 TB; 60 GB/day; 347 events/s | PASS. Matches step 8 and step 2. | None. Optional: step 2's headline line has a typo ("60 GB/day x 60 GB/day days"; it should read "× 365 days"). The result 21.9 is right. |
| 2 | Sensitivity table, all 9 rows incl. monthly cost (step 8) | Recomputed TB × price | PASS within rounding. The $23 and $40 prices come from a 2016 press release [S3, S14], so they are an unconfirmed 2026 assumption. The 3x, 5x and 8x compression ratios are assumptions. | Label the prices "assumption, 2016 source" in the final answer. Step 8 cited [S2] for the 21.9 TB arithmetic, but [S2] is a pricing page. Cite calc instead. |
| 3 | Dedup, DAU and idempotency SQL (step 8) | Read the SQL: MERGE with `QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY ingested_at)=1`; DAU is COUNT(DISTINCT user_id) by UTC day and country; DAU window deleted and re-inserted | PASS on logic. The Snowflake SQL was never executed in Snowflake (steps 3 and 4 say so). The sqlite equivalent was run. | Say plainly in the final answer that the Snowflake SQL is untested. Column naming is inconsistent: MART uses `day` in Snowflake and the runbook, but `event_date` in sqlite and the step 1 memo. Align them. |
| 4 | test_dedup_dau.py (step 8) | Compared with test_report.md | The result file shows mismatches 0 and 21,750 / 21,000 / 750 [S76]. Step 8 reran it [S59]. I did not rerun it myself in step 9, so this is not independently confirmed here. | Rerun once more in the final pass if a clean first-hand confirmation is needed. |
| 5 | Watchdog rerun and the +30 rule | Reran sim_watchdog.py; compared with watchdog_report.md | PASS. 15 of 15 pass, 0 FAIL [S75]. The rule is measured from the SLA deadline, strictly greater than +30 min [S48]. | None. The SLA of 04:00 UTC is an example value. Replace it with the real SLA. |
| 6 | Payload files and NOT SENT | Looked for the NOT SENT markers | UNCONFIRMED by me (grep output cut off [S73]). The report states both files are marked NOT SENT [S49]. | Reviewer should open `payloads/trigger.NOT_SENT.json` and `payloads/resolve.NOT_SENT.json` and confirm the marker. |
| 7 | Watchdog behaviour for the runbook | `should_page` stays True after a late finish (scenario 5), so only a resolve payload clears the page | Valid behaviour. It must appear in the runbook's resolve step. Step 7's text says the runbook should cover this, but I cannot confirm it is in the file. | Make sure the resolve step says who sends the resolve and how. |
| 8 | **runbook.md completeness** | Does the file on disk hold a backfill procedure? | **FAIL.** Step 7 states that runbook.md holds only sections 1 to 3. Both appends were refused by the sandbox, and sections 4 to 7 (fixes, backfill, verification, escalation, post-incident) exist only in the step 7 text. Sections 1 to 3 come from step 6, which is marked STALE (built before step 4's rework) and was not re-checked. | Write sections 4 to 7 into runbook.md using local:Write or local:Edit (not a heredoc). Then re-check sections 1 to 3 against the reworked pipeline. |
| 9 | Runbook uses only tables and tasks found in pipeline_code.md | Table names: RAW.CLICK_EVENTS, CLEAN.EVENTS, MART.DAU_BY_COUNTRY, OPS.JOB_RUNS | Tables match pipeline_code.md and snowflake_pipeline.sql [S67]. Task, warehouse and connector names are placeholders (`<ROOT_TASK>`, `<WAREHOUSE>`, `<CONNECTOR>`), so the "tasks that exist" check cannot pass. The RAW.CLICK_EVENTS column names are assumed. | Replace the placeholders with the real task names from snowflake_pipeline.sql, or add task names to pipeline_code.md. Confirm the RAW column list. |
| 10 | Backfill procedure (in step 7's text) | Is it correct and idempotent? | The text has a prerequisite check, before-counts, MERGE with earliest `ingested_at`, and DELETE plus INSERT of MART for one day. The design is idempotent. It is untested: no Snowflake access, and no SQL or shell was run. | Run it in a test account. Move it into runbook.md (finding 8). |
| 11 | No claim of execution in Snowflake or PagerDuty | Read the limits lines in the steps | PASS in the text I can see. Step 5 says nothing was sent and Snowflake and PagerDuty were not reached. Step 7 says no SQL or shell was run. Steps 3, 4 and 6 say the same. My grep for execution claims was cut off, so the check is partial. PagerDuty-side dedup was not observed. | Keep these limits in the final answer. State that PagerDuty dedup is assumed from the API contract. |

## Differences from my own expected result
- I expected the backfill section to be unconfirmed. Step 7 shows it is **not in runbook.md**. Step 7 is right and my expectation was only "unconfirmed".
- Step 8's PASS did not mention the column-name mismatch (`day` vs `event_date`) or the 2016 price source. I would add both as caveats. They do not change a number.

## Verdict
Verdict: FAIL

Reason: the runbook is a required deliverable and it is incomplete on disk. The backfill procedure and the other sections are not in runbook.md (step 7). The numbers, tests and watchdog logic are fine; the watchdog rerun passed 15 of 15 [S75]. This is not PASS in any case, because the NOT SENT markers and the first-hand rerun of the test script in this step are unconfirmed.

## Required fixes
1. Write runbook sections 4 to 7, including the backfill procedure, into runbook.md. Re-check sections 1 to 3 against the reworked pipeline.
2. Replace the placeholder task, warehouse and connector names with real names from snowflake_pipeline.sql, or state clearly that they are placeholders.
3. Align the MART column name (`day` vs `event_date`) across the Snowflake SQL, sqlite, the runbook and the step 1 memo.
4. Fix the step 2 typo ("60 GB/day x 60 GB/day days"). Label the $23 and $40 prices as 2016-sourced assumptions.
5. Confirm the NOT SENT marker in both payload files by opening them.
6. In the final answer, state that no Snowflake or PagerDuty execution took place.
BLOCKED: Snowflake account — SQL (pipeline and runbook backfill) could not be executed
BLOCKED: PagerDuty account — no payload could be sent; PagerDuty-side dedup not observed
MISSING DATA: Contents of payloads/*.json STATUS lines — grep output cut off in S73
MISSING DATA: First-hand rerun of test_dedup_dau.py in step 9 — relied on step 8's rerun and the result file [S76]
MISSING DATA: Backfill section in runbook.md — step 7 reports it was never written to disk
MISSING INPUT: Complete runbook.md (sections 4-7) — step 7
MISSING INPUT: Re-check of runbook sections 1-3 against reworked pipeline — step 6 marked STALE
Issues:
1. Step 7: runbook.md on disk holds only sections 1-3; the backfill procedure and the fixes, verification, escalation and post-incident sections exist only in the step output. Fix: write them into runbook.md with local:Write or local:Edit and re-check sections 1-3 against the reworked pipeline.
2. Step 7: task, warehouse and connector names are placeholders, so the runbook does not use tasks that exist in pipeline_code.md. Fix: use the real task names from snowflake_pipeline.sql.
3. Steps 1/3/6/7: MART column is `day` in Snowflake SQL and the runbook but `event_date` in sqlite and the step 1 memo. Fix: align the name.
4. Step 2: headline line typo '60 GB/day x 60 GB/day days' (result 21.9 TB is correct); $23 and $40 prices rest on a 2016 source [S3]. Fix: correct the typo and label the prices as assumptions.
5. Step 8: cited [S2] for the 21.9 TB arithmetic, and the claimed reruns could not all be seen by step 9 (NOT SENT markers in payload files unconfirmed in S73). Fix: cite calc; open the payload files to confirm NOT SENT.
