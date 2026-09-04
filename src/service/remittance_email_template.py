from decimal import Decimal

from src.model.remittance import AllowedCoins, Remittance, RemittanceStatus

_COIN_LABELS = {
    AllowedCoins.EUR: "EUR",
    AllowedCoins.AOA: "AOA",
}

_STATUS_LABELS = {
    RemittanceStatus.IN_PROGRESS: "Em processamento",
    RemittanceStatus.SENT: "Enviada",
    RemittanceStatus.REJECTED: "Rejeitada",
}


def _format_amount(value: Decimal) -> str:
    """1234.5 -> '1.234,50' — milhares com '.', decimais com ',' (convenção PT/AO), sem
    depender do locale do sistema onde o backend está a correr."""
    quantized = value.quantize(Decimal("0.01"))
    integer_part, _, decimal_part = f"{quantized:,.2f}".partition(".")
    return f"{integer_part.replace(',', '.')},{decimal_part}"


def _mask_iban(iban: str) -> str:
    """Mesma máscara usada no frontend (ver maskIban em iban.ts) — só os últimos 4 caracteres,
    para não pôr o IBAN completo do destinatário em texto simples num email."""
    cleaned = iban.replace(" ", "")
    return f"•••• {cleaned[-4:]}" if len(cleaned) >= 4 else cleaned


def remittance_created_subject(remittance: Remittance) -> str:
    amount = _format_amount(remittance.amount)
    coin = _COIN_LABELS[remittance.source_coin]
    return f"Pedido de remessa criado — {amount} {coin}"


def render_remittance_created_email(client_name: str, remittance: Remittance) -> str:
    """
    HTML do email enviado assim que uma remessa é submetida (ver RemittanceService.submit) — um
    resumo de tudo o que foi pedido e o estado atual, para o cliente ficar sempre com um registo
    por email do que submeteu, mesmo que nunca mais abra a app.

    Nota: o método de pagamento (MB WAY / Referência Multibanco / Cartão, escolhido no
    frontend) não aparece aqui de propósito — nesta fase é só uma escolha de UI, o backend ainda
    não recebe nem persiste esse campo (ver PAYMENT_METHODS em types/transfer.ts no frontend).
    """
    status_label = _STATUS_LABELS[remittance.status]
    reference = str(remittance.id)[:8].upper()
    source_label = _COIN_LABELS[remittance.source_coin]
    target_label = _COIN_LABELS[remittance.target_coin]

    rows = [
        ("Referência", reference),
        ("Estado", status_label),
        ("Destinatário", remittance.recipient_name),
        ("IBAN do destinatário", _mask_iban(remittance.recipient_account_iban)),
        ("Enviaste", f"{_format_amount(remittance.amount)} {source_label}"),
        ("Taxa de serviço", f"{_format_amount(remittance.service_fee_amount)} {source_label}"),
        ("Taxa de câmbio", f"1 {source_label} = {_format_amount(remittance.exchange_rate)} {target_label}"),
        ("O destinatário recebe", f"{_format_amount(remittance.amount_converted)} {target_label}"),
    ]

    rows_html = "".join(
        f'<tr>'
        f'<td style="padding:10px 0;border-bottom:1px solid #E5E4EC;color:#60646C;font-size:14px;">{label}</td>'
        f'<td style="padding:10px 0;border-bottom:1px solid #E5E4EC;color:#000000;font-size:14px;'
        f'font-weight:600;text-align:right;">{value}</td>'
        f'</tr>'
        for label, value in rows
    )

    return f"""
    <div style="font-family:-apple-system,Helvetica,Arial,sans-serif;background:#F6F5FA;padding:32px 16px;">
      <div style="max-width:480px;margin:0 auto;background:#FFFFFF;border-radius:20px;overflow:hidden;">
        <div style="background:#5B4B9E;padding:24px;text-align:center;">
          <span style="color:#FFFFFF;font-size:18px;font-weight:700;">Sentchu</span>
        </div>
        <div style="padding:24px;">
          <p style="color:#000000;font-size:16px;margin:0 0 4px;">Olá, {client_name}.</p>
          <p style="color:#60646C;font-size:14px;margin:0 0 20px;">
            Recebemos o teu pedido de remessa. Aqui fica o resumo:
          </p>
          <table style="width:100%;border-collapse:collapse;">
            {rows_html}
          </table>
          <p style="color:#60646C;font-size:13px;margin:20px 0 0;">
            Vamos avisar-te assim que o estado mudar. Podes acompanhar esta remessa a qualquer
            momento no histórico da app.
          </p>
        </div>
      </div>
      <p style="color:#9A9AA0;font-size:12px;text-align:center;margin-top:16px;">
        Este é um email automático — não é preciso responder.
      </p>
    </div>
    """
