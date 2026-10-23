I read "multi-tenant" as Shared database with a tenant ID column or tenant field; if you meant Separate schema or database per tenant, the answer below may not apply.

# GDPR legal framework for EU tenant data (step 9)

**Not legal advice.** This memo is an engineering and delivery summary for planning only. It is not legal advice. EU counsel and our DPO must confirm every point before we sign contracts or host EU tenant data.

**Source status (read first).** Only one official source was confirmed with a live fetch.
- Confirmed: European Commission, "Standard Contractual Clauses (SCC)", https://commission.europa.eu/law/law-topic/data-protection/international-dimension-data-protection/standard-contractual-clauses-scc_en, accessed 22 Oct 2026 [S87]. This is the run date given in the task.
- Failed: the EUR-Lex fetch of Regulation (EU) 2016/679, https://eur-lex.europa.eu/eli/reg/2016/679/oj, returned a fetch error on the same access date. The GDPR article text below is therefore not verified against the primary text.
- Not fetched: EDPB pages and provider DPA pages (the step ran out of turns).
- Everything tagged [unverified] comes from my own knowledge. Treat it as a pointer for counsel to check, not as a cited fact.

## 1. Chapter V: transfers outside the EU/EEA
- GDPR Chapter V (Articles 44–50 [unverified]) restricts transfers of personal data to third countries unless a transfer tool applies [unverified]. The official text is at https://eur-lex.europa.eu/eli/reg/2016/679/oj and was not retrieved.
- The tools, in order of preference [unverified]:
  1. An adequacy decision (Art. 45 [unverified]).
  2. Appropriate safeguards (Art. 46), mainly Standard Contractual Clauses (SCCs) or Binding Corporate Rules.
  3. Derogations (Art. 49 [unverified]), which are narrow and not for routine use.
- Why it matters for us: a US-headquartered provider's remote support or admin access to EU-hosted data can count as a transfer [unverified]. Hosting in an EU region alone does not remove the Chapter V analysis.

## 2. Standard Contractual Clauses (SCCs)
- The European Commission SCC page (accessed 22 Oct 2026 [S87]) says there are two sets of SCCs [S87]. It also points to documents, including questions and answers on their use, and to best practices companies can use to operationalise the safeguards required under the clauses [S87].
- The page excerpt I could read does not name the two sets. From my own knowledge they are:
  - SCCs for controller-to-processor relationships inside the EU/EEA (Art. 28 [unverified]).
  - SCCs for transfers to third countries (Art. 46).
  - Commission Implementing Decision (EU) 2021/914 of 4 June 2021 is the transfer-SCC decision [unverified].
- For the transfer SCCs, we need to pick the right module and sign them with each provider that is a non-EU recipient [unverified]. Counsel should confirm this against the provider DPAs.

## 3. EU-US Data Privacy Framework (DPF)
- From my own knowledge, the Commission adopted an adequacy decision for the EU-US DPF on 10 July 2023 [unverified]. It covers transfers only to US organisations that are DPF-certified [unverified]. I also recall a General Court ruling in 2025 (Latombe) that upheld the decision, with an appeal possible [unverified].
- **I could not confirm the DPF's current status "as of" today (22 Oct 2026, the run date).** No newer official statement was searched. Counsel must check the Commission DPF page, the DPF list at dataprivacyframework.gov and any court developments.
- Planning stance: do not rely on the DPF alone. Keep SCCs and a transfer impact assessment (TIA) as a fallback in each provider contract [unverified]. This is a design recommendation, not a legal conclusion.

## 4. Transfer impact assessments (TIAs)
- Under the Schrems II ruling (CJEU, 16 July 2020 [unverified]), exporters relying on SCCs must assess whether the third country's law undermines the clauses, and add supplementary measures where needed [unverified].
- The Commission page refers to best practices for operationalising SCC safeguards [S87]. I did not fetch the EDPB recommendations on supplementary measures. The counsel checklist lists them as "to be retrieved".
- Practical TIA inputs for our shared-database design:
  - Which provider personnel can access EU tenant data, and from where.
  - Whether data is encrypted with customer-managed keys.
  - Where backups, logs and support tickets are stored.

## 5. DPAs and sub-processors
- Under Art. 28 [unverified], a controller must have a written contract (DPA) with each processor [unverified]. It must cover:
  - Processing only on documented instructions.
  - Confidentiality.
  - Security under Art. 32 [unverified].
  - Sub-processor flow-down and authorisation.
  - Assistance with data-subject requests (DSRs) and breaches.
  - Deletion or return of data at the end of the contract.
  - Audit rights.
- Our role (for counsel to confirm): we are likely a processor for our tenants' end-user data, and our tenants are controllers. The cloud and database providers are then our sub-processors. We need a DPA with each tenant and a DPA with each provider, plus a sub-processor list we can share with tenants [unverified].
- Provider DPA and sub-processor pages were not fetched. Steps 10 and 11 should read them directly.

## 6. Erasure and data-subject requests (DSRs)
- Art. 17 [unverified] gives a right to erasure. Arts. 15–22 [unverified] cover access, rectification, restriction, portability and objection. The usual response deadline is one month (Art. 12(3) [unverified]).
- Engineering implications for a shared database with a tenant ID:
  - Every event and dashboard row needs a stable data-subject key (pseudonymous ID) in addition to the tenant ID.
  - Deletion must reach primary data, replicas, derived tables and aggregates.
  - Backups need a documented expiry window instead of immediate rewrite.
  - Deletion proof needs to be logged.
  - A tenant offboarding job must delete all rows for a tenant ID.
- Per-engine erasure mechanics are covered in step 10 (PostgreSQL) and step 11 (MongoDB Atlas).

## 7. What this step could not confirm
1. The GDPR article text from EUR-Lex (fetch failed).
2. The two SCC sets by name, their adoption dates and the DPF status as of the run date. The Commission page was fetched but its relevant lines were truncated in my view.
3. EDPB guidance and provider DPA and sub-processor pages (not fetched).

## 8. Source list
- [S87] European Commission, Standard Contractual Clauses (SCC). URL as above. Accessed 22 Oct 2026 [S87].
- EUR-Lex GDPR (https://eur-lex.europa.eu/eli/reg/2016/679/oj): fetch failed, so not cited as a source.
BLOCKED: fetch_url (EUR-Lex) — could not retrieve the GDPR primary text from https://eur-lex.europa.eu/eli/reg/2016/679/oj (Failed to fetch url)
MISSING DATA: Current EU-US DPF status as of 22 Oct 2026 — only the Commission SCC page was fetched; no DPF page or court update was checked
MISSING DATA: EDPB guidance on supplementary measures and TIAs — not fetched (out of turns)
MISSING DATA: Provider DPA and sub-processor pages (AWS, GCP, MongoDB) — not fetched in this step
MISSING DATA: Names and adoption dates of the two SCC sets — the fetched Commission page text was truncated in my view
