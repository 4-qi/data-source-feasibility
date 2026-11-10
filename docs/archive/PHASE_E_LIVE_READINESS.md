# Phase E — Live readiness

> Current operational-boundary correction: access/data-use and retention
> considerations remain project documentation for project-level review, not
> collector confirmation gates. The historical tests/approval checks below
> describe the earlier E implementation. Use the
> [current smoke procedure](APPLE_FIRST_LIVE_SMOKE_TEST.md) for technical-only
> configuration, default disablement and explicit operator start.

> Subsequent local-deployment authorization: the persistent WSL database and
> long-term technical retention are now prepared and verified. See
> [the local deployment report](APPLE_INGESTION_LOCAL_DEPLOYMENT.md) for current
> host/backup status and remaining first-run blockers. The counts and deployment
> boundary below describe the completed E preparation gate. The later
> [smoke preparation](APPLE_FIRST_LIVE_SMOKE_TEST.md) simplifies authorization to
> a reusable default-closed project policy; no daily receipts are required.

**Date:** November 3, 2026, America/Los_Angeles.  
**Current status:** preparation and offline engineering gate complete; **first real run remains blocked**. No real run authorized.  
**Previous gate:** A–D engineering delivery passed external document-level review.  
**Stop boundary:** complete E, report readiness/blockers and stop. Phase F remains unauthorized.

## Scope and chosen integration approach

The approved seven-table schema, complete title/body versions, reconciliation,
comparison-reference policy and stopping predicates remain fixed. No alternate
source, new service, production deployment, scheduler, real Apple RSS request,
Git commit or push is authorized by this task.

Use the same Controller and page-transaction path for both run modes. Synthetic
behavior stays available; a separate explicit live execution policy is required
for live mode. Merely changing `run_mode` or an environment flag must not enable
network access. A one-run authorization must identify scope, operator/approver,
validity, budget and access/retention decision references; prepared templates are
pending and are not such an authorization. New targets remain disabled until a
future authorized maintenance action. An enabled row alone is insufficient.

The live factory performs read-only preflight and prepares a single target.
It consumes a local one-use receipt at `run_target` entry; the actual
`requests.Session` is constructed lazily at the first HTTP fetch. Live batch
execution is rejected before receipt consumption or Session construction. Offline verification mounts an in-process adapter on a real Session,
returns real Response objects from invented bytes and passes them through the
bounded transport, controller, database and diagnostics. This tests requests
preparation/integration; it does not test external DNS, TLS negotiation, Apple
availability, format distribution or current HTTP responses.

## Evidence and readiness status

| Area | Required evidence | Current state |
| --- | --- | --- |
| Approved architecture | Seven tables, full-text history, ownership/deferred FK, page atomicity, unchanged reference/stop semantics | Unchanged; complete 630-test regression passed. |
| Controlled live entry | Explicit fresh one-run approval, validity/scope checks before Session creation/run mutation, disabled targets blocked, no live batch/pilot shortcut | Implemented; 48 focused live-readiness cases and 5 independent integration cases passed. |
| Real requests integration | Real requests preparation + mounted offline adapter + real PostgreSQL + diagnostic/recovery assertions | Passed with actual non-superuser runtime LOGIN; no network claim. |
| JSON/Atom compatibility | Inventory of existing saved material plus explicitly synthetic structural fixtures | 36 new compatibility cases passed; inspected evidence is sanitized metadata, not raw-response replay. |
| Nested XML/XHTML | Determine whether original evidence establishes presence/absence; never silently drop valid text | Real representation unresolved; current strict rejection is retained unless separately reviewed evidence justifies a change. |
| Deployment | Reviewed host/DSN, maintenance/runtime/report roles, migration, disabled seed, permissions, UTC/logging and health checks | 25 deployment cases passed under two nonadmin ownership layouts; templates ready; no persistent host supplied or initialized. |
| Diagnostics/recovery | Private writable spool, bounded safe fields, receipt/unknown-state handling, stop/recovery procedure | E adapter/DB tests cover safe diagnostics, session loss, recovery, private receipt and unknown-state handling. Actual host durability remains unverified. |
| Retention | Named owner, approved period/policy, backup/export lifecycle and enforcement responsibility | Not supplied; live-blocking pending values. |
| Access basis | Project-specific applicability decision and references | Unresolved; see access/retention memo. |
| Runtime authorization | Explicit permission for a first bounded run | Not supplied. Preparation is not execution authorization. |
| Platform | Actual host/OS test evidence | Linux/WSL only; no Windows-native acceptance. |
| Seven-day live evidence | Separately authorized Phase F | Not started and not authorized. |

## Operator checklist before a first bounded run

The checklist separates preparation artifacts from facts that must be checked
on the chosen deployment. A checked template is not proof of a deployed system.

1. Confirm external A–D acceptance and the exact reviewed code/revision or source
   hashes. Record Python, dependency, PostgreSQL and OS versions. Verify migration
   head and seven core tables without regenerating history or using `create_all`.
