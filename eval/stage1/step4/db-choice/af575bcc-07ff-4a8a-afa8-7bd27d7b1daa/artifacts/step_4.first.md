**Atlas dedicated-tier pricing: what was confirmed**
Source: MongoDB list price page, https://www.mongodb.com/pricing [S76][S77]. Captured 2026-10-23T04:17 UTC, which is the evening of 2026-10-22 Chicago time. Every figure below is "as of 2026-10-22". I found no newer or more specific source before my turns ran out.

Limits of the capture:
- The excerpt I read shows the dedicated-tier table but not the cloud-provider or region selector. I cannot say whether these $/hour figures are AWS, GCP or a reference region, so I have not assigned them to either cloud.
- No EU-region or US-region price was confirmed.
- No separate AWS-versus-GCP price was confirmed.
- Backup, data-transfer and support prices were not captured (see missing_data).

| Cloud | Tier | vCPU / RAM | Region | $/hour (per node, as listed, as of 2026-10-22) | Storage range listed (per node, as of 2026-10-22) | Backup / transfer | URL | Date captured |
|---|---|---|---|---|---|---|---|---|
| Atlas, cloud not shown in excerpt (AWS/GCP unconfirmed) | M40 | 4 vCPU / 16 GB [S76] | Not shown (unconfirmed) | $1.04/hr [S76] | 80 GB–1 TB [S76] | Not captured | https://www.mongodb.com/pricing | 2026-10-22 |
| same | M50 | 8 vCPU / 32 GB [S76] | Not shown | $2.00/hr [S76] | 160 GB–4 TB [S76] | Not captured | https://www.mongodb.com/pricing | 2026-10-22 |
| same | M60 | 16 vCPU / 64 GB [S76] | Not shown | $3.95/hr [S76] | 320 GB–4 TB [S76] | Not captured | https://www.mongodb.com/pricing | 2026-10-22 |
| same | M80 | 32 vCPU / 128 GB [S76] | Not shown | $7.30/hr [S76] | 750 GB–4 TB [S76] | Not captured | https://www.mongodb.com/pricing | 2026-10-22 |
| same | M140 | 48 vCPU / 192 GB [S76] | Not shown | $10.99/hr [S76] | 1–4 TB [S76] | Not captured | https://www.mongodb.com/pricing | 2026-10-22 |
| same | M200 | 64 vCPU / 256 GB [S76] | Not shown | $/hr not visible in my excerpt (cut off) | 1.5–4 TB [S76] | Not captured | https://www.mongodb.com/pricing | 2026-10-22 |
| Atlas on AWS, EU region (e.g. Frankfurt/Ireland) | M60/M80 | – | EU | NOT FOUND | – | NOT FOUND | https://www.mongodb.com/pricing (cloud/region selector not visible in the excerpt) | 2026-10-22 |
| Atlas on AWS, US region | M60/M80 | – | US | NOT FOUND | – | NOT FOUND | same | 2026-10-22 |
| Atlas on GCP, EU region | M60/M80 | – | EU | NOT FOUND | – | NOT FOUND | same | 2026-10-22 |
| Atlas on GCP, US region | M60/M80 | – | US | NOT FOUND | – | NOT FOUND | same | 2026-10-22 |

Cost-model consequence: until the missing rows are filled, use the M60 and M80 rows above as a **provisional, cloud-unspecified list price**. Label them "page list price, cloud/region unconfirmed" in the workbook. As a rough check, M80 at $7.30/hr [S76] x 730 h/month = $5,329 per node per month. The 730 h is 8,760 h per year / 12 [unverified: my own convention]. This is arithmetic on the unconfirmed list price. It needs a replica-set node multiplier that I did not verify. Do not present it as an AWS or GCP price.

**Sharding note**
- The listed maximum storage for every tier from M50 to M200 is 4 TB per node (as of 2026-10-22) [S76].
- Volume: 50 x 200 GB = 10,000 GB raw (task input). That is above 4 TB x 1,000 GB/TB = 4,000 GB.
- If Atlas disk usage equals raw data size, 10 TB needs at least ceil(10/4) = 3 shards. In practice use 4 or more for headroom.
- Peak load is 5,000 QPM / 60 = 83.3 QPS (task input, divided by 60 s). That is a light query load, so shard count is driven by storage rather than throughput.
- If the 0.5 compression ratio (role-card default, not yet measured) holds, data is 10,000 GB x 0.5 = 5,000 GB before indexes. That is still above 4,000 GB, so at least 2 shards, or several clusters, are needed once indexes are added.
- The alternative is multiple clusters, for example one per tenant group or one per region. That also fits EU/US residency, because EU tenants stay in an EU cluster.
- Either way the compute cost is multiplied by the number of shards (each shard is a replica set) or clusters. The cost model should include a "shard/cluster count" input and not assume a single cluster. [unverified: shard and replica-set multiplication is general knowledge, not read from a source]
- Whether the 4 TB limit applies identically on AWS and GCP was not confirmed. [S76] shows one table with no per-cloud split in my excerpt.

**Not confirmed (must not be treated as facts)**
- Cloud backup $/GB-month.
- Data transfer rates.
- Support plan prices.
- Storage $/GB, and whether storage is bundled into the tier price.
- Per-cloud and per-region price differences, and the M200 hourly rate.
MISSING DATA: Atlas cloud/region selector for the tier table (AWS vs GCP, EU vs US) — mongodb.com/pricing excerpt (S76) did not show it
MISSING DATA: Atlas Cloud Backup $/GB-month — not in the read portion of mongodb.com/pricing
MISSING DATA: Atlas data transfer prices (inter-region, internet egress) — not found
MISSING DATA: Atlas support plan prices — not found
MISSING DATA: Atlas storage $/GB (or confirmation it is bundled with the tier) — not found
MISSING DATA: M200 $/hour — cut off in excerpt
MISSING DATA: Atlas on GCP rows (EU and US) and Atlas on AWS EU/US rows — not found; no per-cloud price capture
