"""Módulo 3 — Árvore AVL para o histórico de auditoria.

A árvore AVL (Adelson-Velsky e Landis, 1962) é uma árvore binária de busca
autobalanceada: em todo nó, as alturas das subárvores esquerda e direita
diferem no máximo em 1 (fator de balanceamento ∈ {-1, 0, +1}). Isso limita a
altura a cerca de 1,44·log2(n+2), e por isso:

    operação              complexidade (pior caso)
    buscar                O(log n)
    inserir               O(log n)   (no máximo uma rotação simples ou dupla)
    remover               O(log n)   (até O(log n) rotações)
    percurso em ordem     O(n)
    buscar_por_prefixo    O(log n + k), k = quantidade de chaves encontradas
    memória               O(n)

No GAA, a chave é o identificador do decreto (ex.: "ALQ-10492") e o valor é
a lista de tentativas de auditoria daquele identificador. Como as chaves
ficam ordenadas, também dá para listar todos os decretos de uma guilda
(prefixo "ALQ-") sem varrer a árvore inteira.

Implementação própria: não usa dict, bisect nem bibliotecas de árvores.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Generic, Iterator, TypeVar

C = TypeVar("C")  # tipo da chave (precisa ser comparável com < e ==)
V = TypeVar("V")  # tipo do valor


class NoAVL(Generic[C, V]):
    """Nó da árvore: chave, valor, filhos e altura da subárvore."""

    __slots__ = ("chave", "valor", "esquerda", "direita", "altura")

    def __init__(self, chave: C, valor: V) -> None:
        self.chave = chave
        self.valor = valor
        self.esquerda: NoAVL[C, V] | None = None
        self.direita: NoAVL[C, V] | None = None
        self.altura = 1  # uma folha tem altura 1; a árvore vazia tem altura 0


@dataclass(frozen=True)
class ResultadoBusca(Generic[V]):
    """Resultado de ``buscar``: o valor e quantas comparações foram feitas."""

    encontrado: bool
    valor: V | None
    comparacoes: int


def _altura(no: NoAVL | None) -> int:
    return no.altura if no is not None else 0


def _fator(no: NoAVL | None) -> int:
    """Fator de balanceamento: altura(esquerda) - altura(direita)."""
    return _altura(no.esquerda) - _altura(no.direita) if no is not None else 0


def _atualizar_altura(no: NoAVL) -> None:
    no.altura = 1 + max(_altura(no.esquerda), _altura(no.direita))


class ArvoreAVL(Generic[C, V]):
    """Árvore AVL com chaves únicas.

    ``estatisticas_rotacoes`` conta quantas vezes cada caso de rebalanceamento
    ocorreu (LL, RR, LR, RL); os testes usam isso para provar que os quatro
    casos são exercitados.
    """

    def __init__(self) -> None:
        self._raiz: NoAVL[C, V] | None = None
        self._tamanho = 0
        self.estatisticas_rotacoes: Counter[str] = Counter()
        # Sinalizadores preenchidos pela recursão de inserir/remover.
        self._inseriu_novo = False
        self._removeu = False

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return self._tamanho

    def __contains__(self, chave: C) -> bool:
        return self.buscar(chave).encontrado

    def __iter__(self) -> Iterator[tuple[C, V]]:
        """Percorre os pares (chave, valor) em ordem crescente de chave."""
        return self.em_ordem()

    @property
    def raiz(self) -> NoAVL[C, V] | None:
        return self._raiz

    def altura(self) -> int:
        """Altura da árvore (0 se vazia, 1 se só tem a raiz)."""
        return _altura(self._raiz)

    def buscar(self, chave: C) -> ResultadoBusca[V]:
        """Procura ``chave`` descendo a árvore, de forma iterativa. O(log n)."""
        no = self._raiz
        comparacoes = 0
        while no is not None:
            comparacoes += 1
            if chave == no.chave:
                return ResultadoBusca(True, no.valor, comparacoes)
            no = no.esquerda if chave < no.chave else no.direita
        return ResultadoBusca(False, None, comparacoes)

    def obter(self, chave: C, padrao: V | None = None) -> V | None:
        """Devolve o valor associado a ``chave``, ou ``padrao`` se não existir."""
        resultado = self.buscar(chave)
        return resultado.valor if resultado.encontrado else padrao

    def em_ordem(self) -> Iterator[tuple[C, V]]:
        """Percurso em ordem (esquerda, raiz, direita), com pilha explícita."""
        pilha: list[NoAVL[C, V]] = []
        no = self._raiz
        while pilha or no is not None:
            while no is not None:
                pilha.append(no)
                no = no.esquerda
            no = pilha.pop()
            yield no.chave, no.valor
            no = no.direita

    def buscar_por_prefixo(self, prefixo: str) -> list[tuple[C, V]]:
        """Lista, em ordem, as chaves (strings) que começam com ``prefixo``.

        Em ordem lexicográfica, as chaves com o mesmo prefixo formam um bloco
        contíguo que começa em ``prefixo``. A busca só desce pelos ramos que
        podem conter esse bloco: O(log n + k).
        """
        encontrados: list[tuple[C, V]] = []

        def visitar(no: NoAVL[C, V] | None) -> None:
            if no is None:
                return
            chave: Any = no.chave
            # À esquerda só há chaves menores; vale descer se esta já é >= prefixo.
            if chave >= prefixo:
                visitar(no.esquerda)
            if chave.startswith(prefixo):
                encontrados.append((no.chave, no.valor))
            # À direita só há chaves maiores; vale descer enquanto não passamos do bloco.
            if chave < prefixo or chave.startswith(prefixo):
                visitar(no.direita)

        visitar(self._raiz)
        return encontrados

    # ------------------------------------------------------------------
    # Inserção
    # ------------------------------------------------------------------
    def inserir(self, chave: C, valor: V) -> bool:
        """Insere ``chave`` com ``valor``. Se a chave já existe, troca o valor.

        Devolve True se a chave era nova e False se só o valor foi trocado.
        """
        self._inseriu_novo = False
        self._raiz = self._inserir(self._raiz, chave, valor)
        if self._inseriu_novo:
            self._tamanho += 1
        return self._inseriu_novo

    def _inserir(self, no: NoAVL[C, V] | None, chave: C, valor: V) -> NoAVL[C, V]:
        # 1) Inserção comum de árvore binária de busca.
        if no is None:
            self._inseriu_novo = True
            return NoAVL(chave, valor)
        if chave == no.chave:
            no.valor = valor
            return no
        if chave < no.chave:
            no.esquerda = self._inserir(no.esquerda, chave, valor)
        else:
            no.direita = self._inserir(no.direita, chave, valor)
        # 2) Na volta da recursão, atualiza a altura e rebalanceia se preciso.
        _atualizar_altura(no)
        return self._balancear(no)

    # ------------------------------------------------------------------
    # Remoção
    # ------------------------------------------------------------------
    def remover(self, chave: C) -> bool:
        """Remove ``chave`` da árvore. Devolve True se ela existia."""
        self._removeu = False
        self._raiz = self._remover(self._raiz, chave)
        if self._removeu:
            self._tamanho -= 1
        return self._removeu

    def _remover(self, no: NoAVL[C, V] | None, chave: C) -> NoAVL[C, V] | None:
        if no is None:
            return None
        if chave < no.chave:
            no.esquerda = self._remover(no.esquerda, chave)
        elif no.chave < chave:
            no.direita = self._remover(no.direita, chave)
        else:
            self._removeu = True
            # Zero ou um filho: o filho (ou None) ocupa o lugar do nó.
            if no.esquerda is None:
                return no.direita
            if no.direita is None:
                return no.esquerda
            # Dois filhos: copia o sucessor em ordem (menor da direita) e o remove.
            sucessor = no.direita
            while sucessor.esquerda is not None:
                sucessor = sucessor.esquerda
            no.chave, no.valor = sucessor.chave, sucessor.valor
            no.direita = self._remover_minimo(no.direita)
        _atualizar_altura(no)
        return self._balancear(no)

    def _remover_minimo(self, no: NoAVL[C, V]) -> NoAVL[C, V] | None:
        if no.esquerda is None:
            return no.direita
        no.esquerda = self._remover_minimo(no.esquerda)
        _atualizar_altura(no)
        return self._balancear(no)

    # ------------------------------------------------------------------
    # Rotações e rebalanceamento
    # ------------------------------------------------------------------
    @staticmethod
    def _rotacao_direita(y: NoAVL[C, V]) -> NoAVL[C, V]:
        """Rotação simples à direita.

                y              x
               / \\            / \\
              x   C   ==>    A   y
             / \\                / \\
            A   B              B   C
        """
        x = y.esquerda
        assert x is not None
        y.esquerda = x.direita
        x.direita = y
        _atualizar_altura(y)
        _atualizar_altura(x)
        return x

    @staticmethod
    def _rotacao_esquerda(x: NoAVL[C, V]) -> NoAVL[C, V]:
        """Rotação simples à esquerda (espelho da rotação à direita)."""
        y = x.direita
        assert y is not None
        x.direita = y.esquerda
        y.esquerda = x
        _atualizar_altura(x)
        _atualizar_altura(y)
        return y

    def _balancear(self, no: NoAVL[C, V]) -> NoAVL[C, V]:
        """Restaura |fator| <= 1 no nó, aplicando um dos quatro casos."""
        fator = _fator(no)
        if fator > 1:  # pende para a esquerda
            if _fator(no.esquerda) >= 0:
                self.estatisticas_rotacoes["LL"] += 1
            else:
                self.estatisticas_rotacoes["LR"] += 1
                no.esquerda = self._rotacao_esquerda(no.esquerda)
            return self._rotacao_direita(no)
        if fator < -1:  # pende para a direita
            if _fator(no.direita) <= 0:
                self.estatisticas_rotacoes["RR"] += 1
            else:
                self.estatisticas_rotacoes["RL"] += 1
                no.direita = self._rotacao_direita(no.direita)
            return self._rotacao_esquerda(no)
        return no

    # ------------------------------------------------------------------
    # Diagnóstico
    # ------------------------------------------------------------------
    def verificar_invariantes(self) -> bool:
        """Confere as propriedades de árvore AVL; lança ValueError se alguma falhar.

        Verifica: (1) ordem de árvore binária de busca, (2) alturas guardadas
        corretas, (3) fator de balanceamento entre -1 e +1 em todo nó e
        (4) contador de tamanho igual ao número real de nós.
        """
        contagem = 0

        def checar(no: NoAVL[C, V] | None, minimo: Any, maximo: Any) -> int:
            nonlocal contagem
            if no is None:
                return 0
            contagem += 1
            if minimo is not None and not (minimo < no.chave):
                raise ValueError(f"ordem violada: {no.chave!r} deveria ser > {minimo!r}")
            if maximo is not None and not (no.chave < maximo):
                raise ValueError(f"ordem violada: {no.chave!r} deveria ser < {maximo!r}")
            h_esq = checar(no.esquerda, minimo, no.chave)
            h_dir = checar(no.direita, no.chave, maximo)
            if no.altura != 1 + max(h_esq, h_dir):
                raise ValueError(f"altura incorreta no nó {no.chave!r}")
            if abs(h_esq - h_dir) > 1:
                raise ValueError(f"nó {no.chave!r} desbalanceado (fator {h_esq - h_dir})")
            return no.altura

        checar(self._raiz, None, None)
        if contagem != self._tamanho:
            raise ValueError(f"tamanho registrado {self._tamanho} != {contagem} nós")
        return True

    def desenhar(self) -> str:
        """Desenha a árvore "deitada" (raiz à esquerda), com altura e fator.

        Cada nó aparece como ``chave (h=altura, fb=fator)``; a subárvore direita
        fica acima e a esquerda abaixo, como numa árvore girada 90°.
        """
        if self._raiz is None:
            return "(árvore vazia)"
        linhas: list[str] = []

        def desenhar_no(no: NoAVL[C, V] | None, prefixo: str, ramo: str) -> None:
            if no is None:
                return
            desenhar_no(no.direita, prefixo + ("    " if ramo in ("┌── ", "") else "│   "), "┌── ")
            linhas.append(f"{prefixo}{ramo}{no.chave} (h={no.altura}, fb={_fator(no):+d})")
            desenhar_no(no.esquerda, prefixo + ("    " if ramo in ("└── ", "") else "│   "), "└── ")

        desenhar_no(self._raiz, "", "")
        return "\n".join(linhas)
