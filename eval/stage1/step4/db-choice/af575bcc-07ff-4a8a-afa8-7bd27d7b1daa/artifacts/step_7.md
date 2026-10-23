# MEMO: GDPR residency mechanics (Part 1): PostgreSQL services vs MongoDB Atlas on AWS and GCP

Prepared by: Privacy & Risk Lead. Date: Thursday 22 October 2026 (as of 22 Oct 2026).
NOT LEGAL ADVICE. This is a technical-mechanics review. Legal conclusions are for qualified EU counsel (questions at the end).

## 0. How much is verified
- Only two vendor pages were read in this step, and only partial excerpts of each:
  - [S82] MongoDB Atlas docs, "Copy Snapshots to Additional Regions", https://www.mongodb.com/docs/atlas/backup/cloud-backup/snapshot-distribution. Fetched Oct 2026 (as of 22 Oct 2026).
  - [S89]/[S90] Google Cloud docs, "Manage instance locations | Cloud SQL for PostgreSQL", https://cloud.google.com/sql/docs/postgres/locations. Fetched 2026-10-23T04:22:27+00:00, which is 22 Oct 2026 in Chicago. [S90] is a grep of the saved page.
- The AWS RDS, Aurora and AlloyDB pages were NOT fetched. The MongoDB and AWS/Google sub-processor and support-access pages were NOT fetched either.
- Every cell tagged [unverified] comes from general knowledge. It is a lead to confirm at the URL named, not a finding. Those URLs have no verified date.
- These are qualitative mechanics, not "latest value" figures. The date I settled on for the fetched pages is 22 Oct 2026. I made no newer-value search.

## 1. Facts from the fetched pages
- F1. Atlas can copy snapshots to additional regions through a snapshot copy policy. If "Point-in-Time Restore" is On for a copy-policy item, Atlas also copies oplogs to the copy region and enables point-in-time restores there. [S82, fetched Oct 2026, as of 22 Oct 2026]
  - INTERP: cross-region backup copy is an opt-in setting. For EU-only tenants, copy regions must be limited to EU regions, and that setting must be audited.
- F2. When you create a Cloud SQL instance, you choose a region where the instance and its data are stored. [S90, from S89, 2026-10-23T04:22:27+00:00]
- F3. Cloud SQL defines a regional location (a specific place, such as London) and a multi-regional location (a large area containing at least two places). Multi-regional locations are used only for backups. [S90, from S89, 2026-10-23T04:22:27+00:00]
  - INTERP: Cloud SQL backups can sit in a multi-region, such as an EU-wide area, rather than one place. For strict residency, check that the backup location is set to an EU location. The exact default and the list of EU locations were cut off in my read and are not confirmed.

