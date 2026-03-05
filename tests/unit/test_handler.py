"""Unit tests for the Lambda handler (lambda_function.py)."""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import os
from unittest.mock import MagicMock, patch
from urllib.parse import quote_plus

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambdas/webhook_consumer"))

APP_SECRET = "test_secret"

ALLOWED_PHONE = "5534999990001"
UNKNOWN_PHONE = "5500000000000"


def _make_payload(phone: str, text: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"field": "messages", "value": {"messages": [{"from": phone, "type": "text", "text": {"body": text}}]}}]}],
    }


def _sign(body: str) -> str:
    digest = hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _make_sqs_record(payload: dict, phone: str, text: str, secret: str = APP_SECRET) -> dict:
    body = json.dumps(payload)
    sig = _sign(body) if secret == APP_SECRET else "sha256=invalido"
    return {
        "messageId": "msg-001",
        "body": body,
        "messageAttributes": {
            "X-Hub-Signature-256": {"stringValue": quote_plus(sig), "dataType": "String"},
        },
    }


@patch("joiner_bot.secrets.get", return_value=APP_SECRET)
@patch("joiner_bot.flow.process")
@patch("joiner_bot.allowlist.is_allowed", return_value=True)
@patch("joiner_bot.allowlist.get_name", return_value="João Silva")
def test_valid_message_calls_flow(mock_name, mock_allowed, mock_process, mock_secret):
    import lambda_function

    payload = _make_payload(ALLOWED_PHONE, "oi")
    record = _make_sqs_record(payload, ALLOWED_PHONE, "oi")
    event = {"Records": [record]}

    result = lambda_function.lambda_handler(event, None)

    assert result["batchItemFailures"] == []
    mock_process.assert_called_once_with(phone=ALLOWED_PHONE, message="oi", name="João Silva")


@patch("joiner_bot.secrets.get", return_value=APP_SECRET)
@patch("joiner_bot.whatsapp.send_text")
@patch("joiner_bot.allowlist.is_allowed", return_value=False)
def test_unknown_phone_sends_pilot_message(mock_allowed, mock_send, mock_secret):
    import lambda_function

    payload = _make_payload(UNKNOWN_PHONE, "oi")
    record = _make_sqs_record(payload, UNKNOWN_PHONE, "oi")
    event = {"Records": [record]}

    result = lambda_function.lambda_handler(event, None)

    assert result["batchItemFailures"] == []
    mock_send.assert_called_once()


@patch("joiner_bot.secrets.get", return_value=APP_SECRET)
@patch("joiner_bot.flow.process")
def test_invalid_signature_discards_message(mock_process, mock_secret):
    import lambda_function

    payload = _make_payload(ALLOWED_PHONE, "oi")
    body = json.dumps(payload)
    record = {
        "messageId": "msg-bad-sig",
        "body": body,
        "messageAttributes": {
            "X-Hub-Signature-256": {"stringValue": "sha256=invalida", "dataType": "String"},
        },
    }
    event = {"Records": [record]}

    result = lambda_function.lambda_handler(event, None)

    assert result["batchItemFailures"] == []
    mock_process.assert_not_called()
