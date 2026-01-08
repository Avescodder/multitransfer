import asyncio
import random
import dotenv
import uuid
import time
import os
from datetime import datetime, timedelta

import httpx

from httpFlowRunner import FlowRunner, Step, ExtractRule
from config import config
from yamlManage import YamlManage
from config.config import CARD_COUNTRIES, DATES_PASSPORT

dotenv.load_dotenv()


class CaptchaCache:
    _cache = {}
    _lock = asyncio.Lock()
    
    @classmethod
    async def get(cls, captcha_key):
        async with cls._lock:
            if captcha_key in cls._cache:
                token, expires = cls._cache[captcha_key]
                if datetime.now() < expires:
                    return token
                del cls._cache[captcha_key]
        return None
    
    @classmethod
    async def set(cls, captcha_key, token):
        async with cls._lock:
            expires = datetime.now() + timedelta(seconds=110)
            cls._cache[captcha_key] = (token, expires)


async def solve_captcha_rucaptcha(captcha_key: str, rucaptcha_api_key: str) -> str:
    start = time.time()
    
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://rucaptcha.com/in.php",
            data={
                "key": rucaptcha_api_key,
                "method": "yandex",
                "sitekey": captcha_key,
                "pageurl": "https://multitransfer.ru",
                "json": 1,
            }
        )
        
        result = resp.json()
        
        if result.get("status") != 1:
            raise RuntimeError(f"RuCaptcha submit failed: {result.get('request')}")
        
        captcha_id = result["request"]
        
        wait_times = [2] * 3 + [3] * 37
        
        for i, wait in enumerate(wait_times):
            await asyncio.sleep(wait)
            
            resp = await client.get(
                "https://rucaptcha.com/res.php",
                params={
                    "key": rucaptcha_api_key,
                    "action": "get",
                    "id": captcha_id,
                    "json": 1
                }
            )
            
            result = resp.json()
            
            if result.get("status") == 1:
                elapsed = time.time() - start
                print(f"[Captcha] Solved in {elapsed:.1f}s")
                return result["request"]
            
            if result.get("request") == "CAPCHA_NOT_READY":
                continue
            
            raise RuntimeError(f"RuCaptcha error: {result.get('request')}")
        
        raise RuntimeError("RuCaptcha timeout (120s)")


async def createQr(amount: int, proxy: str = os.getenv('PROXY')):
    user_agent = random.choice(config.USER_AGENTS)
    session_id = str(uuid.uuid4())
    
    runner = FlowRunner(
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
        },
        proxy=proxy,
    )
    
    runner.ctx["fhpsessionid"] = session_id
    
    country = CARD_COUNTRIES["TJK"]
    sender_details = YamlManage.get_path("api.link_details.sender_details")
    
    steps_init = [
        Step(
            name="Get captcha key",
            method="GET",
            url=f"https://multitransfer.ru/_next/data/{sender_details}/ru/transfer/tajikistan/sender-details.json",
            headers={"User-Agent": user_agent, "referer": "https://multitransfer.ru/"},
            params={"country": "tajikistan"},
            expect_status=200,
            extracts=[ExtractRule("captcha_key", "json", "pageProps.captcha_key")],
        ),
    ]
    
    runner.run(steps_init)
    
    captcha_token = await CaptchaCache.get(runner.ctx["captcha_key"])
    
    if not captcha_token:
        rucaptcha_api_key = os.getenv('RUCAPTCHA_API_KEY')
        captcha_token = await solve_captcha_rucaptcha(
            captcha_key=runner.ctx["captcha_key"],
            rucaptcha_api_key=rucaptcha_api_key
        )
        await CaptchaCache.set(runner.ctx["captcha_key"], captcha_token)
    
    runner.ctx["captcha_token"] = captcha_token
    
    passport = random.choice(DATES_PASSPORT)
    
    steps_create = [
        Step(
            name="Calculate fee",
            method="POST",
            url="https://api.multitransfer.ru/anonymous/multi/multitransfer-fee-calc/v3/commissions",
            headers={
                "client-id": "multitransfer-web-id",
                "fhpsessionid": session_id,
                "User-Agent": user_agent,
                "content-type": "application/json",
                "fhprequestid": str(uuid.uuid4()),
                "x-request-id": str(uuid.uuid4()),
            },
            json_body={
                "countryCode": country["countryCode"],
                "range": "ALL_PLUS_LIMITS",
                "money": {
                    "acceptedMoney": {
                        "amount": amount,
                        "currencyCode": country["currencyFrom"],
                    },
                    "withdrawMoney": {
                        "currencyCode": country["currencyTo"],
                    },
                },
            },
            expect_status=200,
            extracts=[
                ExtractRule("commission_id", "json", "fees.0.commissions.0.commissionId"),
                ExtractRule("payment_system_id", "json", "fees.0.commissions.0.paymentSystemId"),
            ],
        ),
        Step(
            name="Create transfer",
            method="POST",
            url="https://api.multitransfer.ru/anonymous/multi/multitransfer-transfer-create/v3/anonymous/transfers/create",
            headers={
                "client-id": "multitransfer-web-id",
                "content-type": "application/json",
                "fhpsessionid": session_id,
                "fhptokenid": "{{captcha_token}}",
                "fhprequestid": str(uuid.uuid4()),
                "x-request-id": str(uuid.uuid4()),
                "User-Agent": user_agent,
            },
            json_body={
                "transfer": {
                    "paymentSystemId": "{{payment_system_id}}",
                    "countryCode": "TJK",
                    "beneficiaryAccountNumber": "5058270855938719",
                    "commissionId": "{{commission_id}}",
                    "paymentInstrument": {"type": "ANONYMOUS_CARD"}
                },
                "sender": {
                    "lastName": random.choice(config.LAST_NAMES),
                    "firstName": random.choice(config.FIRST_NAMES),
                    "middleName": random.choice(config.MIDDLE_NAMES),
                    "birthDate": passport["birth_date"],
                    "phoneNumber": config.genPhone(),
                    "documents": [{
                        "type": "21",
                        "series": config.random_series(),
                        "number": config.random_number(),
                        "issueDate": passport["issue_date"],
                        "countryCode": "RUS",
                    }],
                },
            },
            expect_status=201,
            extracts=[ExtractRule("transfer_id", "json", "transferId")],
        ),
        Step(
            name="Confirm transfer",
            method="POST",
            url="https://api.multitransfer.ru/anonymous/multi/multitransfer-qr-processing/v3/anonymous/confirm",
            headers={
                "client-id": "multitransfer-web-id",
                "content-type": "application/json",
                "fhpsessionid": session_id,
                "fhprequestid": str(uuid.uuid4()),
                "x-request-id": str(uuid.uuid4()),
                "User-Agent": user_agent,
            },
            json_body={
                "transactionId": "{{transfer_id}}",
                "recordType": "transfer"
            },
            expect_status=200,
            extracts=[ExtractRule("qr_payload", "json", "externalData.payload")],
        ),
    ]
    
    runner.run(steps_create)
    runner.close()
    
    return runner.ctx


async def test_parallel(n=3):
    tasks = [createQr(amount=1000 + i*100) for i in range(n)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = 0
    for result in results:
        if not isinstance(result, Exception) and result.get("transfer_id"):
            success_count += 1
    
    return success_count, len(results)


if __name__ == "__main__":
    asyncio.run(test_parallel(3))