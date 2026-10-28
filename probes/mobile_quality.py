"""Bounded mobile-review comparison; private inspection text stays outside the repository."""
import json,time,re,html,hashlib,requests,xml.etree.ElementTree as ET
import argparse
from zoneinfo import ZoneInfo
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1];O=None
APPS=json.loads((R/'results/mainstream/app_sample_manifest.json').read_text())['apps']
legacy={r['fingerprint'] for name in ('apple_rss_access.json','apple_xml_review_sample.json') for run in json.loads((R/'results/mainstream'/name).read_text())['runs'] for r in run['records']}
SESSION=requests.Session();SESSION.trust_env=False;SESSION.headers.update({'User-Agent':'DataSourceFeasibility/0.1 (bounded comparative quality validation; no training)'})
PRIVATE={}; EVENTS=[];BLOCKED=set();LAST=None

def normalize(text):return re.sub(r'\s+',' ',html.unescape(str(text or ''))).strip()
def apple_rows(body,fmt):
 if fmt=='xml':
  ns={'a':'http://www.w3.org/2005/Atom','im':'http://itunes.apple.com/rss'};root=ET.fromstring(body)
  if root.tag!='{http://www.w3.org/2005/Atom}feed':raise ValueError('feed_schema')
  return [{'id':x.findtext('a:id',namespaces=ns),'text':x.findtext('a:content',namespaces=ns),'rating':x.findtext('im:rating',namespaces=ns),'date':x.findtext('a:updated',namespaces=ns),'version':x.findtext('im:version',namespaces=ns)} for x in root.findall('a:entry',ns) if x.find('im:rating',ns) is not None]
 data=json.loads(body)
 if not isinstance(data,dict) or not isinstance(data.get('feed'),dict):raise ValueError('feed_schema')
 entries=data['feed'].get('entry',[]);entries=[entries] if isinstance(entries,dict) else entries
 if not isinstance(entries,list):raise ValueError('entry_schema')
 def label(x):return x.get('label') if isinstance(x,dict) else None
 return [{'id':label(x.get('id')),'text':label(x.get('content')),'rating':label(x.get('im:rating')),'date':label(x.get('updated')),'version':label(x.get('im:version'))} for x in entries if isinstance(x,dict) and label(x.get('im:rating')) is not None]

def google_rows(body):
 envelope=None
 for line in body.decode('utf-8').splitlines():
  if line.startswith('['):
   try:
    candidate=json.loads(line)
    for row in candidate:
     if isinstance(row,list) and len(row)>2 and row[0]=='wrb.fr' and row[1]=='oCPfdb' and isinstance(row[2],str):envelope=json.loads(row[2])
   except (ValueError,TypeError):continue
 if not isinstance(envelope,list) or not envelope or not isinstance(envelope[0],list):raise ValueError('google_schema')
 rows=[]
 for row in envelope[0]:
  if not isinstance(row,list) or len(row)<6 or not isinstance(row[0],str) or not isinstance(row[4],str) or type(row[2]) is not int or row[2] not in range(1,6):raise ValueError('google_review_schema')
  rows.append({'id':row[0],'text':row[4],'rating':row[2],'date':row[5][0] if isinstance(row[5],list) and row[5] else None,'version':row[10] if len(row)>10 else None})
 try:cursor=envelope[-2][-1]
 except (IndexError,TypeError):cursor=None
 return rows,cursor if isinstance(cursor,str) and cursor else None

def project(row,source,app):
 text=normalize(row['text']);key=str(row.get('id') or '')
 prefix='apple:us:'+app['app_store_id'] if source=='apple' else 'google_play:'+app['google_play_package']
 fp=hashlib.sha256((prefix+':'+key).encode()).hexdigest() if key else None
 if not key or not isinstance(row.get('text'),str):raise ValueError('missing_identity_or_text')
 record={'source':source,'app_store_id':app['app_store_id'],'google_play_package':app['google_play_package'],'stratum':app['analysis_stratum'],'fingerprint':fp,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'characters':len(text),'words':len(text.split()),'rating':int(row['rating']),'date':row.get('date'),'date_semantics':'feed_updated_not_proven_creation' if source=='apple' else 'web_review_timestamp','has_version':bool(row.get('version')),'prefix_limited':len(text)>500,'legacy_apple_fingerprint':source=='apple' and fp in legacy}
 PRIVATE[fp]={'source':source,'app':app['name'],'stratum':app['analysis_stratum'],'fingerprint':fp,'characters':len(text),'prefix_limited':len(text)>500,'inspection_prefix':re.sub(r'https?://\S+|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[redacted]',text[:500])}
 return record

