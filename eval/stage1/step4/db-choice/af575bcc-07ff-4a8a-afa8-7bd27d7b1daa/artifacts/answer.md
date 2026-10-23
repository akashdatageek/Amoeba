# Partial answer: the run stopped before it finished

**Why it stopped:** Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_paid_tier_input_token_count, limit: 16000, model: gemma-4-31b\nPlease retry in 59.943718703s.', 'status': 'RESOURCE_EXHAUST

**Steps that did not run:** 9 (Estimate monthly cost for 50 tenants, 10 TB, 5,000 QPM), 10 (Verify cost model and prototype results), 12 (Verify the GDPR assessment's sources and consistency), 13 (Decision matrix, recommendation and risk table), 14 (90-day migration plan), 15 (Assemble the recommendation memo)

**Steps that ran but did not finish:** 1 (partial), 2 (partial), 3 (partial), 4 (partial), 5 (partial), 6 (partial), 7 (partial), 8 (partial), 11 (partial)

The sections below are the outputs of the steps that ran, put together by plain code.

## Step 1: Gather current PostgreSQL vs MongoDB benchmarks

**Scope and limits (as of today, 22 Oct 2026, America/Chicago).** Benchmarks like these are vendor-skewed and do not replace our own prototype on our schema and queries. sources/index.json has no publication-date field for these pages. It only holds fetch times of 2026-10-23 UTC [S127]. The publication dates for S2, S3 and S14 below are the page dates found by the verification review. I did not re-open those pages this turn. I could not confirm dates for S1, S4 or S27. No source measures a tenant-scoped analytics dashboard workload at our load.

**Benchmark evidence table** (every row was fetched 2026-10-23 UTC, i.e. the evening of 22 Oct 2026 Chicago time [S127])

| Source (title) | URL | Date | Workload | Result (what the page supports) | Sponsor / bias | Relevance to tenant-scoped dashboards |
|---|---|---|---|---|---|---|
| PERFORMANCE BENCHMARK POSTGRESQL / MONGODB (EnterpriseDB whitepaper) [S4] | https://info.enterprisedb.com/rs/069-ALB-339/images/PostgreSQL_MongoDB_Benchmark-WhitepaperFinal.pdf | Publication date not extracted. Fetched 2026-10-23 UTC. **Dated:** it tests PostgreSQL 11 and MongoDB 4.0 [S132], which are far behind current versions. | Three parts [S132]: (1) the MongoDB "Transactions" project, an airline reservation model; (2) Sysbench OLTP, in-memory and 2 TB datasets; (3) a JSON-based OLAP benchmark with four custom queries over one year of GitHub archive data, using jsonb in PostgreSQL. Tuning: max_connections=600, shared_buffers=12GB, temp_buffers=256MB [S4][S35]. | **Headline: "PostgreSQL 11 was found to be faster than MongoDB 4.0 in almost every benchmark."** Throughput was higher by dozens of percent up to one or two orders of magnitude on some tests. Latency was also lower on PostgreSQL [S132]. PostgreSQL depends heavily on the number of concurrent users and needs a pooler such as PgBouncer at high connection counts [S4][S37]. | **Dated, EDB-sponsored (PostgreSQL vendor), skewed toward PostgreSQL** [S4]. | Medium. It is the only source with an OLAP/jsonb part, but the versions are old and the queries are not tenant-scoped. The pooling finding applies to many tenants. |
| MongoDB Vs PostgreSQL (MongoDB resource page) [S27] | https://www.mongodb.com/resources/compare/mongodb-postgresql | Not extracted. Fetched 2026-10-23 UTC [S127]. | Feature and architecture comparison (BSON documents vs relational). I could not confirm any measured benchmark [S27]. | No numeric result captured | **Vendor marketing by MongoDB, skewed toward MongoDB** [S27]. | Low. Useful only for MongoDB's own claims. |
| MongoDB vs PostgreSQL: When NoSQL Actually Wins [2026] (Tech Insider) [S1] | https://tech-insider.org/mongodb-vs-postgresql-2026 | Not extracted. The title carries the year 2026. Fetched 2026-10-23 UTC [S127]. | Editorial comparison. I did not verify any original measurements. | No headline figure verified | Independent publisher. Sponsor and method unverified [S1]. | Medium. A recent decision guide, not primary evidence. |
| PostgreSQL vs. MongoDB in 2025: Which Database Should Power Your Next Project? (DEV Community, hamzakhan) [S3] | https://dev.to/hamzakhan/postgresql-vs-mongodb-in-2025-which-database-should-power-your-next-project-2h97 | **11 Aug 2025** (page date, from the verification review) [S3] | Blog comparison | No verified headline figure. Any sample figures are not reproducible. | Individual author, no sponsor found (independent, low rigor). | Low to medium |
| Postgres vs. MongoDB: a Complete Comparison in 2025 (Bytebase) [S2] | https://www.bytebase.com/blog/postgres-vs-mongodb | **27 Feb 2025** (page date, from the verification review) [S2] | Qualitative comparison of features and data model | No benchmark numbers verified | Bytebase sells database tooling, so there is a mild PostgreSQL lean (inferred) [S2]. | Low to medium |
| Can PostgreSQL with its JSONB column type replace MongoDB? (Medium, yurexus) [S14] | https://medium.com/@yurexus/can-postgresql-with-its-jsonb-column-type-replace-mongodb-30dc7feffaf3 | **2 Aug 2023** (page date, from the verification review). It is older than the preferred two-year window. [S14] | JSONB vs document model, insert and storage comparison | Per the verification review: **MongoDB was faster on inserts, and PostgreSQL JSONB used much larger storage** [S14]. I could not recover the numbers, so I give no ratio. | Independent blogger, no sponsor found, method not reproducible [S14]. | Medium to high for cost. A larger JSONB footprint argues against the 1.3 PostgreSQL storage-ratio default. Slower ingest matters for event writes. Both need measuring in the prototype. |

**S15 (MongoDB blog).** The verification review said S15 was a MongoDB blog. A lookup of S15 in sources/index.json this turn returned no entry (only S1, S4 and S27 were matched), and no S15 file is in sources/ [S134]. I therefore cannot give its title, URL, date or claims. If it is a MongoDB-authored blog, treat it as vendor-sponsored and skewed toward MongoDB. I take no figure from it.

Two other fetched pages are not benchmarks. S13 is a vendor page, "MongoDB Atlas Alternatives in Europe: GDPR-Compliant Options", useful only for the GDPR step [S13]. S6 is a bytebase.com manifest with no content for this step [S6].

**Freshness conclusion (revised, as of 22 Oct 2026).** S2 (27 Feb 2025) and S3 (11 Aug 2025) fall inside the preferred last-24-months window [S2][S3]. S1 is titled 2026 but has no confirmed date. S14 (2 Aug 2023) is outside the window [S14]. S4 is the only source with explicit test settings, and its versions (PostgreSQL 11, MongoDB 4.0) are old [S132]. The newest dated sources are qualitative blogs, so there is no fresh, rigorous benchmark. I found no newer source on the recency check.

**Takeaways**
1. **Vendor skew.** The only source with explicit test settings (S4) is sponsored by a PostgreSQL vendor and tests old versions [S4][S132]. S27 is MongoDB marketing [S27]. The rest are blogs with unverified methods. Treat every comparison as skewed, not as a verdict. The schema prototype on our own data replaces all of them.
2. **Wrong workload.** Nothing fetched measures tenant-filtered aggregation dashboards at our load. The task gives 5,000 queries per minute across all tenants, which is 5,000 / 60 = 83.3 QPS. The material is OLTP, a single-dataset OLAP test (S4), or qualitative [S4][S2][S3]. I found no independent analytics, time-series or multi-tenant benchmark.
3. **Cost-relevant signal.** S14 says MongoDB was faster on inserts but PostgreSQL JSONB storage was much larger [S14]. This affects the storage ratios in the cost model. Measure both ratios in the prototype. Use the task defaults (PostgreSQL 1.3, MongoDB 0.5 plus indexes) only until then, and label them estimates.
4. **Operational details outweigh headline ratios.** Connection pooling, tuning and instance size shaped the S4 outcome [S4]. We control all three in the prototype, so record p95 latency for tenant-scoped dashboard queries and event ingest on both databases.
5. **JSONB can cover document-style events.** S14 and S3 argue this, but none gives verified numbers for tenant-scoped aggregations [S14][S3]. If events are mostly relational, the JSONB storage penalty may matter less.

**Out of scope here.** The rework list also covers the AWS RDS/Aurora, Cloud SQL, AlloyDB and Atlas pricing steps (items 4-7). Those belong to the pricing steps and were not redone here. I did not check any price in this step.

**Not confirmed:** publication dates for S1, S4 and S27; the existence, title and URL of S15; numeric results for S14 and S27; and any independent time-series or multi-tenant analytics benchmark.
MISSING DATA: Publication dates for S1, S4 and S27 — page text and sources/index.json had no date
MISSING DATA: S15 (MongoDB blog) title, URL, date and claims — no S15 entry in sources/index.json and no S15 file in sources/
MISSING DATA: Numeric insert and storage figures from S14 — not captured
MISSING DATA: Independent analytics, time-series and multi-tenant PostgreSQL vs MongoDB benchmarks — not found within the turn budget

## Step 2: Gather AWS managed PostgreSQL pricing (RDS, Aurora)

## AWS RDS for PostgreSQL and Aurora PostgreSQL pricing (captured 2026-10-22, America/Chicago)

**Bottom line.** The cost model still has no verified AWS compute price (as of 2026-10-22). RDS storage, extra-IOPS and backup rates have third-party figures only. Instance, Aurora, eu-central-1, transfer and support prices are missing or are memory estimates tagged [unverified]. Review issue 5 could not be fixed with the tools available.

**Date settled on: 2026-10-22.** The AWS pages were fetched on 2026-10-22. The Aurora page was fetched at 2026-10-23T04:13 UTC, which is 2026-10-22 in Chicago [S51]. I tried the AWS bulk price-list JSON endpoint for RDS PostgreSQL Multi-AZ, https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/rds/USD/current/rds-postgresql-ma-ref.json. It returned HTTP 404 on 2026-10-22, so no newer or machine-readable figure was found. I made no other newer-value search.

**Sources and how far to trust them**
- **Official AWS pages** (RDS https://aws.amazon.com/rds/postgresql/pricing/ [S39]; Aurora https://aws.amazon.com/rds/aurora/pricing/ [S51]), both fetched 2026-10-22. The saved text has no per-instance, per-GB or per-I/O USD tables because AWS renders them with JavaScript. The only USD figure read there is the Extended Support surcharge (R1).
- **Third-party guide** "RDS Pricing Calculator" on usage.ai. Its page text shows "Updated June 19, 2026" [S140]. It is a secondary source, not a vendor price page. It does not state a region in the lines I read, so treat it as likely us-east-1 and unconfirmed.
- **Not used.** The `prices.csv` files S40 and S41 are AWS SMS price lists, not database prices [S54].
- **[unverified]** means the figure comes from my own memory of AWS list prices, not from a page read in this run. These are placeholders only. Replace them with AWS Pricing Calculator or Price List API values before the model is final.

| Row | Service | Instance / unit | Region | USD price (as of date) | Status | URL | Date captured |
|---|---|---|---|---|---|---|---|
| R1 | RDS PostgreSQL | Extended Support surcharge for out-of-support major versions, per vCPU-hour | us-east-2 (AWS worked example) | $0.100 per vCPU-hr from 2025-03-01 to 2027-02-28, then $0.200 from 2027-03-01, as of 2026-10-22 [S52] | Verified on official page | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R2 | RDS PostgreSQL | db.r6g.4xlarge (16 vCPU / 128 GB), Multi-AZ, per hour | us-east-1 | Not captured. Rough range only: about $2–4 per hour, as of 2026-10-22 | Missing; estimate | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 (table absent) [S39] |
| R3 | RDS PostgreSQL | db.r6g.8xlarge (32 vCPU / 256 GB), Multi-AZ, per hour | us-east-1 | Not captured. Price scales roughly with vCPU, so about 2x R2, as of 2026-10-22 | Missing; estimate | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R4 | RDS PostgreSQL | Same two classes, Multi-AZ | eu-central-1 | Not captured; no estimate offered. Do not reuse us-east-1 figures for Frankfurt. | Missing | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R5a | RDS PostgreSQL | gp3 storage, per GB-month. Baseline of 3,000 IOPS and 125 MB/s included [unverified]. | Region not stated; likely us-east-1 | $0.115 per GB-month, as of 2026-06-19 (page update date) [S140] | Third-party, secondary source | https://www.usage.ai (page "RDS Pricing Calculator", saved as S116) | 2026-10-22 [S140] |
| R5b | RDS PostgreSQL | gp3 storage, Multi-AZ, per GB-month | us-east-1 | 2 x $0.115 = $0.23 per GB-month, as of 2026-10-22. It assumes Multi-AZ doubles the single-AZ rate [unverified], which I have not checked. | Derived estimate | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R6 | RDS PostgreSQL | Extra provisioned IOPS above the gp3 baseline, per IOPS-month | Region not stated | $0.02 per IOPS-month, as of 2026-06-19 [S140]. io1/io2 rates not captured. | Third-party, secondary source | https://www.usage.ai (S116) | 2026-10-22 [S140] |
| R7 | RDS PostgreSQL | Backup storage above 100% of provisioned DB size (free up to that point), per GB-month | Region not stated | about $0.095 per GB-month, as of 2026-06-19 [S140] | Third-party, secondary source | https://www.usage.ai (S116) | 2026-10-22 [S140] |
| R8 | RDS PostgreSQL | Cross-region data transfer out, per GB | eu-central-1 to us-east-1 | about $0.02 per GB, as of 2026-10-22 | Estimate | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R9 | Aurora PostgreSQL | db.r6g.4xlarge or db.r7g.4xlarge, per hour. The HA equivalent is a second instance at the same hourly rate. | us-east-1 and eu-central-1 | Not captured | Missing | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S51] |
| R10 | Aurora PostgreSQL | Aurora Standard storage, per GB-month | us-east-1 | about $0.10, as of 2026-10-22 | Estimate | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 (table absent) [S51] |
| R11 | Aurora PostgreSQL | Aurora Standard I/O, per million requests | us-east-1 | about $0.20, as of 2026-10-22 | Estimate | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S51] |
| R12 | Aurora PostgreSQL | Aurora I/O-Optimized storage, per GB-month. No per-I/O charge; the instance price carries a premium. | us-east-1 | about $0.225, as of 2026-10-22 | Estimate | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S57] |
| R13 | Aurora PostgreSQL | Backup storage beyond the free allowance, per GB-month | us-east-1 | about $0.021, as of 2026-10-22 | Estimate | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S76] |
| R14 | Aurora PostgreSQL | Cross-region replication or transfer, per GB | eu-central-1 to us-east-1 | Not captured; assume the same as R8 (about $0.02, as of 2026-10-22) | Missing; estimate | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S51] |
| R15 | AWS Support (RDS and Aurora) | Business, Enterprise On-Ramp, Enterprise | Global | Not captured. Page not fetched. | Missing | https://aws.amazon.com/premiumsupport/pricing/ | Not fetched (no capture date) |

