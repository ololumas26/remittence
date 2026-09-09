"""
Concorrência ao mudar o estado de uma remessa: dois membros do staff podem, em teoria,
tentar marcar a mesma remessa como enviada/rejeitada ao mesmo tempo (ou o mesmo staff
pode repetir o pedido, ex: duplo clique / retry de rede). RemittanceService._transition_status
tem de ser idempotente para o caso "mesmo estado pretendido" e continuar a recusar um
conflito real (ex: já rejeitada, agora tentam marcar como enviada).

Usa fakes em memória para os repositórios — sem tocar na base de dados real (ver
SqlRemittanceRepository.transition_status para a versão que faz o UPDATE atómico condicional
de verdade; aqui testamos só a lógica de decisão em RemittanceService).
"""

import pytest
from uuid import uuid4

from src.service.remittance_service import RemittanceService
from src.model.remittance import Remittance, RemittanceStatus, AllowedCoins
from src.model.payment import Payment, PaymentStatus
from src.exception.exceptions import InvalidRemittanceStatusError, ResourceNotFoundError


class FakeRemittanceRepo:
    """Simula a tabela remittance com um UPDATE condicional atómico (compare-and-swap em
    memória), tal como o SqlRemittanceRepository real faz na base de dados."""

    def __init__(self, remittance: Remittance):
        self._by_id = {remittance.id: remittance}
        # Quantas vezes a transição "venceu" de facto (para os testes de corrida abaixo
        # simularem um concorrente que já ganhou antes desta chamada correr).
        self.transition_calls = 0

    def get_by_id(self, remittance_id):
        return self._by_id.get(remittance_id)

    def transition_status(self, remittance_id, new_status):
        self.transition_calls += 1
        current = self._by_id[remittance_id]
        if current.status != RemittanceStatus.IN_PROGRESS:
            return None
        current.status = new_status
        return current


class RacingRemittanceRepo(FakeRemittanceRepo):
    """Simula um concorrente que vence a corrida entre a leitura e o UPDATE condicional:
    a primeira chamada a transition_status já encontra o estado mudado por "outro pedido"."""

    def transition_status(self, remittance_id, new_status):
        current = self._by_id[remittance_id]
        # O "concorrente" já ganhou antes desta transação correr.
        current.status = new_status
        return None


class FakeClientRepo:
    def __init__(self, client=None):
        self._client = client

    def get_by_id(self, client_id):
        return self._client


class FakePaymentRepo:
    def __init__(self, payment: Payment | None):
        self._payment = payment

    def get_by_id(self, payment_id):
        return self._payment


def make_remittance(status=RemittanceStatus.IN_PROGRESS, payment_id=None) -> Remittance:
    return Remittance(
        id=uuid4(),
        client_id=uuid4(),
        recipient_id=uuid4(),
        payment_id=payment_id or uuid4(),
        amount=100,
        source_coin=AllowedCoins.EUR,
        target_coin=AllowedCoins.AOA,
        service_fee_rate=0,
        service_fee_amount=0,
        exchange_rate=1,
        amount_converted=100,
        recipient_name="Destinatário",
        recipient_account_iban="PT50",
        recipient_bank_code="0001",
        status=status,
    )


def make_service(remittance_repo, payment=None, client=None) -> RemittanceService:
    return RemittanceService(
        remittance_repository=remittance_repo,
        client_repository=FakeClientRepo(client),
        document_repository=None,
        recipient_repository=None,
        geolocation_service=None,
        email_service=None,
        payment_repository=FakePaymentRepo(payment),
    )


class TestTransitionIdempotency:

    def test_marcar_como_enviada_e_repetir_e_idempotente(self):
        """Segundo pedido (mesmo staff a repetir, ou outro staff a clicar depois) para o MESMO
        estado não deve dar erro — só confirma o que já aconteceu."""
        payment = Payment(id=uuid4(), status=PaymentStatus.SUCCEEDED)
        remittance = make_remittance(payment_id=payment.id)
        repo = FakeRemittanceRepo(remittance)
        service = make_service(repo, payment=payment)

        first = service.mark_as_sent(str(remittance.id))
        assert first.status == RemittanceStatus.SENT

        # Repetir o mesmo pedido não deve levantar InvalidRemittanceStatusError.
        second = service.mark_as_sent(str(remittance.id))
        assert second.status == RemittanceStatus.SENT
        # Só a primeira chamada tentou de facto o UPDATE condicional na BD.
        assert repo.transition_calls == 1

    def test_dois_staff_em_corrida_para_o_mesmo_estado_nao_da_erro(self):
        """Simula a janela de corrida real: entre a leitura e o UPDATE condicional, outro
        pedido já ganhou e pôs a remessa no MESMO estado pretendido — deve ser tratado como
        sucesso idempotente, não como conflito."""
        payment = Payment(id=uuid4(), status=PaymentStatus.SUCCEEDED)
        remittance = make_remittance(payment_id=payment.id)
        repo = RacingRemittanceRepo(remittance)
        service = make_service(repo, payment=payment)

        result = service.mark_as_sent(str(remittance.id))
        assert result.status == RemittanceStatus.SENT

    def test_estado_terminal_diferente_continua_a_dar_erro(self):
        """Já rejeitada, agora tentam marcar como enviada — conflito real, tem de continuar a
        recusar (não é a mesma transição a repetir-se)."""
        payment = Payment(id=uuid4(), status=PaymentStatus.SUCCEEDED)
        remittance = make_remittance(status=RemittanceStatus.REJECTED, payment_id=payment.id)
        repo = FakeRemittanceRepo(remittance)
        service = make_service(repo, payment=payment)

        with pytest.raises(InvalidRemittanceStatusError):
            service.mark_as_sent(str(remittance.id))

    def test_marcar_como_enviada_sem_pagamento_sucedido_continua_a_falhar(self):
        remittance = make_remittance()
        repo = FakeRemittanceRepo(remittance)
        service = make_service(repo, payment=None)

        with pytest.raises(ResourceNotFoundError):
            service.mark_as_sent(str(remittance.id))
