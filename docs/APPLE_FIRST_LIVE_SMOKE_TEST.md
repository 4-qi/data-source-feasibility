# First Live Smoke Test preparation

Prepared November 3, 2026. **Preparation only: no Apple request, target
enablement, Phase F activation, commit or push.** The user accepted Phase E and
the persistent deployment, and authorized simplifying routine execution policy.
This does not confirm the outstanding data-use/long-term-retention arrangements.
No update to John is drafted or sent by this task.

## Selected target and bounded plan

**Todoist: To Do List & Calendar — `572688855`, US, mostrecent.** This is one of
the original eight apps. Existing [initial evidence](../results/mainstream/apple_rss_access.json)
records JSON page 1, page 2 and a repeated page 1, each successful/nonempty with
50 returned reviews and a five-record sanitized projection. The later
[online-readiness summary](../results/mainstream/apple_online_readiness.json)
records JSON success with 50 reviews. The artifact date is October 27; the actual
request timestamps are October 28 UTC. The [mobile comparison](../results/mobile_quality/collection.json)
provides additional historical page/repeat metadata.

This makes Todoist a practical first chain check without expanding source
research. These are historical sanitized observations, not retained raw feeds,
current availability, full-text replay or proof of nested-XHTML absence. Do not
import or rerun the old feasibility probes to execute this smoke test.

| Setting | Smoke plan |
| --- | --- |
| Scope | One explicit call for Todoist only; no batch or other app |
| Endpoint policy | Existing fixed HTTPS Apple host, US/mostrecent, JSON first |
| Logical pages | Minimum 2 for the normal stop predicate; maximum 5 |
| Overlap predicate | At least 20 overlapping IDs AND at least 20%; thresholds unchanged |
| HTTP budget | At most 10 physical requests, including fallback |
| Retry/fallback | Zero automatic retries; one Atom fallback on a JSON page with no reviews |
| Start spacing | At least 2 seconds globally within the shared sequential transport |
| HTTP limits | Connect/read 10/25 seconds; 2,000,000 decoded bytes per response |
| Target deadline | 900 seconds, further bounded by the project's remaining validity |
| Reference | Latest eligible LIVE evidence; insufficient previous overlap does not exclude it; >72h warns only |
| Current execution state | Policy disabled, access confirmation false, retention arrangement false, all targets disabled |

There is no early-stop guarantee after page 2: if no eligible prior LIVE run
exists, this first run normally uses the five-page baseline budget. Empty feeds
do not prove source exhaustion. Denial, malformed/unsupported content, deadline
or infrastructure failure can stop before two pages. Observed overlap is not
proof of complete review coverage. Low observable volume does not lower thresholds.

## Simplified project policy

The new entry is `ProjectExecutionPolicy` / `prepare_project_controller`.
One confirmed project JSON can be reused for multiple manually initiated or
future scheduled runs in its scope/window. It does **not** require fresh
approval documents, approver fields or one-use credentials for every run.
No receipt is created or consumed. Legacy single-run APIs remain for historical
compatibility/tests; they are not required by this procedure. Do not fill the
old `single-run-approval.json` to use the new path.

The [smoke template](../deploy/apple_ingestion/project-smoke.example.json) names
only Todoist and `purpose=smoke`. The [pilot plan template](../deploy/apple_ingestion/project-pilot-plan.example.json)
names the fixed eight apps and `purpose=pilot`. Both are disabled, unconfirmed,
with null policy ID, validity and access-basis reference. The private prepared
copies are `project-policy.smoke.json` and `project-policy.pilot-plan.json` in
`/home/l2838/.config/data-source-feasibility`.

The policy checks declared scope, validity (at most seven days), unchanged
per-run configuration and deployment, and reloads a file-backed policy before
requests. Mid-run changes/revocation stop the run. Every immutable run snapshot
records the project policy ID and canonical configuration SHA-256 in the existing
`access_decision_ref`; no snapshot-schema/table change is needed. Keep the
corresponding policy revision privately so the digest can be resolved later.
Archive policy revisions once when changed, not as a fresh daily approval.

