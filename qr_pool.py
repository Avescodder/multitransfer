import asyncio
import random
import httpx
from typing import List, Dict, Any

from config import config
from qr_generator import QRGenerator


class QRGeneratorPool:
    
    def __init__(self, proxy: str, max_concurrent: int = 10):
        self.proxy = proxy
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        self.shared_client = httpx.AsyncClient(
            proxy=proxy,
            follow_redirects=True,
            timeout=60.0,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0
            ),
            transport=httpx.AsyncHTTPTransport(retries=0)
        )
    
    async def generate_single(
        self,
        amount: float,
        card_number: str,
        card_country: str = "TJK"
    ) -> Dict[str, Any]:
        async with self.semaphore:
            try:
                user_agent = random.choice(config.USER_AGENTS)
                
                generator = QRGenerator(
                    proxy=self.proxy,
                    user_agent=user_agent,
                    shared_client=self.shared_client
                )
                
                result = await generator.generate(amount, card_number, card_country)
                
                if result:
                    return {"success": True, **result}
                else:
                    return {"success": False, "error": "Generation failed"}
                    
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def generate_batch(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results = await asyncio.gather(*[
            self.generate_single(
                amount=task["amount"],
                card_number=task["card_number"],
                card_country=task.get("card_country", "TJK")
            )
            for task in tasks
        ], return_exceptions=True)
        
        processed = []
        for result in results:
            if isinstance(result, Exception):
                processed.append({"success": False, "error": str(result)})
            else:
                processed.append(result)
        
        return processed
    
    async def close(self):
        await self.shared_client.aclose()
