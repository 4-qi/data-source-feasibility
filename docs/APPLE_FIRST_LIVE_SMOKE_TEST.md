# First Live Smoke Test preparation

> Final baseline handoff: the execution-policy correction has been accepted for
> a separate local follow-up commit to `cadc16c`. Implementation bytes match the
> 668-test regression record; only handoff/status documentation is updated now.
> The operator procedure below is fixed. This handoff does not enable a target,
> perform a real request, confirm data-use rights or activate Phase F.

Prepared November 3, 2026. **Preparation only: no Apple request, target
enablement, Phase F activation, commit or push.** The user accepted Phase E and
the persistent deployment, and requested technical-only runtime configuration.
Data-use and long-term-retention questions remain documented for discussion;
they are not runtime confirmation flags or approval-document prerequisites.
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
| Current execution state | Project execution disabled; all targets disabled; no current operation changes either state |

There is no early-stop guarantee after page 2: if no eligible prior LIVE run
exists, this first run normally uses the five-page baseline budget. Empty feeds
do not prove source exhaustion. Denial, malformed/unsupported content, deadline
or infrastructure failure can stop before two pages. Observed overlap is not
proof of complete review coverage. Low observable volume does not lower thresholds.

## Simplified project policy

The new entry is `ProjectExecutionPolicy` / `prepare_project_controller`.
One technically configured project JSON can be reused for multiple manually initiated or
future scheduled runs in its scope/window. It does **not** require fresh
approval documents, approver fields or one-use credentials for every run.
No receipt is created or consumed. Legacy single-run APIs remain for historical
compatibility/tests; they are not required by this procedure. Do not fill the
old `single-run-approval.json` to use the new path.

The [smoke template](../deploy/apple_ingestion/project-smoke.example.json) names
only Todoist and `purpose=smoke`. The [pilot plan template](../deploy/apple_ingestion/project-pilot-plan.example.json)
names the fixed eight apps and `purpose=pilot`. Both are disabled,
with null technical policy ID and validity. The policy contains only its tracking
ID, operator, scope, window, execution switch and request limits; no access
confirmation, access-basis reference, approver or rights declaration is needed. The private prepared
copies are `project-policy.smoke.json` and `project-policy.pilot-plan.json` in
`/home/l2838/.config/data-source-feasibility`.

The policy checks declared scope, validity (at most seven days), unchanged
per-run configuration and deployment, and reloads a file-backed policy before
requests. Mid-run changes/revocation stop the run. Every immutable run snapshot
records the project policy ID and canonical configuration SHA-256 in the existing
`access_decision_ref` reference slot; this legacy field name carries a technical
trace, **not** a rights decision or approval. `retention_policy_ref` may be null.
No snapshot-schema/table change is needed. Keep the
corresponding policy revision privately so the digest can be resolved later.
Archive technical policy revisions when changed; no daily approval is involved.

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

That earlier read-only check reported retention/access-related blockers under
the former gates. Those administrative gates are now removed from runtime; the
old result must not be presented as a fresh check of the corrected code. No
persistent configuration or database was changed/rechecked by this correction.
Current execution remains disabled at both the technical project switch and
the targets. A future read-only check must assess actual PostgreSQL/roles,
scope/window/budgets and diagnostic safety, without asking the code to confirm
data-use or long-term arrangements. The deployment report's `live_ready` field
is technical readiness only: it may be true while project execution is disabled,
and it neither starts HTTP nor confirms administrative arrangements.

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
                'technical_policy_id': str(project.policy_id) if project.policy_id else None,
                'targets': [dict(app=row[0], enabled=row[1]) for row in targets]}, indent=2))
finally:
    runtime.dispose()
    owner.dispose()
