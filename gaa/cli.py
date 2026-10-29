"""Interface de linha de comando do Grimório Automático de Auditoria.

Uso (a partir da pasta do projeto):

    python -m gaa auditar pergaminhos/          audita arquivos ou pastas
    python -m gaa consultar ALQ-10492           status de um decreto (busca na AVL)
    python -m gaa listar [--guilda ALQ]         lista os decretos em ordem
    python -m gaa ranking                       regera e mostra o ranking de fraudes
    python -m gaa afd abacbc                    simula o AFD passo a passo
    python -m gaa afd --tabela                  mostra a tabela de transição
    python -m gaa arvore                        desenha a árvore AVL
    python -m gaa interativo                    menu para os guardas da cidade

Opções globais: --historico ARQ (padrão saida/historico.json),
--saida PASTA (padrão saida) e --sem-cor.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from typing import Callable, Sequence, TextIO

from gaa import __version__
from gaa.afd import AFD_RUNAS, SIGNIFICADO_ESTADOS, descrever_estado, diagnosticar
from gaa.auditor import Auditor, ErroHistorico, ResumoLote
from gaa.leitor import ErroLeitura
from gaa.modelos import ResultadoAuditoria, nome_guilda
from gaa.relatorio import calcular_ranking, gerar_relatorios, ranking_para_texto

HISTORICO_PADRAO = Path("saida") / "historico.json"
SAIDA_PADRAO = Path("saida")

# Códigos de saída do programa.
OK = 0
NAO_ENCONTRADO = 1
ERRO = 2


# --------------------------------------------------------------------------
# Cores ANSI (só em terminal de verdade, e desligáveis)
# --------------------------------------------------------------------------
def _habilitar_ansi_windows() -> bool:
    """Liga o processamento de sequências ANSI no console do Windows."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        saida = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        modo = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(saida, ctypes.byref(modo)):
            return False
        return bool(kernel32.SetConsoleMode(saida, modo.value | 0x0004))  # VT processing
    except (AttributeError, OSError):
        return False


class Estilo:
    """Aplica cores ANSI quando permitido; senão devolve o texto puro."""

    CODIGOS = {"verde": "32", "vermelho": "31", "amarelo": "33", "ciano": "36", "negrito": "1", "fraco": "2"}

    def __init__(self, ativo: bool) -> None:
        self.ativo = ativo

    def __call__(self, texto: str, *estilos: str) -> str:
        if not self.ativo or not estilos:
            return texto
        codigos = ";".join(self.CODIGOS[e] for e in estilos)
        return f"\033[{codigos}m{texto}\033[0m"


def _cores_permitidas(sem_cor: bool, saida: TextIO) -> bool:
    if sem_cor or os.environ.get("NO_COLOR"):
        return False
    return hasattr(saida, "isatty") and saida.isatty() and _habilitar_ansi_windows()


# --------------------------------------------------------------------------
# Formatação
# --------------------------------------------------------------------------
def _banner(largura: int = 62) -> str:
    """Moldura de abertura do modo interativo."""
    linhas = ["GRIMÓRIO AUTOMÁTICO DE AUDITORIA", "Reino de Aethelgard",
              "Ordem dos Arquivistas e Mestres do Saber"]
    miolo = [f"║{t.center(largura - 2)}║" for t in linhas]
    return "\n".join(["╔" + "═" * (largura - 2) + "╗", *miolo, "╚" + "═" * (largura - 2) + "╝"])


def _selo_status(resultado: ResultadoAuditoria, estilo: Estilo) -> str:
    if resultado.autentico:
        return estilo("[AUTÊNTICO]", "verde", "negrito")
    return estilo("[FRAUDE]   ", "vermelho", "negrito")


def _linha_resultado(resultado: ResultadoAuditoria, estilo: Estilo) -> list[str]:
    linhas = [f"{_selo_status(resultado, estilo)} {resultado.identificador:<14} "
              f"{estilo(resultado.origem, 'fraco')}"]
    for motivo, detalhe in zip(resultado.motivos, resultado.detalhes):
        linhas.append(f"              ↳ {motivo.descricao}")
        linhas.append(estilo(f"                {detalhe}", "fraco"))
    # Problemas de estrutura podem ter mais de um detalhe para um só motivo.
    for detalhe in resultado.detalhes[len(resultado.motivos):]:
        linhas.append(estilo(f"                {detalhe}", "fraco"))
    return linhas


