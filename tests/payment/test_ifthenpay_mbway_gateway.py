"""
IfthenpayMbwayGateway.request_payment é a única chamada de rede real do fluxo de pagamento MB
WAY (POST https://api.ifthenpay.com/spg/payment/mbway) — testado aqui isoladamente, sem tocar na
rede, substituindo httpx.post por um stub (monkeypatch). O resto do fluxo (PaymentService a
construir o Payment/Remittance e a confirmação por callback) é testado em
test_payment_service_mbway.py com um gateway falso.
"""

from decimal import Decimal

import httpx
import pytest

from src.exception.exceptions import PaymentGatewayError
from src.external.service.ifthenpay_mbway_service import IfthenpayMbwayGateway


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)

    def json(self):
        return self._json_data


def make_gateway(monkeypatch, response=None, raise_error=None):
    gateway = IfthenpayMbwayGateway(mbway_key="chave-teste")

    def fake_post(url, json, timeout):
        if raise_error is not None:
            raise raise_error
        return response

    monkeypatch.setattr(httpx, "post", fake_post)
    return gateway


def test_request_payment_devolve_request_id_quando_aceite(monkeypatch):
    gateway = make_gateway(
        monkeypatch,
        response=FakeResponse({"Status": "000", "RequestId": "abc123", "Message": "Success"}),
    )

    request_id = gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="912345678")

    assert request_id == "abc123"


def test_request_payment_formata_numero_com_indicativo(monkeypatch):
    captured = {}
    gateway = IfthenpayMbwayGateway(mbway_key="chave-teste")

    def fake_post(url, json, timeout):
        captured.update(json)
        return FakeResponse({"Status": "000", "RequestId": "abc123"})

    monkeypatch.setattr(httpx, "post", fake_post)

    gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="912345678")

    assert captured["mobileNumber"] == "351#912345678"
    assert captured["orderId"] == "order-1"
    assert captured["amount"] == "50.00"


def test_request_payment_levanta_gateway_error_quando_recusado(monkeypatch):
    gateway = make_gateway(
        monkeypatch,
        response=FakeResponse({"Status": "999", "Message": "Chave inválida"}),
    )

    with pytest.raises(PaymentGatewayError):
        gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="912345678")


def test_request_payment_levanta_gateway_error_em_falha_de_rede(monkeypatch):
    gateway = make_gateway(monkeypatch, raise_error=httpx.ConnectError("falhou"))

    with pytest.raises(PaymentGatewayError):
        gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="912345678")


def test_request_payment_levanta_gateway_error_sem_chave_configurada():
    gateway = IfthenpayMbwayGateway(mbway_key=None)

    with pytest.raises(PaymentGatewayError):
        gateway.request_payment(order_id="order-1", amount=Decimal("50.00"), phone_number="912345678")