`config.interval_hours=24` declares the plan. It is not a database-enforced
24-hour embargo: explicit manual follow-up is possible inside a valid scope.
There is no scheduler, new approval ledger or automatic retry. Planned seven-day
totals below assume exactly one run/app/day and are not an extra aggregate quota.
Use one collector process at a time; global spacing is not a distributed
cross-process rate limiter. Do not launch concurrent copies. Leave at least two
seconds after the previous request before a separate manual invocation.

## Current read-only readiness

The actual persistent WSL database was inspected using read-only transactions
and actual maintenance/runtime/report LOGIN connections. All match configured
nonadmin identities, UTC and public schema. PostgreSQL 16.15, existing revision
`0001_apple_ingestion`, seven core tables plus Alembic bookkeeping, exact eight
app seeds and existing least-privilege grants are correct. All eight targets are
disabled. Run/attempt/review/version/observation tables remain empty.

Private config/socket/log/diagnostic/receipt directories retain their expected
ownership and 0700 modes; files are 0600, the spool empty and receipts absent.
No restart, database/configuration mutation or diagnostic write probe was needed
for this check. Sanitized evidence: `/tmp/apple-smoke-persistent-preflight.json`.
See [persistent operations](APPLE_INGESTION_LOCAL_DEPLOYMENT.md) for actual paths,
manual PostgreSQL startup, private credentials and tested backup/restore.

Expected current readiness is database-ready **and live-blocked**:
`LONG_TERM_ARRANGEMENT_UNCONFIRMED`, `RETENTION_DECISION_PENDING`, plus the new
project's disabled/unconfirmed execution state. A pending configuration is
preparation, not an authorization record.

## Exact operator procedure

Run from the existing checkout and Conda interpreter. None of the activation or
execution steps below was performed in this preparation task.

### 1. Recheck without changing anything

The following command connects only to local PostgreSQL and prints safe
readiness metadata. It creates no HTTP Session, run, attempt or receipt.

<!-- smoke-readonly-check -->
```sh
cd '/mnt/c/Users/siqi/Downloads/实习/data-source-feasibility'
PYTHONNOUSERSITE=1 /home/l2838/miniconda3/envs/data-source-feasibility/bin/python - <<'PY'
import json
from pathlib import Path
from sqlalchemy import text
from feasibility.apple_ingestion.deployment import load_config, deployment_engine, preflight
from feasibility.apple_ingestion.live import ProjectExecutionConfig
private = Path('/home/l2838/.config/data-source-feasibility')
config = load_config(private / 'deployment.json')
environment = json.loads((private / 'connection.env.json').read_text())
project = ProjectExecutionConfig.from_dict(json.loads((private / 'project-policy.smoke.json').read_text()))
owner = deployment_engine(config, 'owner', environ=environment)
runtime = deployment_engine(config, 'runtime', environ=environment)
try:
    with owner.connect() as audit, runtime.connect() as actual_runtime:
        with audit.begin(), actual_runtime.begin():
            audit.exec_driver_sql('SET TRANSACTION READ ONLY')
            actual_runtime.exec_driver_sql('SET TRANSACTION READ ONLY')
            result = preflight(audit, config, for_live=True,
                environ=environment, runtime_connection=actual_runtime)
            targets = audit.execute(text('SELECT a.source_application_id,t.enabled FROM application a JOIN collection_target t ON t.application_id=a.id ORDER BY a.source_application_id')).all()
            print(json.dumps({'database_ready': result['database_ready'],
                'live_ready': result['live_ready'], 'blockers': result['blockers'],
                'purpose': project.purpose, 'selected_apps': project.source_application_ids,
                'execution_enabled': project.execution_enabled,
                'access_arrangement_confirmed': project.access_arrangement_confirmed,
                'targets': [dict(app=row[0], enabled=row[1]) for row in targets]}, indent=2))
finally:
    runtime.dispose()
    owner.dispose()
PY
```

### 2. Resolve actual project prerequisites once

Only after the responsible owner confirms the applicable arrangements and the
user authorizes the bounded real smoke run, an operator can update the private
files. These are **future required changes**, not values filled by Codex now:

