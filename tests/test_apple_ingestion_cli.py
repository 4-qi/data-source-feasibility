"""Offline CLI boundaries: explicit DB, synthetic only, no secret-bearing errors."""
import json

import pytest

from feasibility.apple_ingestion.cli import main


def test_help_and_subcommand_help_never_connect(monkeypatch,capsys):
    from feasibility.apple_ingestion import db
    monkeypatch.setattr(db,'create_db_engine',lambda *args:pytest.fail('help touched database'))
    for argv in (['--help'],['rehearse','--help'],['report','--help'],['assessment','--help']):
        with pytest.raises(SystemExit) as stop:
            main(argv)
        assert stop.value.code==0
    assert 'live collection command' in capsys.readouterr().out


@pytest.mark.parametrize('argv',[
    [],['live'],['collect'],['rehearse','--output','/tmp/fresh'],
    ['report','--database-url','postgresql://PRIVATE_SECRET@remote/shared','--output','/tmp/out'],
    ['assessment','--database-url','postgresql://PRIVATE_SECRET@remote/shared','--disposable','--output','/tmp/out'],
])
def test_incomplete_or_live_arguments_reject_without_echoing_secrets(argv,monkeypatch,capsys):
    from feasibility.apple_ingestion import db
    monkeypatch.setattr(db,'create_db_engine',lambda *args:pytest.fail('invalid arguments connected'))
    assert main(argv)==2
    captured=capsys.readouterr()
    assert 'PRIVATE_SECRET' not in captured.out+captured.err
    assert json.loads(captured.out)['error']=='INVALID_ARGUMENTS'


def test_remote_database_rejected_without_connection_or_credentials(capsys):
    assert main(['rehearse','--database-url','postgresql://PRIVATE_SECRET@remote.example/production',
        '--disposable','--output','/tmp/uncreated-offline-cli-test'])==1
    captured=capsys.readouterr()
    assert 'PRIVATE_SECRET' not in captured.out+captured.err
    assert json.loads(captured.out)['error']=='PRIVATE_DISPOSABLE_DATABASE_REQUIRED'


def test_actual_report_and_pending_assessment_commands(apple_database,tmp_path,capsys):
    from datetime import datetime,timezone
    from pathlib import Path
    from uuid import uuid4
    from feasibility.apple_ingestion.contracts import ConfigSnapshot
    from feasibility.apple_ingestion.controller import Controller
    from feasibility.apple_ingestion.parser import PARSER_VERSION
    from feasibility.apple_ingestion.recovery import DiagnosticSpool
    from feasibility.apple_ingestion.seed import load_seed_manifest,seed_defaults
    from feasibility.apple_ingestion.synthetic import SimulatedClock,ScenarioSession
    from feasibility.apple_ingestion.transport import BoundedTransport
    manifest=Path(__file__).resolve().parents[1]/'results/mainstream/app_sample_manifest.json'
    apps=load_seed_manifest(manifest)
    with apple_database.begin() as c:
        seeded=seed_defaults(c,manifest)
    clock=SimulatedClock(datetime(2026,10,29,16,tzinfo=timezone.utc))
    session=ScenarioSession([app.source_application_id for app in apps],clock)
    controller=Controller(apple_database,BoundedTransport(session,clock=clock.monotonic,sleep=clock.sleep),
        DiagnosticSpool(tmp_path/'spool.jsonl'),now=clock.now,monotonic=clock.monotonic)
    snapshot=ConfigSnapshot(application_id=seeded.application_ids[0],target_id=seeded.target_ids[0],
        source_application_id=apps[0].source_application_id,software_revision='synthetic-cli-fixture',parser_version=PARSER_VERSION)
    run=controller.run_target(snapshot,uuid4())
    assert run.execution_status=='succeeded'
    url=apple_database.url.render_as_string(hide_password=False)
    report_dir=tmp_path/'safe-report'
    assert main(['report','--database-url',url,'--disposable','--output',str(report_dir),
        '--run-id',str(run.run_id)])==0
    safe=(report_dir/'report.json').read_text()
    assert 'SYNTHETIC_BODY' not in safe and json.loads(safe)['evidence_kind']=='synthetic'
    private=tmp_path/'assessment'
    assert main(['assessment','--database-url',url,'--disposable','--output',str(private),
        '--cutoff',clock.now().isoformat(),'--seed','cli-private-synthetic'])==0
    pending=json.loads((private/'private-assessment/responses.pending.json').read_text())
    assert len(pending['records'])==10 and all(row['label'] is None and not row['full_text_read'] for row in pending['records'])
    summary=json.loads((private/'assessment-pending.json').read_text())['summary']['overall']
    assert summary['assessed']==0 and summary['unassessed']==10 and summary['usefulness_rate'] is None
    assert summary['shortfall']==70
    captured=capsys.readouterr()
    assert url not in captured.out+captured.err
    assert 'SYNTHETIC_BODY' not in captured.out+captured.err
