I read "multi-tenant" as Shared database with a tenant ID column or tenant field; if you meant Separate schema or database per tenant, the answer below may not apply.

# Step 10: GDPR residency on AWS and GCP (RDS, Aurora, Cloud SQL, AlloyDB)

**Not legal advice.** This is an engineering planning note. EU counsel and our DPO must confirm it before we host EU tenant data.

**Source status (all dates are access dates; run date 22 Oct 2026).**
- Three official documentation pages were fetched. They cover EU region availability only:
  - [S96] AWS, "Regions, Availability Zones, and Local Zones", Amazon RDS User Guide, https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.RegionsAndAvailabilityZones.html, accessed 22 Oct 2026.
  - [S97] Google Cloud, "Manage instance locations", Cloud SQL for PostgreSQL, https://cloud.google.com/sql/docs/postgres/locations, accessed 22 Oct 2026.
  - [S99] Google Cloud, "AlloyDB locations", https://cloud.google.com/alloydb/docs/locations, accessed 22 Oct 2026 (fetch stamp 2026-10-23T03:33 UTC, which is 22 Oct 2026 in Chicago).
- No newer version of these pages was sought. Each page is dated 22 Oct 2026, the run date, so that is the date I settled on.
- I ran out of turns before fetching any page on backups, replicas, support access or telemetry. Everything marked **[unverified]** is my own knowledge, a pointer for counsel and engineering to check, not a cited fact.
- Legal basis from step 9: only the European Commission SCC page [S87], accessed 22 Oct 2026, was confirmed. The GDPR article text (EUR-Lex), EU-US DPF status and the AWS/GCP DPAs are unconfirmed.

## Table: one row per service

| Service | EU regions (hosting) | Backups / replicas / snapshots / logs | Support access and telemetry | Erasure (PostgreSQL) | URL and access date |
|---|---|---|---|---|---|
| **Amazon RDS for PostgreSQL** | The RDS regions table lists Europe (Ireland) `eu-west-1` and Europe (Frankfurt) `eu-central-1` [S96] (as of 22 Oct 2026). We can pin instances to either region. | Partial, from the page: RDS resources are regional, and DB instances and data are not replicated automatically across AWS Regions [S96] (as of 22 Oct 2026). So an EU instance stays in its region unless we create a cross-region copy. [unverified] Automated backups and snapshots are stored in the same region by default. A cross-Region read replica or snapshot copy is something we configure, and it can send data out of the EU. Logs and metrics go to CloudWatch in the same region unless exported. | Not fetched. [unverified] AWS support staff and the control plane could touch metadata or, with our permission, data. Check the AWS DPA, sub-processor list and support-case handling. | [unverified] `DELETE` by data-subject key, then `VACUUM`. Dead rows persist until vacuum. Backups and snapshots keep the data until they expire (retention window). Tenant offboarding means deleting by `tenant_id` or dropping a partition. | [S96] https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.RegionsAndAvailabilityZones.html, accessed 22 Oct 2026 |
| **Amazon Aurora PostgreSQL** | **No Aurora-specific page was fetched.** The RDS regions page [S96] (as of 22 Oct 2026) is the only AWS source. I did not see Aurora availability in `eu-west-1` or `eu-central-1` on it, so this is unconfirmed. [unverified] Aurora is available in both regions. | [unverified] Cluster storage is replicated across AZs within the region. Backups stay in-region by default. Aurora Global Database, cross-Region replicas and snapshot copies are opt-in and can leave the EU. | Not fetched. [unverified] Same as RDS. | [unverified] Same as PostgreSQL. Continuous backups keep deleted data until the backup retention window ends. | [S96] (RDS page only; not confirmed for Aurora), accessed 22 Oct 2026 |
| **Google Cloud SQL for PostgreSQL** | The page describes regional and multi-regional locations. A multi-regional location is a large geographic area that contains at least two geographic places [S97] (as of 22 Oct 2026). Excerpts show `europe-west1` and `europe-west4`, with Netherlands named, in the region list [S97] (as of 22 Oct 2026). I could not confirm from the excerpt which region is Belgium and which is the Netherlands. [unverified] `europe-west1` is Belgium and `europe-west4` is the Netherlands. | The fetched excerpt shows the multi-region concept [S97] (as of 22 Oct 2026). It does not show the backup location rules. [unverified] Backups default to a multi-region location (for example `eu`), and a custom location can be set. Cross-region replicas are opt-in. Check that the backup location is an EU one. | Not fetched. [unverified] Google support access, Access Transparency and Access Approval options, and Cloud Logging and Monitoring locations all need checking. | [unverified] Same as PostgreSQL: delete, vacuum, and wait for backups to expire. | [S97] https://cloud.google.com/sql/docs/postgres/locations, accessed 22 Oct 2026 |
| **Google AlloyDB for PostgreSQL** | The AlloyDB locations page lists regions. Excerpts show `europe-west1`, `europe-west4`, `europe-west10` (Berlin) and `europe-west12` (Turin) [S99] (as of 22 Oct 2026). I did not confirm the exact AlloyDB table row for each region. [unverified] AlloyDB is available in `europe-west1` and `europe-west4`. | Not in the fetched excerpt. [unverified] Cluster backups and continuous backup are regional by default, and a backup location can be set. Cross-region replication is opt-in. | Not fetched. [unverified] Same questions as Cloud SQL. | [unverified] Same as PostgreSQL. | [S99] https://cloud.google.com/alloydb/docs/locations, accessed 22 Oct 2026 |

