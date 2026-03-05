"""
joiner_bot.secrets
-------------------
AWS Secrets Manager client with in-memory cache.
Shared across all modules in the Lambda execution environment.
"""

from __future__ import annotations

import json
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

SECRET_NAME = os.environ.get("SECRET_NAME", "prod/lambdas")

_cache: dict[str, str] | None = None


def get_secrets() -> dict[str, str]:
    """Fetch and cache secrets from AWS Secrets Manager."""
    global _cache
    if _cache is not None:
        return _cache

    logger.info("Fetching secrets from Secrets Manager: %s", SECRET_NAME)
    client = boto3.client("secretsmanager")
    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        logger.error("Secrets Manager error [%s]: %s", code, exc)
        raise RuntimeError(f"Failed to fetch secret '{SECRET_NAME}': {code}") from exc
    except BotoCoreError as exc:
        logger.error("BotoCoreError fetching secret: %s", exc)
        raise RuntimeError(f"Failed to fetch secret '{SECRET_NAME}'.") from exc

    try:
        _cache = json.loads(response.get("SecretString", "{}"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Secret '{SECRET_NAME}' is not valid JSON.") from exc

    return _cache


def get(key: str) -> str:
    """Return a single secret value by key. Raises if not found."""
    value = get_secrets().get(key, "")
    if not value:
        raise RuntimeError(f"Key '{key}' not found in secret '{SECRET_NAME}'.")
    return value
