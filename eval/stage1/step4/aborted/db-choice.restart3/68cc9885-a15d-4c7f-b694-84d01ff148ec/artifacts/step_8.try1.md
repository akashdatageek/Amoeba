I read "multi-tenant" as Shared database with a tenant ID column or tenant field; if you meant Separate schema or database per tenant, the answer below may not apply.

# Step 8: monthly cost estimate for 50 tenants x 200 GB at 5,000 queries/min (prices as of 2026-10-22)

**All figures are estimates from public list prices where found and from labelled assumptions where not. They are not vendor quotes.**

**File:** `cost_model.xlsx` (sheets Assumptions, Prices, Model, Summary). The LibreOffice recalculation (recalc.py) reported 565 formulas and 0 errors [S107]. Model column L is `=SUM(G:K)`, per-tenant cost is `=L/tenants`, and Summary rows pull from Model by formula.

**Status: partial. Open items:**
1. Assumptions!E8 (the total vCPU, 48) is still a typed number. It should be `=SUM(C8:D8)`. My fix attempt was refused by the sandbox (a `cd /workspace` command), so it was not applied. Set it by hand before relying on that cell. Nothing else in the workbook is known to depend on it.
2. I did not read back the values of 10 Summary rows plus the EU 20% and 50% sensitivity rows (see the table). I will not invent them.
3. No separate by-hand recomputation was done. The "calc re-check" is the LibreOffice recalculation [S107]. The two read-back spot checks are consistent: 8,667 / 50 = 173.3, and 18,190 / 50 = 363.8.

## 1. Workload
- 50 tenants x 200 GB = 10,000 GB raw (10 TB).
- Peak 5,000 / 60 = 83.3 queries per second across all tenants.
- EU share: 50% base, with sensitivity at 20% and 100%. HA required.

## 2. Sizing (every number below is a labelled assumption in the Assumptions sheet, [unverified])
- **PostgreSQL nodes (RDS, Aurora, Cloud SQL, AlloyDB):** 16 / 32 / 48 vCPU for low / base / high, at 8 GB RAM per vCPU [unverified].
  - Basis: 83.3 qps x 0.2 / 0.4 / 0.6 CPU-seconds per query [unverified] = 16.7 / 33.3 / 50 busy cores. That is about 17 / 33 / 50 cores, rounded to the vCPU steps.
  - The hot set is 10-20% of 10,000 GB = 1-2 TB. It cannot be fully cached, so the memory-optimised class is used.
- **Storage footprint:**
  - PostgreSQL: 1.25 / 1.4 / 1.5 x raw (the role-card range [unverified]).
  - MongoDB: compression 0.5 / 0.7 / 1.0 plus indexes 0.15 / 0.2 / 0.25 [unverified]. That gives 0.65 / 0.9 / 1.25 x raw (0.5+0.15, 0.7+0.2, 1.0+0.25).
  - The step 7 prototype ratio is not used. It came from a proxy (sqlite and Python dicts), not a real engine [step 7].
- **Atlas sharding is forced.**
  - The pricing page shows a 4 TB maximum for a dedicated cluster [S74]. The data is 10 TB.
  - Target size per shard is 3,000 / 2,500 / 2,000 GB [unverified]. Shards = ROUNDUP(footprint / target). Base gives 4 shards x 3 nodes in the Model sheet.
  - The enhanced-performance option (128 TB per HA shard) has no captured price and is not costed [S73].
- **Replicas and copies:**
  - RDS: Multi-AZ primary plus 1 read replica = 3 compute units and 3 storage copies.
  - Aurora: writer plus 1 reader, with 1 shared storage copy.
  - Cloud SQL: an HA node plus a standard node, with 3 storage copies.
  - AlloyDB: 2 nodes.
