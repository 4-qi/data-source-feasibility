from collections import Counter
from .quality import screen, counts, language_flag
from .http import utcnow
import hashlib
import json


def summarize(source, config, collected, client, started, error=None):
    records = collected.records
    seen, unique, without_id = set(), [], 0
    for r in records:
        fp = r.fingerprint()
        if fp is None:
            without_id += 1
            unique.append(r)
        elif fp not in seen:
            seen.add(fp)
            unique.append(r)
    screens = [screen(r.text, r.author_type) for r in unique]
    fields = Counter(k for r in unique for k, present in r.fields.items() if present)
    row_metrics = []
    for r, s in zip(unique, screens):
        row_metrics.append({"record_fingerprint": r.fingerprint(), "kind": r.kind,
            "parent_fingerprint": hashlib.sha256(f"{r.source}:{'issue' if r.source == 'github' else 'story'}:{r.parent}".encode()).hexdigest() if r.parent else None,
            "created": r.created, "updated": r.updated, "field_presence": r.fields,
            "metadata": r.metadata, **s,
            "language_triage_flag": language_flag(r.text, r.metadata.get("language"))})
    statuses = dict(Counter(str(e['status']) if e['status'] is not None else 'transport_error' for e in client.events))
    return {
        "source": source, "started_at_utc": started, "finished_at_utc": utcnow(),
        "evidence": "CURRENT_LIVE" if client.events else "NOT_TESTED",
        "config": config, "endpoint_family": client.host, "requested_record_limit": config['max_records'],
        "http_requests": len(client.events), "response_status_summary": statuses,
        "successful_http_responses": sum(e['status'] == 200 for e in client.events),
        "records_returned": len(records), "unique_records_with_id": len(seen),
        "records_without_id": without_id, "duplicate_records": len(records) - len(unique),
        "text_screen_counts": counts(screens),
        "usable_text_count": sum(s['screen'] == 'eligible_for_manual_review' for s in screens),
        "usable_text_definition": 'Heuristic eligibility only: normalized text >=20 characters and >=4 words, excluding Bot. NOT a validated count of meaningful opinions.',
        "human_validated_opinion_count": None,
        "missing_required_field_counts": {k: sum(getattr(r, k) is None for r in unique) for k in ['key', 'created']},
        "empty_body_count": sum(not r.text for r in unique),
        "available_fields": dict(sorted(fields.items())),
        "excluded": collected.excluded, "observations": collected.observations,
        "errors": [error] if error else [], "source_stopped": client.blocked,
        "requests": client.events, "record_metrics": row_metrics,
        "repeat_config": collected.repeat_config,
        "limitations": ['Small selection-biased sample; no population estimate or long-term stability claim.',
                        'Raw text, usernames and account IDs are not saved. Fingerprints identify records, not authors.',
                        'No delete replay or production-use approval tested.'],
    }


def compare(a, b):
    ka = {r['record_fingerprint'] for r in a['record_metrics'] if r['record_fingerprint']}
    kb = {r['record_fingerprint'] for r in b['record_metrics'] if r['record_fingerprint']}
    return {'source': a['source'], 'first_run': a['run_id'], 'second_run': b['run_id'],
            'overlapping_unique_ids': len(ka & kb), 'first_only': len(ka-kb), 'second_only': len(kb-ka),
            'field_names_equal': set(a['available_fields']) == set(b['available_fields']),
            'first_http': a['response_status_summary'], 'second_http': b['response_status_summary'],
            'seconds_between_starts': (__import__('datetime').datetime.fromisoformat(b['started_at_utc']) -
                                       __import__('datetime').datetime.fromisoformat(a['started_at_utc'])).total_seconds(),
            'interpretation': 'Two bounded executions only. Steam anonymous responses may be cached up to 10 minutes; overlap does not prove live freshness.'}
