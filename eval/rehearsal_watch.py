"""Read-only timestamped observation of a fresh console engagement, not pixels."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

import websockets


async def watch(output):
    path = Path(output)
    with path.open('x',encoding='utf-8',newline='\n') as log:
        async with websockets.connect('ws://127.0.0.1:8001/ws',max_size=16*1024*1024) as socket:
            initial = json.loads(await socket.recv())['data'].get('engagement_id')
            seen, previous, engagement = {}, None, None
            print('WATCHING for engagement after '+str(initial),flush=True)
            async with asyncio.timeout(360):
                while True:
                    state = json.loads(await socket.recv())['data']
                    eid = state.get('engagement_id')
                    if not eid or eid == initial:
                        continue
                    if engagement is None:
                        engagement = eid
                        print('OBSERVED NEW ENGAGEMENT '+eid,flush=True)
                    if eid != engagement:
                        raise RuntimeError('Another engagement replaced the rehearsal')
                    now = datetime.now(timezone.utc).isoformat()
                    agents = {a['role']:{'status':a['status'],'task':a.get('current_task'),'tier':a.get('model_tier')} for a in state.get('agents',[])}
                    phase = {'status':state['status'],'agents':agents}
                    if phase != previous:
                        event = {'observed_at':now,'engagement_id':eid,'type':'phase',**phase}
                        log.write(json.dumps(event)+'\n');log.flush()
                        print(json.dumps(event),flush=True)
                        previous = phase
                    for entry in state.get('transcript',[]):
                        signature = (entry.get('kind'),len(str(entry.get('output',''))),str(entry.get('result','')))
                        if seen.get(entry['id']) == signature:
                            continue
                        seen[entry['id']] = signature
                        event = {'observed_at':now,'engagement_id':eid,'type':'transcript',
                            **{k:entry[k] for k in ('id','seq','timestamp','agent_id','agent_role','kind','content','tool_name','decision','audit_entry_id') if k in entry},
                            'output_characters':len(str(entry.get('output','')))}
                        log.write(json.dumps(event,ensure_ascii=False)+'\n');log.flush()
                        if entry['kind'] in ('tool_started','finding_verified','report_saved','roe_loaded'):
                            print(json.dumps(event,ensure_ascii=False),flush=True)
                    if state['status'] in ('failed','completed') and all(m.get('status')!='answering' for m in state.get('messages',[])):
                        final = {'observed_at':now,'engagement_id':eid,'type':'final','status':state['status'],
                            'findings':len(state.get('findings',[])),'transcript_entries':len(state.get('transcript',[])),
                            'limit':'HTTP/WebSocket observation, not rendered visual acceptance'}
                        log.write(json.dumps(final)+'\n');log.flush()
                        print(json.dumps(final),flush=True)
                        return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    asyncio.run(watch(parser.parse_args().output))
