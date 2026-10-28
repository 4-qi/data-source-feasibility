"""Bounded read-only check of an undocumented public web review transport."""
import requests,json,time,hashlib
from pathlib import Path
from datetime import datetime,timezone

import argparse


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("results/route_recheck"))
    args=parser.parse_args(argv)
    args.output.mkdir(parents=True,exist_ok=True)
    OUT=args.output
    URL='https://play.google.com/_/PlayStoreUi/data/batchexecute'
    s=requests.Session();s.trust_env=False;s.headers.update({'User-Agent':'DataSourceFeasibility/0.1 (bounded public review feasibility check; no training)'})
    events=[];cursor=None
    for page in (1,2):
     if page==2 and not cursor:break
     if events:time.sleep(2)
     count=[3] if page==1 else [3,None,cursor]
     args=[None,[2,2,count,None,[None,None,None,None,None,None,None,None,None]],['com.spotify.music',7]]
     payload={'f.req':json.dumps([[['oCPfdb',json.dumps(args,separators=(',',':')),None,'generic']]],separators=(',',':'))}
     e={'at_utc':datetime.now(timezone.utc).isoformat(),'url':URL,'method':'POST','purpose':'Read review data; no posting or account mutation','query_parameters':{'hl':'en','gl':'us'},'application':'com.spotify.music','page':page,'requested_records':3,'sort_numeric':2,'cursor_supplied':bool(cursor),'status':None,'error':None,'raw_body_saved':False,'author_values_saved':False,'credentials_supplied':False,'automatic_retries':0,'tls_verification':True,'records':[]}
     try:
      with s.post(URL,params=e['query_parameters'],data=payload,timeout=(10,25),allow_redirects=False,stream=True) as r:
       e['status']=r.status_code
       if r.status_code!=200:e['error']='non_200_stop';events.append(e);break
       body=bytearray()
       for chunk in r.iter_content(16384):
        body.extend(chunk)
        if len(body)>2000000:raise ValueError('response_limit')
       envelope=None
       for line in body.decode('utf-8').splitlines():
        if line.startswith('['):
         try:
          candidate=json.loads(line)
          if isinstance(candidate,list):
           for row in candidate:
            if isinstance(row,list) and len(row)>2 and row[0]=='wrb.fr' and row[1]=='oCPfdb' and isinstance(row[2],str):envelope=json.loads(row[2])
         except ValueError:continue
       if not isinstance(envelope,list) or not envelope or not isinstance(envelope[0],list):raise ValueError('unexpected_review_response')
       rows=envelope[0];e['review_rows_returned']=len(rows)
       for row in rows[:3]:
        if not isinstance(row,list) or len(row)<6 or not isinstance(row[0],str) or not isinstance(row[4],str) or type(row[2]) is not int or row[2] not in range(1,6):raise ValueError('unexpected_review_row')
        text=row[4].strip()
        e['records'].append({'fingerprint':hashlib.sha256(('google_play:com.spotify.music:'+row[0]).encode()).hexdigest(),'identity_basis':'source_review_id','has_text':bool(text),'characters':len(text),'words':len(text.split()),'rating':row[2],'has_date':isinstance(row[5],list) and bool(row[5]) and isinstance(row[5][0],int)})
       try:token=envelope[-2][-1]
       except (IndexError,TypeError):token=None
       cursor=token if isinstance(token,str) and token else None;e['continuation_token_present']=bool(cursor)
     except Exception as exc:e['error']=type(exc).__name__
     events.append(e);print('page',page,e['status'],e['error'],len(e['records']),flush=True)
     if e['error']:break
    unique={r['fingerprint'] for e in events for r in e['records']}
    result={'assessment_date':'2026-10-27 PDT','interface_status':'Undocumented Google Play web transport; not Android Publisher API or a supported public review API contract','schema_source':'https://github.com/JoMingyu/google-play-scraper/blob/master/google_play_scraper/constants/request.py','field_source':'https://github.com/JoMingyu/google-play-scraper/blob/master/google_play_scraper/constants/element.py','maximum_requests':2,'http_requests':len(events),'requests':events,'distinct_fingerprints':len(unique),'pagination_overlap':len({r['fingerprint'] for r in events[0]['records']}&{r['fingerprint'] for r in events[1]['records']}) if len(events)==2 else None,'ongoing_updates':'NOT_TESTED','collection_retention_analysis_rights':'NOT_ESTABLISHED','third_party_library_executed':False,'raw_text_saved':False}
    (OUT/'google_play_review_rpc_recheck.json').write_text(json.dumps(result,indent=2)+'\n')
    print('distinct',len(unique))


if __name__ == "__main__":
    main()
