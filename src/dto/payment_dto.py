from pydantic import BaseModel

from src.dto.remittance_dto import CreateRemittance


class BasePaymentMethod(BaseModel):
    client_id : str | None = None

class CreateMbway(BasePaymentMethod):
    phone_number : str | None = None

class CreatMultibank(BasePaymentMethod):
    multibank_reference : str | None = None

class CreateCard(BasePaymentMethod):
    card_holder : str | None = None
    card_number : str | None = None  # TODO: Não esquecer de encriptar esse número
    expiration : str
    cv : str | None = None

class CreatePayment(BaseModel):
    # Dados da remessa (destinatário, montante, moedas, método escolhido) — a rota de pagamento
    # passa a ser o único sítio onde o pedido de remessa é recebido; já não se chama
    # POST /remittance diretamente a partir do frontend para isto.
    remittance : CreateRemittance
    mbway : CreateMbway | None = None
    card : CreateCard | None = None
    multibank : CreatMultibank | None = None



payment_dto = {
    'mbway' : {
        'phone_number': 99999999,
        'user_id' : 'normalmente vem da sessão do utilizador'
    },
    'card' : {
        'card_holder': '',
        'card_number': 'esse número deve ser encriptado',
        'expiration': 'ano e mês de expiração',
        'cv': 'esse número deve ser encriptado'
    },
    'multibank' : 'referencia de pagamento'
}
