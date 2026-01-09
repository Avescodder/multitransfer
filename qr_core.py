import asyncio
import random
import uuid
import time
import re
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

import httpx

from config.config import (
    USER_AGENTS, FIRST_NAMES, LAST_NAMES, MIDDLE_NAMES,
    CARD_COUNTRIES, generate_passport_dates
)


CARD_COUNTRY = CARD_COUNTRIES["TJK"]


class Cache:
    build_id: Optional[str] = None
    build_id_expires: float = 0
    build_id_lock = asyncio.Lock()
    
    captcha_cache: Dict[str, Tuple[str, float]] = {}
    captcha_lock = asyncio.Lock()
    
    @classmethod
    async def get_build_id(cls, client: httpx.AsyncClient) -> str:
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
            
            cls.build_id = "L8H5E8MPmOkkA0naeeocl"
            cls.build_id_expires = now + 3600
            return cls.build_id
    
    @classmethod
    async def get_or_solve_captcha(cls, key: str, solver, api_key: str, client: httpx.AsyncClient) -> str:
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
        async with cls.captcha_lock:
            if key in cls.captcha_cache:
                del cls.captcha_cache[key]


async def solve_captcha(key: str, api_key: str, client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "https://rucaptcha.com/in.php",
        data={"key": api_key, "method": "yandex", "sitekey": key, "pageurl": "https://multitransfer.ru", "json": 1},
        timeout=15.0
    )
    
    result = resp.json()
    if result.get("status") != 1:
        raise RuntimeError(f"Captcha submit: {result.get('request')}")
    
    captcha_id = result["request"]
    
    for i in range(40):
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
            raise RuntimeError(f"Captcha: {result.get('request')}")
    
    raise RuntimeError("Captcha timeout")


@dataclass
class QRResult:
    success: bool
    transfer_id: Optional[str] = None
    transfer_num: Optional[str] = None
    qr_payload: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0


async def create_qr(amount: int, api_key: str, client: httpx.AsyncClient, retries: int = 2) -> QRResult:
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
            
            build_id = await Cache.get_build_id(client)
            
            resp = await client.get(
                f"https://multitransfer.ru/_next/data/{build_id}/ru/transfer/tajikistan/sender-details.json",
                params={"country": "tajikistan"},
                headers={**headers, "referer": "https://multitransfer.ru/"},
                timeout=8.0
            )
            
            if resp.status_code != 200 or not resp.text:
                if attempt < retries:
                    await asyncio.sleep(0.5)
                    continue
                raise RuntimeError(f"Captcha key fetch: {resp.status_code}")
            
            captcha_key = resp.json()["pageProps"]["captcha_key"]
            
            captcha_token = await Cache.get_or_solve_captcha(captcha_key, solve_captcha, api_key, client)
            
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
                    await asyncio.sleep(1.0)
                    continue
                raise RuntimeError(f"Commission: {resp.status_code}")
            
            data = resp.json()
            commission_id = data["fees"][0]["commissions"][0]["commissionId"]
            payment_system_id = data["fees"][0]["commissions"][0]["paymentSystemId"]
            
            passport = generate_passport_dates()
            card_number = f"505827{random.randint(1000000000, 9999999999)}"
            
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
                    
                    if error_code in [103, 400, 403]:
                        if captcha_key:
                            await Cache.invalidate_captcha(captcha_key)
                        if attempt < retries:
                            await asyncio.sleep(1.0)
                            continue
                    
                    raise RuntimeError(f"Transfer {resp.status_code}: {error_code}")
                except:
                    if attempt < retries:
                        await asyncio.sleep(0.5)
                        continue
                    raise RuntimeError(f"Transfer: {resp.status_code}")
            
            resp_data = resp.json()
            
            if "transferId" not in resp_data:
                error_code = resp_data.get("error", {}).get("code")
                if error_code in [103, 400, 403]:
                    if captcha_key:
                        await Cache.invalidate_captcha(captcha_key)
                    if attempt < retries:
                        await asyncio.sleep(1.0)
                        continue
                raise KeyError(f"No transferId: {error_code}")
            
            transfer_id = resp_data["transferId"]
            transfer_num = resp_data["transferNum"]
            
            resp = await client.post(
                "https://api.multitransfer.ru/anonymous/multi/multitransfer-qr-processing/v3/anonymous/confirm",
                headers={**headers, "fhprequestid": str(uuid.uuid4()), "x-request-id": str(uuid.uuid4())},
                json={"transactionId": transfer_id, "recordType": "transfer"},
                timeout=10.0
            )
            
            if resp.status_code != 200:
                raise RuntimeError(f"Confirm: {resp.status_code}")
            
            qr_payload = resp.json()["externalData"]["payload"]
            
            return QRResult(
                success=True,
                transfer_id=transfer_id,
                transfer_num=transfer_num,
                qr_payload=qr_payload,
                duration=time.time() - start
            )
            
        except Exception as e:
            if attempt == retries:
                return QRResult(success=False, error=str(e), duration=time.time() - start)
            await asyncio.sleep(0.3)
    
    return QRResult(success=False, error="Max retries", duration=time.time() - start)


class QRPool:
    def __init__(self, api_key: str, max_concurrent: int = 5, proxy: Optional[str] = None):
        self.api_key = api_key
        self.max_concurrent = max_concurrent
        self.proxy = proxy
        self.client: Optional[httpx.AsyncClient] = None
        self.sem = asyncio.Semaphore(max_concurrent)
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=20.0,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=20, keepalive_expiry=60.0),
            proxy=self.proxy if self.proxy else None,
            follow_redirects=True
        )
        return self
    
    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()
    
    async def generate(self, amount: int) -> QRResult:
        async with self.sem:
            return await create_qr(amount, self.api_key, self.client)
    
    async def generate_batch(self, amounts: List[int]) -> List[QRResult]:
        return await asyncio.gather(*[self.generate(amt) for amt in amounts])