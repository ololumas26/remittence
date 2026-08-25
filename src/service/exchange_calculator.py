from decimal import Decimal


def calculate_service_fee_amount(amount: Decimal, service_fee_rate: Decimal) -> Decimal:
    return amount * service_fee_rate


def calculate_amount_converted(amount: Decimal, exchange_rate: Decimal, service_fee_amount: Decimal) -> Decimal:
    return (amount  - service_fee_amount) * exchange_rate
