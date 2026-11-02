"""Issue narrowly scoped, local execution contexts from the actual signed ROE.

Tokens are written only to ignored local files, never printed or committed.
"""
import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

from integration.roe_signing import signing_key, sign_roe

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_TYPES = ['primary_agent','reporter','generator','refiner','reflector','enricher','adviser',
    'coder','memorist','searcher','installer','pentester','summarizer','tool_call_fixer','assistant']


def new_contract(operator='local PentAGI comparison operator', minutes=20):
    now = datetime.now(timezone.utc)
    roe = {'engagement_id':str(uuid.uuid4()),'authorized_by':operator,
        'scope':{'targets':['127.0.0.1','host.docker.internal'],
            'allowed_techniques':['recon','web-app','network','reporting','planning','workflow'], 'forbidden_actions':[]},
        'time_window':{'start':(now-timedelta(seconds=2)).isoformat(),'end':(now+timedelta(minutes=minutes)).isoformat()},
        'signature':''}
    roe['signature'] = sign_roe(roe)
    response = httpx.post('http://127.0.0.1:8000/roe/load',json=roe,timeout=10)
    response.raise_for_status()
    if response.json().get('status') != 'loaded':
        raise RuntimeError('TrustGate did not confirm the signed ROE load')
    return roe


def role_profile(role):
    origin = 'http://host.docker.internal:8888'
    marker = lambda: 'KAYAN_'+secrets.token_hex(8)
    evidence = {}
    if role == 'recon_agent':
        urls = [origin+'/',origin+'/api/products']
    elif role == 'network_agent':
        urls = [origin+'/']
    elif role == 'webapp_agent':
        xss,command,file = marker(),marker(),marker()
        payload = '<script>/*'+xss+'*/</script>'
        urls = [origin+'/search?'+urlencode({'q':payload}),
            origin+'/ping?'+urlencode({'host':'127.0.0.1 & echo '+command}),
            origin+'/file?'+urlencode({'path':'../kayan-trustgate/lab/fixtures/verification_marker.txt'})]
        fixture = ROOT/'lab/fixtures/verification_marker.txt'
        fixture.parent.mkdir(exist_ok=True)
        fixture.write_text(file,encoding='utf-8')
        evidence = {'xss':{'marker':xss,'payload':payload},'command_injection':{'marker':command},'path_traversal':{'marker':file}}
    else:
        urls = [origin+'/']
    commands = ["curl -q -s --max-time 5 '"+url+"'" for url in urls] if role in ('recon_agent','webapp_agent','network_agent') else []
    return {'role':role,'allowed_endpoints':urls,'approved_commands':commands,'expected_evidence':evidence}


def issue(roe, user_id, profile):
    if profile['role'] not in ('planner_agent','recon_agent','webapp_agent','network_agent','reporting_agent'):
        raise ValueError('Unknown security capability role')
    payload = {'version':1,'engagement_id':roe['engagement_id'],'operator_user_id':user_id,
        'expires_at':roe['time_window']['end'],
        'agents':{kind:{'agent_id':f"{roe['engagement_id']}:{profile['role']}:{kind}",'role':profile['role']} for kind in UPSTREAM_TYPES},
        'allowed_endpoints':profile['allowed_endpoints'],'approved_commands':profile['approved_commands']}
    raw = json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode()
    signature = hmac.new(signing_key().encode(),b'kayan-pentagi-governance-v1:'+raw,hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(raw).rstrip(b'=').decode()+'.'+signature
    directory = ROOT/'data/pentagi_governance'
    directory.mkdir(exist_ok=True)
    path = directory/(roe['engagement_id']+'_'+profile['role']+'.token')
    with path.open('x',encoding='utf-8') as output:
        output.write(token)
    return token,path
