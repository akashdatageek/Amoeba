**Status: PARTIAL.** Only one source page (Bytebase) was fetched. The other rows rest on search snippets or my own memory, and each is labelled that way. I found no fetched, independent, dated benchmark of multi-tenant analytics, JSONB vs documents, or time-series. I did not run the newer-value search. The newest dated item I have is Feb 27, 2025 [S2], which is before today (22 Oct 2026). Treat this as thin evidence. These sources do not replace the prototype.

## Benchmark and comparison evidence

| Source | URL | Date | Workload | Result | Sponsor / bias | Relevance to tenant-scoped dashboards |
|---|---|---|---|---|---|---|
| "Postgres vs. MongoDB: a Complete Comparison in 2025" (Bytebase, author Tianzhou). **Page fetched.** I read only the first 6,000 of 13,991 characters, which were mostly navigation. | https://www.bytebase.com/blog/postgres-vs-mongodb | Feb 27, 2025 (as of the fetch on 2026-10-23, no newer version seen). Dated by the page [S2]. | Qualitative feature comparison (JSONB, joins, transactions, AI section). No benchmark. | Search-snippet conclusion: "Overall, Postgres is a more versatile database" [S2]. I did not read the comparison table on the page. | Bytebase sells database-tooling products (self-host and cloud links on the page) [S2]. It is vendor-adjacent and not a neutral test. | Low to medium. It is useful as a feature checklist. It has no tenant-scale latency or cost numbers. |
| "MongoDB vs PostgreSQL: When NoSQL Actually Wins [2026]" (tech-insider.org). Snippet only, not fetched. | https://tech-insider.org/mongodb-vs-postgresql-2026 | Exact publication date not shown. The title says 2026. The underlying survey is the Stack Overflow Developer Survey 2025 [S1]. Snippet, unverified. | Developer adoption survey, not a performance test. | PostgreSQL about 45% adoption vs MongoDB about 25% [S1]. Snippet, unverified. | Sponsor unknown. Editorial blog. Not independent testing. | Low. It shows popularity and hiring pool, not latency or cost. |
| Third comparison article from the same search. Title and URL were truncated in the output I read, so I could not capture them. | Not captured (the search output is in tool_results/step1_1.txt) | Title says 2025; exact date not captured. Snippet, unverified. | Qualitative "choose the right tool" advice. | "PostgreSQL has narrowed the gap on flexibility, while MongoDB has caught up on transactional integrity" [S10]. Snippet, unverified. | Unknown. | Low. Directional only. |
| EDB (EnterpriseDB) PostgreSQL vs MongoDB benchmark, recalled from memory. **Not retrieved this session.** | URL not retrieved | About 2019 [unverified]. Outside the 24-month window. | Mixed OLTP and document workloads [unverified]. | EDB reported PostgreSQL ahead on several workloads [unverified]. I did not record figures. | Vendor-sponsored by a PostgreSQL vendor [unverified]. A MongoDB-side counter-claim reportedly exists [unverified]. | Low to medium. It is old, vendor-skewed, and not an analytics or multi-tenant workload. |

Benchmarks in this space are vendor-skewed. Both PostgreSQL vendors and MongoDB tend to publish results that favour their own product. None of this replaces testing your own tenant-scoped queries in the prototype.

## Takeaways
1. **Published evidence cannot decide this choice.** What I found is opinion, a popularity survey, or old vendor material. Prototype your own tenant-filtered dashboard queries at 50 tenants x 200 GB = 10,000 GB and 5,000 / 60 = 83.3 queries per second. Use the prototype p95 to size compute in the cost model.
2. **Adoption is not performance.** The only hard figure, about 45% vs 25% developer adoption [S1] (snippet, unverified), speaks to hiring pool and tooling. It says nothing about dashboard latency or cost per tenant.
3. **Check the sponsor before the headline.** Postgres vendors tend to show Postgres winning, and MongoDB shows the reverse. Check who ran the test, the data shape, and whether hardware and indexes were matched.
4. **Tenant-scoped dashboards need tests that published numbers rarely cover.** These include multi-tenant isolation and noisy neighbours, tenant-filtered aggregations, partitioning or sharding by tenant, and index size and compression at 200 GB per tenant. The prototype must cover these.
5. **Flexibility is converging.** The snippet [S10] says Postgres has closed the flexibility gap and MongoDB the transaction gap. Schema fit, operations and managed-service cost are therefore likely to matter more than raw speed. Treat that as unverified until the page is fetched.

## Next steps (not done)
- Fetch an independent benchmark, a Postgres-vendor benchmark and a MongoDB-vendor benchmark, each with a publication date.
- Search for a 2026 benchmark.
BLOCKED: fetch_url — only the Bytebase page was fetched; the tech-insider.org page, the third source and any vendor benchmark (EDB, MongoDB) were not fetched, so those rows rest on snippets or memory
MISSING DATA: Independent PostgreSQL vs MongoDB benchmark for multi-tenant analytics, JSONB vs documents or time-series, with a publication date — looked in one web_search plus one Bytebase fetch
MISSING DATA: Exact publication date of the tech-insider.org article — search snippet shows only the year in the title
MISSING DATA: Title and URL of the third snippet source — cut off in the truncated search output
MISSING DATA: Vendor-sponsored benchmark (EDB or MongoDB) with URL, date and figures — recalled from memory only, not retrieved
MISSING DATA: Newer 2026 benchmark search — not run because turns ran out