**Check against done_when**
- RDS has compute (R2–R4), storage (R5a/R5b) and I/O (R6) rows. Aurora has compute (R9), storage (R10, R12) and I/O (R11) rows.
- Backup (R7, R13) and transfer (R8, R14) rows are present.
- Every row has a URL. R1–R14 have a capture date of 2026-10-22; R15 was not fetched. Only R1 is verified from an official AWS page. R5a, R6 and R7 are third-party figures.
- Aurora, eu-central-1, transfer and support rows are still estimates or gaps.

**Cost-model guidance**
- Load every row into the `Pricing` sheet with a status flag (verified / third-party / estimate / missing). Do not present estimates as verified.
- Compute needs an instance price. R2 and R3 are placeholders. The headline AWS monthly figures must be labelled "estimate" until replaced.
- Sizing: 50 tenants x 200 GB = 10,000 GB raw (from the task). The PostgreSQL storage ratio is an assumed default of 1.3 [unverified] until the prototype measures one. The default gives 10,000 GB x 1.3 = 13,000 GB. Peak load is 5,000 / 60 = 83.3 QPS.
- Run Aurora Standard and I/O-Optimized side by side. Aurora I/O cost depends on the prototype's measured I/O rate.
- I believe 13,000 GB (the calculation above) fits on one instance in either service. The RDS limit is about 64 TiB and the Aurora limit about 128 TiB, as of 2026-10-22. Confirm both limits in the AWS docs.
- R1 shows that the PostgreSQL major version affects cost. Use a current major version to avoid the Extended Support surcharge.
BLOCKED: AWS Pricing Calculator / Price List API — verified per-instance, Aurora, eu-central-1 and transfer prices could not be read; the AWS pages render prices with JavaScript and the bulk price-list JSON URL returned HTTP 404
BLOCKED: Fetch of AWS Support pricing page — not performed within the turn limit
MISSING DATA: RDS PostgreSQL Multi-AZ hourly price for 16-64 vCPU classes, us-east-1 and eu-central-1 — AWS RDS pricing page [S39] (table absent) and price-list JSON (404)
MISSING DATA: Aurora PostgreSQL instance hourly prices, us-east-1 and eu-central-1 — AWS Aurora pricing page [S51] (table absent)
MISSING DATA: Verified Aurora storage, I/O and backup prices, and RDS Multi-AZ storage, io1/io2, backup and cross-region transfer prices — AWS pages [S39][S51]; only third-party or [unverified] figures found
MISSING DATA: All eu-central-1 prices — not found, no estimate offered
MISSING DATA: AWS Support plan prices — https://aws.amazon.com/premiumsupport/pricing/ not fetched

