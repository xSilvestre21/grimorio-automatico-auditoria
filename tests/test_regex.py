"""Testes do Módulo 1 — Expressões Regulares do cabeçalho."""

import calendar
import unittest

from gaa import regex_validador as rv
from gaa.modelos import GUILDA_NAO_IDENTIFICADA, MotivoFraude


class TestIdentificador(unittest.TestCase):
    VALIDOS = ["ALQ-10492", "FOR-2231", "MAG-777777", "MER-0042", "ZZZ-000000", "ABC-1234"]
    INVALIDOS = {
        "AL-1234": "sigla com 2 letras",
        "ALQQ-1234": "sigla com 4 letras",
        "alq-1234": "sigla minúscula",
        "Alq-1234": "sigla com minúsculas",
        "ÁLQ-1234": "letra acentuada na sigla",
        "ALQ-123": "3 dígitos",
        "ALQ-1234567": "7 dígitos",
        "ALQ1234": "sem hífen",
        "ALQ_1234": "sublinhado no lugar do hífen",
        "ALQ--1234": "hífen duplo",
        "ALQ-12a4": "letra no número",
        " ALQ-1234": "espaço antes",
        "ALQ-1234 ": "espaço depois",
        "ALQ-1234\n": "quebra de linha no final",
        "ALQ-١٢٣٤": "dígitos arábicos-índicos (\\d aceitaria)",
        "ALQ-": "sem número",
        "": "vazio",
    }

    def test_identificadores_validos(self):
        for texto in self.VALIDOS:
            with self.subTest(texto=texto):
                self.assertTrue(rv.validar_identificador(texto))

    def test_identificadores_invalidos(self):
        for texto, motivo in self.INVALIDOS.items():
            with self.subTest(texto=texto, motivo=motivo):
                self.assertFalse(rv.validar_identificador(texto))

    def test_quantidade_de_digitos_de_1_a_9(self):
        for n in range(1, 10):
            with self.subTest(digitos=n):
                self.assertEqual(rv.validar_identificador("MAG-" + "7" * n), 4 <= n <= 6)

    def test_extrair_guilda(self):
        self.assertEqual(rv.extrair_guilda("ALQ-10492"), "ALQ")
        self.assertEqual(rv.extrair_guilda("alq-10492"), GUILDA_NAO_IDENTIFICADA)
        self.assertEqual(rv.extrair_guilda(None), GUILDA_NAO_IDENTIFICADA)


class TestSeloTemporal(unittest.TestCase):
    def test_exaustivo_contra_o_calendario(self):
        """Compara a Regex com o calendário real em ~56 mil combinações DD/MM/AAAA."""
        divergencias = []
        for ano in range(1990, 2111):
            for mes in range(0, 14):
                for dia in range(0, 33):
                    texto = f"{dia:02d}/{mes:02d}/{ano:04d}"
                    existe = 1 <= mes <= 12 and 1 <= dia <= calendar.monthrange(ano, mes)[1]
                    esperado = 2000 <= ano <= 2099 and existe
                    if rv.validar_selo(texto) != esperado:
                        divergencias.append(texto)
        self.assertEqual(divergencias, [])

    def test_anos_bissextos(self):
        for texto in ["29/02/2000", "29/02/2004", "29/02/2024", "29/02/2048", "29/02/2096"]:
            with self.subTest(texto=texto):
                self.assertTrue(rv.validar_selo(texto))
        for texto in ["29/02/2001", "29/02/2023", "29/02/2050", "29/02/2099", "29/02/2100"]:
            with self.subTest(texto=texto):
                self.assertFalse(rv.validar_selo(texto))

    def test_formatos_invalidos(self):
        for texto in ["5/3/2047", "05/3/2047", "2047-03-15", "15-03-2047", "15.03.2047",
                      "15/03/47", "15/03/02047", "15/03/2047 ", "15/03/2047\n",
                      "١٥/٠٣/٢٠٤٧", "aa/bb/cccc", ""]:
            with self.subTest(texto=texto):
                self.assertFalse(rv.validar_selo(texto))


class TestAssinatura(unittest.TestCase):
    def test_assinaturas_validas(self):
        for texto in ["[Mestre Alabaster]", "[Merla]", "[Lorde Mercador Bastião]",
                      "[Escriba Íris Valença]", "[Sir Galahad de Aethelgard Cavaleiro Real]",
                      "[  Mago  ]"]:
            with self.subTest(texto=texto):
                self.assertTrue(rv.validar_assinatura(texto))

    def test_assinaturas_invalidas(self):
        for texto in ["[Zed]", "[Abcd]", "[Mago Merlin 3]", "[R2D2]", "[Mestre Alabaster²]",
                      "[Mestre ½ Alabaster]", "Mestre Alabaster", "[Mestre Alabaster",
                      "Mestre Alabaster]", "[     ]", "[]", "[Mestre_Alabaster]",
                      "[Mestre-Alabaster]", "[Mestre\tAlabaster]", "[[Mestre]]",
                      "[Mestre Alabaster] extra", "[Mestre × Alabaster]", ""]:
            with self.subTest(texto=texto):
                self.assertFalse(rv.validar_assinatura(texto))

    def test_limites_de_tamanho(self):
        for n in range(1, 46):
            with self.subTest(caracteres=n):
                self.assertEqual(rv.validar_assinatura("[" + "a" * n + "]"), 5 <= n <= 40)


class TestCabecalho(unittest.TestCase):
    def test_cabecalho_autentico_nao_tem_falhas(self):
        self.assertEqual(rv.validar_cabecalho("ALQ-10492", "15/03/2047", "[Mestre Alabaster]"), [])

    def test_relata_todas_as_falhas_de_uma_vez(self):
        falhas = rv.validar_cabecalho("for-12", "32/13/1999", "[R2D2]")
        self.assertEqual([f.motivo for f in falhas], [
            MotivoFraude.ID_INVALIDO, MotivoFraude.SELO_INVALIDO, MotivoFraude.ASSINATURA_INVALIDA,
        ])
        self.assertTrue(all(f.detalhe for f in falhas))

    def test_linha_campo_valor(self):
        casamento = rv.PADRAO_LINHA_CAMPO.fullmatch("Selo Temporal :  15/03/2047  ")
        self.assertIsNotNone(casamento)
        self.assertEqual(casamento["campo"], "Selo Temporal")
        self.assertEqual(casamento["valor"], "15/03/2047")
        self.assertIsNone(rv.PADRAO_LINHA_CAMPO.fullmatch("abacbc"))


if __name__ == "__main__":
    unittest.main()
