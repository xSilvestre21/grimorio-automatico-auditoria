"""Orquestração da auditoria: Regex -> AFD -> Árvore AVL.

Fluxo de um pergaminho:

    1. Estrutura   O leitor já apontou campos ausentes, repetidos ou
                   desconhecidos? -> CABECALHO_MALFORMADO.
    2. Regex       Os três campos do cabeçalho são validados (todas as falhas
                   são relatadas juntas).
    3. AFD         Só se o cabeçalho passou (é a "pré-validação" do enunciado),
                   as runas são processadas caractere por caractere.
    4. Histórico   Se o identificador já foi autenticado antes com conteúdo
                   diferente -> DECRETO_CLONADO.
    5. Registro    O veredito entra na árvore AVL (chave = identificador).

O mesmo conteúdo auditado duas vezes é reconhecido pelo digesto SHA-256 e
ignorado, de modo que rodar a auditoria de novo sobre as mesmas pastas não
duplica o histórico.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from gaa.afd import AFD_RUNAS, descrever_estado, diagnosticar
from gaa.avl import ArvoreAVL, ResultadoBusca
from gaa.leitor import ErroLeitura, coletar_arquivos, ler_arquivo, ler_texto
from gaa.modelos import MotivoFraude, Pergaminho, ResultadoAuditoria
from gaa.regex_validador import extrair_guilda, validar_cabecalho

VERSAO_HISTORICO = 1
PREFIXO_SEM_ID = "<sem-id-"


class ErroHistorico(Exception):
    """O arquivo de histórico existe, mas está corrompido ou ilegível."""


def calcular_digesto(pergaminho: Pergaminho) -> str:
    """SHA-256 do conteúdo do pergaminho, independente de espaços e comentários.

    Pergaminhos bem formados são resumidos pelos quatro campos; os malformados,
    pelo texto bruto (sem as linhas de comentário).
    """
    if not pergaminho.problemas:
        canonico = "\n".join([
            pergaminho.decreto or "", pergaminho.selo or "",
            pergaminho.assinatura or "", pergaminho.runas or "",
        ])
    else:
        canonico = "\n".join(
            l.strip() for l in pergaminho.texto_bruto.splitlines()
            if l.strip() and not l.strip().startswith("#")
        )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class ResumoLote:
    """O que aconteceu ao auditar um conjunto de arquivos."""

    resultados: list[ResultadoAuditoria] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)   # já auditados antes
    erros: list[str] = field(default_factory=list)       # arquivos ilegíveis

    @property
    def autenticos(self) -> int:
        return sum(1 for r in self.resultados if r.autentico)

    @property
    def fraudes(self) -> int:
        return sum(1 for r in self.resultados if not r.autentico)


class Auditor:
    """O Grimório em si: audita pergaminhos e mantém o histórico na AVL."""

    def __init__(self, relogio: Callable[[], str] | None = None) -> None:
        self.arvore: ArvoreAVL[str, list[ResultadoAuditoria]] = ArvoreAVL()
        self.historico: list[ResultadoAuditoria] = []  # ordem cronológica
        self._digestos: set[str] = set()
        self._sem_id = 0
        self._relogio = relogio or _agora

    # ------------------------------------------------------------------
    # Auditoria
    # ------------------------------------------------------------------
    def auditar(self, pergaminho: Pergaminho) -> ResultadoAuditoria | None:
        """Audita um pergaminho e registra o veredito.

        Devolve ``None`` se exatamente o mesmo conteúdo já estava no histórico.
        """
        digesto = calcular_digesto(pergaminho)
        if digesto in self._digestos:
            return None

        motivos: list[MotivoFraude] = []
        detalhes: list[str] = []
        estado_final: str | None = None

        if pergaminho.problemas:
            # 1) Estrutura quebrada: não há cabeçalho para pré-validar.
            motivos.append(MotivoFraude.CABECALHO_MALFORMADO)
            detalhes.extend(pergaminho.problemas)
        else:
            assert pergaminho.decreto is not None and pergaminho.selo is not None
            assert pergaminho.assinatura is not None and pergaminho.runas is not None
            # 2) Módulo Regex.
            falhas = validar_cabecalho(pergaminho.decreto, pergaminho.selo, pergaminho.assinatura)
            for falha in falhas:
                motivos.append(falha.motivo)
                detalhes.append(falha.detalhe)
            if not falhas:
                # 3) Módulo AFD (só depois da pré-validação por Regex).
                resultado_afd = AFD_RUNAS.processar(pergaminho.runas, registrar_rastro=False)
                estado_final = resultado_afd.estado_final
                for motivo in diagnosticar(resultado_afd):
                    motivos.append(motivo)
                    if motivo is MotivoFraude.RUNA_FORA_DO_ALFABETO:
                        detalhes.append(
                            f"símbolo {resultado_afd.simbolo_invalido!r} na posição "
                            f"{resultado_afd.posicao_invalida + 1} não pertence a Σ = {{a, b, c}}"
                        )
                    else:
                        detalhes.append(
                            f"o AFD terminou em {estado_final} ({descrever_estado(estado_final)}), "
                            f"que não pertence a F = {{q2}}"
                        )
                # 4) Histórico: o mesmo decreto já foi autenticado com outro conteúdo?
                anteriores = self.arvore.obter(pergaminho.decreto) or []
                original = next((r for r in anteriores if r.autentico), None)
                if original is not None:
                    motivos.append(MotivoFraude.DECRETO_CLONADO)
                    detalhes.append(
                        f"o decreto {pergaminho.decreto} já foi autenticado a partir de {original.origem}"
                    )

        resultado = ResultadoAuditoria(
            identificador=self._chave_para(pergaminho.decreto),
            guilda=extrair_guilda(pergaminho.decreto),
            autentico=not motivos,
            motivos=motivos,
            detalhes=detalhes,
            origem=pergaminho.origem,
            selo=pergaminho.selo,
            assinatura=pergaminho.assinatura,
            runas=pergaminho.runas,
            estado_final_afd=estado_final,
            digesto=digesto,
            auditado_em=self._relogio(),
        )
        self.registrar(resultado)
        return resultado

    def auditar_texto(self, texto: str, origem: str = "<texto>") -> ResumoLote:
        """Audita todos os pergaminhos contidos num texto."""
        resumo = ResumoLote()
        for pergaminho in ler_texto(texto, origem):
            self._auditar_no_resumo(pergaminho, resumo)
        return resumo

    def auditar_caminhos(self, caminhos: Iterable[str | Path]) -> ResumoLote:
        """Audita arquivos e pastas. Arquivos ilegíveis vão para ``erros``.

        Lança ``ErroLeitura`` se algum caminho não existir.
        """
        resumo = ResumoLote()
        for arquivo in coletar_arquivos(caminhos):
            try:
                pergaminhos = ler_arquivo(arquivo)
            except ErroLeitura as erro:
                resumo.erros.append(str(erro))
                continue
            for pergaminho in pergaminhos:
                self._auditar_no_resumo(pergaminho, resumo)
        return resumo

    def _auditar_no_resumo(self, pergaminho: Pergaminho, resumo: ResumoLote) -> None:
        resultado = self.auditar(pergaminho)
        if resultado is None:
            resumo.ignorados.append(pergaminho.origem)
        else:
            resumo.resultados.append(resultado)

    def _chave_para(self, decreto: str | None) -> str:
        """Chave na AVL: o identificador lido, ou um rótulo "<sem-id-N>"."""
        if decreto and decreto.strip():
            return decreto.strip()
        self._sem_id += 1
        return f"{PREFIXO_SEM_ID}{self._sem_id}>"

    # ------------------------------------------------------------------
    # Estrutura de dados
    # ------------------------------------------------------------------
    def registrar(self, resultado: ResultadoAuditoria) -> None:
        """Insere um veredito na AVL (e no histórico cronológico)."""
        tentativas = self.arvore.obter(resultado.identificador)
        if tentativas is None:
            self.arvore.inserir(resultado.identificador, [resultado])
        else:
            tentativas.append(resultado)  # a lista é o valor guardado no nó
        self.historico.append(resultado)
        self._digestos.add(resultado.digesto)
        if resultado.identificador.startswith(PREFIXO_SEM_ID):
            numero = resultado.identificador[len(PREFIXO_SEM_ID):-1]
            if numero.isdigit():
                self._sem_id = max(self._sem_id, int(numero))

    def consultar(self, identificador: str) -> ResultadoBusca[list[ResultadoAuditoria]]:
        """Busca o status de auditoria de um decreto pelo identificador. O(log n)."""
        return self.arvore.buscar(identificador.strip())

    # ------------------------------------------------------------------
    # Persistência do histórico
    # ------------------------------------------------------------------
    def salvar(self, caminho: str | Path) -> None:
        """Grava o histórico em JSON (escrita atômica: arquivo temporário + troca)."""
        caminho = Path(caminho)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        dados = {
            "sistema": "GAA - Grimório Automático de Auditoria",
            "versao": VERSAO_HISTORICO,
            "salvo_em": self._relogio(),
            "total": len(self.historico),
            "registros": [r.para_dict() for r in self.historico],
        }
        temporario = caminho.with_name(caminho.name + ".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporario, caminho)

    @classmethod
    def carregar(cls, caminho: str | Path, relogio: Callable[[], str] | None = None) -> "Auditor":
        """Reconstrói o auditor (e a AVL) a partir do histórico salvo.

        Se o arquivo não existir, começa com um histórico vazio.
        """
        auditor = cls(relogio)
        caminho = Path(caminho)
        if not caminho.exists():
            return auditor
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            if dados.get("versao") != VERSAO_HISTORICO:
                raise ErroHistorico(f"versão de histórico não suportada: {dados.get('versao')!r}")
            for registro in dados["registros"]:
                auditor.registrar(ResultadoAuditoria.de_dict(registro))
        except ErroHistorico:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError,
                KeyError, TypeError, ValueError, AttributeError) as erro:
            raise ErroHistorico(f"histórico {caminho} corrompido ou ilegível: {erro}") from erro
        return auditor