| Private field | Required actual value/action |
| --- | --- |
| `project-policy.smoke.json`: `purpose`, apps | Keep `smoke`, exactly `["572688855"]` |
| `policy_id` | A real UUID identifying this project policy revision, generated once; not per run |
| `operator` | Existing actual operator `l2838`, matching deployment diagnostics |
| `access_basis_ref` | Reviewable reference to the actual project-level access/data-use decision; no invented approval |
| `valid_from`, `valid_until` | Actual UTC-aware window; proposed smoke window one hour, never more than seven days; currently null |
| `access_arrangement_confirmed` | Set true only when that confirmation actually exists |
| `execution_enabled` | Set true only for the separately authorized scope/window |
| `deployment.json`: `retention.arrangement_confirmed` | Set true only after actual long-term arrangements are confirmed; keep `long_term` and null days |
| Other config limits | Keep the prepared defaults; do not edit thresholds to make a small sample pass |

Do not alter credentials or DSNs. Keep old policy revisions and private backups.
The project-level confirmation can cover the seven-day scope; no daily forms
are needed. Activating `purpose=pilot` and its broader app list remains a later,
explicit Phase F decision, not a side effect of this smoke configuration.

### 3. Enable only the smoke target, after prerequisites

This is a future maintenance operation. Do not run now. First take the private
backup described in the deployment report. Use the existing owner service;
runtime has no target UPDATE permission.

```sh
export PGSERVICEFILE=/home/l2838/.config/data-source-feasibility/pg_service.conf
export PGPASSFILE=/home/l2838/.config/data-source-feasibility/pgpass
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGOPTIONS
/usr/lib/postgresql/16/bin/psql --dbname='service=apple_ingestion_owner' -X --set ON_ERROR_STOP=1 <<'SQL'
BEGIN;
UPDATE collection_target t SET enabled=true
FROM application a
WHERE t.application_id=a.id AND a.source='apple_app_store'
  AND a.source_application_id='572688855'
  AND t.storefront='us' AND t.sort_by='mostrecent';
SELECT a.source_application_id,t.enabled
FROM application a JOIN collection_target t ON t.application_id=a.id
ORDER BY a.source_application_id;
COMMIT;
SQL
```

Require exactly one enabled row, Todoist; stop if any other target is enabled.
Re-run the read-only check and inspect all blockers. Enabling a row alone never
authorizes HTTP. Never use a superuser connection for collection.

### 4. One bounded real invocation, only after clearance

This command makes **one** existing `Controller.run_target` call. It does not
schedule, loop over apps, create a receipt or automatically retry. The explicit
environment flag is operator intent to execute, not a replacement for the
project/deployment gates. Do not run it as part of current preparation.

