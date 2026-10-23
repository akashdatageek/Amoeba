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