- **EU handling:** regional blend factor = (1 + EU share x (EU uplift - 1)) x (1 + split overhead, applied only when the EU share is strictly between 0 and 1).
  - EU uplift 1.0 / 1.1 / 1.2 and split overhead 10 / 15 / 20%. EU-region rates were not found on the fetched pages [S57][S61][S65][S66][S70].
  - EU backups and DR copies stay inside the EU.
  - The inter-region transfer line models a copy to a second EU region, with 2 / 5 / 10% of the footprint changing per month [unverified].

## 3. Price rows (URL, date 2026-10-22; I found no newer figure)
**LIST rows (found on fetched pages):**

| Item | Price | Source |
|---|---|---|
| Aurora storage (region and configuration not stated) | $0.225/GB-month | [S63] via [S61], https://aws.amazon.com/rds/aurora/pricing/ |
| Cloud SQL vCPU (region not confirmed) | $0.0413/vCPU-hour | [S67], https://cloud.google.com/sql/pricing |
| Cloud SQL HA vCPU | $0.0826/vCPU-hour | [S67], same URL |
| Cloud SQL memory | $0.007/GiB-hour | [S69], same URL |
| Cloud SQL SSD | 0.000465753 x 730 = $0.34/GiB-month | [S66], same URL |
| Cloud SQL backup | 0.000109589 x 730 = $0.08/GiB-month | [S106], same URL |
| AlloyDB vCPU (column meaning unconfirmed) | $0.06608/vCPU-hour | [S106], https://cloud.google.com/alloydb/pricing |
| AlloyDB memory | $0.0112/GiB-hour | [S106], same URL |
| AlloyDB storage | 0.0004109 x 730 = $0.30/GiB-month | [S66], same URL |
| AlloyDB backup | 0.000137 x 730 = $0.10/GiB-month | [S69], same URL |
| GCP internet egress (tier and region unconfirmed) | $0.19/GiB | [S106] |

**ASSUMPTION rows (price not found; all [unverified]):**
- RDS: vCPU $0.13/hour, gp3 $0.115/GB-month, backup $0.095/GB-month, IOPS $0.02.
- Aurora: vCPU $0.145/hour, backup $0.021/GB-month, I/O $0.20 per million requests.
- Atlas M50 / M60 / M80 node-hour: $2.00 / $3.95 / $7.30, for both AWS and GCP.
- Atlas storage $0.30/GB-month and backup $0.14/GB-month.
- AWS egress $0.09/GB, AWS inter-region $0.02/GB, GCP inter-region $0.05/GiB.
- Cloud SQL HA memory $0.014/GiB-hour, assumed at 2x single memory (0.007 x 2), the same ratio as the vCPU rate.
- A widening factor of 0.85 / 1.0 / 1.25 [unverified] is applied to these rows, so the low/base/high spread also covers the missing prices.

The only Atlas entry price captured is $0.08/hour, "starts at $56.94/month" [S74]. It is not an M40+ price and is not used.

## 4. Results (EU 50% unless stated; rounded; read back from the recalculated workbook [S107])

| provider | database | scenario | monthly USD (estimate) | USD per tenant |
|---|---|---|---|---|
| AWS | RDS PostgreSQL | Low | 8,667 [S107] | 173 |
| AWS | RDS PostgreSQL | Base | 18,190 [S107] | 364 |
| AWS | RDS PostgreSQL | High | 35,021 [S107] | 700 |
| AWS | Aurora PostgreSQL | Low | 6,991 [S107] | 140 |
| AWS | Aurora PostgreSQL | Base | 13,887 [S107] | 278 |
| AWS | Aurora PostgreSQL | High | 26,340 [S107] | 527 |
| GCP | Cloud SQL PostgreSQL | Low | 17,995 [S107] | 360 |
| GCP | Cloud SQL PostgreSQL | Base | in Summary sheet, not read back | not read back |
| GCP | Cloud SQL PostgreSQL | High | in Summary sheet, not read back | not read back |
| GCP | AlloyDB | Low | in Summary sheet, not read back | not read back |
| GCP | AlloyDB | Base | in Summary sheet, not read back | not read back |
| GCP | AlloyDB | High | in Summary sheet, not read back | not read back |
| AWS | MongoDB Atlas | Low | in Summary sheet, not read back | not read back |
| AWS | MongoDB Atlas | Base | in Summary sheet, not read back | not read back |
| AWS | MongoDB Atlas | High | in Summary sheet, not read back | not read back |
| GCP | MongoDB Atlas | Low | in Summary sheet, not read back | not read back |
| GCP | MongoDB Atlas | Base | in Summary sheet, not read back | not read back |
| GCP | MongoDB Atlas | High | in Summary sheet, not read back | not read back |
| GCP | Cloud SQL PostgreSQL | Base, EU 100% | 24,173 [S107] | 483 |
| GCP | AlloyDB | Base, EU 100% | 13,769 [S107] | 275 |
| AWS | MongoDB Atlas | Base, EU 100% | 47,903 [S107] | 958 |
| GCP | MongoDB Atlas | Base, EU 100% | 48,016 [S107] | 960 |

