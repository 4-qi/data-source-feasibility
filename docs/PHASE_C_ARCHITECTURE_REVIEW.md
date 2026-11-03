# Phase C internal architecture consistency review

Status: **internal review passed after owner fixes and real-PostgreSQL
regression**, November 3, 2026. This review is limited to synthetic engineering
behavior. The coordinating chat controls the Phase C gate; Phase D is not
authorized by this document. The approved design is not changed here.

## Review method and required evidence

Read actual implementation paths, trace committed database states with the
independent integration tests, and inspect the complete regression results.
Report a defect to its implementation owner rather than silently changing a
core rule. A finding can close only after the owner fixes it and regression
evidence is available. A checklist entry without code/test evidence is not a
passed review.

At review start, SHA-256 baselines were:

```text
5fc05c31ad38c551d567d2282dc9b49a2479bc22209f74cc85571c6ab0cc0cf7  docs/APPLE_INGESTION_SYSTEM_DESIGN.md
bc20a7f0056774c26af9ad70e6f992d92e31126476bd2ae1aab7c421661687e4  src/feasibility/apple_ingestion/models.py
3a8a8b14df715033d9679f372fe0a40699c05c2b97f6987937de8ed88df27455  migrations/versions/0001_apple_ingestion.py
```

| Design requirement | Implementation and regression evidence inspected |
| --- | --- |
| Seven-table ownership, full title/body and first-committed conflict handling | `models.py` and migration hashes below; `reconcile._write_page` stores full accepted record, compares later occurrences against the observed version; Phase B integration verifies stored original text and alternate-body exclusion. Controller conflict regression continues bounded collection and excludes reference eligibility. |
| Atomic pages and committed-marker replay | `reconcile.persist_page` owns page transaction including marker; controller reads the durable marker after acknowledgement loss. Reconciliation fault tests and independent `test_commit_acknowledgement_loss_reads_marker_without_replaying` inspect persisted counters/versions. Driver-commit tests separately cover C-10. |
| Reference eligibility independent of coverage and age | `reference.comparison_eligibility` checks committed evidence, not sufficient overlap; `select_reference` chooses latest earlier compatible usable row. Independent five-run chain in `test_insufficient_chain_age_boundary_and_committed_intent` verifies each latest insufficient predecessor. |
| Strictly above 72 hours warns, never excludes | `select_reference` compares age with `>`; independent chain tests exactly 72h and 72h+1s and preserves the predecessor ID. Owner `test_reference_age_is_strict_warning_not_cutoff` checks exact measured hours. |
| Initial baseline and compatibility restart | `select_reference` counts only same-mode usable history; `classify_coverage` handles baseline/no-reference independently. Owner tests cover other-mode history, incompatible parser history followed by new anchor reuse, empty history and future finish exclusion. |
| Low observable window reasons and stop AND conditions | `coverage_metrics` deduplicates committed IDs and calculates independent reason predicates; `CoverageMetrics.thresholds_met` requires all page/count/ratio predicates. Owner exact-boundary tests cover 12/12/12, 50/50/5, 10/50/1 and 20/100; independent stop test proves first-page count/ratio cannot bypass min pages. `_finalize` labels failure windows `measured_partial_only`. |
| Empty/duplicate-only coverage caution still permits usable references | `Controller._metrics` reads committed selected attempts; `classify_coverage` yields indeterminate for nonempty caution and empty_window for entirely empty normal runs. Independent parameterized test reuses successful duplicate-only and JSON-empty/XML-empty cautioned runs as next references. |
| Intent before HTTP and honest crash states | `run_target` commits intent before `transport.fetch`; independent fake HTTP callback reads it via a separate connection and checks lock-holder `pg_stat_activity.state='idle'`. Backend-termination test checks null HTTP status, unknown code and new run page 1. |
| Bounded fallback, budget, global spacing and time/body limits | `run_target` bounds page/physical-attempt loops and JSON-only empty fallback; `BoundedTransport.fetch` performs one fake-session call, global start spacing, stream cap and deadline checks. Independent tests cover incomplete fallback and source-wide batch 429; owner transport tests cover redirects, timeouts, cap, spacing across applications and disabled retries. |
| One application session lock on same reconciliation connection | `recovery.application_session` pins driver/backend and app lock; controller passes `session.connection` directly to `persist_page`. Independent actual contention produces no run/attempt/fetch. Existing schema permits one US/mostrecent target per app; app-keyed lock also covers future multiple-target configurations without changing schema. |
| Session loss aborts without silent continuation | `ApplicationSession.assert_alive` checks pinned driver, PID, lock and driver IDLE state; failed handle is discarded. Independent real backend termination verifies no accepted review, no further request on old run, retained spool and restart page 1. Owner checks termination after a committed page and no new pool checkout during repeated failed liveness checks. |
| Safe durable spool, idempotent import | `DiagnosticSpool._entry/_file/append` restrict fields, codes, path, ownership/mode and symlink handling, then fsync file+directory. `replay_spool` hashes complete events into JSON marker keys; owner append-after-replay tests verify new events import exactly once, with explicit capacity failure. Committed marker remains committed; no HTTP result is manufactured. |
| Terminal runs have no pending attempt or coverage | `Controller._finalize` resolves pending attempts then derives statuses; `recover_interrupted` finalizes orphan runs under app lock. Independent `assert_terminal_resolved` queries actual run/attempt rows after normal, denial, budget, acknowledgement and recovery cases. |
| No network escape or body/credential leakage | `tests/conftest.py` denies Python IPv4/IPv6 connects, preserving PostgreSQL Unix sockets; independent transport subclasses `requests.Session` and overrides request without network. `BoundedTransport._scrub_session` clears ambient credentials/cookies/retries; body is excluded from response repr. Independent assertions inspect run/attempt/spool diagnostics and safe RunResult repr; `create_db_engine` hides parameters and disables echo. |