## Step 3: Gather GCP managed PostgreSQL pricing (Cloud SQL, AlloyDB)

**GCP managed PostgreSQL pricing (Cloud SQL and AlloyDB): PARTIAL.**

**Capture date and freshness.** Every row is "as of" 2026-10-22 Chicago time, which is today. The Cloud SQL page was fetched at 2026-10-23T04:15 UTC [S63]. The AlloyDB page was fetched at 2026-10-23T04:40 UTC [S142]. I found no newer or dated version of either page. Both are live vendor price pages, so "as of" means the fetch date, not a publication date. I did not make a further search for a newer value because I ran out of turns.

**Caveats**
- **Cloud SQL columns and region.** The text dump of the Cloud SQL table does not show the region or the column headers [S66]. I read the first price column as on-demand Enterprise edition. I read the next two as one-year and three-year committed-use discounts, based on a "Cloud SQL CUD" label [S65]. This is inferred. The default region is not confirmed as us-central1, and no europe-west3 Cloud SQL compute price was captured.
- **AlloyDB region mapping.** Frankfurt (europe-west3) and Iowa (us-central1) both appear in the region lists above the AlloyDB compute tables [S146]. The dump does not show which price table belongs to which region group, so I did not assign compute prices to a region.
- **Month length.** Monthly figures use 365 × 24 ÷ 12 = 730 hours per month. This is my assumption, not a page figure. One GB is treated as one GiB.
- **Cloud SQL memory ratio.** The Enterprise maximum is 96 vCPU and 624 GiB [S67]. That gives 624 ÷ 96 = 6.5 GiB per vCPU. So 16 vCPU gets 16 × 6.5 = 104 GiB, and 32 vCPU gets 32 × 6.5 = 208 GiB.
- **AlloyDB memory ratio.** I assumed 8 GiB per vCPU [unverified]. That gives 16 vCPU with 128 GiB, and 32 vCPU with 256 GiB.
- **Machine classes.** The 16 and 32 vCPU classes are my picks from the 16–64 vCPU range in the task.

| Service | Machine / unit | Region | USD price | URL | Date captured | Status |
|---|---|---|---|---|---|---|
| Cloud SQL PG (Enterprise) | vCPU, single zone, per hour | default table; region not confirmed | $0.0413 [S66] | https://cloud.google.com/sql/docs/postgres/pricing | as of 2026-10-22 [S63] | read from page; column and region inferred |
| Cloud SQL PG | Memory, single zone, per GiB-hour | same | $0.007 [S66] | same | as of 2026-10-22 [S63] | same |
| Cloud SQL PG | HA vCPU, per hour | same | $0.0826 [S66] | same | as of 2026-10-22 [S63] | same; HA is exactly double the single-zone rate ($0.0413 [S66] × 2 = $0.0826) |
| Cloud SQL PG | HA memory, per GiB-hour | same | $0.014 [S66] | same | as of 2026-10-22 [S63] | same; double the single-zone $0.007 [S66]; not re-verified against a labelled region table |
| Cloud SQL PG | Committed-use columns (assumed one-year / three-year): vCPU per hour; HA vCPU per hour | same | vCPU $0.030975 / $0.019824 [S66]; HA vCPU $0.06195 / $0.039648 [S66] | same | as of 2026-10-22 [S63] | column meaning inferred [S65] |
| Cloud SQL PG | Derived: 16 vCPU / 104 GiB, single zone, per month | same | (16 × $0.0413 [S66] + 104 × $0.007 [S66]) × 730 = 1.3888 × 730 ≈ $1,014 | same | as of 2026-10-22 [S63] | estimate derived from the rows above |
| Cloud SQL PG | Derived: 16 vCPU / 104 GiB, HA, per month | same | (16 × $0.0826 [S66] + 104 × $0.014 [S66]) × 730 = 2.7776 × 730 ≈ $2,028 | same | as of 2026-10-22 [S63] | estimate |
| Cloud SQL PG | Derived: 32 vCPU / 208 GiB, HA, per month | same | (32 × $0.0826 [S66] + 208 × $0.014 [S66]) × 730 = 5.5552 × 730 ≈ $4,055 | same | as of 2026-10-22 [S63] | estimate |
| Cloud SQL PG | SSD storage, per GB-month | europe-west3 / us-central1 | NOT CAPTURED | same | as of 2026-10-22 [S63] | the page says storage depends on the region dropdown [S67]; values are not in my extract |
| Cloud SQL PG | Backup storage, per GB-month | europe-west3 / us-central1 | NOT CAPTURED | same | as of 2026-10-22 [S63] | not read |
| Cloud SQL PG | Cross-region replica / network egress, per GB | europe-west3 to us-central1 | NOT CAPTURED | same | as of 2026-10-22 [S63] | not read; needs the GCP network pricing page |
| Cloud SQL PG | I/O charge | any | none seen; only provisioned IOPS and throughput above a baseline of 3,000 IOPS [S67] | same | as of 2026-10-22 [S63] | partial; extract truncated |
| Cloud SQL PG | Support plan | n/a | NOT CAPTURED | n/a (needs the Google Cloud support pricing page) | as of 2026-10-22 | missing |
| AlloyDB (N2 / C4A series) | vCPU per hour: on-demand / one-year / three-year | region group unconfirmed | $0.06608 / $0.04956 / $0.0317184 [S146] | https://cloud.google.com/alloydb/pricing | as of 2026-10-22 [S142] | read from page; region mapping unconfirmed |
| AlloyDB (N2 / C4A series) | Memory per GiB-hour: on-demand / one-year / three-year | same | $0.0112 / $0.0084 / $0.005376 [S146] | same | as of 2026-10-22 [S142] | same |
| AlloyDB (C4 series) | vCPU per hour: on-demand / one-year / three-year | region group unconfirmed | $0.091 / $0.06825 / $0.04368 [S146] | same | as of 2026-10-22 [S142] | same |
| AlloyDB (C4 series) | Memory per GiB-hour: on-demand / one-year / three-year | same | $0.0105 / $0.007875 / $0.00504 [S146] | same | as of 2026-10-22 [S142] | same |
| AlloyDB | Another memory table, per GiB-hour (series and region group not identified) | unconfirmed | $0.0175 / $0.013125 / $0.0084 [S146] | same | as of 2026-10-22 [S142] | do not use until series and region are identified |
| AlloyDB | Derived: 16 vCPU / 128 GiB (N2/C4A on-demand), per month per instance | unconfirmed | (16 × $0.06608 [S146] + 128 × $0.0112 [S146]) × 730 = 2.49088 × 730 ≈ $1,818 | same | as of 2026-10-22 [S142] | estimate; HA price and standby charging not confirmed |
| AlloyDB | Derived: 32 vCPU / 256 GiB (same basis), per month per instance | unconfirmed | (32 × $0.06608 [S146] + 256 × $0.0112 [S146]) × 730 = 4.98176 × 730 ≈ $3,637 | same | as of 2026-10-22 [S142] | estimate; HA not confirmed |
| AlloyDB | Per-vCPU-hour pair; the second value is about double the first. The heading is not visible in my extract. It may be an Extended Support surcharge, since the page has that section [S146]. | europe-west3 | $0.083 / $0.165 per vCPU-hour [S145] | same | as of 2026-10-22 [S142] | meaning unconfirmed; do not use as a compute price |
| AlloyDB | same pair | us-central1 | $0.07 / $0.14 per vCPU-hour [S145] | same | as of 2026-10-22 [S142] | same |
| AlloyDB | SSD storage capacity, per GiB-hour; two values seen in two region groups | region mapping unconfirmed | $0.000232877 [S146] × 730 ≈ $0.17 per GB-month; $0.000465753 [S145] × 730 ≈ $0.34 per GB-month | same | as of 2026-10-22 [S142] | derived; the higher value is double the lower, likely a region-group difference |
| AlloyDB | HDD storage capacity, per GiB-hour | same | $0.000123288 [S146] × 730 ≈ $0.09 per GB-month; $0.000246575 [S145] × 730 ≈ $0.18 per GB-month | same | as of 2026-10-22 [S142] | derived; region mapping unconfirmed |
| AlloyDB | Hyperdisk Balanced capacity, per GiB-hour | one region group | $0.000157534 [S145] × 730 ≈ $0.115 per GB-month | same | as of 2026-10-22 [S142] | derived; region unconfirmed |
| AlloyDB | Backup storage ("Backups (used)"), per GiB-hour; same value in both region groups | both groups seen | $0.000109589 [S145][S146] × 730 ≈ $0.08 per GB-month | same | as of 2026-10-22 [S142] | derived from the page |
| AlloyDB | Cross-region replica / network egress, per GB | europe-west3 to us-central1 | NOT CAPTURED | https://cloud.google.com/alloydb/pricing (network section not read) | as of 2026-10-22 | missing |
| AlloyDB | Support plan | n/a | NOT CAPTURED | n/a | as of 2026-10-22 | missing |