<!-- smoke-execute-command -->
```sh
APPLE_EXECUTE_SMOKE=1 PYTHONNOUSERSITE=1 /home/l2838/miniconda3/envs/data-source-feasibility/bin/python - <<'PY'
import hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from feasibility.apple_ingestion.deployment import load_config, deployment_engine
from feasibility.apple_ingestion.live import ProjectExecutionPolicy, prepare_project_controller, LivePolicyError
from feasibility.apple_ingestion.recovery import DiagnosticSpool
from feasibility.apple_ingestion import controller as controller_module
if os.environ.get('APPLE_EXECUTE_SMOKE') != '1':
    raise SystemExit('PREPARATION_ONLY')
private = Path('/home/l2838/.config/data-source-feasibility')
policy = ProjectExecutionPolicy(config_path=private / 'project-policy.smoke.json')
try:
    project = policy.check_configuration(datetime.now(timezone.utc))
except LivePolicyError as error:
    print(str(error))
    raise SystemExit(2)
if project.purpose != 'smoke' or project.source_application_ids != ('572688855',):
    raise SystemExit('SMOKE_SCOPE_REQUIRED')
config = load_config(private / 'deployment.json')
environment = json.loads((private / 'connection.env.json').read_text())
owner = deployment_engine(config, 'owner', environ=environment)
runtime = deployment_engine(config, 'runtime', environ=environment)
code = Path(controller_module.__file__).parent
revision = 'uncommitted-' + hashlib.sha256(b''.join(
    path.name.encode() + path.read_bytes() for path in sorted(code.glob('*.py')))).hexdigest()[:20]
try:
    with owner.connect() as audit:
        with audit.begin():
            audit.exec_driver_sql('SET TRANSACTION READ ONLY')
            selected = audit.execute(text("SELECT a.id,a.source_application_id,t.id FROM application a JOIN collection_target t ON t.application_id=a.id WHERE a.source='apple_app_store' AND a.source_application_id='572688855' AND t.storefront='us' AND t.sort_by='mostrecent'")).one()
            enabled = audit.execute(text('SELECT a.source_application_id FROM application a JOIN collection_target t ON t.application_id=a.id WHERE t.enabled')).scalars().all()
            if enabled != ['572688855']:
                raise SystemExit('ONLY_SMOKE_TARGET_MAY_BE_ENABLED')
    snapshot = policy.make_snapshot(application_id=selected[0], source_application_id=selected[1],
        target_id=selected[2], software_revision=revision,
        retention_policy_ref=config.retention.policy_ref)
    batch_id = uuid4()
    with prepare_project_controller(runtime, DiagnosticSpool(environment[config.diagnostics.spool_path_env]),
            policy=policy, deployment_config=config, audit_engine=owner, environ=environment) as collector:
        result = collector.run_target(snapshot, batch_id)
    print(json.dumps({'batch_id': str(batch_id),
        'run_id': str(result.run_id) if result.run_id else None,
        'execution_status': result.execution_status, 'coverage_status': result.coverage_status,
        'stop_reason': result.stop_reason, 'reason_codes': list(result.reason_codes),
        'committed_pages': result.committed_pages, 'request_intents': result.request_count,
        'source_stop': result.source_stop, 'recovery_required': result.recovery_required}, indent=2))
finally:
    runtime.dispose()
    owner.dispose()
PY
```

Record the actual returned run ID. A null ID, error, partial/interrupted run or
uncertain persistence is not a successful smoke. Do not infer no request was
sent from a missing result. If interrupted, use existing spool/session recovery;
a later intentional run starts at page one, not the previous RSS page. Preserve
attempts, markers and uncertainty; do not delete evidence to obtain a clean result.

### 5. Verify the actual run without leaking review text

Set `SMOKE_RUN_ID` to the actual returned UUID, never a fabricated evidence ID.
The [SQL file](../deploy/apple_ingestion/smoke-postrun.sql) runs entirely inside
a read-only repeatable-read transaction and outputs only metadata/counts/lengths.

```sh
export PGSERVICEFILE=/home/l2838/.config/data-source-feasibility/pg_service.conf
export PGPASSFILE=/home/l2838/.config/data-source-feasibility/pgpass
unset PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD PGSERVICE PGOPTIONS
: "${SMOKE_RUN_ID:?Set the actual completed run UUID}"
/usr/lib/postgresql/16/bin/psql --dbname='service=apple_ingestion_report' -X --set ON_ERROR_STOP=1 --set run_id="$SMOKE_RUN_ID" --file=deploy/apple_ingestion/smoke-postrun.sql
```

Require `run_exists=true`; an empty result is not acceptance. Check terminal
execution/coverage, physical attempts <=10, pages <=5, no retries, finished
attempts, no pending/unknown persistence, version ownership, conflicts and
contiguous version sequence/current pointer. Sum committed page occurrences
must equal observation occurrences. Ordinary baseline/no-reference or
low-overlap classification is not an ingestion defect; interpret safe reason
codes rather than lowering thresholds. Versions created by this run and versions
observed by it are different counts on later unchanged runs.

For authoritative safe coverage/eligibility reasons, whole-database integrity
and recalculation of stored fingerprints, use the existing APIs. Full text is
read into private process memory only and is never printed:

