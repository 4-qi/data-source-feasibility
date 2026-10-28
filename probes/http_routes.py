import json,time,re,hashlib,html
from datetime import datetime,timezone
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
import requests
class Scripts(HTMLParser):
 def __init__(self):super().__init__();self.collect=False;self.current=[];self.blocks=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag=='script' and (attrs.get('type','').lower()=='application/ld+json' or attrs.get('id')=='__NEXT_DATA__'):self.collect=True;self.current=[]
 def handle_data(self,data):
  if self.collect:self.current.append(data)
 def handle_endtag(self,tag):
  if tag=='script' and self.collect:self.blocks.append(''.join(self.current));self.collect=False

def walk_reviews(node,found):
 if isinstance(node,list):
  for value in node:walk_reviews(value,found)
 elif isinstance(node,dict):
  text=node.get('reviewBody')
  if isinstance(text,str) and text.strip():
   rating=node.get('reviewRating',{})
   rating=rating.get('ratingValue') if isinstance(rating,dict) else None
   found.append({'text':text,'id':node.get('@id') or node.get('id'),'rating':rating,'date':node.get('datePublished')})
  for value in node.values():
   if isinstance(value,(dict,list)):walk_reviews(value,found)

def project(record,source):
 text=re.sub(r'\s+',' ',html.unescape(record['text'])).strip();key=record.get('id')
 return {'fingerprint':hashlib.sha256((source+':'+(str(key) if key else text)).encode()).hexdigest(),'identity_basis':'source_id' if key else 'exact_text_only','has_text':bool(text),'characters':len(text),'words':len(text.split()),'has_date':bool(record.get('date')),'rating':record.get('rating')}

def request(source,url,params=None,kind='html'):
 session=requests.Session();session.trust_env=False;session.headers.update({'User-Agent':'DataSourceFeasibility/0.1 (bounded public access recheck; no training)','Accept':'application/json' if kind!='html' else 'text/html'})
 event={'source':source,'at_utc':datetime.now(timezone.utc).isoformat(),'url':url,'parameters':params or {},'status':None,'error':None,'response_bytes':0,'content_type':None,'challenge_marker_detected':False,'raw_body_saved':False,'credentials_supplied':False,'redirects_allowed':False,'retry_count':0,'records':[]}
 cursor=None
 try:
  with session.get(url,params=params,timeout=(10,25),allow_redirects=False,stream=True) as response:
   event['status']=response.status_code;event['content_type']=response.headers.get('Content-Type','').split(';')[0]
   if response.status_code!=200:event['error']='non_200_stop';return event,None
   body=bytearray()
   for chunk in response.iter_content(16384):
    body.extend(chunk)
    if len(body)>5000000:raise ValueError('response_size_limit')
   event['response_bytes']=len(body)
   records=[]
   if kind=='html':
    text=body.decode(response.encoding or 'utf-8',errors='replace')
    # Challenge markers are diagnostics, not an assertion about all visitors.
    event['challenge_marker_detected']=bool(re.search(r'<title>\s*(?:Robot or human|Access Denied|Just a moment)|Please verify you are a human|verify you are human|Press & Hold',text,re.I))
    if event['challenge_marker_detected']:event['error']='challenge_stop';return event,None
    parser=Scripts();parser.feed(text);event['public_embedded_json_blocks']=len(parser.blocks)
    for block in parser.blocks:
     try:walk_reviews(json.loads(block),records)
     except (ValueError,RecursionError):continue
    event['embedded_review_objects']=len(records)
   elif kind=='bluesky':
    data=json.loads(body)
    if not isinstance(data,dict) or not isinstance(data.get('posts'),list):raise ValueError('unexpected_posts_schema')
    posts=data['posts'];event['records_returned']=len(posts);cursor=data.get('cursor')
    for post in posts:
     record=post.get('record',{})
     if isinstance(record.get('text'),str):records.append({'text':record['text'],'id':post.get('uri'),'date':record.get('createdAt')})
    event['cursor_present']=bool(cursor)
   elif kind=='mastodon':
    data=json.loads(body)
    if not isinstance(data,list):raise ValueError('unexpected_statuses_schema')
    event['records_returned']=len(data)
    for post in data:
     if isinstance(post,dict) and isinstance(post.get('content'),str):
      records.append({'text':re.sub('<[^>]+>',' ',post['content']),'id':post.get('id'),'date':post.get('created_at')})
    cursor=data[-1].get('id') if data else None;event['next_id_present']=bool(cursor)
   event['records']=[project(r,source) for r in records[:5]]
 except Exception as exc:event['error']=type(exc).__name__
 finally:session.close()
 return event,cursor


import argparse


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("results/route_recheck"))
    args=parser.parse_args(argv)
    args.output.mkdir(parents=True,exist_ok=True)
    OUT=args.output
    checks=[('bluesky','https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts',{'q':'Spotify','sort':'latest','limit':3,'lang':'en'},'bluesky'),('mastodon','https://mastodon.social/api/v1/timelines/tag/firefox',{'limit':3},'mastodon'),('walmart','https://www.walmart.com/ip/703412326',None,'html'),('bestbuy','https://www.bestbuy.com/product/sony-wh-1000xm5-wireless-noise-cancelling-over-the-ear-headphones-black/J7XSRH5CXG/sku/6505727/reviews',None,'html'),('yelp','https://www.yelp.com/biz/north-india-restaurant-san-francisco',None,'html'),('google_play','https://play.google.com/store/apps/details',{'id':'com.spotify.music','hl':'en_US'},'html')]
    events=[]
    for source,url,params,kind in checks:
     time.sleep(2);event,cursor=request(source,url,params,kind);events.append(event);print(source,event['status'],event['error'],len(event['records']),flush=True)
     if source in ('bluesky','mastodon') and event['status']==200 and not event['error'] and cursor:
      time.sleep(2);page=dict(params);page['cursor' if kind=='bluesky' else 'max_id']=cursor
      second,_=request(source,url,page,kind);events.append(second)
      first_ids={r['fingerprint'] for r in event['records']};second_ids={r['fingerprint'] for r in second['records']}
      second['overlap_with_first_page']=len(first_ids&second_ids)
      # Saved pagination tokens are record linkage metadata; hash them after request.
      second['parameters']['cursor' if kind=='bluesky' else 'max_id']='sha256:'+hashlib.sha256(str(cursor).encode()).hexdigest()
      print(source,'page2',second['status'],second['error'],len(second['records']),flush=True)
    result={'assessment_date':'2026-10-27 PDT','purpose':'Bounded route recheck; no platform-wide impossibility inference','maximum_requests':8,'http_requests':len(events),'requests':events,'raw_content_saved':False,'amazon_requests':0,'long_term_reliability':'NOT_TESTED','use_rights':'NOT_ESTABLISHED_BY_ACCESS_CHECK'}
    (OUT/'source_route_recheck.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == "__main__":
    main()
