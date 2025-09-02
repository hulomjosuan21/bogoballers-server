import os
import aiohttp
import base64
from typing import Dict, Any
from src.utils.api_response import ApiException

PAYMONGO_SECRET_KEY = os.environ.get("PAYMONGO_SECRET_KEY")
PAYMONGO_API_BASE = "https://api.paymongo.com/v1"

class PayMongoService:
    def __init__(self):
        if not PAYMONGO_SECRET_KEY:
            raise ApiException("PayMongo secret key not configured", 500)
        self.secret_key = PAYMONGO_SECRET_KEY
        self.api_base = PAYMONGO_API_BASE
        self.auth_header = self._get_auth_header()
    
    def _get_auth_header(self):
        auth_string = f"{self.secret_key}:"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        return f"Basic {encoded_auth}"
    
    async def create_payment_intent(self, amount_in_pesos: float, description: str, 
                                  success_url: str, cancel_url: str, error_url: str,
                                  metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.api_base}/payment_intents"
        amount_in_centavos = int(amount_in_pesos * 100)
        
        payload = {
            "data": {
                "attributes": {
                    "amount": amount_in_centavos,
                    "payment_method_allowed": ["gcash", "grab_pay", "card", "paymaya"],
                    "currency": "PHP",
                    "description": description,
                    "statement_descriptor": "Team Registration",
                    "metadata": metadata or {}
                }
            }
        }
        
        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()
                if response.status == 200:
                    return response_data
                raise ApiException(f"PayMongo API Error: {response_data.get('errors', 'Unknown error')}", response.status)
    
    async def create_checkout_session(self, payment_intent_id: str, success_url: str, 
                                    cancel_url: str, error_url: str, 
                                    amount_in_pesos: float = None, description: str = "Team Registration Fee") -> Dict[str, Any]:
        url = f"{self.api_base}/checkout_sessions"
        amount_in_centavos = int(amount_in_pesos * 100) if amount_in_pesos else None
        
        payload = {
            "data": {
                "attributes": {
                    "send_email_receipt": True,
                    "show_description": True,
                    "description": description,  # Added required description
                    "show_line_items": True,
                    "cancel_url": cancel_url,
                    "success_url": success_url,
                    "error_url": error_url,
                    "payment_method_types": ["gcash", "grab_pay", "card", "paymaya"],
                    "payment_intent_id": payment_intent_id
                }
            }
        }
        
        if amount_in_centavos:
            payload["data"]["attributes"]["line_items"] = [
                {
                    "currency": "PHP",
                    "amount": amount_in_centavos,
                    "description": description,
                    "name": "League Registration",
                    "quantity": 1
                }
            ]
        
        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()
                if response.status == 200:
                    return response_data
                raise ApiException(f"PayMongo Checkout Error: {response_data.get('errors', 'Unknown error')}", response.status)
    
    async def retrieve_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        url = f"{self.api_base}/payment_intents/{payment_intent_id}"
        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response_data = await response.json()
                if response.status == 200:
                    return response_data
                raise ApiException(f"PayMongo Retrieve Error: {response_data.get('errors', 'Unknown error')}", response.status)