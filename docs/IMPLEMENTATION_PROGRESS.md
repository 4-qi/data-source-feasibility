# Apple ingestion implementation progress

The approved baseline is [APPLE_INGESTION_SYSTEM_DESIGN.md](APPLE_INGESTION_SYSTEM_DESIGN.md).
The main coordinating chat owns phase gates, integration and final acceptance;
execution uses the three independent chats listed in [Phase A delivery](PHASE_A_DELIVERY.md).

| Phase | Status | Gate |
| --- | --- | --- |
| A — Contracts/database | Accepted | 228 tests passed with disposable PostgreSQL; see Phase A record. |
| B — Parser/normalizer/reconciler | Accepted | Main chat: 336 passed, zero failures/skips; JUnit `/tmp/apple-phase-b-main.xml`. |
| C — Controller/attempts/recovery | Accepted | Main chat: 444 passed, no failures/skips; C-01 through C-10 closed in internal review; `/tmp/apple-phase-c-main.xml`. |
| D — Reports/synthetic seven days/human tools | Accepted; external document-level review passed | Main chat: 516 passed, zero failures/skips; 56-slot rehearsal and 15 payload checksums verified. |
| E — Live readiness | Preparation/offline engineering complete; actual first run blocked | Main chat: 630 passed, zero failures/errors/skips; see [readiness report](PHASE_E_LIVE_READINESS.md). |
| Local persistent deployment (after E) | Deployed and verified; live remains blocked | Main chat: 640 passed; actual PG16 restart, private backup/isolated restore, eight disabled targets and unconfirmed long-term arrangements. See [deployment report](APPLE_INGESTION_LOCAL_DEPLOYMENT.md). |
| First smoke preparation / project policy | Complete; actual execution remains blocked | Main chat: 668 passed, zero failures/errors/skips; reusable project scope, exact procedure verified offline, all actual targets disabled. [Procedure and checklist](APPLE_FIRST_LIVE_SMOKE_TEST.md). |
| Pre-Live Engineering Baseline | Committed locally as `cadc16c`; no push | Clean-export regression: 668 passed; no secrets/runtime data included. See [commit review](PRE_LIVE_ENGINEERING_BASELINE.md). |
| Operational-policy correction | Accepted for local follow-up commit; default execution disabled | Main chat: 668 passed, zero failures/errors/skips. Actual DB operational-ready; no administrative runtime gates; two project configs off and eight targets disabled. See [updated smoke procedure](APPLE_FIRST_LIVE_SMOKE_TEST.md). |
| F — Seven-day live pilot | Not authorized | Do not execute or schedule. |

Engineering tests use synthetic data and disposable PostgreSQL in the shared
`data-source-feasibility` Conda environment. Seven core tables, complete observed
versions, reconciliation rules, comparison-reference rules and stopping predicates
remain fixed. The prior local milestone commit is complete. No Apple RSS requests or
pushes are authorized. The accepted correction now has authorization for one
separate local follow-up commit; actual smoke execution remains a later explicit
operator action. The separately authorized
dedicated local WSL database is deployed; live collection remains closed.
Phase E may prepare a controlled live-capable path and deployment templates using offline tests.
Historical feasibility evidence and existing tests are preserved.

A–D delivery: [implementation summary](APPLE_INGESTION_IMPLEMENTATION_SUMMARY.md).
Phase E delivery: [offline live readiness](PHASE_E_LIVE_READINESS.md).
Current local operations: [persistent deployment and first-run blockers](APPLE_INGESTION_LOCAL_DEPLOYMENT.md).
A–D external document-level engineering review passed. Phase E is complete at its preparation boundary; F remains closed.
