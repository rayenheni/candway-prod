import logging

import requests

from backend.config import get_settings
from backend.database import SessionLocal, SystemConfig
from backend.secret_encryption import decrypt_value

settings = get_settings()

KONNECT_API_URL = "https://api.konnect.network/api/v2/payments/init-payment"


class KonnectService:
    def get_config(self):
        db = SessionLocal()
        try:
            wallet_id = (
                db.query(SystemConfig)
                .filter(SystemConfig.key == "konnect_wallet_id")
                .first()
            )
            api_key = (
                db.query(SystemConfig)
                .filter(SystemConfig.key == "konnect_api_key")
                .first()
            )

            raw_api_key = api_key.value if api_key else None
            secret_key = settings.secret_key
            if raw_api_key and secret_key:
                raw_api_key = decrypt_value(raw_api_key, secret_key)

            return {
                "walletId": wallet_id.value if wallet_id else None,
                "x-api-key": raw_api_key,
            }
        finally:
            db.close()

    def init_payment(
        self,
        amount: float,
        currency: str = "TND",
        enrollment_id: int = None,
        user_email: str = None,
    ):
        config = self.get_config()

        if not config["walletId"] or not config["x-api-key"]:
            logging.error("Konnect keys missing in SystemConfig.")
            raise RuntimeError(
                "Konnect payment gateway is not configured. Set WALLET_ID and X_API_KEY in SystemConfig."
            )

        headers = {"x-api-key": config["x-api-key"], "Content-Type": "application/json"}

        payload = {
            "receiverWalletId": config["walletId"],
            "token": "TND",
            "amount": int(
                amount * 1000
            ),  # Konnect uses millimes? Or smallest unit. TND often 3 decimals. Usually smallest unit.
            "type": "immediate",
            "description": f"Enrollment #{enrollment_id}",
            "acceptedPaymentMethods": ["bank_card", "e_dinar"],
            "lifespan": 10,
            "checkoutForm": True,  # Use Konnect hosted page
            "addPaymentFeesToAmount": True,
            "firstName": "Candidate",  # Could enrich if we had user name passed
            "lastName": "User",
            "phoneNumber": "22222222",
            "email": user_email or "client@example.com",
            "orderId": str(enrollment_id),
            "webhook": f"{settings.base_url}/api/courses/konnect-webhook",
            "successUrl": f"{settings.frontend_url}/courses?payment=success",
            "failUrl": f"{settings.frontend_url}/courses?payment=failed",
            "theme": "light",
        }

        try:
            response = requests.post(KONNECT_API_URL, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()  # Should contain 'payUrl'
            else:
                logging.error(f"Konnect Init Failed: {response.text}")
                return None
        except Exception as e:
            logging.error(f"Konnect Error: {e}")
            return None


konnect_service = KonnectService()