**Use in the cost model**
- AlloyDB backup of about $0.08 per GB-month is the only backup figure here. It is derived, and the AlloyDB SSD rates are derived too.
- For AlloyDB SSD, use about $0.17 per GB-month for the low case and about $0.34 per GB-month for the high case. The region mapping is unconfirmed.
- Mark all GCP egress and support lines, and Cloud SQL storage and backup lines, as "missing" or "estimate". Do not invent values.
- Treat all derived monthly compute rows as estimates until the region and column are confirmed.
- Tie AlloyDB vCPU and memory rates to the instance class, not to a region, until the mapping is confirmed.

**Next fetches, if turns allow:** the Cloud SQL storage section for europe-west3 and us-central1, the GCP network egress page, the Google Cloud support pricing page, and the AlloyDB network section.
MISSING DATA: Cloud SQL PostgreSQL SSD storage $/GB-month for europe-west3 and us-central1 — pricing page dump S63 truncated, region dropdown not rendered; grep of S63 found no storage rows
MISSING DATA: Cloud SQL backup storage $/GB-month — not found in S63
MISSING DATA: GCP cross-region replica and network egress $/GB (Cloud SQL and AlloyDB) — network pricing page not fetched
MISSING DATA: GCP support plan pricing — Google Cloud support page not fetched
MISSING DATA: Region and column headers of the Cloud SQL compute table — S66 shows unlabelled price columns
MISSING DATA: Cloud SQL europe-west3 compute prices — only one default-region table seen
MISSING DATA: AlloyDB compute price mapping to europe-west3 versus us-central1 — S142 text dump does not show which table belongs to which region
MISSING DATA: AlloyDB HA pricing and standby charging, and the meaning of the per-vCPU-hour pairs for europe-west3 and us-central1 — headings not visible in my extract

## Step 4: Gather MongoDB Atlas pricing on AWS and GCP

**Atlas Dedicated-Tier Pricing**
Source: MongoDB list price page, https://www.mongodb.com/pricing [S76]. Figures captured/verified 2026-10-22. 
Note: The source [S76, S151] indicates these tiers are available on AWS, Google Cloud, and Azure, but the provided pricing table does not list separate rates by cloud provider or region. The figures below represent the global list price.

| Cloud | Tier | vCPU / RAM | Region | $/hour (per node, as of 2026-10-22) | Storage limit (per node, as of 2026-10-22) | Backup / Transfer | URL | Date captured |
|---|---|---|---|---|---|---|---|---|
| AWS/GCP | M40 | 4 vCPU / 16 GB [S76] | List Price | $1.04 [S76] | 80 GB–1 TB [S76] | Egress: $0.12/GB [S150] | https://www.mongodb.com/pricing | 2026-10-22 |
| AWS/GCP | M50 | 8 vCPU / 32 GB [S76] | List Price | $2.00 [S76] | 160 GB–4 TB [S76] | Egress: $0.12/GB [S150] | https://www.mongodb.com/pricing | 2026-10-22 |
| AWS/GCP | M60 | 16 vCPU / 64 GB [S76] | List Price | $3.95 [S76] | 320 GB–4 TB [S76] | Egress: $0.12/GB [S150] | https://www.mongodb.com/pricing | 2026-10-22 |
| AWS/GCP | M80 | 32 vCPU / 128 GB [S76] | List Price | $7.30 [S76] | 750 GB–4 TB [S76] | Egress: $0.12/GB [S150] | https://www.mongodb.com/pricing | 2026-10-22 |
| AWS/GCP | M140 | 48 vCPU / 192 GB [S76] | List Price | $10.99 [S76] | 1–4 TB [S76] | Egress: $0.12/GB [S150] | https://www.mongodb.com/pricing | 2026-10-22 |
| AWS/GCP | M200 | 64 vCPU / 256 GB [S151] | List Price | $14.59 [S151] | 1.5–4 TB [S151] | Egress: $0.12/GB [S150] | https://www.mongodb.com/pricing | 2026-10-22 |
| AWS/GCP | M400 | 64 vCPU / 488 GB [S151] | List Price | $22.40 [S151] | 3–4 TB [S151] | Egress: $0.12/GB [S150] | https://www.mongodb.com/pricing | 2026-10-22 |

**Sharding Note**
- **Volume Requirement:** 50 tenants x 200 GB = 10,000 GB (10 TB) raw data.
- **Storage Limit:** The maximum storage per node for the M-series dedicated tiers is 4 TB [S151].
- **Sharding Necessity:** 
    - For raw data (10 TB), at least ceil(10/4) = 3 shards are required.
    - If the 0.5 compression ratio (role-card default) is applied, data is 5,000 GB. This still exceeds the 4 TB per-node limit, requiring at least 2 shards.
- **Alternative:** Atlas Infinite (Public Preview) supports up to 128 TB per HA shard [S150], which would allow the entire 10 TB workload to reside on a single shard.
- **Conclusion:** For standard M-series tiers, 6-10 TB of data **requires sharding** (minimum 2-3 shards) to stay within the 4 TB per-node limit.

**Unconfirmed / Missing Data**
- **Regional/Cloud Split:** No specific price variance between AWS vs GCP or US vs EU was found in the source [S76].
- **Backup:** Cloud Backup $/GB-month was not captured.
- **Support:** Support plan pricing was not captured (URL provided in [S151] but not detailed in excerpts).
MISSING DATA: Atlas regional price differences (EU vs US) — mongodb.com/pricing [S76] did not specify regional variance for dedicated tiers
MISSING DATA: Atlas cloud-provider price differences (AWS vs GCP) — mongodb.com/pricing [S76] did not specify provider variance for dedicated tiers
MISSING DATA: Atlas Cloud Backup $/GB-month — not found in mongodb.com/pricing [S76] or excerpts [S150, S151]
MISSING DATA: Atlas support plan pricing — URL provided [S151] but prices not captured in excerpts

## Step 5: Prototype and test the event and dashboard schema in PostgreSQL

**NOT EXECUTED: this sandbox has no PostgreSQL server and no psycopg2, so I took no PostgreSQL measurements. No benchmark number below is a measurement. results_postgres.json exists in the workspace [S81] and states NOT EXECUTED with the reason.**

## 1. Environment check (measured, run on 22 Oct 2026)
- Command: `which psql postgres pg_ctl initdb mongod; python3 -c 'import psycopg2'`.
- Result [S78]: `which rc=1`, so none of those binaries is on PATH. Python raised `ModuleNotFoundError: No module named 'psycopg2'`.
- Two earlier probes were refused by the sandbox as unsafe: the /usr/lib/postgresql path and docker. I could not look for embedded or alternative binaries there.
- There is no network, so nothing could be installed.
- As a result, I did no load, no 50+ warm runs per query, no mixed read/write run at concurrency 8/32/84, and no bytes-on-disk measurement.

