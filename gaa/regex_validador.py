"""Módulo 1 — Reconhecimento do cabeçalho por Expressões Regulares.

Todo pergaminho autêntico traz um cabeçalho de segurança com três campos:

    Decreto:        identificador da guilda + número sequencial (ex.: ALQ-10492)
    Selo Temporal:  data DD/MM/AAAA da Terceira Era, anos 2000 a 2099
    Assinatura:     nome do mago emissor entre colchetes (ex.: [Mestre Alabaster])

Cada campo tem sua própria expressão regular, aplicada com ``fullmatch``.
``fullmatch`` exige que a cadeia INTEIRA case com o padrão, o que equivale a
ancorar a expressão com ``^...$``, mas sem a pegadinha de ``$`` aceitar uma
quebra de linha no final. Assim "ALQ-10492X" ou " ALQ-10492" são rejeitados.

As justificativas detalhadas de cada padrão estão no relatório técnico,
seção 3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gaa.modelos import GUILDA_NAO_IDENTIFICADA, MotivoFraude

# --------------------------------------------------------------------------
# Identificador de decreto
# --------------------------------------------------------------------------
# [A-Z] e [0-9] são escritos por extenso de propósito: em Python, \d casa
# com QUALQUER dígito Unicode (ex.: os algarismos arábicos-índicos ١٢٣٤),
# o que abriria uma brecha para os falsificadores.
PADRAO_IDENTIFICADOR = re.compile(
    r"""
    [A-Z]{3}      # sigla da guilda: exatamente três letras maiúsculas
    -             # hífen separador
    [0-9]{4,6}    # número sequencial: de 4 a 6 dígitos
    """,
    re.VERBOSE,
)

# --------------------------------------------------------------------------
# Selo Temporal Mágico
# --------------------------------------------------------------------------
# A expressão valida o calendário completo, e não apenas o formato: rejeita
# 31/04, 30/02 e 29/02 em anos não bissextos. Entre 2000 e 2099 todo ano
# divisível por 4 é bissexto (2000 também, pois é divisível por 400), e os
# dois últimos dígitos YY são múltiplos de 4 exatamente quando:
#   - a dezena é par e a unidade é 0, 4 ou 8   ([02468][048]), ou
#   - a dezena é ímpar e a unidade é 2 ou 6    ([13579][26]).
PADRAO_SELO = re.compile(
    r"""
    (?:
        (?:
            (?:0[1-9]|1[0-9]|2[0-8]) / (?:0[1-9]|1[0-2])   # dias 01-28: todos os meses
          | (?:29|30) / (?:0[13-9]|1[0-2])                 # dias 29 e 30: menos fevereiro
          | 31 / (?:0[13578]|1[02])                        # dia 31: só nos meses de 31 dias
        )
        / 20[0-9]{2}                                       # Terceira Era: 2000-2099
    )
    |
    29 / 02 / 20(?:[02468][048]|[13579][26])               # 29/02 só nos anos bissextos
    """,
    re.VERBOSE,
)

# --------------------------------------------------------------------------
# Assinatura do Mago Emissor
# --------------------------------------------------------------------------
# "Letras" = alfabeto latino com acentos (bloco Latin-1), o que cobre nomes
# como "Bastião" ou "Íris". A faixa À-ÿ é quebrada em três para excluir os
# sinais × (U+00D7) e ÷ (U+00F7). Não usamos [^\W\d_] porque, em Python,
# essa classe aceita símbolos numéricos como "²" e "½", e o enunciado proíbe
# números na assinatura.
_LETRA = "A-Za-zÀ-ÖØ-öø-ÿ"

PADRAO_ASSINATURA = re.compile(
    r"""
    \[                      # colchete de abertura
    (?=[^\]]*[""" + _LETRA + r"""])  # lookahead: ao menos uma letra (barra "[     ]")
    [""" + _LETRA + r"""\x20]{5,40}  # de 5 a 40 caracteres, cada um letra ou espaço
    \]                      # colchete de fechamento
    """,
    re.VERBOSE,
)

# --------------------------------------------------------------------------
# Estrutura das linhas do cabeçalho ("Campo: valor")
# --------------------------------------------------------------------------
PADRAO_LINHA_CAMPO = re.compile(
    r"""
    (?P<campo>[""" + _LETRA + r"""][""" + _LETRA + r"""\x20]*?)  # nome do campo
    [\x20\t]*:[\x20\t]*     # dois-pontos, com espaços opcionais em volta
    (?P<valor>.*?)          # valor (pode ser vazio)
    [\x20\t]*               # espaços finais descartados
    """,
    re.VERBOSE,
)


def validar_identificador(texto: str) -> bool:
    """Indica se ``texto`` é um identificador de decreto válido (ex.: ALQ-10492)."""
    return PADRAO_IDENTIFICADOR.fullmatch(texto) is not None


def validar_selo(texto: str) -> bool:
    """Indica se ``texto`` é uma data DD/MM/AAAA real entre 2000 e 2099."""
    return PADRAO_SELO.fullmatch(texto) is not None


def validar_assinatura(texto: str) -> bool:
    """Indica se ``texto`` é uma assinatura [Nome do Mago] válida."""
    return PADRAO_ASSINATURA.fullmatch(texto) is not None


def extrair_guilda(identificador: str | None) -> str:
    """Devolve a sigla da guilda de um identificador válido.

    Se o identificador for inválido, não há como confiar na sigla, e a
    fraude é atribuída à "guilda não identificada".
    """
    if identificador and validar_identificador(identificador):
        return identificador[:3]
    return GUILDA_NAO_IDENTIFICADA


@dataclass(frozen=True)
class FalhaCabecalho:
    """Um campo do cabeçalho que não casou com sua expressão regular."""

    motivo: MotivoFraude
    detalhe: str


def validar_cabecalho(decreto: str, selo: str, assinatura: str) -> list[FalhaCabecalho]:
    """Valida os três campos do cabeçalho e devolve TODAS as falhas encontradas.

    Os campos são verificados de forma independente, para que o guarda saiba
    de uma vez tudo o que está errado no pergaminho. Lista vazia = cabeçalho
    autêntico.
    """
    falhas: list[FalhaCabecalho] = []
    if not validar_identificador(decreto):
        falhas.append(FalhaCabecalho(
            MotivoFraude.ID_INVALIDO,
            f"identificador {decreto!r} não segue o padrão AAA-NNNN (ex.: ALQ-10492)",
        ))
    if not validar_selo(selo):
        falhas.append(FalhaCabecalho(
            MotivoFraude.SELO_INVALIDO,
            f"selo {selo!r} não é uma data DD/MM/AAAA válida entre 2000 e 2099",
        ))
    if not validar_assinatura(assinatura):
        falhas.append(FalhaCabecalho(
            MotivoFraude.ASSINATURA_INVALIDA,
            f"assinatura {assinatura!r} não é [letras e espaços] com 5 a 40 caracteres",
        ))
    return falhas
