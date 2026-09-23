# Box 2 on a complex task — gemini-3.1-flash-lite (2026-09-23)

    python -m scripts.eval_draft --tasks tasks/draft_eval_complex.jsonl --repeats 3 --llm openai

The task: a 12-person startup must choose PostgreSQL or MongoDB. It needs current benchmarks and managed-service
pricing on AWS and GCP, a cost estimate (50 tenants × 200 GB, 5,000 queries/min peak), a GDPR data-residency
assessment, a prototyped and tested schema in both databases, and a recommendation memo with a risk table and a
90-day migration plan.

| | attempt 0 | attempt 1 | attempt 2 |
|---|---|---|---|
| accepted | yes | yes | yes |
| rounds / consensus | 3 / no | 3 / no | 3 / no |
| roles (tools) | Cloud Architect & Cost Analyst (calc), Compliance & Data Privacy Officer (echo), Database Schema Engineer (echo), Technical Writer & Strategist (echo) | Database Architect (echo), Cloud Economist (calc), Compliance Officer (echo), Language Expert (echo) | Cloud Architect & Cost Analyst (calc), Data Compliance & Legal Specialist (echo), Database Schema Engineer (echo), Language Expert (echo) |
| plan steps written / kept | 5 / 4 (`[All Roles]` dropped) | 5 / 5 | 4 / 4 |
| capability requests | none | none | none |
| tokens / calls | 17,798 / 9 | 18,096 / 9 | 18,999 / 9 |

Mean: 18,298 tokens and 9 calls per draft, about 2.6× a simple task. All three drafts use the full 3 rounds.

## How Box 2 responded
1. **The team is sensible.** Four specialists (cost, compliance, schema, writer) and a plan that ends with a synthesis
   step. The structure was stable across attempts and never hit the 5-role cap.
2. **No capability requests, even though the task needs them.** The work needs web search (benchmarks, pricing) and
   code execution (prototype and test a schema). In all 9 Planner replies the Capability Requests section is "None",
   and roles that must search or run code are given **`echo`** as a stand-in tool. The simple need-a-tool tasks
   (fx-rate, papers-rag) did request web_search, so on a long, busy prompt D19 loses to "prefer existing tools".
3. **The observers never question the tools.** No observer says that echo cannot gather pricing or run a schema. They
   critique scope and hand-offs only. The Agent Observer said "No Suggestions" in 5 of 9 rounds.
4. **The Plan Observer never converges.** Every round it adds new refinements (an integration step, a decision
   matrix, operational overhead, go/no-go thresholds), so drafting always stops at the round cap. The last draft is
   used, and the round-3 suggestions are never applied.
5. **A plan step can vanish silently.** Attempt 0's `4. [All Roles]: Review findings…` names no role, so plain code
   dropped it (D6). The team loses its review step with no event in the trace.
6. The copied role regex caused no rejections here: no role prompt contained `{…}`.
