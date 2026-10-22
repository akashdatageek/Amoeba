I read "small desktop invoicing app" as A client-facing app the consultancy builds and delivers to a customer who uses it on their own laptop; if you meant An internal tool for the consultancy's own invoicing, with the consultant as the sole user, the answer below may not apply.

## Recommendation

**Use SQLite.** With one user on one laptop there is no concurrent-write load, so PostgreSQL's server process, ports, credentials, upgrades and tuning would add install and support burden for a customer with no admin skills, and give nothing back. SQLite is a single file inside the app: nothing to install, no service to fail, simple to back up and restore, and transactional (ACID) when configured properly. Change the choice if the app becomes multi-user or networked (several machines writing to one shared database) or needs central server-side reporting. Keep the SQL portable behind a data-access layer so a later move to PostgreSQL stays feasible.

| Risk | Likelihood | Mitigation |
|---|---|---|
| Data loss or corruption of the database file (power loss, crash, user moving or copying the file while the app runs) | Low: SQLite is transactional and a single process writes, but laptops lose power and customers touch files | Enable WAL mode and `synchronous=FULL`; wrap each invoice save in one transaction; store the file in the app's per-user data folder, not a visible or synced folder; run `PRAGMA integrity_check` at startup and offer restore from the latest backup if it fails |
| Backup failure (no backup made, backup copy is inconsistent, or restore never tested) | Medium: a non-technical customer will not back up by hand, and a plain file copy during a write can be inconsistent | Make backups automatic on app exit and periodically, using the SQLite online backup API or `VACUUM INTO` (never a raw file copy); keep several dated copies; add a one-click "Export all data" (CSV/JSON) and a tested in-app Restore; test restore before each delivery |
| Migration or scaling limits (schema changes in later releases, or the customer later needs multi-user or networked access) | Medium: schema changes are likely; the need for multi-user access is unlikely | Keep a schema version table and numbered, forward-only migrations; take an automatic backup before every migration; isolate SQL in a repository/data-access layer using portable SQL; if multi-user is requested, treat it as a scoped change and move to PostgreSQL then |

## Files made
- tool_results/step2_2.txt (2,130 bytes, made in step 2; listed by plain code)
- tool_results/step2_3.txt (2,128 bytes, made in step 2; listed by plain code)
- tool_results/step2_4.txt (6,182 bytes, made in step 2; listed by plain code)
- tool_results/step2_5.txt (4,332 bytes, made in step 2; listed by plain code)
- tool_results/step2_6.txt (3,837 bytes, made in step 2; listed by plain code)

## Limitations

- Interpretation: the working interpretation (client-facing app delivered to a customer's own laptop; risks of the chosen database, SQLite) was kept unchanged. The three table rows cover those risks: data loss, backup failure, and migration or scaling limits.
- Step 2 (Technical Reviewer) finished as partial: one citation was mislabelled (the "never delete -wal or -journal files" point is not in S23), so I left that optional addition out.
- Files: the task asked for no files. Step 2 made working files only (out/r.txt and tool_results/step2_1.txt to step2_7.txt) holding the reviewer's source checks and notes. None is a deliverable and none is needed to read this answer.
- The reviewer counted the recommendation paragraph at 104 words, under a 120-word limit [S5].
- [unverified] The PostgreSQL server-process and admin burden is general knowledge, not checked against a source.
- [unverified] Using `synchronous=FULL` with WAL for durability is general knowledge. The reviewer did not confirm the exact wording in [S1].
- The Low/Medium likelihood ratings are judgement calls. The reviewer expected Medium for row 1 and Medium to High for row 2, and said this does not change the conclusion.

- NOT MET: R5 — Plan on the working interpretation settled before planning (client-facing app delivered to a customer's own laptop; risks of the chosen database) and do not re- (the final answer does not cover it; checked by plain code on the final answer)

