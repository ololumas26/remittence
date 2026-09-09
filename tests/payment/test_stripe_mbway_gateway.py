"""
StripeMbwayGateway isolado: create_checkout_session (cria a Checkout Session MB WAY) e
verify_webhook (valida a assinatura do webhook). Nenhuma chamada de rede real —
stripe.checkout.Session.create e stripe.Webhook.construct_event são substituídos (monkeypatch).
O resto do fluxo é testado em test_payment_service_mbway.py com um gateway falso.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
import stripe

from src.exception.exceptions import InvalidPaymentCallbackError, PaymentGatewayError
from src.external.service.stripe_mbway_service import StripeMbwayGateway


def test_create_checkout_session_devolve_url_e_id_da_session(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_123", id="cs_123")

    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_create))
    gateway = StripeMbwayGateway(api_key="sk_test_123")

    checkout_url, session_id = gateway.create_checkout_session(
        order_id="order-1",
        amount=Decimal("50.00"),
        success_url="sentchu://enviando?id=order-1&paymentMethod=mbway",
        cancel_url="sentchu://enviando?id=order-1&paymentMethod=mbway",
        customer_email="cliente@example.com",
    )

    assert checkout_url == "https://checkout.stripe.com/c/pay/cs_123"
    assert session_id == "cs_123"
    assert captured["mode"] == "payment"
    assert captured["payment_method_types"] == ["mb_way"]
    assert captured["line_items"][0]["price_data"]["currency"] == "eur"
    assert captured["line_items"][0]["price_data"]["unit_amount"] == 5000
    assert captured["payment_intent_data"]["metadata"]["order_id"] == "order-1"
    assert captured["success_url"] == "sentchu://enviando?id=order-1&paymentMethod=mbway"
    assert captured["customer_email"] == "cliente@example.com"
    assert captured["idempotency_key"] == "order-1"


def test_create_checkout_session_sem_email_nao_manda_o_parametro(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_123", id="cs_123")

    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_create))
    gateway = StripeMbwayGateway(api_key="sk_test_123")

    gateway.create_checkout_session(
        order_id="order-1",
        amount=Decimal("50.00"),
        success_url="sentchu://enviando",
        cancel_url="sentchu://enviando",
    )

    assert "customer_email" not in captured


def test_create_checkout_session_levanta_gateway_error_quando_stripe_recusa(monkeypatch):
    def fake_create(**kwargs):
        raise stripe.CardError("recusado", param=None, code=None)

    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(fake_create))
    gateway = StripeMbwayGateway(api_key="sk_test_123")

    with pytest.raises(PaymentGatewayError):
        gateway.create_checkout_session(
            order_id="order-1",
            amount=Decimal("50.00"),
            success_url="sentchu://enviando",
            cancel_url="sentchu://enviando",
        )


def test_create_checkout_session_levanta_gateway_error_sem_chave_configurada():
    gateway = StripeMbwayGateway(api_key=None)

    with pytest.raises(PaymentGatewayError):
        gateway.create_checkout_session(
            order_id="order-1",
            amount=Decimal("50.00"),
            success_url="sentchu://enviando",
            cancel_url="sentchu://enviando",
        )


def test_verify_webhook_devolve_o_evento_quando_assinatura_valida(monkeypatch):
    fake_event = {"type": "payment_intent.succeeded", "data": {"object": {"id": "pi_123"}}}
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda payload, sig, secret: fake_event)

    gateway = StripeMbwayGateway(webhook_secret="whsec_teste")

    event = gateway.verify_webhook(payload=b"{}", signature="assinatura-valida")

    assert event == fake_event


def test_verify_webhook_levanta_erro_com_assinatura_invalida(monkeypatch):
    def fake_construct_event(payload, sig, secret):
        raise stripe.SignatureVerificationError("assinatura inválida", sig_header=sig)

    monkeypatch.setattr(stripe.Webhook, "construct_event", fake_construct_event)
    gateway = StripeMbwayGateway(webhook_secret="whsec_teste")

    with pytest.raises(InvalidPaymentCallbackError):
        gateway.verify_webhook(payload=b"{}", signature="assinatura-errada")


def test_verify_webhook_levanta_erro_sem_secret_configurado():
    gateway = StripeMbwayGateway(webhook_secret=None)

    with pytest.raises(InvalidPaymentCallbackError):
        gateway.verify_webhook(payload=b"{}", signature="qualquer-coisa")
