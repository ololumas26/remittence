import logging
import os

import resend
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("remittance")

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
# os.environ.get(key, default) só usa o default quando a chave NÃO EXISTE no ambiente — uma
# variável presente mas vazia (ex: "RESEND_FROM_EMAIL=" no .env, sem valor a seguir ao "=") conta
# como existente, com valor "". Foi exatamente isto que aconteceu: o Resend recebia from="" e
# respondia "The domain is invalid" (uma string vazia não tem domínio nenhum). O `or` aqui cobre
# os dois casos — chave ausente OU vazia — caindo sempre no endereço de sandbox do Resend.
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL") or "Sentchu <onboarding@resend.dev>"


class EmailService:
    """
    Fina camada sobre a API do Resend para emails transacionais (ex: confirmação de remessa
    submetida — ver RemittanceService.submit). Deliberadamente nunca levanta exceção: quem chama
    isto trata o envio de email como "melhor esforço" — uma falha aqui não deve impedir a
    operação principal (a remessa continua submetida mesmo que o email falhe).
    """

    def __init__(self, api_key: str | None = RESEND_API_KEY, from_email: str = RESEND_FROM_EMAIL):
        self.api_key = api_key
        self.from_email = from_email

    def send(self, to: str, subject: str, html: str) -> None:
        if not self.api_key:
            logger.warning("RESEND_API_KEY não configurada — email '%s' para %s não foi enviado", subject, to)
            return

        try:
            resend.api_key = self.api_key
            resend.Emails.send({
                "from": self.from_email,
                # Subbstituir para o email real do cliente depois que configurar o SMTP do resend
                "to": [to],
                "subject": subject,
                "html": html,
            })
        except Exception:
            logger.exception("Falha ao enviar email '%s' para %s via Resend", subject, to)
