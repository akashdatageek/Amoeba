# Test report: dedup + DAU (sqlite equivalent) on sample_events.csv

**Not executed in Snowflake.** The Snowflake dialect (QUALIFY, MERGE, DATE_TRUNC, Tasks) was not executed in Snowflake: no account or network. Only the sqlite3 equivalent in pipeline_sqlite.py was run. sqlite tests logic, not performance or Snowflake semantics.

## Counts
| Metric | Value |
|---|---|
| Rows in | 21,750 |
| Rows out (clean_events) | 21,000 |
| Duplicates removed | 750 (3.45% of rows) |
| Distinct event_ids (oracle) | 21,000 |
| Cross-day duplicate ids | 200 |
| Null/empty country rows; lowercase country rows | 217; 347 |
| Midnight events (23:59 / 00:00 UTC) in deduped set | 1317 |
| (day,country) cells compared | 48 |
| **Mismatches vs oracle** | **0** |

## Results (check x expected x actual x pass)
| Check | Expected | Actual | Pass |
|---|---|---|---|
| (day,country) rows: mismatches vs oracle (48 cells) | 0 | 0 | PASS |
| rows in (raw loaded) | 21750 | 21750 | PASS |
| rows after dedup == distinct event_ids | 21000 | 21000 | PASS |
| duplicates removed | 750 | 750 | PASS |
| no duplicate event_id in clean_events | 21000 | 21000 | PASS |
| idempotent rerun: DAU rows + clean count unchanged | True | True | PASS |
| incremental 2-night load (look-back 1 day) == oracle, mismatches | 0 | 0 | PASS |
| incremental clean rows == distinct ids | 21000 | 21000 | PASS |
| cross-day duplicate ids (200) each kept exactly once | 0 | 0 | PASS |
| midnight: synthetic 23:59:59 -> 10-19, 00:00:00 -> 10-20, US/lowercase merged, null->UNKNOWN | {('2026-10-19', 'US'): 1, ('2026-10-20', 'US'): 2, ('2026-10-20', 'UNKNOWN'): 1} | {('2026-10-19', 'US'): 1, ('2026-10-20', 'UNKNOWN'): 1, ('2026-10-20', 'US'): 2} | PASS |
| midnight events in sample (count>0) | True | True | PASS |
| every midnight-event user is within its UTC day oracle & table (cells ok) | True | True | PASS |

Overall: 12/12 checks passed. The oracle is independent pure Python (dict/set; earliest ingested_at per event_id; day = event_ts[:10]; country upper-cased, blank -> UNKNOWN; null user_id excluded). The idempotent rerun leaves DAU and clean_events unchanged (job_runs gets one more audit row per run: 2 rows after the first run was repeated... see below).
job_runs after run 1 + rerun: 2 rows; first = ('dau_nightly', '2026-10-21', 'SUCCESS', 21750, 21000, 750, '2026-10-23 02:53:04')

## Sample of output (top 4 countries per day by DAU)
| event_date | country | dau |
|---|---|---|
| 2026-10-19 | US | 1457 |
| 2026-10-19 | IN | 859 |
| 2026-10-19 | BR | 571 |
| 2026-10-19 | GB | 487 |
| 2026-10-20 | US | 1375 |
| 2026-10-20 | IN | 803 |
| 2026-10-20 | BR | 605 |
| 2026-10-20 | GB | 440 |
| 2026-10-21 | US | 1525 |
| 2026-10-21 | IN | 844 |
| 2026-10-21 | BR | 594 |
| 2026-10-21 | GB | 466 |

## Limits
- Snowflake dialect not executed in Snowflake; QUALIFY/MERGE/DATE_TRUNC translations are untested there.
- sqlite tests logic, not performance, clustering, concurrency or 30M-row/day scale.
- Dedup follows the settled interpretation (same event_id, earliest ingested_at wins). Duplicates arriving after the look-back window would be re-inserted unless the anti-join covers all of CLEAN; the incremental test used a 1-day look-back with the anti-join against CLEAN.
