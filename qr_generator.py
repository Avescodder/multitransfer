import asyncio
import random
import uuid
from typing import Optional, Dict, Any
import httpx  

from config import config
from captcha_solver import solve_captcha
from http_client import AsyncHttpClient, generate_headers


class QRGenerator:
    API_BASE = "https://api.multitransfer.ru"
    
    def __init__(
        self, 
        proxy: str, 
        user_agent: str,
        shared_client: Optional[httpx.AsyncClient] = None  
    ):
        self.proxy = proxy
        self.user_agent = user_agent
        self.fhpsessionid = str(uuid.uuid4())
        
        self.client = AsyncHttpClient(
            proxy=proxy,
            shared_client=shared_client  
        )
    
    async def generate(
        self,
        amount: float,
        card_number: str,
        card_country: str = "TJK"
    ) -> Optional[Dict[str, Any]]:
        try:
            commission_data = await self._calc_commissions(amount, card_country)
            if not commission_data:
                return None
            
            captcha_key = await self._get_captcha_key(card_country)
            if not captcha_key:
                return None
            
            captcha_token = await solve_captcha(captcha_key)
            if not captcha_token:
                return None
            
            transfer_data = await self._create_transfer(
                amount,
                card_number,
                card_country,
                commission_data,
                captcha_token
            )
            
            if not transfer_data:
                return None
            
            qr_data = await self._confirm_transfer(transfer_data["transferId"])
            
            return {
                "transfer_id": transfer_data["transferId"],
                "transfer_num": transfer_data["transferNum"],
                "qr_payload": qr_data.get("externalData", {}).get("payload") if qr_data else None
            }
        
        except Exception as e:
            print(f"[QRGenerator] Error: {e}")
            return None
        finally:
            await self.client.close()  
    
    
    async def _calc_commissions(self, amount: float, card_country: str) -> Optional[Dict[str, Any]]:
        country_data = config.CARD_COUNTRIES[card_country]
        headers = generate_headers(self.user_agent, self.fhpsessionid)
        
        payload = {
            "countryCode": country_data["countryCode"],
            "range": "ALL_PLUS_LIMITS",
            "money": {
                "acceptedMoney": {
                    "amount": amount,
                    "currencyCode": country_data["currencyFrom"]
                },
                "withdrawMoney": {
                    "currencyCode": country_data["currencyTo"]
                }
            }
        }
        
        response = await self.client.request(
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
    
    async def _get_captcha_key(self, card_country: str) -> Optional[str]:
        from build_id_fetcher import get_build_id
        
        build_id = await get_build_id()
        if not build_id:
            return None
        
        country_name = config.CARD_COUNTRIES[card_country]["name"].lower()
        
        response = await self.client.request(
            "GET",
            f"https://multitransfer.ru/_next/data/{build_id}/ru/transfer/{country_name}/sender-details.json",
            params={"country": country_name},
            headers={"User-Agent": self.user_agent}
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        return data.get("pageProps", {}).get("captcha_key")
    
    async def _create_transfer(
        self,
        amount: float,
        card_number: str,
        card_country: str,
        commission_data: Dict[str, Any],
        captcha_token: str
    ) -> Optional[Dict[str, Any]]:
        country_data = config.CARD_COUNTRIES[card_country]
        passport_dates = random.choice(config.DATES_PASSPORT)
        
        headers = generate_headers(self.user_agent, self.fhpsessionid)
        headers["Fhptokenid"] = captcha_token
        
        payload = {
            "transfer": {
                "service_name": "multitransfer",
                "paymentSystemId": commission_data["payment_system_id"],
                "countryCode": country_data["countryCode"],
                "beneficiaryAccountNumber": card_number,
                "commissionId": commission_data["commission_id"],
                "paymentInstrument": {"type": "ANONYMOUS_CARD"}
            },
            "sender": {
                "lastName": random.choice(config.LAST_NAMES),
                "firstName": random.choice(config.FIRST_NAMES),
                "middleName": random.choice(config.MIDDLE_NAMES),
                "birthDate": passport_dates["birth_date"],
                "phoneNumber": config.genPhone(),
                "documents": [{
                    "type": "21",
                    "series": config.random_series(),
                    "number": config.random_number(),
                    "issueDate": passport_dates["issue_date"],
                    "countryCode": "RUS"
                }]
            }
        }
        
        for attempt in range(3):
            try:
                response = await self.client.request(
                    "POST",
                    f"{self.API_BASE}/anonymous/multi/multitransfer-transfer-create/v3/anonymous/transfers/create",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 201:
                    return response.json()
                
                if response.status_code == 502:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                
                print(f"[QRGenerator] Transfer creation failed: {response.status_code}, {response.text[:500]}")
                return None
            
            except Exception as e:
                print(f"[QRGenerator] Request error on attempt {attempt + 1}: {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return None
        
        return None
    
    async def _confirm_transfer(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        headers = generate_headers(self.user_agent, self.fhpsessionid)
        
        payload = {
            "transactionId": transfer_id,
            "recordType": "transfer"
        }
        
        for attempt in range(3):
            response = await self.client.request(
                "POST",
                f"{self.API_BASE}/anonymous/multi/multitransfer-qr-processing/v3/anonymous/confirm",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()
            
            if attempt < 2:
                await asyncio.sleep(1)
        
        return None


async def create_qr(
    amount: float,
    card_number: str,
    card_country: str = "TJK",
    proxy: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if not proxy:
        proxy = config.PROXY
    
    user_agent = random.choice(config.USER_AGENTS)
    generator = QRGenerator(proxy, user_agent)
    
    return await generator.generate(amount, card_number, card_country)