## 2. Files in the workspace
- `gen_data.py` [S79]. This is the shared seeded generator (seed 42). Usage: `python3 gen_data.py N_EVENTS OUTDIR`.
  - It writes events.csv, events.jsonl, dashboards.jsonl and manifest.json. Both databases are meant to load these same files.
  - Design: 50 tenants with Zipf-like sizes (largest about 10x the median), 90 days of data ending 2026-10-22 UTC, 20 event types, about 10k users per tenant, and 5-15 properties per event nested 1 level. Amount is nullable.
  - I did not run it. Its row counts and tenant skew are unverified.
- `schema_postgres.sql` [S80]. Only the head and the RLS tail were visible to me. The partition, index and dashboards DDL in the middle was not shown to me, so I cannot quote it here. Open the file and review it before use.
- `results_postgres.json` [S81]. It holds status NOT EXECUTED, the reason, and null for every metric.
- **`bench_pg.py` was NOT written to disk.** The JSON's `scripts` list names it, but the file does not exist. Section 3 is a design only.

### DDL as I could confirm it from [S80]
```sql
CREATE TABLE events (
  event_id    bigint       NOT NULL,
  tenant_id   int          NOT NULL,
  occurred_at timestamptz  NOT NULL,
  event_type  text         NOT NULL,
  user_id     text         NOT NULL,
  session_id  text         NOT NULL,
  properties  jsonb        NOT NULL,
  amount      numeric(14,2),
  PRIMARY KEY (tenant_id, occurred_at, event_id)  -- PK must contain the partition key
) PARTITION BY RANGE (occurred_at);
-- monthly range partitions, tenant_id-leading index, GIN on properties (JSONB),
-- BRIN on occurred_at, and the dashboards table (widgets JSONB) are described in the
-- file header, but I did not see their exact text. See schema_postgres.sql.

ALTER TABLE events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboards ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_iso ON events     USING (tenant_id = current_setting('app.tenant_id')::int);
CREATE POLICY tenant_iso ON dashboards USING (tenant_id = current_setting('app.tenant_id')::int);
-- usage: SET ROLE app_user; SET app.tenant_id = '7';
```

## 3. Planned bench_pg.py (design only, not delivered, not run)
- Load events.csv with COPY, then ANALYZE.
- Q1: `date_trunc('hour',occurred_at), event_type, count(*)` for one tenant over the last 24 hours, grouped by hour and type.
- Q2: `count(DISTINCT user_id)` per day over 30 days.
- Q3: top 10 event types over 7 days.
- Q4: 3-step funnel per session over 7 days, using `bool_or(event_type=...)` per step.
- Q5: `properties @> '{"k":"v"}'` with `sum(amount)` by day.
- Q6: dashboard by id, with widgets as JSONB.
- Q7: `execute_values` insert of 1,000 events.
- Run each query 50+ times warm and report p50/p95/p99.
- Run an 80/20 read/write mix with threads at concurrency 8, 32 and 84 for a fixed duration.
- Compute size as `pg_total_relation_size` divided by the raw CSV/JSONL bytes.

## 4. Results table (all NOT EXECUTED: no server)
| Query | p50 ms | p95 ms | p99 ms | Throughput |
|---|---|---|---|---|
| Q1 events/hour 24h by type | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q2 daily unique users 30d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q3 top 10 types 7d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q4 3-step funnel 7d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q5 JSONB filter + sum(amount)/day | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q6 dashboard + widgets | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q7 batch insert 1,000 events | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Mixed 80/20 at concurrency 8/32/84 | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |

Storage ratio to raw: NOT EXECUTED.

## 5. results_postgres.json
It exists [S81]. Its fields:
- `status`: "NOT EXECUTED"
- `reason`: no binaries, no psycopg2, no network, and the two refused probes
- `environment`: sandbox without PostgreSQL server binaries; python_driver null; network none
- Null values for postgres_version, rows, load_time_s, bytes_on_disk, raw_bytes and ratio_to_raw
- Q1 to Q7: each has p50, p95 and p99 set to null
- `throughput_qps` for c8, c32 and c84: null
- `scripts`: lists gen_data.py, schema_postgres.sql and bench_pg.py. bench_pg.py was not actually written (see section 2).

## 6. Findings and caveats
- The partitioned events table has the composite primary key `(tenant_id, occurred_at, event_id)` [S80]. PostgreSQL requires the primary key to include the partition column [unverified]. Event ids are therefore unique only per `(tenant_id, occurred_at)` pair, not globally.
- Row-level security keyed on `current_setting('app.tenant_id')` gives tenant isolation inside one shared schema [S80]. With pooled connections, the setting must be set per transaction (`SET LOCAL`) [unverified]. The RLS overhead is untested.
- JSONB with a GIN index suits Q5-style property filters [unverified]. Index size and write amplification, which affect Q7, are unmeasured and remain an open risk.
- Nothing was run, so there is nothing to extrapolate. Even a 1M-5M-event test would not prove behaviour at 10 TB (50 tenants x 200 GB). At that scale cache residency, partition count, vacuum and index sizes change.
- After a real run, this is what I would expect to carry over:
  - Bytes-per-event ratios would feed the cost model reasonably well.
  - Small-scale latencies are indicative only.
  - Concurrency throughput does not transfer, because it depends on instance size.
- Not verified: the generator's output, the SQL syntax (no static parse was run), and any comparison with MongoDB.
- To finish, use a machine with PostgreSQL 16+ and psycopg2:
  1. Run `python3 gen_data.py 2000000 data`.
  2. Run `psql -f schema_postgres.sql`.
  3. Write and run bench_pg.py as designed in section 3.
BLOCKED: PostgreSQL server binaries (postgres/initdb/pg_ctl/psql) and psycopg2 — could not start a database, load data, time Q1-Q7, run the concurrency tests or measure on-disk size
BLOCKED: local:Write — bench_pg.py was not written to disk within the turn budget (design only in the output)
MISSING DATA: Measured Q1-Q7 p50/p95/p99, throughput at concurrency 8/32/84, load time and storage ratio for PostgreSQL — no runnable server in the sandbox [S78]
MISSING DATA: Exact text of the partition, index and dashboards DDL in schema_postgres.sql — only the head and the RLS tail were visible in the tool output [S80]

## Step 6: Prototype and test the event and dashboard schema in MongoDB

**NOT EXECUTED: no MongoDB benchmark was run, so this step has no measurements. Every metric in results_mongodb.json is null. The reason is that the sandbox has no MongoDB server and no Python driver. I checked this on 22 Oct 2026 and it is confirmed [S104].**

## 1. Environment check (measured, 22 Oct 2026)
- Probe [S104]: `command -v` found no mongod, no mongosh, no mongo and no mongos. All four are reported MISSING.
- Python [S104]: `ModuleNotFoundError: No module named 'pymongo'`. The same error appears for `mongomock`, so there is no in-process fake either.
- There is no network, so nothing could be installed. Step 5 found the same for PostgreSQL: no binaries and no psycopg2 [S78].
- Static check [S104]: `python3 -m py_compile mongo_bench.py gen_data.py` printed COMPILE_OK. This supersedes my earlier caveat. The syntax of both scripts is valid, but neither has run, so their behaviour is untested.
- File sizes [S104]: mongo_bench.py is 11,079 bytes and results_mongodb.json is 1,554 bytes.
- Not done: no load, no 50+ warm runs per query, no mixed read/write run at concurrency 8/32/84, and no bytes-on-disk measurement.

## 2. Files in the workspace
- `gen_data.py`: the shared seed-42 generator from step 5 [S79]. It compiles [S104] but has not been run, so its row counts and tenant skew are unverified. Use `python3 gen_data.py 2000000 data`. It writes events.jsonl and dashboards.jsonl, which MongoDB should load. Step 5 loads the same files, so the data would be identical.
- `mongo_bench.py`: written as [S101] and compiles [S104]. It is meant to create the collections, load the data, time Q1-Q7, run the mixed workload and write the results JSON. I could not re-read it after writing it. The design below is the intent and may differ in detail from the file, so review the file before use.
- `results_mongodb.json` [S103]: status NOT EXECUTED, with null for every metric. Its text says there is no mongod and no pymongo, and [S104] now supports both statements.

