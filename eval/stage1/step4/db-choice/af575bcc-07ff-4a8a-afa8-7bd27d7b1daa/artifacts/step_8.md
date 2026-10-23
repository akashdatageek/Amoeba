# GDPR legal controls memo: PostgreSQL (RDS/Aurora/Cloud SQL/AlloyDB) vs MongoDB Atlas (AWS and GCP)

**Not legal advice.** This is a technical and privacy-risk review. Facts are kept apart from interpretation, and nothing here is a legal conclusion. Counsel must confirm the points in the "Questions for counsel" list.

**Dating and sourcing.**
- Today is 22 Oct 2026, the date given in the task.
- The pages were read in this run. sources/index.json logs their retrieval as 2026-10-23 (UTC timestamp) [S100]. "As of" below means that retrieval date.
- I did not see any page's own publication date, so none is given.
- Items tagged [unverified] come from my background knowledge. I fetched no page for them, so verify them before relying on them.
- Source URLs, as listed in sources/index.json [S100]:
  - S91: https://aws.amazon.com/compliance/eu-data-protection
  - S92: https://docs.aws.amazon.com/whitepapers/latest/navigating-gdpr-compliance/aws-data-processing-addendum-dpa.html
  - S82: https://www.mongodb.com/docs/atlas/backup/cloud-backup/snapshot-distribution
  - S83: https://www.mongodb.com/docs/atlas/backup/cloud-backup/dedicated-cluster-backup
  - S84: https://ottomatik.io/post/exploring-mongodb-atlas-backups
  - S89: https://cloud.google.com/sql/docs/postgres/locations

**What I could not confirm.**
- No GCP DPA/SCC page was fetched.
- No MongoDB DPA or sub-processor page was fetched.
- No Atlas customer-managed-key (CMK) page and no AWS or GCP KMS page was fetched.
- No current DPF status source was fetched, such as the European Commission or dataprivacyframework.gov.
- Rows marked [unverified] are hypotheses to check.

## 1. Legal controls table

