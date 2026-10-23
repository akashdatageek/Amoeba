AWS RDS for PostgreSQL and Aurora PostgreSQL pricing. Retrieved 2026-10-22 (Chicago time). The fetch logs show 2026-10-23T03:22 UTC [S57][S61]. This is the date I settled on. I did not find a newer figure, because no turns were left for a second search.

Sources:
- RDS for PostgreSQL pricing page, https://aws.amazon.com/rds/postgresql/pricing/ [S57].
- Aurora pricing page, https://aws.amazon.com/rds/aurora/pricing/ [S61].

Only the first part of each page came back from the fetch. I read the rest from the saved page text [S63]. Both pages render their per-region price tables dynamically. The tables for the task's vCPU range (the mid-size to large instance classes), for eu-west-1 and for the US regions, were therefore not in the text. Anything not in the text is marked "not found". I did not use my own knowledge for any price.

| provider | service | region | tier | unit | USD price | URL | date retrieved |
|---|---|---|---|---|---|---|---|
| AWS | RDS for PostgreSQL | eu-west-1 (Ireland) | On-Demand instances, task vCPU range (e.g. db.m/db.r 2xlarge to 8xlarge) | per instance-hour | not found (dynamic table not in fetched text) | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | RDS for PostgreSQL | US East (N. Virginia) | On-Demand instances, task vCPU range | per instance-hour | not found (dynamic table not in fetched text) | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | RDS for PostgreSQL | US East (N. Virginia) | io1 Dedicated Log Volume, storage | per GiB-month | $0.125 (from the page's worked example) [S63] | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | RDS for PostgreSQL | US East (N. Virginia) | io1 Dedicated Log Volume, provisioned IOPS | per IOPS-month | $0.10 (from the page's worked example; 1,024 GiB plus 3,000 IOPS = $428/month) [S63] | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | RDS for PostgreSQL | eu-west-1 (Ireland) | General Purpose gp3/gp2 and io1/io2 data storage | per GB-month | not found | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | RDS for PostgreSQL | eu-west-1 / US East | T4g/T3 burstable CPU credits (surplus credits only, not in the task vCPU range) | per vCPU-hour | $0.075 (same for all T4g and T3 sizes) [S63] | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | RDS for PostgreSQL | eu-west-1 / US East | Multi-AZ deployment and read replicas | per instance-hour / per GB-month | not found (the text gives no price or multiplier) | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | RDS for PostgreSQL | eu-west-1 / US East | Backup storage beyond the free allowance | per GB-month | not found | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | RDS for PostgreSQL | eu-west-1 / US East | Data transfer out to internet and cross-region transfer | per GB | not found (the RDS page does not list it; see the EC2 data-transfer pricing page) | https://aws.amazon.com/rds/postgresql/pricing/ [S57] | 2026-10-22 |
| AWS | Aurora PostgreSQL | eu-west-1 (Ireland) | Provisioned instances, task vCPU range (e.g. db.r6g/r7g 2xlarge to 8xlarge) | per instance-hour | not found (dynamic table not in fetched text) | https://aws.amazon.com/rds/aurora/pricing/ [S61] | 2026-10-22 |
| AWS | Aurora PostgreSQL | US East (N. Virginia) / US East (Ohio) | Provisioned instances, task vCPU range | per instance-hour | not found | https://aws.amazon.com/rds/aurora/pricing/ [S61] | 2026-10-22 |
| AWS | Aurora PostgreSQL | not stated in the excerpt | Storage in the page's worked example | per GB-month | $0.225 (80 GB = $18.00; the same example shows $271.44 for instance-hours) [S63] | https://aws.amazon.com/rds/aurora/pricing/ [S61] | 2026-10-22 |
| AWS | Aurora PostgreSQL | eu-west-1 / US East | Storage (Standard vs I/O-Optimized), I/O requests, backup storage, Aurora Replicas, cross-region replication and data transfer | per GB-month / per million I/Os / per GB | not found (only the $0.225/GB-month example figure [S63] was captured; the per-region price tables did not render) | https://aws.amazon.com/rds/aurora/pricing/ [S61] | 2026-10-22 |

The Aurora page also contains a sentence about a charge of "$0.100 per vCPU-hr" for deployments in US East (Ohio) from 1 March [S63]. The excerpt I read was cut off, so I can't say which feature it applies to. I did not use it as a database price.

Gaps (all figures below are "not found"; nothing was estimated):
- Per-hour prices for the task's vCPU range, for RDS and for Aurora, in eu-west-1 and in any US region. The dynamic price tables were not in the fetched text. The price must be taken from the AWS Pricing Calculator or the AWS Price List API before the 50-tenant cost estimate is final.
- The RDS gp3/io1/io2 storage price per GB-month in eu-west-1. The only storage figures found are for the io1 Dedicated Log Volume in US East (N. Virginia) [S63]. Don't apply them to the data volume or to EU regions.
- Backup storage price beyond the free allowance, for RDS and Aurora.
- Multi-AZ and replica pricing for RDS, and Aurora Replica and Global Database replication prices.
- Aurora I/O request price and the Standard vs I/O-Optimized instance and storage rates. The only Aurora figure captured ($0.225/GB-month [S63]) has no region or configuration stated in the excerpt.
- Egress and inter-region transfer prices. Neither page states them. Use the EC2 on-demand pricing page, which wasn't fetched.
- Only two pages were fetched, fewer than the fetch limit allowed. The step had no turns left to retry with the pricing API or the calculator, and I did not look for a newer figure than the live pages.
- The only EU region attempted was eu-west-1. eu-central-1 was not checked.
MISSING DATA: RDS PostgreSQL and Aurora PostgreSQL hourly instance prices for the task vCPU range in eu-west-1 and US East — pricing pages fetched, tables not rendered in text
MISSING DATA: RDS gp3/io1 data storage price per GB-month in eu-west-1 — RDS pricing page
MISSING DATA: Backup storage, Multi-AZ, replica, Aurora I/O request prices — RDS and Aurora pricing pages
MISSING DATA: Egress and inter-region transfer prices — RDS and Aurora pricing pages (not listed; EC2 data-transfer page not fetched)
