"""Módulo 2 — Autômato Finito Determinístico (AFD) das runas de ativação.

Depois que o cabeçalho passa pela Regex, o corpo do decreto (a sequência de
comandos rúnicos) é lido caractere por caractere por um AFD explícito.

Definição formal: M = (Q, Σ, δ, q0, F), com

    Q  = {q0, q1, q2, q3}
    Σ  = {a, b, c}
    q0 = estado inicial
    F  = {q2}
    δ  = TABELA_TRANSICAO (logo abaixo)

M reconhece L = { w ∈ Σ* | w tem número par de 'a' e termina em "bc" }.

Como M foi obtido (resumo no relatório técnico, seção 4.2):
    1. L = L_par ∩ L_bc, cada uma reconhecida por um AFD pequeno
       (2 estados para a paridade, 3 para o sufixo "bc");
    2. a construção do produto gera um AFD de 2 × 3 = 6 estados;
    3. a minimização (algoritmo de preenchimento de tabela) mostra que os três
       estados de paridade ímpar são equivalentes: enquanto a paridade é
       ímpar, lembrar o sufixo é inútil, pois corrigir a paridade exige ler
       um 'a', e esse 'a' apaga qualquer sufixo. Resta o AFD mínimo:

    estado   paridade de 'a'   o que o estado lembra
    q0       par               nenhum sufixo útil
    q1       par               último símbolo foi 'b'
    q2       par               termina em "bc"   <- único estado de aceitação
    q3       ímpar             (sufixo irrelevante)

IMPORTANTE: este módulo não usa o módulo ``re`` (nem outra biblioteca de
expressões regulares). Toda a lógica de estados está na tabela δ, que é
convertida numa matriz de inteiros e percorrida símbolo a símbolo. Há um
teste automatizado que confere isso (tests/test_afd.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from gaa.modelos import MotivoFraude


@dataclass(frozen=True)
class Passo:
    """Uma transição executada: δ(origem, símbolo) = destino."""

    posicao: int
    origem: str
    simbolo: str
    destino: str


@dataclass(frozen=True)
class ResultadoAFD:
    """Resultado do processamento de uma cadeia pelo AFD.

    Se aparecer um símbolo fora de Σ, o processamento para ali:
    ``simbolo_invalido`` e ``posicao_invalida`` dizem qual foi e onde, e
    ``estado_final`` é o último estado alcançado antes dele.
    """

    aceita: bool
    estado_final: str
    rastro: tuple[Passo, ...]
    simbolo_invalido: str | None = None
    posicao_invalida: int | None = None


class AFD:
    """Autômato Finito Determinístico genérico, guiado por tabela de transição.

    A tabela ``delta`` é um mapeamento ``{estado: {símbolo: próximo_estado}}``.
    O construtor confere que δ é uma função TOTAL (há transição para todo par
    estado × símbolo) e que só aponta para estados de Q. O determinismo vem
    da própria estrutura: cada par (estado, símbolo) tem uma única entrada.

    Internamente a tabela vira uma matriz ``matriz[i][j]`` de índices inteiros,
    com acesso O(1) por transição. Processar uma cadeia de tamanho n custa
    portanto O(n) de tempo e O(1) de memória extra (fora o rastro opcional).
    """

    def __init__(
        self,
        estados: Iterable[str],
        alfabeto: Iterable[str],
        delta: Mapping[str, Mapping[str, str]],
        inicial: str,
        finais: Iterable[str],
    ) -> None:
        self.estados: tuple[str, ...] = tuple(estados)
        self.alfabeto: tuple[str, ...] = tuple(alfabeto)
        self.inicial = inicial
        self.finais: frozenset[str] = frozenset(finais)

        self._validar_definicao(delta)

        # Índices numéricos de estados e símbolos, para montar a matriz.
        self._indice_estado = {q: i for i, q in enumerate(self.estados)}
        self._indice_simbolo = {s: j for j, s in enumerate(self.alfabeto)}
        self._matriz: list[list[int]] = [
            [self._indice_estado[delta[q][s]] for s in self.alfabeto]
            for q in self.estados
        ]

    def _validar_definicao(self, delta: Mapping[str, Mapping[str, str]]) -> None:
        """Garante que (Q, Σ, δ, q0, F) é uma definição válida de AFD."""
        if not self.estados:
            raise ValueError("Q não pode ser vazio")
        if len(set(self.estados)) != len(self.estados):
            raise ValueError("Q contém estados repetidos")
        if len(set(self.alfabeto)) != len(self.alfabeto):
            raise ValueError("Σ contém símbolos repetidos")
        for simbolo in self.alfabeto:
            if len(simbolo) != 1:
                raise ValueError(f"o símbolo {simbolo!r} de Σ deve ter exatamente 1 caractere")
        if self.inicial not in self.estados:
            raise ValueError(f"o estado inicial {self.inicial!r} não pertence a Q")
        if not self.finais <= set(self.estados):
            raise ValueError("F deve ser subconjunto de Q")
        if set(delta) != set(self.estados):
            raise ValueError("δ deve ter exatamente uma linha para cada estado de Q")
        for q in self.estados:
            linha = delta[q]
            if set(linha) != set(self.alfabeto):
                raise ValueError(
                    f"δ não é total: a linha de {q!r} deve ter uma transição "
                    f"para cada símbolo de Σ (e nenhum símbolo a mais)"
                )
            for s, destino in linha.items():
                if destino not in self.estados:
                    raise ValueError(f"δ({q}, {s}) = {destino!r} não pertence a Q")

    def transicao(self, estado: str, simbolo: str) -> str:
        """Aplica δ(estado, símbolo) uma vez, consultando a matriz."""
        i = self._indice_estado[estado]
        j = self._indice_simbolo[simbolo]
        return self.estados[self._matriz[i][j]]

    def processar(self, cadeia: str, registrar_rastro: bool = True) -> ResultadoAFD:
        """Lê ``cadeia`` caractere por caractere e devolve o resultado.

        Calcula a função de transição estendida δ*(q0, w) e aceita sse
        δ*(q0, w) ∈ F.
        """
        atual = self._indice_estado[self.inicial]
        rastro: list[Passo] = []

        for posicao, simbolo in enumerate(cadeia):
            j = self._indice_simbolo.get(simbolo)
            if j is None:
                # Símbolo fora de Σ: δ não está definida, o pergaminho é rejeitado.
                return ResultadoAFD(
                    aceita=False,
                    estado_final=self.estados[atual],
                    rastro=tuple(rastro),
                    simbolo_invalido=simbolo,
                    posicao_invalida=posicao,
                )
            proximo = self._matriz[atual][j]
            if registrar_rastro:
                rastro.append(Passo(posicao, self.estados[atual], simbolo, self.estados[proximo]))
            atual = proximo

        estado_final = self.estados[atual]
        return ResultadoAFD(
            aceita=estado_final in self.finais,
            estado_final=estado_final,
            rastro=tuple(rastro),
        )

    def aceita(self, cadeia: str) -> bool:
        """Atalho: indica se a cadeia pertence à linguagem do autômato."""
        return self.processar(cadeia, registrar_rastro=False).aceita

    def tabela_formatada(self, marcar: Mapping[str, str] | None = None) -> str:
        """Desenha a tabela de transição em texto (→ inicial, * final)."""
        marcar = marcar or {}
        largura = max(len(q) for q in self.estados) + 3
        cabecalho = "δ".ljust(largura) + "".join(s.center(6) for s in self.alfabeto)
        linhas = [cabecalho, "-" * len(cabecalho)]
        for q in self.estados:
            prefixo = ("→" if q == self.inicial else " ") + ("*" if q in self.finais else " ")
            celulas = "".join(self.transicao(q, s).center(6) for s in self.alfabeto)
            sufixo = f"   {marcar[q]}" if q in marcar else ""
            linhas.append(f"{prefixo}{q}".ljust(largura) + celulas + sufixo)
        return "\n".join(linhas)


# --------------------------------------------------------------------------
# Instância do enunciado: runas de ativação do feitiço
# --------------------------------------------------------------------------
ESTADOS = ("q0", "q1", "q2", "q3")
ALFABETO = ("a", "b", "c")
ESTADO_INICIAL = "q0"
ESTADOS_FINAIS = frozenset({"q2"})

# δ: Q × Σ → Q
#   paridade par:   'a' -> q3 (vira ímpar); 'b' -> q1; 'c' completa "bc" só a partir de q1.
#   paridade ímpar: 'a' -> q0 (volta a par, sem sufixo); 'b' e 'c' não mudam nada.
TABELA_TRANSICAO: dict[str, dict[str, str]] = {
    "q0": {"a": "q3", "b": "q1", "c": "q0"},
    "q1": {"a": "q3", "b": "q1", "c": "q2"},
    "q2": {"a": "q3", "b": "q1", "c": "q0"},
    "q3": {"a": "q0", "b": "q3", "c": "q3"},
}

# O que cada estado "lembra" da cadeia lida até agora.
SIGNIFICADO_ESTADOS: dict[str, str] = {
    "q0": "'a' par, sem sufixo útil",
    "q1": "'a' par, último símbolo 'b'",
    "q2": "'a' par, termina em \"bc\"",
    "q3": "'a' ímpar",
}

# Motivo da rejeição conforme o estado em que a leitura terminou.
DIAGNOSTICO_POR_ESTADO: dict[str, tuple[MotivoFraude, ...]] = {
    "q0": (MotivoFraude.RUNAS_SEM_SUFIXO_BC,),
    "q1": (MotivoFraude.RUNAS_SEM_SUFIXO_BC,),
    "q2": (),
    "q3": (MotivoFraude.RUNAS_A_IMPAR,),
}

AFD_RUNAS = AFD(ESTADOS, ALFABETO, TABELA_TRANSICAO, ESTADO_INICIAL, ESTADOS_FINAIS)


def descrever_estado(estado: str) -> str:
    """Texto curto com o significado de um estado do AFD das runas."""
    return SIGNIFICADO_ESTADOS[estado]


def diagnosticar(resultado: ResultadoAFD) -> list[MotivoFraude]:
    """Traduz o resultado do AFD das runas no motivo da fraude.

    O estado onde a leitura termina explica a rejeição:
        q0, q1  -> a paridade está certa, mas falta o sufixo "bc";
        q3      -> número ímpar de 'a'.
    Em q3 o AFD mínimo não sabe (nem precisa saber) se a cadeia termina em
    "bc": qualquer conserto teria de ler mais um 'a' e depois "bc" de novo.
    """
    if resultado.simbolo_invalido is not None:
        return [MotivoFraude.RUNA_FORA_DO_ALFABETO]
    return list(DIAGNOSTICO_POR_ESTADO[resultado.estado_final])
