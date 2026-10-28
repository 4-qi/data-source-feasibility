"""Bounded public RSS technical diagnostic; no ongoing ingestion or use license implied.

The live exploration used the same JSON/Atom record projection.
This CLI combines bounded XML fallback, manifest/feed validation and timestamped output.
It does not save review text or author values. Run only for an approved test scope.
"""
import argparse
import xml.etree.ElementTree as ET
import requests,json,time,hashlib,re,html
from pathlib import Path
from datetime import datetime,timezone


def decode_feed(body, xml=False):
    if not xml:
        data=json.loads(body)
        if not isinstance(data,dict) or not isinstance(data.get('feed'),dict):
            raise ValueError('feed_schema')
        return data['feed']
    root=ET.fromstring(body)
    ns={'a':'http://www.w3.org/2005/Atom','im':'http://itunes.apple.com/rss'}
    if root.tag!='{http://www.w3.org/2005/Atom}feed':
        raise ValueError('feed_schema')
    entries=[]
    for item in root.findall('a:entry',ns):
        entry={}
        for target,path in [('id','a:id'),('content','a:content'),('title','a:title'),
                            ('updated','a:updated'),('im:rating','im:rating'),('im:version','im:version')]:
            value=item.findtext(path,namespaces=ns)
            if value is not None:entry[target]={'label':value}
        entries.append(entry)
    return {'entry':entries,'link':[{}] if root.findall('a:link',ns) else []}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=Path('results/mainstream/app_sample_manifest.json'))
    parser.add_argument('--output',type=Path,default=Path('results/mainstream'))
    args=parser.parse_args(argv)
    out=args.output; manifest=json.loads(args.manifest.read_text())
    apps=manifest.get('apps', [])
    if len(apps)!=8 or len({a.get('app_store_id') for a in apps})!=8 or any(not re.fullmatch(r'[0-9]{1,20}',str(a.get('app_store_id',''))) for a in apps):
        raise ValueError('manifest_requires_eight_distinct_numeric_app_ids')
    out.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.trust_env=False;s.headers.update({'User-Agent':'DataSourceFeasibility/0.1 (bounded public-feed technical validation; no training)','Accept':'application/json'})
    requests_log=[];runs=[];stopped=False
    schedule=[(a,1,'cross_category') for a in manifest['apps']]+[(manifest['apps'][0],2,'pagination'),(manifest['apps'][0],1,'repeat')]
    def value(x):
        return x.get('label') if isinstance(x,dict) else None
    for app,page,phase in schedule:
        if stopped or len(requests_log)>=13:break
        if requests_log:time.sleep(2)
        fmt="xml" if phase=="xml_fallback" else "json"
        url=f"https://itunes.apple.com/us/rss/customerreviews/page={page}/id={app['app_store_id']}/sortby=mostrecent/{fmt}"
        event={'at_utc':datetime.now(timezone.utc).isoformat(),'url':url,'phase':phase,'page':page,'app_store_id':app['app_store_id'],'status':None,'error':None,'redirects_allowed':False,'credentials_supplied':False,'retries':0}
        result={'app_store_id':app['app_store_id'],'stratum':app['analysis_stratum'],'phase':phase,'page':page,'entries_returned':None,'review_entries_received':None,'records':[],'pagination_links_present':False}
        try:
            s.cookies.clear()
            with s.get(url,timeout=(10,25),allow_redirects=False,stream=True) as r:
                event['status']=r.status_code;event['content_type']=r.headers.get('Content-Type','').split(';')[0]
                if r.status_code!=200:
                    event['error']='non_200_stop';stopped=True
                else:
                    body=bytearray()
                    for chunk in r.iter_content(16384):
                        body.extend(chunk)
                        if len(body)>2000000:raise ValueError('body_limit')
                    event['response_bytes']=len(body)
                    feed=decode_feed(body,xml=fmt=='xml');entries=feed.get('entry',[])
                    if isinstance(entries,dict):entries=[entries]
                    if not isinstance(entries,list):raise ValueError('entry_schema')
                    reviews=[x for x in entries if isinstance(x,dict) and value(x.get('im:rating')) is not None and value(x.get('content')) is not None]
                    result.update(entries_returned=len(entries),review_entries_received=len(reviews),pagination_links_present=bool(feed.get('link')))
                    if not reviews and phase=='cross_category':schedule.append((app,1,'xml_fallback'))
                    for x in reviews[:5]:
                        text=re.sub(r'\s+',' ',html.unescape(str(value(x.get('content')) or ''))).strip()
                        key=str(value(x.get('id')) or '')
                        rating=value(x.get('im:rating'))
                        result['records'].append({'fingerprint':hashlib.sha256(('apple:us:'+app['app_store_id']+':'+key).encode()).hexdigest() if key else None,'has_id':bool(key),'has_text':bool(text),'characters':len(text),'words':len(text.split()),'rating':int(rating) if str(rating).isdigit() else None,'has_title':bool(value(x.get('title'))),'has_updated':bool(value(x.get('updated'))),'has_version':bool(value(x.get('im:version'))),'text_sha256':hashlib.sha256(text.encode()).hexdigest()})
        except Exception as e:
            event['error']=type(e).__name__;stopped=True
        requests_log.append(event);runs.append(result)
        print(app['name'],phase,event['status'],event['error'],result['review_entries_received'])
    allrecords=[r for run in runs for r in run['records']];uniq={r['fingerprint']:r for r in allrecords if r['fingerprint']}
    first=next((x for x in runs if x['app_store_id']==manifest['apps'][0]['app_store_id'] and x['phase']=='cross_category'),None)
    repeat=next((x for x in runs if x['phase']=='repeat'),None)
    second=next((x for x in runs if x['phase']=='pagination'),None)
    def ids(run):return {r['fingerprint'] for r in run['records'] if r['fingerprint']} if run else None
    result={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'purpose':'Bounded technical availability check; not a production license or ongoing ingestion implementation','request_budget':13,'max_records_parsed_per_response':5,'max_response_bytes':2000000,'http_requests':len(requests_log),'http_200':sum(x['status']==200 for x in requests_log),'stopped_on_error':stopped,'request_budget_exhausted':len(schedule)>len(requests_log) and len(requests_log)>=13,'requests':requests_log,'runs':runs,'parsed_record_occurrences':len(allrecords),'distinct_parsed_fingerprints':len(uniq),'review_entries_received_sum':sum(x['review_entries_received'] or 0 for x in runs),'repeat_same_sample_ids':ids(first)==ids(repeat) if repeat else None,'page_1_page_2_sample_overlap':len(ids(first)&ids(second)) if first and second else None,'raw_review_text_saved':False,'author_values_saved':False,'sentiment_analysis':'NOT_PERFORMED','ongoing_update_detection':'NOT_TESTED','production_use_rights':'NOT_ESTABLISHED'}
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (out/f'apple_rss_access_{stamp}.json').write_text(json.dumps(result,indent=2)+'\n')
    print('summary',result['http_requests'],result['http_200'],result['distinct_parsed_fingerprints'])

    return 1 if stopped or result['request_budget_exhausted'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
