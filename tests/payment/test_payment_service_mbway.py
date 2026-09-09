"""
PaymentService com o pagamento MB WAY real (via Stripe Checkout): execute_payment (pedir a
Checkout Session antes de gravar Payment+Remittance) e handle_stripe_webhook (o webhook
assíncrono que confirma ou falha o pagamento e é o que desbloqueia
RemittanceService.mark_as_sent, ver _transition_status/mark_as_sent em remittance_service.py).
Tudo com fakes em memória — sem base de dados nem rede real (a chamada de rede em si já está
coberta isoladamente em test_stripe_mbway_gateway.py).

A partir da mudança para Checkout Session, o Payment.provider_reference guardado no momento da
submissão é o id da Session ("cs_..."), não de um PaymentIntent — a Session não cria um
PaymentIntent de forma síncrona. Por isso o webhook passa a encontrar o Payment sobretudo pela
metadata.order_id (o próprio Payment.id) que viaja com o PaymentIntent assim que ele é criado do
lado da Stripe — ver _succeeded_event/_failed_event abaixo, que já embutem essa metadata.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from src.dto.payment_dto import CreateMbway, CreatePayment
from src.dto.remittance_dto import CreateRemittance
from src.exception.exceptions import InvalidPaymentCallbackError, PaymentGatewayError
from src.model.payment import Payment, PaymentStatus
from src.model.payment_method import PaymentMethod
from src.model.remittance import AllowedCoins, Remittance
from src.service.payment_service import PaymentService


class FakeStripeObject(dict):
    """Imita o essencial de um stripe.PaymentIntent real: um objecto com .to_dict() (usado em
    PaymentService.handle_stripe_webhook), sem ser literalmente um dict — para apanhar exactamente
    o bug que apareceu em produção (StripeObject deixou de suportar .get()/[] como um dict a
    partir do stripe-python v15; só .to_dict() funciona)."""

    def to_dict(self):
        return dict(self)


class FakeGateway:
    """Substitui StripeMbwayGateway: nem create_checkout_session nem verify_webhook fazem
    qualquer chamada de rede — devolvem o que o teste configurar."""

    def __init__(self, checkout_url="https://checkout.stripe.com/c/pay/cs_123", session_id="cs_123", error=None):
        self.checkout_url = checkout_url
        self.session_id = session_id
        self.error = error
        self.calls = []
        self.events = []

    def create_checkout_session(self, order_id, amount, success_url, cancel_url):
        self.calls.append((order_id, amount, success_url, cancel_url))
        if self.error:
            raise self.error
        return self.checkout_url, self.session_id

    def verify_webhook(self, payload, signature):
        if signature == "assinatura-invalida":
            raise InvalidPaymentCallbackError("Assinatura do callback inválida")
        return self.events.pop(0)


class FakePaymentRepo:
    def __init__(self):
        self._by_id = {}

    def get_by_id(self, payment_id):
        return self._by_id.get(payment_id)

    def save(self, payment):
        self._by_id[payment.id] = payment
        return payment

    def get_by_provider_reference(self, provider_reference):
        for payment in self._by_id.values():
            if payment.provider_reference == provider_reference:
                return payment
        return None


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


def test_execute_payment_pede_a_checkout_session_e_grava_payment_pendente():
    gateway = FakeGateway(checkout_url="https://checkout.stripe.com/c/pay/cs_999", session_id="cs_999")
    transaction_repo = FakePaymentTransactionRepo()
    service = make_service(gateway=gateway, transaction_repo=transaction_repo)

    create_payment = make_create_payment()
    returned_remittance, returned_payment, redirect_url = service.execute_payment(create_payment)

    assert len(gateway.calls) == 1
    assert len(transaction_repo.saved) == 1
    saved_payment, saved_rem, _ = transaction_repo.saved[0]
    assert saved_payment.status == PaymentStatus.PENDING
    assert saved_payment.provider_reference == "cs_999"
    assert redirect_url == "https://checkout.stripe.com/c/pay/cs_999"
    assert saved_rem is returned_remittance
    assert saved_payment is returned_payment

    # order_id passado ao gateway é o próprio Payment.id — é isso que o webhook usa depois para
    # encontrar este Payment via metadata.order_id (ver _get_payment_for_callback).
    order_id, amount, success_url, cancel_url = gateway.calls[0]
    assert order_id == str(saved_payment.id)
    assert amount == Decimal("50.00")
    assert success_url == f"sentchu://enviando?id={saved_payment.id}&paymentMethod=mbway"
    assert cancel_url == success_url


def test_execute_payment_sem_dados_mbway_ainda_cria_a_sessao():
    # O número de telemóvel deixou de ser exigido aqui — quem o pede agora é a própria página de
    # Checkout da Stripe, não este fluxo (ver o comentário em Mbway.execute).
    gateway = FakeGateway()
    transaction_repo = FakePaymentTransactionRepo()
    service = make_service(gateway=gateway, transaction_repo=transaction_repo)

    create_payment = make_create_payment(phone_number=None)
    service.execute_payment(create_payment)

    assert len(transaction_repo.saved) == 1


def test_execute_payment_gateway_recusado_nao_grava_nada():
    gateway = FakeGateway(error=PaymentGatewayError("recusado"))
    transaction_repo = FakePaymentTransactionRepo()
    service = make_service(gateway=gateway, transaction_repo=transaction_repo)

    with pytest.raises(PaymentGatewayError):
        service.execute_payment(make_create_payment())

    assert transaction_repo.saved == []


def _pending_payment(payment_id=None, reference="cs_999", amount=Decimal("50.00")):
    return Payment(
        id=payment_id or uuid4(),
        method=PaymentMethod.MBWAY,
        status=PaymentStatus.PENDING,
        amount=amount,
        provider_reference=reference,
    )


def _succeeded_event(order_id, provider_reference="pi_999", amount_cents=5000):
    return {
        "type": "payment_intent.succeeded",
        "data": {
            "object": FakeStripeObject(
                id=provider_reference,
                amount=amount_cents,
                amount_received=amount_cents,
                metadata={"order_id": str(order_id)},
            )
        },
    }


def _failed_event(order_id, provider_reference="pi_999", amount_cents=5000, message="Cancelado pelo cliente"):
    return {
        "type": "payment_intent.payment_failed",
        "data": {
            "object": FakeStripeObject(
                id=provider_reference,
                amount=amount_cents,
                last_payment_error={"message": message},
                metadata={"order_id": str(order_id)},
            )
        },
    }


def test_handle_stripe_webhook_confirma_pagamento_com_sucesso():
    payment = _pending_payment()
    payment_repo = FakePaymentRepo()
    payment_repo.save(payment)
    gateway = FakeGateway()
    gateway.events.append(_succeeded_event(order_id=payment.id))
    service = make_service(gateway=gateway, payment_repo=payment_repo)

    service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")

    updated = payment_repo.get_by_id(payment.id)
    assert updated.status == PaymentStatus.SUCCEEDED
    # provider_reference passa a ser o id do PaymentIntent (vindo do próprio evento), já não o
    # id da Checkout Session guardado na submissão — ver _confirm_payment.
    assert updated.provider_reference == "pi_999"


def test_handle_stripe_webhook_e_idempotente_para_evento_repetido():
    payment = _pending_payment()
    payment_repo = FakePaymentRepo()
    payment_repo.save(payment)
    gateway = FakeGateway()
    gateway.events.append(_succeeded_event(order_id=payment.id))
    gateway.events.append(_succeeded_event(order_id=payment.id))
    service = make_service(gateway=gateway, payment_repo=payment_repo)

    service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")
    service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")

    assert payment_repo.get_by_id(payment.id).status == PaymentStatus.SUCCEEDED


def test_handle_stripe_webhook_marca_como_failed():
    payment = _pending_payment()
    payment_repo = FakePaymentRepo()
    payment_repo.save(payment)
    gateway = FakeGateway()
    gateway.events.append(_failed_event(order_id=payment.id, message="Pedido expirou"))
    service = make_service(gateway=gateway, payment_repo=payment_repo)

    service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")

    updated = payment_repo.get_by_id(payment.id)
    assert updated.status == PaymentStatus.FAILED
    assert updated.failure_reason == "Pedido expirou"


def test_handle_stripe_webhook_sucesso_depois_de_falha_nao_reverte():
    payment = _pending_payment()
    payment_repo = FakePaymentRepo()
    payment_repo.save(payment)
    gateway = FakeGateway()
    gateway.events.append(_failed_event(order_id=payment.id))
    gateway.events.append(_succeeded_event(order_id=payment.id))
    service = make_service(gateway=gateway, payment_repo=payment_repo)

    service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")
    with pytest.raises(InvalidPaymentCallbackError):
        service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")

    assert payment_repo.get_by_id(payment.id).status == PaymentStatus.FAILED


def test_handle_stripe_webhook_assinatura_invalida_nao_altera_estado():
    payment = _pending_payment()
    payment_repo = FakePaymentRepo()
    payment_repo.save(payment)
    service = make_service(payment_repo=payment_repo)

    with pytest.raises(InvalidPaymentCallbackError):
        service.handle_stripe_webhook(payload=b"{}", signature="assinatura-invalida")

    assert payment_repo.get_by_id(payment.id).status == PaymentStatus.PENDING


def test_handle_stripe_webhook_valor_errado_nao_altera_estado():
    payment = _pending_payment()
    payment_repo = FakePaymentRepo()
    payment_repo.save(payment)
    gateway = FakeGateway()
    gateway.events.append(_succeeded_event(order_id=payment.id, amount_cents=999900))
    service = make_service(gateway=gateway, payment_repo=payment_repo)

    with pytest.raises(InvalidPaymentCallbackError):
        service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")

    assert payment_repo.get_by_id(payment.id).status == PaymentStatus.PENDING


def test_handle_stripe_webhook_referencia_desconhecida():
    gateway = FakeGateway()
    gateway.events.append(_succeeded_event(order_id=uuid4()))
    service = make_service(gateway=gateway)

    with pytest.raises(InvalidPaymentCallbackError):
        service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")


def test_handle_stripe_webhook_ignora_evento_irrelevante():
    payment = _pending_payment()
    payment_repo = FakePaymentRepo()
    payment_repo.save(payment)
    gateway = FakeGateway()
    gateway.events.append({
        "type": "payment_intent.created",
        "data": {"object": FakeStripeObject(id="pi_999", metadata={"order_id": str(payment.id)})},
    })
    service = make_service(gateway=gateway, payment_repo=payment_repo)

    service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")

    assert payment_repo.get_by_id(payment.id).status == PaymentStatus.PENDING


def test_handle_stripe_webhook_fallback_por_provider_reference_quando_sem_metadata():
    # Cobertura do fallback em _get_payment_for_callback — um evento sem metadata.order_id (não
    # deveria acontecer para MB WAY, mas outros métodos podem vir a confiar só no
    # provider_reference) ainda consegue encontrar o Payment se o id bater certo.
    payment = _pending_payment(reference="pi_999")
    payment_repo = FakePaymentRepo()
    payment_repo.save(payment)
    gateway = FakeGateway()
    gateway.events.append({
        "type": "payment_intent.succeeded",
        "data": {"object": FakeStripeObject(id="pi_999", amount=5000, amount_received=5000)},
    })
    service = make_service(gateway=gateway, payment_repo=payment_repo)

    service.handle_stripe_webhook(payload=b"{}", signature="assinatura-valida")

    assert payment_repo.get_by_id(payment.id).status == PaymentStatus.SUCCEEDED
