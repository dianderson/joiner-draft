import hashlib
import hmac
import json
from urllib.parse import quote_plus

APP_SECRET = "seu_app_secret_aqui"


def make_event(phone: str, text: str) -> dict:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {
            "messages": [{"from": phone, "type": "text", "text": {"body": text}}]
        }}]}]
    }
    body = json.dumps(payload)
    sig = "sha256=" + hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return {
        "Records": [{
            "messageId": "test-001",
            "body": body,
            "messageAttributes": {
                "X-Hub-Signature-256": {
                    "stringValue": quote_plus(sig),
                    "dataType": "String"
                }
            }
        }]
    }


# Importa o handler depois de setar as envs
import sys

sys.path.insert(0, "lambdas/webhook_consumer")
from lambdas.webhook_consumer.lambda_function import lambda_handler

# Troque pelo seu número cadastrado na allowlist
PHONE = "5534999990001"

# Simula mensagens em sequência
for msg in ["oi", "Armário", "750", "1100", "4", "MDF_18"]:
    print(f"\n{'=' * 50}")
    print(f">>> Usuário enviou: {msg}")
    result = lambda_handler(make_event(PHONE, msg), None)
    print(f"<<< batchItemFailures: {result['batchItemFailures']}")
