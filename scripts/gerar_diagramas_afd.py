"""Desenha os diagramas de estados do AFD para o relatório técnico.

Gera, na pasta docs/:
    afd_minimo.png   AFD mínimo M (4 estados), o que o sistema executa;
    afd_produto.png  AFD-produto (6 estados), antes da minimização (material de apoio).

As transições do AFD mínimo são lidas da própria tabela em gaa/afd.py, então
o desenho nunca fica diferente do código. Uso:

    python scripts/gerar_diagramas_afd.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from gaa.afd import AFD_RUNAS  # noqa: E402

RAIO = 0.42
COR_TRACO = "#1f2a44"
COR_A = "#b4432f"      # transições por 'a' (mudam a paridade)
COR_BC = "#1f2a44"     # transições por 'b' e 'c'
COR_FINAL = "#e8f1e4"
COR_ESTADO = "#ffffff"


def agrupar(delta: dict[str, dict[str, str]]) -> dict[tuple[str, str], str]:
    """Junta símbolos com a mesma origem e destino num só rótulo ("b, c")."""
    arestas: dict[tuple[str, str], list[str]] = {}
    for origem, linha in delta.items():
        for simbolo, destino in linha.items():
            arestas.setdefault((origem, destino), []).append(simbolo)
    return {par: ", ".join(sorted(simbolos)) for par, simbolos in arestas.items()}


def desenhar(
    delta: dict[str, dict[str, str]],
    posicoes: dict[str, tuple[float, float]],
    finais: set[str],
    inicial: str,
    curvas: dict[tuple[str, str], float],
    lacos: dict[str, float],
    titulo: str,
    legenda: str,
    caminho: Path,
    destaques: list[tuple[tuple[float, float, float, float], str, str]] = (),
    deslocar_rotulo: dict[tuple[str, str], tuple[float, float]] | None = None,
    posicao_rotulo: dict[tuple[str, str], float] | None = None,
) -> None:
    """Desenha um AFD. ``posicao_rotulo`` põe o rótulo da aresta na fração t da
    curva (0 = origem, 1 = destino); o padrão é o meio (t = 0,5)."""
    deslocar_rotulo = deslocar_rotulo or {}
    posicao_rotulo = posicao_rotulo or {}
    xs = [x for x, _ in posicoes.values()]
    ys = [y for _, y in posicoes.values()]
    fig, ax = plt.subplots(figsize=(1.55 * (max(xs) - min(xs) + 3.2), 1.55 * (max(ys) - min(ys) + 3.4)), dpi=200)
    ax.set_aspect("equal")
    ax.axis("off")

    for (x0, y0, largura, altura), texto, cor in destaques:
        ax.add_patch(FancyBboxPatch((x0, y0), largura, altura, boxstyle="round,pad=0.05,rounding_size=0.35",
                                    linewidth=1.2, linestyle="--", edgecolor=cor, facecolor=cor + "14", zorder=0))
        ax.text(x0 + largura - 0.2, y0 + altura - 0.12, texto, fontsize=9, color=cor, va="top", ha="right",
                style="italic", zorder=7,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.9))

    circulos = {}
    for q, (x, y) in posicoes.items():
        cor = COR_FINAL if q in finais else COR_ESTADO
        circulo = Circle((x, y), RAIO, facecolor=cor, edgecolor=COR_TRACO, linewidth=1.6, zorder=3)
        ax.add_patch(circulo)
        if q in finais:
            ax.add_patch(Circle((x, y), RAIO * 0.80, facecolor="none", edgecolor=COR_TRACO, linewidth=1.3, zorder=4))
        ax.text(x, y, q, ha="center", va="center", fontsize=14, fontweight="bold", color=COR_TRACO, zorder=5)
        circulos[q] = circulo

    # Seta de entrada no estado inicial.
    xi, yi = posicoes[inicial]
    ax.add_patch(FancyArrowPatch((xi - 1.35, yi), (xi - RAIO, yi), arrowstyle="-|>", mutation_scale=16,
                                 linewidth=1.6, color=COR_TRACO, zorder=2))
    ax.text(xi - 1.35, yi + 0.14, "início", fontsize=9, color=COR_TRACO, ha="left", va="bottom")

    for (origem, destino), rotulo in agrupar(delta).items():
        cor = COR_A if "a" in rotulo else COR_BC
        x1, y1 = posicoes[origem]
        if origem == destino:
            angulo = math.radians(lacos.get(origem, 90))
            abertura = math.radians(28)
            pa = (x1 + RAIO * math.cos(angulo + abertura), y1 + RAIO * math.sin(angulo + abertura))
            pb = (x1 + RAIO * math.cos(angulo - abertura), y1 + RAIO * math.sin(angulo - abertura))
            ax.add_patch(FancyArrowPatch(pa, pb, connectionstyle="arc3,rad=-2.6", arrowstyle="-|>",
                                         mutation_scale=14, linewidth=1.4, color=cor, zorder=2))
            lx = x1 + (RAIO + 0.62) * math.cos(angulo)
            ly = y1 + (RAIO + 0.62) * math.sin(angulo)
        else:
            x2, y2 = posicoes[destino]
            rad = curvas.get((origem, destino), 0.0)
            ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), patchA=circulos[origem], patchB=circulos[destino],
                                         connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=15,
                                         linewidth=1.4, color=cor, zorder=2))
            # Ponto B(t) da curva de Bézier quadrática usada por arc3, cujo ponto
            # de controle é o meio do segmento deslocado de rad·(dy, -dx).
            dx, dy = x2 - x1, y2 - y1
            cx, cy = (x1 + x2) / 2 + rad * dy, (y1 + y2) / 2 - rad * dx
            t = posicao_rotulo.get((origem, destino), 0.5)
            lx = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t ** 2 * x2
            ly = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t ** 2 * y2
        ox, oy = deslocar_rotulo.get((origem, destino), (0.0, 0.0))
        ax.text(lx + ox, ly + oy, rotulo, ha="center", va="center", fontsize=12, color=cor, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none"), zorder=6)

    ax.set_xlim(min(xs) - 1.6, max(xs) + 1.0)
    ax.set_ylim(min(ys) - 1.5, max(ys) + 1.9)
    ax.set_title(titulo, fontsize=14, color=COR_TRACO, pad=6)
    fig.text(0.5, 0.035, legenda, ha="center", fontsize=10, color="#444444")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"gerado: {caminho.relative_to(RAIZ)}")


def main() -> None:
    delta_minimo = {q: {s: AFD_RUNAS.transicao(q, s) for s in AFD_RUNAS.alfabeto} for q in AFD_RUNAS.estados}
    desenhar(
        delta=delta_minimo,
        posicoes={"q0": (0, 0), "q1": (3, 0), "q2": (6, 0), "q3": (3, -2.8)},
        finais=set(AFD_RUNAS.finais),
        inicial=AFD_RUNAS.inicial,
        curvas={("q1", "q2"): -0.25, ("q2", "q1"): -0.25, ("q2", "q0"): 0.45,
                ("q0", "q3"): 0.18, ("q3", "q0"): 0.18},
        lacos={"q0": 90, "q1": 90, "q3": 270},
        titulo="AFD mínimo M das runas de ativação",
        legenda="M = ({q0, q1, q2, q3}, {a, b, c}, δ, q0, {q2})     "
                "L(M) = { w ∈ {a, b, c}* | w tem número par de 'a' e termina em \"bc\" }\n"
                "vermelho: transições por 'a' (invertem a paridade)    azul-escuro: transições por 'b' e 'c'",
        caminho=RAIZ / "docs" / "afd_minimo.png",
        deslocar_rotulo={("q1", "q3"): (0.18, 0.35), ("q2", "q3"): (0.15, 0.25)},
    )

    delta_produto = {
        "q0": {"a": "q3", "b": "q1", "c": "q0"},
        "q1": {"a": "q3", "b": "q1", "c": "q2"},
        "q2": {"a": "q3", "b": "q1", "c": "q0"},
        "q3": {"a": "q0", "b": "q4", "c": "q3"},
        "q4": {"a": "q0", "b": "q4", "c": "q5"},
        "q5": {"a": "q0", "b": "q4", "c": "q3"},
    }
    desenhar(
        delta=delta_produto,
        posicoes={"q0": (0, 0), "q1": (3, 0), "q2": (6, 0), "q3": (0, -3.6), "q4": (3, -3.6), "q5": (6, -3.6)},
        finais={"q2"},
        inicial="q0",
        curvas={("q1", "q2"): -0.25, ("q2", "q1"): -0.25, ("q2", "q0"): 0.42,
                ("q4", "q5"): 0.25, ("q5", "q4"): 0.25, ("q5", "q3"): -0.42,
                ("q0", "q3"): 0.22, ("q3", "q0"): 0.22, ("q1", "q3"): 0.08, ("q4", "q0"): 0.08,
                ("q2", "q3"): 0.05, ("q5", "q0"): 0.05},
        lacos={"q0": 90, "q1": 90, "q3": 270, "q4": 270},
        titulo="AFD-produto (paridade de 'a' × sufixo \"bc\"), antes da minimização",
        legenda="Linha de cima: paridade par (q0, q1, q2).  Linha de baixo: paridade ímpar (q3, q4, q5).\n"
                "O algoritmo de preenchimento de tabela prova q3 ≡ q4 ≡ q5: fundidos, viram o estado q3 do AFD mínimo.",
        caminho=RAIZ / "docs" / "afd_produto.png",
        destaques=[((-0.75, -4.65, 7.5, 1.9), "estados equivalentes: q3 ≡ q4 ≡ q5", "#b4432f")],
        posicao_rotulo={("q1", "q3"): 0.22, ("q4", "q0"): 0.22, ("q2", "q3"): 0.2, ("q5", "q0"): 0.2},
    )


if __name__ == "__main__":
    main()
