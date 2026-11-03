"""Deterministic synthetic calendar-day rehearsal; no real HTTP implementation.

The database must be explicitly disposable, local, migrated and empty. Fake
clock advancement is not seven days of live evidence. Reporting and assessment
remain separate components; this module only supplies scenarios and orchestrates.
"""
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
from uuid import UUID, uuid5
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from .contracts import ConfigSnapshot, IngestionConfig, RunMode
from .controller import Controller
from .models import Base
from .normalizer import HASH_CONTRACT_VERSION
from .parser import PARSER_VERSION
from .recovery import DiagnosticSpool
from .seed import load_seed_manifest, seed_defaults
from .transport import BoundedTransport

ROOT=Path(__file__).resolve().parents[3]
PROTOCOL_VERSION='apple-synthetic-seven-days/1'
NAMESPACE=UUID('8ec080fa-f51e-43d7-b293-631ebca0f8bf')
DEFAULT_START=date(2026,10,29)
LOCAL_ZONE=ZoneInfo('America/Los_Angeles')


class SyntheticError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


def validate_disposable_engine(engine,*,disposable=False):
    """Check explicit opt-in and private /tmp Unix socket before connecting."""
    if disposable is not True:
        raise SyntheticError('DISPOSABLE_OPT_IN_REQUIRED')
    url=engine.url
    host=url.query.get('host')
    if (url.drivername!='postgresql+psycopg' or not url.database
            or not re.fullmatch(r'apple_phase_a_[A-Za-z0-9_]+',url.database)
            or url.host is not None or type(host) is not str
            or not Path(host).is_absolute() or not Path(host).is_relative_to('/tmp')
            or Path(host).resolve()!=Path(host)
            or '..' in Path(host).parts or ',' in host
            or set(url.query)-{'host','port'} or engine.echo or not engine.hide_parameters):
        raise SyntheticError('PRIVATE_DISPOSABLE_DATABASE_REQUIRED')
    with engine.connect() as c:
        if c.execute(text('SELECT current_database()')).scalar_one()!=url.database:
            raise SyntheticError('DISPOSABLE_DATABASE_IDENTITY_MISMATCH')


def fresh_output_directory(path):
    """Reserve an entirely new 0700 output tree under /tmp, outside any Git tree."""
    path=Path(path)
    if (not path.is_absolute() or '..' in path.parts or not path.is_relative_to('/tmp')
            or path==Path('/tmp') or path.exists() or path.is_symlink()
            or not path.parent.is_dir() or path.parent.resolve()!=path.parent
            or any((parent/'.git').is_file() or (parent/'.git/HEAD').is_file() for parent in path.parents)):
        raise SyntheticError('FRESH_PRIVATE_TMP_OUTPUT_REQUIRED')
    path.mkdir(mode=0o700)
    return path


def write_json(path,value):
    """Exclusive JSON write; every top-level artifact explicitly names its kind."""
    if type(value) is not dict or value.get('evidence_kind')!='synthetic':
        raise SyntheticError('SYNTHETIC_ARTIFACT_MARKER_REQUIRED')
    with Path(path).open('x',encoding='utf-8') as handle:
        handle.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
    Path(path).chmod(0o600)


class SimulatedClock:
    def __init__(self,start):
        self.origin=start.astimezone(timezone.utc)
        self.elapsed=0.0

    def now(self):
        return self.origin+timedelta(seconds=self.elapsed)

    def monotonic(self):
        return self.elapsed

    def sleep(self,seconds):
        self.elapsed+=seconds

    def advance_to(self,instant):
        seconds=(instant.astimezone(timezone.utc)-self.origin).total_seconds()
        if seconds<self.elapsed:
            raise SyntheticError('SIMULATED_TIME_CANNOT_REWIND')
        self.elapsed=seconds


def _window(day):
    ids=list(range(100))
    for offset in range(1,day+1):
        ids=list(range(100+10*(offset-1),100+10*offset))+ids[:90]
    return ids


def _record(app_index,identity,day,*,conflicting=False):
    body=f'SYNTHETIC_BODY app={app_index} record={identity}: invented review. 正文🙂 &amp;\r\n'
    if app_index==0 and identity==0:
        body+='snapshot B' if day==1 else 'snapshot A'
    if app_index==7:
        body+='Full synthetic Unicode text is retained. 完整文字🙂\r\n'*600
    if conflicting:
        body='SYNTHETIC_DISPUTED_ALTERNATE_DO_NOT_EXPORT'
    return {'id':f'synthetic:{app_index}:{identity:04d}',
        'title':f'SYNTHETIC_TITLE {identity}','content':body,
        'im:rating':'5' if app_index==0 and identity==1 and day>=2 else '4',
        'im:version':'2.0' if app_index==1 and identity==0 and day>=3 else '1.0',
        # Keep source timestamp fixed except deliberate metadata changes.
        'updated':'2026-10-29T16:00:00Z'}