def fetch(source,app,page,phase,limit=5,cursor=None):
 global LAST
 if source in BLOCKED:return None,None
 if len(EVENTS)>=32:raise ValueError('request_budget_exhausted')
 if LAST is not None:time.sleep(max(0,2-(time.monotonic()-LAST)))
 LAST=time.monotonic();fmt='xml' if app['app_store_id'] in ('1212616790','368677368') else 'json'
 url=f"https://itunes.apple.com/us/rss/customerreviews/page={page}/id={app['app_store_id']}/sortby=mostrecent/{fmt}" if source=='apple' else 'https://play.google.com/_/PlayStoreUi/data/batchexecute'
 event={'at_utc':datetime.now(timezone.utc).isoformat(),'source':source,'app_store_id':app['app_store_id'],'package':app['google_play_package'],'stratum':app['analysis_stratum'],'phase':phase,'page':page,'format':fmt if source=='apple' else 'web_rpc','url':url,'status':None,'error':None,'records':[],'entries_received':None,'maximum_records_retained':limit,'credentials_supplied':False,'raw_text_saved':False}
 try:
  SESSION.cookies.clear()
  if source=='apple':response=SESSION.get(url,timeout=(10,25),allow_redirects=False,stream=True)
  else:
   count=[limit,None,cursor] if cursor else [limit]
   args=[None,[2,2,count,None,[None,None,None,None,None,None,None,None,None]],[app['google_play_package'],7]]
   payload={'f.req':json.dumps([[['oCPfdb',json.dumps(args,separators=(',',':')),None,'generic']]],separators=(',',':'))}
   response=SESSION.post(url,params={'hl':'en','gl':'us'},data=payload,timeout=(10,25),allow_redirects=False,stream=True)
  with response as resp:
   event['status']=resp.status_code
   if resp.status_code!=200:BLOCKED.add(source);raise ValueError('non_200_stop')
   body=bytearray()
   for chunk in resp.iter_content(16384):
    body.extend(chunk)
    if len(body)>2000000:raise ValueError('response_limit')
   event['response_bytes']=len(body)
   rows=apple_rows(body,fmt) if source=='apple' else None
   if source=='google':rows,cursor=google_rows(body);event['continuation_token_present']=bool(cursor)
   event['entries_received']=len(rows)
   chosen=rows[:limit]
   # Recover previously inspected Apple IDs from the received window without guessing their text.
   if source=='apple' and phase in ('baseline','legacy_page2'):
    selected={str(x['id']) for x in chosen}
    for row in rows[limit:]:
     fp=hashlib.sha256(('apple:us:'+app['app_store_id']+':'+str(row.get('id') or '')).encode()).hexdigest()
     if fp in legacy and str(row['id']) not in selected:chosen.append(row);selected.add(str(row['id']))
   event['records']=[project(row,source,app) for row in chosen]
 except Exception as exc:event['error']=type(exc).__name__;event['error_stage']='bounded_request_or_schema';BLOCKED.add(source)
 EVENTS.append(event);print(source,app['name'],phase,page,event['status'],event['error'],len(event['records']),flush=True)
 return event,cursor

def main(argv=None):
 global O,EVENTS,PRIVATE,BLOCKED,LAST
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('phase',choices=['initial','repeat'])
 parser.add_argument('--output',type=Path,default=Path('results/mobile_quality'))
 parser.add_argument('--inspection-output',type=Path,required=True,help='Temporary rating-hidden text prefix file; must be outside this repository')
 args=parser.parse_args(argv)
 inspection_path=args.inspection_output.resolve()
 if inspection_path.is_relative_to(R.resolve()):raise ValueError('inspection_output_must_be_outside_repository')
 O=args.output
 if args.phase=='initial' and (O/'collection.json').exists():raise FileExistsError('initial_output_already_exists')
 O.mkdir(parents=True,exist_ok=True)
 phase=args.phase
 EVENTS=[];PRIVATE={};BLOCKED=set();LAST=None
 if phase=='repeat':
  prior=json.loads((O/'collection.json').read_text());EVENTS=prior['requests'];PRIVATE=json.loads(inspection_path.read_text());BLOCKED=set(prior.get('blocked_sources',[]))
 selected=[APPS[i] for i in (0,3,5,7)]
 if phase=='initial':
  cursors={}
  for source in ('apple','google'):
   for app in APPS:
    event,cursor=fetch(source,app,1,'baseline')
    if source=='google':cursors[app['app_store_id']]=cursor
  fetch('apple',APPS[0],2,'legacy_page2',5)
  for app in selected[1:]:fetch('apple',app,2,'pagination',2)
  for app in selected:
   if cursors.get(app['app_store_id']):fetch('google',app,2,'pagination',2,cursors[app['app_store_id']])
 elif phase=='repeat':
  for source in ('apple','google'):
   for app in selected:fetch(source,app,1,'repeat',5)
 else:raise ValueError('unknown_phase')
 result={'assessment_date':datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d %Z'),'maximum_requests':32,'request_spacing_seconds':2,'maximum_response_bytes':2000000,'raw_content_saved':False,'blocked_sources':sorted(BLOCKED),'requests':EVENTS,'http_requests':len(EVENTS),'raw_inspection_location':'Outside repository; temporary inspection prefixes, no author fields; excluded from delivery','semantic_labels':'Pending separate AI-assisted inspection; ratings hidden in inspection view'}
 (O/'collection.json').write_text(json.dumps(result,indent=2)+'\n');inspection_path.parent.mkdir(parents=True,exist_ok=True);inspection_path.touch(mode=0o600,exist_ok=True);inspection_path.chmod(0o600);inspection_path.write_text(json.dumps(PRIVATE,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
 main()