2. Review the chosen database/host, schema and explicit DSN source. Keep secrets
   out of repository files, command-line logs and report output. Use a secured
   Unix socket or the deployment's validated TLS configuration; do not fall back
   to ambient `.netrc`, proxy credentials or another database/service definition.
3. Initialize only with a separately authorized maintenance operation. Ensure
   a real non-superuser maintenance owner owns the objects; runtime/report roles
   are separate nonowners with constrained privileges and no inherited bypass.
   Apply existing migrations/grants and seed exactly the eight US applications.
   Verify repeated seeding preserves existing settings. Leave targets disabled.
4. Confirm runtime SELECT/INSERT and narrow UPDATE permissions, append-only
   versions, no runtime DELETE, read-only report access, UTC-aware timestamps,
   safe SQL logging and no bound text/DSN/credential output. Test these under
   actual role logins on the selected host before calling it deployed-ready.
5. Resolve and record the applicable access basis, full-text/version retention
   owner/duration/policy and backup/export/spool lifecycle. Unknown or pending
   decisions block live execution. Do not replace full text with hashes.
6. Obtain a separate one-run authorization for named selected target(s), US/
   mostrecent, a validity window and bounded request scope. Ensure the approval
   matches the immutable run snapshot and references the reviewed access and
   retention decisions. No seven-day or recurring schedule is implied.
7. Verify the existing defaults: minimum two processed logical pages, maximum
   five pages, at least 20 overlapping IDs AND 20% overlap, ten HTTP requests
   including fallback, zero retries, global two-second spacing, 2 MB decoded
   body cap, 10/25-second connect/read limits and target deadline. Explicit
   settings must match target/snapshot/authorization; never relax them to make
   a low-volume run pass. Reference age above 72 hours warns, not excludes.
8. Confirm a private durable diagnostic/spool location and stable local receipt
   directory, correct modes, capacity and recovery owner. Test liveness/session
   loss without silent reconnection. A consumed/uncertain one-run record cannot
   be treated as permission for an automatic retry or a resumed RSS page.
9. Run a read-only deployment/readiness check and inspect every blocker. Enable
   only the selected target through an authorized maintenance action, then
   recheck. Construct the live HTTP session only after all gates are valid.
10. During the later run, retain safe run/attempt/configuration/coverage evidence.
    Store accepted review text only in the authorized database path. Ordinary
    logs and public reports must not retain raw responses or review bodies.
    Measure requests from durable evidence and retain honest unknown states.
11. Stop on access/rate denial, redirects, schema/unsupported-content failure,
    exhausted budget, session loss, uncertain persistence, diagnostic storage
    failure, expiry or revoked authorization. Do not retry automatically, change
    storefronts/hosts, bypass denial or skip malformed comments to claim coverage.
12. Inspect terminal state, committed markers, integrity, scope/budget and safe
    reports. An unexpected legal nested representation is a compatibility
    blocker to investigate, not a reason for permanent valid-comment exclusion.
    Preserve full text if handling is authorized; any raw quarantine/retrieval
    beyond the agreed evidence handling requires an explicit separate scope.
    End the bounded run without a scheduler. Do not start Phase F.

## Related evidence

- [Access and retention conditions](PHASE_E_ACCESS_RETENTION.md): official material
  checked in E, confirmed text versus unresolved applicability and needed decisions.
- [Feed compatibility inventory](PHASE_E_FEED_COMPATIBILITY.md): historical
  evidence limits, tested scalar profiles and the nested-content stop procedure.
- [Deployment runbook](PHASE_E_DEPLOYMENT_RUNBOOK.md): configuration, actual role
  checks, initialization, permissions, diagnostics, recovery and retention limits.
- [Independent integration review](PHASE_E_INTEGRATION_REVIEW.md): five
  cross-module scenarios and closed interface findings.
- [A–D implementation summary](../APPLE_INGESTION_IMPLEMENTATION_SUMMARY.md) and
  [C consistency review](PHASE_C_ARCHITECTURE_REVIEW.md) remain historical gate
  records; their old stop boundary was superseded only for E preparation.

## Test results, changes and concrete blockers

### Actual validation

The complete suite ran independently after focused implementation checks, using the shared Conda environment and a fresh temporary
PostgreSQL 16 cluster with TCP disabled:

```sh
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q --junitxml=/tmp/apple-phase-e-main.xml
```

**630 passed in 63.52 seconds, 0 failed, 0 errors, 0 skipped.** No pytest warnings
were emitted. The JUnit suite records 63.504 seconds. All 516 A–D tests remain
present and pass; E adds 114 cases:

| New suite | Cases | Main assertions |
| --- | ---: | --- |
| Feed compatibility | 36 | Scalar JSON/Atom mappings, full strings/tails in supported profiles, entity/CDATA distinctions, sanitized-evidence limits and strict unsupported nesting |
| Deployment | 25 | Strict pending templates, safe DSNs/TLS settings, nonadmin migration/seed/grants/rollback, actual runtime/report permissions, both ownership layouts and wrong-database rejection |
| Live readiness | 48 | Pending/default closure, one-use receipt, snapshot/batch/engine binding, actual requests streaming/fallback, budgets/expiry/denial, full text, lock/session/recovery and diagnostics |
| Independent integration | 5 | End-to-end real runtime LOGIN plus in-process requests adapter; no premature Session/run/receipt, prepared binding, expiry, cross-database isolation and receipt reuse |

