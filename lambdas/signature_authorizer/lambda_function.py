"""
Lambda Authorizer: Meta Webhook Signature Validation
------------------------------------------------------
Validates the HMAC-SHA256 signature that Meta attaches to every
webhook delivery (POST request).

Meta adds the header:
  X-Hub-Signature-256: sha256=<hex_digest>

The digest is computed over the raw request body using your
App Secret as the HMAC key.

This Lambda is configured as a **REQUEST-based Lambda Authorizer**
in API Gateway (not TOKEN-based), because it needs access to both
headers AND the raw body.

IAM Policy returned:
  - Allow  → signature is valid
  - Deny   → signature is invalid / missing

Secrets are fetched from AWS Secrets Manager (secret: prod/lambdas)
and cached in-memory for the lifetime of the Lambda execution environment.

References:
  https://developers.facebook.com/docs/graph-api/webhooks/getting-started#verification-requests
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SIGNATURE_HEADER = "x-hub-signature-256"
SIGNATURE_PREFIX = "sha256="

SECRET_NAME = os.environ.get("SECRET_NAME", "prod/lambdas")
SECRET_KEY = "META_APP_SECRET"

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


def _get_app_secret() -> bytes:
    secrets = _get_secrets()
    secret = secrets.get(SECRET_KEY, "")
    if not secret:
        raise RuntimeError(f"Key '{SECRET_KEY}' not found in secret '{SECRET_NAME}'.")
    return secret.encode()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _compute_signature(payload: bytes, secret: bytes) -> str:
    """Return the expected HMAC-SHA256 hex digest prefixed with 'sha256='."""
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{digest}"


def _signatures_match(received: str, expected: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(received.lower(), expected.lower())


def _build_policy(
    effect: str,
    method_arn: str,
    principal_id: str = "meta-webhook",
) -> dict[str, Any]:
    """Build a minimal IAM policy document for API Gateway."""
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": method_arn,
                }
            ],
        },
    }


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    """
    AWS Lambda entry-point — REQUEST-based Lambda Authorizer.

    API Gateway passes the full request context, including headers and body.
    """
    logger.info("Signature authorizer invoked.")

    method_arn: str = event.get("methodArn", "")

    # --- Extract headers (API Gateway normalises header names to lowercase) ---
    headers: dict[str, str] = {
        k.lower(): v for k, v in (event.get("headers") or {}).items()
    }

    received_signature = headers.get(SIGNATURE_HEADER, "")
    if not received_signature:
        logger.warning("Missing %s header.", SIGNATURE_HEADER)
        return _build_policy("Deny", method_arn)

    if not received_signature.startswith(SIGNATURE_PREFIX):
        logger.warning("Signature header has unexpected format: %r", received_signature)
        return _build_policy("Deny", method_arn)

    # --- Get raw body ---
    raw_body: str | None = event.get("body")
    if raw_body is None:
        logger.warning("Request body is missing.")
        return _build_policy("Deny", method_arn)

    payload_bytes = raw_body.encode("utf-8")

    # --- Load secret & compute expected signature ---
    try:
        app_secret = _get_app_secret()
    except RuntimeError as exc:
        logger.error("Configuration error: %s", exc)
        return _build_policy("Deny", method_arn)

    expected_signature = _compute_signature(payload_bytes, app_secret)

    # --- Compare ---
    if not _signatures_match(received_signature, expected_signature):
        logger.warning("Signature mismatch. Request rejected.")
        return _build_policy("Deny", method_arn)

    logger.info("Signature validated successfully.")
    return _build_policy("Allow", method_arn)