def scenario_response(app_index,day,page,format):
    """Return (HTTP status, invented bytes), never a URL or request operation."""
    if app_index==4 and day==1 and page==2:
        return 503,b''
    if app_index==4 and day==3 and page==1:
        return 200,b'{"feed":{"entry":[{"im:rating":{"label":"4"}}]}}'
    empty=(app_index==3 and day==2 and page==1) or (app_index==7 and day==4)
    missing=app_index==3 and day==1 and page==1 and format=='json'
    if missing:
        return 200,b'{"feed":{}}'
    if empty:
        return (200,b'{"feed":{"entry":[]}}') if format=='json' else (200,b'<feed xmlns="http://www.w3.org/2005/Atom"/>')
    if app_index==0:
        ids=_window(day)[(page-1)*20:page*20]
    elif app_index==1:
        ids=[list(range(3)),list(range(3,6)),list(range(6,8)),list(range(8,10)),list(range(10,12))][page-1]
    elif app_index==2:
        window=list(range(5))+list(range(1000+day*100,1045+day*100))
        ids=window[(page-1)*10:page*10]
    elif app_index==6 and day:
        ids=list(range(20,120))[(page-1)*20:page*20]
    elif app_index==5 and day==2 and page==2:
        ids=list(range(20))
    else:
        ids=list(range(100))[(page-1)*20:page*20]
    records=[_record(app_index,identity,day) for identity in ids]
    if app_index==5 and day==1 and page==1:
        records.append(_record(app_index,0,day))
    if app_index==5 and day==1 and page==2:
        records.append(_record(app_index,0,day,conflicting=True))
    if format=='json':
        entries=[{key:{'label':value} for key,value in record.items()} for record in records]
        return 200,json.dumps({'feed':{'entry':entries}},ensure_ascii=False).encode()
    entries=''.join('<entry>'+''.join(f'<{key}>{escape(value)}</{key}>' for key,value in record.items())+'</entry>' for record in records)
    return 200,('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">'+entries+'</feed>').encode()


class _Response:
    def __init__(self,status,body):
        self.status_code,self._body=status,body

    def __enter__(self):
        return self

    def __exit__(self,*args):
        return False

    def iter_content(self,chunk_size):
        for offset in range(0,len(self._body),chunk_size):
            yield self._body[offset:offset+chunk_size]


class ScenarioSession:
    """Injected get() returns fixtures; no requests.Session or socket exists."""
    def __init__(self,source_ids,clock):
        self.source_ids=tuple(source_ids)
        self.clock=clock
        self.day=0
        self.calls=[]

    def get(self,url,**kwargs):
        match=re.fullmatch(r'https://itunes\.apple\.com/us/rss/customerreviews/page=([0-9]+)/id=([0-9]+)/sortby=mostrecent/(json|xml)',url)
        if match is None or match[2] not in self.source_ids:
            raise SyntheticError('UNEXPECTED_SYNTHETIC_REQUEST')
        page,source,format=int(match[1]),match[2],match[3]
        self.calls.append({'day':self.day+1,'application_index':self.source_ids.index(source),
            'page':page,'format':format,'monotonic_seconds':self.clock.monotonic()})
        status,body=scenario_response(self.source_ids.index(source),self.day,page,format)
        return _Response(status,body)


