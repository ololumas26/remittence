"""
PaymentService com o pagamento MB WAY real: execute_payment (pedir o pagamento à ifthenpay antes
de gravar Payment+Remittance) e confirm_mbway_payment (o callback assíncrono que confirma o
pagamento e é o que desbloqueia RemittanceService.mark_as_sent, ver
_transition_status/mark_as_sent em remittance_service.py). Tudo com fakes em memória — sem base
de dados nem rede real (a chamada de rede em si já está coberta isoladamente em
test_ifthenpay_mbway_gateway.py).
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.dto.payment_dto import CreateMbway, CreatePayment
from src.dto.remittance_dto import CreateRemittance
from src.exception.exceptions import InvalidPaymentCallbackError, InvalidPaymentDataError, PaymentGatewayError
from src.model.payment import Payment, PaymentStatus
from src.model.payment_method import PaymentMethod
from src.model.remittance import AllowedCoins, Remittance
from src.service.payment_service import PaymentService


class FakeGateway:
    """Substitui IfthenpayMbwayGateway: não faz nenhuma chamada de rede, só devolve o que o
    teste configurar (um RequestId de sucesso, ou levanta PaymentGatewayError)."""

    def __init__(self, request_id="req-123", error=None):
        self.request_id = request_id
        self.error = error
        self.calls = []

    def request_payment(self, order_id, amount, phone_number):
        self.calls.append((order_id, amount, phone_number))
        if self.error:
            raise self.error
        return self.request_id


class FakePaymentRepo:
    def __init__(self):
        self._by_reference = {}

    def get_by_id(self, payment_id):
        for payment in self._by_reference.values():
            if payment.id == payment_id:
                return payment
        return None

    def save(self, payment):
        self._by_reference[payment.provider_reference] = payment
        return payment

    def get_by_provider_reference(self, provider_reference):
        return self._by_reference.get(provider_reference)


class FakePaymentTransactionRepo:
    def __init__(self):
        self.saved = []

    def save(self, payment, remittance, notification):
        remittance.payment_id = payment.id
        self.saved.append((payment, remittance, notification))
        return payment, remittance


class FakeRemittanceService:
    def __init__(self):
        self.sent_emails = []
        self.built = []

    def build_remittance(self, create_remittance, ip_address=""):
        remittance = Remittance(
            client_id=create_remittance.client_id,
            recipient_id=create_remittance.recipient_id,
            service_fee_rate=Decimal("0.02"),
            amount=create_remittance.amount,
            amount_converted=create_remittance.amount * Decimal("1000"),
            source_coin=create_remittance.source_coin,
            target_coin=create_remittance.target_coin,
            service_fee_amount=Decimal("1.00"),
            exchange_rate=Decimal("1000"),
            recipient_name="Recipiente Teste",
            recipient_account_iban="AO0600000000000000000000",
            recipient_bank_code="006",
        )
        client = type("Client", (), {"id": create_remittance.client_id, "name": "Cliente Teste"})()
        self.built.append(remittance)
        return remittance, client

    def send_created_email(self, client, remittance):
        self.sent_emails.append((client, remittance))


def make_service(gateway=None, payment_repo=None, transaction_repo=None):
    return PaymentService(
        remittance_service=FakeRemittanceService(),
        payment_transaction_repository=transaction_repo or FakePaymentTransactionRepo(),
        payment_repository=payment_repo or FakePaymentRepo(),
        mbway_gateway=gateway or FakeGateway(),
        mbway_callback_key="segredo-teste",
    )


def make_create_payment(phone_number="912345678", amount=Decimal("50.00")):
    return CreatePayment(
        remittance=CreateRemittance(
            client_id=uuid4(),
            recipient_id=uuid4(),
            amount=amount,
            source_coin=AllowedCoins.EUR,
            target_coin=AllowedCoins.AOA,
            payment_method=PaymentMethod.MBWAY,
        ),
        mbway=CreateMbway(phone_number=phone_number),
    )


def test_execute_payment_pede_o_pagamento_e_grava_payment_pendente():
    gateway = FakeGateway(request_id="req-999")
    transaction_repo = FakePaymentTransactionRepo()
    service = make_service(gateway=gateway, transaction_repo=transaction_repo)

    create_payment = make_create_payment()
    saved_remittance = service.execute_payment(create_payment)

    assert len(gateway.calls) == 1
    assert len(transaction_repo.saved) == 1
    saved_payment, saved_rem, _ = transaction_repo.saved[0]
    assert saved_payment.status == PaymentStatus.PENDING
    assert saved_payment.provider_reference == "req-999"
    assert saved_rem is saved_remittance


def test_execute_payment_sem_numero_de_telemovel_levanta_erro_sem_gravar():
    transaction_repo = FakePaymentTransactionRepo()
    service = make_service(transaction_repo=transaction_repo)

    create_payment = make_create_payment(phone_number=None)

    with pytest.raises(InvalidPaymentDataError):
        service.execute_payment(create_payment)

    assert transaction_repo.saved == []


def test_execute_payment_gateway_recusado_nao_grava_nada():
    gateway = FakeGateway(error=PaymentGatewayError("recusado"))
    transaction_repo = FakePaymentTransactionRepo()
    service = make_service(gateway=gateway, transaction_repo=transaction_repo)

    with pytest.raises(PaymentGatewayError):
        service.execute_payment(make_create_payment())

    assert transaction_repo.saved == []


def _pending_payment(reference="req-999", amount=Decimal("50.00")):
    return Payment(
        id=uuid4(),
        method=PaymentMethod.MBWAY,
        status=PaymentStatus.PENDING,
        amount=amount,
        provider_reference=reference,
    )


def test_confirm_mbway_payment_marca_como_succeeded():
    payment_repo = FakePaymentRepo()
    payment = _pending_payment()
    payment_repo.save(payment)
    service = make_service(payment_repo=payment_repo)

    confirmed = service.confirm_mbway_payment(
        antiphishing_key="segredo-teste", transaction_id="req-999", amount="50.00"
    )

    assert confirmed.status == PaymentStatus.SUCCEEDED


def test_confirm_mbway_payment_e_idempotente_para_callback_repetido():
    payment_repo = FakePaymentRepo()
    payment = _pending_payment()
    payment_repo.save(payment)
    service = make_service(payment_repo=payment_repo)

    service.confirm_mbway_payment(antiphishing_key="segredo-teste", transaction_id="req-999", amount="50.00")
    confirmed_again = service.confirm_mbway_payment(
        antiphishing_key="segredo-teste", transaction_id="req-999", amount="50.00"
    )

    assert confirmed_again.status == PaymentStatus.SUCCEEDED


def test_confirm_mbway_payment_chave_errada_nao_altera_estado():
    payment_repo = FakePaymentRepo()
    payment = _pending_payment()
    payment_repo.save(payment)
    service = make_service(payment_repo=payment_repo)

    with pytest.raises(InvalidPaymentCallbackError):
        service.confirm_mbway_payment(antiphishing_key="chave-errada", transaction_id="req-999", amount="50.00")

    assert payment_repo.get_by_provider_reference("req-999").status == PaymentStatus.PENDING


def test_confirm_mbway_payment_valor_errado_nao_altera_estado():
    payment_repo = FakePaymentRepo()
    payment = _pending_payment()
    payment_repo.save(payment)
    service = make_service(payment_repo=payment_repo)

    with pytest.raises(InvalidPaymentCallbackError):
        service.confirm_mbway_payment(antiphishing_key="segredo-teste", transaction_id="req-999", amount="999.00")

    assert payment_repo.get_by_provider_reference("req-999").status == PaymentStatus.PENDING


def test_confirm_mbway_payment_referencia_desconhecida():
    service = make_service()

    with pytest.raises(InvalidPaymentCallbackError):
        service.confirm_mbway_payment(antiphishing_key="segredo-teste", transaction_id="inexistente", amount="50.00")
