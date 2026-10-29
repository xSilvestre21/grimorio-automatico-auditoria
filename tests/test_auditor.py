"""Testes de integração: leitor + Regex + AFD + AVL sobre os pergaminhos de exemplo."""

import json
import tempfile
import unittest
from pathlib import Path

from gaa.auditor import Auditor, ErroHistorico
from gaa.leitor import ErroLeitura, coletar_arquivos, ler_arquivo
from gaa.modelos import GUILDA_NAO_IDENTIFICADA, MotivoFraude

PASTA_PERGAMINHOS = Path(__file__).resolve().parent.parent / "pergaminhos"
RELOGIO = lambda: "2026-10-29T12:00:00"  # noqa: E731 (relógio fixo para os testes)


def pergaminho(decreto="ALQ-10492", selo="15/03/2047", assinatura="[Mestre Alabaster]", runas="abacbc"):
    return f"Decreto: {decreto}\nSelo Temporal: {selo}\nAssinatura: {assinatura}\n---\n{runas}\n"


class TestSuiteDePergaminhos(unittest.TestCase):
    """Confere cada arquivo de pergaminhos/ contra o gabarito esperado.json."""

    @classmethod
    def setUpClass(cls):
        cls.gabarito = json.loads((PASTA_PERGAMINHOS / "esperado.json").read_text(encoding="utf-8"))["pergaminhos"]
        cls.auditor = Auditor(RELOGIO)
        cls.obtidos = {}
        for arquivo in coletar_arquivos([PASTA_PERGAMINHOS]):
            rotulo = arquivo.relative_to(PASTA_PERGAMINHOS).as_posix()
            for p in ler_arquivo(arquivo, rotulo):
                resultado = cls.auditor.auditar(p)
                cls.obtidos[p.origem] = None if resultado is None else [m.value for m in resultado.motivos]

    def test_cada_pergaminho_bate_com_o_gabarito(self):
        for origem, esperado in self.gabarito.items():
            with self.subTest(pergaminho=origem):
                self.assertEqual(self.obtidos.get(origem, "AUSENTE"), esperado)

    def test_gabarito_cobre_todos_os_arquivos(self):
        self.assertEqual(set(self.obtidos), set(self.gabarito))

    def test_suite_exercita_todos_os_motivos(self):
        usados = {m for motivos in self.gabarito.values() if motivos for m in motivos}
        self.assertEqual(usados, {m.value for m in MotivoFraude})

    def test_suite_tem_validos_e_invalidos(self):
        valores = list(self.gabarito.values())
        self.assertGreaterEqual(sum(1 for v in valores if v == []), 10)
        self.assertGreaterEqual(sum(1 for v in valores if v), 30)

    def test_arvore_resultante_e_avl_valida(self):
        self.auditor.arvore.verificar_invariantes()
        self.assertEqual(sum(len(v) for _, v in self.auditor.arvore), len(self.auditor.historico))


