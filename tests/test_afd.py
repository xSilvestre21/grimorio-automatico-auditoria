"""Testes do Módulo 2 — Autômato Finito Determinístico das runas."""

import ast
import itertools
import unittest
from pathlib import Path

from gaa import afd as modulo_afd
from gaa.afd import AFD, AFD_RUNAS, TABELA_TRANSICAO, diagnosticar
from gaa.modelos import MotivoFraude


def referencia(w: str) -> bool:
    """Definição da linguagem L escrita diretamente, sem autômato."""
    return w.count("a") % 2 == 0 and w.endswith("bc")


# AFD-produto (paridade de 'a' × progresso do sufixo "bc") descrito no relatório,
# antes da minimização: q0..q2 = paridade par, q3..q5 = paridade ímpar.
PRODUTO_ESTADOS = ("q0", "q1", "q2", "q3", "q4", "q5")
PRODUTO_DELTA = {
    "q0": {"a": "q3", "b": "q1", "c": "q0"},
    "q1": {"a": "q3", "b": "q1", "c": "q2"},
    "q2": {"a": "q3", "b": "q1", "c": "q0"},
    "q3": {"a": "q0", "b": "q4", "c": "q3"},
    "q4": {"a": "q0", "b": "q4", "c": "q5"},
    "q5": {"a": "q0", "b": "q4", "c": "q3"},
}


def classes_de_equivalencia(afd: AFD) -> list[tuple[str, ...]]:
    """Agrupa os estados indistinguíveis (algoritmo de preenchimento de tabela)."""
    pares = list(itertools.combinations(afd.estados, 2))
    marcados = {(p, q) for p, q in pares if (p in afd.finais) != (q in afd.finais)}
    mudou = True
    while mudou:
        mudou = False
        for p, q in pares:
            if (p, q) in marcados:
                continue
            for s in afd.alfabeto:
                destinos = (afd.transicao(p, s), afd.transicao(q, s))
                destinos = tuple(sorted(destinos, key=afd.estados.index))
                if destinos in marcados:
                    marcados.add((p, q))
                    mudou = True
                    break
    classes: list[tuple[str, ...]] = []
    for q in afd.estados:
        for i, classe in enumerate(classes):
            par = tuple(sorted((classe[0], q), key=afd.estados.index))
            if par not in marcados:
                classes[i] = classe + (q,)
                break
        else:
            classes.append((q,))
    return classes


class TestDefinicaoFormal(unittest.TestCase):
    def test_cinco_tupla(self):
        self.assertEqual(AFD_RUNAS.estados, ("q0", "q1", "q2", "q3"))
        self.assertEqual(AFD_RUNAS.alfabeto, ("a", "b", "c"))
        self.assertEqual(AFD_RUNAS.inicial, "q0")
        self.assertEqual(AFD_RUNAS.finais, frozenset({"q2"}))

    def test_delta_e_total_e_deterministica(self):
        for q in AFD_RUNAS.estados:
            self.assertEqual(set(TABELA_TRANSICAO[q]), set(AFD_RUNAS.alfabeto))
            for s in AFD_RUNAS.alfabeto:
                self.assertIn(AFD_RUNAS.transicao(q, s), AFD_RUNAS.estados)

    def test_todos_os_estados_sao_alcancaveis(self):
        alcancados, fronteira = {"q0"}, ["q0"]
        while fronteira:
            q = fronteira.pop()
            for s in AFD_RUNAS.alfabeto:
                destino = AFD_RUNAS.transicao(q, s)
                if destino not in alcancados:
                    alcancados.add(destino)
                    fronteira.append(destino)
        self.assertEqual(alcancados, set(AFD_RUNAS.estados))

    def test_afd_e_minimo(self):
        """Algoritmo de preenchimento de tabela (Moore): todo par é distinguível."""
        classes = classes_de_equivalencia(AFD_RUNAS)
        self.assertEqual(len(classes), len(AFD_RUNAS.estados), f"existem estados equivalentes: {classes}")

    def test_minimizacao_do_automato_produto(self):
        """Confere a seção 4.2 do relatório: o produto de 6 estados minimiza para AFD_RUNAS."""
        produto = AFD(PRODUTO_ESTADOS, "abc", PRODUTO_DELTA, "q0", ["q2"])
        for n in range(0, 8):
            for simbolos in itertools.product("abc", repeat=n):
                w = "".join(simbolos)
                self.assertEqual(produto.aceita(w), referencia(w), w)
        classes = classes_de_equivalencia(produto)
        self.assertEqual(sorted(classes), [("q0",), ("q1",), ("q2",), ("q3", "q4", "q5")])
        # O quociente (cada classe vira um estado) é exatamente a tabela implementada.
        nome = {q: c[0] for c in classes for q in c}
        quociente = {nome[q]: {s: nome[produto.transicao(q, s)] for s in "abc"} for q in nome}
        self.assertEqual(quociente, TABELA_TRANSICAO)

    def test_construtor_rejeita_definicoes_invalidas(self):
        delta_ok = {"p": {"0": "p", "1": "p"}}
        casos = {
            "delta parcial": dict(delta={"p": {"0": "p"}}),
            "destino fora de Q": dict(delta={"p": {"0": "p", "1": "x"}}),
            "linha a mais": dict(delta={**delta_ok, "x": {"0": "p", "1": "p"}}),
            "inicial fora de Q": dict(delta=delta_ok, inicial="x"),
            "final fora de Q": dict(delta=delta_ok, finais=["x"]),
            "símbolo com 2 caracteres": dict(delta={"p": {"0": "p", "11": "p"}}, alfabeto=["0", "11"]),
        }
        for nome, kw in casos.items():
            with self.subTest(caso=nome):
                with self.assertRaises(ValueError):
                    AFD(estados=["p"], alfabeto=kw.get("alfabeto", ["0", "1"]), delta=kw["delta"],
                        inicial=kw.get("inicial", "p"), finais=kw.get("finais", ["p"]))

    def test_modulo_nao_usa_expressoes_regulares(self):
        arvore = ast.parse(Path(modulo_afd.__file__).read_text(encoding="utf-8"))
        importados = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                importados.update(alias.name.split(".")[0] for alias in no.names)
            elif isinstance(no, ast.ImportFrom) and no.module:
                importados.add(no.module.split(".")[0])
        self.assertFalse(importados & {"re", "regex", "fnmatch"}, importados)


