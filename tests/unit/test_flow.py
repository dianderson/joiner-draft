"""Unit tests for joiner_bot.flow — mocks WhatsApp and DynamoDB."""

from __future__ import annotations

import sys
import os
from typing import Any
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambdas/webhook_consumer"))

from joiner_bot.context import Context
from joiner_bot.flow import (
    _handle_start,
    _handle_await_product,
    _handle_await_width,
    _handle_await_height,
    _handle_await_shelves,
    _handle_await_material,
    PRODUCTS,
    MATERIALS,
)


PHONE = "5534999990001"
NAME = "João Silva"


@patch("joiner_bot.flow.whatsapp")
def test_start_sends_greeting_and_menu(mock_wa: MagicMock) -> None:
    ctx = Context(phone=PHONE)
    updated = _handle_start("oi", ctx, NAME)

    assert updated.step == "AWAIT_PRODUCT"
    mock_wa.send_text.assert_called_once()
    mock_wa.send_interactive_list.assert_called_once()
    assert NAME in mock_wa.send_text.call_args[0][1]


@patch("joiner_bot.flow.whatsapp")
def test_await_product_invalid_shows_menu_again(mock_wa: MagicMock) -> None:
    ctx = Context(phone=PHONE, step="AWAIT_PRODUCT")
    updated = _handle_await_product("coisa_invalida", ctx, NAME)

    assert updated.step == "AWAIT_PRODUCT"
    mock_wa.send_interactive_list.assert_called_once()


@patch("joiner_bot.flow.whatsapp")
def test_await_product_valid_advances_step(mock_wa: MagicMock) -> None:
    ctx = Context(phone=PHONE, step="AWAIT_PRODUCT")
    updated = _handle_await_product("Armário", ctx, NAME)

    assert updated.step == "AWAIT_WIDTH"
    assert updated.data["product"] == "Armário"


@patch("joiner_bot.flow.whatsapp")
def test_await_width_invalid_asks_again(mock_wa: MagicMock) -> None:
    ctx = Context(phone=PHONE, step="AWAIT_WIDTH")
    updated = _handle_await_width("abc", ctx, NAME)

    assert updated.step == "AWAIT_WIDTH"


@patch("joiner_bot.flow.whatsapp")
def test_await_width_valid_stores_and_advances(mock_wa: MagicMock) -> None:
    ctx = Context(phone=PHONE, step="AWAIT_WIDTH")
    updated = _handle_await_width("750", ctx, NAME)

    assert updated.step == "AWAIT_HEIGHT"
    assert updated.data["width_mm"] == 750


@patch("joiner_bot.flow.whatsapp")
def test_await_height_valid_advances(mock_wa: MagicMock) -> None:
    ctx = Context(phone=PHONE, step="AWAIT_HEIGHT")
    updated = _handle_await_height("1100", ctx, NAME)

    assert updated.step == "AWAIT_SHELVES"
    assert updated.data["height_mm"] == 1100


@patch("joiner_bot.flow.whatsapp")
def test_await_shelves_valid_advances(mock_wa: MagicMock) -> None:
    ctx = Context(phone=PHONE, step="AWAIT_SHELVES")
    updated = _handle_await_shelves("4", ctx, NAME)

    assert updated.step == "AWAIT_MATERIAL"
    assert updated.data["shelves"] == 4


@patch("joiner_bot.flow._publish_order")
@patch("joiner_bot.flow.whatsapp")
def test_await_material_valid_completes_flow(mock_wa: MagicMock, mock_publish: MagicMock) -> None:
    ctx = Context(
        phone=PHONE,
        step="AWAIT_MATERIAL",
        data={"product": "Armário", "width_mm": 750, "height_mm": 1100, "shelves": 4},
    )
    updated = _handle_await_material("MDF_18", ctx, NAME)

    assert updated.step == "DONE"
    assert updated.data["material"] == "MDF_18"
    mock_publish.assert_called_once()
    order = mock_publish.call_args[0][0]
    assert order["phone"] == PHONE
    assert order["material"] == "MDF_18"


@patch("joiner_bot.flow.whatsapp")
def test_await_material_invalid_asks_again(mock_wa: MagicMock) -> None:
    ctx = Context(phone=PHONE, step="AWAIT_MATERIAL")
    updated = _handle_await_material("MADEIRA", ctx, NAME)

    assert updated.step == "AWAIT_MATERIAL"
    mock_wa.send_interactive_list.assert_called_once()