| Control | PostgreSQL on AWS (RDS/Aurora) | PostgreSQL on GCP (Cloud SQL/AlloyDB) | MongoDB Atlas (AWS/GCP) | Basis and source |
|---|---|---|---|---|
| **SCC** (GDPR Chapter V) | **Fact:** the AWS GDPR DPA includes SCCs and applies automatically to customers subject to GDPR. AWS says customers can move content from Europe to the US and elsewhere in line with EU data-protection law [S91, https://aws.amazon.com/compliance/eu-data-protection, as of 2026-10-23]. The whitepaper page was seen only as a search excerpt [S92, https://docs.aws.amazon.com/whitepapers/latest/navigating-gdpr-compliance/aws-data-processing-addendum-dpa.html, as of 2026-10-23]. | **Not confirmed.** Google Cloud is said to offer SCCs in its Cloud Data Processing Addendum [unverified]. | **Not confirmed.** MongoDB's DPA is said to incorporate SCCs [unverified]. Atlas runs on AWS/GCP, so the cloud provider is probably also a sub-processor [unverified]. | **Interpretation:** the SCC chain for Atlas must cover you → MongoDB → hyperscaler. For Postgres it is you → hyperscaler. Atlas adds one party. |
| **DPF** | The DPF is a transfer mechanism that applies only if the US importer is self-certified. AWS is said to be certified [unverified]. | Google is said to be certified [unverified]. | MongoDB, Inc. is said to be certified [unverified]. | **Fragility [unverified]:** the Commission adequacy decision dates from 10 Jul 2023. The EU General Court is reported to have dismissed the Latombe challenge on 3 Sep 2025, with an appeal to the CJEU reported. **Interpretation:** keep SCCs plus a transfer impact assessment (TIA) as a fallback and do not rely on the DPF alone. Check current status before signing. No official source was fetched. |
| **Erasure (Art. 17), backups** | RDS/Aurora automated backups and snapshots hold the whole instance. One tenant's rows cannot be removed from a snapshot. Retention is bounded and configurable [unverified]. | **Fact:** Cloud SQL multi-regional locations are used only for backups [S89, https://cloud.google.com/sql/docs/postgres/locations, as of 2026-10-23]. Backups are restored as whole instances [unverified]. | **Fact:** by default Atlas stores snapshots in the same cloud region as the cluster's primary node. A snapshot copy policy can add copies in additional regions, and oplogs can optionally be copied for point-in-time restore [S82, https://www.mongodb.com/docs/atlas/backup/cloud-backup/snapshot-distribution, as of 2026-10-23]. The single-region backup page says snapshots are stored in the same cloud region as the cluster [S83, as of 2026-10-23]. Snapshots are whole-cluster and immutable [unverified]. | **Interpretation:** erasure from backups is usually handled by a documented retention window that expires the data ("beyond use"). Counsel must confirm that is acceptable. Do not promise instant erasure from backups in the tenant contract. |
| **Erasure (Art. 17), per-tenant deletion** | **Schema-per-tenant or database-per-tenant:** `DROP SCHEMA/DATABASE` gives clean deletion. **Shared table with `tenant_id`:** `DELETE` plus VACUUM, with bloat and replication lag. Partitioning by tenant gives a fast `DROP PARTITION` [unverified]. | Same Postgres mechanics [unverified]. | **Collection or database per tenant:** a drop is clean, but very many collections strain a cluster. **Shared collection:** `deleteMany` on an indexed `tenant_id`, with compaction needed [unverified]. | **Interpretation:** at 50 tenants of 200 GB each, tenant-per-database or per-schema, with a per-tenant key, is the easiest way to prove erasure. A shared table or collection is cheaper to run but harder to evidence. |
| **Art. 28 DPA** | The AWS DPA applies automatically [S91, as of 2026-10-23]. | Google Cloud DPA [unverified]. | MongoDB DPA with sub-processor list [unverified]. | **Fact [unverified, GDPR text]:** Art. 28 requires a processor contract and flow-down of sub-processor terms. **Interpretation:** you are probably the processor for your tenants, who are the controllers. You need your own sub-processor list and a change-notice mechanism. Atlas adds a second layer (MongoDB plus the cloud host). |
| **Art. 32 encryption and keys** | RDS/Aurora encrypt at rest with KMS, and CMKs are supported. Encryption must be chosen at creation [unverified]. | Cloud SQL and AlloyDB support CMEK through Cloud KMS [unverified]. | Atlas encrypts at rest by default and supports CMK through AWS KMS or GCP KMS [unverified]. | **Interpretation:** CMKs help with crypto-shredding. A per-tenant key is feasible only with a cluster per tenant or with application-level encryption. |
| **CLOUD Act exposure** | US-headquartered provider, so US legal process can reach data held abroad [unverified]. | Same [unverified]. | MongoDB, Inc. is US-headquartered, so the same applies [unverified]. | **Interpretation:** an EU region does not remove the exposure. Mitigations are customer-held or external keys and a TIA. Counsel to advise. |
| **Provider and support access from outside the EU** | Follow-the-sun support may access data [unverified]. | Same [unverified]. | Atlas support and engineering access is a likely extra transfer path [unverified]. | Request the contractual support-location terms and access logging. |

## 2. Residency mechanics seen in sources (facts)
- A copy region outside the EU in an Atlas snapshot copy policy would move EU tenant backups out of the EU [S82, as of 2026-10-23]. **Interpretation:** allow only EU regions for copy targets.
- Cloud SQL separates regional locations from multi-regional locations. Multi-regional locations hold backups only [S89, as of 2026-10-23]. **Interpretation:** set the backup location explicitly to an EU location.
- I fetched no page on Aurora Global Database or Cloud SQL cross-region replicas. Choose the replica region deliberately and use EU regions only for EU tenants [unverified].

## 3. Qualitative cost impact of an EU/US two-region setup
- **Interpretation:** a cluster or instance per region roughly doubles the fixed baseline of compute, HA nodes and backups. Data volume does not double, because each tenant lives in one region. If US tenants are few, you still pay a floor cost for a second, mostly idle HA cluster.
- A single global cluster is cheaper but cannot honour EU-only residency.
- Cross-region replication and backup copies add inter-region transfer and storage charges [unverified].
- Atlas Global Clusters with zone sharding are a third option. They need a check against the pricing step's figures.

## 4. Required controls (recommended, subject to counsel)
1. Pin all EU tenants to EU regions: eu-central-1 or eu-west-1 on AWS, europe-west3 or europe-west4 on GCP. Pin backups, snapshot copies, oplog copies and replicas to EU regions too.
2. Sign the DPA with SCCs for every provider (AWS, Google, MongoDB). Keep the sub-processor lists and a change-notice process.
3. Record a TIA. Do not depend on the DPF alone.
4. Encrypt at rest with CMK/CMEK. Consider per-tenant keys or application-level encryption for crypto-shredding.
5. Use tenant-per-database or per-schema, or partition by tenant, so per-tenant erasure is provable. Document a backup retention window and an erasure procedure.
6. Restrict and log provider support access. Prefer EU-only support where offered.
7. Test the erasure runbook, including reapplying deletions after any backup restore.
8. Put the Art. 30 record, a DPIA trigger and breach-notice terms (Art. 33) in the tenant DPA [unverified, GDPR article numbers].

## 5. Questions for counsel
1. Are SCCs plus a TIA sufficient if the DPF is annulled? What is the current status of the Latombe appeal?
2. Is expiry through backup retention acceptable for Art. 17 requests? What maximum retention window is defensible?
3. Does CLOUD Act exposure of US-headquartered providers need supplementary measures, such as customer-held keys, for our EU tenants?
4. As processor, what sub-processor notice and objection rights must our tenant DPA grant, given the Atlas plus hyperscaler chain?
5. Is provider support access from outside the EU a restricted transfer that needs separate SCC coverage?
6. Do any tenants have sector rules (health, finance) or national localisation rules beyond the GDPR?
7. Is a DPIA required for the analytics product?

## 6. Sources (retrieved 2026-10-23 per sources/index.json [S100]; page publication dates not seen)
- [S91] AWS, "EU Data Protection – GDPR": https://aws.amazon.com/compliance/eu-data-protection
- [S92] AWS whitepaper, "Navigating GDPR Compliance – DPA": https://docs.aws.amazon.com/whitepapers/latest/navigating-gdpr-compliance/aws-data-processing-addendum-dpa.html (search excerpt only)
- [S82] MongoDB Atlas, "Copy Snapshots to Additional Regions": https://www.mongodb.com/docs/atlas/backup/cloud-backup/snapshot-distribution
- [S83] MongoDB Atlas, "Dedicated Cluster Backups": https://www.mongodb.com/docs/atlas/backup/cloud-backup/dedicated-cluster-backup
- [S84] Ottomatik, "Exploring MongoDB Atlas Backups": https://ottomatik.io/post/exploring-mongodb-atlas-backups (context only, not used for a claim)
- [S89] Google Cloud SQL locations: https://cloud.google.com/sql/docs/postgres/locations
- Every row marked [unverified] has no fetched source. Verify it against the vendor DPA pages, the European Commission DPF decision and dataprivacyframework.gov before reliance.
MISSING DATA: GCP Cloud Data Processing Addendum / SCC page — not fetched in this step
MISSING DATA: MongoDB DPA, SCC and sub-processor list — not fetched
MISSING DATA: Atlas and AWS/GCP KMS customer-managed key documentation — not fetched
MISSING DATA: Current EU-US DPF status (Commission decision, Latombe appeal) with official date — not fetched
MISSING DATA: Aurora Global / Cloud SQL cross-region replica residency pages — not fetched
MISSING DATA: Page publication dates for S91, S92, S82, S83 and S89 — only retrieval date available
