from src.model.document import Document


def document_approved_subject(document: Document) -> str:
    return f"O teu {document.document_type.value} foi aprovado"


def document_rejected_subject(document: Document) -> str:
    return f"O teu {document.document_type.value} foi rejeitado"


def _wrap(client_name: str, body_html: str) -> str:
    """Mesmo invólucro visual dos emails de remessa (ver remittance_email_template.py) —
    cabeçalho roxo com o nome "Sentchu", corpo branco arredondado, rodapé cinzento."""
    return f"""
    <div style="font-family:-apple-system,Helvetica,Arial,sans-serif;background:#F6F5FA;padding:32px 16px;">
      <div style="max-width:480px;margin:0 auto;background:#FFFFFF;border-radius:20px;overflow:hidden;">
        <div style="background:#5B4B9E;padding:24px;text-align:center;">
          <span style="color:#FFFFFF;font-size:18px;font-weight:700;">Sentchu</span>
        </div>
        <div style="padding:24px;">
          <p style="color:#000000;font-size:16px;margin:0 0 4px;">Olá, {client_name}.</p>
          {body_html}
        </div>
      </div>
      <p style="color:#9A9AA0;font-size:12px;text-align:center;margin-top:16px;">
        Este é um email automático — não é preciso responder.
      </p>
    </div>
    """


def render_document_approved_email(client_name: str, document: Document) -> str:
    """
    HTML do email enviado quando a equipa de verificação aprova um documento (ver
    DocumentService.approve) — para o cliente saber, sem ter de voltar à app, que já não
    precisa de fazer mais nada quanto a esse documento.
    """
    body = f"""
      <p style="color:#60646C;font-size:14px;margin:0 0 20px;">
        Boas notícias — o teu <strong>{document.document_type.value}</strong>
        (nº {document.document_number}) foi aprovado.
      </p>
      <p style="color:#60646C;font-size:13px;margin:20px 0 0;">
        Podes acompanhar o estado de todos os teus documentos a qualquer momento na app, em
        Conta → Verificação de identidade.
      </p>
    """
    return _wrap(client_name, body)


def render_document_rejected_email(client_name: str, document: Document, note: str) -> str:
    """
    HTML do email enviado quando um documento é rejeitado — inclui sempre o motivo (note),
    para o cliente saber o que corrigir sem ter de contactar o suporte.
    """
    body = f"""
      <p style="color:#60646C;font-size:14px;margin:0 0 16px;">
        O teu <strong>{document.document_type.value}</strong> (nº {document.document_number})
        foi rejeitado.
      </p>
      <div style="background:#FCEBEA;border-radius:12px;padding:14px 16px;margin:0 0 20px;">
        <p style="color:#8A2A22;font-size:13px;margin:0;font-weight:600;">Motivo</p>
        <p style="color:#8A2A22;font-size:13px;margin:4px 0 0;">{note}</p>
      </div>
      <p style="color:#60646C;font-size:13px;margin:0;">
        Podes submeter um novo documento a qualquer momento na app, em Conta → Verificação de
        identidade.
      </p>
    """
    return _wrap(client_name, body)