The original 57 feasibility tests are included unchanged. The private cluster
was stopped and removed. `pip check` found no broken requirements in the shared
environment; `git diff --check` passed. Tests use invented response bytes and
test-only approval/access/retention fixtures. Even where a test database stores
`run_mode=live`, it is explicitly simulated branch coverage, not a real source
observation, real approval or seven-day live evidence. The Python TCP guard is
a test guard, not an OS firewall. External DNS/TLS/HTTP was not exercised.

### Implemented changes and architecture review

- `live.py` adds a pending approval format, explicit single-run policy, validity/
  scope/reference checks, local private fsynced one-use receipt and a context-
  managed live factory. A fresh actual-login deployment check precedes activation.
  Receipt reservation survives skips/failures and does not authorize retries.
- `controller.py` only integrates that policy into the existing acquisition
  path, forbids live batches, and caps the existing target deadline by remaining
  approval validity. `recovery.py` adds only a read-only configured-path property.
  Neither change alters reconciliation, references, thresholds or recovery rules.
- `deployment.py` adds typed configuration, review-only initialization/grant
  plans, explicitly requested caller-transaction initialization and SELECT-only
  preflight. It uses the existing Alembic revision, seed and permissions. The
  collector receives only the runtime engine; its audit connection remains
  separate. No extra runtime access to Alembic bookkeeping is granted.
- Prepared artifacts are [Unix configuration](../../deploy/apple_ingestion/unix.example.json),
  [TLS configuration](../../deploy/apple_ingestion/tls.example.json) and
  [single-run approval](../../deploy/apple_ingestion/single-run-approval.example.json).
  These contain no credentials and intentionally remain pending with null
  decision fields, no selected apps and execution authorization false.
- Compatibility, current access/retention conditions, deployment operations and
  independent review are documented in the linked records. README/progress
  now distinguish E preparation from the historical A–D gate and unopened F.

No core architecture deviation was required. Interface review found and closed
prepared-binding enforcement, actual database identity and diagnostic-path
contract issues; see E-I01 through E-I04 in the independent review. All related
tests pass. No parser/hash representation change was made without real evidence
and review. No new source/table/service, destructive migration, historical
rewrite, automated purge, scheduler or credential mechanism was introduced.

Against the 129-file pre-E checksum baseline, the only changed existing files
are README, the A–D summary's subsequent-status note, progress, controller and
recovery. No baseline file is missing. Approved design, seven-table models,
migration, parser, normalizer, reconciliation, reference code, historical
feasibility evidence and every existing test retain their pre-E bytes. New E
files are additive. Branch remains `main`, HEAD
`474736abcee2a67f186299f09d196125400eb1ab`, with nothing staged; these are
uncommitted working-tree changes, not a deployed release.

### Concrete blockers before the first bounded real run

1. **Execution authority:** no separate authorization for a real request/run was
   supplied. The pending example is not approval; no pilot or scheduler is permitted.
2. **Project decisions:** the applicable access basis and full-text retention
   owner/duration/policy, backup/export expiry and enforcement responsibilities
   remain unresolved. Current official wording and unresolved applicability are
   separated in the access/retention memo. A completed JSON record alone does
   not prove actual permission or operational enforcement.
3. **Actual deployment:** no persistent host/DSNs/authentication, runtime identity,
   private diagnostic/receipt locations, backup/expiry controls or separately
   authorized initialization has been selected and validated. Templates and
   temporary-database tests are preparation, not a deployment certificate.
4. **First technical source check:** no permitted current raw-response check or
   real DNS/TLS handshake occurred. The existing artifacts cannot establish
   nested-XHTML absence. A separately authorized bounded diagnostic must check
   the observed structure; legitimate unsupported content must stop as
   `COMPATIBILITY_BLOCKED` for correct support/review before continued use.
   This is an unverified compatibility condition, not a demonstrated feed defect.

The code validates explicit records; it does not authenticate approver identity
or synchronize revocations/receipts across hosts. Receipt uniqueness applies
only to processes sharing the same protected local directory. Operational
authorization custody, fixed directory and single-host control are prerequisites.
Retention expiry/backup restoration is a reviewed operational responsibility;
no purge implementation was requested or added. TLS profile configuration is
tested, not its real handshake. Only Linux/WSL is validated; Windows native,
actual arrival/edit ordering, complete source coverage, independent human
assessment and seven-day continuity remain unverified.

**Phase E stops here.** Preparation/offline engineering is complete; the actual
first-run prerequisites are not cleared. No Apple RSS request, persistent
deployment, Phase F collection, Git commit or push occurred.