class TestFluxoDeAuditoria(unittest.TestCase):
    def setUp(self):
        self.auditor = Auditor(RELOGIO)

    def auditar(self, texto, origem="teste"):
        resumo = self.auditor.auditar_texto(texto, origem)
        return resumo.resultados[0] if resumo.resultados else None

    def test_pergaminho_autentico(self):
        r = self.auditar(pergaminho())
        self.assertTrue(r.autentico)
        self.assertEqual((r.identificador, r.guilda, r.estado_final_afd), ("ALQ-10492", "ALQ", "q2"))
        busca = self.auditor.consultar("ALQ-10492")
        self.assertTrue(busca.encontrado)
        self.assertEqual(busca.valor, [r])

    def test_afd_so_roda_depois_da_regex(self):
        r = self.auditar(pergaminho(selo="31/04/2050", runas="xyz"))
        self.assertEqual(r.motivos, [MotivoFraude.SELO_INVALIDO])
        self.assertIsNone(r.estado_final_afd)

    def test_clone_de_decreto_autenticado(self):
        self.auditar(pergaminho())
        r = self.auditar(pergaminho(assinatura="[Mestre Alabastro]"))
        self.assertEqual(r.motivos, [MotivoFraude.DECRETO_CLONADO])
        self.assertEqual(len(self.auditor.consultar("ALQ-10492").valor), 2)
        self.assertEqual(len(self.auditor.arvore), 1)

    def test_decreto_rejeitado_pode_ser_reapresentado_corrigido(self):
        self.assertFalse(self.auditar(pergaminho(runas="abc")).autentico)
        self.assertTrue(self.auditar(pergaminho(runas="aabc")).autentico)

    def test_conteudo_identico_e_ignorado(self):
        self.assertIsNotNone(self.auditar(pergaminho()))
        resumo = self.auditor.auditar_texto("# comentário diferente\n" + pergaminho().replace(": ", ":   "), "copia")
        self.assertEqual(resumo.resultados, [])
        self.assertEqual(resumo.ignorados, ["copia"])

    def test_pergaminho_sem_decreto_recebe_chave_propria(self):
        r1 = self.auditar("Selo Temporal: 15/03/2047\nAssinatura: [Mestre Alabaster]\n---\nbc")
        r2 = self.auditar("Selo Temporal: 16/03/2047\nAssinatura: [Mestre Alabaster]\n---\nbc")
        self.assertEqual((r1.identificador, r2.identificador), ("<sem-id-1>", "<sem-id-2>"))
        self.assertEqual(r1.guilda, GUILDA_NAO_IDENTIFICADA)
        self.assertEqual(r1.motivos, [MotivoFraude.CABECALHO_MALFORMADO])

    def test_assinatura_em_unicode_decomposto(self):
        r = self.auditar(pergaminho(assinatura="[Lorde Bastião]"))  # "ã" como a + til combinante
        self.assertTrue(r.autentico)

    def test_bom_e_quebras_de_linha_windows(self):
        r = self.auditar("﻿" + pergaminho().replace("\n", "\r\n"))
        self.assertTrue(r.autentico)


class TestPersistencia(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "historico.json"

    def tearDown(self):
        self.pasta.cleanup()

    def test_salvar_e_carregar_reconstroi_a_arvore(self):
        auditor = Auditor(RELOGIO)
        auditor.auditar_caminhos([PASTA_PERGAMINHOS])
        auditor.salvar(self.caminho)

        recarregado = Auditor.carregar(self.caminho, RELOGIO)
        self.assertEqual([r.para_dict() for r in recarregado.historico],
                         [r.para_dict() for r in auditor.historico])
        self.assertEqual(len(recarregado.arvore), len(auditor.arvore))
        recarregado.arvore.verificar_invariantes()
        self.assertTrue(recarregado.consultar("ALQ-10492").encontrado)
        # Reauditar as mesmas pastas não duplica nada.
        resumo = recarregado.auditar_caminhos([PASTA_PERGAMINHOS])
        self.assertEqual(resumo.resultados, [])
        self.assertEqual(len(recarregado.historico), len(auditor.historico))

    def test_contador_sem_id_continua_apos_carregar(self):
        auditor = Auditor(RELOGIO)
        auditor.auditar_texto("Selo Temporal: 15/03/2047\n---\nbc")
        auditor.salvar(self.caminho)
        recarregado = Auditor.carregar(self.caminho, RELOGIO)
        r = recarregado.auditar_texto("Assinatura: [Mestre Alabaster]\n---\nbc").resultados[0]
        self.assertEqual(r.identificador, "<sem-id-2>")

    def test_historico_inexistente_comeca_vazio(self):
        self.assertEqual(len(Auditor.carregar(self.caminho).historico), 0)

    def test_historico_corrompido(self):
        for conteudo in ["{ isto não é json", '{"versao": 99, "registros": []}', '{"versao": 1}',
                         '{"versao": 1, "registros": [{"identificador": "X"}]}']:
            with self.subTest(conteudo=conteudo):
                self.caminho.write_text(conteudo, encoding="utf-8")
                with self.assertRaises(ErroHistorico):
                    Auditor.carregar(self.caminho)


class TestLeituraDeArquivos(unittest.TestCase):
    def test_caminho_inexistente(self):
        with self.assertRaises(ErroLeitura):
            Auditor().auditar_caminhos(["nao/existe.txt"])

    def test_arquivo_que_nao_e_utf8_vai_para_erros(self):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / "latin1.txt").write_bytes(pergaminho(assinatura="[Bastião]").encode("latin-1"))
            (Path(pasta) / "ok.txt").write_text(pergaminho(), encoding="utf-8")
            resumo = Auditor().auditar_caminhos([pasta])
        self.assertEqual(len(resumo.erros), 1)
        self.assertEqual(resumo.autenticos, 1)


if __name__ == "__main__":
    unittest.main()
