import base64
import os
from dotenv import load_dotenv
import httpx
load_dotenv()

PAYMONGO_SECRET_KEY = os.environ.get("PAYMONGO_SECRET_KEY")
PAYMONGO_API_BASE = "https://api.paymongo.com/v1"

class PaymongoClient:
    BASE_URL = PAYMONGO_API_BASE

    def __init__(self, api_key: str = PAYMONGO_SECRET_KEY):
        token = base64.b64encode(f"{api_key}:".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    async def create_checkout_session(
        self,
        amount: float,
        description: str,
        success_url: str,
        cancel_url: str,
        currency="PHP",
    ):
        if not amount or amount < 1:
            raise ValueError("Amount must be at least 1.00 PHP")

        url = f"{self.BASE_URL}/checkout_sessions"
        payload = {
            "data": {
                "attributes": {
                    "line_items": [
                        {
                            "name": description or "League Registration Fee",
                            "amount": int(round(amount * 100)),
                            "currency": currency,
                            "quantity": 1,
                        }
                    ],
                    "payment_method_types": ["gcash", "grab_pay", "card", "paymaya"],
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                }
            }
        }

        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=self.headers, json=payload)

            if r.status_code >= 400:
                try:
                    error_data = r.json()
                except Exception:
                    error_data = r.text
                raise Exception(f"PayMongo error {r.status_code}: {error_data}")

            return r.json()

    async def retrieve_checkout_session(self, session_id: str):
        url = f"{self.BASE_URL}/checkout_sessions/{session_id}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self.headers)
            if r.status_code >= 400:
                try:
                    error_data = r.json()
                except Exception:
                    error_data = r.text
                raise Exception(f"PayMongo error {r.status_code}: {error_data}")
            return r.json()

    async def create_refund(self, payment_id: str, amount: float, reason: str = "requested_by_customer"):
        url = f"{self.BASE_URL}/refunds"
        payload = {
            "data": {
                "attributes": {
                    "amount": int(amount * 100),
                    "payment_id": payment_id,
                    "reason": reason
                }
            }
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=self.headers, json=payload)

            if r.status_code >= 400:
                try:
                    error_data = r.json()
                except Exception:
                    error_data = r.text
                raise Exception(f"PayMongo refund error {r.status_code}: {error_data}")

            return r.json()
