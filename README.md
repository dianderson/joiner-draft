# Joiner — WhatsApp Bot on AWS Lambda

Mono-repo with AWS Lambda functions for the Joiner WhatsApp bot integration.

## Structure

```
joiner/
├── lambdas/
│   ├── webhook_consumer/       # SQS consumer + bot engine
│   │   ├── lambda_function.py  # Lambda entry-point
│   │   └── joiner_bot/
│   │       ├── allowlist/      # Allowed users validation
│   │       ├── context/        # DynamoDB conversation context
│   │       ├── flow/           # Conversation flow / state machine
│   │       └── whatsapp/       # WhatsApp Cloud API client
│   ├── webhook_verification/   # Meta GET handshake
│   └── signature_authorizer/   # HMAC-SHA256 request authorizer
├── tests/
│   ├── unit/
│   └── integration/
└── pyproject.toml
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[webhook-consumer,dev]"
```

## Running tests

```bash
pytest
```

## Environment variables (Lambda)

| Variable | Description |
|---|---|
| `SECRET_NAME` | AWS Secrets Manager secret name (default: `prod/lambdas`) |
| `DYNAMODB_TABLE` | DynamoDB table name for conversation context |
| `OUTPUT_SQS_URL` | SQS URL to publish completed orders |

## Secrets (prod/lambdas)

| Key | Description |
|---|---|
| `META_APP_SECRET` | Meta App Secret for signature validation |
| `META_ACCESS_TOKEN` | WhatsApp Cloud API access token |
| `META_VERIFY_TOKEN` | Webhook verification token |
| `META_PHONE_NUMBER_ID` | Sender phone number ID |