PY
```

### 2. Configure the technical scope once — future operator action

These are prepared instructions, not actions performed now. The operator fills
only the technical configuration needed for a later explicitly initiated run:

| Private field | Technical value/action |
| --- | --- |
| `project-policy.smoke.json`: `purpose`, apps | Keep `smoke`, exactly `["572688855"]` |
| `policy_id` | UUID identifying this technical configuration revision, generated once; tracking only, not approval or a per-run receipt |
| `operator` | Named actual operator, matching deployment diagnostics |
| `valid_from`, `valid_until` | UTC-aware window; proposed smoke window one hour, never more than seven days; currently null |
| `execution_enabled` | Explicit operator switch for that scope/window; remains false during this preparation |
| Other config limits | Keep the prepared defaults; do not edit thresholds to make a small sample pass |

No `access_basis_ref`, access confirmation, retention confirmation, approval file
or approver identity is required to execute the technical path. Do not invent
such values to satisfy code. Administrative data-use and long-term-retention
questions remain in the discussion list below; an unresolved discussion is not
a code-confirmed permission or a runtime blocker. A nullable retention reference
is metadata, not an execution decision.

Do not alter credentials or DSNs. Keep technical revisions and private backups.
Activating `purpose=pilot` and its broader app list remains a later explicit
Phase F decision, not a side effect of this smoke configuration.

### 3. Enable only the smoke target after technical configuration

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
Re-run the read-only check and inspect all blockers. A target row alone does not start HTTP: the technical project switch,
scope/window/limits and PostgreSQL checks must also pass. Never use a superuser connection for collection.

### 4. One bounded invocation — future explicit operator action

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
        retention_policy_ref=None)
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

Let `T0` be the future operator-selected UTC start. No calendar start or valid policy
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
explicit Phase F start uses the enabled technical pilot configuration and
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

The earlier main-chat full regression recorded **668 passed**, with no failed,
error or skipped tests, before this technical-only gate correction. That is a
historical checkpoint, not a claim that the revised working tree has already
passed a fresh full suite. The coordinating chat owns the updated full-suite
acceptance and its actual totals.

The narrow procedure test executes the actual `smoke-execute-command` Python
body below this document's marker with only its private path replaced by a tmp
fixture. The same real factory receives an injected clock and requests.Session
with an in-process Adapter. Its pending retention metadata and absent approval/
rights-confirmation fields must not block the technical run. All configuration,
review text and target changes in that test belong only to a disposable test
database. No actual deployment, target or project switch is activated.

### Full correction acceptance (current)

The main chat ran the complete regression after the runtime correction:

```sh
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite -q --junitxml=/tmp/apple-operational-controls-full-suite.xml
```

**668 passed in 82.80 seconds; 0 failed, 0 errors, 0 skipped, no pytest warnings.**
Affected tests now verify the corrected boundary rather than demanding the old
administrative gates. Default disablement, app scope, validity, unchanged
budgets/spacing/timeouts, denial stops, safe logs, actual restricted logins,
transactions, integrity, recovery and immutable technical trace remain covered.
The suite uses invented responses and a separate temporary PostgreSQL cluster;
no test success is real source evidence.

The main chat also checked the actual persistent environment in read-only
transactions. `database_ready=true`, `runtime_login_verified=true` and
`operational_ready=true`, with no engineering preflight blockers. The legacy
`live_ready` field means only deployment operational readiness; it is not
permission or an assertion of data-use rights. Both actual project configurations
still fail pure policy checks with `PROJECT_EXECUTION_DISABLED`, all eight
targets are disabled, and run/attempt/review/version/observation counts are zero.
Four private configuration files retain their exact bytes; their old false
administrative flags are accepted and ignored, never changed to true.
Sanitized verification: `/tmp/apple-operational-correction-readiness.json`.

The scope of the code change is the live policy, snapshot value-contract
validation and deployment preflight. No table/migration, parsing, normalization,
reconciliation, comparison-reference or stopping-algorithm change was made.
The design document only clarifies this administrative/technical boundary.
No actual HTTP, target enablement, scheduler, Phase F, John update, commit or push
was performed. The working HEAD remains the prior baseline `cadc16c`.

Targeted correction validation:

```sh
PYTHONNOUSERSITE=1 APPLE_TEST_PYTHON=/home/l2838/miniconda3/envs/data-source-feasibility/bin/python bash scripts/test_apple_ingestion_postgres.sh --full-suite tests/test_apple_ingestion_smoke_procedure.py -q --tb=short
```

Result: **1 passed in 1.71 seconds, 0 failed, 0 skipped**. No access/approval
fields appear in the technical project JSON, retention metadata stays pending
with null references, and the one fixture Todoist run completes two pages.
`request_intents=2` agrees with `known_sent_lower_bound=2` and the two Adapter
calls. The actual smoke remains unexecuted. The procedure prints durable `request_intents`, not
an assumed number of actual sends. Cross-check the known-send lower bound using
`run_report.requests.known_sent_lower_bound`. Keep the safe `stop_reason` and
`reason_codes` so a local technical refusal cannot be mistaken for a clean run.
The actual prepared smoke cap remains five pages; the positive fixture uses two
pages within the existing 2–5 range. No source evidence or human assessment is
manufactured by these fixtures.

Current operational steps remain technical: record the tracking ID/operator,
scope and window; explicitly enable project execution and only the selected
target during a future requested operation; inspect actual PostgreSQL/diagnostic
checks; then make one bounded call and review its real result. Current upstream
format/DNS/TLS remains untested by this preparation. The pending administrative
questions are documented separately and do not become runtime authorization
flags, mandatory references or an approval workflow.

Readiness checklist:

- [x] Actual persistent deployment checked read-only; private configs unchanged, all eight targets disabled.
- [x] Todoist selected from existing evidence; limits, fallback and stop conditions unchanged.
- [x] Technical-only policy and safe post-run procedure prepared; no fabricated approval fields are needed.
- [x] Seven-day plan prepared with no scheduling activated.
- [ ] Operator records technical ID/operator/scope/window and explicitly enables project execution for a future run.
- [ ] Future maintenance enables only Todoist and checks actual database/diagnostic safety; currently all targets stay disabled.
- [ ] Smoke obtains actual evidence and passes post-run review; no success is claimed now.
- [ ] Separate Phase F start decision, after smoke review; never automatic.

Discussion items, **not runtime gates**: applicable source/data-use conditions,
long-term retention intent and owner, private full-text access, backups/exports,
and their lifecycle. Successful HTTP or an enabled switch settles none of those
questions. They remain available for a later discussion with John; this task
neither drafts nor sends that update and does not mark any arrangement confirmed.

**Stop after preparation.** No real RSS request, persistent target/project
activation, Phase F execution, commit or push is part of this correction.
