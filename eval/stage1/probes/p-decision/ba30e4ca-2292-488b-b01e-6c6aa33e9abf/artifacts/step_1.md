# Database recommendation: SQLite vs PostgreSQL

## Recommendation

**Use SQLite.** With one user on one laptop there is no concurrent-write load, so PostgreSQL's server process, ports, credentials, upgrades and tuning would add install and support burden for a customer with no admin skills, and give nothing back. SQLite is a single file inside the app: nothing to install, no service to fail, simple to back up and restore, and transactional (ACID) when configured properly. Change the choice if the app becomes multi-user or networked (several machines writing to one shared database) or needs central server-side reporting. Keep the SQL portable behind a data-access layer so a later move to PostgreSQL stays feasible.

## Risk table

| Risk | Likelihood | Mitigation |
|---|---|---|
| Data loss or corruption of the database file (power loss, crash, user moving or copying the file while the app runs) | Low: SQLite is transactional and a single process writes, but laptops lose power and customers touch files | Enable WAL mode and `synchronous=FULL`; wrap each invoice save in one transaction; store the file in the app's per-user data folder, not a visible or synced folder; run `PRAGMA integrity_check` at startup and offer restore from the latest backup if it fails |
| Backup failure (no backup made, backup copy is inconsistent, or restore never tested) | Medium: a non-technical customer will not back up by hand, and a plain file copy during a write can be inconsistent | Make backups automatic on app exit and periodically, using the SQLite online backup API or `VACUUM INTO` (never a raw file copy); keep several dated copies; add a one-click "Export all data" (CSV/JSON) and a tested in-app Restore; test restore before each delivery |
| Migration or scaling limits (schema changes in later releases, or the customer later needs multi-user or networked access) | Medium: low for scaling (the one-user scope is fixed), but schema changes are likely as each update ships new versions | Keep a schema version table and numbered, forward-only migrations; take an automatic backup before every migration; isolate SQL in a repository/data-access layer using portable SQL; if multi-user is requested, treat it as a scoped change and move to PostgreSQL then |
