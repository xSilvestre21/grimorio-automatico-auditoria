"""Leitura dos arquivos de pergaminho.

Formato de um pergaminho (arquivo de texto UTF-8):

    # linhas iniciadas por '#' antes do '---' são comentários e são ignoradas
    Decreto: ALQ-10492
    Selo Temporal: 15/03/2047
    Assinatura: [Mestre Alabaster]
    ---
    abacbc

O cabeçalho vem antes da linha ``---``; o corpo (as runas) vem depois dela.
Um mesmo arquivo pode trazer vários pergaminhos separados por uma linha
contendo apenas ``===``.

Este módulo só separa e interpreta a estrutura. Quem decide se cada campo é
válido são os módulos Regex (regex_validador) e AFD (afd).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

from gaa.modelos import Pergaminho
from gaa.regex_validador import PADRAO_LINHA_CAMPO

SEPARADOR_CORPO = "---"
PADRAO_SEPARADOR_PERGAMINHOS = re.compile(r"^[ \t]*={3,}[ \t]*$", re.MULTILINE)

# Nomes aceitos para cada campo do cabeçalho (comparação sem distinguir maiúsculas).
NOMES_CAMPOS: dict[str, str] = {
    "decreto": "decreto",
    "selo temporal": "selo",
    "selo": "selo",
    "assinatura": "assinatura",
}
CAMPOS_OBRIGATORIOS = ("decreto", "selo", "assinatura")
ROTULOS_CAMPOS = {"decreto": "Decreto", "selo": "Selo Temporal", "assinatura": "Assinatura"}


class ErroLeitura(Exception):
    """Falha ao abrir ou decodificar um arquivo de pergaminho."""


def interpretar_pergaminho(bloco: str, origem: str) -> Pergaminho:
    """Converte o texto de UM pergaminho num objeto ``Pergaminho``.

    O texto é normalizado para Unicode NFC, para que "ã" escrito como "a" +
    til combinante fique igual ao caractere único "ã" esperado pela Regex.
    """
    texto = unicodedata.normalize("NFC", bloco).strip("﻿\r\n")
    pergaminho = Pergaminho(origem=origem, texto_bruto=texto)
    linhas = texto.splitlines()

    try:
        indice_separador = next(i for i, linha in enumerate(linhas) if linha.strip() == SEPARADOR_CORPO)
    except StopIteration:
        indice_separador = None
        pergaminho.problemas.append("separador '---' entre cabeçalho e runas não encontrado")

    linhas_cabecalho = linhas if indice_separador is None else linhas[:indice_separador]
    if indice_separador is not None:
        pergaminho.runas = "\n".join(linhas[indice_separador + 1:]).strip()

    vistos: set[str] = set()
    for numero, linha in enumerate(linhas_cabecalho, start=1):
        conteudo = linha.strip()
        if not conteudo or conteudo.startswith("#"):
            continue
        casamento = PADRAO_LINHA_CAMPO.fullmatch(conteudo)
        if casamento is None:
            pergaminho.problemas.append(f"linha {numero} não está no formato 'Campo: valor': {conteudo!r}")
            continue
        nome = " ".join(casamento["campo"].split()).casefold()
        campo = NOMES_CAMPOS.get(nome)
        if campo is None:
            pergaminho.problemas.append(f"campo desconhecido {casamento['campo']!r} na linha {numero}")
            continue
        if campo in vistos:
            pergaminho.problemas.append(f"campo {ROTULOS_CAMPOS[campo]!r} repetido na linha {numero}")
            continue
        vistos.add(campo)
        setattr(pergaminho, campo, casamento["valor"])

    for campo in CAMPOS_OBRIGATORIOS:
        if campo not in vistos:
            pergaminho.problemas.append(f"campo obrigatório {ROTULOS_CAMPOS[campo]!r} ausente")

    return pergaminho


def ler_texto(texto: str, origem: str) -> list[Pergaminho]:
    """Separa um texto em pergaminhos (pela linha ``===``) e interpreta cada um.

    Se houver mais de um pergaminho, a origem ganha o sufixo ``#n`` (1, 2, ...).
    Blocos vazios ou só com comentários são ignorados.
    """
    blocos = [
        b for b in PADRAO_SEPARADOR_PERGAMINHOS.split(texto)
        if any(l.strip() and not l.strip().startswith("#") for l in b.splitlines())
    ]
    if len(blocos) == 1:
        return [interpretar_pergaminho(blocos[0], origem)]
    return [interpretar_pergaminho(b, f"{origem}#{i}") for i, b in enumerate(blocos, start=1)]


def ler_arquivo(caminho: str | Path, rotulo: str | None = None) -> list[Pergaminho]:
    """Lê um arquivo de pergaminhos. ``rotulo`` substitui o caminho na origem."""
    caminho = Path(caminho)
    try:
        texto = caminho.read_text(encoding="utf-8-sig")
    except FileNotFoundError as erro:
        raise ErroLeitura(f"arquivo não encontrado: {caminho}") from erro
    except UnicodeDecodeError as erro:
        raise ErroLeitura(f"o arquivo {caminho} não está em UTF-8") from erro
    except OSError as erro:
        raise ErroLeitura(f"não foi possível ler {caminho}: {erro.strerror}") from erro
    return ler_texto(texto, rotulo if rotulo is not None else caminho.as_posix())


def coletar_arquivos(caminhos: Iterable[str | Path]) -> list[Path]:
    """Expande pastas em arquivos ``*.txt`` (recursivamente, em ordem alfabética).

    Arquivos passados diretamente são aceitos com qualquer extensão.
    """
    arquivos: list[Path] = []
    for item in caminhos:
        caminho = Path(item)
        if caminho.is_dir():
            arquivos.extend(sorted(p for p in caminho.rglob("*.txt") if p.is_file()))
        elif caminho.is_file():
            arquivos.append(caminho)
        else:
            raise ErroLeitura(f"caminho não encontrado: {caminho}")
    return arquivos