## 2. Comparison table
Key: FACT = read in a fetched source, with [S#]. [unverified] = general knowledge, to confirm at the URL given. INTERP = my interpretation.

| Dimension | RDS for PostgreSQL (AWS) | Aurora PostgreSQL (AWS) | Cloud SQL for PostgreSQL (GCP) | AlloyDB (GCP) | MongoDB Atlas (AWS and GCP) |
|---|---|---|---|---|---|
| EU regions (eu-central-1 Frankfurt, eu-west-1 Ireland; europe-west3 Frankfurt, europe-west4 Netherlands) | Offered in the AWS EU regions. [unverified; confirm https://aws.amazon.com/rds/postgresql/pricing/] | Same AWS regions. [unverified; confirm https://aws.amazon.com/rds/aurora/pricing/] | Region is chosen at instance creation, and data stays in that region. FACT [S90, 2026-10-23]. Whether europe-west3 and europe-west4 are listed is [unverified]. | Regional clusters. EU availability [unverified; confirm https://cloud.google.com/alloydb/docs/locations] | Atlas offers AWS and GCP EU regions. [unverified; confirm https://www.mongodb.com/docs/atlas/cloud-providers-regions/] |
| Backups and snapshots | Stored in the instance's region by default. Cross-region backup replication is optional. [unverified; confirm https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReplicateBackups.html] | Backups stay in the cluster's region. Cross-region snapshot copy is user-initiated. [unverified; confirm https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/] | Backups can use a multi-regional location. FACT [S90, 2026-10-23]. INTERP: explicitly set an EU backup location. | Backup location is configurable. [unverified; confirm https://cloud.google.com/alloydb/docs/backup/overview] | Snapshot copy to additional regions is an opt-in policy, and point-in-time oplog copy is optional. FACT [S82, Oct 2026]. Default snapshot location is the cluster's region. [unverified] |
| Replicas and cross-region | Cross-region read replicas are optional. EU-only is possible if you choose EU targets. [unverified] | Aurora Global Database replicates to chosen secondary regions. [unverified; confirm https://aws.amazon.com/rds/aurora/global-database/] | Cross-region replicas are user-chosen. [unverified] | Secondary clusters in other regions are user-chosen. [unverified] | Multi-region clusters and snapshot copies are user-defined. [S82, Oct 2026] |
| Logs and monitoring data | Logs go to CloudWatch in the same region by default. Telemetry location is [unverified]. | Same as RDS. [unverified] | Logs go to Cloud Logging, and the log bucket location is configurable. [unverified] | Same as Cloud SQL. [unverified] | Logs and metrics sit in the Atlas control plane. Location is [unverified]. |
| Support access from outside the EU | Not confirmed. Governed by the AWS DPA and service terms. [unverified; confirm https://aws.amazon.com/compliance/gdpr-center/] | Same as RDS. [unverified] | Not confirmed. Check Google support-location and Access Transparency terms. [unverified; confirm https://cloud.google.com/terms/data-processing-addendum] | Same as Cloud SQL. [unverified] | Not confirmed. MongoDB support staff may be outside the EU, so this is a key question for MongoDB. [unverified; confirm https://www.mongodb.com/legal/dpa] |
| Sub-processors | AWS publishes a list. [unverified; confirm https://aws.amazon.com/compliance/sub-processors/] | Same. | Google Cloud publishes a list. [unverified; confirm https://cloud.google.com/terms/subprocessors] | Same. | Two layers: MongoDB's own sub-processors plus the hyperscaler (AWS or GCP). [unverified; confirm https://www.mongodb.com/legal/sub-processors] |
| Tenant region pinning | One instance per region. Deploy a separate EU instance for EU tenants. [INTERP] | One cluster per region. Avoid Global Database for EU-only tenants unless every secondary is in the EU. [INTERP] | One instance per region. [INTERP] | One cluster per region. [INTERP] | One cluster per region is simplest. Global Clusters with zone sharding can pin documents by location key. [unverified; confirm https://www.mongodb.com/docs/atlas/global-clusters/] |

## 3. Interpretation (not fact)
- All five options appear able to keep primary data in the EU. The residency risk sits in optional features (cross-region copies and replicas), in log and telemetry destinations, and in support access.
- A "cluster per region" design is the most defensible pinning model on both stacks. Qualitatively, it raises baseline infrastructure cost for the EU share of tenants, because EU tenants need their own HA footprint. Pricing belongs to the cost steps.
- Atlas adds one more layer to review (MongoDB as processor, plus AWS or GCP as sub-processor). Managed PostgreSQL has a single-vendor chain.

## 4. Required controls (proposed)
1. Use EU-only regions for EU tenants.
2. Set backup, snapshot-copy and replica targets explicitly to EU regions. For Atlas, restrict snapshot-copy policies [S82]. For Cloud SQL, set an EU backup location [S90].
3. Use Org Policy or SCP region restrictions to block non-EU regions.
4. Confirm where logs and metrics go.
5. Obtain and review each vendor's DPA, sub-processor list and support-access terms.
6. Use customer-managed keys where offered.

## 5. Gaps I could not confirm
- Official AWS RDS and Aurora backup and replication pages, and the AlloyDB pages, were not fetched.
- The Cloud SQL default backup location and the full EU region list were cut off in my read.
- The MongoDB sub-processor list, DPA and support-access pages were not fetched.
- The AWS and Google sub-processor lists and support-location terms were not fetched.
- Every [unverified] cell is a lead, not a finding.

## 6. Questions for counsel
1. Is EU-only storage with possible remote non-EU support access acceptable under the GDPR international-transfer chapter, or are SCCs and a transfer impact assessment required?
2. Does reliance on the EU-US Data Privacy Framework for MongoDB, AWS or Google need a fallback to SCCs?
3. How should CLOUD Act exposure be documented in EU tenant contracts?
4. Are Atlas's two-layer sub-processor chain and its notice and objection mechanics adequate under the GDPR processor-contract article?
5. Does a "cluster per region" model satisfy the data-residency promises in our tenant contracts?

## 7. Sources
- [S82] https://www.mongodb.com/docs/atlas/backup/cloud-backup/snapshot-distribution, fetched Oct 2026 (as of 22 Oct 2026).
- [S89]/[S90] https://cloud.google.com/sql/docs/postgres/locations, fetched 2026-10-23T04:22:27+00:00 (22 Oct 2026 Chicago time).
- URLs marked "confirm" above were NOT fetched and have no verified date.
MISSING DATA: AWS RDS/Aurora backup, cross-region replication and region pages — not fetched (turn limit reached)
MISSING DATA: AlloyDB locations/backup pages — not fetched
MISSING DATA: Cloud SQL default backup location and EU region list — page text truncated, not fully read
MISSING DATA: MongoDB Atlas sub-processor list, DPA and support-access policy — not fetched
MISSING DATA: AWS and Google sub-processor lists and support-location terms — not fetched
