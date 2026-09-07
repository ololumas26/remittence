# Decisões — fluxo de pagamento (Stripe)

Data: 2026-09-04
Contexto: feature/payment-processment

## Contexto

Design do fluxo de processamento de pagamento de uma remessa (MB WAY, cartão, referência
Multibanco), integrado com a Stripe. Documento captura as decisões tomadas em discussão antes
de se começar a implementar.

## Fluxo

1. O pedido chega a `POST /api/v1/payment`. A API identifica o método de pagamento escolhido
   (`mbway` / `card` / `multibanco`) e despacha para a classe/processador correspondente a esse
   método.
2. Cada processador comunica com a Stripe para iniciar o pagamento.
3. **O webhook da Stripe (`POST /api/v1/stripe/webhook`) é a única fonte de verdade sobre o
   resultado do pagamento** — mesmo para o cartão, cuja chamada à Stripe pode responder de forma
   síncrona. A resposta síncrona não decide o status final de nada; serve, no máximo, de
   feedback imediato de UI.
4. No momento em que o pagamento é iniciado (antes de se saber o resultado), criam-se **na
   mesma transação**:
   - `Payment`: `status=pending`, com o identificador da Stripe (ex: `payment_intent_id`),
     método, e o suficiente do pedido original (`recipient_id`, `amount`, moedas) para depois se
     conseguir construir a `Remittance` sem pedir essa informação outra vez.
   - `Remittance`: `status=IN_PROGRESS` (valor já existente por omissão no modelo), com
     `payment_id` a apontar já para o `Payment` criado no mesmo passo, snapshot do destinatário
     (nome/IBAN), taxa de câmbio e taxa de serviço calculadas nesse momento, `client_id`.
5. Quando o webhook resolve o pagamento (sucesso ou falha), atualiza-se o `status` do `Payment`
   e o `status` da `Remittance` correspondente (`SENT` / `REJECTED`) na mesma operação.
6. Depois de resolvido, monta-se e envia-se o email de confirmação/notificação ao cliente,
   conforme o resultado (reaproveita o padrão já existente em `RemittanceService` — falha a
   enviar o email nunca bloqueia nem reverte o resto).

## Decisões de modelação

- **Relação `Payment` ↔ `Remittance` é 1:1.** Uma remessa nasce já agarrada a um pagamento
  específico. Uma remessa rejeitada é um registo terminal — não há retry "dentro" da mesma
  remessa; tentar outra vez (ex: com outro método) é sempre uma remessa nova e um pagamento
  novo.
- **`Payment` fica "magro"**, com dados de processamento (id da Stripe, método, status, valor a
  cobrar, referências) — não deve conhecer IBAN, destinatário ou taxa de câmbio. Isso continua a
  ser responsabilidade da `Remittance`, que se mantém o agregado de domínio rico, apesar de ter
  agora `payment_id`.
- `Payment` tem o seu próprio enum de status (`pending` / `success` / `failed`), separado do
  `RemittanceStatus` (`IN_PROGRESS` / `SENT` / `REJECTED`).

## Riscos assumidos / pontos a garantir na implementação

- Os dois inserts (`payment` e `remittance`) têm de acontecer na mesma transação — falha de um
  sem o outro deixa o sistema inconsistente.
- Nem toda a falha chega pelo webhook: se a própria chamada síncrona à Stripe para iniciar o
  pagamento falhar (ex: cartão inválido logo na criação do `PaymentIntent`), `payment` e
  `remittance` têm de ser marcados como falhados diretamente nesse momento — não podem ficar
  presos em `pending` à espera de um webhook que nunca chega.
- O handler do webhook tem de verificar a assinatura (`Stripe-Signature`) antes de confiar no
  conteúdo, e tem de ser idempotente — a Stripe pode reenviar o mesmo evento mais do que uma
  vez.

## Em aberto (não decidido ainda)

- Nomes exatos dos campos/colunas e do enum de status do `Payment`.
- Como a referência Multibanco é obtida a sério via Stripe (hoje o frontend gera uma referência
  mock, só para UI).
- Se o `card_token`/dados do cartão devem ser tokenizados no cliente (Stripe.js/SDK) antes de
  chegarem ao backend, para nunca guardar/receber o número de cartão em bruto — consistente com
  já ter sido levantado antes, mas ainda não formalizado como decisão para esta integração
  específica.
