import asyncio
import random
import dotenv
import uuid
import time
import os

from httpFlowRunner import FlowRunner, Step, ExtractRule
from config import config
from yamlManage import YamlManage
from config.config import CARD_COUNTRIES, DATES_PASSPORT
from captcha.solve import solve_captcha_with_playwright

dotenv.load_dotenv()

RUCAPTCHA_API_KEY = os.getenv('RUCAPTCHA_API_KEY')


async def createQr(amount: int, proxy: str = os.getenv('PROXY')):
    start = time.time()
    
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
    
    t1 = time.time()
    print(f"[Step 1] {t1 - start:.1f}s")
    
    captcha_token = await solve_captcha_with_playwright(
        captcha_key=runner.ctx["captcha_key"],
        proxy=proxy,
        user_agent=user_agent,
        cookies=dict(runner.client.cookies),
        rucaptcha_api_key=RUCAPTCHA_API_KEY,
    )
    
    runner.ctx["captcha_token"] = captcha_token
    
    t2 = time.time()
    print(f"[Step 2] {t2 - t1:.1f}s (total {t2 - start:.1f}s)")
    
    passport = random.choice(DATES_PASSPORT)
    
    steps_create = [
        Step(
            name="Calc fee",
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
            name="Confirm transfer (QR)",
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
    
    t3 = time.time()
    print(f"[Step 3] {t3 - t2:.1f}s (total {t3 - start:.1f}s)")
    print(f"[Result] transfer_id={runner.ctx.get('transfer_id')}")
    print(f"[QR] {runner.ctx.get('qr_payload')}")
    
    return runner.ctx


if __name__ == "__main__":
    result = asyncio.run(createQr(1000))
    print(result)