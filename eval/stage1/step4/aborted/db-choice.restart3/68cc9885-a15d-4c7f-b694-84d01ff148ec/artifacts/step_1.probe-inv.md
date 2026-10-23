EDB whitepaper capture (vendor-funded: EDB). Retrieval date 22 Oct 2026. Partial: the headline design is captured, but the numeric result tables and the publication date are not.

**Source**
- Whitepaper PDF: "PERFORMANCE BENCHMARK POSTGRESQL / MONGODB", hosted by EDB at https://info.enterprisedb.com/rs/069-ALB-339/images/PostgreSQL_MongoD… [S2][S33]. The URL is cut off in my notes. The full URL is in sources/index.json [S31].
- EDB landing page: https://www.enterprisedb.com/performance-benchmark-postgresql-vs-mon… [S23][S32]. This URL is also cut off. The full URL is in sources/index.json [S31].
- Related EDB comparison page: "Comparison of MongoDB vs PostgreSQL – EDB" [S24]. I did not capture its content in this step.
- Related news item: "EDB Says It Tops Oracle, Other Databases…" [S25]. I did not capture its content in this step.
- The PDF's author line includes @ongres.com addresses [S34]. OnGres appears to be the engineering contractor, but I did not capture the funding statement.

**Date**
- Publication date: not found in the text I reviewed.
- The tested versions (PostgreSQL 11, MongoDB 4.0) [S35] suggest an older study. That is my inference, not a stated date. Both versions are long superseded as of 22 Oct 2026.
- I did not find a newer EDB benchmark in this step. I did not read S24 or S25 closely enough to say whether they hold newer figures.

**Funder**
- Vendor-funded (EDB). The PDF is hosted on EDB's domain [S2].
- An independent re-run has not been confirmed.

**Versions**
- PostgreSQL 11 against MongoDB 4.0. The paper compares PostgreSQL with "MongoDB Community Server", not Atlas [S35].
- This is not the managed MongoDB Atlas service we are evaluating. It is also not RDS, Aurora, Cloud SQL or AlloyDB.

**Hardware**
- The JSON-based OLAP benchmark used an AWS m5.4xlarge instance with 16 CPU and 62 GB RAM. The OLAP section says its instance sizes and characteristics are the same as the OLTP benchmark [S35].
- Storage type, IOPS and the number of nodes were not captured.

**Workload**
Three benchmarks [S35]:
1. A transaction benchmark. It is custom-developed, inspired by the MongoDB Pymongo-Transactions project, and models an airline reservation system.
2. Sysbench OLTP, run on both in-memory and 2 TB datasets.
3. A JSON-based OLAP benchmark. It runs four custom-written queries over 1 year of GitHub Archive data, using jsonb in PostgreSQL.
- The authors say they automated the infrastructure and published all the software as open source, so third parties can reproduce the results [S35].

**Numeric results captured (qualitative statements only)**
- "PostgreSQL 11 was found to be faster than MongoDB 4.0 in almost every benchmark." Throughput was higher "ranging from dozens of percent points up to one and even two orders of magnitude" [S35]. The sentence is cut off in my notes.
- When the dataset fits in RAM, the paper says to consider MongoDB for faster performance. When the dataset is bigger than RAM, PostgreSQL's advantage grows as the dataset grows [S34].
- The paper describes a typical BI application as including lookup tables. This is the setup for its OLAP section [S34].

**Not captured (gaps)**
- Per-benchmark numeric tables: transactions per second, latency, OLAP query times for each of the four queries, and Sysbench in-memory versus 2 TB results. They are in the saved PDF text (about 63,384 characters) [S2], but my reads of it were truncated.
- The exact publication date.
- The full, untruncated URLs for the PDF and landing page. Look them up in sources/index.json [S31].
- Storage, IOPS, node count and configuration tuning details.
- Whether MongoDB ran with transactions, journaling or write-concern settings that favour either side.
- Whether S24 and S25 contain a newer EDB benchmark.

**Relevance**
- Only the JSON OLAP test touches dashboard analytics. It covers 1 year of GitHub events with four queries, so it is a rough proxy for an event-and-dashboard schema.
- It is single-instance, not multi-tenant, and not run on managed services.
- Treat the results as directional evidence only. Do not use them as cost or capacity figures.
MISSING DATA: Numeric result tables (TPS, latency, OLAP query times, Sysbench) — in the saved PDF text S2, but my reads were truncated
MISSING DATA: Publication date of the EDB whitepaper — not stated in the text I reviewed
MISSING DATA: Full untruncated PDF and landing-page URLs — recorded in sources/index.json [S31], not captured in my notes
MISSING DATA: Storage type, IOPS and node count for the benchmark hardware — not captured
MISSING DATA: Whether a newer EDB benchmark exists — S24 and S25 not fully read
