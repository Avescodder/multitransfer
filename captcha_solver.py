import asyncio
import httpx
from typing import Optional

from config import config


class TwoCaptchaSolver:
    BASE_URL = "https://2captcha.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def solve_yandex(
        self, 
        sitekey: str, 
        page_url: str, 
        priority: int = config.PRIORITY
    ) -> Optional[str]:
        try:
            task_id = await self._create_task(sitekey, page_url, priority)
            if not task_id:
                return None
            
            return await self._get_result(task_id)
        except Exception as e:
            print(f"[2Captcha] Error: {e}")
            return None
    
    async def _create_task(
        self, 
        sitekey: str, 
        page_url: str, 
        priority: int
    ) -> Optional[str]:
        payload = {
            "key": self.api_key,
            "method": "yandex",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }
        
        if priority >= 5:
            payload["pingback"] = f"priority_{priority}"
        
        response = await self.client.post(f"{self.BASE_URL}/in.php", data=payload)
        data = response.json()
        
        if data.get("status") == 1:
            task_id = data.get("request")
            print(f"[2Captcha] Task created: {task_id} (priority: {priority})")
            return task_id
        
        print(f"[2Captcha] Task creation failed: {data}")
        return None
    
    async def _get_result(
        self, 
        task_id: str, 
        max_attempts: int = 60,
        poll_interval: int = 2
    ) -> Optional[str]:
        params = {
            "key": self.api_key,
            "action": "get",
            "id": task_id,
            "json": 1
        }
        
        for attempt in range(max_attempts):
            await asyncio.sleep(poll_interval)
            
            response = await self.client.get(f"{self.BASE_URL}/res.php", params=params)
            data = response.json()
            
            if data.get("status") == 1:
                token = data.get("request")
                print(f"[2Captcha] Task {task_id} solved in {(attempt + 1) * poll_interval}s")
                return token
            
            if data.get("request") == "CAPCHA_NOT_READY":
                if (attempt + 1) % 10 == 0:  
                    print(f"[2Captcha] Task {task_id} still processing... ({(attempt + 1) * poll_interval}s)")
                continue
            
            print(f"[2Captcha] Unexpected response: {data}")
            return None
        
        print(f"[2Captcha] Timeout waiting for task {task_id}")
        return None
    
    async def get_balance(self) -> Optional[float]:
        try:
            params = {
                "key": self.api_key,
                "action": "getbalance",
                "json": 1
            }
            
            response = await self.client.get(f"{self.BASE_URL}/res.php", params=params)
            data = response.json()
            
            if data.get("status") == 1:
                balance = float(data.get("request", 0))
                print(f"[2Captcha] Balance: {balance:.2f}р")
                return balance
            
            return None
        except Exception as e:
            print(f"[2Captcha] Balance check error: {e}")
            return None
    
    async def close(self):
        await self.client.aclose()


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
        
        print("[RucaptchaSolver] Timeout waiting for result")
        return None
    
    async def close(self):
        await self.client.aclose()


async def solve_captcha(
    sitekey: str, 
    page_url: str = "https://multitransfer.ru",
    priority: int = 10,
    service: str = config.CAPTCHA_SERVICE
) -> Optional[str]:
    
    if service == "2captcha":
        solver = TwoCaptchaSolver(config.CAPTCHA_API_KEY)
    else:
        solver = RucaptchaSolver(config.CAPTCHA_API_KEY)
    
    try:
        if isinstance(solver, TwoCaptchaSolver):
            await solver.get_balance()
        
        return await solver.solve_yandex(sitekey, page_url, priority)
    finally:
        await solver.close()