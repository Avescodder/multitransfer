import asyncio
import random
import uuid
import time
import re
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

import httpx

from config.config import (
    USER_AGENTS, FIRST_NAMES, LAST_NAMES, MIDDLE_NAMES,
    CARD_COUNTRIES, generate_passport_dates
)


CARD_COUNTRY = CARD_COUNTRIES["TJK"]


# =========================================================
# Proxy Pool
# =========================================================

class ProxyPool:
    """
    Thread-safe proxy pool with health tracking and auto-recovery.
    """
    
    def __init__(self, proxies: List[str], recovery_time: int = 300):
        """
        Args:
            proxies: List of proxy URLs (e.g. "http://user:pass@host:port")
            recovery_time: Seconds before retrying failed proxy (default: 5 min)
        """
        self.proxies = proxies
        self.recovery_time = recovery_time
        
        self.available = asyncio.Queue()
        self.failed: Dict[str, float] = {}  # proxy -> failed_at timestamp
        self.stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"success": 0, "failed": 0})
        self.lock = asyncio.Lock()
        
        for p in proxies:
            self.available.put_nowait(p)
    
    async def get(self) -> Optional[str]:
        """Get an available proxy. Returns None if all proxies failed."""
        # Try to recover expired proxies first
        await self._recover_expired_proxies()
        
        if self.available.empty():
            # All proxies are currently failed
            return None
        
        return await self.available.get()
    
    async def release(self, proxy: str, success: bool = True):
        """
        Return proxy to pool.
        
        Args:
            proxy: Proxy URL
            success: Whether the operation was successful
        """
        async with self.lock:
            if success:
                self.stats[proxy]["success"] += 1
                await self.available.put(proxy)
            else:
                self.stats[proxy]["failed"] += 1
                self.failed[proxy] = time.time()
    
    async def _recover_expired_proxies(self):
        """Move expired failed proxies back to available pool."""
        now = time.time()
        async with self.lock:
            recovered = []
            for proxy, failed_at in list(self.failed.items()):
                if now - failed_at >= self.recovery_time:
                    recovered.append(proxy)
            
            for proxy in recovered:
                del self.failed[proxy]
                await self.available.put(proxy)
    
    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get proxy statistics."""
        return dict(self.stats)


# =========================================================
# Cache
# =========================================================

class Cache:
    """Global cache for build_id and captcha tokens."""
    
    build_id: Optional[str] = None
    build_id_expires: float = 0
    build_id_lock = asyncio.Lock()
    
    captcha_cache: Dict[str, Tuple[str, float]] = {}
    captcha_lock = asyncio.Lock()
    
    @classmethod
    async def get_build_id(cls, client: httpx.AsyncClient) -> str:
        """Get cached or fetch new build_id."""
        now = time.time()
        
        if cls.build_id and now < cls.build_id_expires:
            return cls.build_id
        
        async with cls.build_id_lock:
            if cls.build_id and now < cls.build_id_expires:
                return cls.build_id
            
            try:
                resp = await client.get("https://multitransfer.ru/", timeout=5.0)
                match = re.search(r'/_next/static/([^/]+)/_buildManifest\.js', resp.text)
                if match:
                    cls.build_id = match.group(1)
                    cls.build_id_expires = now + 3600
                    return cls.build_id
            except:
                pass
            
            # Fallback
            cls.build_id = "L8H5E8MPmOkkA0naeeocl"
            cls.build_id_expires = now + 3600
            return cls.build_id
    
    @classmethod
    async def get_or_solve_captcha(cls, key: str, solver, api_key: str, client: httpx.AsyncClient) -> str:
        """Get cached captcha token or solve new one."""
        now = time.time()
        
        async with cls.captcha_lock:
            if key in cls.captcha_cache:
                token, expires = cls.captcha_cache[key]
                if now < expires:
                    return token
                del cls.captcha_cache[key]
        
        token = await solver(key, api_key, client)
        
        async with cls.captcha_lock:
            cls.captcha_cache[key] = (token, time.time() + 90)
        
        return token
    
    @classmethod
    async def invalidate_captcha(cls, key: str):
        """Invalidate cached captcha token."""
        async with cls.captcha_lock:
            if key in cls.captcha_cache:
                del cls.captcha_cache[key]


# =========================================================
# Captcha Solver
# =========================================================

async def solve_captcha(key: str, api_key: str, client: httpx.AsyncClient) -> str:
    """
    Solve Yandex SmartCaptcha using RuCaptcha API.
    
    Raises:
        RuntimeError: If captcha solving fails
    """
    resp = await client.post(
        "https://rucaptcha.com/in.php",
        data={
            "key": api_key,
            "method": "yandex",
            "sitekey": key,
            "pageurl": "https://multitransfer.ru",
            "json": 1
        },
        timeout=15.0
    )
    
    result = resp.json()
    if result.get("status") != 1:
        raise RuntimeError(f"Captcha submit failed: {result.get('request')}")
    
    captcha_id = result["request"]
    
    # Poll for result (max 40 seconds)
    for _ in range(40):
        await asyncio.sleep(1.0)
        
        resp = await client.get(
            "https://rucaptcha.com/res.php",
            params={"key": api_key, "action": "get", "id": captcha_id, "json": 1},
            timeout=8.0
        )
        
        result = resp.json()
        
        if result.get("status") == 1:
            return result["request"]
        
        if result.get("request") != "CAPCHA_NOT_READY":
            raise RuntimeError(f"Captcha polling failed: {result.get('request')}")
    
    raise RuntimeError("Captcha timeout (40s)")


# =========================================================
# Result
# =========================================================

@dataclass
class QRResult:
    """Result of QR generation."""
    success: bool
    transfer_id: Optional[str] = None
    transfer_num: Optional[str] = None
    qr_payload: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0
    attempts: int = 0
    proxy_used: Optional[str] = None


# =========================================================
# Core QR Generation
# =========================================================

async def create_qr(
    amount: int,
    api_key: str,
    client: httpx.AsyncClient,
    retries: int = 4,
    proxy: Optional[str] = None
) -> QRResult:
    """
    Create QR code for transfer.
    
    Args:
        amount: Transfer amount in RUB
        api_key: RuCaptcha API key
        client: HTTP client
        retries: Number of retry attempts
        proxy: Proxy used (for stats only)
    
    Returns:
        QRResult with success/error info
    """
    start = time.time()
    captcha_key = None
    
    for attempt in range(retries + 1):
        try:
            session_id = str(uuid.uuid4())
            user_agent = random.choice(USER_AGENTS)
            
            headers = {
                "User-Agent": user_agent,
                "client-id": "multitransfer-web-id",
                "fhpsessionid": session_id,
                "content-type": "application/json",
                "Accept": "application/json, text/plain, */*",
            }
            
            # Get build_id
            build_id = await Cache.get_build_id(client)
            
            # Get captcha key
            resp = await client.get(
                f"https://multitransfer.ru/_next/data/{build_id}/ru/transfer/tajikistan/sender-details.json",
                params={"country": "tajikistan"},
                headers={**headers, "referer": "https://multitransfer.ru/"},
                timeout=8.0
            )
            
            if resp.status_code != 200 or not resp.text:
                if attempt < retries:
                    await asyncio.sleep(0.5 * (1.5 ** attempt))
                    continue
                raise RuntimeError(f"Captcha key fetch failed: {resp.status_code}")
            
            captcha_key = resp.json()["pageProps"]["captcha_key"]
            
            # Solve captcha
            captcha_token = await Cache.get_or_solve_captcha(
                captcha_key, solve_captcha, api_key, client
            )
            
            # Calculate commission
            resp = await client.post(
                "https://api.multitransfer.ru/anonymous/multi/multitransfer-fee-calc/v3/commissions",
                headers={**headers, "fhprequestid": str(uuid.uuid4()), "x-request-id": str(uuid.uuid4())},
                json={
                    "countryCode": CARD_COUNTRY["countryCode"],
                    "range": "ALL_PLUS_LIMITS",
                    "money": {
                        "acceptedMoney": {"amount": amount, "currencyCode": CARD_COUNTRY["currencyFrom"]},
                        "withdrawMoney": {"currencyCode": CARD_COUNTRY["currencyTo"]},
                    },
                },
                timeout=10.0
            )
            
            if resp.status_code != 200:
                if resp.status_code in [502, 503, 504] and attempt < retries:
                    await asyncio.sleep(0.5 * (1.5 ** attempt))
                    continue
                raise RuntimeError(f"Commission calc failed: {resp.status_code}")
            
            data = resp.json()
            commission_id = data["fees"][0]["commissions"][0]["commissionId"]
            payment_system_id = data["fees"][0]["commissions"][0]["paymentSystemId"]
            
            # Generate random data
            passport = generate_passport_dates()
            card_number = f"505827{random.randint(1000000000, 9999999999)}"
            
            # Create transfer
            resp = await client.post(
                "https://api.multitransfer.ru/anonymous/multi/multitransfer-transfer-create/v3/anonymous/transfers/create",
                headers={
                    **headers,
                    "fhptokenid": captcha_token,
                    "fhprequestid": str(uuid.uuid4()),
                    "x-request-id": str(uuid.uuid4()),
                },
                json={
                    "transfer": {
                        "paymentSystemId": payment_system_id,
                        "countryCode": CARD_COUNTRY["countryCode"],
                        "beneficiaryAccountNumber": card_number,
                        "commissionId": commission_id,
                        "paymentInstrument": {"type": "ANONYMOUS_CARD"}
                    },
                    "sender": {
                        "lastName": random.choice(LAST_NAMES),
                        "firstName": random.choice(FIRST_NAMES),
                        "middleName": random.choice(MIDDLE_NAMES),
                        "birthDate": passport["birth_date"],
                        "phoneNumber": f"79{random.randint(100000000, 999999999)}",
                        "documents": [{
                            "type": "21",
                            "series": f"{random.randint(10, 99)}{random.randint(10, 99)}",
                            "number": str(random.randint(100000, 999999)),
                            "issueDate": passport["issue_date"],
                            "countryCode": "RUS",
                        }],
                    },
                },
                timeout=10.0
            )
            
            if resp.status_code != 201:
                try:
                    resp_data = resp.json()
                    error_code = resp_data.get("error", {}).get("code")
                    
                    # Captcha errors - invalidate and retry
                    if error_code in [103, 400, 403]:
                        if captcha_key:
                            await Cache.invalidate_captcha(captcha_key)
                        if attempt < retries:
                            await asyncio.sleep(0.5 * (1.5 ** attempt))
                            continue
                    
                    raise RuntimeError(f"Transfer create failed: {resp.status_code}, code: {error_code}")
                except Exception as e:
                    if attempt < retries:
                        await asyncio.sleep(0.5 * (1.5 ** attempt))
                        continue
                    raise RuntimeError(f"Transfer create failed: {resp.status_code}")
            
            resp_data = resp.json()
            
            if "transferId" not in resp_data:
                error_code = resp_data.get("error", {}).get("code")
                if error_code in [103, 400, 403]:
                    if captcha_key:
                        await Cache.invalidate_captcha(captcha_key)
                    if attempt < retries:
                        await asyncio.sleep(0.5 * (1.5 ** attempt))
                        continue
                raise KeyError(f"No transferId in response: {error_code}")
            
            transfer_id = resp_data["transferId"]
            transfer_num = resp_data["transferNum"]
            
            # Confirm and get QR
            resp = await client.post(
                "https://api.multitransfer.ru/anonymous/multi/multitransfer-qr-processing/v3/anonymous/confirm",
                headers={**headers, "fhprequestid": str(uuid.uuid4()), "x-request-id": str(uuid.uuid4())},
                json={"transactionId": transfer_id, "recordType": "transfer"},
                timeout=10.0
            )
            
            if resp.status_code != 200:
                raise RuntimeError(f"QR confirm failed: {resp.status_code}")
            
            qr_payload = resp.json()["externalData"]["payload"]
            
            return QRResult(
                success=True,
                transfer_id=transfer_id,
                transfer_num=transfer_num,
                qr_payload=qr_payload,
                duration=time.time() - start,
                attempts=attempt + 1,
                proxy_used=proxy
            )
            
        except Exception as e:
            if attempt == retries:
                return QRResult(
                    success=False,
                    error=str(e),
                    duration=time.time() - start,
                    attempts=attempt + 1,
                    proxy_used=proxy
                )
            
            # Exponential backoff
            await asyncio.sleep(0.5 * (1.5 ** attempt))
    
    return QRResult(
        success=False,
        error="Max retries exceeded",
        duration=time.time() - start,
        attempts=retries + 1,
        proxy_used=proxy
    )


# =========================================================
# QR Pool
# =========================================================

class QRPool:
    """
    High-performance QR generation pool with proxy rotation.
    """
    
    def __init__(
        self,
        api_key: str,
        max_concurrent: int = 3,
        proxy_pool: Optional[ProxyPool] = None,
        single_proxy: Optional[str] = None
    ):
        """
        Args:
            api_key: RuCaptcha API key
            max_concurrent: Max concurrent operations
            proxy_pool: ProxyPool instance for rotation
            single_proxy: Single proxy URL (alternative to proxy_pool)
        """
        self.api_key = api_key
        self.max_concurrent = max_concurrent
        self.proxy_pool = proxy_pool
        self.single_proxy = single_proxy
        
        self.sem = asyncio.Semaphore(max_concurrent)
        self.clients: Dict[str, httpx.AsyncClient] = {}
        self.main_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        if not self.proxy_pool and self.single_proxy:
            # Single proxy mode
            self.main_client = httpx.AsyncClient(
                timeout=20.0,
                limits=httpx.Limits(
                    max_connections=30,
                    max_keepalive_connections=20,
                    keepalive_expiry=60.0
                ),
                proxy=self.single_proxy,
                follow_redirects=True
            )
        return self
    
    async def __aexit__(self, *args):
        # Close all clients
        if self.main_client:
            await self.main_client.aclose()
        
        for client in self.clients.values():
            await client.aclose()
        
        self.clients.clear()
    
    async def _get_client(self, proxy: Optional[str]) -> httpx.AsyncClient:
        """Get or create HTTP client for proxy."""
        if proxy is None:
            if self.main_client:
                return self.main_client
            
            # Create default client
            if "default" not in self.clients:
                self.clients["default"] = httpx.AsyncClient(
                    timeout=20.0,
                    limits=httpx.Limits(
                        max_connections=30,
                        max_keepalive_connections=20,
                        keepalive_expiry=60.0
                    ),
                    follow_redirects=True
                )
            return self.clients["default"]
        
        # Proxy-specific client
        if proxy not in self.clients:
            self.clients[proxy] = httpx.AsyncClient(
                timeout=20.0,
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                    keepalive_expiry=30.0
                ),
                proxy=proxy,
                follow_redirects=True
            )
        
        return self.clients[proxy]
    
    async def generate(self, amount: int) -> QRResult:
        """Generate single QR code."""
        proxy = None
        
        try:
            # Get proxy if pool available
            if self.proxy_pool:
                proxy = await self.proxy_pool.get()
                if proxy is None:
                    return QRResult(
                        success=False,
                        error="No available proxies",
                        duration=0
                    )
            
            # Rate limiting
            async with self.sem:
                client = await self._get_client(proxy or self.single_proxy)
                result = await create_qr(amount, self.api_key, client, proxy=proxy)
            
            return result
            
        finally:
            # Return proxy to pool
            if self.proxy_pool and proxy:
                await self.proxy_pool.release(proxy, result.success if 'result' in locals() else False)
    
    async def generate_batch(self, amounts: List[int]) -> List[QRResult]:
        """Generate multiple QR codes concurrently."""
        return await asyncio.gather(*[self.generate(amt) for amt in amounts])