## Findings and disposition

The following findings were recorded during review. C-04, C-05 and C-09 came
from this independent review/test session; the coordinating chat reported the
other findings. All were fixed by their implementation owners, not by silently
changing core rules in this validation session:

| ID | Finding | Required disposition |
| --- | --- | --- |
| C-01 | `select_reference` initially set usable history before comparing run modes, so history exclusively from another mode could cause a restart instead of the current mode's first baseline. | Count only usable same-mode history; regression distinguishes other-mode history from same-mode parser/hash incompatibility. |
| C-02 | `comparison_eligibility` initially permitted a terminal row whose coverage remained `pending`. | Treat pending coverage as unresolved internal state while retaining genuine nonpending coverage cautions as eligible. |
| C-03 | Snapshot validation initially compared internal app/target IDs without checking source app identity and actual target storefront/sort. | Validate stored snapshot against application/target rows; a forged snapshot must be excluded, without narrowing legitimate reference eligibility. |
| C-04 | Independent read found recovery's `ApplicationBusy.code` is `APPLICATION_BUSY`, absent from controller's lock-skip branch. | Owner must align the interfaces; actual lock contention must skip without run, attempt, request or spool failure. |
| C-05 | Independent read found controller outage stages such as `run_intent`, `response_metadata`, `page_commit`, `after_page_commit` and initial `lock` were absent from spool's allowed stage set. | Owner must ensure each real outage path can record its intended safe diagnostic or return an explicit pre-run error, without treating a valid failure stage as corrupt input. |
| C-06 | Coordinating chat found first-import `SPOOL_REPLAYED`/`SPOOL_RUN_REPLAYED` group markers caused later safe events for the same group to be ignored. | Recovery owner to use per-event fingerprint/watermark semantics within existing JSON diagnostics; test later append plus repeat replay without overwriting committed markers or fabricating HTTP state. |
| C-07 | Coordinating chat found controller rejected explicit nondefault min-page/count/ratio and budget settings despite the design's configurable frozen settings. | Owner to retain approved defaults and unchanged AND rule, allow explicit valid target/snapshot-matching settings, and explicitly reject unimplemented retry policy. No automatic threshold relaxation. |
| C-08 | Coordinating chat found a DB failure before run insertion left `run_id=None`, which spool rejected instead of recording the safe failure. | Preallocate an intended run UUID before lock/intent persistence, send no HTTP if persistence fails, and distinguish intended UUID from a persisted row. |
| C-09 | Independent backend-termination integration failed after recovery: a request whose response metadata was never committed ended with only `APPLICATION_SESSION_LOST`, not the required `REQUEST_OUTCOME_UNKNOWN`. Spool replay had resolved its pending states, so orphan recovery no longer recognized the unknown request. | Recovery owner must preserve unknown-request semantics while importing safe event diagnostics, leave HTTP status null, and retain idempotence. Regression: `test_session_loss_after_fetch_spools_unknown_then_restarts_page_one`. |
| C-10 | Coordinating chat identified a shared transaction-boundary root cause: SQLAlchemy commit failure can deactivate its logical transaction while psycopg remains INTRANS. Logical-only rollback followed by a new short transaction could then accidentally commit the old run/page. | Controller, reconciliation and recovery owners must discard/roll back the actual driver transaction before liveness checks, rollback diagnostics or pool reuse. Validate failures before sending COMMIT separately from a successful COMMIT whose acknowledgement is lost. |

These findings do not reopen approved reference or coverage semantics.
Controller/reference owner fixed C-01 through C-04, C-07 and C-08.
Transport/recovery owner fixed C-06 and C-09. C-05 combined recovery's stage
whitelist fix with controller's pre-lock intent-stage mapping. C-10 involved
both sessions and additionally required the coordinating chat's explicitly authorized
minimal reconciliation defense and its regression tests. This validation
session did not modify implementation files.

The first independent cross-layer run recorded six failures ending in
`DIAGNOSTIC_DURABILITY_FAILED` (`/tmp/phase-c-crosslayer-first.xml`). It was not
counted as acceptance. Postmortem observed the pre-run recovery stage and absent
persisted run ID behind the masked error; owners subsequently aligned the interfaces
and preallocated the intended UUID. The empty-spool startup sequence then
passed independently. After these owner changes, the full independent module
measured **9 passed, 1 failed** in 3.94 seconds
(`/tmp/phase-c-crosslayer-after-fixes.xml`), exposing C-09 rather than suppressing
it. No same-error full-suite retry was used to conceal these findings.