<!-- smoke-postrun-python -->
```sh
PYTHONNOUSERSITE=1 /home/l2838/miniconda3/envs/data-source-feasibility/bin/python - <<'PY'
import json, os
from pathlib import Path
from uuid import UUID
from sqlalchemy import text
from feasibility.apple_ingestion.contracts import ReviewRecord
from feasibility.apple_ingestion.deployment import load_config, deployment_engine
from feasibility.apple_ingestion.normalizer import fingerprint
from feasibility.apple_ingestion.reporting import run_report, integrity_report
private = Path('/home/l2838/.config/data-source-feasibility')
config = load_config(private / 'deployment.json')
environment = json.loads((private / 'connection.env.json').read_text())
run_id = UUID(os.environ['SMOKE_RUN_ID'])
engine = deployment_engine(config, 'report', environ=environment)
try:
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            report = run_report(connection, run_id)
            rows = connection.execute(text('SELECT i.source_review_id,v.title,v.body,v.rating,v.application_version,v.source_updated_at,v.content_hash,v.metadata_hash FROM review_observation o JOIN review i ON i.id=o.review_id JOIN review_version v ON v.id=o.observed_version_id WHERE o.run_id=:run_id'), dict(run_id=run_id)).all()
            mismatches = 0
            for row in rows:
                record = ReviewRecord(row[0], row[1], row[2], row[3], row[4], row[5])
                mismatches += fingerprint(record) != (bytes(row[6]), bytes(row[7]))
            print(json.dumps({'run': report, 'integrity': integrity_report(connection),
                'checked_observed_versions': len(rows), 'stored_fingerprint_mismatches': mismatches}, indent=2))
finally:
    engine.dispose()
PY
```

Hash agreement proves consistency with stored fields, not complete upstream
coverage or independent absence of truncation. At least one accepted nonempty
review/version/observation is needed to exercise the text-storage part of the
chain. If an authorized private text inspection is needed, query only selected
`title`, `body` and metadata in a private read-only database client; do not use
ordinary terminal logs, `tee`, screenshots or public reports for that output.
Do not print raw response bytes, SQL parameters, exceptions, credentials or
complete policy/config snapshots. Existing private human-assessment export is
available later; no human labels are invented by this smoke test.

Stop on denial/rate limit, redirect, unsupported schema/nested content, cap or
deadline, project expiry/change, session loss, uncertain persistence or unsafe
diagnostic storage. Legitimate unsupported XML/XHTML is an operational
`COMPATIBILITY_BLOCKED` finding, not a reason to skip valid reviews. Do not force
an extra XML request merely to exercise fallback. The smoke may exercise only
JSON; paired-format diagnosis would be a separately scoped technical action.

After inspecting the result, take a private backup and leave collection stopped.
An authorized maintenance operator can set Todoist back to disabled using the
same UPDATE above with `enabled=false`. Do not enable other targets or switch
to the pilot configuration automatically.

## Seven-day plan, not activated

Let `T0` be the future approved UTC start. No calendar start or valid policy
dates have been filled. Use the original fixed eight apps in manifest order:
Todoist, Microsoft To Do, Duolingo, Khan Academy, Amazon Shopping, Etsy,
Uber and Lyft. Verify the manifest identities rather than adding
apps or changing storefronts. The first smoke remains outside this schedule.

| Slot | Planned start | Work |
| --- | --- | --- |
| Day 1 | `T0` | Sequential eight-app batch, one shared transport; select existing eligible LIVE references |
| Days 2–6 | `T0 + 24h` through `T0 + 120h` | One sequential batch per day, unchanged per-target limits |
| Day 7 | `T0 + 144h` | Final batch, terminal/integrity review and private backup |
| End | Before `T0 + 168h` | Stop collection; no automatic extension or eighth-day run |

Use exact 24-hour UTC spacing across DST. There are 56 planned target runs,
at most 280 committed logical pages and **560 planned physical-request budget
slots**, including fallback, plus the separately counted smoke <=10. They are
upper bounds for the declared schedule, not promises that every request/page
will occur. Additional manual follow-up is never automatic; account for it
explicitly rather than claiming it was included in these totals.

No cron/systemd timer, task, daemon or schedule activation is installed. A later
explicit Phase F start uses the confirmed pilot project configuration and
`prepare_project_controller` with the existing `Controller.run_batch`, one batch
UUID per daily invocation, no daily approval documents/receipts. It retains
the existing source-denial/infrastructure short-circuit across subsequent apps.
No second controller or source is developed for this plan.

Daily reporting checklist (not a draft to John):

