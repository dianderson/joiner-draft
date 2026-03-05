"""
joiner_bot.whatsapp
--------------------
WhatsApp Cloud API client.

Handles sending text messages and interactive list messages.
Token is read from Secrets Manager (key: META_ACCESS_TOKEN).
Phone Number ID is read from Secrets Manager (key: META_PHONE_NUMBER_ID).

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/messages
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from lambdas.webhook_consumer.joiner_bot import secrets

logger = logging.getLogger(__name__)

_GRAPH_API_VERSION = "v22.0"
_BASE_URL = f"https://graph.facebook.com/{_GRAPH_API_VERSION}"
_TIMEOUT = 5  # seconds
_META_PHONE_NUMBER_ID = "966357683235683"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {secrets.get('META_ACCESS_TOKEN')}",
        "Content-Type": "application/json",
    }


def _post(payload: dict[str, Any]) -> None:
    url = f"{_BASE_URL}/{_META_PHONE_NUMBER_ID}/messages"
    response = requests.post(url, json=payload, headers=_headers(), timeout=_TIMEOUT)
    if not response.ok:
        logger.error(
            "WhatsApp API error %s: %s", response.status_code, response.text
        )
        response.raise_for_status()
    logger.info("WhatsApp message sent. status=%s", response.status_code)


def send_text(to: str, body: str) -> None:
    """Send a plain text message."""
    _post({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    })


def send_interactive_list(to: str, body: str, options: list[str]) -> None:
    """
    Send an interactive list message.
    Each option becomes a selectable row — the user taps to reply.

    WhatsApp limits: max 10 rows per list, title max 24 chars.
    """
    rows = [
        {"id": opt, "title": opt[:24]}
        for opt in options
    ]
    _post({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": "Ver opções",
                "sections": [{"title": "Opções", "rows": rows}],
            },
        },
    })
