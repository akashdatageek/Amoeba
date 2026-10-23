Verdict: FAIL
CITATION VERIFICATION, steps 1-4. Checked 22 Oct 2026 (America/Chicago). Not legal advice; this is a technical citation check.

Method. I re-opened the saved source files under sources/ with grep (local:Bash, results [S123], [S125], [S126]). I did not re-fetch live URLs, because only the local tools were usable in this last turn. "Pass" means the saved page text supports the figure. "Unverifiable" means I could not read the page text that would show it. I did not count unverifiable items as pass.

CHECKS TABLE (citation x step x finding x pass/fail)
| # | Citation | Step | Finding | Result |
|---|---|---|---|---|
| 1 | S4 EnterpriseDB/OnGres whitepaper, https://info.enterprisedb.com/rs/069-ALB-339/images/PostgreSQL_MongoDB_Benchmark-WhitepaperFinal.pdf | 1 | Sponsor label is correct. The page says "EnterpriseDB ... sponsored the work" and that OnGres ran it [S123]. Step 1 labelled it vendor-sponsored. | PASS (sponsor label) |
| 2 | S4, headline result and age | 1 | The page states "PostgreSQL 11 was found to be faster than MongoDB 4.0 in almost every benchmark", with throughput up to one or two orders of magnitude higher [S123]. Step 1 said no headline was captured and gave "Date not extracted". It also described the study as OLTP-style, but the page covers Transactions, OLTP and OLAP benchmarks [S35]. PostgreSQL 11 and MongoDB 4.0 are old releases, so the study is dated and its age should be stated. | FAIL (headline and versions omitted; age not flagged) |
| 3 | S3 dev.to (hamzakhan), https://dev.to/hamzakhan/postgresql-vs-mongodb-in-2025-which-database-should-power-your-next-project-2h97 | 1 | The page shows "Posted on Aug 11, 2025" [S34]. Step 1 said the date was not extracted, so the date was available and missed. | FAIL (date missing) |
| 4 | S2 Bytebase, https://www.bytebase.com/blog/postgres-vs-mongodb | 1 | The page shows "Tianzhou · Feb 27, 2025" [S126]. Step 1 said the date was not extracted. | FAIL (date missing) |
| 5 | S14 Medium (yurexus), https://medium.com/@yurexus/can-postgresql-with-its-jsonb-column-type-replace-mongodb-30dc7feffaf3 | 1 | The page is dated Aug 2, 2023. It tested PostgreSQL 14.6 and MongoDB 6.0.3 at the start of 2023 [S126]. It also states "MongoDB is substantially faster than PostgreSQL on inserts" and that PostgreSQL JSONB is "very inefficient in terms of storage space" [S33]. Step 1 said "Not captured" for the result and gave no date. The storage finding bears directly on the cost model's PostgreSQL storage ratio. | FAIL (date and findings omitted) |
| 6 | S1 tech-insider.org (2026) and S27 mongodb.com compare page | 1 | S1 has no publication date in the lines I grepped. For S27, my grep for "benchmark/faster" was cut off, so I did not see whether it holds any figures. The S27 label "MongoDB marketing" is reasonable. | UNVERIFIABLE (S1 date; S27 content); sponsor labels not contradicted |
| 7 | S76 https://www.mongodb.com/pricing, M40-M80 | 4 | M40 $1.04/hr, M50 $2.00/hr, M60 $3.95/hr, M80 $7.30/hr, M140 $10.99/hr, with storage ranges 80 GB-1 TB, 160 GB-4 TB, 320 GB-4 TB, 750 GB-4 TB, 1-4 TB [S125]. All match step 4. | PASS |
| 8 | S76, M200 | 4 | Step 4 said the M200 $/hr was cut off. The page shows "M200 \| 1.5-4 TB \| 256 GB \| 64 vCPUs \| $14.59/hr", and M400 at $22.40/hr [S125]. The missing figure exists. | FAIL (stale gap, now fillable) |
| 9 | S76, cloud and region (AWS vs GCP, EU vs US) | 4 | The table does not state a cloud or region. Step 4 correctly refused to assign it to AWS or GCP. Its $/hr x 730 h and "at least 3 shards" arithmetic is correct: 7.30 x 730 = 5,329; ceil(10/4) = 3. | PASS (honest limitation) |
| 10 | S63 Cloud SQL, https://cloud.google.com/sql/docs/postgres/pricing | 3 | vCPU $0.0413/hr, memory $0.007/GiB-hr, HA vCPU $0.0826/hr [S125][S126]. The other two columns are $0.030975 (0.75 x 0.0413) and $0.019824 (about 0.48 x 0.0413), consistent with the 1-year and 3-year committed-use discounts step 3 inferred. HA memory $0.014 was not visible in my cut-off output; step 3 cites it from [S66]. The page title reads "404 Page Not Found" yet the content is the pricing page. The region is not shown. | PASS for the three figures I saw; HA memory and region UNVERIFIED |
| 11 | S63 derived rows, recomputed | 3 | 16 x 0.0413 + 104 x 0.007 = 1.3888, x 730 = $1,013.8. HA: 2.7776 x 730 = $2,027.6. 32 vCPU HA: 5.5552 x 730 = $4,055.0. All match step 3's $1,014, $2,028 and $4,055. | PASS |
| 12 | S39 AWS RDS PostgreSQL pricing, https://aws.amazon.com/rds/postgresql/pricing/ | 2 | The Extended Support surcharge matches: $0.100 per vCPU-hr between March 1, 2025 and February 28, 2027, and $0.200 from March 1, 2027, with a US East (Ohio) example [S126]. Step 2 correctly named us-east-2. The page text holds no instance, GB or I/O prices. Step 2 flagged this, and its remaining rows are marked estimate or missing. | PASS for R1; all other AWS rows UNVERIFIABLE (not in page text) |
| 13 | S51 Aurora pricing, https://aws.amazon.com/rds/aurora/pricing/ | 2 | I did not re-read this page. Step 2 says it holds no USD tables. | UNVERIFIABLE |
| 14 | S40/S41 prices.json | 2 | These are AWS SMS price lists, not database prices [S54, per step 2]. Step 2 correctly ignored them. | PASS |
| 15 | Givens, recomputed | 2-4 | 50 x 200 = 10,000 GB. 5,000/60 = 83.3 QPS. 10,000 x 1.3 = 13,000 GB. Steps 2-4 use these correctly. No step builds an HA compute total. Step 3 prices HA, and step 4 notes the replica-set multiplier without verifying it. | PASS |

