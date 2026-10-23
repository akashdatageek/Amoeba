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
