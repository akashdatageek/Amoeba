GCP Cloud SQL for PostgreSQL and AlloyDB pricing. Retrieved 2026-10-22 America/Chicago (fetch timestamps 2026-10-23T03:23 UTC [S65][S66]). Sources: https://cloud.google.com/sql/pricing [S65] and https://cloud.google.com/alloydb/pricing [S66].

Caveats:
- The pages render prices one region at a time, and my text capture did not label the Cloud SQL tables by region. The Cloud SQL rows are therefore marked "region not confirmed". The list of regions on the page starts with Iowa (us-central1) [S68], so that is a likely default, but I could not prove it.
- For AlloyDB I captured the vCPU rows for europe-west1, europe-west4, us-central1 and us-east1 [S69]. The two price columns are not labelled in my capture. The nearest header, 19 lines above, reads "Region | Year 1 & Year 2 Price (USD) | Year 3 Price (USD)" [S69]. The second column is exactly double the first. That is odd for a 3-year discount, so I do not state what the columns mean.
- All prices are on-demand or committed-use list prices as captured. I did not run a Google pricing-update date check or a second search for a newer value. I settled on the 2026-10-22 retrieval of the official pages.

| provider | service | region | tier | unit | USD price | URL | date retrieved |
|---|---|---|---|---|---|---|---|
| GCP | Cloud SQL for PostgreSQL, Enterprise, General Purpose series | not confirmed (likely us-central1) [S68] | vCPU, on-demand | per vCPU-hour | $0.0413 [S67] | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | Cloud SQL, Enterprise, General Purpose | same table, region not confirmed | vCPU, 1-year CUD / 3-year CUD | per vCPU-hour | $0.030975 / $0.019824 [S67] | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | Cloud SQL, Enterprise, General Purpose | same table, region not confirmed | HA vCPU, on-demand / 1-year CUD / 3-year CUD | per vCPU-hour | $0.0826 / $0.06195 / $0.039648 [S67] | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | Cloud SQL, Enterprise, General Purpose | same table, region not confirmed | Memory, on-demand / 1-year CUD / 3-year CUD | per GiB-hour | $0.007 / $0.00525 / $0.00336 [S69] (the same row appears in two tables; a third table shows $0.009 / $0.00675 / $0.00432 [S69] and its region or series is not identified) | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | Cloud SQL, Enterprise, N4 series | region not confirmed | vCPU / HA vCPU, on-demand | per vCPU-hour | $0.0413 / $0.0826 [S67] | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | Cloud SQL, Enterprise Plus, C4 series | region not confirmed | vCPU, on-demand / 1-year CUD / 3-year CUD | per vCPU-hour | $0.054 / $0.0405 / $0.02592 [S67] | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | Cloud SQL, Enterprise Plus, C4 series | region not confirmed | HA vCPU, on-demand / 1-year CUD / 3-year CUD | per vCPU-hour | $0.108 / $0.081 / $0.05184 [S67] | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | Cloud SQL | europe-west1 / europe-west4 | vCPU, memory, HA | per hour | not found (EU tables not captured) | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | Cloud SQL | EU and US | SSD storage; backup storage; read replica; egress and inter-region transfer | per GB-month / per hour / per GB | not found | https://cloud.google.com/sql/pricing | 2026-10-22 [S65] |
| GCP | AlloyDB for PostgreSQL | europe-west1 (Belgium) | vCPU, two price columns, headers not captured | per vCPU-hour | $0.077 and $0.154 [S69] | https://cloud.google.com/alloydb/pricing | 2026-10-22 [S66] |
| GCP | AlloyDB for PostgreSQL | europe-west4 (Netherlands) | vCPU, two price columns, headers not captured | per vCPU-hour | $0.074 and $0.147 [S69] | https://cloud.google.com/alloydb/pricing | 2026-10-22 [S66] |
| GCP | AlloyDB for PostgreSQL | us-central1 (Iowa) | vCPU, two price columns, headers not captured | per vCPU-hour | $0.07 and $0.14 [S69] | https://cloud.google.com/alloydb/pricing | 2026-10-22 [S66] |
| GCP | AlloyDB for PostgreSQL | us-east1 | vCPU, two price columns, headers not captured | per vCPU-hour | $0.079 and $0.158 [S69] | https://cloud.google.com/alloydb/pricing | 2026-10-22 [S66] |
| GCP | AlloyDB for PostgreSQL | region not confirmed (table not labelled in my capture) | Regional cluster storage | per GiB-hour | $0.0004109 [S69]. Per month, assuming 730 hours: 0.0004109 × 730 = about $0.30 per GiB-month | https://cloud.google.com/alloydb/pricing | 2026-10-22 [S66] |
| GCP | AlloyDB for PostgreSQL | region not confirmed | Standard backup storage | per GiB-hour | $0.000137 [S69]. Per month, assuming 730 hours: 0.000137 × 730 = about $0.10 per GiB-month | https://cloud.google.com/alloydb/pricing | 2026-10-22 [S66] |
| GCP | AlloyDB for PostgreSQL | EU and US | Memory, read pool instance, 8/16/32 vCPU classes, egress and inter-region transfer | per GiB-hour / per hour / per GB | not found. The page has an "Outbound traffic source and destination pairs" table [S69], but I did not capture its values. | https://cloud.google.com/alloydb/pricing | 2026-10-22 [S66] |

Derived example, vCPU charge only, using the Cloud SQL Enterprise General Purpose on-demand rate [S67]. The region is unconfirmed and 730 hours per month is my assumption. A 16-vCPU instance costs 16 × $0.0413 = $0.6608 per hour. Over a month that is 0.6608 × 730 = about $482. The HA vCPU rate, $0.0826 [S67], is exactly 2 × $0.0413. This excludes memory, storage, backup and network, so it is not a full instance cost.

Gaps:
- Cloud SQL europe-west1 and europe-west4 vCPU, memory and HA tables were not captured. The Cloud SQL rates above carry no confirmed region, and the US-region assignment (us-central1) is unproven [S68].
- Cloud SQL SSD storage per GB-month, backup storage, read replica, network egress and inter-region transfer: not found.
- AlloyDB: the meaning of the two vCPU price columns is unconfirmed [S69]. Memory per GiB-hour, read pool pricing and network egress values were not captured. The storage and backup rows carry no confirmed region.
- The 8, 16 and 32 vCPU classes are priced per vCPU-hour, so I did not capture fixed per-instance prices. Multiply the per-vCPU rate by the vCPU count.
- Next step: read the saved sources/S65 and sources/S66 files in full for the region sections and the network tables, or use the Google Cloud Pricing Calculator or the Cloud Billing SKU catalog.
MISSING DATA: Cloud SQL for PostgreSQL europe-west1/europe-west4 vCPU, memory and HA prices — https://cloud.google.com/sql/pricing (EU tables not in captured text)
MISSING DATA: Cloud SQL SSD storage, backup, read replica, egress and inter-region transfer prices — https://cloud.google.com/sql/pricing
MISSING DATA: AlloyDB memory, read pool, egress and inter-region transfer prices, and the meaning of the two vCPU price columns — https://cloud.google.com/alloydb/pricing
MISSING DATA: Region label for the Cloud SQL $0.0413 per vCPU-hour table — https://cloud.google.com/sql/pricing