Re-checks I ran: S76 tier table grep, S63 compute-row grep, S39 Extended Support grep, S4 sponsor and headline grep, publication-date greps on S3, S2 and S14, and hand recomputation of rows 11 and 15.
Date basis: step 1's own pages carry dates (S3 Aug 2025, S2 Feb 2025, S14 Aug 2023). The only newer-source search I ran was none. No newer source was found, and none of the step outputs show a newer-value search either.

SPONSOR LABELLING. The EDB/OnGres study is labelled vendor-sponsored (pass). The MongoDB page is labelled vendor marketing (pass). One omission: S15, a MongoDB blog on update-heavy PostgreSQL JSONB vs MongoDB BSON, was fetched in step 1 but is missing from the table. It is MongoDB-published and would need a sponsor label.

FIX LIST
1. Step 1: add the correct dates from the pages. S3 is Aug 11, 2025. S2 is Feb 27, 2025. S14 is Aug 2, 2023 [S34][S126]. Remove "the evidence cannot be shown fresh" as applied to these.
2. Step 1: state S4's headline and age. It is OnGres for EDB, PostgreSQL 11 vs MongoDB 4.0, with PostgreSQL faster in almost every test, and it covers Transactions, OLTP and OLAP [S123][S35]. Label it dated and sponsored, and low weight for current versions.
3. Step 1: add S14's findings. MongoDB was substantially faster on inserts, and PostgreSQL JSONB used far more storage [S33]. Feed this into the storage-ratio assumption, rather than a flat 1.3, until the prototype measures it. Add S15 with a MongoDB-sponsored label.
4. Step 4: fill M200 at $14.59/hr (and M400 at $22.40/hr) [S125].
5. Step 2: all AWS prices other than R1 are estimates or missing. The cost model must not present them as verified. Obtain figures from the AWS Price List API or Pricing Calculator for eu-central-1 and us-east-1. Step 3: confirm the Cloud SQL region and column headers, HA memory $0.014, europe-west3 prices, storage, backup, egress and AlloyDB.
6. Step 4: find the AWS/GCP and EU/US price split, plus backup, transfer and support prices. Until then the cost model has no verified Atlas cloud-specific figure.
7. Re-fetch S1 and S27 to confirm their dates and any benchmark figures.

Coverage: 15 rows, at least 2 per step across steps 1-4, and 4 of them unverifiable. Confirmed: 8 pass items. Not confirmed: AWS RDS/Aurora instance, storage and I/O prices, S1 and S27 content, Cloud SQL region.

VERDICT: FAIL
MISSING DATA: AWS RDS/Aurora instance, storage and I/O prices (eu-central-1, us-east-1) — not in the saved page text of S39 or S51
MISSING DATA: Cloud SQL region and column confirmation, HA memory $0.014 visibility — S63 grep output cut off
MISSING DATA: S1 publication date and S27 benchmark content — grep output cut off
Issues:
1. Step 1: publication dates for S3 (Aug 11, 2025), S2 (Feb 27, 2025) and S14 (Aug 2, 2023) exist on the pages but were reported as 'not extracted'. Fix: add the dates and revise the freshness conclusion.
2. Step 1: S4's headline (PostgreSQL 11 faster than MongoDB 4.0 in almost every benchmark; Transactions, OLTP and OLAP) was omitted and its old versions were not flagged. Fix: state the headline, the versions and 'dated, EDB-sponsored'.
3. Step 1: S14's findings (MongoDB faster on inserts; PostgreSQL JSONB much larger in storage) were omitted, though they affect the cost model's storage ratio. S15 (a MongoDB blog) was fetched but not tabled or labelled. Fix: add both with sponsor labels.
4. Step 4: the M200 price was reported as cut off, but S76 shows $14.59/hr (M400 $22.40/hr). Fix: fill the figures.
5. Step 2: only the Extended Support surcharge (R1) is verified. Other AWS prices are memory estimates or missing, so the cost model has no verified AWS figure. Fix: use the AWS Price List API or Pricing Calculator.
6. Step 3: the Cloud SQL region and column headers are unconfirmed, HA memory $0.014 was not re-verified, and there is no AlloyDB, storage, backup or egress data. Fix: fetch these.
7. Step 4: no AWS-versus-GCP or EU-versus-US Atlas split, and no backup, transfer or support prices. Fix: capture them.
