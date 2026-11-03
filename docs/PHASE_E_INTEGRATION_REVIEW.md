# Phase E — Independent cross-module integration review

> Current operational-boundary correction: access/data-use and retention
> considerations remain project documentation for review with John, not
> collector confirmation gates. The historical tests/approval checks below
> describe the earlier E implementation. Use the
> [current smoke procedure](APPLE_FIRST_LIVE_SMOKE_TEST.md) for technical-only
> configuration, default disablement and explicit operator start.

Review date: November 3, 2026 (America/Los_Angeles).

**Result: PASS for the five independent offline integration scenarios below.** This is the independent cross-module portion of E; the coordinating chat owns the complete-suite E gate and final readiness decision. No actual Apple request, persistent deployment, production authorization or Phase F execution was performed.

Reviewed entry path: `live.prepare_live_controller` → fresh `deployment.preflight` with an audit connection and an actual runtime login → `Controller.run_target` → lazy real `requests.Session` with an in-process `BaseAdapter` → `BoundedTransport` → parser/normalizer → page reconciliation → PostgreSQL run/attempt/observation/version state. The collector receives only the runtime engine; the maintenance/audit engine is not used for collector writes.

The review added only [`tests/test_apple_ingestion_phase_e_integration.py`](../tests/test_apple_ingestion_phase_e_integration.py) and this document. Issues found in owned implementation files were reported to the coordinator and repaired by their owners. This review did not change core schema, reconciliation, reference selection, stopping predicates, parser/hash policy or historical evidence.

## 1. Evidence environment and limits

- Python: the shared `data-source-feasibility` Conda environment, invoked with `PYTHONNOUSERSITE=1`.
- PostgreSQL: isolated temporary local cluster, TCP disabled, private Unix socket. Each case uses a private migrated database and uniquely named actual LOGIN roles: maintenance owner, runtime and read-only report. Runtime/report have no administrative attributes or role memberships.
- This integration fixture receives the shared fixture's already migrated empty database, transfers its objects/schema/database to the nonadmin maintenance owner, and then calls the real maintenance initialization/seed/grant APIs. It exercises the existing migration-head path and actual maintenance transaction, not an independent proof of first-time migration DDL under that owner; the deployment owner's tests cover fresh migration/rollback separately.
- HTTP: actual `requests.Session`, `PreparedRequest` and `Response` handling, with every response supplied by an in-process `BaseAdapter`. Python TCP connects are blocked by the shared test guard. No DNS lookup, external socket, TLS negotiation, Apple availability, upstream header behavior or current feed representation was tested.
- The adapter checks safe request options, no authorization/cookie headers, fixed host/path, project User-Agent, 10/25-second timeout tuple, no redirects/retries and two-second global start spacing. It observes the actual advisory-lock holder through the isolated admin test connection: the collecting backend is the runtime login and is idle with no open transaction during HTTP.
- Review content, approval/access/retention references, named people and policy durations in these tests are explicitly **synthetic fixtures**. `RunMode.LIVE` names the exercised code branch; it does not turn invented responses or test declarations into actual live source evidence or a genuine approval.
- The receipt and diagnostic locations are private temporary paths. Databases, test roles, engines and the PostgreSQL cluster are cleaned up after the run.

## 2. Five accepted cross-module scenarios

| Test | Cross-module assertion | Actual result |
| --- | --- | --- |
| `test_e_default_pending_decisions_and_disabled_target_block_before_http_resources` | No policy, pending approval, missing access reference, pending deployment retention, expired approval and disabled target all fail before a Session, request, receipt claim or run/attempt/version write | Passed; no HTTP resources or database evidence created |
| `test_e_nonadmin_runtime_real_requests_adapter_full_pipeline_and_receipt_reuse` | Fresh deployment audit identifies the real runtime login but grants no authorization. Live batch is refused before lazy activation. The approved fixture's one-target call then takes JSON-empty → Atom fallback plus four JSON pages through the ordinary Controller/persistence path | Passed; 1 run, 6 physical attempts, 5 committed logical pages, 9 complete accepted versions; one fallback remains not-applicable, all attempts finish with HTTP 200, full title/body tails and bytes32 hashes retained |
| Same full-pipeline test | Collector really uses the non-superuser runtime login, no transaction spans adapter send, and narrow runtime privileges remain intact. One receipt is 0600; a separate policy instance reusing it cannot create another Session/run/attempt. Routine result/run/attempt diagnostics contain no private title/body | Passed; starts at injected seconds 0, 2, 4, 6, 8, 10; runtime still cannot update/delete versions or enable targets; Session/adapter closed |
| `test_e_approval_deadline_during_real_response_stream_stops_without_fallback` | Authorization deadline expires after the request starts and before its body is accepted. The transport/controller must finish safe metadata, create no review version and issue no XML fallback or extra request | Passed; one attempted request, failed terminal run, `TARGET_DEADLINE`, not-applicable persistence, receipt retained |
| `test_e_prepared_snapshot_batch_cannot_be_swapped_before_execution` | Replacing the preflighted snapshot revision/batch before first claim must fail against the prepared binding, even when the application is otherwise within the approval's broad scope | Passed; `LIVE_APPROVAL_SCOPE_MISMATCH`, no Session/receipt/run/attempt |
| `test_e_same_cluster_wrong_database_cannot_satisfy_runtime_readiness` | A second database is correctly migrated/seeded/granted with the same role names and table contract. Its runtime connection still cannot validate the first database's audit. The live factory must reject the actual endpoint/database mismatch before activation | Passed; deployment reports runtime unverified/not live-ready (`ACTUAL_RUNTIME_LOGIN_REQUIRED`); factory returns `LIVE_DEPLOYMENT_DATABASE_MISMATCH`; neither database receives a run |

