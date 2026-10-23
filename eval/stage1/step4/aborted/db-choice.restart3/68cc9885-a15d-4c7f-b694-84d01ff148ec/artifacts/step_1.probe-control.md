I read "multi-tenant" as Shared database with a tenant ID column or tenant field; if you meant Separate schema or database per tenant, the answer below may not apply.

**Benchmarks A: PostgreSQL vs MongoDB comparisons (retrieved 22 Oct 2026; the fetch index stamps 2026-10-23T03:13 UTC, the same day in Chicago [S14])**

| source | URL | date | funded by | workload | versions | result | relevance |
|---|---|---|---|---|---|---|---|
| "New Benchmarks Show Postgres Dominating MongoDB in Varied Workloads" (EnterpriseDB press release) | Press-release page on prnewswire.com. The exact URL is listed in sources/index.json [S14]. I did not copy it. Page text saved as sources/S1 [S1] | Jun 26, 2019 [S1][S18] | **Vendor-funded.** Published by EnterpriseDB (EDB), a PostgreSQL vendor [S1][S18]. | "Varied workloads", a head-to-head of the two databases [S1]. | Not found in the excerpts I read. | The headline claims Postgres is "emerging as the winner" [S1]. I did not extract numeric figures, so none are quoted. | Low to medium. It is a vendor claim dated Jun 26, 2019 [S1]. It probably does not cover Atlas, managed services or multi-tenant dashboard queries. |
| "PERFORMANCE BENCHMARK POSTGRESQL / MONGODB" (EDB whitepaper, PDF) | https://info.enterprisedb.com/rs/069-ALB-339/images/PostgreSQL_MongoDB_Benchmark-WhitepaperFinal.pdf [S2][S14] | Not found. The PDF text I scanned showed no clear publication date. The companion press release is dated Jun 26, 2019 [S1]. | **Vendor-funded** (EDB) [S2][S14]. | OLTP-style and JSON document workloads, per the title and EDB's framing. I did not confirm the workload details. | Not found in what I extracted. | Numeric results were not extracted, so none are quoted. | Medium for JSON document workloads, but it is vendor-authored and old. It is not a TPC-H/DS-style analytics test and not a shared-tenant dashboard test. |
| "MongoDB vs PostgreSQL: When NoSQL Actually Wins [2026]" (tech-insider.org) | https://tech-insider.org/mongodb-vs-postgresql-2026 [S3][S14] | The page says its guidance holds "as of April 2026" [S3]. I did not confirm a publication date. | Funder not found. It is a secondary blog or aggregator, not an original benchmark. I could not tell whether it is independent. | A decision matrix by application archetype, drawing on "data and production deployments in this comparison" [S3]. | Not confirmed in what I read. | A qualitative decision matrix [S3]. It is not a primary benchmark, and I extracted no numbers from it. | Medium for framing. It is a secondary source, so treat it as opinion until its underlying data is checked. |

**Caveats and gaps**
- **Both primary benchmark sources are vendor-funded.** S1 and S2 come from EDB, which sells PostgreSQL. They cannot be treated as independent evidence [S1][S2].
- **Little independent evidence was found.** The searches and fetches found no independent source such as an academic paper, an OnGres study, or a YCSB- or TPC-style study. An independent third-party comparison is *not found* in this step.
- **Headline numbers are missing.** I read only excerpts of these pages within the turn budget. I did not extract throughput ratios, latencies, versions or hardware, so I quote none. I will not guess them.
- **Dates:** S1 is dated Jun 26, 2019 [S1][S18], which is old relative to today, 22 Oct 2026. The S2 date is not found. S3 refers to April 2026 [S3].
- **No newer-value search was run.** The task asks for the latest figures. Any benchmark from the 2019 vintage [S1] predates current PostgreSQL and MongoDB major versions and predates Atlas as a test target. A newer search is still needed.
- **Missing workloads:** no source I read tests a shared multi-tenant schema with a tenant ID filter, the 10 TB total, or the 5,000 queries per minute peak of dashboard aggregation. Relevance to the product is therefore indirect.
- **Managed services:** none of these sources tests RDS/Aurora, Cloud SQL/AlloyDB or Atlas. Results are for self-managed or generic deployments.
- **Recommendation:** downstream steps should use these results only as vendor-claim context, not as the basis for the decision. The prototype tests and an independent benchmark search should carry the decision.
MISSING DATA: Independent (non-vendor) PostgreSQL vs MongoDB benchmark (OnGres, academic or YCSB-based) — not found in the fetched pages S1 to S3
MISSING DATA: Numeric headline results, versions and hardware for the EDB studies — not extracted from S1/S2 within the turn budget
MISSING DATA: Publication date of the EDB whitepaper PDF — not found in S2 excerpts
MISSING DATA: Funder and publication date of the tech-insider.org article — not confirmed in S3
MISSING DATA: Newer benchmark than the 2019 EDB study — no further search made