- Expected versus actual target slots, safe run/batch IDs, terminal states and
  honest missing/skipped/unknown slots; distinguish real evidence from fixtures.
- Physical attempts, fallback/retries, page commits, HTTP/parse/persistence errors,
  denial and source-stop/recovery conditions. Do not automatically replay a failed day.
- Distinct observations, occurrences/duplicates/disputes, new/changed/unchanged
  versions, coverage classification/reasons, comparison eligibility and age warning.
- Six integrity counters, safe logs/private directory capacity, backup identity
  and restore-readiness checks; no review-body export in ordinary reports.
- Separately record any actual human assessment and remaining applicability or
  retention questions. Successful HTTP does not establish rights, fresh arrivals,
  complete source coverage or seven-day continuity.

## Acceptance and remaining actions

Main-chat full regression completed on the final working tree:

```sh
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q --junitxml=/tmp/apple-project-smoke-full-suite.xml
```

**668 passed in 79.56 seconds: 0 failed, 0 errors, 0 skipped; no pytest warnings.**
All previous 640 cases remain; 27 new project-policy cases cover pending states,
limits, scope/window, repeated runs, changed/revoked configuration, immutable
trace, legacy compatibility and retention closure. Two of those cases exercise
the same project/transport across two eight-app batches with a simulated 24h
gap (16 fixture runs, 32 injected requests), under both nonadmin ownership layouts.
One additional integration case executes the actual smoke-command Python body
with only its private config directory replaced by temporary files, injected
clock and a genuine requests.Session with an in-process Adapter. It verifies
one Todoist run, terminal baseline, two committed fixture pages and output/API
correctness. These are explicitly invented responses/confirmations, not actual
source observations or a real pilot. The actual prepared smoke configuration
retains the default five-page cap; the integration fixture deliberately uses
two pages within the supported 2–5 range.

The exact read-only runbook command was separately executed on persistent WSL:
database ready, all targets disabled and live blocked. All three embedded Python
procedures compile. The execute procedure was negatively checked with the actual
pending private policy: `PROJECT_EXECUTION_DISABLED`, exit 2, before any engine
or HTTP Session construction. The report-role SQL file was executed read-only
against the empty persistent database with an intentionally nonexistent UUID;
it correctly reported `run_exists=false`. That syntax check is not a run or
a successful post-collection acceptance. No business rows were created.

Reporting recognizes `policy_stop` and the enumerated `PROJECT_*` codes; known
send lower bounds continue to use durable HTTP status, distinct from request
intent counts. Deployment preflight identifies the reusable project policy as
the default authorization boundary and labels the legacy API separately; it
still grants no execution permission itself. No new table, migration, source,
scheduler or ingestion/reconciliation/reference/parser/hash change was made.
`git diff --check` and dependency consistency checks pass; no historical evidence
was modified. Working branch/HEAD remain `main` /
`474736abcee2a67f186299f09d196125400eb1ab`, with nothing staged.

The current concrete prerequisites remain: actual
project-level access/long-term arrangement confirmation; genuine policy scope,
validity and execution enablement; and a later authorized enablement of the
single target. No fresh per-run approval mechanism is needed. Current upstream
format/DNS/TLS is an untested technical condition for that later bounded run,
not a reason to invent a successful observation now.

Readiness checklist:

- [x] Persistent database, migration, actual roles and private directories checked read-only.
- [x] Todoist selected from existing evidence; limits, fallback and stop conditions fixed.
- [x] Reusable policy, exact smoke command and safe post-run checks verified offline.
- [x] Seven-day plan prepared with no scheduling activated.
- [ ] Responsible owner confirms actual access/long-term arrangements.
- [ ] Operator records genuine scope/reference/window and explicitly enables project execution.
- [ ] Later authorized maintenance enables only Todoist; preflight then clears all actual blockers.
- [ ] Authorized smoke obtains real evidence and passes post-run review; no success is claimed now.
- [ ] Separate Phase F start decision, after smoke review; never automatic.

**Stop after preparation.** The next discussion with John can address the
outstanding arrangements, but drafting/sending it and executing the smoke or
Phase F are outside this task.
