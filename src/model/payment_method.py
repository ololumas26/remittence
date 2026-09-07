from enum import Enum


class PaymentMethod(Enum):
    """
    Ficheiro à parte (não em model/remittance.py nem em dto/payment_dto.py) para evitar import
    circular: CreateRemittance (dto/remittance_dto.py) precisa disto, e CreatePayment
    (dto/payment_dto.py) precisa de CreateRemittance — se este enum vivesse num dos dois, o
    outro ficaria a importar de si próprio por tabela.
    """

    MBWAY = 'mbway'
    CARD = 'card'
    MULTIBANK = 'multibank'
