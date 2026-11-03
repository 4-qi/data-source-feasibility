"""Synthetic bytes -> parser -> normalizer -> committed PostgreSQL behavior."""
from contextlib import contextmanager
from datetime import timedelta
import json
from uuid import uuid4
from xml.sax.saxutils import escape

from sqlalchemy import text

from apple_ingestion_db_helpers import NOW, application, target
from feasibility.apple_ingestion.contracts import ConfigSnapshot, FeedFormat
from feasibility.apple_ingestion.parser import PARSER_VERSION, parse_feed


SOURCE_ID='000opaque/评论'


def json_feed(*, title='Cafe\u0301\r\n标题',body='完整正文🙂\r\n&amp;',rating=4,repeat=1):
    entry={key:{'label':value} for key,value in {
        'id':SOURCE_ID,'title':title,'content':body,'im:rating':str(rating),
        'im:version':'1.0','updated':'2026-11-03T04:00:00-08:00',
    }.items()}
    entry['author']={'name':{'label':'SYNTHETIC_AUTHOR_EXCLUDED'}}
    return json.dumps({'feed':{'entry':[entry]*repeat}},ensure_ascii=False).encode()


def xml_feed():
    fields={'id':SOURCE_ID,'title':'Café\n标题','content':'完整正文🙂\n&amp;',
            'im:rating':'4','im:version':'1.0','updated':'2026-11-03T12:00:00Z'}
    entries=''.join(f'<{key}>{escape(value)}</{key}>' for key,value in fields.items())
    return ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:im="http://itunes.apple.com/rss">'
            '<entry>'+entries+'</entry></feed>').encode()


def identity(engine):
    raw=engine.raw_connection()
    try:
        c=raw.driver_connection
        app=application(c,'synthetic')
        tid=target(c,app)
        c.commit()
        return app,tid
    finally:
        raw.close()


def new_run(engine,app,tid):
    from psycopg.types.json import Jsonb
    rid=uuid4()
    snapshot=ConfigSnapshot(application_id=app,source_application_id='synthetic',
        target_id=tid,software_revision='synthetic-integration',parser_version=PARSER_VERSION)
    with engine.begin() as c:
        c.execute(text('''INSERT INTO collection_run
            (id,target_id,application_id,batch_id,started_at,execution_status,
             coverage_status,config_snapshot)
            VALUES (:rid,:tid,:app,:batch,:now,'running','pending',:snapshot)'''),
            dict(rid=rid,tid=tid,app=app,batch=uuid4(),now=NOW,snapshot=Jsonb(snapshot.to_dict())))
    return rid


def parsed_attempt(engine,rid,page,payload,format,observed_at=NOW):
    parsed=parse_feed(payload,format)
    with engine.begin() as c:
        aid=c.execute(text('''INSERT INTO fetch_attempt
            (run_id,request_number,page_number,format,attempt_number,started_at,
             finished_at,http_status,parsing_status,persistence_status,entry_count)
            VALUES (:rid,:page,:page,:format,1,:now,:now,200,'succeeded','pending',:count)
            RETURNING id'''),dict(rid=rid,page=page,format=format.value,now=observed_at,count=parsed.entry_count)).scalar_one()
    return aid,parsed.records


@contextmanager
def writer(engine,app):
    from feasibility.apple_ingestion.reconcile import application_lock_key
    with engine.connect() as c:
        key=application_lock_key(app)
        c.execute(text('SELECT pg_advisory_lock(:key)'),dict(key=key))
        c.commit()
        try:
            yield c
        finally:
            c.rollback()
            c.execute(text('SELECT pg_advisory_unlock(:key)'),dict(key=key))
            c.commit()


def finish(engine,rid):
    with engine.begin() as c:
        c.execute(text("""UPDATE collection_run SET execution_status='succeeded',
            coverage_status='baseline',finished_at=:now,stop_reason='synthetic'
            WHERE id=:rid"""),dict(now=NOW+timedelta(seconds=1),rid=rid))


def test_json_atom_equivalence_then_metadata_change_and_historical_return(apple_database):
    from feasibility.apple_ingestion.reconcile import persist_page
    engine=apple_database
    app,tid=identity(engine)
    inputs=[(json_feed(),FeedFormat.JSON),(xml_feed(),FeedFormat.XML),
            (json_feed(rating=5),FeedFormat.JSON),(xml_feed(),FeedFormat.XML)]
    for payload,format in inputs:
        rid=new_run(engine,app,tid)
        aid,records=parsed_attempt(engine,rid,1,payload,format)
        with writer(engine,app) as c:
            persist_page(c,rid,aid,records,NOW)
        finish(engine,rid)
    with engine.connect() as c:
        versions=c.execute(text('SELECT version_number,title,body,rating FROM review_version ORDER BY version_number')).all()
        assert [row[0] for row in versions]==[1,2,3]
        assert [row[3] for row in versions]==[4,5,4]
        assert versions[0][1:3]==('Cafe\u0301\r\n标题','完整正文🙂\r\n&amp;')
        assert versions[2][1:3]==('Café\n标题','完整正文🙂\n&amp;')
        assert c.execute(text('SELECT source_review_id FROM review')).scalar_one()==SOURCE_ID
        assert c.execute(text('SELECT count(*) FROM review_observation')).scalar_one()==4
        assert c.execute(text('SELECT v.version_number FROM review r JOIN review_version v ON r.current_version_id=v.id')).scalar_one()==3
        assert c.execute(text("SELECT count(*) FROM fetch_attempt WHERE persistence_status='committed'")).scalar_one()==4


def test_parsed_duplicates_conflicts_and_replay_keep_first_committed_snapshot(apple_database):
    from feasibility.apple_ingestion.reconcile import persist_page
    engine=apple_database
    app,tid=identity(engine)
    rid=new_run(engine,app,tid)
    first,records=parsed_attempt(engine,rid,1,json_feed(repeat=2),FeedFormat.JSON)
    conflicting='SYNTHETIC_ALTERNATE_BODY_MUST_NOT_ENTER_DIAGNOSTICS'
    second,alternates=parsed_attempt(engine,rid,2,json_feed(body=conflicting),FeedFormat.JSON,
                                   observed_at=NOW+timedelta(seconds=1))
    with writer(engine,app) as c:
        persist_page(c,rid,first,records,NOW)
        persist_page(c,rid,second,alternates,NOW+timedelta(seconds=1))
        persist_page(c,rid,first,records,NOW+timedelta(seconds=2))
        persist_page(c,rid,second,alternates,NOW+timedelta(seconds=2))
    with engine.connect() as c:
        assert c.execute(text('SELECT occurrence_count,conflict_count FROM review_observation')).one()==(3,1)
        assert c.execute(text('SELECT count(*) FROM review_version')).scalar_one()==1
        assert c.execute(text('SELECT body FROM review_version')).scalar_one()=='完整正文🙂\r\n&amp;'
        assert c.execute(text('SELECT last_observed_at FROM review')).scalar_one()==NOW+timedelta(seconds=1)
        diagnostics=c.execute(text('SELECT anomalies FROM collection_run')).scalar_one()
        assert diagnostics
        saved=json.dumps(diagnostics,ensure_ascii=False)
        saved+=json.dumps(c.execute(text('SELECT anomalies,error_codes FROM fetch_attempt')).all(),default=str,ensure_ascii=False)
        assert conflicting not in saved and 'SYNTHETIC_AUTHOR_EXCLUDED' not in saved