def _ficha(resultado: ResultadoAuditoria, estilo: Estilo, numero: int) -> list[str]:
    """Ficha completa de uma tentativa de auditoria (usada em ``consultar``)."""
    status = "AUTÊNTICO" if resultado.autentico else "FRAUDE"
    cor = "verde" if resultado.autentico else "vermelho"
    linhas = [
        estilo(f"  Tentativa {numero}: {status}", cor, "negrito"),
        f"    Guilda ........ {resultado.guilda} — {nome_guilda(resultado.guilda)}",
        f"    Selo .......... {resultado.selo}",
        f"    Assinatura .... {resultado.assinatura}",
        f"    Runas ......... {resultado.runas}",
        f"    Estado do AFD . {resultado.estado_final_afd or '(AFD não executado)'}",
        f"    Origem ........ {resultado.origem}",
        f"    Auditado em ... {resultado.auditado_em}",
    ]
    if resultado.motivos:
        linhas.append("    Motivos:")
        for motivo in resultado.motivos:
            linhas.append(f"      - {motivo.descricao}")
        for detalhe in resultado.detalhes:
            linhas.append(estilo(f"        · {detalhe}", "fraco"))
    return linhas


# --------------------------------------------------------------------------
# Comandos
# --------------------------------------------------------------------------
class Contexto:
    """Dados compartilhados pelos comandos de uma execução."""

    def __init__(self, args: argparse.Namespace, saida: TextIO) -> None:
        self.historico = Path(args.historico)
        self.pasta_saida = Path(args.saida)
        self.saida = saida
        self.estilo = Estilo(_cores_permitidas(args.sem_cor, saida))
        self._auditor: Auditor | None = None

    def escrever(self, texto: str = "") -> None:
        print(texto, file=self.saida)

    @property
    def auditor(self) -> Auditor:
        """Carrega o histórico (e reconstrói a AVL) só quando for preciso."""
        if self._auditor is None:
            self._auditor = Auditor.carregar(self.historico)
        return self._auditor

    def salvar(self) -> None:
        self.auditor.salvar(self.historico)


def comando_auditar(ctx: Contexto, caminhos: Sequence[str], limpar: bool = False) -> int:
    if limpar:
        ctx._auditor = Auditor()
    resumo: ResumoLote = ctx.auditor.auditar_caminhos(caminhos)
    e = ctx.estilo

    for resultado in resumo.resultados:
        for linha in _linha_resultado(resultado, e):
            ctx.escrever(linha)
    for origem in resumo.ignorados:
        ctx.escrever(f"{e('[IGNORADO] ', 'amarelo')} {'':<14} {e(origem, 'fraco')} (já auditado, conteúdo idêntico)")
    for erro in resumo.erros:
        ctx.escrever(e(f"[ERRO]      {erro}", "vermelho"))

    ctx.salvar()
    caminho_json, caminho_txt = gerar_relatorios(ctx.auditor.historico, ctx.pasta_saida)

    ctx.escrever()
    ctx.escrever(e("Resumo da auditoria", "negrito"))
    ctx.escrever(f"  Pergaminhos auditados agora: {len(resumo.resultados)}")
    ctx.escrever(f"  Autênticos: {e(str(resumo.autenticos), 'verde')}   "
                 f"Fraudes: {e(str(resumo.fraudes), 'vermelho')}   "
                 f"Ignorados (repetidos): {len(resumo.ignorados)}   "
                 f"Arquivos com erro: {len(resumo.erros)}")
    ctx.escrever(f"  Histórico total: {len(ctx.auditor.historico)} registro(s) em "
                 f"{len(ctx.auditor.arvore)} decreto(s); altura da AVL = {ctx.auditor.arvore.altura()}")
    ctx.escrever(f"  Histórico salvo em {ctx.historico}")
    ctx.escrever(f"  Ranking gerado em {caminho_json} e {caminho_txt}")
    return ERRO if resumo.erros else OK


