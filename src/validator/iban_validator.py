import re
import string

from src.constant.angola_bank_codes import ANGOLA_BANK_CODES

# Formato de um IBAN angolano: "AO" + 2 dígitos de controlo + 4 do banco +
# 4 da agência + 11 da conta + 2 de controlo nacional = 25 caracteres no
# total. Ou seja: "AO" seguido de 23 dígitos quaisquer. Os dígitos de
# controlo NÃO são fixos (dependem do banco/agência/conta) — quem confirma
# se estão matematicamente certos é o has_valid_checksum, não esta regex.
_AO_IBAN_FORMAT = re.compile(r'^AO\d{23}$')

# A = 10, B = 11, ..., Z = 35 — conversão usada no cálculo do checksum.
_LETTER_TO_DIGITS = {letter: str(value) for value, letter in enumerate(string.ascii_uppercase, start=10)}


def clean_iban(iban: str) -> str:
    """Remove espaços e converte para maiúsculas. Só normaliza, não valida
    nada — serve para aceitar o IBAN como o utilizador o copiou (com
    espaços, em minúsculas), antes de qualquer verificação a sério."""

    if not iban:
        return ""

    return iban.replace(" ", "").upper()


def has_valid_format(iban_clean : str) -> bool:
    """Verifica só a FORMA do IBAN (começa por 'AO', tem 25 caracteres, só
    dígitos a seguir ao país). Não confirma se os dígitos de controlo estão
    matematicamente corretos — só que o IBAN tem o formato certo para sequer
    valer a pena calcular o checksum."""

    return bool(_AO_IBAN_FORMAT.match(iban_clean))


def _rearranged_numeric_string(iban_clean : str) -> str:
    """Passo do algoritmo do IBAN: move os 4 primeiros caracteres (país +
    dígitos de controlo) para o fim, e substitui cada letra pelo número
    correspondente (A=10, ..., Z=35). Só deve ser chamada depois de
    has_valid_format confirmar que iban_clean só tem 'AO' + dígitos — caso
    contrário pode haver letras sem correspondência no mapa."""

    rearranged = iban_clean[4:] + iban_clean[:4]
    return "".join(_LETTER_TO_DIGITS.get(char, char) for char in rearranged)


def has_valid_checksum(iban_clean : str) -> bool:
    """Confirma os dígitos de controlo pelo algoritmo mod-97 do IBAN,
    calculado em blocos (o número tem demasiados dígitos para ser prático
    calcular de outra forma nalgumas linguagens — em Python até dava para
    calcular o mod 97 de uma vez, mas o cálculo em blocos é o standard usado
    por todas as implementações de IBAN, incluindo bancos).

    Só deve ser chamada depois de has_valid_format confirmar o formato —
    assume que iban_clean é 'AO' + 23 dígitos."""

    numeric = _rearranged_numeric_string(iban_clean)

    start, end = 0, 9
    remainder = 0
    chunk = numeric[start:end]

    while True:
        remainder = int(chunk) % 97
        start = end
        end = start + 9 - len(str(remainder))
        next_part = numeric[start:end]

        if not next_part:
            break

        chunk = str(remainder) + next_part

    return remainder == 1


def is_valid_iban(iban : str) -> bool:
    """Ponto de entrada principal: recebe o IBAN tal como o utilizador o
    escreveu (pode ter espaços, minúsculas) e diz se é um IBAN angolano
    válido — forma certa E dígitos de controlo matematicamente corretos.
    Nunca levanta exceção: qualquer input, por mais estranho, só dá True/False."""

    iban_clean = clean_iban(iban)

    if not has_valid_format(iban_clean):
        return False

    return has_valid_checksum(iban_clean)


def get_bank_code(iban_clean : str) -> str:
    """Extrai o código do banco (posições 5 a 8) de um IBAN já limpo. Não
    valida nada — chama has_valid_format antes de confiar no resultado."""

    return iban_clean[4:8]


def get_bank_name(iban : str) -> str | None:
    """Devolve o nome do banco a que este IBAN pertence, ou None se o IBAN
    não tiver o formato certo ou o código do banco não for conhecido."""

    iban_clean = clean_iban(iban)

    if not has_valid_format(iban_clean):
        return None

    return ANGOLA_BANK_CODES.get(get_bank_code(iban_clean))
