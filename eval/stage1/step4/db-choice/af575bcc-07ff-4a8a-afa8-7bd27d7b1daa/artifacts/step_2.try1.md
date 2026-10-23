**AWS managed PostgreSQL pricing: RDS and Aurora (partial capture, as of 22 Oct 2026, America/Chicago)**

Only one AWS page was fetched: the RDS for PostgreSQL pricing page [S39], https://aws.amazon.com/rds/postgresql/pricing/. It was fetched 2026-10-23T04:12Z, which is 2026-10-22 in America/Chicago. Only the first 6,000 of 28,306 characters reached me [S39]. My grep passes over the saved file did not return its instance-price tables [S45]. I therefore have no verified per-instance, storage, I/O, backup or transfer price for us-east-1 or eu-central-1.
- The Aurora pricing page (https://aws.amazon.com/rds/aurora/pricing/) was never fetched.
- The two data files that came back with the search, [S40] and [S41], contain SMS prices and are not relevant.
- I settled on the 2026-10-22 capture of the RDS page. I found no newer value.

I did not invent prices. Rows tagged [unverified] come from my own recollection of AWS list prices, not from a page I read. They must be re-checked before they go into cost_model.xlsx. Do not use them as list prices until they are confirmed.

| Service | Instance / unit | Region | USD price | URL | Date captured | Status |
|---|---|---|---|---|---|---|
| RDS PostgreSQL | Extended Support, per vCPU-hour (charged for engine versions past end of standard support, e.g. PG 12) | us-east-2 (Ohio) | $0.100 per vCPU-hr; the text was cut off after this figure [S45] | https://aws.amazon.com/rds/postgresql/pricing/ [S39] | 2026-10-22 (CDT) | Snippet from the fetched page, partly truncated. Not a core price. Ohio is not a target region. |
| RDS PostgreSQL | Compute, Multi-AZ, first class in the step brief's vCPU range (memory-optimized "r" family) | us-east-1 | NOT CAPTURED | https://aws.amazon.com/rds/postgresql/pricing/ [S39] | 2026-10-22 (CDT) | Page fetched, but the table was not in the readable text. |
| RDS PostgreSQL | Compute, Multi-AZ, second, larger class in the same vCPU range | us-east-1 | NOT CAPTURED | https://aws.amazon.com/rds/postgresql/pricing/ [S39] | 2026-10-22 (CDT) | Same. |
| RDS PostgreSQL | Compute, Multi-AZ, both classes | eu-central-1 | NOT CAPTURED | https://aws.amazon.com/rds/postgresql/pricing/ [S39] | 2026-10-22 (CDT) | The region price table was not read. |
| RDS PostgreSQL | gp3 storage, Multi-AZ, per GB-month | us-east-1 | about $0.23 per GB-month [unverified]; single-AZ about $0.115 [unverified] | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 (CDT); recalled, not read from the page | Unverified. Re-check. |
| RDS PostgreSQL | gp3 storage, Multi-AZ, per GB-month | eu-central-1 | NOT CAPTURED | https://aws.amazon.com/rds/postgresql/pricing/ [S39] | 2026-10-22 (CDT) | Not readable. |
| RDS PostgreSQL | Provisioned IOPS / gp3 extra IOPS and throughput | us-east-1 and eu-central-1 | NOT CAPTURED. gp3 includes a baseline IOPS allowance whose size I could not verify. | https://aws.amazon.com/rds/postgresql/pricing/ [S39] | 2026-10-22 (CDT) | Not readable. |
| RDS PostgreSQL | Backup storage beyond 100% of provisioned DB storage, per GB-month | us-east-1 | about $0.095 per GB-month [unverified] | https://aws.amazon.com/rds/postgresql/pricing/ | 2026-10-22 (CDT); recalled, not read from the page | Unverified. |
| RDS PostgreSQL | Cross-region data transfer out (us-east-1 to eu-central-1), per GB | us-east-1 to eu-central-1 | about $0.02 per GB [unverified] | https://aws.amazon.com/rds/postgresql/pricing/ (the page has a "Data transfer costs" heading, which was all I saw [S45]) | 2026-10-22 (CDT); recalled, not read from the page | Unverified. Check the EC2 data-transfer page too. |
| Aurora PostgreSQL | Compute, Multi-AZ (writer plus reader), both classes | us-east-1 and eu-central-1 | NOT CAPTURED | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 (CDT); page not fetched | The page was never fetched. |
| Aurora PostgreSQL | Storage (Standard configuration), per GB-month | us-east-1 | about $0.10 per GB-month [unverified] | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 (CDT); recalled, page not fetched | Unverified. |
| Aurora PostgreSQL | I/O (Standard configuration), per million requests | us-east-1 | about $0.20 per million requests [unverified]. I/O-Optimized has no per-I/O charge but higher compute and storage rates (not captured). | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 (CDT); recalled, page not fetched | Unverified. |
| Aurora PostgreSQL | Backup storage, per GB-month | us-east-1 and eu-central-1 | NOT CAPTURED | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 (CDT); page not fetched | |
| Aurora PostgreSQL | Global Database cross-region replicated writes and transfer | us-east-1 to eu-central-1 | NOT CAPTURED | https://aws.amazon.com/rds/aurora/pricing/ | 2026-10-22 (CDT); page not fetched | |
| RDS and Aurora | AWS Support plans (Developer, Business, Enterprise On-Ramp) | n/a (global) | NOT CAPTURED | https://aws.amazon.com/premiumsupport/pricing/ | 2026-10-22 (CDT); page not fetched | Business is the likely fit for a 12-person startup. |

**Coverage against the done_when test**
- RDS and Aurora each have compute, storage and I/O rows. Backup and transfer rows are present. Every row has a URL and a capture date.
- Not every row has a price. Only the Extended Support row holds a figure read from a fetched page [S45], and it is not a core cost line.
- The [unverified] rows are recollection only.

**Caveats for the cost model**
- Confirm the unverified rows before use. In particular confirm the instance prices for both regions, the gp3 baseline IOPS allowance, and Aurora Standard against I/O-Optimized.
- For 10 TB raw data (50 tenants x 200 GB = 10,000 GB), Aurora Standard versus I/O-Optimized will probably matter more than instance class. Treat it as a scenario switch in the model.
- The maximum RDS or Aurora storage per instance or cluster was not confirmed. Check whether 10 TB or more fits on one instance or needs a split (one per region or group of tenants).
MISSING DATA: RDS PostgreSQL Multi-AZ hourly price for two instance classes in the 16-64 vCPU range, us-east-1 and eu-central-1 — fetched https://aws.amazon.com/rds/postgresql/pricing/ [S39], price tables not in readable text
MISSING DATA: RDS gp3/io1/io2 storage and IOPS prices for eu-central-1 and verified us-east-1 — same page, not readable
MISSING DATA: Aurora PostgreSQL compute, storage, I/O, backup and Global Database prices for both regions — Aurora pricing page never fetched
MISSING DATA: AWS cross-region data transfer price (verified) — only a 'Data transfer costs' heading seen on S39
MISSING DATA: AWS Support plan pricing — https://aws.amazon.com/premiumsupport/pricing/ not fetched
MISSING DATA: Maximum RDS and Aurora storage per instance or cluster — AWS documentation not fetched
