"""
StripeMbwayGateway isolado: request_payment (cria+confirma o PaymentIntent) e verify_webhook
(valida a assinatura do webhook). Nenhuma chamada de rede real — stripe.PaymentIntent.create e
stripe.Webhook.construct_event são substituídos (monkeypatch). O resto do fluxo é testado em
test_payment_service_mbway.py com um gateway falso.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
import stripe

from src.exception.exceptions import InvalidPaymentCallbackError, PaymentGatewayError
from src.external.service.stripe_mbway_service import StripeMbwayGateway


def test_request_payment_devolve_o_id_do_payment_intent(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="pi_123")

    monkeypatch.setattr(stripe.PaymentIntent, "create", staticmethod(fake_create))
    gateway = StripeMbwayGateway(api_key="sk_test_123")

    request_id = gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="912345678")

    assert request_id == "pi_123"
    assert captured["amount"] == 5000
    assert captured["currency"] == "eur"
    assert captured["payment_method_types"] == ["mb_way"]
    assert captured["payment_method_data"]["billing_details"]["phone"] == "+351912345678"
    assert captured["confirm"] is True
    assert captured["idempotency_key"] == "order-1"


def test_request_payment_formata_numero_ja_com_indicativo(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="pi_123")

    monkeypatch.setattr(stripe.PaymentIntent, "create", staticmethod(fake_create))
    gateway = StripeMbwayGateway(api_key="sk_test_123")

    gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="+351912345678")

    assert captured["payment_method_data"]["billing_details"]["phone"] == "+351912345678"


def test_request_payment_levanta_gateway_error_quando_stripe_recusa(monkeypatch):
    def fake_create(**kwargs):
        raise stripe.CardError("recusado", param=None, code=None)

    monkeypatch.setattr(stripe.PaymentIntent, "create", staticmethod(fake_create))
    gateway = StripeMbwayGateway(api_key="sk_test_123")

    with pytest.raises(PaymentGatewayError):
        gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="912345678")


def test_request_payment_levanta_gateway_error_sem_chave_configurada():
    gateway = StripeMbwayGateway(api_key=None)

    with pytest.raises(PaymentGatewayError):
        gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="912345678")


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
