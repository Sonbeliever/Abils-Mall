import json
import hmac
import hashlib
import requests
from flask import current_app


def _sign_payload(payload_json: str) -> str:
    secret = current_app.config.get("OPAY_SECRET_KEY", "")
    return hmac.new(secret.encode(), payload_json.encode(), hashlib.sha512).hexdigest()


def _headers(payload_json: str) -> dict:
    return {
        "Authorization": f"Bearer {_sign_payload(payload_json)}",
        "MerchantId": current_app.config.get("OPAY_MERCHANT_ID", ""),
        "Content-Type": "application/json"
    }


def opay_post(endpoint: str, payload: dict) -> dict:
    payload_json = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    headers = _headers(payload_json)
    api_base = current_app.config.get("OPAY_API_BASE", "https://testapi.opaycheckout.com")
    url = f"{api_base}{endpoint}"
    res = requests.post(url, data=payload_json, headers=headers, timeout=30)
    return res.json()


def query_status(reference: str) -> dict:
    # TODO: Confirm required fields from OPay docs for status query
    payload = {
        "reference": reference,
        "country": current_app.config.get("OPAY_COUNTRY", "NG")
    }
    endpoint = current_app.config.get("OPAY_STATUS_ENDPOINT", "/api/v1/international/cashier/status")
    return opay_post(endpoint, payload)


def refund(reference: str, amount: int, currency: str = "NGN") -> dict:
    # TODO: Confirm required fields from OPay docs for refund
    payload = {
        "reference": reference,
        "amount": amount,
        "currency": currency,
        "country": current_app.config.get("OPAY_COUNTRY", "NG")
    }
    endpoint = current_app.config.get("OPAY_REFUND_ENDPOINT", "/api/v1/international/cashier/refund")
    return opay_post(endpoint, payload)
