from decimal import Decimal

APP_PREFIX = '/api/v1'
MAJOR_AGE = 18
MIN_AMOUNT = 50

# TODO: valores temporários (1:1, sem taxas) — substituir pelos valores reais
# assim que houver uma fonte confiável (config do parceiro bancário ou API de câmbio).
EXCHANGE_RATE = Decimal('1300')
SERVICE_FEE_RATE = Decimal('0.05')
