"""Real loopback transport latency, independent of model/policy semantics."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
import pytest

from integration.bridge_signing import bridge_signature
from pentagi.live_engagement import LiveEngagement


def test_governed_route_waits_for_delayed_confirmation_without_duplicate_delivery():
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append((payload,self.headers.get('X-Kayan-Bridge')))
            time.sleep(2.2)  # Exceeds the general snapshot client's original 2s budget.
            body=b'{"delivered":true,"id":"one-delivery"}'
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        with httpx.Client(timeout=2.0)as client:
            runtime=SimpleNamespace(engagement_id='latency-test',_console=client,console_url=f'http://127.0.0.1:{server.server_port}')
            result=LiveEngagement._route(runtime,SimpleNamespace(agent_id='planner'),SimpleNamespace(agent_id='recon'),'Inspect owned lab')
        assert result['delivered'] and len(received)==1
        payload,signature=received[0];assert signature==bridge_signature(payload)
        assert payload=={'engagement_id':'latency-test','sender_agent_id':'planner','recipient_agent_id':'recon','text':'Inspect owned lab'}
    finally:
        server.shutdown();server.server_close();worker.join(timeout=3)


def test_ambiguous_route_timeout_stops_without_automatic_resend():
    calls=[]
    def transport(request):
        calls.append(request)
        raise httpx.ReadTimeout('delayed',request=request)
    with httpx.Client(transport=httpx.MockTransport(transport))as client:
        runtime=SimpleNamespace(engagement_id='latency-test',_console=client,console_url='http://127.0.0.1:8001')
        with pytest.raises(RuntimeError,match='delivery may have occurred.*No automatic resend'):
            LiveEngagement._route(runtime,SimpleNamespace(agent_id='planner'),SimpleNamespace(agent_id='recon'),'Inspect owned lab')
    assert len(calls)==1