The table includes sub-assertions of the full-pipeline test; there are **five test functions**, not seven independent execution runs. The small new integration set deliberately does not repeat the owner's per-column permission matrix, every approval-field mutation, denial status matrix, XML safety matrix or all C-stage crash injection tests. Those remain part of their existing focused suites and the main E gate.

## 3. Interface findings and closure

| Finding | Why it mattered | Disposition in reviewed integration |
| --- | --- | --- |
| E-I01 — Deployment readiness must reach the live factory | A standalone readiness report can be blocked while an unrelated approved-looking policy object exists; a Boolean declaration alone must not substitute for actual role/retention/diagnostic checks | Closed by owner integration of fresh deployment config/audit/runtime preflight before activation; pending retention and disabled target scenarios pass |
| E-I02 — Prepared snapshot/batch binding must be enforced before claim | Saving `_prepared_binding` without comparing it at execution would allow the preflighted object to differ from the executed object | Reported during static review; owner added prepared-binding comparison; independent swap test passes with zero side effects |
| E-I03 — Same role/table names are insufficient database identity | A runtime login from another database on the same cluster can have the same role, UTC and table names | Coordinator/deployment owner addressed connected database/endpoint binding; live factory also compares actual libpq endpoint/database identity. The independent fully provisioned second-database test passes |
| E-I04 — Diagnostic-path interface must agree across modules | The live factory binds the configured diagnostic path to the supplied spool; an unavailable/mismatched accessor can make a valid deployment fail preflight | Owner/coordinator aligned the path contract; actual nonadmin readiness and full pipeline pass. This review did not bypass diagnostics validation |

No finding required a new table/service, a new acquisition loop, broad runtime privileges, a changed reference policy or a changed stopping rule. The live entry delegates acquisition, fallback, parsing, reconciliation and finalization to the existing components.

## 4. Validation record

```bash
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite tests/test_apple_ingestion_phase_e_integration.py -q --tb=short
```

Result: **5 passed, 0 failed, 0 skipped in 3.08 seconds**. Private cluster cleanup completed. `git diff --check` passed. Execution was against the current shared uncommitted checkout on `main`, whose Git HEAD remained `474736abcee2a67f186299f09d196125400eb1ab`; this is not a committed release or a production-deployed binary.

The first fixture run exposed an integration-test setup error: PostgreSQL identity sequences follow table ownership and cannot be independently reassigned. The fixture was corrected to transfer tables, which transfers those sequences too, and to avoid masking setup errors during cleanup. A later test expectation was aligned with the deployment API's generic `ACTUAL_RUNTIME_LOGIN_REQUIRED` blocker; the security assertions remained not-live-ready/runtime-unverified/no resources/no writes. Neither correction weakened an implementation guard or changed production code.

## 5. Remaining readiness boundary

This passing review proves the tested offline integration and fail-closed boundaries, not external operation. Actual access applicability/retention approval, operational authority for a first limited request, chosen host provisioning, backup/export expiry operations and current raw-feed structural validation remain separate prerequisites. Test fixtures with an approved status prove policy mechanics, not approver identity or an applicable legal basis.

The [feed compatibility inventory](PHASE_E_FEED_COMPATIBILITY.md) remains authoritative for the evidence limitation: historical artifacts contain sanitized projections, not raw JSON/Atom; nested XML/XHTML absence is unproven. Unsupported legitimate nested content encountered in a later separately authorized bounded read must produce `COMPATIBILITY_BLOCKED` and correct full-content support before continued use, not record skipping or permanent unsupported-source acceptance.

No TLS handshake, Windows-native execution, persistent deployment, actual review arrival/edit behavior, independent human assessment or seven-day pilot is claimed. Main-session full-suite E acceptance is a separate gate. Phase F and any real RSS request remain unauthorized by this work.
