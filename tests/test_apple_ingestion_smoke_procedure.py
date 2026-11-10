"""Execute the documented Smoke Python body with offline synthetic fixtures.

This proves the procedure's public APIs/output under a real nonadmin PostgreSQL
runtime and requests.Session with an in-process Adapter. The enabled test target,
technical settings, operator, full text and private files are synthetic fixtures
in a disposable database/tmp directory. No real permission or RSS evidence is
created; the actual /home deployment configuration is never read or written.
"""
import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from feasibility.apple_ingestion import live
from feasibility.apple_ingestion.reporting import run_report
from test_apple_ingestion_deployment import deployed_roles
from test_apple_ingestion_live_readiness import ready, OfflineAdapter, factory_for, rows, R, F
from test_apple_ingestion_phase_c_integration import Clock, feed, assert_terminal_resolved

ROOT = Path(__file__).resolve().parents[1]
PROCEDURE = ROOT / 'docs/archive/APPLE_FIRST_LIVE_SMOKE_TEST.md'


@pytest.mark.parametrize('deployed_roles', ['database_owner'], indirect=True)
def test_documented_smoke_execute_command_completes_one_offline_run(
        deployed_roles, ready, tmp_path, monkeypatch, capsys):
    config, engines, environment, legacy_snapshot, _ = ready
    # Unresolved administrative metadata is deliberately left pending, not
    # invented as a confirmation or reference to get the technical path to run.
    config = replace(config, retention=replace(config.retention, state='pending', owner=None,
        duration_days=None, policy_ref=None, backup_handling_ref=None, export_handling_ref=None,
        expiry_review_ref=None))
    assert config.retention.state == 'pending' and config.retention.policy_ref is None
    # The procedure deliberately checks wall-clock validity before opening DBs.
    # Center this explicit test-only policy on real wall time and inject a
    # monotonic fake clock at the same instant for the actual factory/run.
    instant = datetime.now(timezone.utc)
    value = live.ProjectExecutionConfig(policy_id=uuid4(), operator=config.diagnostics.operator,
        execution_enabled=True, valid_from=instant-timedelta(minutes=1), valid_until=instant+timedelta(days=1),
        purpose='smoke', source_application_ids=('572688855',), config=legacy_snapshot.config)
    assert value.purpose == 'smoke' and value.source_application_ids == ('572688855',)
    payload = value.to_dict()
    assert set(payload) == {'schema_version', 'policy_id', 'operator', 'execution_enabled',
        'valid_from', 'valid_until', 'purpose', 'source_application_ids', 'storefront', 'sort_by', 'config'}
    assert not {'access_basis_ref', 'access_arrangement_confirmed', 'approved_by', 'approval_id',
                'execution_authorized', 'retention_policy_ref'} & payload.keys()
    private = tmp_path / 'synthetic-private-config'
    private.mkdir(mode=0o700)
    for name, data in (
        ('project-policy.smoke.json', payload),
        ('deployment.json', config.to_dict()),
        ('connection.env.json', environment),
    ):
        path = private / name
        path.touch(mode=0o600)
        path.write_text(json.dumps(data), encoding='utf-8')

    clock = Clock()
    clock.now = lambda: instant + timedelta(seconds=clock.seconds)
    adapter = OfflineAdapter(engines['runtime'], clock, [
        (200, feed(('SYNTHETIC_SMOKE_FIRST',))),
        (200, feed(('SYNTHETIC_SMOKE_SECOND',))),
    ])
    session_factory, sessions = factory_for(adapter)
    actual_prepare = live.prepare_project_controller
    preparations = []

    def offline_prepare(*args, **kwargs):
        assert kwargs['policy'].config_path == private / 'project-policy.smoke.json'
        assert not {'session_factory', 'now', 'clock', 'sleep'} & kwargs.keys()
        preparations.append(1)
        return actual_prepare(*args, **kwargs, session_factory=session_factory,
                              now=clock.now, clock=clock.monotonic, sleep=clock.sleep)

    monkeypatch.setattr(live, 'prepare_project_controller', offline_prepare)
    monkeypatch.setenv('APPLE_EXECUTE_SMOKE', '1')
    document = PROCEDURE.read_text(encoding='utf-8')
    marker = '<!-- smoke-execute-command -->'
    assert document.count(marker) == 1
    shell = document.split(marker, 1)[1].split('```sh\n', 1)[1].split('```', 1)[0]
    python = shell.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    program = ast.parse(python)
    substitutions = 0
    for statement in program.body:
        if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == 'private'):
            assert isinstance(statement.value, ast.Call)
            assert isinstance(statement.value.func, ast.Name) and statement.value.func.id == 'Path'
            assert len(statement.value.args) == 1 and not statement.value.keywords
            assert ast.literal_eval(statement.value.args[0]) == '/home/l2838/.config/data-source-feasibility'
            # The only source substitution: bind the private path to tmp files.
            statement.value.args[0] = ast.copy_location(ast.Constant(str(private)), statement.value.args[0])
            substitutions += 1
    assert substitutions == 1
    assert rows(engines['runtime'], R) == rows(engines['runtime'], F) == []
    capsys.readouterr()
    exec(compile(ast.fix_missing_locations(program), str(PROCEDURE) + '::smoke-execute-command', 'exec'),
         {'__name__': '__main__'})
    output = json.loads(capsys.readouterr().out)
    assert set(output) == {'batch_id', 'run_id', 'execution_status', 'coverage_status',
                           'committed_pages', 'request_intents', 'source_stop', 'recovery_required',
                           'stop_reason', 'reason_codes'}
    assert UUID(output['batch_id']) and UUID(output['run_id'])
    assert output['execution_status'] == 'succeeded' and output['coverage_status'] == 'baseline'
    assert output['committed_pages'] == output['request_intents'] == 2
    assert output['source_stop'] is output['recovery_required'] is False
    assert len(preparations) == len(sessions) == 1 and adapter.closed
    assert [(app, page, format) for app, page, format, _ in adapter.calls] == [
        ('572688855', 1, 'json'), ('572688855', 2, 'json')]
    runs, attempts = rows(engines['runtime'], R), rows(engines['runtime'], F)
    assert len(runs) == 1 and str(runs[0]['id']) == output['run_id']
    assert str(runs[0]['batch_id']) == output['batch_id']
    assert runs[0]['config_snapshot']['source_application_id'] == '572688855'
    assert runs[0]['config_snapshot']['retention_policy_ref'] is None
    assert len(attempts) == 2 and all(row['persistence_status'] == 'committed' for row in attempts)
    with engines['runtime'].connect() as connection:
        report = run_report(connection, UUID(output['run_id']))
    assert report['requests']['intent_count'] == output['request_intents'] == 2
    assert report['requests']['known_sent_lower_bound'] == len(adapter.calls) == 2
    assert_terminal_resolved(engines['runtime'])