## What we can conclude
- **Hosting (confirmed by official docs, as of 22 Oct 2026):** the EU regions named in the task are available for RDS (`eu-west-1`, `eu-central-1`) [S96]. For Cloud SQL and AlloyDB, `europe-west1` and `europe-west4` appear in the location pages [S97][S99].
- **Hosting in the EU does not settle Chapter V.** Step 9 notes that remote support or admin access from a non-EU provider can count as a transfer [unverified, per step 9]. That is why support access matters even when the data sits in the EU.
- **Shared database with `tenant_id`:** EU tenants need their own EU-region instance or cluster, with backups, replicas and log exports pinned to the EU. Placement, backups and replicas are set at instance or cluster level, not per row.
- **Erasure:** in PostgreSQL, deletion is row-level, but vacuum and backup retention mean data is not gone at once. Write down the retention window and tell data subjects about it. [unverified] This is the standard approach, and counsel must confirm it. Step 9 already requires a data-subject key in every row.

## Gaps
1. **Backup, snapshot, replica and log locations** for all four services were not fetched. Every such claim in the table is [unverified]. Needed: the RDS and Aurora backup and replication docs, and the Cloud SQL and AlloyDB backup-location docs.
2. **Support access and telemetry:** no AWS or GCP DPA, sub-processor, Access Transparency or Access Approval page was fetched. This is the main residency risk and is open.
3. **Aurora:** no Aurora page was fetched. Aurora availability in the EU regions is unconfirmed.
4. **Region names:** Belgium for `europe-west1` and the Netherlands for `europe-west4` are only partly seen in the excerpts and are unconfirmed.
5. **Newer versions:** no further search was made for newer page versions. All pages are dated 22 Oct 2026.
6. **Legal basis:** EUR-Lex, EDPB, DPF status and the provider DPAs are still unconfirmed from step 9.
MISSING DATA: AWS and GCP backup, snapshot, replica and log location rules for RDS, Aurora, Cloud SQL, AlloyDB — not fetched (out of turns); only region pages were read
MISSING DATA: AWS and GCP support access, DPA, sub-processor and Access Transparency / Access Approval pages — not fetched
MISSING DATA: Aurora PostgreSQL EU region availability — no Aurora documentation page fetched
MISSING DATA: Exact Belgium/Netherlands mapping for europe-west1 and europe-west4 — only partial excerpts seen
MISSING INPUT: GDPR article text, DPF status and provider DPAs — step 9 delivered only the Commission SCC page [S87]
