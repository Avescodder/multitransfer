import asyncio
import httpx
from typing import Optional

from config import config


class RucaptchaSolver:
    BASE_URL = "https://rucaptcha.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def solve_yandex(self, sitekey: str, page_url: str, priority: int = 10) -> Optional[str]:
        try:
            task_id = await self._create_task(sitekey, page_url, priority)
            if not task_id:
                return None
            
            return await self._get_result(task_id)
        except Exception as e:
            print(f"[RucaptchaSolver] Error: {e}")
            return None
    
    async def _create_task(self, sitekey: str, page_url: str, priority: int) -> Optional[str]:
        payload = {
            "key": self.api_key,
            "method": "yandex",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1,
            "priority": priority
        }
        
        response = await self.client.post(f"{self.BASE_URL}/in.php", data=payload)
        data = response.json()
        
        if data.get("status") == 1:
            return data.get("request")
        
        print(f"[RucaptchaSolver] Task creation failed: {data}")
        return None
    
    async def _get_result(self, task_id: str, max_attempts: int = 60) -> Optional[str]:
        params = {"key": self.api_key, "action": "get", "id": task_id, "json": 1}
        
        for _ in range(max_attempts):
            await asyncio.sleep(2)
            
            response = await self.client.get(f"{self.BASE_URL}/res.php", params=params)
            data = response.json()
            
            if data.get("status") == 1:
                return data.get("request")
            
            if data.get("request") != "CAPCHA_NOT_READY":
                print(f"[RucaptchaSolver] Unexpected response: {data}")
                return None
        
        print(f"[RucaptchaSolver] Timeout waiting for result")
        return None
    
    async def close(self):
        await self.client.aclose()


async def solve_captcha(sitekey: str, page_url: str = "https://multitransfer.ru") -> Optional[str]:
    solver = RucaptchaSolver(config.RUCAPTCHA_API_KEY)
    try:
        return await solver.solve_yandex(sitekey, page_url, priority=10)
    finally:
        await solver.close()