def comando_consultar(ctx: Contexto, identificador: str) -> int:
    auditor = ctx.auditor
    busca = auditor.consultar(identificador)
    n = len(auditor.arvore)
    # Altura máxima de uma AVL com n nós: h < 1,4405·log2(n+2) - 0,3277.
    limite = 1.4405 * math.log2(n + 2) - 0.3277 if n else 0
    estatistica = (f"{busca.comparacoes} comparação(ões) numa AVL com {n} decreto(s), "
                   f"altura {auditor.arvore.altura()} (limite teórico ≈ {limite:.1f})")
    e = ctx.estilo
    if not busca.encontrado:
        ctx.escrever(e(f"Decreto {identificador!r} não consta nos arquivos da Ordem.", "amarelo"))
        ctx.escrever(e(f"  Busca: {estatistica}", "fraco"))
        return NAO_ENCONTRADO

    tentativas = busca.valor or []
    autenticado = any(r.autentico for r in tentativas)
    status = e("AUTÊNTICO", "verde", "negrito") if autenticado else e("FRAUDULENTO", "vermelho", "negrito")
    fraudes = sum(1 for r in tentativas if not r.autentico)
    ctx.escrever(f"Decreto {e(identificador, 'negrito')}: {status}"
                 f" — {len(tentativas)} tentativa(s) registrada(s), {fraudes} fraudulenta(s)")
    ctx.escrever(e(f"  Busca: {estatistica}", "fraco"))
    for numero, resultado in enumerate(tentativas, start=1):
        ctx.escrever()
        for linha in _ficha(resultado, e, numero):
            ctx.escrever(linha)
    return OK


def comando_listar(ctx: Contexto, guilda: str | None, status: str) -> int:
    arvore = ctx.auditor.arvore
    if guilda:
        prefixo = guilda.strip().upper() + "-"
        sigla = prefixo[:-1]
        # A busca por prefixo na AVL é O(log n + k). O filtro descarta chaves
        # inválidas que só "parecem" da guilda (ex.: "ALQ-١٢٣٤"), que o ranking
        # atribui à guilda não identificada.
        pares = [(chave, tentativas) for chave, tentativas in arvore.buscar_por_prefixo(prefixo)
                 if any(r.guilda == sigla for r in tentativas)]
        titulo = f"Decretos da guilda {guilda.upper()} — {nome_guilda(guilda.upper())}"
    else:
        pares = list(arvore.em_ordem())
        titulo = "Todos os decretos registrados (em ordem de identificador)"
    e = ctx.estilo
    ctx.escrever(e(titulo, "negrito"))
    exibidos = 0
    for chave, tentativas in pares:
        autenticado = any(r.autentico for r in tentativas)
        if (status == "autenticos" and not autenticado) or (status == "fraudes" and autenticado):
            continue
        exibidos += 1
        marca = e("✔ autêntico", "verde") if autenticado else e("✘ fraude   ", "vermelho")
        motivos = sorted({m.value for r in tentativas for m in r.motivos})
        ctx.escrever(f"  {chave:<16} {marca}  {len(tentativas)} tentativa(s)"
                     + (e(f"  [{', '.join(motivos)}]", "fraco") if motivos else ""))
    if not exibidos:
        ctx.escrever("  (nenhum decreto encontrado)")
    return OK if exibidos else NAO_ENCONTRADO


def comando_ranking(ctx: Contexto) -> int:
    historico = ctx.auditor.historico
    caminho_json, caminho_txt = gerar_relatorios(historico, ctx.pasta_saida)
    ctx.escrever(ranking_para_texto(calcular_ranking(historico)).rstrip())
    ctx.escrever()
    ctx.escrever(ctx.estilo(f"Arquivos gravados: {caminho_json} e {caminho_txt}", "fraco"))
    return OK


