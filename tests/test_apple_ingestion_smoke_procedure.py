"""Execute the documented Smoke Python body with offline synthetic fixtures.

This proves the procedure's public APIs/output under a real nonadmin PostgreSQL
runtime and requests.Session with an in-process Adapter. The enabled test target,
policy confirmations, people, full text and private files are synthetic fixtures
in a disposable database/tmp directory. No real permission or RSS evidence is
created; the actual /home deployment configuration is never read or written.
"""
import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from feasibility.apple_ingestion import live
from feasibility.apple_ingestion.reporting import run_report
from test_apple_ingestion_deployment import deployed_roles
from test_apple_ingestion_live_readiness import ready, OfflineAdapter, factory_for, rows, R, F
from test_apple_ingestion_phase_c_integration import Clock, feed, assert_terminal_resolved
from test_apple_ingestion_project_policy import configured

ROOT = Path(__file__).resolve().parents[1]
PROCEDURE = ROOT / 'docs/APPLE_FIRST_LIVE_SMOKE_TEST.md'


@pytest.mark.parametrize('deployed_roles', ['database_owner'], indirect=True)
def test_documented_smoke_execute_command_completes_one_offline_run(
        deployed_roles, ready, tmp_path, monkeypatch, capsys):
    config, engines, environment, _, _ = ready
    value, _, _, _ = configured(ready, tmp_path)
    # The procedure deliberately checks wall-clock validity before opening DBs.
    # Center this explicit test-only policy on real wall time and inject a
    # monotonic fake clock at the same instant for the actual factory/run.
    instant = datetime.now(timezone.utc)
    value = replace(value, valid_from=instant-timedelta(minutes=1), valid_until=instant+timedelta(days=1))
    assert value.purpose == 'smoke' and value.source_application_ids == ('572688855',)
    assert 'offline-fixture' in value.access_basis_ref and 'not-real-confirmation' in value.access_basis_ref
    private = tmp_path / 'synthetic-private-config'
    private.mkdir(mode=0o700)
    for name, data in (
        ('project-policy.smoke.json', value.to_dict()),
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
    assert len(attempts) == 2 and all(row['persistence_status'] == 'committed' for row in attempts)
    with engines['runtime'].connect() as connection:
        report = run_report(connection, UUID(output['run_id']))
    assert report['requests']['intent_count'] == output['request_intents'] == 2
    assert report['requests']['known_sent_lower_bound'] == len(adapter.calls) == 2
    assert_terminal_resolved(engines['runtime'])