## 3. Schema and collection setup (code, not executed)
```javascript
// Tenant isolation choice: ONE shared collection, tenant_id as the leading key of every index.
// 50 tenants is too few to justify database-per-tenant. The largest tenants could get dedicated collections.
// Isolation is enforced in the app/query layer. Atlas has no row-level security, unlike Postgres RLS (step 5 DDL [S80]).
// Use a mandatory tenant-filter wrapper.
db.createCollection("events", {
  validator: {$jsonSchema: {
    bsonType: "object",
    required: ["tenant_id","ts","event_type","user_id","session_id","properties"],
    properties: {
      tenant_id:{bsonType:"int"}, ts:{bsonType:"date"},
      event_type:{bsonType:"string"}, user_id:{bsonType:"string"},
      session_id:{bsonType:"string"}, properties:{bsonType:"object"},
      amount:{bsonType:["decimal","null"]}
    }}}
});
db.events.createIndex({tenant_id:1, ts:-1});                    // main access path
db.events.createIndex({tenant_id:1, event_type:1, ts:-1});      // Q3
db.events.createIndex({tenant_id:1, session_id:1, ts:1});       // Q4
db.events.createIndex({tenant_id:1, "properties.k":1, ts:-1});  // Q5 (one hot property)

// Variant to test: time-series collection
db.createCollection("events_ts", {timeseries:{timeField:"ts", metaField:"tenant_id", granularity:"hours"}});
// Caveat: time-series collections limit updates, deletes and some index types [unverified].

db.createCollection("dashboards", {validator:{$jsonSchema:{
  bsonType:"object", required:["tenant_id","name","owner","widgets","updated_at"],
  properties:{ widgets:{bsonType:"array", items:{bsonType:"object",
    required:["widget_id","type","query_def"]}}}}}});
db.dashboards.createIndex({tenant_id:1, _id:1});
// Widgets are embedded, so Q6 is a single-document read.
```

## 4. Aggregation pipelines (design, not executed)
```javascript
// Q1 events per hour by type, last 24h
[{$match:{tenant_id:T, ts:{$gte:now24h}}},
 {$group:{_id:{h:{$dateTrunc:{date:"$ts",unit:"hour"}}, t:"$event_type"}, n:{$sum:1}}}]
// Q2 daily unique users, 30d
[{$match:{tenant_id:T, ts:{$gte:now30d}}},
 {$group:{_id:{d:{$dateTrunc:{date:"$ts",unit:"day"}}, u:"$user_id"}}},
 {$group:{_id:"$_id.d", users:{$sum:1}}}]
// Q3 top 10 event types, 7d
[{$match:{tenant_id:T, ts:{$gte:now7d}}},{$group:{_id:"$event_type",n:{$sum:1}}},{$sort:{n:-1}},{$limit:10}]
// Q4 3-step funnel per session, 7d
[{$match:{tenant_id:T, ts:{$gte:now7d}, event_type:{$in:[A,B,C]}}},
 {$group:{_id:"$session_id", s:{$addToSet:"$event_type"}}},
 {$match:{s:{$all:[A,B,C]}}},{$count:"completed"}]
// This checks that all three steps occurred, not their order. An ordered funnel needs min(ts) per step.
// Q5 JSON property filter + sum(amount)/day
[{$match:{tenant_id:T, "properties.k":V, ts:{$gte:now30d}}},
 {$group:{_id:{$dateTrunc:{date:"$ts",unit:"day"}}, total:{$sum:"$amount"}}}]
// Q6  db.dashboards.findOne({tenant_id:T, _id:D})
// Q7  db.events.insertMany(batch_of_1000, {ordered:false})
```

## 5. Results table (all NOT EXECUTED, no server)
| Query | p50 ms | p95 ms | p99 ms | Throughput |
|---|---|---|---|---|
| Q1 events/hour by type, 24h | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q2 daily unique users, 30d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q3 top 10 event types, 7d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q4 3-step funnel, 7d | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q5 JSON filter + sum(amount)/day | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q6 dashboard with widgets | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Q7 insert 1,000 events | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Mixed read/write workload at concurrency 8 / 32 / 84 | n/a | n/a | n/a | NOT EXECUTED |

Load time, bytes on disk and ratio to raw: NOT EXECUTED. All are null in results_mongodb.json [S103].

## 6. Findings and caveats
- **No MongoDB performance claim can be made from this step.** The PostgreSQL side is also NOT EXECUTED (step 5). There is no like-for-like comparison, so the recommendation memo must not cite benchmark numbers from these prototypes.
- **Ergonomics (design judgement, not measured):**
  - Embedded widgets make Q6 a single-document read.
  - Q2 and Q4 need `$group` aggregation stages that can be memory-heavy, so `allowDiskUse` may be needed [unverified].
  - Exact distinct-user counting (Q2) is expensive in both databases.
- **Tenant isolation:** MongoDB has no row-level security. Isolation depends on application code always adding `tenant_id`, which is a real risk for a 12-person team. Postgres RLS (step 5 DDL [S80]) is stronger on this point. Atlas offers database-level roles, so database-per-tenant is the stronger-isolation option.
- **Time-series option:** untested here. Its update and delete limits matter for GDPR erasure requests.
- **Scripts:** mongo_bench.py and gen_data.py pass a syntax compile [S104] but have never been executed. Treat them as unproven.
- **Extrapolation:** nothing was run, so nothing extrapolates. Even a 1M-5M event test would not prove behaviour at 10 TB (50 x 200 GB = 10,000 GB). If run, bytes-per-document ratios would feed the cost model reasonably well. Small-scale latencies would be indicative only. Concurrency throughput depends on the Atlas tier and would not transfer.
- **To finish:** on a machine with a current mongod and pymongo [unverified], run `python3 gen_data.py 2000000 data`, review mongo_bench.py, run `python3 mongo_bench.py`, and keep the JSON it writes.
BLOCKED: MongoDB server (mongod/mongosh) and pymongo driver, local sandbox — could not start a server, load data, run Q1-Q7, run the concurrency tests or measure on-disk size
MISSING DATA: Measured MongoDB Q1-Q7 p50/p95/p99, throughput at concurrency 8/32/84, load time, bytes on disk and ratio to raw — no runnable server in the sandbox [S104]

## Step 7: Assess GDPR residency mechanics (regions, backups, support access)

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

## Step 8: Assess GDPR legal controls (transfers, Art. 17/28/32) and counsel questions

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

## Step 11: Verify benchmark and pricing citations

Verdict: FAIL
CITATION VERIFICATION, steps 1-4. Checked 22 Oct 2026 (America/Chicago). Not legal advice; this is a technical citation check.

Method. I re-opened the saved source files under sources/ with grep (local:Bash, results [S123], [S125], [S126]). I did not re-fetch live URLs, because only the local tools were usable in this last turn. "Pass" means the saved page text supports the figure. "Unverifiable" means I could not read the page text that would show it. I did not count unverifiable items as pass.

