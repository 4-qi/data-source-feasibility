"""Assessment mechanics only; all submitted labels are synthetic test fixtures.

No test represents an actual independent human quality assessment.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import insert, select, update

from feasibility.apple_ingestion.assessment import (
    AssessmentError, LABEL_SCHEMA, QUERY_VERSION, RUBRIC_VERSION, SAMPLE_SCHEMA,
    build_sample, compare_double_review, export_assessment, pending_labels, summarize_assessment,
)
from feasibility.apple_ingestion.contracts import ConfigSnapshot, ReviewRecord, RunMode
from feasibility.apple_ingestion.models import Application, CollectionRun, CollectionTarget, FetchAttempt
from feasibility.apple_ingestion.parser import PARSER_VERSION
from feasibility.apple_ingestion.reconcile import persist_page
from feasibility.apple_ingestion.recovery import application_session
from feasibility.apple_ingestion.seed import load_seed_manifest, seed_defaults

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'results/mainstream/app_sample_manifest.json'
NOW = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
A, R, T, F = (model.__table__ for model in (Application, CollectionRun, CollectionTarget, FetchAttempt))


def ident(sample):
    data = {key: value for key, value in sample.items() if key != 'manifest_id'}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@pytest.fixture
def sample():
    apps, records = [], []
    for number, app in enumerate(load_seed_manifest(MANIFEST), 1):
        apps.append(dict(application_id=number, source_application_id=app.source_application_id,
            name=app.name, analytical_category=app.analytical_category, eligible=1, selected=1,
            shortfall=9, exclusion_counts={}))
        records.append(dict(application_id=number, source_application_id=app.source_application_id,
            analytical_category=app.analytical_category, review_id=number, version_id=number*10,
            version_number=1, observed_run_id=str(uuid4()), title='PRIVATE_TITLE <script>bad()</script>',
            body='PRIVATE_BODY\r\n' + '完整正文 &amp; 😀 ' * 5000 + 'FULL_TAIL'))
    result = dict(schema_version=SAMPLE_SCHEMA, query_version=QUERY_VERSION, rubric_version=RUBRIC_VERSION,
        assessment_type='pending_human', run_mode='synthetic', evidence_kind='synthetic', cutoff='2026-11-03T12:00:00.000000Z',
        sampling_seed='synthetic-seed', per_app=10, apps=apps, records=records,
        totals=dict(eligible=8, selected=8, assessed=0, unassessed=8, usefulness_rate=None, shortfall=72),
        double_review=dict(status='optional_pending_human', requested_per_app=2, target=16,
            selected_review_ids=list(range(1, 9)), selected=8, shortfall=8, agreement_rate=None))
    result['manifest_id'] = ident(result)
    return result


def submitted(sample, labels=('U2', 'U0'), reviewer='SYNTHETIC_REVIEWER_A'):
    responses = pending_labels(sample)
    for row, label in zip(responses['records'], labels):
        row.update(label=label, reason='SYNTHETIC_TEST: concrete fixture experience',
            reviewer_id=reviewer, language='en', full_text_read=True,
            assessed_at='2026-11-04T12:00:00+00:00', assessment_type='synthetic_test',
            provenance='synthetic_test', ai_assistance=False, unassessed_reason=None)
    if labels:
        responses['assessment_type'] = 'synthetic_test'
    return responses


def seed_frame(engine):
    with engine.begin() as connection:
        result = seed_defaults(connection, MANIFEST)
    return [(app, target, item.source_application_id) for app, target, item in zip(
        result.application_ids, result.target_ids, load_seed_manifest(MANIFEST))]


def observed_run(engine, frame, records, *, at=NOW, mode=RunMode.SYNTHETIC,
                 execution='succeeded', finished_at=None):
    app, target, source_id = frame
    run_id = uuid4()
    snapshot = ConfigSnapshot(application_id=app, target_id=target, source_application_id=source_id,
        software_revision='synthetic-assessment-test', parser_version=PARSER_VERSION, run_mode=mode,
        access_decision_ref='synthetic-live-mode-contract-fixture' if mode is RunMode.LIVE else None,
        retention_policy_ref='synthetic-live-mode-contract-fixture' if mode is RunMode.LIVE else None)
    with application_session(engine, app) as owner:
        with owner.connection.begin():
            owner.connection.execute(insert(R).values(id=run_id, application_id=app, target_id=target,
                batch_id=uuid4(), started_at=at, execution_status='running', coverage_status='pending',
                config_snapshot=snapshot.to_dict()))
            attempt = owner.connection.scalar(insert(F).values(run_id=run_id, request_number=1,
                page_number=1, format='json', attempt_number=1, started_at=at,
                finished_at=at+timedelta(seconds=1), parsing_status='succeeded', persistence_status='pending',
                entry_count=len(records), http_status=200).returning(F.c.id))
        persist_page(owner.connection, run_id, attempt, records, at+timedelta(seconds=1))
        if execution != 'running':
            with owner.connection.begin():
                owner.connection.execute(update(R).where(R.c.id == run_id).values(execution_status=execution,
                    coverage_status='baseline' if execution == 'succeeded' else 'indeterminate',
                    finished_at=finished_at or at+timedelta(seconds=2), stop_reason='synthetic_fixture'))
    return run_id


def test_pending_means_no_assessed_denominator_and_no_actual_human_claim(sample):
    pending = pending_labels(sample)
    assert all(row['label'] is None and row['assessment_type'] == 'pending_human' for row in pending['records'])
    assert all(row['reviewer_id'] is row['assessed_at'] is row['language'] is None for row in pending['records'])
    summary = summarize_assessment(sample, pending)
    assert summary['overall'] == dict(eligible=8, selected=8, assessed=0, unassessed=8, shortfall=72,
        label_counts={'U3': 0, 'U2': 0, 'U1': 0, 'U0': 0}, useful=0, usefulness_rate=None,
        human_assessed=0, synthetic_test_assessed=0)
    assert summary['double_review']['agreement_rate'] is None
    assert summary['sentiment_assessment'] == 'NOT_PERFORMED'
    assert summary['evidence_kind'] == pending['evidence_kind'] == sample['run_mode']


def test_fixture_usefulness_counts_unique_reviews_without_claiming_human_results(sample):
    summary = summarize_assessment(sample, submitted(sample))
    assert summary['assessment_type'] == 'synthetic_test'
    assert summary['overall']['assessed'] == 2 and summary['overall']['usefulness_rate'] == .5
    assert summary['overall']['human_assessed'] == 0 and summary['overall']['synthetic_test_assessed'] == 2
    assert summary['overall']['unassessed'] == 6
    assert 'PRIVATE' not in json.dumps(summary) and 'SYNTHETIC_REVIEWER' not in json.dumps(summary)
    assert summary['apps'][0]['usefulness_rate'] == 1
    assert summary['categories']['productivity']['usefulness_rate'] == .5
    partial = submitted(sample)
    partial['records'] = partial['records'][:2]
    assert summarize_assessment(sample, partial)['unassessed_reasons'] == {'MISSING_RESPONSE': 6}


def test_language_and_unread_limitations_remain_unassessed_not_u0(sample):
    responses = pending_labels(sample)
    responses['records'][0]['unassessed_reason'] = 'LANGUAGE_UNAVAILABLE'
    responses['records'][0]['language'] = 'unassessed language'
    responses['records'][1]['unassessed_reason'] = 'FULL_TEXT_NOT_READ'
    summary = summarize_assessment(sample, responses)
    assert summary['overall']['label_counts']['U0'] == 0
    assert summary['overall']['usefulness_rate'] is None
    assert summary['unassessed_reasons']['LANGUAGE_UNAVAILABLE'] == 1


@pytest.mark.parametrize('field,value', [
    ('review_id', 99999), ('review_id', True), ('version_id', 99999), ('version_id', True),
    ('manifest_id', 'foreign'), ('rubric_version', 'foreign'), ('schema_version', 'foreign'),
    ('reviewer_id', None), ('language', None), ('reason', None), ('full_text_read', False),
    ('full_text_read', 1), ('assessed_at', None), ('assessed_at', '2026-11-03'),
    ('label', 'U4'), ('label', 2), ('assessment_type', 'AI'), ('provenance', 'independent_human'),
    ('ai_assistance', True), ('unassessed_reason', 'PENDING_HUMAN'),
])
def test_labels_reject_membership_version_metadata_and_provenance_failures(sample, field, value):
    labels = submitted(sample)
    labels['records'][0][field] = value
    with pytest.raises(AssessmentError) as caught:
        summarize_assessment(sample, labels)
    assert 'PRIVATE' not in str(caught.value)


def test_duplicate_labels_wrong_envelope_and_ai_human_claim_rejected(sample):
    labels = submitted(sample)
    labels['records'].append(deepcopy(labels['records'][0]))
    with pytest.raises(AssessmentError, match='DUPLICATE_REVIEW_LABEL'):
        summarize_assessment(sample, labels)
    labels = submitted(sample)
    labels['records'][0].update(assessment_type='human', provenance='human', ai_assistance=True)
    with pytest.raises(AssessmentError, match='HUMAN_PROVENANCE_REQUIRED'):
        summarize_assessment(sample, labels)
    labels = submitted(sample)
    labels['run_mode'] = 'live'
    with pytest.raises(AssessmentError, match='LABEL_MANIFEST_MISMATCH'):
        summarize_assessment(sample, labels)
    labels = pending_labels(sample)
    labels['records'][0]['unassessed_reason'] = []
    with pytest.raises(AssessmentError):
        summarize_assessment(sample, labels)


def test_optional_double_review_selection_never_manufactures_agreement(sample):
    empty = pending_labels(sample)
    assert compare_double_review(sample, empty, empty)['agreement_rate'] is None
    first = submitted(sample, ('U2', 'U1'))
    second = submitted(sample, ('U2', 'U3'), reviewer='SYNTHETIC_REVIEWER_B')
    result = compare_double_review(sample, first, second)
    assert result['selected'] == 8 and result['assessed_pairs'] == 2
    assert result['human_pairs_assessed'] == 0 and result['agreement_rate'] is None
    assert result['assessment_type'] == 'synthetic_test' and result['disagreements'] == [2]
    with pytest.raises(AssessmentError, match='INDEPENDENT_SECOND_REVIEWER_REQUIRED'):
        compare_double_review(sample, first, first)


def test_private_export_fulltext_ratings_hidden_escaped_and_nooverwrite(sample, tmp_path):
    output = tmp_path / 'private-assessment'
    paths = export_assessment(sample, output)
    assert output.stat().st_mode & 0o777 == 0o700
    assert set(paths) == {'manifest', 'reading_material', 'responses', 'rubric'}
    for value in paths.values():
        assert Path(value).is_absolute() and Path(value).stat().st_mode & 0o777 == 0o600
    manifest = json.loads(Path(paths['manifest']).read_text())
    assert manifest == sample and manifest['records'][0]['body'].endswith('FULL_TAIL')
    reading = Path(paths['reading_material']).read_text()
    assert 'FULL_TAIL' in reading and '&lt;script&gt;' in reading and '<script>' not in reading
    assert 'rating' not in reading.lower() and 'star' not in reading.lower()
    assert 'rating' not in manifest['records'][0]
    for key in ('manifest', 'responses', 'rubric'):
        assert json.loads(Path(paths[key]).read_text())['evidence_kind'] == sample['run_mode']
    responses = json.loads(Path(paths['responses']).read_text())
    assert summarize_assessment(sample, responses)['overall']['usefulness_rate'] is None
    with pytest.raises(AssessmentError, match='PRIVATE_EXPORT_FAILED'):
        export_assessment(sample, output)
    assert json.loads(Path(paths['manifest']).read_text()) == sample


def test_private_export_refuses_repository_symlink_and_storage_failure(sample, tmp_path, monkeypatch):
    with pytest.raises(AssessmentError, match='PRIVATE_EXPORT_FAILED'):
        export_assessment(sample, ROOT / 'private-assessment')
    link = tmp_path / 'linked'
    link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AssessmentError):
        export_assessment(sample, link / 'export')
    def fail(*_):
        raise OSError('PRIVATE_STORAGE_ERROR')
    monkeypatch.setattr(os, 'fsync', fail)
    with pytest.raises(AssessmentError) as caught:
        export_assessment(sample, tmp_path / 'failed-export')
    assert 'PRIVATE' not in str(caught.value).replace('PRIVATE_EXPORT_FAILED', '')
    assert not (tmp_path / 'failed-export').exists()


def test_sample_manifest_tampering_is_detected(sample):
    sample['records'][0]['body'] = 'tampered'
    with pytest.raises(AssessmentError, match='INVALID_ASSESSMENT_MANIFEST'):
        pending_labels(sample)


def test_postgresql_balanced_sample_reproducible_hash_order_and_version_updates(apple_database):
    frame = seed_frame(apple_database)
    for number, item in enumerate(frame):
        observed_run(apple_database, item, [ReviewRecord(f'opaque-{index}', f'title-{index}',
            '正文' * (index+1), index % 5 + 1) for index in range(12)])
    with apple_database.connect() as connection:
        before = build_sample(connection, cutoff=NOW+timedelta(minutes=1), seed='fixed-seed')
        assert before == build_sample(connection, cutoff=NOW+timedelta(minutes=1), seed='fixed-seed')
    assert before['totals'] == dict(eligible=96, selected=80, assessed=0, unassessed=80, usefulness_rate=None, shortfall=0)
    assert len({row['review_id'] for row in before['records']}) == 80
    assert before['double_review']['selected'] == 16
    for app in before['apps']:
        assert app['eligible'] == 12 and app['selected'] == 10 and app['shortfall'] == 0
        with apple_database.connect() as connection:
            from feasibility.apple_ingestion.models import Review
            identities = connection.scalars(select(Review.id).where(Review.application_id == app['application_id'])).all()
        expected = sorted(identities, key=lambda identity: (hashlib.sha256(json.dumps(
            ['fixed-seed', app['application_id'], identity], separators=(',', ':'), ensure_ascii=False).encode()).digest(), identity))[:10]
        assert [row['review_id'] for row in before['records'] if row['application_id'] == app['application_id']] == expected
    observed_run(apple_database, frame[0], [ReviewRecord(f'opaque-{index}', None,
        'changed FULL_TAIL' * (12-index), 5-index%5) for index in range(12)], at=NOW+timedelta(minutes=2))
    with apple_database.connect() as connection:
        after = build_sample(connection, cutoff=NOW+timedelta(minutes=3), seed='fixed-seed')
        frozen = build_sample(connection, cutoff=NOW+timedelta(minutes=1), seed='fixed-seed')
    assert frozen == before
    assert [row['review_id'] for row in after['records']] == [row['review_id'] for row in before['records']]
    assert after['manifest_id'] != before['manifest_id']


def test_postgresql_cutoff_conflicts_clean_confirmation_and_running_versions(apple_database):
    frame = seed_frame(apple_database)
    observed_run(apple_database, frame[0], [
        ReviewRecord('clean', None, 'A', 1, source_updated_at=NOW+timedelta(days=900)),
        ReviewRecord('conflicted-only', None, 'A', 1), ReviewRecord('conflicted-only', None, 'B', 1),
        ReviewRecord('confirmed-later', None, 'A', 1), ReviewRecord('confirmed-later', None, 'B', 1),
    ], execution='partial')
    observed_run(apple_database, frame[0], [ReviewRecord('clean', None, 'C', 2),
        ReviewRecord('confirmed-later', None, 'A', 1)], at=NOW+timedelta(minutes=2))
    observed_run(apple_database, frame[0], [ReviewRecord('clean', None, 'RUNNING_FUTURE', 5)],
                 at=NOW+timedelta(minutes=4), execution='running')
    with apple_database.connect() as connection:
        old = build_sample(connection, cutoff=NOW+timedelta(minutes=1), seed='cutoff')
        later = build_sample(connection, cutoff=NOW+timedelta(minutes=5), seed='cutoff')
    assert old['totals']['eligible'] == 1 and old['records'][0]['body'] == 'A'
    assert later['totals']['eligible'] == 2
    assert {row['body'] for row in later['records']} == {'A', 'C'}
    assert later['apps'][0]['exclusion_counts']['CONFLICTED_OBSERVATION'] == 2
    assert later['apps'][0]['exclusion_counts']['RUN_NOT_FINISHED_BY_CUTOFF'] == 1
    assert later['totals']['shortfall'] == 78  # no cross-app replacement


def test_postgresql_modes_never_mix_and_postcutoff_finish_is_excluded(apple_database):
    frame = seed_frame(apple_database)
    observed_run(apple_database, frame[0], [ReviewRecord('synthetic', None, 'SYNTHETIC', 2)])
    observed_run(apple_database, frame[1], [ReviewRecord('live-mode-fixture', None, 'MODE_TEST_ONLY', 2)], mode=RunMode.LIVE)
    observed_run(apple_database, frame[2], [ReviewRecord('mixed-origin', None, 'SYNTHETIC', 2)])
    observed_run(apple_database, frame[2], [ReviewRecord('mixed-origin', None, 'SYNTHETIC', 2)],
                 mode=RunMode.LIVE, at=NOW+timedelta(minutes=2))
    observed_run(apple_database, frame[3], [ReviewRecord('late-finish', None, 'LATE', 2)],
                 finished_at=NOW+timedelta(minutes=10))
    with apple_database.connect() as connection:
        synthetic = build_sample(connection, cutoff=NOW+timedelta(minutes=5), seed='modes')
        live_fixture = build_sample(connection, cutoff=NOW+timedelta(minutes=5), seed='modes', run_mode=RunMode.LIVE)
    assert live_fixture['evidence_kind'] == 'live'
    assert pending_labels(live_fixture)['evidence_kind'] == 'live'
    assert summarize_assessment(live_fixture, pending_labels(live_fixture))['evidence_kind'] == 'live'
    assert synthetic['totals']['eligible'] == 2
    assert live_fixture['totals']['eligible'] == 1
    assert live_fixture['apps'][2]['exclusion_counts']['VERSION_ORIGIN_NOT_ELIGIBLE'] == 1
    assert 'LATE' not in {row['body'] for row in synthetic['records']}
    assert summarize_assessment(live_fixture, pending_labels(live_fixture))['overall']['assessed'] == 0


def test_postgresql_sampling_validates_cutoff_frame_and_configuration(apple_database):
    with apple_database.connect() as connection:
        with pytest.raises(AssessmentError, match='EIGHT_APP_FRAME_REQUIRED'):
            build_sample(connection, cutoff=NOW, seed='seed')
    frame = seed_frame(apple_database)
    with apple_database.connect() as connection:
        for kwargs in (dict(cutoff=NOW.replace(tzinfo=None), seed='seed'), dict(cutoff=NOW, seed=''),
                       dict(cutoff=NOW, seed='seed', per_app=True), dict(cutoff=NOW, seed='seed', run_mode='unknown')):
            with pytest.raises(AssessmentError):
                build_sample(connection, **kwargs)
    with apple_database.begin() as connection:
        connection.execute(update(A).where(A.c.id == frame[0][0]).values(analytical_category='education'))
    with apple_database.connect() as connection:
        with pytest.raises(AssessmentError, match='EIGHT_APP_FRAME_REQUIRED'):
            build_sample(connection, cutoff=NOW, seed='seed')


def test_evidence_kind_must_match_mode_and_label_manifest(sample):
    labels = pending_labels(sample)
    labels['evidence_kind'] = 'live'
    with pytest.raises(AssessmentError, match='LABEL_MANIFEST_MISMATCH'):
        summarize_assessment(sample, labels)
    sample['evidence_kind'] = 'live'
    sample['manifest_id'] = ident(sample)
    with pytest.raises(AssessmentError, match='INVALID_ASSESSMENT_MANIFEST'):
        pending_labels(sample)