After the unknown-request fix, the original ten cross-layer cases plus two
pre-run-failure cases passed: **12 passed in 4.15 seconds**
(`/tmp/phase-c-crosslayer-final.xml`). One test assumption was corrected during
this work: the design does not prescribe exactly one spool event per failure.
The assertion now checks the correct run/attempt group and outage code; the
required unknown-outcome/null-HTTP/no-continuation assertions were retained.
Two driver-level commit-failure cases were then added for C-10.

## Finding closure and final evidence

| Finding | Owner fix and regression evidence | Final disposition |
| --- | --- | --- |
| C-01 | `reference.select_reference` counts usable history only after same-mode comparison; `test_only_other_run_mode_history_does_not_create_restart` and `test_same_mode_incompatible_parser_history_restarts_then_new_anchor_is_usable`. | Closed. |
| C-02 | `comparison_eligibility` rejects successful rows with pending coverage; `test_defective_candidates_do_not_become_reference[pending_coverage]`. Nonpending indeterminate cautions remain usable in independent coverage-caution integration. | Closed. |
| C-03 | Eligibility queries actual application/target identity; defective snapshot identity falls back to the valid earlier candidate. Controller validates target identity/settings before recovery and inserts. | Closed. |
| C-04 | Controller recognizes `APPLICATION_BUSY`; independent actual session contention creates no run/attempt/request. | Closed. |
| C-05 | Recovery stage whitelist includes actual controller stages; pre-lock stage is safely mapped to intent. Independent pre-run, backend-loss and commit-failure cases successfully preserve diagnostics. | Closed. |
| C-06 | `replay_spool` tracks full-event SHA-256 keys in existing JSON markers. Owner append-after-import and capacity tests verify new-event import, repeat idempotence and explicit overflow failure. | Closed. |
| C-07 | `_validate` preserves contract defaults, validates explicit snapshots and rejects only the unsupported retry policy; `_validate_target` checks stored target settings. Owner `test_explicit_configuration_is_frozen_and_used_without_replacing_defaults` verifies custom settings and unchanged defaults/AND semantics. | Closed. |
| C-08 | Intended UUID is allocated before acquisition. `run_persisted` distinguishes confirmed persistence from absent/unknown persistence; actual row queries remain authoritative. Independent lock/insert failures send no HTTP and preserve a safe intended UUID; owner commit-failure test verifies no invented row. | Closed. |
| C-09 | `_resolve_attempt` derives uncertainty from the original durable row before resolving it, retains outage code, adds unknown-outcome code only where applicable, and preserves known HTTP metadata. Independent real backend kill/restart plus owner known/unknown-metadata regression pass. | Closed. |
| C-10 | Reconciler clears actual INTRANS/INERROR driver state before marker/diagnostic reads, invalidates if cleanup/diagnostic commit cannot safely finish, and preserves IDLE committed-marker state. Controller discards uncertain run-intent connection; recovery rejects nonidle liveness checks and rolls back driver state before cleanup. Independent direct psycopg commit-before-send failures at run intent/second page prove no leaked run/page; acknowledgement-loss tests prove committed pages are not undone or replayed. | Closed as one shared transaction-boundary root cause. |

This session's final command was:

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q --tb=short --junitxml=/tmp/data-source-feasibility-phase-c-validation.xml
```

Result: **444 passed in 22.55 seconds**, **0 failed, 0 skipped, 0 warnings**.
JUnit confirms 444 tests, zero errors/failures/skips. This includes all prior
regressions, 14 independent Phase C cross-layer cases, controller 28, reference
17, transport 24, recovery 23 and reconciliation 23 cases. The latter counts
are module totals, not additive to 444. The temporary cluster was cleaned up.

The three baseline hashes were recomputed after implementation and matched
exactly. `git diff --check` passed. No seventh-table replacement, eighth table,
version truncation, reference-age cutoff, automatic threshold relaxation or
changed first-committed snapshot policy was introduced. No unresolved review
finding remains in this measured suite.

The coordinating chat then reported its separate final run: **444 passed in
21.93 seconds**, zero failures, skips or warnings, with JUnit
`/tmp/apple-phase-c-main.xml` and matching design/model/migration hashes. That
is a coordinating-chat report; this review's own measured run remains the
22.55-second result above. Both prerequisites are now evidenced for the
coordinating chat's stage-gate decision; this session does not start D itself.

This sign-off establishes synthetic Phase C architecture consistency only.
The Python socket guard is not an OS firewall; tests inject a fake HTTP session
and exercise no real endpoint. Host deployment, live access/retention, empirical
source behavior, Phase D reporting and human assessment remain outside this
review. Total DB plus spool storage failure is explicitly nondurable and stops
the operation; no unconditional durability is claimed.