CHECKS TABLE (citation x step x finding x pass/fail)
| # | Citation | Step | Finding | Result |
|---|---|---|---|---|
| 1 | S4 EnterpriseDB/OnGres whitepaper, https://info.enterprisedb.com/rs/069-ALB-339/images/PostgreSQL_MongoDB_Benchmark-WhitepaperFinal.pdf | 1 | Sponsor label is correct. The page says "EnterpriseDB ... sponsored the work" and that OnGres ran it [S123]. Step 1 labelled it vendor-sponsored. | PASS (sponsor label) |
| 2 | S4, headline result and age | 1 | The page states "PostgreSQL 11 was found to be faster than MongoDB 4.0 in almost every benchmark", with throughput up to one or two orders of magnitude higher [S123]. Step 1 said no headline was captured and gave "Date not extracted". It also described the study as OLTP-style, but the page covers Transactions, OLTP and OLAP benchmarks [S35]. PostgreSQL 11 and MongoDB 4.0 are old releases, so the study is dated and its age should be stated. | FAIL (headline and versions omitted; age not flagged) |
| 3 | S3 dev.to (hamzakhan), https://dev.to/hamzakhan/postgresql-vs-mongodb-in-2025-which-database-should-power-your-next-project-2h97 | 1 | The page shows "Posted on Aug 11, 2025" [S34]. Step 1 said the date was not extracted, so the date was available and missed. | FAIL (date missing) |
| 4 | S2 Bytebase, https://www.bytebase.com/blog/postgres-vs-mongodb | 1 | The page shows "Tianzhou · Feb 27, 2025" [S126]. Step 1 said the date was not extracted. | FAIL (date missing) |
| 5 | S14 Medium (yurexus), https://medium.com/@yurexus/can-postgresql-with-its-jsonb-column-type-replace-mongodb-30dc7feffaf3 | 1 | The page is dated Aug 2, 2023. It tested PostgreSQL 14.6 and MongoDB 6.0.3 at the start of 2023 [S126]. It also states "MongoDB is substantially faster than PostgreSQL on inserts" and that PostgreSQL JSONB is "very inefficient in terms of storage space" [S33]. Step 1 said "Not captured" for the result and gave no date. The storage finding bears directly on the cost model's PostgreSQL storage ratio. | FAIL (date and findings omitted) |
| 6 | S1 tech-insider.org (2026) and S27 mongodb.com compare page | 1 | S1 has no publication date in the lines I grepped. For S27, my grep for "benchmark/faster" was cut off, so I did not see whether it holds any figures. The S27 label "MongoDB marketing" is reasonable. | UNVERIFIABLE (S1 date; S27 content); sponsor labels not contradicted |
| 7 | S76 https://www.mongodb.com/pricing, M40-M80 | 4 | M40 $1.04/hr, M50 $2.00/hr, M60 $3.95/hr, M80 $7.30/hr, M140 $10.99/hr, with storage ranges 80 GB-1 TB, 160 GB-4 TB, 320 GB-4 TB, 750 GB-4 TB, 1-4 TB [S125]. All match step 4. | PASS |
| 8 | S76, M200 | 4 | Step 4 said the M200 $/hr was cut off. The page shows "M200 \| 1.5-4 TB \| 256 GB \| 64 vCPUs \| $14.59/hr", and M400 at $22.40/hr [S125]. The missing figure exists. | FAIL (stale gap, now fillable) |
| 9 | S76, cloud and region (AWS vs GCP, EU vs US) | 4 | The table does not state a cloud or region. Step 4 correctly refused to assign it to AWS or GCP. Its $/hr x 730 h and "at least 3 shards" arithmetic is correct: 7.30 x 730 = 5,329; ceil(10/4) = 3. | PASS (honest limitation) |
| 10 | S63 Cloud SQL, https://cloud.google.com/sql/docs/postgres/pricing | 3 | vCPU $0.0413/hr, memory $0.007/GiB-hr, HA vCPU $0.0826/hr [S125][S126]. The other two columns are $0.030975 (0.75 x 0.0413) and $0.019824 (about 0.48 x 0.0413), consistent with the 1-year and 3-year committed-use discounts step 3 inferred. HA memory $0.014 was not visible in my cut-off output; step 3 cites it from [S66]. The page title reads "404 Page Not Found" yet the content is the pricing page. The region is not shown. | PASS for the three figures I saw; HA memory and region UNVERIFIED |
| 11 | S63 derived rows, recomputed | 3 | 16 x 0.0413 + 104 x 0.007 = 1.3888, x 730 = $1,013.8. HA: 2.7776 x 730 = $2,027.6. 32 vCPU HA: 5.5552 x 730 = $4,055.0. All match step 3's $1,014, $2,028 and $4,055. | PASS |
| 12 | S39 AWS RDS PostgreSQL pricing, https://aws.amazon.com/rds/postgresql/pricing/ | 2 | The Extended Support surcharge matches: $0.100 per vCPU-hr between March 1, 2025 and February 28, 2027, and $0.200 from March 1, 2027, with a US East (Ohio) example [S126]. Step 2 correctly named us-east-2. The page text holds no instance, GB or I/O prices. Step 2 flagged this, and its remaining rows are marked estimate or missing. | PASS for R1; all other AWS rows UNVERIFIABLE (not in page text) |
| 13 | S51 Aurora pricing, https://aws.amazon.com/rds/aurora/pricing/ | 2 | I did not re-read this page. Step 2 says it holds no USD tables. | UNVERIFIABLE |
| 14 | S40/S41 prices.json | 2 | These are AWS SMS price lists, not database prices [S54, per step 2]. Step 2 correctly ignored them. | PASS |
| 15 | Givens, recomputed | 2-4 | 50 x 200 = 10,000 GB. 5,000/60 = 83.3 QPS. 10,000 x 1.3 = 13,000 GB. Steps 2-4 use these correctly. No step builds an HA compute total. Step 3 prices HA, and step 4 notes the replica-set multiplier without verifying it. | PASS |

Re-checks I ran: S76 tier table grep, S63 compute-row grep, S39 Extended Support grep, S4 sponsor and headline grep, publication-date greps on S3, S2 and S14, and hand recomputation of rows 11 and 15.
Date basis: step 1's own pages carry dates (S3 Aug 2025, S2 Feb 2025, S14 Aug 2023). The only newer-source search I ran was none. No newer source was found, and none of the step outputs show a newer-value search either.

SPONSOR LABELLING. The EDB/OnGres study is labelled vendor-sponsored (pass). The MongoDB page is labelled vendor marketing (pass). One omission: S15, a MongoDB blog on update-heavy PostgreSQL JSONB vs MongoDB BSON, was fetched in step 1 but is missing from the table. It is MongoDB-published and would need a sponsor label.

FIX LIST
1. Step 1: add the correct dates from the pages. S3 is Aug 11, 2025. S2 is Feb 27, 2025. S14 is Aug 2, 2023 [S34][S126]. Remove "the evidence cannot be shown fresh" as applied to these.
2. Step 1: state S4's headline and age. It is OnGres for EDB, PostgreSQL 11 vs MongoDB 4.0, with PostgreSQL faster in almost every test, and it covers Transactions, OLTP and OLAP [S123][S35]. Label it dated and sponsored, and low weight for current versions.
3. Step 1: add S14's findings. MongoDB was substantially faster on inserts, and PostgreSQL JSONB used far more storage [S33]. Feed this into the storage-ratio assumption, rather than a flat 1.3, until the prototype measures it. Add S15 with a MongoDB-sponsored label.
4. Step 4: fill M200 at $14.59/hr (and M400 at $22.40/hr) [S125].
5. Step 2: all AWS prices other than R1 are estimates or missing. The cost model must not present them as verified. Obtain figures from the AWS Price List API or Pricing Calculator for eu-central-1 and us-east-1. Step 3: confirm the Cloud SQL region and column headers, HA memory $0.014, europe-west3 prices, storage, backup, egress and AlloyDB.
6. Step 4: find the AWS/GCP and EU/US price split, plus backup, transfer and support prices. Until then the cost model has no verified Atlas cloud-specific figure.
7. Re-fetch S1 and S27 to confirm their dates and any benchmark figures.

Coverage: 15 rows, at least 2 per step across steps 1-4, and 4 of them unverifiable. Confirmed: 8 pass items. Not confirmed: AWS RDS/Aurora instance, storage and I/O prices, S1 and S27 content, Cloud SQL region.

VERDICT: FAIL
MISSING DATA: AWS RDS/Aurora instance, storage and I/O prices (eu-central-1, us-east-1) — not in the saved page text of S39 or S51
MISSING DATA: Cloud SQL region and column confirmation, HA memory $0.014 visibility — S63 grep output cut off
MISSING DATA: S1 publication date and S27 benchmark content — grep output cut off
Issues:
1. Step 1: publication dates for S3 (Aug 11, 2025), S2 (Feb 27, 2025) and S14 (Aug 2, 2023) exist on the pages but were reported as 'not extracted'. Fix: add the dates and revise the freshness conclusion.
2. Step 1: S4's headline (PostgreSQL 11 faster than MongoDB 4.0 in almost every benchmark; Transactions, OLTP and OLAP) was omitted and its old versions were not flagged. Fix: state the headline, the versions and 'dated, EDB-sponsored'.
3. Step 1: S14's findings (MongoDB faster on inserts; PostgreSQL JSONB much larger in storage) were omitted, though they affect the cost model's storage ratio. S15 (a MongoDB blog) was fetched but not tabled or labelled. Fix: add both with sponsor labels.
4. Step 4: the M200 price was reported as cut off, but S76 shows $14.59/hr (M400 $22.40/hr). Fix: fill the figures.
5. Step 2: only the Extended Support surcharge (R1) is verified. Other AWS prices are memory estimates or missing, so the cost model has no verified AWS figure. Fix: use the AWS Price List API or Pricing Calculator.
6. Step 3: the Cloud SQL region and column headers are unconfirmed, HA memory $0.014 was not re-verified, and there is no AlloyDB, storage, backup or egress data. Fix: fetch these.
7. Step 4: no AWS-versus-GCP or EU-versus-US Atlas split, and no backup, transfer or support prices. Fix: capture them.

