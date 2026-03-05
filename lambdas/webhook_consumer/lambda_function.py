"""
Lambda: meta-webhook-consumer
------------------------------
SQS consumer — validates Meta webhook signature, extracts the
WhatsApp message, checks the allowlist, and delegates to the
flow engine.

Flow:
  Meta → API Gateway → SQS → this Lambda → DynamoDB (context)
                                          → WhatsApp Cloud API (replies)
                                          → SQS output (completed orders)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any
from urllib.parse import unquote_plus

from joiner_bot import allowlist, secrets
from joiner_bot import flow
from joiner_bot import whatsapp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------
_SIGNATURE_PREFIX = "sha256="
_SIGNATURE_ATTR = "X-Hub-Signature-256"


def _validate_signature(body: str, received: str) -> bool:
    if not received or not received.startswith(_SIGNATURE_PREFIX):
        logger.warning("Missing or malformed signature.")
        return False
    try:
        secret = secrets.get("META_APP_SECRET").encode()
    except RuntimeError:
        logger.error("META_APP_SECRET not available.")
        return False

    expected = _SIGNATURE_PREFIX + hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(received.lower(), expected.lower())


# ---------------------------------------------------------------------------
# Message extraction
# ---------------------------------------------------------------------------
def _extract_message(payload: dict[str, Any]) -> tuple[str, str] | None:
    """
    Extract (phone, text) from a WhatsApp webhook payload.
    Returns None for non-message events (status updates, etc.).
    """
    try:
        changes = payload["entry"][0]["changes"]
        for change in changes:
            if change.get("field") != "messages":
                continue
            value = change["value"]
            messages = value.get("messages", [])
            if not messages:
                return None

            msg = messages[0]
            phone: str = msg["from"]
            msg_type: str = msg.get("type", "")

            # Interactive list reply
            if msg_type == "interactive":
                text = msg["interactive"]["list_reply"]["id"]
            # Plain text
            elif msg_type == "text":
                text = msg["text"]["body"].strip()
            else:
                logger.info("Unsupported message type: %s — ignoring.", msg_type)
                return None

            logger.info("Message extracted — from=%s type=%s content=%r", phone, msg_type, text)
            return phone, text
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Could not extract message: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    batch_item_failures: list[dict[str, str]] = []

    for record in event.get("Records", []):
        message_id: str = record.get("messageId", "unknown")
        try:
            raw_body: str = record["body"]

            # --- Signature validation ---
            attrs = record.get("messageAttributes", {})
            signature: str = unquote_plus(
                attrs.get(_SIGNATURE_ATTR, {}).get("stringValue", "")
            )
            if not _validate_signature(raw_body, signature):
                logger.error("Invalid signature for message %s — discarding.", message_id)
                continue  # discard silently — do not retry

            # --- Parse payload ---
            payload = json.loads(raw_body)

            # --- Extract message ---
            result = _extract_message(payload)
            if result is None:
                logger.info("No actionable message in record %s — skipping.", message_id)
                continue

            phone, text = result

            # --- Allowlist check ---
            if not allowlist.is_allowed(phone):
                logger.info("Phone %s not in allowlist — sending pilot message.", phone)
                whatsapp.send_text(phone, allowlist.PILOT_DENIED_MESSAGE)
                continue

            name = allowlist.get_name(phone)

            # --- Flow engine ---
            flow.process(phone=phone, message=text, name=name)

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error on message %s: %s", message_id, exc)
            batch_item_failures.append({"itemIdentifier": message_id})

        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error on message %s: %s", message_id, exc)
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}
