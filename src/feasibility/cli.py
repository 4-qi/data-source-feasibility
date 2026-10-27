"""CLI: probe one source or execute the fixed two-round experiment."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from .http import Client, StopCollection, utcnow
from .model import Collected
from .collectors import steam, github_issues, hackernews
from .quality import clean_text
from .reporting import summarize, compare

SOURCES = {'steam': ('api.steampowered.com', steam.collect),
           'github': ('api.github.com', github_issues.collect),
           'hackernews': ('hacker-news.firebaseio.com', hackernews.collect)}


def execute(source, limit, budget, delay, extra=None, inspect=False):
    client = Client(SOURCES[source][0], budget, delay)
    config = {'max_records': limit, 'max_requests': budget, 'min_request_interval_seconds': delay,
              'anonymous': True, **(extra or {})}
    started, error = utcnow(), None
    try:
        collected = SOURCES[source][1](client, max_records=limit, **(extra or {}))
    except StopCollection as exc:
        error = exc.code
        collected = getattr(client, 'collected', Collected())
    result = summarize(source, config, collected, client, started, error)
    result['run_id'] = source + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    if inspect:
        emitted = set()
        for rec in collected.records:
            fp = rec.fingerprint()
            if fp in emitted:
                continue
            emitted.add(fp)
            snippet = re.sub(r'https?://\S+|@[\w.-]+', '[omitted]', clean_text(rec.text))[:500]
            print(json.dumps({'audit_record': fp, 'kind': rec.kind, 'author_type': rec.author_type,
                              'prefix_only': len(clean_text(rec.text)) > 500, 'prefix': snippet}, ensure_ascii=False))
    return result


def save_run(result, output):
    runs = output / 'runs'
    runs.mkdir(parents=True, exist_ok=True)
    p = runs / (result['run_id'] + '.json')
    p.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'saved': str(p), 'source': result['source'], 'http': result['response_status_summary'],
                      'records': result['records_returned'], 'unique_ids': result['unique_records_with_id'],
                      'eligible': result['usable_text_count'], 'errors': result['errors']}))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest='command', required=True)
    for name in ['probe', 'experiment']:
        s = subs.add_parser(name)
        if name == 'probe':
            s.add_argument('source', choices=SOURCES)
            s.add_argument('--max-records', type=int, default=16)
            s.add_argument('--max-requests', type=int, default=10)
        s.add_argument('--delay', type=float, default=1.0)
        s.add_argument('--output', type=Path, default=Path('results'))
        s.add_argument('--inspect-text', action='store_true', help='Print bounded text prefixes for human review; never write them to output files.')
    args = p.parse_args(argv)
    if args.delay < 1.0:
        p.error('delay must be >=1 second')
    if args.command == 'probe':
        if not 1 <= args.max_records <= 50 or not 1 <= args.max_requests <= 16:
            p.error('record limit must be 1..50 and request budget 1..16')
        result = execute(args.source, args.max_records, args.max_requests, args.delay, inspect=args.inspect_text)
        save_run(result, args.output)
        return 1 if result['errors'] else 0
    # No automatic source retry after errors or exhausted quota, even across rounds.
    runs, repeat, failed = [], {}, set()
    limits = {'steam': (32, 6), 'github': (24, 4), 'hackernews': (9, 10)}
    for round_number in (1, 2):
        for source in SOURCES:
            if source in failed:
                continue
            limit, budget = limits[source]
            result = execute(source, limit, budget, args.delay,
                             extra=repeat.get(source), inspect=args.inspect_text and round_number == 1)
            result['round'] = round_number
            save_run(result, args.output)
            runs.append(result)
            repeat[source] = result.get('repeat_config') or {}
            if result['errors'] or result['source_stopped']:
                failed.add(source)
    comparisons = []
    for source in SOURCES:
        same = [r for r in runs if r['source'] == source]
        if len(same) == 2:
            comparisons.append(compare(*same))
    summary = {'created_at_utc': utcnow(), 'experiment': 'bounded-two-round-current-live',
               'runs': runs, 'repeatability': comparisons,
               'sources_not_repeated_due_to_failure_or_quota': sorted(failed),
               'amazon': {'evidence': 'NOT_TESTED', 'reason': 'No currently available authorized full-review acquisition route; see research/amazon_access.md.'}}
    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    # Keep each experiment even if the convenience latest summary is refreshed.
    (args.output / f'experiment_{stamp}.json').write_text(json.dumps(summary, indent=2) + '\n')
    (args.output / 'collection_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
