import asyncio
import random
import uuid
from typing import Optional, Dict, Any, TYPE_CHECKING

from config import config
from captcha_solver import solve_captcha
from http_client import AsyncHttpClient, generate_headers

if TYPE_CHECKING:
    from captcha_token_pool import CaptchaTokenPool


class QRGeneratorRace:
    API_BASE = "https://api.multitransfer.ru"
    
    def __init__(
        self,
        proxy: str,
        amount: float,
        card_number: str,
        card_country: str = "TJK",
        attempts: int = 3,
        token_pool: Optional['CaptchaTokenPool'] = None
    ):
        self.proxy = proxy
        self.amount = amount
        self.card_number = card_number
        self.card_country = card_country
        self.attempts = attempts
        self.token_pool = token_pool
        
        self.success_event = asyncio.Event()
        self.winner_result = None
    
    async def generate(self) -> Optional[Dict[str, Any]]:
        print(f"[Race] Starting {self.attempts} parallel attempts for {self.amount} RUB")
        
        tasks = [
            asyncio.create_task(self._single_attempt(attempt_num=i+1))
            for i in range(self.attempts)
        ]
        
        try:
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in done:
                try:
                    result = task.result()
                    if result and result.get("transfer_id"):
                        print(f"[Race] Cancelling {len(pending)} remaining tasks")
                        for pending_task in pending:
                            pending_task.cancel()
                        
                        if pending:
                            await asyncio.wait(pending, timeout=1.0)
                        
                        return result
                except Exception:
                    pass
            
            while pending:
                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    try:
                        result = task.result()
                        if result and result.get("transfer_id"):
                            for pending_task in pending:
                                pending_task.cancel()
                            if pending:
                                await asyncio.wait(pending, timeout=1.0)
                            return result
                    except Exception:
                        pass
            
            print(f"[Race] All {self.attempts} attempts failed")
            return None
            
        except Exception as e:
            print(f"[Race] Error in generate: {e}")
            for task in tasks:
                if not task.done():
                    task.cancel()
            return None
    
    async def _single_attempt(self, attempt_num: int) -> Optional[Dict[str, Any]]:
        user_agent = random.choice(config.USER_AGENTS)
        client = AsyncHttpClient(proxy=self.proxy)
        fhpsessionid = str(uuid.uuid4())
        
        try:
            if self.success_event.is_set():
                return None
            
            commission_data = await self._calc_commissions(
                client, user_agent, fhpsessionid
            )
            if not commission_data:
                print(f"[Race] Attempt {attempt_num}: Failed at commissions")
                return None
            
            if self.success_event.is_set():
                return None
            
            captcha_key = await self._get_captcha_key(client, user_agent)
            if not captcha_key:
                print(f"[Race] Attempt {attempt_num}: Failed at captcha key")
                return None
            
            if self.success_event.is_set():
                return None
            
            captcha_token = None
            if self.token_pool:
                captcha_token = await self.token_pool.get_token()
                if captcha_token:
                    print(f"[Race] Attempt {attempt_num}: Using token from pool")
            
            if not captcha_token:
                print(f"[Race] Attempt {attempt_num}: Solving captcha (no token in pool)")
                try:
                    captcha_token = await solve_captcha(captcha_key, priority=10)
                except asyncio.CancelledError:
                    print(f"[Race] Attempt {attempt_num}: Cancelled during captcha")
                    raise
            
            if not captcha_token:
                print(f"[Race] Attempt {attempt_num}: Failed to get captcha token")
                return None
            
            if self.success_event.is_set():
                return None
            
            print(f"[Race] Attempt {attempt_num}: Creating transfer")
            transfer_data = await self._create_transfer(
                client, user_agent, fhpsessionid,
                commission_data, captcha_token
            )
            if not transfer_data:
                print(f"[Race] Attempt {attempt_num}: Failed at transfer creation")
                return None
            
            if self.success_event.is_set():
                return None
            
            qr_data = await self._confirm_transfer(
                client, user_agent, fhpsessionid, transfer_data["transferId"]
            )
            
            result = {
                "transfer_id": transfer_data["transferId"],
                "transfer_num": transfer_data["transferNum"],
                "qr_payload": qr_data.get("externalData", {}).get("payload") if qr_data else None
            }
            
            if not self.success_event.is_set():
                self.success_event.set()
                self.winner_result = result
                print(f"[Race] Attempt {attempt_num}: QR generated successfully")
            
            return result
        
        except asyncio.CancelledError:
            print(f"[Race] Attempt {attempt_num}: Cancelled")
            raise
        
        except Exception as e:
            print(f"[Race] Attempt {attempt_num}: Exception - {e}")
            return None
        
        finally:
            await client.close()
    
    async def _calc_commissions(
        self, client: AsyncHttpClient, user_agent: str, fhpsessionid: str
    ) -> Optional[Dict[str, Any]]:
        country_data = config.CARD_COUNTRIES[self.card_country]
        headers = generate_headers(user_agent, fhpsessionid)
        
        payload = {
            "countryCode": country_data["countryCode"],
            "range": "ALL_PLUS_LIMITS",
            "money": {
                "acceptedMoney": {
                    "amount": self.amount,
                    "currencyCode": country_data["currencyFrom"]
                },
                "withdrawMoney": {
                    "currencyCode": country_data["currencyTo"]
                }
            }
        }
        
        response = await client.request(
            "POST",
            f"{self.API_BASE}/anonymous/multi/multitransfer-fee-calc/v3/commissions",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        fees = data.get("fees", [])
        
        if not fees or not fees[0].get("commissions"):
            return None
        
        commission = fees[0]["commissions"][0]
        
        return {
            "commission_id": commission["commissionId"],
            "payment_system_id": commission["paymentSystemId"]
        }
    
    async def _get_captcha_key(
        self, client: AsyncHttpClient, user_agent: str
    ) -> Optional[str]:
        from build_id_fetcher import get_build_id
        
        build_id = await get_build_id()
        if not build_id:
            return None
        
        country_name = config.CARD_COUNTRIES[self.card_country]["name"].lower()
        
        response = await client.request(
            "GET",
            f"https://multitransfer.ru/_next/data/{build_id}/ru/transfer/{country_name}/sender-details.json",
            params={"country": country_name},
            headers={"User-Agent": user_agent}
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        return data.get("pageProps", {}).get("captcha_key")
    
    async def _create_transfer(
        self,
        client: AsyncHttpClient,
        user_agent: str,
        fhpsessionid: str,
        commission_data: Dict[str, Any],
        captcha_token: str
    ) -> Optional[Dict[str, Any]]:
        country_data = config.CARD_COUNTRIES[self.card_country]
        
        passport = random.choice(config.PASSPORT_DATES)
        
        headers = generate_headers(user_agent, fhpsessionid)
        headers["Fhptokenid"] = captcha_token
        
        payload = {
            "transfer": {
                "service_name": "multitransfer",
                "paymentSystemId": commission_data["payment_system_id"],
                "countryCode": country_data["countryCode"],
                "beneficiaryAccountNumber": self.card_number,
                "commissionId": commission_data["commission_id"],
                "paymentInstrument": {"type": "ANONYMOUS_CARD"}
            },
            "sender": {
                "lastName": random.choice(config.LAST_NAMES),
                "firstName": random.choice(config.FIRST_NAMES),
                "middleName": random.choice(config.MIDDLE_NAMES),
                "birthDate": passport["date_birth"],
                "phoneNumber": config.genPhone(),
                "documents": [{
                    "type": "21",
                    "series": config.random_series(),
                    "number": config.random_number(),
                    "issueDate": passport["date_issue"],
                    "countryCode": "RUS"
                }]
            }
        }
        
        try:
            response = await client.request(
                "POST",
                f"{self.API_BASE}/anonymous/multi/multitransfer-transfer-create/v3/anonymous/transfers/create",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 201:
                return response.json()
            
            return None
        
        except Exception:
            return None
    
    async def _confirm_transfer(
        self,
        client: AsyncHttpClient,
        user_agent: str,
        fhpsessionid: str,
        transfer_id: str
    ) -> Optional[Dict[str, Any]]:
        headers = generate_headers(user_agent, fhpsessionid)
        
        payload = {
            "transactionId": transfer_id,
            "recordType": "transfer"
        }
        
        response = await client.request(
            "POST",
            f"{self.API_BASE}/anonymous/multi/multitransfer-qr-processing/v3/anonymous/confirm",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        
        return None


async def generate_qr_race(
    proxy: str,
    amount: float,
    card_number: str,
    card_country: str = "TJK",
    attempts: int = 3,
    token_pool: Optional['CaptchaTokenPool'] = None
) -> Optional[Dict[str, Any]]:
    generator = QRGeneratorRace(
        proxy=proxy,
        amount=amount,
        card_number=card_number,
        card_country=card_country,
        attempts=attempts,
        token_pool=token_pool
    )
    
    return await generator.generate()