def comando_afd(ctx: Contexto, runas: str | None, mostrar_tabela: bool) -> int:
    e = ctx.estilo
    significados = {q: descrever_estado(q) for q in SIGNIFICADO_ESTADOS}
    if mostrar_tabela or runas is None:
        ctx.escrever(e("AFD das runas: M = (Q, Σ, δ, q0, F)", "negrito"))
        ctx.escrever(f"  Q = {{{', '.join(AFD_RUNAS.estados)}}}   Σ = {{{', '.join(AFD_RUNAS.alfabeto)}}}   "
                     f"q0 = {AFD_RUNAS.inicial}   F = {{{', '.join(sorted(AFD_RUNAS.finais))}}}")
        ctx.escrever("  L(M) = { w ∈ Σ* | w tem número par de 'a' e termina em \"bc\" }")
        ctx.escrever()
        ctx.escrever(AFD_RUNAS.tabela_formatada(significados))
        if runas is None:
            return OK
        ctx.escrever()

    resultado = AFD_RUNAS.processar(runas)
    ctx.escrever(e(f"Processando a cadeia {runas!r} ({len(runas)} símbolo(s))", "negrito"))
    ctx.escrever(f"  início em {AFD_RUNAS.inicial} ({significados[AFD_RUNAS.inicial]})")
    for passo in resultado.rastro:
        ctx.escrever(f"  {passo.posicao + 1:>3}. δ({passo.origem}, {passo.simbolo}) = {passo.destino}"
                     f"   {e(significados[passo.destino], 'fraco')}")
    if resultado.simbolo_invalido is not None:
        ctx.escrever(e(f"  {resultado.posicao_invalida + 1:>3}. símbolo {resultado.simbolo_invalido!r} "
                       f"fora de Σ: δ indefinida, processamento interrompido", "vermelho"))
    if resultado.aceita:
        ctx.escrever(e(f"Cadeia ACEITA: parou em {resultado.estado_final} ∈ F", "verde", "negrito"))
        return OK
    ctx.escrever(e(f"Cadeia REJEITADA: parou em {resultado.estado_final} ∉ F", "vermelho", "negrito"))
    for motivo in diagnosticar(resultado):
        ctx.escrever(f"  ↳ {motivo.descricao}")
    return NAO_ENCONTRADO


def comando_arvore(ctx: Contexto) -> int:
    arvore = ctx.auditor.arvore
    ctx.escrever(ctx.estilo("Árvore AVL do histórico (direita em cima, esquerda embaixo)", "negrito"))
    ctx.escrever(arvore.desenhar())
    ctx.escrever()
    rotacoes = ", ".join(f"{caso}={arvore.estatisticas_rotacoes[caso]}" for caso in ("LL", "RR", "LR", "RL"))
    ctx.escrever(f"Nós: {len(arvore)}   Altura: {arvore.altura()}   Rotações na reconstrução: {rotacoes}")
    arvore.verificar_invariantes()
    ctx.escrever(ctx.estilo("Invariantes AVL verificadas: ordem, alturas e |fb| ≤ 1 em todos os nós.", "verde"))
    return OK


def comando_interativo(ctx: Contexto, entrada: Callable[[str], str] = input) -> int:
    """Menu de texto para os guardas consultarem o grimório."""
    e = ctx.estilo
    ctx.escrever(e(_banner(), "ciano"))
    opcoes = {
        "1": "Auditar arquivo ou pasta de pergaminhos",
        "2": "Consultar decreto pelo identificador",
        "3": "Listar decretos (todos ou de uma guilda)",
        "4": "Ver ranking de fraudes por guilda",
        "5": "Simular o AFD com uma sequência de runas",
        "6": "Desenhar a árvore AVL",
        "0": "Sair",
    }
    while True:
        ctx.escrever()
        for chave, descricao in opcoes.items():
            ctx.escrever(f"  [{chave}] {descricao}")
        try:
            escolha = entrada("Escolha uma opção: ").strip()
            if escolha == "0":
                ctx.escrever("Que os selos reais permaneçam íntegros. Até logo, guarda!")
                return OK
            if escolha == "1":
                caminho = entrada("Caminho do arquivo ou pasta: ").strip().strip('"')
                comando_auditar(ctx, [caminho])
            elif escolha == "2":
                comando_consultar(ctx, entrada("Identificador (ex.: ALQ-10492): "))
            elif escolha == "3":
                guilda = entrada("Sigla da guilda (Enter para todas): ").strip()
                comando_listar(ctx, guilda or None, "todos")
            elif escolha == "4":
                comando_ranking(ctx)
            elif escolha == "5":
                comando_afd(ctx, entrada("Runas: ").strip(), mostrar_tabela=False)
            elif escolha == "6":
                comando_arvore(ctx)
            else:
                ctx.escrever(e("Opção desconhecida.", "amarelo"))
        except (EOFError, KeyboardInterrupt):
            ctx.escrever()
            ctx.escrever("Sessão encerrada.")
            return OK
        except (ErroLeitura, ErroHistorico, OSError) as erro:
            ctx.escrever(e(f"Erro: {erro}", "vermelho"))