class TestLinguagemReconhecida(unittest.TestCase):
    def test_exaustivo_ate_8_simbolos(self):
        """Todas as 9 841 cadeias de Σ* com até 8 símbolos."""
        total = 0
        for n in range(0, 9):
            for simbolos in itertools.product("abc", repeat=n):
                w = "".join(simbolos)
                total += 1
                self.assertEqual(AFD_RUNAS.aceita(w), referencia(w), w)
        self.assertEqual(total, 9841)

    def test_exemplos(self):
        for w in ["bc", "abacbc", "aabc", "cccaacbbbc", "bcbc", "aaaabc", "babcabcbc"]:
            with self.subTest(w=w):
                self.assertTrue(AFD_RUNAS.aceita(w))
        for w in ["", "a", "b", "c", "abc", "cb", "aacb", "bca", "aaabc", "bcb"]:
            with self.subTest(w=w):
                self.assertFalse(AFD_RUNAS.aceita(w))

    def test_cadeia_longa(self):
        w = "ccbaab" * 5000 + "bc"
        self.assertTrue(AFD_RUNAS.aceita(w))
        self.assertFalse(AFD_RUNAS.aceita("a" + w))


class TestProcessamento(unittest.TestCase):
    def test_rastro_passo_a_passo(self):
        resultado = AFD_RUNAS.processar("abacbc")
        self.assertTrue(resultado.aceita)
        caminho = [resultado.rastro[0].origem] + [p.destino for p in resultado.rastro]
        self.assertEqual(caminho, ["q0", "q3", "q3", "q0", "q0", "q1", "q2"])
        self.assertEqual([p.simbolo for p in resultado.rastro], list("abacbc"))

    def test_rastro_opcional(self):
        self.assertEqual(AFD_RUNAS.processar("abacbc", registrar_rastro=False).rastro, ())

    def test_simbolo_fora_do_alfabeto(self):
        for w, simbolo, posicao in [("abxbc", "x", 2), ("AABC", "A", 0), ("aa bc", " ", 2), ("bc\n", "\n", 2)]:
            with self.subTest(w=w):
                resultado = AFD_RUNAS.processar(w)
                self.assertFalse(resultado.aceita)
                self.assertEqual(resultado.simbolo_invalido, simbolo)
                self.assertEqual(resultado.posicao_invalida, posicao)
                self.assertEqual(diagnosticar(resultado), [MotivoFraude.RUNA_FORA_DO_ALFABETO])


class TestDiagnostico(unittest.TestCase):
    IMPAR, SEM_BC = MotivoFraude.RUNAS_A_IMPAR, MotivoFraude.RUNAS_SEM_SUFIXO_BC

    def test_motivo_por_estado_final(self):
        casos = {"": ("q0", [self.SEM_BC]), "b": ("q1", [self.SEM_BC]), "bc": ("q2", []),
                 "a": ("q3", [self.IMPAR]), "ab": ("q3", [self.IMPAR]), "abc": ("q3", [self.IMPAR])}
        for w, (estado, motivos) in casos.items():
            with self.subTest(w=w):
                resultado = AFD_RUNAS.processar(w)
                self.assertEqual(resultado.estado_final, estado)
                self.assertEqual(diagnosticar(resultado), motivos)

    def test_diagnostico_bate_com_a_definicao(self):
        """Paridade ímpar tem prioridade; com paridade par, o defeito é o sufixo."""
        for n in range(0, 7):
            for simbolos in itertools.product("abc", repeat=n):
                w = "".join(simbolos)
                if w.count("a") % 2:
                    esperado = [self.IMPAR]
                elif not w.endswith("bc"):
                    esperado = [self.SEM_BC]
                else:
                    esperado = []
                self.assertEqual(diagnosticar(AFD_RUNAS.processar(w, registrar_rastro=False)), esperado, w)


if __name__ == "__main__":
    unittest.main()