The Summary sheet has 36 rows:
- 18 main rows: 6 combinations x low/base/high.
- 18 sensitivity rows: 6 combinations at base with EU share 20%, 50% and 100%.
- Not read back: the EU 20% and 50% sensitivity rows, and the RDS and Aurora EU 100% rows.

## 5. Main cost drivers (from the rows read back)
- **Atlas, base case:** compute dominates. 4 shards x 3 nodes x $3.95 x 730 x 1.1 = $38,062 of the $47,903 total at EU 100% [S107]. The $3.95 is an assumed price, so the Atlas figures carry the most uncertainty.
- **Cloud SQL:** storage is the largest line, $14,025 of $17,995 in the low case [S107]. That is 3 copies of a 1.25x footprint at the list SSD price [S106].
- **RDS:** compute is the largest line in the base case, $11,001 of $18,190, followed by storage at $5,832 [S107].
- **Aurora:** compute is $8,180 of $13,887 in the base case. The I/O line is $1,587 in base and $4,336 in high, driven by the assumed I/O request rates [S107].
- **EU share:** going to 100% removes the split overhead but applies the full EU uplift.
- **Transfer and backup:** small lines, under $1,000 per month in the cases read back [S107].

## 6. Limits and caveats
- AWS RDS and Aurora hourly instance prices, Atlas M40-M80 prices, and Atlas, Cloud SQL and AWS backup and transfer prices were not found [S57][S61][S65][S70]. The workbook marks them as assumptions. Re-price with the AWS Pricing Calculator, the Google Cloud Pricing Calculator and the Atlas pricing modal before relying on any total.
- The GCP regions of the Cloud SQL and AlloyDB tables are unconfirmed [S68][S69]. The Aurora $0.225 storage figure has no stated region or configuration [S63].
- The step 7 prototype was a proxy, so no performance evidence or real-engine storage ratio feeds this model.
- Because the spread is built on assumed prices, the cost gap between Atlas and the PostgreSQL options is not a reliable basis for the recommendation until the Atlas M-tier prices are confirmed.
BLOCKED: local:Bash — the fix for the typed number in Assumptions!E8 (should be =SUM(C8:D8)) and the read-back of the remaining Summary rows were refused as an unsafe command (cd /workspace), so neither was done
MISSING DATA: RDS and Aurora PostgreSQL hourly instance prices, eu-west-1 and US East — AWS pricing pages [S57][S61]; modelled as labelled assumptions
MISSING DATA: Atlas M40-M80 hourly prices, storage, backup and transfer on AWS and GCP — MongoDB pricing page [S70]; modelled as labelled assumptions
MISSING DATA: Cloud SQL and AlloyDB EU-region tables, and the meaning of the AlloyDB price columns — GCP pricing pages [S65][S66]
MISSING DATA: Read-back values of the Cloud SQL Base/High, AlloyDB, Atlas and EU 20%/50% sensitivity rows — cost_model.xlsx Summary; not read back
