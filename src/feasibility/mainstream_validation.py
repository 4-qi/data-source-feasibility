"""One-request access check for the CFPB public API; no review corpus is stored."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .http import Client, StopCollection, utcnow

ENDPOINT = 'https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/'
PARAMS = {'size': 2, 'frm': 0, 'sort': 'created_date_desc',
          'no_aggs': 'true', 'no_highlight': 'true'}


def probe(client=None):
    """Check access once. A successful response establishes schema, not narrative usability."""
    client = client or Client('www.consumerfinance.gov', max_requests=1, delay=2.0)
    result = {'checked_at_utc': utcnow(), 'source': 'cfpb', 'request_limit': 1,
              'purpose': 'Bounded public API access and response-schema check',
              'error': None, 'response_schema': None,
              'narrative_availability': 'NOT_ASSESSED', 'raw_content_saved': False}
    try:
        data = client.get(ENDPOINT, params=dict(PARAMS))
        if not isinstance(data, dict):
            raise StopCollection('unexpected_cfpb_schema')
        result['response_schema'] = {k: type(v).__name__ for k, v in data.items()}
    except StopCollection as exc:
        result['error'] = exc.code
    result['requests'] = client.events
    result['http_requests'] = len(client.events)
    result['response_status_summary'] = {}
    for event in client.events:
        status = str(event['status']) if event['status'] is not None else 'transport_error'
        result['response_status_summary'][status] = result['response_status_summary'].get(status, 0) + 1
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results/mainstream'))
    args = parser.parse_args(argv)
    result = probe()
    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = args.output / f'cfpb_access_{stamp}.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'saved': str(path), 'http': result['response_status_summary'],
                      'error': result['error'], 'narrative_availability': result['narrative_availability']}))
    return 1 if result['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
