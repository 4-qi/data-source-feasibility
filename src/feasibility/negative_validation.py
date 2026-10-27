"""Supplemental negative-review validation: at most two GETs and four records."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from .collectors import steam
from .http import Client, StopCollection, utcnow
from .model import Collected
from .reporting import summarize


def run(client=None):
    client = client or Client('api.steampowered.com', max_requests=2, delay=1.0)
    config = {'max_records':4, 'max_requests':2, 'min_request_interval_seconds':1.0,
              'anonymous':True, 'review_type':2, 'filter':1, 'appids':[620,413150],
              'page_size':2, 'pages_per_game':1}
    started, error = utcnow(), None
    try:
        records = steam.collect_negative(client)
    except StopCollection as exc:
        error = exc.code
        records = getattr(client, 'collected', Collected())
    result = summarize('steam', config, records, client, started, error)
    result['run_id'] = 'steam_negative_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    result['experiment_phase'] = 'supplemental_negative_filter_validation'
    flags = [x['metadata'].get('voted_up') for x in result['record_metrics']]
    result['recommendation_flag_counts'] = {
        'true':sum(x is True for x in flags), 'false':sum(x is False for x in flags),
        'missing':sum(x is None for x in flags),
        'non_boolean':sum(x is not None and type(x) is not bool for x in flags)}
    result['label_validation_passed'] = bool(flags) and all(x is False for x in flags) and not error
    result['sampling_note'] = ('Deliberately selected review_type=2 (Negative). Verifies retrieval and label preservation; '
                               'not a natural sentiment distribution, balanced training set, or sentence-level sentiment evaluation.')
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('results/negative_validation'))
    args=p.parse_args(argv)
    result=run()
    args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/(result['run_id']+'.json')
    path.write_text(json.dumps(result,indent=2)+'\n')
    # No raw text is printed or saved.
    print(json.dumps({'saved':str(path),'http':result['response_status_summary'],
          'records':result['records_returned'],'unique_ids':result['unique_records_with_id'],
          'duplicates':result['duplicate_records'],'flags':result['recommendation_flag_counts'],
          'label_validation_passed':result['label_validation_passed'],'errors':result['errors']},indent=2))
    return 0 if result['label_validation_passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
