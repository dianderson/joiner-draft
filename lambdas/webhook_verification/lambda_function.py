"""
Lambda: Meta Webhook Verification (GET)
---------------------------------------
Handles the one-time challenge/response handshake that Meta sends
when you register or update a webhook endpoint.

Meta sends:
  GET ?hub.mode=subscribe
      &hub.verify_token=<your_token>
      &hub.challenge=<random_string>

Expected response:
  - 200 + hub.challenge (plain text) → subscription confirmed
  - 403                              → token mismatch / bad request

Secrets are fetched from AWS Secrets Manager (secret: prod/lambdas)
and cached in-memory for the lifetime of the Lambda execution environment.
"""

from __future__ import annotations

import json
import logging
import os
from http import HTTPStatus
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERIFY_TOKEN_PARAM = "hub.verify_token"
CHALLENGE_PARAM = "hub.challenge"
MODE_PARAM = "hub.mode"
EXPECTED_MODE = "subscribe"

SECRET_NAME = os.environ.get("SECRET_NAME", "prod/lambdas")
SECRET_KEY = "META_VERIFY_TOKEN"

# ---------------------------------------------------------------------------
# In-memory cache (lives for the duration of the execution environment)
# ---------------------------------------------------------------------------
_secrets_cache: dict[str, str] | None = None


def _get_secrets() -> dict[str, str]:
    """Fetch secrets from Secrets Manager, using in-memory cache."""
    global _secrets_cache

    if _secrets_cache is not None:
        logger.debug("Returning secrets from cache.")
        return _secrets_cache

    logger.info("Fetching secrets from Secrets Manager: %s", SECRET_NAME)

    client = boto3.client("secretsmanager")
    try:
        response = client.get_secret_value(SecretId=SECRET_NAME)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error("Secrets Manager ClientError [%s]: %s", error_code, exc)
        raise RuntimeError(f"Failed to fetch secret '{SECRET_NAME}': {error_code}") from exc
    except BotoCoreError as exc:
        logger.error("Secrets Manager BotoCoreError: %s", exc)
        raise RuntimeError(f"Failed to fetch secret '{SECRET_NAME}'.") from exc

    raw = response.get("SecretString", "{}")
    try:
        _secrets_cache = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Secret '{SECRET_NAME}' is not valid JSON.") from exc

    return _secrets_cache


def _get_verify_token() -> str:
    secrets = _get_secrets()
    token = secrets.get(SECRET_KEY, "")
    if not token:
        raise RuntimeError(f"Key '{SECRET_KEY}' not found in secret '{SECRET_NAME}'.")
    return token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_response(status_code: int, body: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "text/plain"},
        "body": body,
    }


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    """AWS Lambda entry-point for Meta webhook verification (GET)."""

    logger.info("Webhook verification request received.")

    query_params: dict[str, str] = event.get("queryStringParameters") or {}

    mode = query_params.get(MODE_PARAM, "")
    received_token = query_params.get(VERIFY_TOKEN_PARAM, "")
    challenge = query_params.get(CHALLENGE_PARAM, "")

    if not all([mode, received_token, challenge]):
        logger.warning(
            "Missing required query parameters. mode=%r token_present=%s challenge_present=%s",
            mode,
            bool(received_token),
            bool(challenge),
        )
        return _build_response(HTTPStatus.BAD_REQUEST, "Missing required query parameters.")

    if mode != EXPECTED_MODE:
        logger.warning("Unexpected hub.mode: %r", mode)
        return _build_response(HTTPStatus.FORBIDDEN, "Invalid hub.mode.")

    try:
        expected_token = _get_verify_token()
    except RuntimeError as exc:
        logger.error("Configuration error: %s", exc)
        return _build_response(HTTPStatus.INTERNAL_SERVER_ERROR, "Server configuration error.")

    if received_token != expected_token:
        logger.warning("Verify token mismatch.")
        return _build_response(HTTPStatus.FORBIDDEN, "Verification token mismatch.")

    logger.info("Webhook verified successfully. Returning challenge.")
    return _build_response(HTTPStatus.OK, challenge)