# --------------------------------------------------------------------------
# Ponto de entrada
# --------------------------------------------------------------------------
def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m gaa",
        description="GAA — Grimório Automático de Auditoria do Reino de Aethelgard.",
    )
    parser.add_argument("--version", action="version", version=f"GAA {__version__}")
    parser.add_argument("--historico", default=str(HISTORICO_PADRAO),
                        help=f"arquivo JSON do histórico (padrão: {HISTORICO_PADRAO})")
    parser.add_argument("--saida", default=str(SAIDA_PADRAO),
                        help=f"pasta dos relatórios de ranking (padrão: {SAIDA_PADRAO})")
    parser.add_argument("--sem-cor", action="store_true", help="desliga as cores no terminal")
    sub = parser.add_subparsers(dest="comando", metavar="COMANDO")

    p = sub.add_parser("auditar", help="audita arquivos ou pastas de pergaminhos")
    p.add_argument("caminhos", nargs="+", help="arquivos .txt ou pastas (lidas recursivamente)")
    p.add_argument("--limpar", action="store_true", help="descarta o histórico anterior antes de auditar")

    p = sub.add_parser("consultar", help="mostra o status de auditoria de um decreto")
    p.add_argument("identificador", help="identificador do decreto (ex.: ALQ-10492)")

    p = sub.add_parser("listar", help="lista os decretos registrados, em ordem")
    p.add_argument("--guilda", help="sigla da guilda (ex.: ALQ)")
    p.add_argument("--status", choices=("todos", "autenticos", "fraudes"), default="todos")

    sub.add_parser("ranking", help="regera e mostra o ranking de fraudes por guilda")

    p = sub.add_parser("afd", help="simula o AFD das runas passo a passo")
    p.add_argument("runas", nargs="?", help="sequência de runas (ex.: abacbc)")
    p.add_argument("--tabela", action="store_true", help="mostra também a tabela de transição")

    sub.add_parser("arvore", help="desenha a árvore AVL do histórico")
    sub.add_parser("interativo", help="abre o menu interativo")
    return parser


def _usar_utf8(fluxo: TextIO) -> None:
    """No Windows, garante que acentos e símbolos (Σ, δ, ✔) saiam corretamente."""
    reconfigurar = getattr(fluxo, "reconfigure", None)
    if reconfigurar is not None:
        try:
            reconfigurar(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main(argv: Sequence[str] | None = None, saida: TextIO | None = None) -> int:
    if saida is None:
        _usar_utf8(sys.stdout)
        _usar_utf8(sys.stderr)
        saida = sys.stdout
    parser = criar_parser()
    args = parser.parse_args(argv)
    if args.comando is None:
        args.comando = "interativo"
    ctx = Contexto(args, saida)

    try:
        if args.comando == "auditar":
            return comando_auditar(ctx, args.caminhos, args.limpar)
        if args.comando == "consultar":
            return comando_consultar(ctx, args.identificador)
        if args.comando == "listar":
            return comando_listar(ctx, args.guilda, args.status)
        if args.comando == "ranking":
            return comando_ranking(ctx)
        if args.comando == "afd":
            return comando_afd(ctx, args.runas, args.tabela)
        if args.comando == "arvore":
            return comando_arvore(ctx)
        return comando_interativo(ctx)
    except (ErroLeitura, ErroHistorico) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return ERRO
    except OSError as erro:
        print(f"Erro de arquivo: {erro}", file=sys.stderr)
        return ERRO
