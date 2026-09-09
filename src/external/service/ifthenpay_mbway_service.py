import logging
import os
from decimal import Decimal

import httpx
from dotenv import load_dotenv

from src.exception.exceptions import PaymentGatewayError

load_dotenv()

logger = logging.getLogger("remittance")

IFTHENPAY_MBWAY_KEY = os.environ.get("IFTHENPAY_MBWAY_KEY")
IFTHENPAY_MBWAY_REQUEST_URL = "https://api.ifthenpay.com/spg/payment/mbway"

# Status devolvido pelo PEDIDO de pagamento (endpoint /spg/payment/mbway) — '000' aqui só
# significa que o pedido foi aceite e a notificação push foi enviada para o telemóvel do
# cliente. NÃO significa que o pagamento já foi feito: essa confirmação chega depois, de forma
# assíncrona, via callback (ver PaymentService.confirm_mbway_payment /
# payment_controller.mbway_callback).
REQUEST_STATUS_ACCEPTED = "000"


class IfthenpayMbwayGateway:
    """
    Fina camada sobre a API MB WAY da ifthenpay (https://ifthenpay.com/mbway/) para iniciar um
    pedido de pagamento. Ao contrário do EmailService, uma falha aqui É propagada (levanta
    PaymentGatewayError) — ao contrário de um email, um pagamento que falhou a iniciar não pode
    ser tratado como "melhor esforço": a remessa não deve avançar sem um pedido de pagamento
    aceite pela ifthenpay.
    """

    def __init__(
        self,
        mbway_key: str | None = IFTHENPAY_MBWAY_KEY,
        request_url: str = IFTHENPAY_MBWAY_REQUEST_URL,
        timeout: float = 10.0,
    ):
        self.mbway_key = mbway_key
        self.request_url = request_url
        self.timeout = timeout

    def request_payment(self, order_id: str, amount: Decimal, phone_number: str) -> str:
        """Inicia o pedido de pagamento MB WAY. Devolve o RequestId da ifthenpay (guardado como
        Payment.provider_reference — é ele que liga o callback de confirmação ao Payment certo).
        Levanta PaymentGatewayError se a ifthenpay recusar o pedido ou não responder."""

        if not self.mbway_key:
            logger.error("IFTHENPAY_MBWAY_KEY não configurada — não é possível iniciar pagamentos MB WAY")
            raise PaymentGatewayError("Pagamentos MB WAY não estão configurados de momento.")

        payload = {
            "mbWayKey": self.mbway_key,
            "orderId": order_id,
            "amount": str(amount),
            "mobileNumber": self._format_phone(phone_number),
            "description": f"Sentchu - remessa {order_id}",
        }

        try:
            response = httpx.post(self.request_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            logger.exception("Falha de rede/HTTP ao pedir pagamento MB WAY (order_id=%s)", order_id)
            raise PaymentGatewayError("Não foi possível contactar o MB WAY neste momento. Tenta novamente.")
        except ValueError:
            logger.exception(
                "Resposta inválida (não-JSON) da ifthenpay ao pedir pagamento MB WAY (order_id=%s)", order_id
            )
            raise PaymentGatewayError("Resposta inesperada do MB WAY. Tenta novamente.")

        if data.get("Status") != REQUEST_STATUS_ACCEPTED:
            message = data.get("Message") or "Pedido de pagamento MB WAY recusado."
            logger.warning("Pedido MB WAY recusado (order_id=%s): %s", order_id, message)
            raise PaymentGatewayError(message)

        request_id = data.get("RequestId")
        if not request_id:
            logger.error("Resposta MB WAY sem RequestId (order_id=%s): %s", order_id, data)
            raise PaymentGatewayError("Resposta inesperada do MB WAY. Tenta novamente.")

        return request_id

    @staticmethod
    def _format_phone(phone_number: str) -> str:
        # A API espera o indicativo separado do número por '#' (ex: "351#912345678"). Aceita-se
        # aqui tanto um número já nesse formato como só os dígitos nacionais — assume-se sempre
        # Portugal (+351), único país onde o MB WAY está disponível.
        cleaned = phone_number.strip()

        if "#" in cleaned:
            return cleaned

        digits = "".join(ch for ch in cleaned if ch.isdigit())

        if digits.startswith("351") and len(digits) > 9:
            digits = digits[-9:]

        return f"351#{digits}"
