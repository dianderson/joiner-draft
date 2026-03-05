"""Unit tests for joiner_bot.allowlist"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambdas/webhook_consumer"))

from joiner_bot.allowlist import is_allowed, get_name, ALLOWED_USERS, PILOT_DENIED_MESSAGE


def test_is_allowed_returns_true_for_known_number() -> None:
    phone = next(iter(ALLOWED_USERS))
    assert is_allowed(phone) is True


def test_is_allowed_returns_false_for_unknown_number() -> None:
    assert is_allowed("5500000000000") is False


def test_get_name_returns_correct_name() -> None:
    phone, name = next(iter(ALLOWED_USERS.items()))
    assert get_name(phone) == name


def test_get_name_returns_empty_for_unknown() -> None:
    assert get_name("5500000000000") == ""


def test_pilot_denied_message_is_not_empty() -> None:
    assert len(PILOT_DENIED_MESSAGE) > 10
