"""
inmet_cleaner.py

Trata os arquivos de dados meteorológicos exportados do portal do INMET
(https://bdmep.inmet.gov.br), no formato de estações automáticas mensais.

O arquivo bruto do INMET tem uma estrutura particular que impede sua leitura
direta como CSV convencional:
    - As primeiras 9 linhas são metadados da estação (nome, código, coordenadas,
      período de cobertura), não dados tabulares.
    - O separador de coluna é ";" e o separador decimal é "," (padrão brasileiro),
      o que quebra a leitura padrão do pandas (que espera "." como decimal).
    - Valores ausentes aparecem como a string literal "null", não como célula
      vazia.

Este script isola os metadados, localiza a linha de cabeçalho real, converte
os separadores decimais e trata os valores nulos — devolvendo um DataFrame
pronto para análise.

Uso:
    python inmet_cleaner.py caminho/para/arquivo_bruto.csv caminho/de/saida.xlsx
"""

import sys
from pathlib import Path

import pandas as pd


# Nomes de coluna esperados nos arquivos de estação automática do INMET.
# relativa em vez de pressão atmosférica e vento).
COLUNAS_PADRAO = [
    "data",
    "hora(UTC)",
    "precipitacao_horaria_mm",
    "radiacao_global_(kj/m2)",
    "temperatura_bulbo_seco_(C)",
    "temp_ponto_de_orvalho_(C)",
    "umidade_relativa_(%)",
]


def ler_metadados(linhas_arquivo: list[str]) -> dict:
    """Extrai os metadados da estação (linhas 0 a 8) como um dicionário."""
    metadados = {}
    for linha in linhas_arquivo[:9]:
        chave, _, valor = linha.strip().rstrip(",").partition(":")
        metadados[chave.strip()] = valor.strip()
    return metadados


def localizar_linha_cabecalho(linhas_arquivo: list[str]) -> int:
    """Retorna o índice da linha que contém o cabeçalho real dos dados
    (a linha que começa com "Data Medicao")."""
    for i, linha in enumerate(linhas_arquivo):
        if linha.startswith("Data Medicao"):
            return i
    raise ValueError('Cabeçalho "Data Medicao" não encontrado no arquivo.')


def carregar_dados_brutos(caminho_csv: str) -> pd.DataFrame:
    """Lê o CSV bruto do INMET e devolve um DataFrame com tipos corretos.

    Trata os três problemas estruturais do formato original:
    1. Separador de coluna ";" em vez de ",".
    2. Separador decimal "," em vez de ".".
    3. Valores ausentes representados pela string "null".
    """
    with open(caminho_csv, encoding="utf-8") as f:
        linhas = f.readlines()

    linha_cabecalho = localizar_linha_cabecalho(linhas)
    linhas_dados = linhas[linha_cabecalho + 1 :]

    registros = []
    for linha in linhas_dados:
        campos = linha.strip("\n").split(";")[: len(COLUNAS_PADRAO)]
        if len(campos) < len(COLUNAS_PADRAO):
            continue  # linha incompleta ou vazia no final do arquivo
        registros.append(campos)

    df = pd.DataFrame(registros, columns=COLUNAS_PADRAO)

    # Data
    df["data_medicao"] = pd.to_datetime(df["data_medicao"])

    # Colunas numéricas: "null" -> NaN, vírgula -> ponto, string -> float
    colunas_numericas = COLUNAS_PADRAO[1:]
    for coluna in colunas_numericas:
        df[coluna] = (
            df[coluna]
            .replace("null", pd.NA)
            .astype(str)
            .str.replace(",", ".", regex=False)
        )
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    return df


def resumo_cobertura(df: pd.DataFrame) -> pd.DataFrame:
    """Retorna a contagem de valores ausentes por coluna — útil para decidir
    rapidamente se uma estação tem cobertura suficiente para uso na análise."""
    return df.isna().sum().to_frame(name="meses_sem_dado")


def salvar(df: pd.DataFrame, caminho_saida: str) -> None:
    """Salva o DataFrame tratado em .xlsx ou .csv, conforme a extensão informada."""
    caminho_saida = Path(caminho_saida)
    if caminho_saida.suffix == ".xlsx":
        df.to_excel(caminho_saida, index=False)
    else:
        df.to_csv(caminho_saida, index=False)


def main() -> None:
    if len(sys.argv) != 3:
        print("Uso: python inmet_cleaner.py <arquivo_bruto.csv> <arquivo_saida.xlsx>")
        sys.exit(1)

    caminho_entrada, caminho_saida = sys.argv[1], sys.argv[2]

    with open(caminho_entrada, encoding="utf-8") as f:
        metadados = ler_metadados(f.readlines())
    print("Estação:", metadados.get("Nome"), "-", metadados.get("Codigo Estacao"))

    df = carregar_dados_brutos(caminho_entrada)
    print(f"{len(df)} meses carregados.")
    print("\nCobertura por variável (meses sem dado):")
    print(resumo_cobertura(df))

    salvar(df, caminho_saida)
    print(f"\nArquivo tratado salvo em: {caminho_saida}")


if __name__ == "__main__":
    main()
