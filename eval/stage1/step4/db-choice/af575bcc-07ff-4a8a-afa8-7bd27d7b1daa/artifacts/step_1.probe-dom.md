**Web access.** Fetches worked. Only one source (S1) showed a publication date on the page [S25][S28]. I verified no numeric benchmark results. So this table has no benchmark figures. Every row is qualitative.

**Benchmark evidence table**

| # | Source (title) | URL | Date | Workload | Result (qualitative, no figures) | Sponsor / bias | Relevance to tenant-scoped dashboards |
|---|---|---|---|---|---|---|---|
| 1 | "MongoDB vs PostgreSQL: When NoSQL Actually Wins" (tech-insider.org) [S1] | https://tech-insider.org/mongodb-vs-postgresql-2026 [S29] | Published March 25, 2026, page byline; page also says "Last updated: April 2026" [S25][S28] | General comparison article. No tenant-scoped analytics workload identified. | The title frames the question as when MongoDB wins. I extracted no verified headline number, so I give none. [S1] | Independent media or blog. I saw no sponsor in a keyword scan [S28]. Not a controlled benchmark. | Low to medium. Framing only. |
| 2 | "MongoDB Vs PostgreSQL" (mongodb.com resources/compare) [S27] | https://www.mongodb.com/resources/compare/mongodb-postgresql [S27] | Date unverified. Fetched 2026-10-23 UTC, and no publication date was seen on the page. [S27] | Vendor feature comparison | It claims MongoDB gives "more flexibility than PostgreSQL" in data modelling, horizontal scalability and developer productivity. I took no benchmark figures. [S27] | **MongoDB-sponsored (vendor-owned page).** Expect pro-MongoDB framing. | Medium for the sharding and scale-out argument. It is not evidence of analytics query speed. |
| 3 | "Postgres vs. MongoDB: a Complete Comparison" (Bytebase blog) [S2] | https://www.bytebase.com/blog/postgres-vs-mongodb [S29] | Date unverified | General comparison | Qualitative only. No figures taken. | Vendor blog from a database-tooling company. The sponsor of the comparison is unverified. | Low. Context only. |
| 4 | "PostgreSQL vs. MongoDB: Which Database Should Power Your Next Project?" (DEV Community) [S3] | https://dev.to/hamzakhan/postgresql-vs-mongodb-in-2025-which-database-should-power-your-next-project-2h97 [S29] | Date unverified | General comparison, individual author post | Qualitative only. No figures taken. | Individual blogger. Sponsor unverified. | Low. Context only. |
| 5 | "Can PostgreSQL with its JSONB column type replace MongoDB?" (Medium) [S14] | https://medium.com/@yurexus/can-postgresql-with-its-jso… (the URL was cut off in my notes; the full URL is in sources/index.json [S29]) | Date unverified | JSONB vs document model. The page shows SQL examples with a JSONB table [S14]. | Qualitative only. No figures taken. | Individual author. Sponsor unverified. | Medium. It addresses JSONB vs documents, but it is unverified. |
| 6 | "PERFORMANCE BENCHMARK POSTGRESQL MONGODB" (document) [S4] | URL not retained in my notes; see sources/index.json [S4] | Date unverified | Performance benchmark, title only. Workload and results not verified. | No figures reported. | Sponsor unverified | Potentially the closest to a real benchmark, but unusable until its date, method and sponsor are checked. |

**What I could not do**
- I found no independent time-series or multi-tenant benchmark.
- I found no benchmark with a page-verified date, a stated sponsor and figures I can cite.
- Only S1 has a page-verified date. Rows 2–6 are 'date unverified' and carry no figures.
- I did not retain the URL for S4 and the full URL for S14. A later step should read sources/index.json before quoting either.
- The work-around does not cover verified publication dates for S2, S3, S4, S14 and S27, or any numeric benchmark results.

**Takeaways: what benchmarks can and cannot say about tenant-scoped dashboards**
1. Public PostgreSQL-vs-MongoDB comparisons are skewed. Vendor pages such as [S27] favour the vendor's own strengths. Blog posts such as [S1] are generally not controlled tests. They do not replace our own prototype.
2. Most comparisons test generic CRUD or document workloads. Our workload is tenant-filtered aggregation over events: 50 tenants, with a peak of 5,000 queries per minute combined (task input, about 83.3 QPS from 5,000/60). Only a prototype with our event and dashboard schema, measuring p95 latency, can answer that.
3. MongoDB's main argument is horizontal scale-out and flexible modelling [S27]. At 10 TB total (50 x 200 GB, task input), sharding and per-tenant data layout will matter more to cost and operations than single-query speed. The cost model should capture that.
4. The JSONB-vs-documents question [S14] only matters if our events are semi-structured. If dashboards are mostly fixed-shape aggregates, a relational schema with partitioning and indexes is the fairer comparison. Check this in the prototype.
5. A benchmark figure only counts when the source states the date, version, hardware, dataset size and sponsor. I found none that does, so the cost model should label sizing as 'estimate' and use the prototype's measured p95.
MISSING DATA: Publication dates for S2, S3, S4, S14 and S27 — page text in sources/ (no byline or meta date seen)
MISSING DATA: URL for S4 and full URL for S14 — not retained in notes; see sources/index.json
MISSING DATA: Independent time-series or multi-tenant PostgreSQL vs MongoDB benchmark with figures — web search and fetch results
MISSING DATA: Numeric benchmark results with a page-verified date and sponsor — fetched pages
