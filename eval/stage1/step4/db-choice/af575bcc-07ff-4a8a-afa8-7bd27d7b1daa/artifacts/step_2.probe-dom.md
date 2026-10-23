**AWS managed PostgreSQL pricing: RDS and Aurora (eu-central-1, us-east-1). Captured 2026-10-22 (America/Chicago) [S62].**

**Result: no USD price could be read from any fetched page, so every price below is "not found". I wrote no number from memory.**

**Sources actually fetched**
- Amazon RDS for PostgreSQL pricing page: https://aws.amazon.com/rds/postgresql/pricing/ [S39]. Fetched 2026-10-22 (index timestamp 2026-10-23T04:12:03 UTC, which is the evening of 2026-10-22 in Chicago) [S62].
- Amazon Aurora pricing page: https://aws.amazon.com/rds/aurora/pricing/ [S51]. Fetched 2026-10-22 (index timestamp 2026-10-23T04:13:21 UTC) [S62].
- The URLs are now confirmed from sources/index.json [S62]. They are no longer inferred.
- Greps of both pages for dollar amounts, region names, Multi-AZ, per-GB, IOPS and backup found no price lines [S58][S60]. The prices appear to be script-rendered, and this run has no dynamic price-table rendering.
- The only pricing statement found was a free-tier offer for new RDS customers [S60]. It is not a price.
- AWS Pricing API offer file for RDS in us-east-1: `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/us-east-1/index.json`. The fetch failed because the file is over the fetch tool's size limit. I did not try the eu-central-1 file. No price came from either file.
- [S40] and [S41] are AWS SMS/messaging price JSON, not database prices [S61]. I ignored them.
- AWS Support plan pricing was not fetched (out of turns). Its URL below is a standard AWS address and was not fetched.

**Pricing table (service x instance/unit x region x USD x URL x date captured)**

| # | Service | Instance / unit | Region | USD price | Status | URL | Date captured |
|---|---|---|---|---|---|---|---|
| 1 | RDS for PostgreSQL | db.r6g.4xlarge (candidate 16 vCPU class [unverified]), Multi-AZ, per instance-hour | eu-central-1 | not found | page fetched [S39]; price not in text | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S62] |
| 2 | RDS for PostgreSQL | db.r6g.4xlarge, Multi-AZ, per instance-hour | us-east-1 | not found | page fetched [S39]; price not in text | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S62] |
| 3 | RDS for PostgreSQL | db.r6g.8xlarge (candidate 32 vCPU class [unverified]), Multi-AZ, per instance-hour | eu-central-1 | not found | page fetched [S39]; price not in text | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S62] |
| 4 | RDS for PostgreSQL | db.r6g.8xlarge, Multi-AZ, per instance-hour | us-east-1 | not found | page fetched [S39]; price not in text | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S62] |
| 5 | RDS for PostgreSQL | gp3 storage Multi-AZ $/GB-month, plus IOPS/throughput above baseline | eu-central-1 and us-east-1 | not found | page fetched [S39]; price not in text | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S62] |
| 6 | RDS for PostgreSQL | Backup storage beyond free allowance, $/GB-month | eu-central-1 and us-east-1 | not found | page fetched [S39]; price not in text | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S62] |
| 7 | Aurora PostgreSQL | db.r6g.4xlarge, per instance-hour (HA = writer plus one reader, billed as two instances) | eu-central-1 | not found | page fetched [S51]; price not in text | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S62] |
| 8 | Aurora PostgreSQL | db.r6g.4xlarge, per instance-hour (writer plus one reader) | us-east-1 | not found | page fetched [S51]; price not in text | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S62] |
| 9 | Aurora PostgreSQL | db.r6g.8xlarge, per instance-hour (writer plus one reader) | eu-central-1 and us-east-1 | not found | page fetched [S51]; price not in text | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S62] |
| 10 | Aurora PostgreSQL | Storage $/GB-month and I/O $ per million requests (Standard); I/O-Optimized instance and storage rates | eu-central-1 and us-east-1 | not found | page fetched [S51]; price not in text | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S62] |
| 11 | Aurora PostgreSQL | Backup storage beyond cluster-volume size, $/GB-month | eu-central-1 and us-east-1 | not found | page fetched [S51]; price not in text | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 [S62] |
| 12 | RDS and Aurora | Cross-region data transfer / replication, $/GB | eu-central-1 to us-east-1 and reverse | not found | not read | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 [S62] |
| 13 | AWS Support plans (Developer, Business, Enterprise) | % of monthly spend or minimum monthly fee | global | not found | not fetched | https://aws.amazon.com/premiumsupport/pricing/ (standard address, not fetched) | 2026-10-22 [S62] |

**Date settled on.** The newest data I had was the page fetch of 2026-10-22 [S62]. I made one further attempt at a newer machine-readable source (the Pricing API file), and it failed.

**For the cost model (next step).** Treat every AWS RDS and Aurora price as an input to fill from the AWS Pricing API files or the AWS Pricing Calculator. Until then, label any such cell "estimate" or leave it blank. Do not present these as list prices.

- The Pricing API file is over the fetch limit, so it gave no prices.
- The static pages carry no readable prices.
- So no instance, storage, I/O, backup, transfer or support price was obtained for either region.
BLOCKED: Dynamic price-table rendering / large-file reader — AWS Pricing API offer file exceeded the fetch size limit and the AWS pricing pages' script-rendered price tables could not be read, so no AWS price was captured
MISSING DATA: RDS PostgreSQL Multi-AZ instance-hour price for 16 and 32 vCPU classes, eu-central-1 and us-east-1 — AWS RDS PostgreSQL pricing page [S39] and Pricing API index.json (too large)
MISSING DATA: RDS gp3/io1/io2 storage, IOPS and throughput prices — [S39], not in page text
MISSING DATA: RDS backup storage $/GB-month — [S39], not in page text
MISSING DATA: Aurora PostgreSQL instance-hour, storage, I/O and I/O-Optimized prices — [S51], not in page text
MISSING DATA: Aurora backup storage price — [S51], not in page text
MISSING DATA: Cross-region transfer price for RDS/Aurora — [S39][S51], not read
MISSING DATA: AWS Support plan pricing — not fetched (no turns left)
