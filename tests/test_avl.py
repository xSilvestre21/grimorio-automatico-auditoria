"""Testes do Módulo 3 — Árvore AVL."""

import math
import random
import unittest

from gaa.avl import ArvoreAVL


def limite_altura(n: int) -> float:
    """Altura máxima de uma AVL com n nós: 1,4405·log2(n+2) - 0,3277."""
    return 1.4405 * math.log2(n + 2) - 0.3277


class TestRotacoes(unittest.TestCase):
    CASOS = {"LL": [3, 2, 1], "RR": [1, 2, 3], "LR": [3, 1, 2], "RL": [1, 3, 2]}

    def test_quatro_casos_de_rotacao(self):
        for caso, chaves in self.CASOS.items():
            with self.subTest(caso=caso):
                arvore = ArvoreAVL()
                for k in chaves:
                    arvore.inserir(k, str(k))
                self.assertEqual(arvore.raiz.chave, 2)
                self.assertEqual(arvore.raiz.esquerda.chave, 1)
                self.assertEqual(arvore.raiz.direita.chave, 3)
                self.assertEqual(arvore.altura(), 2)
                self.assertEqual(dict(arvore.estatisticas_rotacoes), {caso: 1})
                arvore.verificar_invariantes()


class TestBalanceamento(unittest.TestCase):
    def test_insercao_em_ordem_crescente_nao_degenera(self):
        arvore = ArvoreAVL()
        for k in range(1, 1001):
            arvore.inserir(k, k)
        arvore.verificar_invariantes()
        self.assertGreaterEqual(arvore.altura(), math.ceil(math.log2(1001)))
        self.assertLessEqual(arvore.altura(), limite_altura(1000))  # uma BST comum teria altura 1000

    def test_insercao_em_ordem_decrescente(self):
        arvore = ArvoreAVL()
        for k in range(1000, 0, -1):
            arvore.inserir(k, k)
        arvore.verificar_invariantes()
        self.assertLessEqual(arvore.altura(), limite_altura(1000))

    def test_operacoes_aleatorias_contra_oraculo(self):
        """3 000 inserções/remoções aleatórias comparadas com um dicionário."""
        gerador = random.Random(2026)
        arvore, oraculo = ArvoreAVL(), {}
        for i in range(3000):
            chave = gerador.randint(0, 600)
            if gerador.random() < 0.6:
                self.assertEqual(arvore.inserir(chave, i), chave not in oraculo)
                oraculo[chave] = i
            else:
                self.assertEqual(arvore.remover(chave), chave in oraculo)
                oraculo.pop(chave, None)
            if i % 25 == 0:
                arvore.verificar_invariantes()
                self.assertLessEqual(arvore.altura(), limite_altura(len(oraculo)) + 1e-9)
        arvore.verificar_invariantes()
        self.assertEqual(list(arvore.em_ordem()), sorted(oraculo.items()))
        self.assertEqual(len(arvore), len(oraculo))


class TestBuscaEInsercao(unittest.TestCase):
    def setUp(self):
        self.arvore = ArvoreAVL()
        for chave in ["MAG-1000", "ALQ-2000", "FOR-3000", "NAV-4000", "ESC-5000", "ALQ-1000", "FOR-1000"]:
            self.arvore.inserir(chave, chave.lower())

    def test_busca_encontra_e_conta_comparacoes(self):
        resultado = self.arvore.buscar("FOR-3000")
        self.assertTrue(resultado.encontrado)
        self.assertEqual(resultado.valor, "for-3000")
        self.assertLessEqual(resultado.comparacoes, self.arvore.altura())

    def test_busca_inexistente(self):
        resultado = self.arvore.buscar("XYZ-0000")
        self.assertFalse(resultado.encontrado)
        self.assertIsNone(resultado.valor)
        self.assertLessEqual(resultado.comparacoes, self.arvore.altura())
        self.assertNotIn("XYZ-0000", self.arvore)
        self.assertEqual(self.arvore.obter("XYZ-0000", "padrão"), "padrão")

    def test_chave_repetida_troca_o_valor(self):
        self.assertFalse(self.arvore.inserir("FOR-3000", "novo"))
        self.assertEqual(len(self.arvore), 7)
        self.assertEqual(self.arvore.obter("FOR-3000"), "novo")

    def test_percurso_em_ordem(self):
        chaves = [k for k, _ in self.arvore]
        self.assertEqual(chaves, sorted(chaves))

    def test_arvore_vazia(self):
        vazia = ArvoreAVL()
        self.assertEqual(vazia.altura(), 0)
        self.assertEqual(len(vazia), 0)
        self.assertEqual(list(vazia), [])
        self.assertEqual(vazia.desenhar(), "(árvore vazia)")
        self.assertFalse(vazia.remover("x"))
        self.assertTrue(vazia.verificar_invariantes())

    def test_desenho_mostra_altura_e_fator(self):
        desenho = self.arvore.desenhar()
        self.assertIn(f"{self.arvore.raiz.chave} (h={self.arvore.altura()}, fb=", desenho)
        self.assertEqual(len(desenho.splitlines()), 7)


class TestRemocao(unittest.TestCase):
    def test_remocao_de_folha_um_filho_dois_filhos_e_raiz(self):
        arvore = ArvoreAVL()
        for k in [50, 30, 70, 20, 40, 60, 80, 10]:
            arvore.inserir(k, k)
        for chave in [10, 20, 30, arvore.raiz.chave]:  # folha, um filho, dois filhos, raiz
            with self.subTest(chave=chave):
                self.assertTrue(arvore.remover(chave))
                self.assertNotIn(chave, arvore)
                arvore.verificar_invariantes()
        self.assertFalse(arvore.remover(999))
        self.assertEqual(len(arvore), 4)


class TestBuscaPorPrefixo(unittest.TestCase):
    def test_prefixo_contra_filtro_ingenuo(self):
        gerador = random.Random(7)
        siglas = ["ALQ", "FOR", "MAG", "MER", "NAV", "ALA", "FO"]
        arvore = ArvoreAVL()
        for _ in range(400):
            chave = f"{gerador.choice(siglas)}-{gerador.randint(0, 99999):05d}"
            arvore.inserir(chave, None)
        todas = [k for k, _ in arvore]
        for prefixo in ["ALQ-", "FOR-", "FO", "MER-", "NAV-0", "ZZZ-", "", "A"]:
            with self.subTest(prefixo=prefixo):
                obtidas = [k for k, _ in arvore.buscar_por_prefixo(prefixo)]
                self.assertEqual(obtidas, [k for k in todas if k.startswith(prefixo)])


class TestVerificacaoDeInvariantes(unittest.TestCase):
    def test_detecta_altura_corrompida(self):
        arvore = ArvoreAVL()
        for k in [2, 1, 3]:
            arvore.inserir(k, k)
        arvore.raiz.altura = 5
        with self.assertRaises(ValueError):
            arvore.verificar_invariantes()

    def test_detecta_ordem_violada(self):
        arvore = ArvoreAVL()
        for k in [2, 1, 3]:
            arvore.inserir(k, k)
        arvore.raiz.esquerda.chave = 9
        with self.assertRaises(ValueError):
            arvore.verificar_invariantes()


if __name__ == "__main__":
    unittest.main()
