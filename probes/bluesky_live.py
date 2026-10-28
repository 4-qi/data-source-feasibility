"""One bounded connection to the documented public live stream; no raw posts stored."""
import os,json,time,hashlib
from datetime import datetime,timezone
from pathlib import Path

import argparse


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("results/route_recheck"))
    args=parser.parse_args(argv)
    args.output.mkdir(parents=True,exist_ok=True)
    import websocket
    OUT=args.output
    for key in list(os.environ):
     if key.lower().endswith('_proxy'):os.environ.pop(key,None)
    URL='wss://jetstream.us-east.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents?collections=app.bsky.feed.post&kinds=commit'
    result={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'url':URL,'connections_attempted':1,'connection_opened':False,'maximum_seconds':20,'maximum_frames':10,'maximum_text_records':3,'maximum_frame_bytes':2000000,'dependency':'websocket-client=='+websocket.__version__,'credentials_supplied':False,'raw_text_saved':False,'author_values_saved':False,'reconnect_attempts':0,'error':None,'frames_received':0,'operations':{},'records':[],'resume_replay_delete_handling':'NOT_TESTED'}
    client=None;start=time.monotonic()
    try:
     client=websocket.create_connection(URL,subprotocols=['xrpc.v1.json'],timeout=8,redirect_limit=0)
     result['connection_opened']=True
     while time.monotonic()-start<20 and result['frames_received']<10 and len(result['records'])<3:
      client.settimeout(min(8,max(.1,20-(time.monotonic()-start))))
      frame=client.recv()
      if not frame:break
      result['frames_received']+=1
      if len(frame)>2000000:raise ValueError('frame_size_limit')
      data=json.loads(frame);event=data.get('payload',{})
      operation=event.get('operation','unknown');result['operations'][operation]=result['operations'].get(operation,0)+1
      record=event.get('record',{})
      if event.get('collection')=='app.bsky.feed.post' and operation in ('create','update') and isinstance(record.get('text'),str):
       text=record['text'];key='at://'+str(event.get('did',''))+'/app.bsky.feed.post/'+str(event.get('rkey',''))
       result['records'].append({'fingerprint':hashlib.sha256(key.encode()).hexdigest(),'operation':operation,'has_text':bool(text.strip()),'characters':len(text.strip()),'words':len(text.split()),'has_created_at':bool(record.get('createdAt')),'has_sequence':event.get('seq') is not None,'has_event_time':bool(event.get('time'))})
    except Exception as exc:result['error']=type(exc).__name__
    finally:
     if client:client.close()
    result['duration_seconds']=round(time.monotonic()-start,3)
    (OUT/'bluesky_jetstream_recheck.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('connection_opened','frames_received','operations','error','dependency')}));print('text_records',len(result['records']))


if __name__ == "__main__":
    main()
