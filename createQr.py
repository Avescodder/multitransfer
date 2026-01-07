import asyncio
import random
import uuid
import time

from httpFlowRunner import FlowRunner, Step, ExtractRule
from config import config
from app.core.yamlManage import YamlManage
from config.config import CARD_COUNTRIES, DATES_PASSPORT
from captcha.solve import solve_captcha_with_playwright


async def createQr(amount: int):
    user_agent = random.choice(config.USER_AGENTS)
    proxy = "http://user:pass@host:port"

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

    steps_before = [
        Step(
            name="Init page",
            method="GET",
            url=f"https://multitransfer.ru/_next/data/{sender_details}/ru/transfer/tajikistan/sender-details.json",
            headers={
                "User-Agent": user_agent,
                "referer": "https://multitransfer.ru/",
            },
            expect_status=200,
            extracts=[
                ExtractRule("captcha_key", "json", "pageProps.captcha_key")
            ],
        ),
    ]

    runner.run(steps_before)

    captcha_token = await solve_captcha_with_playwright(
        captcha_key=runner.ctx["captcha_key"],
        proxy=proxy,
        user_agent=user_agent,
        cookies=runner.client.cookies,
    )

    runner.ctx["captcha_token"] = captcha_token

    passport = random.choice(DATES_PASSPORT)

    steps_main = [
        Step(
            name="Calc fee",
            method="POST",
            url="https://api.multitransfer.ru/anonymous/multi/multitransfer-fee-calc/v3/commissions",
            headers={
                "client-id": "multitransfer-web-id",
                "fhpsessionid": session_id,
                "User-Agent": user_agent,
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
                "fhpsessionid": session_id,
                "fhptokenid": "{{captcha_token}}",
                "User-Agent": user_agent,
            },
            json_body={
                "transfer": {
                    "service_name": "multitransfer",
                    "paymentSystemId": "{{payment_system_id}}",
                    "countryCode": country["countryCode"],
                    "beneficiaryAccountNumber": "5058270855938719",
                    "commissionId": "{{commission_id}}",
                    "paymentInstrument": {"type": "ANONYMOUS_CARD"},
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
            extracts=[
                ExtractRule("transfer_id", "json", "transferId"),
            ],
        ),
    ]

    runner.run(steps_main)
    runner.close()

    return runner.ctx


if __name__ == "__main__":
    result = asyncio.run(createQr(100))
    print(result)
