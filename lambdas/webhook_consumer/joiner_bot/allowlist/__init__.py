"""
joiner_bot.allowlist
---------------------
Hardcoded list of allowed WhatsApp users for the pilot.

To add/remove users, update ALLOWED_USERS and redeploy the Lambda.
The dict is stored in module-level memory — zero latency after cold start.

Format:
    { "<phone_e164_no_plus>": "<display_name>" }

Example:
    "5534999990000": "João Silva"
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Allowed users — edit this dict to manage pilot access
# ---------------------------------------------------------------------------
ALLOWED_USERS: dict[str, str] = {
    "5534999990001": "João Silva",
    "5534999990002": "Maria Souza",
    # add more users here
}

PILOT_DENIED_MESSAGE = (
    "Olá! 👋 Este é um projeto piloto com acesso restrito.\n\n"
    "Seu número foi registrado e você será notificado assim que "
    "tivermos disponibilidade. Obrigado pela compreensão! 🙏"
)


def is_allowed(phone: str) -> bool:
    """Return True if the phone number is in the allowed list."""
    return phone in ALLOWED_USERS


def get_name(phone: str) -> str:
    """Return the display name for an allowed phone number."""
    return ALLOWED_USERS.get(phone, "")
