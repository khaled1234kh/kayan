"""Console/gate availability must not be confused with authorization."""
import httpx,pytest
from fastapi.testclient import TestClient
from console.backend import main

@pytest.mark.parametrize('payload,available',[
 ({'status':'ok','engine':'cedar-policy 4.14.0','roe_authentication':'HMAC-SHA256'},True),
 ({'status':'ok','engine':'unrelated service','roe_authentication':'HMAC-SHA256'},False),
 ({'status':'ok','engine':'cedar-policy 4.14.0'},False),
 ([],False),
 (None,False),
])
def test_runtime_health_is_fail_closed_and_never_grants_authority(monkeypatch,payload,available):
    class Client:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        async def get(self,url):
            assert url=='http://127.0.0.1:8000/health'
            if payload is None:raise httpx.ConnectError('controlled unavailable')
            return httpx.Response(200,json=payload,request=httpx.Request('GET',url))
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    with TestClient(main.app) as client:
        response=client.get('/runtime/health')
        assert response.status_code==200
        assert response.json()=={'gate':{'available':available},'live_execution_authorized':False}
