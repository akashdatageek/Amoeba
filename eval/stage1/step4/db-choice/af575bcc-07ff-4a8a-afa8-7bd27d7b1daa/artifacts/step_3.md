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