def _assert_empty(connection):
    existing=set(connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'")).scalars())
    if existing!=set(Base.metadata.tables)|{'alembic_version'}:
        raise SyntheticError('EXACT_MIGRATED_SEVEN_TABLES_REQUIRED')
    for table in Base.metadata.tables.values():
        if connection.execute(select(table).limit(1)).first() is not None:
            raise SyntheticError('EMPTY_DISPOSABLE_DATABASE_REQUIRED')


def rehearse(engine,output_dir,*,disposable=False,start_date=DEFAULT_START,
             software_revision='synthetic-uncommitted-phase-d'):
    """Run seven local calendar days, 56 planned slots, seven distinct batches."""
    validate_disposable_engine(engine,disposable=disposable)
    if (type(start_date) is not date or type(software_revision) is not str
            or not re.fullmatch(r'[A-Za-z0-9._+:/-]{1,128}',software_revision)):
        raise SyntheticError('INVALID_SYNTHETIC_PROTOCOL')
    manifest=ROOT/'results/mainstream/app_sample_manifest.json'
    records=load_seed_manifest(manifest)
    with engine.begin() as c:
        _assert_empty(c)
    output=fresh_output_directory(output_dir)
    safe=output/'safe'
    safe.mkdir(mode=0o700)
    start=datetime.combine(start_date,time(9),LOCAL_ZONE)
    clock=SimulatedClock(start)
    config=IngestionConfig()
    with engine.begin() as c:
        seeded=seed_defaults(c,manifest)
    snapshots=tuple(ConfigSnapshot(application_id=app,target_id=tid,
        source_application_id=record.source_application_id,software_revision=software_revision,
        parser_version=PARSER_VERSION,config=config) for app,tid,record in
        zip(seeded.application_ids,seeded.target_ids,records))
    session=ScenarioSession([record.source_application_id for record in records],clock)
    transport=BoundedTransport(session,clock=clock.monotonic,sleep=clock.sleep)
    controller=Controller(engine,transport,DiagnosticSpool(output/'diagnostics.jsonl'),
        now=clock.now,monotonic=clock.monotonic)
    # Imports are late so --help/import/scenario generation never opens reports,
    # assessment files or a database as a side effect.
    from .reporting import batch_report,integrity_report
    from .assessment import build_sample,export_assessment,pending_labels,summarize_assessment
    batches=[]
    outcomes=[]
    for day in range(7):
        local_date=start_date+timedelta(days=day)
        clock.advance_to(datetime.combine(local_date,time(9),LOCAL_ZONE))
        session.day=day
        batch_id=uuid5(NAMESPACE,f'{PROTOCOL_VERSION}:{start_date.isoformat()}:{day+1}')
        results=controller.run_batch(snapshots,batch_id)
        if any(result.recovery_required or not result.finalized for result in results):
            raise SyntheticError('SYNTHETIC_REHEARSAL_INFRASTRUCTURE_FAILURE')
        outcomes.extend(results)
        with engine.connect() as c:
            report=batch_report(c,batch_id,expected_target_ids=seeded.target_ids,outcomes=results)
        artifact={'evidence_kind':'synthetic','protocol_version':PROTOCOL_VERSION,
            'day':day+1,'simulated_local_date':local_date.isoformat(),
            'timezone':'America/Los_Angeles','batch_id':str(batch_id),'report':report}
        write_json(safe/f'day-{day+1:02d}.json',artifact)
        batches.append({'day':day+1,'local_date':local_date.isoformat(),'batch_id':str(batch_id),
            'artifact':f'safe/day-{day+1:02d}.json'})
    with engine.connect() as c:
        integrity=integrity_report(c)
        sample=build_sample(c,cutoff=clock.now(),seed='synthetic-phase-d-assessment-v1',
            per_app=10,run_mode=RunMode.SYNTHETIC)
        assessment_summary=summarize_assessment(sample,pending_labels(sample))
        pg_version=c.execute(text("SELECT current_setting('server_version')")).scalar_one()
    export_assessment(sample,output/'private-assessment')
    write_json(safe/'integrity.json',{'evidence_kind':'synthetic','integrity':integrity})
    write_json(safe/'assessment-pending.json',{'evidence_kind':'synthetic',
        'assessment_status':'pending_human_review','summary':assessment_summary})
    if not integrity['ok']:
        raise SyntheticError('SYNTHETIC_INTEGRITY_FAILED')
    statuses={status:sum(result.execution_status==status for result in outcomes)
        for status in ('succeeded','partial','failed','interrupted')}
    protocol={'evidence_kind':'synthetic','protocol_version':PROTOCOL_VERSION,
        'simulated_calendar_days':7,'timezone':'America/Los_Angeles','daily_local_time':'09:00:00',
        'planned_slots':56,'planned_batches':7,'extra_diagnostic_runs':0,
        'start_date':start_date.isoformat(),'config':config.to_dict(),
        'software_revision':software_revision,'parser_version':PARSER_VERSION,
        'hash_contract_version':HASH_CONTRACT_VERSION,
        'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'scenario_cases':['new_ids','unchanged','metadata_change','body_A_B_A','same_page_duplicate',
            'intra_run_conflict','json_missing_xml_fallback','empty_xml','low_volume','low_overlap',
            'partial_http_failure','failed_parse','absence_is_not_deletion','long_unicode_fulltext'],
        'limitations':['Invented fixtures; no live days or real HTTP.',
            'No human labels are generated; usefulness and source continuity are unassessed.',
            'Scenario inputs are deterministic; controller run UUIDs identify this execution.']}
    write_json(safe/'protocol.json',protocol)
    summary={'evidence_kind':'synthetic','protocol_version':PROTOCOL_VERSION,
        'planned_slots':56,'attempted_slots':sum(result.run_persisted is True for result in outcomes),
        'missing_slots':sum(result.skipped for result in outcomes),'execution_counts':statuses,
        'batches':batches,'requests':len(session.calls),
        'committed_pages':sum(result.committed_pages for result in outcomes),
        'assessment_status':'pending_human_review','safe_directory':'safe',
        'integrity_ok':integrity['ok'],
        'private_assessment_directory':'private-assessment',
        'software':{'revision':software_revision,'python':platform.python_version(),
            'postgresql':pg_version,'source_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(Path(__file__).parent.glob('*.py'))}}}
    write_json(output/'summary.json',summary)
    checksums={str(path.relative_to(output)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.rglob('*')) if path.is_file()}
    write_json(output/'checksums.json',{'evidence_kind':'synthetic','algorithm':'sha256','files':checksums})
    return {'evidence_kind':'synthetic','summary':summary,'output_dir':str(output)}


__all__=['PROTOCOL_VERSION','DEFAULT_START','SyntheticError','SimulatedClock',
    'scenario_response','ScenarioSession','validate_disposable_engine',
    'fresh_output_directory','write_json','rehearse']
