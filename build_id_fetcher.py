import re
import asyncio
import httpx
from typing import Optional

_cached_build_id: Optional[str] = None
_cache_lock = asyncio.Lock()


async def get_build_id(force_refresh: bool = False) -> Optional[str]:
    global _cached_build_id
    
    async with _cache_lock:
        if _cached_build_id and not force_refresh:
            return _cached_build_id
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get("https://multitransfer.ru/ru/transfer/tajikistan/sender-details")
                
                if response.status_code != 200:
                    return None
                
                html = response.text
                
                match = re.search(r'"buildId":"([^"]+)"', html)
                if not match:
                    return None
                
                _cached_build_id = match.group(1)
                return _cached_build_id
        
        except Exception as e:
            print(f"[BuildIdFetcher] Error: {e}")
            return None


async def refresh_build_id() -> Optional[str]:
    return await get_build_id(force_refresh=True)