## Files made
- __pycache__/gen_data.cpython-311.pyc (8,781 bytes, made in step 6; listed by plain code)
- __pycache__/mongo_bench.cpython-311.pyc (25,409 bytes, made in step 6; listed by plain code)
- tool_results/step11_1.txt (6,719 bytes, made in step 11; listed by plain code)
- tool_results/step11_10.txt (2,470 bytes, made in step 1; listed by plain code)
- tool_results/step11_2.txt (8,409 bytes, made in step 11; listed by plain code)
- tool_results/step11_3.txt (5,783 bytes, made in step 11; listed by plain code)
- tool_results/step11_4.txt (6,611 bytes, made in step 11; listed by plain code)
- tool_results/step11_5.txt (2,135 bytes, made in step 11; listed by plain code)
- tool_results/step11_6.txt (2,130 bytes, made in step 11; listed by plain code)
- tool_results/step11_7.txt (4,551 bytes, made in step 11; listed by plain code)
- tool_results/step11_8.txt (4,884 bytes, made in step 11; listed by plain code)
- tool_results/step11_9.txt (2,876 bytes, made in step 11; listed by plain code)
- tool_results/step1_1.txt (2,128 bytes, made in step 1; listed by plain code)
- tool_results/step1_2.txt (2,135 bytes, made in step 1; listed by plain code)
- tool_results/step1_3.txt (7,833 bytes, made in step 1; listed by plain code)
- tool_results/step1_4.txt (7,651 bytes, made in step 1; listed by plain code)
- tool_results/step1_5.txt (3,889 bytes, made in step 1; listed by plain code)
- tool_results/step1_6.txt (5,691 bytes, made in step 1; listed by plain code)
- tool_results/step1_7.txt (5,923 bytes, made in step 1; listed by plain code)
- tool_results/step1_8.txt (6,162 bytes, made in step 1; listed by plain code)
- tool_results/step1_9.txt (3,265 bytes, made in step 2; listed by plain code)
- tool_results/step2_1.txt (2,132 bytes, made in step 2; listed by plain code)
- tool_results/step2_2.txt (2,142 bytes, made in step 2; listed by plain code)
- tool_results/step2_3.txt (2,132 bytes, made in step 2; listed by plain code)
- tool_results/step2_4.txt (2,129 bytes, made in step 2; listed by plain code)
- tool_results/step2_5.txt (2,132 bytes, made in step 2; listed by plain code)
- tool_results/step2_6.txt (6,745 bytes, made in step 3; listed by plain code)
- tool_results/step2_7.txt (2,133 bytes, made in step 2; listed by plain code)
- tool_results/step2_8.txt (2,138 bytes, made in step 3; listed by plain code)
- tool_results/step2_9.txt (4,520 bytes, made in step 3; listed by plain code)
- tool_results/step3_1.txt (6,243 bytes, made in step 3; listed by plain code)
- tool_results/step3_2.txt (2,526 bytes, made in step 3; listed by plain code)
- tool_results/step3_3.txt (7,998 bytes, made in step 3; listed by plain code)
- tool_results/step3_4.txt (6,018 bytes, made in step 3; listed by plain code)
- tool_results/step3_5.txt (4,466 bytes, made in step 4; listed by plain code)
- tool_results/step4_1.txt (5,438 bytes, made in step 4; listed by plain code)
- tool_results/step4_2.txt (6,049 bytes, made in step 4; listed by plain code)
- tool_results/step4_3.txt (4,308 bytes, made in step 4; listed by plain code)
- tool_results/step4_4.txt (2,130 bytes, made in step 4; listed by plain code)
- tool_results/step4_5.txt (2,141 bytes, made in step 11; listed by plain code)
- tool_results/step5_4.txt (4,180 bytes, made in step 5; listed by plain code)
- tool_results/step5_5.txt (2,712 bytes, made in step 5; listed by plain code)
- tool_results/step6_2.txt (2,130 bytes, made in step 6; listed by plain code)
- tool_results/step6_3.txt (2,829 bytes, made in step 6; listed by plain code)
- tool_results/step7_1.txt (4,866 bytes, made in step 7; listed by plain code)
- tool_results/step7_2.txt (5,146 bytes, made in step 7; listed by plain code)
- tool_results/step7_3.txt (6,342 bytes, made in step 7; listed by plain code)
- tool_results/step7_4.txt (5,827 bytes, made in step 7; listed by plain code)
- tool_results/step7_5.txt (6,598 bytes, made in step 7; listed by plain code)
- tool_results/step7_6.txt (2,126 bytes, made in step 8; listed by plain code)
- tool_results/step8_1.txt (5,606 bytes, made in step 8; listed by plain code)
- tool_results/step8_2.txt (5,910 bytes, made in step 8; listed by plain code)
- tool_results/step8_3.txt (2,127 bytes, made in step 8; listed by plain code)
- tool_results/step8_4.txt (2,136 bytes, made in step 8; listed by plain code)
- tool_results/step8_5.txt (6,408 bytes, made in step 8; listed by plain code)

## Limitations
- BLOCKED: AWS Pricing Calculator / Price List API (the team had no such capability; added by plain code)
- BLOCKED: Fetch of AWS Support pricing page (the team had no such capability; added by plain code)
- BLOCKED: MongoDB server (the team had no such capability; added by plain code)
- BLOCKED: PostgreSQL server binaries (the team had no such capability; added by plain code)
- BLOCKED: local (the team had no such capability; added by plain code)
- Mislabelled citation: step 2 cites S39 for '128', which S39 does not contain; it is in S13, S14, S63 (added by plain code)
- Mislabelled citation: step 2 cites S39 for '256', which S39 does not contain; it is in S4, S6, S7 (added by plain code)
- Mislabelled citation: step 3 cites S63 for '23', which S63 does not contain; it is in S1, S11, S12 (added by plain code)
- Mislabelled citation: step 3 cites S142 for '23', which S142 does not contain; it is in S1, S11, S12 (added by plain code)
- Mislabelled citation: step 3 cites S142 for '40', which S142 does not contain; it is in S4, S13, S14 (added by plain code)
- Mislabelled citation: step 3 cites S66 for '16', which S66 does not contain; it is in S1, S4, S7 (added by plain code)
- Mislabelled citation: step 3 cites S66 for '104', which S66 does not contain (added by plain code)
- Mislabelled citation: step 5 cites S78 for '84', which S78 does not contain (added by plain code)
- Mislabelled citation: step 7 cites S90 for 'Manage instance locations | Cloud SQL for PostgreSQL', which S90 does not contain; it is in S89 (added by plain code)
- Mislabelled citation: step 7 cites S90 for '0:00', which S90 does not contain; it is in S11, S12, S17 (added by plain code)
- Mislabelled citation: step 7 cites S90 for '10:27pm', which S90 does not contain (added by plain code)
- Mislabelled citation: step 11 cites S123 for 'EnterpriseDB ... sponsored the work', which S123 does not contain (added by plain code)
- Mislabelled citation: step 11 cites S35 for 'Date not extracted', which S35 does not contain (added by plain code)
- Mislabelled citation: step 11 cites S126 for '5', which S126 does not contain; it is in S2, S3, S4 (added by plain code)
- Mislabelled citation: step 11 cites S125 for 'M200 \\| 1.5-4 TB \\| 256 GB \\| 64 vCPUs \\| $14.59/hr', which S125 does not contain (added by plain code)
- Mislabelled citation: step 11 cites S66 for '0.75', which S66 does not contain (added by plain code)
- DISPUTED: tb — step 4 gives 1,000; the check in step 11, worked out independently, gives 83.3. Neither a source quote nor a re-run settled it (added by plain code)
- DISPUTED: t04 — step 2 gives 13; the check in step 11, worked out independently, gives 29. Neither a source quote nor a re-run settled it (added by plain code)
- DISPUTED: fetch tool titled page — step 3 gives 404; the check in step 11, worked out independently, gives 6,000. Neither a source quote nor a re-run settled it (added by plain code)

