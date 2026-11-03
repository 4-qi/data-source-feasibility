"""Offline synthetic-only commands; --help never imports a DB driver/connects."""
import argparse
from datetime import date, datetime
import json
from uuid import UUID


class _CliError(RuntimeError):
    def __init__(self,code):
        self.code=code


class _Parser(argparse.ArgumentParser):
    def error(self,message):
        # Do not echo an unrecognized credential/DSN argument to stderr.
        raise _CliError('INVALID_ARGUMENTS')


def _parser():
    parser=_Parser(description='Offline synthetic Apple ingestion tools; no live collection command.')
    commands=parser.add_subparsers(dest='command',required=True,parser_class=_Parser)
    for name,description in [('rehearse','Run seven synthetic calendar days in an empty disposable database.'),
                             ('report','Export a safe report from synthetic database rows.'),
                             ('assessment','Export a private pending synthetic assessment sample.')]:
        cmd=commands.add_parser(name,help=description)
        cmd.add_argument('--database-url',required=True,help='Explicit psycopg PostgreSQL URL on a private /tmp Unix socket.')
        cmd.add_argument('--disposable',action='store_true',required=True,help='Required opt-in for an apple_phase_a_ database.')
        cmd.add_argument('--output',required=True,help='New absolute directory under /tmp, outside Git.')
        if name=='rehearse':
            cmd.add_argument('--initialize',action='store_true',help='Explicitly migrate this empty disposable database.')
            cmd.add_argument('--start-date',default='2026-10-29',help='Simulated first local date, YYYY-MM-DD.')
            cmd.add_argument('--software-revision',default='synthetic-uncommitted-phase-d')
        elif name=='report':
            kind=cmd.add_mutually_exclusive_group(required=True)
            kind.add_argument('--run-id')
            kind.add_argument('--batch-id')
            kind.add_argument('--integrity',action='store_true')
        else:
            cmd.add_argument('--cutoff',required=True,help='Aware ISO timestamp; no current-time default.')
            cmd.add_argument('--seed',required=True)
            cmd.add_argument('--per-app',type=int,default=10)
    return parser


def _initialize(engine):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from .synthetic import ROOT,_assert_empty
    with engine.connect() as c:
        tables=set(c.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
        if tables:
            _assert_empty(c)
    config=Config(str(ROOT/'alembic.ini'))
    config.set_main_option('script_location',str(ROOT/'migrations'))
    with engine.connect() as c:
        config.attributes['connection']=c
        command.upgrade(config,'head')


def _synthetic_rows_only(engine):
    from sqlalchemy import text
    from .synthetic import SyntheticError
    with engine.connect() as c:
        if c.execute(text("SELECT count(*) FROM collection_run WHERE config_snapshot->>'run_mode' IS DISTINCT FROM 'synthetic'")).scalar_one():
            raise SyntheticError('SYNTHETIC_DATABASE_ROWS_REQUIRED')


def main(argv=None):
    engine=None
    try:
        args=_parser().parse_args(argv)
        # All dependency imports and connection creation are after parse/help.
        from .db import create_db_engine
        from .synthetic import (SyntheticError,fresh_output_directory,rehearse,
                                validate_disposable_engine,write_json)
        engine=create_db_engine(args.database_url)
        validate_disposable_engine(engine,disposable=args.disposable)
        if args.command=='rehearse':
            start=date.fromisoformat(args.start_date)
            if args.initialize:
                _initialize(engine)
            result=rehearse(engine,args.output,disposable=True,start_date=start,
                software_revision=args.software_revision)
            payload={'evidence_kind':'synthetic','output_dir':result['output_dir'],
                'planned_slots':result['summary']['planned_slots'],
                'attempted_slots':result['summary']['attempted_slots'],
                'assessment_status':'pending_human_review'}
        elif args.command=='report':
            from .reporting import run_report,batch_report,integrity_report
            _synthetic_rows_only(engine)
            with engine.connect() as c:
                report=(run_report(c,UUID(args.run_id)) if args.run_id else
                    batch_report(c,UUID(args.batch_id)) if args.batch_id else integrity_report(c))
            output=fresh_output_directory(args.output)
            write_json(output/'report.json',{'evidence_kind':'synthetic','report':report})
            payload={'evidence_kind':'synthetic','output_dir':str(output),'artifact':'report.json'}
        else:
            from .assessment import build_sample,export_assessment,pending_labels,summarize_assessment
            from .contracts import RunMode
            _synthetic_rows_only(engine)
            cutoff=datetime.fromisoformat(args.cutoff.replace('Z','+00:00'))
            if cutoff.tzinfo is None or cutoff.utcoffset() is None:
                raise _CliError('AWARE_CUTOFF_REQUIRED')
            with engine.connect() as c:
                sample=build_sample(c,cutoff=cutoff,seed=args.seed,per_app=args.per_app,run_mode=RunMode.SYNTHETIC)
            output=fresh_output_directory(args.output)
            export_assessment(sample,output/'private-assessment')
            write_json(output/'assessment-pending.json',{'evidence_kind':'synthetic',
                'assessment_status':'pending_human_review','summary':summarize_assessment(sample,pending_labels(sample))})
            payload={'evidence_kind':'synthetic','output_dir':str(output),'assessment_status':'pending_human_review'}
        print(json.dumps(payload,sort_keys=True))
        return 0
    except _CliError as exc:
        print(json.dumps({'evidence_kind':'synthetic','error':exc.code}))
        return 2
    except Exception as exc:
        allowed={'DISPOSABLE_OPT_IN_REQUIRED','PRIVATE_DISPOSABLE_DATABASE_REQUIRED',
            'DISPOSABLE_DATABASE_IDENTITY_MISMATCH','FRESH_PRIVATE_TMP_OUTPUT_REQUIRED',
            'SYNTHETIC_DATABASE_ROWS_REQUIRED','EXACT_MIGRATED_SEVEN_TABLES_REQUIRED',
            'EMPTY_DISPOSABLE_DATABASE_REQUIRED','INVALID_SYNTHETIC_PROTOCOL',
            'SYNTHETIC_INTEGRITY_FAILED',
            'SYNTHETIC_REHEARSAL_INFRASTRUCTURE_FAILURE'}
        code=getattr(exc,'code',None)
        print(json.dumps({'evidence_kind':'synthetic','error':code if code in allowed else 'OFFLINE_OPERATION_FAILED'}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__=='__main__':
    raise SystemExit(main())
