I read "multi-tenant" as Shared database with a tenant ID column or tenant field; if you meant Separate schema or database per tenant, the answer below may not apply.


EDB WHITEPAPER (retrieved today, the run date given in the task)
- Source URL: https://info.enterprisedb.com/rs/069-ALB-339/images/PostgreSQL_MongoDB_Benchmark-WhitepaperFinal.pdf [S2]
- Title: "PERFORMANCE BENCHMARK POSTGRESQL / MONGODB" [S2]
- Funder: EDB (EnterpriseDB), which sells PostgreSQL products. The PDF is hosted on EDB's own domain, so label it VENDOR-FUNDED (EDB), not independent. [S2]
- Publication date: NOT FOUND in the text I read (see gaps). The versions tested are PostgreSQL 11 and MongoDB 4.0, which suggests roughly 2019. That is an inference and not a printed date. It is older than today, so it is not a current benchmark. I did not find a newer EDB edition of this whitepaper in this step.
- Versions: PostgreSQL 11 vs MongoDB 4.0 [S39]. MongoDB 4.0 added multi-document transactions and new aggregation capabilities [S38]. Exact minor versions and the MongoDB edition (Community or Enterprise): not captured.
- Hardware: NOT CAPTURED. I saw no instance type, vCPU, RAM or storage description (see gaps).
- Workloads, three benchmarks [S39]:
  1. A transactions benchmark that models an airline reservation system.
  2. Sysbench OLTP, covering both in-memory and 2 TB datasets.
  3. A JSON-based OLAP benchmark. It runs four custom-written queries over 1 year of GitHub archive data, using jsonb in PostgreSQL.
- Headline result (EDB's own words): "PostgreSQL 11 was found to be faster than MongoDB 4.0 in almost every benchmark." Throughput was higher by "dozens of percent points up to one and even two orders of magnitude on some benchmarks". Latency, where measured, was also lower on PostgreSQL. [S39]
- Transactions benchmark numbers [S38]:
  - MongoDB without transactions behaves like READ UNCOMMITTED isolation. With transactions it offers SERIALIZABLE.
  - PostgreSQL was tested at both READ COMMITTED and SERIALIZABLE.
  - At the same isolation level, MongoDB was "one order of magnitude (4x-15x) slower" than PostgreSQL on READ COMMITTED. It was 4-14x slower than PostgreSQL on SERIALIZABLE.
  - Latency: "[median] latency is 5-20 times higher than that of PostgreSQL; and 99 percentile is 7-17 times worse." MongoDB's minimum median latency is 5 ms in the best case, without concurrency. It "spikes to hundreds of milliseconds on several scenarios." [S39]
- "17 times" context: the "7-17 times" figure is the 99th-percentile latency ratio, MongoDB versus PostgreSQL [S39]. It sits in the transactions (airline reservation) results, so it is an OLTP-style transactional workload. It is not a dashboard or analytics workload. "17" is the top of a range and not a single result. I place it in the transactions section from the text order only.
- Relevance to our decision: LOW to MODERATE. Only the JSON OLAP test resembles dashboard analytics. It is small, with four queries on 1 year of GitHub data [S39]. It was run on old versions and is vendor-funded. It does not test tenant-ID filtering or a shared multi-tenant layout. It says nothing about managed services (Atlas, RDS, Aurora, Cloud SQL, AlloyDB).

GAPS (not found or not captured)
- Publication date: no printed date seen. My keyword search for years and "Copyright" gave no usable result in the output I read. Other workspace sources S24 (an EDB MongoDB-vs-PostgreSQL comparison page) and S25 (a news story on EDB) exist, but I did not read them, so I cannot date the whitepaper from them.
- Exact versions: minor versions, MongoDB edition and configuration/tuning settings.
- Hardware: instance type, CPU, RAM, disk and cloud provider/region. None captured.
- Numeric result tables: only the summary ranges above were captured. The per-scenario throughput and latency tables for the transactions, Sysbench OLTP (in-memory and 2 TB) and JSON OLAP tests were not read. The Sysbench and OLAP numeric speedups are NOT CAPTURED.
- Third benchmark (JSON OLAP on GitHub archive data): its four queries' timings and the size of the PostgreSQL advantage were not captured. Only the claim that PostgreSQL was faster "in almost every benchmark" is recorded.
- Landing page: no EDB landing page was fetched or read, so the gating and publication context is unknown.
- Independence: no independent replication of these results was checked in this step. Treat all EDB figures as vendor claims.
MISSING DATA: Publication date of EDB whitepaper — searched the S2 text for years and Copyright; none found; landing page not fetched
MISSING DATA: Hardware/instance specs and exact versions — not seen in the portions of S2 I read
MISSING DATA: Per-scenario numeric result tables (transactions, Sysbench OLTP, JSON OLAP) — only summary ranges captured
MISSING DATA: JSON OLAP (third benchmark) numeric results — not captured
MISSING DATA: EDB landing page — not fetched
