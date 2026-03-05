"""
joiner_bot.context
-------------------
Conversation context stored in DynamoDB.

Each user (phone number) has one active context item:
  PK: phone (str)
  step: current flow step (str)
  data: collected form data (dict serialised as JSON string)
  ttl: epoch timestamp for automatic expiry (24h)

Table schema (create once):
  Table name  : <DYNAMODB_TABLE env var>
  Partition key: phone (String)
  TTL attribute: ttl
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import boto3

logger = logging.getLogger(__name__)

_TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "joiner-draft-context")
_TTL_SECONDS = 60 * 5  # 5 min

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(_TABLE_NAME)


@dataclass
class Context:
    phone: str
    step: str = "START"
    data: dict[str, Any] = field(default_factory=dict)


def load(phone: str) -> Context:
    """Load context for a user. Returns a fresh Context if none exists."""
    response = _table.get_item(Key={"phone": phone})
    item = response.get("Item")
    if not item:
        logger.info("No context found for %s — starting fresh.", phone)
        return Context(phone=phone)

    return Context(
        phone=phone,
        step=item.get("step", "START"),
        data=json.loads(item.get("data", "{}")),
    )


def save(ctx: Context) -> None:
    """Persist context to DynamoDB with 24h TTL."""
    _table.put_item(Item={
        "phone": ctx.phone,
        "step": ctx.step,
        "data": json.dumps(ctx.data),
        "expires_at": int(time.time()) + _TTL_SECONDS,
    })
    logger.info("Context saved for %s — step=%s", ctx.phone, ctx.step)


def delete(phone: str) -> None:
    """Delete context after a completed flow."""
    _table.delete_item(Key={"phone": phone})
    logger.info("Context deleted for %s.", phone)
