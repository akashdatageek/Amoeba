**GCP managed PostgreSQL pricing: PARTIAL.** Cloud SQL compute is captured. Cloud SQL storage, backup, egress and support are not captured. AlloyDB has no figures because no AlloyDB page was fetched.

Capture date for every row: "as of 22 Oct 2026" (today, Chicago). The fetch timestamp is 2026-10-23T04:15 UTC [S63]. I did not find a newer value because I ran out of turns.

Source for the Cloud SQL rows: https://cloud.google.com/sql/docs/postgres/pricing, saved as [S63] and read through [S65], [S66] and [S67]. The fetch tool titled the page "404 Page Not Found" but returned the full pricing text [S63], so the figures are usable.

**Caveats on the Cloud SQL figures**
- The text dump of the pricing table does not show which column or region each price belongs to. The page uses a region dropdown, and the table has three unlabelled price columns [S66].
- I read the first column as on-demand Enterprise-edition pricing. I read the next two as 1-year and 3-year committed-use discounts, based on a "Cloud SQL CUD - 1 Y…" label [S65]. This is inferred, not confirmed.
- The default table's region is not shown in the text. I could not confirm that it is us-central1.
- I did not capture europe-west3 prices.
- Monthly figures use 730 hours per month. This is my assumption (8,760 h per year ÷ 12 months), not a figure from the page.
- Memory sizing uses the page's Enterprise maximum of 96 vCPU / 624 GiB [S67]. That is 624 ÷ 96 = 6.5 GiB per vCPU, so 16 vCPU gets 16 × 6.5 = 104 GiB and 32 vCPU gets 32 × 6.5 = 208 GiB.

| Service | Machine / unit | Region | USD price | URL | Date captured | Status |
|---|---|---|---|---|---|---|
| Cloud SQL PG (Enterprise) | vCPU, single zone, per hour | default table; region not confirmed (us-central1 not verified) | $0.0413 [S66] | https://cloud.google.com/sql/docs/postgres/pricing | as of 22 Oct 2026 [S63] | read from page; column and region inferred |
| Cloud SQL PG | Memory, single zone, per GiB-hour | same | $0.007 [S66] | same | as of 22 Oct 2026 [S63] | same |
| Cloud SQL PG | HA vCPU, per hour | same | $0.0826 [S66] | same | as of 22 Oct 2026 [S63] | same |
| Cloud SQL PG | HA memory, per GiB-hour | same | $0.014 [S66] | same | as of 22 Oct 2026 [S63] | same |
| Cloud SQL PG | CUD columns (assumed 1-year and 3-year): vCPU $0.030975 and $0.019824 per hour; HA vCPU $0.06195 and $0.039648 per hour | same | see left [S66] | same | as of 22 Oct 2026 [S63] | column meaning inferred [S65] |
| Cloud SQL PG | Derived: 16 vCPU / 104 GiB, single zone | same | (16 × 0.0413 + 104 × 0.007) × 730 = 1.3888 × 730 ≈ $1,014/month | same | as of 22 Oct 2026 [S63] | estimate, derived from rows 1–2 |
| Cloud SQL PG | Derived: 16 vCPU / 104 GiB, HA | same | (16 × 0.0826 + 104 × 0.014) × 730 = 2.7776 × 730 ≈ $2,028/month | same | as of 22 Oct 2026 [S63] | estimate, derived from rows 3–4 |
| Cloud SQL PG | Derived: 32 vCPU / 208 GiB, HA | same | (32 × 0.0826 + 208 × 0.014) × 730 = 5.5552 × 730 ≈ $4,055/month | same | as of 22 Oct 2026 [S63] | estimate, derived from rows 3–4 |
| Cloud SQL PG | Data cache storage (HA), per GiB-hour. This is the cache add-on, not the main storage price. | Enterprise Plus; region not confirmed | $0.000438356 [S66] | same | as of 22 Oct 2026 [S63] | read from page; column unclear |
| Cloud SQL PG | SSD storage, per GB-month | europe-west3 / us-central1 | NOT CAPTURED | same | as of 22 Oct 2026 [S63] | the page says storage and network prices depend on the region dropdown [S67]; values are not in my extract |
| Cloud SQL PG | Backup storage, per GB-month | europe-west3 / us-central1 | NOT CAPTURED | same | as of 22 Oct 2026 [S63] | not read |
| Cloud SQL PG | Cross-region replica and network egress, per GB | europe-west3 → us-central1 | NOT CAPTURED | same | as of 22 Oct 2026 [S63] | not read |
| Cloud SQL PG | I/O charge | any | none seen. The page only mentions provisioned IOPS and throughput above the baseline of 3,000 IOPS for the higher-performance storage option [S67]. | same | as of 22 Oct 2026 [S63] | partial; the extract was truncated |
| Cloud SQL PG | Support plan | n/a | NOT CAPTURED (not on this page) | n/a | as of 22 Oct 2026 | needs the Google Cloud support pricing page |
| AlloyDB for PostgreSQL | vCPU and memory per hour (HA), 16–64 vCPU | europe-west3 / us-central1 | NOT CAPTURED | https://cloud.google.com/alloydb/pricing (not fetched) | as of 22 Oct 2026 | no data |
| AlloyDB | Storage per GB-month, backup per GB-month, egress and cross-region replica | europe-west3 / us-central1 | NOT CAPTURED | same (not fetched) | as of 22 Oct 2026 | no data |

**What the next step should do**
- Fetch the AlloyDB pricing page.
- Fetch the Cloud SQL storage section for both regions.
- Fetch the GCP network egress pricing page.
- Fetch the GCP support pricing page.
- Until then, the cost model should mark GCP storage, backup, egress, support and all AlloyDB lines as "estimate" or "missing". It must not invent values.
- Treat the derived monthly rows as estimates until the region and column are confirmed.

MISSING DATA: AlloyDB compute, storage, backup and egress prices — no AlloyDB page was fetched in this step.
MISSING DATA: Cloud SQL PostgreSQL SSD storage $/GB-month for europe-west3 and us-central1 — pricing page dump truncated, region dropdown not rendered.
MISSING DATA: Cloud SQL backup storage $/GB-month — not read from page.
MISSING DATA: GCP cross-region replica and network egress $/GB — not read.
MISSING DATA: GCP support plan pricing — not on the Cloud SQL page.
MISSING DATA: Confirmation of the region and column headers of the Cloud SQL compute price table — only unlabelled price columns seen.
MISSING DATA: Cloud SQL europe-west3 compute prices — only one default-region table was seen.
MISSING DATA: AlloyDB compute, storage, backup and egress prices — no AlloyDB page fetched
MISSING DATA: Cloud SQL PostgreSQL SSD storage $/GB-month for europe-west3 and us-central1 — pricing page dump (S63) truncated, region dropdown not rendered
MISSING DATA: Cloud SQL backup storage $/GB-month — not read from S63
MISSING DATA: GCP cross-region replica / network egress $/GB — not read
MISSING DATA: GCP support plan pricing — not on the Cloud SQL page
MISSING DATA: Region and column headers of the Cloud SQL compute table — S66 shows unlabelled columns
MISSING DATA: Cloud SQL europe-west3 compute prices — only one default-region table seen
