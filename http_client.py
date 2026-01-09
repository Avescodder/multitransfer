import uuid
import httpx
from typing import Optional, Dict, Any


class AsyncHttpClient:
    def __init__(self, proxy: Optional[str] = None, headers: Optional[Dict[str, str]] = None):
        self.client = httpx.AsyncClient(
            proxy=proxy,
            headers=headers or {},
            follow_redirects=True,
            timeout=60.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            transport=httpx.AsyncHTTPTransport(retries=0)
        )
    
    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        return await self.client.request(
            method=method,
            url=url,
            headers=headers,
            json=json,
            params=params
        )
    
    async def close(self):
        await self.client.aclose()


def generate_headers(user_agent: str, fhpsessionid: str) -> Dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru,en;q=0.9",
        "Client-Id": "multitransfer-web-id",
        "Content-Type": "application/json",
        "Fhprequestid": str(uuid.uuid4()),
        "Fhpsessionid": fhpsessionid,
        "Priority": "u=1, i",
        "X-Request-Id": str(uuid.uuid4()),
        "Referer": "https://multitransfer.ru/",
        "Origin": "https://multitransfer.ru"
    }