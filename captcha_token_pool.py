import asyncio
import redis.asyncio as redis
from typing import Optional
import time  

from captcha_solver import solve_captcha


class CaptchaTokenPool:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        pool_size: int = 5,
        token_lifetime: int = 48,
        token_min_age: int = 10,  
        captcha_key: Optional[str] = None
    ):
        self.redis_url = redis_url
        self.pool_size = pool_size
        self.token_lifetime = token_lifetime
        self.token_min_age = token_min_age  
        self.captcha_key = captcha_key
        
        self.redis_client: Optional[redis.Redis] = None
        self.token_key_prefix = "captcha_token:"
        self.token_meta_prefix = "captcha_meta:"  
        self.is_running = False
        self.generator_task: Optional[asyncio.Task] = None
        
        self.need_tokens_event = asyncio.Event()
        self._connection_verified = False
    
    async def connect(self):
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5
            )
            await self.redis_client.ping()
            self._connection_verified = True
            print(f"[TokenPool] Connected to Redis at {self.redis_url}")
        except redis.ConnectionError as e:
            print(f"[TokenPool] Failed to connect to Redis: {e}")
            raise RuntimeError(f"Redis connection failed. Is Redis running at {self.redis_url}?") from e
        except Exception as e:
            print(f"[TokenPool] Unexpected error connecting to Redis: {e}")
            raise
    
    async def disconnect(self):
        if self.redis_client:
            await self.redis_client.close()
            print("[TokenPool] Disconnected from Redis")
    
    async def start_generator(self):
        if not self._connection_verified:
            raise RuntimeError("Redis connection not verified. Call connect() first.")
        
        if self.is_running:
            print("[TokenPool] Generator already running")
            return
        
        self.is_running = True
        self.generator_task = asyncio.create_task(self._token_generator_loop())
        print("[TokenPool] Started token generator")
        print(f"  - Pool size: {self.pool_size}")
        print(f"  - Lifetime: {self.token_lifetime}s")
        print(f"  - Min age: {self.token_min_age}s (tokens 'mature' before use)")
    
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
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while self.is_running:
            try:
                current_size = await self.get_pool_size()
                
                if current_size >= self.pool_size:
                    print(f"[TokenPool] Pool full ({current_size}/{self.pool_size}), waiting...")
                    
                    try:
                        await asyncio.wait_for(
                            self.need_tokens_event.wait(),
                            timeout=30.0
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
                failure_count = tokens_needed - success_count
                
                print(f"[TokenPool] Generated {success_count}/{tokens_needed} tokens successfully")
                
                if failure_count > 0:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        print(f"[TokenPool] {consecutive_failures} consecutive failures. Increasing delay.")
                        await asyncio.sleep(10)
                else:
                    consecutive_failures = 0
                
                await asyncio.sleep(2)
            
            except asyncio.CancelledError:
                print("[TokenPool] Generator loop cancelled")
                break
            except redis.ConnectionError as e:
                print(f"[TokenPool] Redis connection lost: {e}")
                await asyncio.sleep(5)
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
            
            token_key = f"{self.token_key_prefix}{token}"
            await self.redis_client.setex(
                token_key,
                self.token_lifetime,
                "1"
            )
            
            meta_key = f"{self.token_meta_prefix}{token}"
            created_at = int(time.time())
            await self.redis_client.setex(
                meta_key,
                self.token_lifetime,
                str(created_at)
            )
            
            print(f"[TokenPool] Token stored: {token[:20]}... (TTL: {self.token_lifetime}s)")
            return True
        
        except redis.ConnectionError as e:
            print(f"[TokenPool] Redis error storing token: {e}")
            return False
        except Exception as e:
            print(f"[TokenPool] Failed to generate token: {e}")
            return False
    
    async def get_token(self) -> Optional[str]:
        try:
            current_time = int(time.time())
            
            async for key in self.redis_client.scan_iter(f"{self.token_key_prefix}*", count=100):
                token = key.replace(self.token_key_prefix, "")
                
                ttl = await self.redis_client.ttl(key)
                if ttl <= 1:
                    await self.redis_client.delete(key)
                    continue
                
                meta_key = f"{self.token_meta_prefix}{token}"
                created_at_str = await self.redis_client.get(meta_key)
                
                if created_at_str:
                    created_at = int(created_at_str)
                    age = current_time - created_at
                    
                    if age < self.token_min_age:
                        print(f"[TokenPool] Token too young: {age}s < {self.token_min_age}s, skipping...")
                        continue
                    
                    print(f"[TokenPool] Token age: {age}s (>= {self.token_min_age}s) ✓")
                
                await self.redis_client.delete(key)
                await self.redis_client.delete(meta_key)
                
                current_size = await self.get_pool_size()
                print(f"[TokenPool] Token retrieved: {token[:20]}... (pool: {current_size}/{self.pool_size})")
                
                self.need_tokens_event.set()
                
                return token
            
            print("[TokenPool] No mature tokens available (all too young or expired)")
            return None
        
        except redis.ConnectionError as e:
            print(f"[TokenPool] Redis error getting token: {e}")
            return None
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
    
    async def get_pool_stats(self) -> dict:
        try:
            size = await self.get_pool_size()
            tokens_info = []
            current_time = int(time.time())
            
            async for key in self.redis_client.scan_iter(f"{self.token_key_prefix}*", count=100):
                token = key.replace(self.token_key_prefix, "")
                ttl = await self.redis_client.ttl(key)
                
                meta_key = f"{self.token_meta_prefix}{token}"
                created_at_str = await self.redis_client.get(meta_key)
                age = current_time - int(created_at_str) if created_at_str else 0
                
                tokens_info.append({
                    "token": token[:20] + "...",
                    "ttl": ttl,
                    "age": age,
                    "mature": age >= self.token_min_age
                })
            
            return {
                "size": size,
                "capacity": self.pool_size,
                "utilization": f"{(size/self.pool_size)*100:.1f}%",
                "tokens": tokens_info
            }
        except Exception as e:
            print(f"[TokenPool] Error getting stats: {e}")
            return {}
    
    async def clear_pool(self):
        try:
            keys = []
            async for key in self.redis_client.scan_iter(f"{self.token_key_prefix}*"):
                keys.append(key)
            async for key in self.redis_client.scan_iter(f"{self.token_meta_prefix}*"):
                keys.append(key)
            
            if keys:
                await self.redis_client.delete(*keys)
                print(f"[TokenPool] Cleared {len(keys)} items from pool")
            else:
                print("[TokenPool] Pool already empty")
        except Exception as e:
            print(f"[TokenPool] Error clearing pool: {e}")