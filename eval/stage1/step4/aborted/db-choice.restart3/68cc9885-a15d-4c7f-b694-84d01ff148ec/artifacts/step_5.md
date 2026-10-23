I read "multi-tenant" as Shared database with a tenant ID column or tenant field; if you meant Separate schema or database per tenant, the answer below may not apply.

**MongoDB Atlas pricing (AWS and GCP) – step 5. Retrieval date 2026-10-22 (US Central). The page was fetched 2026-10-23T03:25 UTC. One page was fetched: https://www.mongodb.com/pricing [S70]. I read excerpts of it [S73][S74]. The M40–M80 per-region price grid was NOT visible in the excerpts I captured. I record it as "not found" rather than guessing.**

| provider | service | region | tier | unit | USD price | URL | date retrieved |
|---|---|---|---|---|---|---|---|
| MongoDB Atlas (any cloud; the page does not split AWS/GCP in the excerpt) | Dedicated cluster, entry price ("Starts at") | not stated in excerpt | Dedicated, smallest tier (the tier name is not captured in the excerpt) | per hour; per month | $0.08/hour; "Starts at $56.94/month" [S74] | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas | Dedicated cluster capacity range | not stated | Dedicated, all tiers | storage / RAM / vCPU range | 10 GB to 4 TB storage; 2 GB to 768 GB RAM; 2 to 96 vCPUs (no price) [S74] | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas | Shared tiers (not suitable for production) | not stated | M0 / M2 / M5 | per month | Free / $9/mo / $25/mo [S74] | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas on AWS | Dedicated M40–M80 (8–32 vCPU class) | eu-west-1 / eu-central-1 | M40, M50, M60, M80 | per hour | not found (the grid is not in the captured text) | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas on AWS | Dedicated M40–M80 | US region (e.g. us-east-1) | M40, M50, M60, M80 | per hour | not found | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas on GCP | Dedicated M40–M80 | europe-west1 / europe-west4 | M40, M50, M60, M80 | per hour | not found | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas on GCP | Dedicated M40–M80 | US region (e.g. us-central1) | M40, M50, M60, M80 | per hour | not found | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas | Enhanced-performance option for dedicated workloads (decoupled compute and storage; the product name is not captured). Available on M10+ dedicated clusters | not stated | M10+ | storage capacity / IOPS | Up to 128 TB per HA shard; 1M+ IOPS burst; no price captured [S73] | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas (a separate "S" tier table; the page excerpt does not name the product, probably search nodes, [unverified]) | S40 / S50 / S60 | not stated | S40 = 8 vCPU, 16 GB RAM; S50 = 16 vCPU, 32 GB RAM; S60 = 32 vCPU, 64 GB RAM | per hour | $0.48/hr; $0.99/hr; $1.77/hr [S74]. S20 and S30 are $0.12/hr and $0.24/hr [S74] | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas on AWS and GCP | Backup (continuous / snapshot), per GB-month | EU and US | n/a | per GB-month | not found | https://www.mongodb.com/pricing [S70] | 2026-10-22 |
| MongoDB Atlas on AWS and GCP | Data transfer (egress, inter-region) | EU and US | n/a | per GB | not found | https://www.mongodb.com/pricing [S70] | 2026-10-22 |

**Derived observation (no tag needed):** The tenant data is 50 x 200 GB = 10,000 GB (10 TB). That is more than the 4 TB top storage of a dedicated cluster shown on the pricing page [S74]. 10,000 / 4,000 = 2.5, so the workload needs at least 3 clusters or shards. The cost model must therefore use a sharded cluster or the 128 TB-per-shard option [S3]. Confirm this against the Atlas docs.

**Gaps**
- The M40, M50, M60 and M80 per-hour prices for AWS and GCP in the EU and US regions are not found. The dedicated pricing table is rendered in a modal ("View dedicated pricing") and was cut off in the text I captured. Closest cited figure: the entry price of $0.08/hour, $56.94/month [S74]. This is not an M40+ price and must not be used for sizing. I did not estimate anything.
- Storage per GB, backup (snapshot and continuous), data transfer (egress and inter-region), and region price differences are all not found. Documentation to check: https://www.mongodb.com/docs/atlas/billing/ and https://www.mongodb.com/pricing.
- Sharding limits are only partly covered: the 4 TB dedicated-cluster maximum [S74] and 128 TB per HA shard for the enhanced-performance option [S73]. Maximum shard count and the per-tier storage included are not found.
- The identity of the "S20–S60" table is unconfirmed. Do not treat it as a core database price.
- Only 1 of 4 allowed fetches was used. The Atlas cluster-tier docs and the AWS/GCP price-by-region pages were not fetched, so a later step should fetch them.
- Atlas is not yet priced for the cost estimate, so that step should mark Atlas M40–M80 cost as "not found" or use a documented figure from a follow-up fetch.
MISSING DATA: Atlas M40/M50/M60/M80 hourly prices on AWS (EU and US regions) — https://www.mongodb.com/pricing (dedicated pricing modal not rendered in fetched text)
MISSING DATA: Atlas M40/M50/M60/M80 hourly prices on GCP (EU and US regions) — https://www.mongodb.com/pricing
MISSING DATA: Atlas storage per GB, backup, data transfer and inter-region transfer prices — https://www.mongodb.com/pricing
MISSING DATA: Atlas sharding limits (max shards, per-tier storage) — not on the fetched pricing page
