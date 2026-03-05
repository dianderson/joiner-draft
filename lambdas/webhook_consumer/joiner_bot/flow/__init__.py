"""
joiner_bot.flow
----------------
Conversation state machine.

Each step is a function that receives the user message and the current
Context, and returns an updated Context. Side effects (sending WhatsApp
messages) are performed inside each step handler.

Steps:
  START          → greet + show main menu
  AWAIT_PRODUCT  → validate product selection
  AWAIT_WIDTH    → collect width (mm, int)
  AWAIT_HEIGHT   → collect height (mm, int)
  AWAIT_SHELVES  → collect number of shelves (int)
  AWAIT_MATERIAL → collect material selection
  DONE           → publish order to SQS + reset context
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

import boto3

from joiner_bot import context as ctx_module
from joiner_bot import whatsapp
from joiner_bot.context import Context

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PRODUCTS = ["Prateleira", "Nicho", "Gaveta", "Armário", "Gaveteiro"]
MATERIALS = ["MDF_15", "MDF_18", "MDF_25"]

OUTPUT_SQS_URL = os.environ.get("OUTPUT_SQS_URL", "")

_sqs = boto3.client("sqs")

# ---------------------------------------------------------------------------
# Step handlers
# ---------------------------------------------------------------------------
StepHandler = Callable[[str, Context, str], Context]


def _handle_start(message: str, ctx: Context, name: str) -> Context:
    """Any message from START → greet + show product menu."""
    whatsapp.send_text(
        ctx.phone,
        f"Olá, {name}! 😊 Espero que esteja tudo ótimo por aí.\nO que vamos criar hoje?",
    )
    whatsapp.send_interactive_list(
        ctx.phone,
        "Selecione o produto que deseja configurar:",
        PRODUCTS,
    )
    ctx.step = "AWAIT_PRODUCT"
    return ctx


def _handle_await_product(message: str, ctx: Context, name: str) -> Context:
    """Validate product selection."""
    if message not in PRODUCTS:
        whatsapp.send_text(
            ctx.phone,
            "❌ Opção não reconhecida. Por favor, clique em uma das opções da lista abaixo:",
        )
        whatsapp.send_interactive_list(
            ctx.phone,
            "Selecione o produto:",
            PRODUCTS,
        )
        return ctx

    ctx.data["product"] = message
    ctx.step = "AWAIT_WIDTH"
    whatsapp.send_text(ctx.phone, f"Ótima escolha! Vamos configurar seu *{message}*. 📐\n\nQual a *largura* em milímetros?")
    return ctx


def _handle_await_width(message: str, ctx: Context, name: str) -> Context:
    """Validate and store width."""
    if not message.isdigit():
        whatsapp.send_text(ctx.phone, "⚠️ Por favor, informe apenas números inteiros em milímetros.\n\nQual a *largura* em milímetros?")
        return ctx

    ctx.data["width_mm"] = int(message)
    ctx.step = "AWAIT_HEIGHT"
    whatsapp.send_text(ctx.phone, "Qual a *altura* em milímetros?")
    return ctx


def _handle_await_height(message: str, ctx: Context, name: str) -> Context:
    """Validate and store height."""
    if not message.isdigit():
        whatsapp.send_text(ctx.phone, "⚠️ Por favor, informe apenas números inteiros em milímetros.\n\nQual a *altura* em milímetros?")
        return ctx

    ctx.data["height_mm"] = int(message)
    ctx.step = "AWAIT_SHELVES"
    whatsapp.send_text(ctx.phone, "Qual a *quantidade de prateleiras*?")
    return ctx


def _handle_await_shelves(message: str, ctx: Context, name: str) -> Context:
    """Validate and store shelf count."""
    if not message.isdigit():
        whatsapp.send_text(ctx.phone, "⚠️ Por favor, informe apenas um número inteiro.\n\nQual a *quantidade de prateleiras*?")
        return ctx

    ctx.data["shelves"] = int(message)
    ctx.step = "AWAIT_MATERIAL"
    whatsapp.send_interactive_list(
        ctx.phone,
        "Qual *material* será usado?",
        MATERIALS,
    )
    return ctx


def _handle_await_material(message: str, ctx: Context, name: str) -> Context:
    """Validate material, publish order and reset context."""
    if message not in MATERIALS:
        whatsapp.send_text(
            ctx.phone,
            "❌ Material não reconhecido. Por favor, clique em uma das opções:",
        )
        whatsapp.send_interactive_list(ctx.phone, "Qual material será usado?", MATERIALS)
        return ctx

    ctx.data["material"] = message

    # Build and publish order
    order: dict[str, Any] = {
        "phone": ctx.phone,
        "name": name,
        "product": ctx.data.get("product"),
        "width_mm": ctx.data.get("width_mm"),
        "height_mm": ctx.data.get("height_mm"),
        "shelves": ctx.data.get("shelves"),
        "material": ctx.data.get("material"),
    }

    _publish_order(order)

    whatsapp.send_text(
        ctx.phone,
        f"✅ Perfeito, {name}! Seu pedido foi registrado com sucesso.\n\n"
        f"*Produto:* {order['product']}\n"
        f"*Largura:* {order['width_mm']}mm\n"
        f"*Altura:* {order['height_mm']}mm\n"
        f"*Prateleiras:* {order['shelves']}\n"
        f"*Material:* {order['material']}\n\n"
        "Estamos processando sua solicitação e em instantes enviaremos a imagem. 🎨"
    )

    ctx.step = "DONE"
    return ctx


# ---------------------------------------------------------------------------
# Step router
# ---------------------------------------------------------------------------
_HANDLERS: dict[str, StepHandler] = {
    "START": _handle_start,
    "AWAIT_PRODUCT": _handle_await_product,
    "AWAIT_WIDTH": _handle_await_width,
    "AWAIT_HEIGHT": _handle_await_height,
    "AWAIT_SHELVES": _handle_await_shelves,
    "AWAIT_MATERIAL": _handle_await_material,
}


def process(phone: str, message: str, name: str) -> None:
    """
    Main entry point for the flow engine.

    Loads context, routes to the correct step handler,
    persists or deletes context, and handles exceptions gracefully.
    """
    ctx = ctx_module.load(phone)
    logger.info("Processing — phone=%s step=%s message=%r", phone, ctx.step, message)

    handler = _HANDLERS.get(ctx.step, _handle_start)
    updated_ctx = handler(message, ctx, name)

    if updated_ctx.step == "DONE":
        ctx_module.delete(phone)
    else:
        ctx_module.save(updated_ctx)


# ---------------------------------------------------------------------------
# SQS publisher
# ---------------------------------------------------------------------------
def _publish_order(order: dict[str, Any]) -> None:
    if not OUTPUT_SQS_URL:
        logger.warning("OUTPUT_SQS_URL not set — order not published: %s", order)
        return

    _sqs.send_message(
        QueueUrl=OUTPUT_SQS_URL,
        MessageBody=json.dumps(order, ensure_ascii=False),
    )
    logger.info("Order published to SQS: %s", order)
