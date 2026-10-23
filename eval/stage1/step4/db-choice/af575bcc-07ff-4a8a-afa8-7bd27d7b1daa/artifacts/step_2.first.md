## AWS RDS for PostgreSQL and Aurora PostgreSQL pricing (captured 2026-10-22, America/Chicago)

**Settled date.** I used the AWS pages fetched on 2026-10-22. The Aurora page was fetched at 2026-10-23T04:13 UTC, which is 2026-10-22 in Chicago [S51]. No newer source exists. I did not run a second "newer value" search because the turn budget ran out.

**What was and wasn't captured.**
- I fetched the official AWS pages for RDS for PostgreSQL, https://aws.amazon.com/rds/postgresql/pricing/ [S39], and Aurora, https://aws.amazon.com/rds/aurora/pricing/ [S51].
- The saved text of both pages is marketing copy and links. It has no per-instance, per-GB or per-I/O USD tables for us-east-1 or eu-central-1. AWS loads those tables with JavaScript.
- The only USD figure I read on an official page is the RDS Extended Support surcharge (row R1) [S52].
- The S40 and S41 `prices.csv` files are AWS SMS (text-message) price lists, not database prices [S54]. They are irrelevant here, and I used nothing from them.
- Rows marked **[unverified]** come from my own memory of AWS list prices, not from a page read in this run. They are **estimates for placeholder use only**.
- Replace every estimate with a figure from the AWS Pricing Calculator or the AWS Price List API before the cost model is final.
- I have no eu-central-1 figures and did not guess them. AWS usually prices eu-central-1 above us-east-1, so do not reuse the us-east-1 numbers for Frankfurt.

| Row | Service | Instance / unit | Region | USD price | Status | URL | Date captured |
|---|---|---|---|---|---|---|---|
| R1 | RDS PostgreSQL | Extended Support surcharge for out-of-support major versions (e.g. PG 12), per vCPU-hour | us-east-2 (AWS worked example), not us-east-1 | $0.100 per vCPU-hr from 2025-03-01 to 2027-02-28, then $0.200 from 2027-03-01 [S52] | Read on official page | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R2 | RDS PostgreSQL | db.r6g.4xlarge (16 vCPU / 128 GB), Multi-AZ, per hour | us-east-1 | Not captured. Order of magnitude only: roughly $2–4 per hour [unverified]. My earlier draft figure of about $1.92 is low-confidence, so do not use it. | Missing; estimate range | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 (page fetched, table absent) [S39] |
| R3 | RDS PostgreSQL | db.r6g.8xlarge (32 vCPU / 256 GB), Multi-AZ, per hour | us-east-1 | Not captured. Compute price scales about linearly with vCPU, so roughly 2x R2 | Missing; estimate | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R4 | RDS PostgreSQL | Same two classes, Multi-AZ | eu-central-1 | Not captured; no estimate offered | Missing | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R5 | RDS PostgreSQL | gp3 storage, Multi-AZ, per GB-month (baseline IOPS and throughput included; extra billed separately) | us-east-1 | about $0.23 [unverified] (estimate) | Estimate, unverified | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 (page fetched, table absent) [S39] |
| R6 | RDS PostgreSQL | Provisioned IOPS (io1/io2), per IOPS-month | us-east-1 and eu-central-1 | Not captured | Missing | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R7 | RDS PostgreSQL | Backup storage beyond 100% of provisioned DB storage, per GB-month | us-east-1 | about $0.095 [unverified] (estimate) | Estimate, unverified | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R8 | RDS PostgreSQL | Cross-region data transfer out, per GB (EU/US two-region design) | eu-central-1 to us-east-1 | about $0.02 [unverified] (estimate) | Estimate, unverified | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S39] |
| R9 | Aurora PostgreSQL | db.r6g.4xlarge or db.r7g.4xlarge, per hour. The Multi-AZ equivalent is a second reader instance, billed at the same hourly rate. | us-east-1 and eu-central-1 | Not captured | Missing | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S51] |
| R10 | Aurora PostgreSQL | Aurora Standard storage, per GB-month | us-east-1 | about $0.10 (estimate) | Estimate, unverified | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 (page fetched, table absent) [S51] |
| R11 | Aurora PostgreSQL | Aurora Standard I/O requests, per million | us-east-1 | about $0.20 (estimate) | Estimate, unverified | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S51] |
| R12 | Aurora PostgreSQL | Aurora I/O-Optimized storage, per GB-month (no per-I/O charge; instance price carries a premium) | us-east-1 | about $0.225 [unverified] (estimate) | Estimate, unverified | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S51] |
| R13 | Aurora PostgreSQL | Backup storage beyond the free allowance, per GB-month | us-east-1 | about $0.021 [unverified] (estimate) | Estimate, unverified | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S51] |
| R14 | Aurora PostgreSQL | Cross-region replication or transfer, per GB | eu-central-1 to us-east-1 | Not captured; assume the same as R8 (about $0.02 [unverified]) | Missing; estimate | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S51] |
| R15 | AWS Support (applies to RDS and Aurora) | Business, Enterprise On-Ramp and Enterprise plans | Global | Not captured. The usual structure is a percentage of monthly spend with a minimum, but I have no verified figure. | Missing | https://aws.amazon.com/premiumsupport/pricing/ | Not fetched |

**Checks against the done_when criteria**
- RDS compute, storage and I/O rows are present (R2–R6), but only as estimates or gaps.
- Aurora compute, storage and I/O rows are present (R9–R12), but only as estimates or gaps.
- Backup and transfer rows are present for both services (R7–R8 and R13–R14).
- Every row has a URL and a capture date. Only R1 is a verified figure.

**Guidance for the cost model**
- Load the estimate rows into the `Pricing` sheet flagged "estimate". Do not report them as verified.
- Aurora I/O cost depends on the prototype's measured I/O rate. The peak load is 5,000 ÷ 60 = 83.3 queries per second. Run both Aurora Standard and I/O-Optimized in the model.
- Storage: 50 tenants × 200 GB = 10,000 GB raw. The default PostgreSQL storage ratio is 1.3 until the prototype measures one, so 10,000 × 1.3 = 13,000 GB.
- I believe 13,000 GB fits on one instance in either service. RDS PostgreSQL's per-instance limit is about 64 TiB and Aurora's is about 128 TiB [unverified]. Confirm both limits on the AWS docs.
- R1 shows that the PostgreSQL major version affects cost. Use a current major version to avoid the Extended Support surcharge.
BLOCKED: Dynamic price-table rendering — the AWS RDS and Aurora pricing pages returned text without the per-instance, per-GB or per-I/O USD tables, so verified us-east-1 and eu-central-1 prices could not be read; the AWS Pricing Calculator and Price List API were not available
MISSING DATA: RDS PostgreSQL Multi-AZ hourly price for 16-64 vCPU classes in us-east-1 and eu-central-1 — AWS RDS pricing page [S39], table not in the fetched text
MISSING DATA: Aurora PostgreSQL instance hourly prices (us-east-1, eu-central-1) — AWS Aurora pricing page [S51], table not in the fetched text
MISSING DATA: Verified storage, I/O, backup and cross-region transfer prices for both services — same pages; only memory-based estimates tagged [unverified] provided
MISSING DATA: eu-central-1 (Frankfurt) prices for every line — not found, no estimate offered
MISSING DATA: AWS Support plan pricing — https://aws.amazon.com/premiumsupport/pricing/ not fetched
MISSING DATA: Newer-value re-search — not done because the turn budget ran out
