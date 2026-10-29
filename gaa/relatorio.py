"""Relatório: ranking das guildas com mais tentativas de fraude.

O ranking é gerado em dois formatos:
    ranking_guildas.json  para outros sistemas da Ordem dos Arquivistas;
    ranking_guildas.txt   para ser afixado no quartel da guarda.

Complexidade: uma passada pelos n registros para contar (O(n)) e uma
ordenação das g guildas (O(g log g)); no total, O(n + g log g).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from gaa.modelos import MotivoFraude, ResultadoAuditoria, nome_guilda

NOME_JSON = "ranking_guildas.json"
NOME_TXT = "ranking_guildas.txt"


@dataclass
class LinhaRanking:
    """Uma guilda no ranking."""

    posicao: int
    sigla: str
    nome: str
    fraudes: int
    autenticos: int
    motivos: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.fraudes + self.autenticos

    @property
    def taxa_fraude(self) -> float:
        return self.fraudes / self.total if self.total else 0.0


def calcular_ranking(registros: Iterable[ResultadoAuditoria]) -> list[LinhaRanking]:
    """Conta autênticos e fraudes por guilda e ordena o ranking.

    Ordem: mais fraudes primeiro; em caso de empate, pela sigla (A-Z). Guildas
    empatadas dividem a mesma posição (ranking de competição: 1, 2, 2, 4).
    """
    fraudes: Counter[str] = Counter()
    autenticos: Counter[str] = Counter()
    motivos: dict[str, Counter[str]] = {}
    for registro in registros:
        if registro.autentico:
            autenticos[registro.guilda] += 1
        else:
            fraudes[registro.guilda] += 1
            contagem = motivos.setdefault(registro.guilda, Counter())
            contagem.update(m.value for m in registro.motivos)

    siglas = sorted(set(fraudes) | set(autenticos), key=lambda s: (-fraudes[s], s))
    ranking: list[LinhaRanking] = []
    for indice, sigla in enumerate(siglas, start=1):
        empatado = ranking and ranking[-1].fraudes == fraudes[sigla]
        ranking.append(LinhaRanking(
            posicao=ranking[-1].posicao if empatado else indice,
            sigla=sigla,
            nome=nome_guilda(sigla),
            fraudes=fraudes[sigla],
            autenticos=autenticos[sigla],
            motivos=dict(sorted(motivos.get(sigla, Counter()).items(), key=lambda kv: (-kv[1], kv[0]))),
        ))
    return ranking


def ranking_para_dict(ranking: list[LinhaRanking], gerado_em: str | None = None) -> dict:
    """Monta o documento JSON do ranking."""
    return {
        "titulo": "Ranking de guildas com mais tentativas de fraude",
        "emissor": "Ordem dos Arquivistas e Mestres do Saber - Reino de Aethelgard",
        "gerado_em": gerado_em or datetime.now().isoformat(timespec="seconds"),
        "total_pergaminhos": sum(l.total for l in ranking),
        "total_fraudes": sum(l.fraudes for l in ranking),
        "ranking": [
            {
                "posicao": l.posicao,
                "guilda": l.sigla,
                "nome": l.nome,
                "fraudes": l.fraudes,
                "autenticos": l.autenticos,
                "total": l.total,
                "taxa_fraude": round(l.taxa_fraude, 4),
                "motivos": l.motivos,
            }
            for l in ranking
        ],
    }


def ranking_para_texto(ranking: list[LinhaRanking], gerado_em: str | None = None) -> str:
    """Monta a versão em texto do ranking (tabela com moldura)."""
    gerado_em = gerado_em or datetime.now().isoformat(timespec="seconds")
    largura = 78
    linhas = [
        "╔" + "═" * (largura - 2) + "╗",
        "║" + "GRIMÓRIO AUTOMÁTICO DE AUDITORIA".center(largura - 2) + "║",
        "║" + "Ranking de guildas com mais tentativas de fraude".center(largura - 2) + "║",
        "║" + "Ordem dos Arquivistas e Mestres do Saber · Reino de Aethelgard".center(largura - 2) + "║",
        "╚" + "═" * (largura - 2) + "╝",
        f"Gerado em: {gerado_em}",
        f"Pergaminhos auditados: {sum(l.total for l in ranking)}   "
        f"Fraudes: {sum(l.fraudes for l in ranking)}",
        "",
    ]
    if not ranking:
        linhas.append("Nenhum pergaminho auditado até o momento.")
        return "\n".join(linhas) + "\n"

    cabecalho = f"{'Pos':>4}  {'Sigla':<5}  {'Guilda':<32}{'Fraudes':>8}{'Autênt.':>9}{'Total':>7}{'Taxa':>8}"
    linhas += [cabecalho, "─" * len(cabecalho)]
    for l in ranking:
        linhas.append(
            f"{str(l.posicao) + 'º':>4}  {l.sigla:<5}  {l.nome[:31]:<32}"
            f"{l.fraudes:>8}{l.autenticos:>9}{l.total:>7}{l.taxa_fraude:>8.0%}"
        )

    linhas += ["", "Detalhamento dos motivos de fraude por guilda", "─" * len(cabecalho)]
    for l in ranking:
        if not l.fraudes:
            continue
        linhas.append(f"{l.posicao}º {l.sigla} — {l.nome} ({l.fraudes} fraude(s))")
        for codigo, quantidade in l.motivos.items():
            linhas.append(f"    {quantidade:>3} × {MotivoFraude(codigo).descricao}")
    linhas.append("")
    linhas.append("Obs.: um pergaminho pode ter mais de um motivo de fraude.")
    return "\n".join(linhas) + "\n"


def gerar_relatorios(
    registros: Iterable[ResultadoAuditoria],
    pasta: str | Path,
    gerado_em: str | None = None,
) -> tuple[Path, Path]:
    """Grava ``ranking_guildas.json`` e ``ranking_guildas.txt`` em ``pasta``."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    gerado_em = gerado_em or datetime.now().isoformat(timespec="seconds")
    ranking = calcular_ranking(registros)

    caminho_json = pasta / NOME_JSON
    caminho_json.write_text(
        json.dumps(ranking_para_dict(ranking, gerado_em), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    caminho_txt = pasta / NOME_TXT
    caminho_txt.write_text(ranking_para_texto(ranking, gerado_em), encoding="utf-8")
    return caminho_json, caminho_txt
