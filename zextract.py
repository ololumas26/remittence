import os
import re

from pypdf import PdfReader, PdfWriter


MESES = {
    "jan": "01",
    "fev": "02",
    "mar": "03",
    "abr": "04",
    "mai": "05",
    "jun": "06",
    "jul": "07",
    "ago": "08",
    "set": "09",
    "out": "10",
    "nov": "11",
    "dez": "12",
}


def limpar_nome(nome):
    nome = nome.strip()

    # Remove caracteres inválidos em nomes de ficheiros
    nome = re.sub(r'[<>:"/\\|?*]', "", nome)

    # Substitui espaços por _
    nome = re.sub(r"\s+", "_", nome)

    return nome


def encontrar_nome(texto):

    # Procuramos:
    #
    # NOME: CÓDIGO CONTRIBUINTE N.I.S.SOCIAL
    # MAIQUEL MENDES 100 331340186 12179690521

    padrao = (
        r"NOME:\s*(?:CÓDIGO\s+CONTRIBUINTE\s+N\.I\.S\.SOCIAL\s*)?"
        r"\n?\s*([A-ZÀ-Ú][A-ZÀ-Ú\s]+?)"
        r"\s+\d+\s+\d+\s+\d+"
    )

    resultado = re.search(
        padrao,
        texto,
        re.IGNORECASE
    )

    if resultado:
        return limpar_nome(resultado.group(1))

    return None


def encontrar_mes(texto):

    padrao = (
        r"\b("
        r"jan|fev|mar|abr|mai|jun|"
        r"jul|ago|set|out|nov|dez"
        r")[-/](\d{4})\b"
    )

    resultado = re.search(
        padrao,
        texto,
        re.IGNORECASE
    )

    if not resultado:
        return None

    mes = resultado.group(1).lower()
    ano = resultado.group(2)

    return f"{ano}-{MESES[mes]}"


def separar_pdf(caminho_pdf):

    reader = PdfReader(caminho_pdf)

    pasta_saida = "separados"

    os.makedirs(pasta_saida, exist_ok=True)

    for numero, pagina in enumerate(reader.pages, start=1):

        texto = pagina.extract_text() or ""

        nome = encontrar_nome(texto)
        mes = encontrar_mes(texto)

        print(f"\nPágina {numero}")
        print(f"Funcionário: {nome}")
        print(f"Vencimento:  {mes}")

        if not nome or not mes:
            print("⚠️ Não foi possível identificar os dados.")
            continue

        nome_ficheiro = f"{nome}_{mes}.pdf"

        caminho_saida = os.path.join(
            pasta_saida,
            nome_ficheiro
        )

        writer = PdfWriter()
        writer.add_page(pagina)

        with open(caminho_saida, "wb") as arquivo:
            writer.write(arquivo)

        print(f"✓ Criado: {nome_ficheiro}")


if __name__ == "__main__":

    caminho_pdf = "762 - duplicados.pdf"

    separar_pdf(caminho_pdf)