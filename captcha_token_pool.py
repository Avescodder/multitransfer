import asyncio
import redis.asyncio as redis
from typing import Optional
from captcha_solver import solve_captcha


class CaptchaTokenPool:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        pool_size: int = 10,
        token_lifetime: int = 8,
        captcha_key: Optional[str] = None
    ):
        self.redis_url = redis_url
        self.pool_size = pool_size
        self.token_lifetime = token_lifetime
        self.captcha_key = captcha_key
        
        self.redis_client: Optional[redis.Redis] = None
        self.token_key_prefix = "captcha_token:"
        self.is_running = False
        self.generator_task: Optional[asyncio.Task] = None
        
        self.need_tokens_event = asyncio.Event()
    
    async def connect(self):
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        print(f"[TokenPool] Connected to Redis at {self.redis_url}")
    
    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()
            print("[TokenPool] Disconnected from Redis")
    
    async def start_generator(self):
        if self.is_running:
            print("[TokenPool] Generator already running")
            return
        
        self.is_running = True
        self.generator_task = asyncio.create_task(self._token_generator_loop())
        print(f"[TokenPool] Started token generator (pool_size={self.pool_size}, lifetime={self.token_lifetime}s)")
    
    async def stop_generator(self):
        self.is_running = False
        if self.generator_task:
            self.generator_task.cancel()
            try:
                await self.generator_task
            except asyncio.CancelledError:
                pass
        print("[TokenPool] Stopped token generator")
    
    async def _token_generator_loop(self):
        while self.is_running:
            try:
                current_size = await self.get_pool_size()
                
                if current_size >= self.pool_size:
                    print(f"[TokenPool] Pool full ({current_size}/{self.pool_size}), waiting for tokens to be used")
                    
                    try:
                        await asyncio.wait_for(
                            self.need_tokens_event.wait(),
                            timeout=10.0
                        )
                    except asyncio.TimeoutError:
                        pass 
                    
                    self.need_tokens_event.clear()
                    continue
                
                tokens_needed = self.pool_size - current_size
                print(f"[TokenPool] Pool size: {current_size}/{self.pool_size}, generating {tokens_needed} tokens")
                
                tasks = [
                    self._generate_and_store_token()
                    for _ in range(tokens_needed)
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                success_count = sum(1 for r in results if r is True)
                print(f"[TokenPool] Generated {success_count}/{tokens_needed} tokens successfully")
                
                await asyncio.sleep(2)
            
            except asyncio.CancelledError:
                print("[TokenPool] Generator loop cancelled")
                break
            except Exception as e:
                print(f"[TokenPool] Error in generator loop: {e}")
                await asyncio.sleep(5)
    
    async def _generate_and_store_token(self) -> bool:
        try:
            token = await solve_captcha(
                sitekey=self.captcha_key,
                priority=10
            )
            
            if not token:
                return False
            
            key = f"{self.token_key_prefix}{token}"
            await self.redis_client.setex(
                key,
                self.token_lifetime,
                "1"  
            )
            
            print(f"[TokenPool] Token stored: {token[:20]} (TTL: {self.token_lifetime}s)")
            return True
        
        except Exception as e:
            print(f"[TokenPool] Failed to generate token: {e}")
            return False
    
    async def get_token(self) -> Optional[str]:
        try:
            keys = []
            async for key in self.redis_client.scan_iter(f"{self.token_key_prefix}*", count=10):
                keys.append(key)
                if len(keys) >= 1:
                    break
            
            if not keys:
                print("[TokenPool] No tokens available in pool")
                return None
            
            key = keys[0]
            token = key.replace(self.token_key_prefix, "")
            
            await self.redis_client.delete(key)
            
            current_size = await self.get_pool_size()
            print(f"[TokenPool] Token retrieved: {token[:20]} (pool size: {current_size}/{self.pool_size})")
            
            self.need_tokens_event.set()
            
            return token
        
        except Exception as e:
            print(f"[TokenPool] Error getting token: {e}")
            return None
    
    async def get_pool_size(self) -> int:
        try:
            count = 0
            async for _ in self.redis_client.scan_iter(f"{self.token_key_prefix}*", count=100):
                count += 1
            return count
        except Exception as e:
            print(f"[TokenPool] Error getting pool size: {e}")
            return 0
    
    async def clear_pool(self):
        try:
            keys = []
            async for key in self.redis_client.scan_iter(f"{self.token_key_prefix}*"):
                keys.append(key)
            
            if keys:
                await self.redis_client.delete(*keys)
                print(f"[TokenPool] Cleared {len(keys)} tokens from pool")
            else:
                print("[TokenPool] Pool already empty")
        except Exception as e:
            print(f"[TokenPool] Error clearing pool: {e}")