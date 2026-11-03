"""Synthetic SQL fixtures for PostgreSQL constraints, not reconciliation code."""
from datetime import datetime, timezone
from uuid import uuid4

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
TABLES = {
    'application', 'collection_target', 'collection_run', 'fetch_attempt',
    'review', 'review_version', 'review_observation',
}


def application(conn, source_id='000opaque-app'):
    return conn.execute("""INSERT INTO application
        (source, source_application_id, name, analytical_category)
        VALUES ('apple_app_store', %s, 'Synthetic app', 'education') RETURNING id""",
        (source_id,)).fetchone()[0]


def target(conn, app):
    return conn.execute("""INSERT INTO collection_target
        (application_id, storefront, sort_by) VALUES (%s, 'us', 'mostrecent') RETURNING id""",
        (app,)).fetchone()[0]


def run(conn, app, target_id, *, reference=None, running=False):
    run_id = uuid4()
    conn.execute("""INSERT INTO collection_run
        (id,target_id,application_id,batch_id,started_at,finished_at,
         execution_status,coverage_status,reference_run_id,stop_reason,config_snapshot)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'{}')""",
        (run_id,target_id,app,uuid4(),NOW,None if running else NOW,
         'running' if running else 'succeeded','pending' if running else 'baseline',
         reference,None if running else 'synthetic_fixture'))
    return run_id


def version(conn, review_id, app, run_id, *, number=1, version_id=None, body='synthetic', title=None):
    fields = ['review_id','application_id','version_number','body','rating',
              'content_hash','metadata_hash','first_observed_at','detecting_run_id','title']
    values = [review_id,app,number,body,5,b'a'*32,b'b'*32,NOW,run_id,title]
    if version_id is not None:
        fields.append('id')
        values.append(version_id)
    return conn.execute(f"INSERT INTO review_version ({','.join(fields)}) VALUES "
        f"({','.join(['%s']*len(fields))}) RETURNING id", values).fetchone()[0]


def review(conn, app, run_id, *, source_id='000opaque-review', body='synthetic', title=None):
    reserved = conn.execute("SELECT nextval(pg_get_serial_sequence('review_version','id'))").fetchone()[0]
    review_id = conn.execute("""INSERT INTO review
        (application_id,source_review_id,current_version_id,first_observed_at,last_observed_at)
        VALUES (%s,%s,%s,%s,%s) RETURNING id""",(app,source_id,reserved,NOW,NOW)).fetchone()[0]
    version(conn,review_id,app,run_id,version_id=reserved,body=body,title=title)
    return review_id,reserved


def observation(conn, app, run_id, review_id, version_id):
    conn.execute("""INSERT INTO review_observation
        (run_id,review_id,application_id,observed_version_id,first_observed_at,
         first_observed_page,first_observed_position,first_action)
        VALUES (%s,%s,%s,%s,%s,1,1,'new')""",(run_id,review_id,app,version_id,NOW))


def attempt(conn, run_id, *, request=1, page=1, committed=False, format='json'):
    return conn.execute("""INSERT INTO fetch_attempt
        (run_id,request_number,page_number,format,attempt_number,started_at,
         parsing_status,persistence_status,entry_count)
        VALUES (%s,%s,%s,%s,1,%s,%s,%s,%s) RETURNING id""",
        (run_id,request,page,format,NOW,'succeeded' if committed else 'pending',
         'committed' if committed else 'pending',1 if committed else None)).fetchone()[0]
