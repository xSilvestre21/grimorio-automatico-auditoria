"""Testes do relatório de ranking de guildas."""

import json
import tempfile
import unittest
from pathlib import Path

from gaa.modelos import MotivoFraude, ResultadoAuditoria
from gaa.relatorio import NOME_JSON, NOME_TXT, calcular_ranking, gerar_relatorios, ranking_para_texto


def registro(guilda, *motivos):
    return ResultadoAuditoria(
        identificador=f"{guilda}-0000", guilda=guilda, autentico=not motivos, motivos=list(motivos),
        detalhes=["detalhe"] * len(motivos), origem="teste", selo=None, assinatura=None, runas=None,
        estado_final_afd=None, digesto="x", auditado_em="2026-10-29T12:00:00",
    )


IMPAR, SELO, CLONE = MotivoFraude.RUNAS_A_IMPAR, MotivoFraude.SELO_INVALIDO, MotivoFraude.DECRETO_CLONADO
REGISTROS = [
    registro("FOR", IMPAR), registro("FOR", SELO), registro("FOR", IMPAR, CLONE), registro("FOR"),
    registro("MAG", SELO), registro("ALQ", IMPAR), registro("ALQ"), registro("HER"),
]


class TestCalculoDoRanking(unittest.TestCase):
    def test_ordem_empate_e_posicoes(self):
        ranking = calcular_ranking(REGISTROS)
        self.assertEqual([(l.posicao, l.sigla, l.fraudes) for l in ranking],
                         [(1, "FOR", 3), (2, "ALQ", 1), (2, "MAG", 1), (4, "HER", 0)])

    def test_contagens_e_taxa(self):
        forjadores = calcular_ranking(REGISTROS)[0]
        self.assertEqual((forjadores.autenticos, forjadores.total), (1, 4))
        self.assertAlmostEqual(forjadores.taxa_fraude, 0.75)
        self.assertEqual(forjadores.motivos, {"RUNAS_A_IMPAR": 2, "DECRETO_CLONADO": 1, "SELO_INVALIDO": 1})

    def test_ranking_vazio(self):
        self.assertEqual(calcular_ranking([]), [])
        self.assertIn("Nenhum pergaminho auditado", ranking_para_texto([], "agora"))


class TestArquivosGerados(unittest.TestCase):
    def test_gera_json_e_txt(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho_json, caminho_txt = gerar_relatorios(REGISTROS, Path(pasta) / "nova", "2026-10-29T12:00:00")
            self.assertEqual((caminho_json.name, caminho_txt.name), (NOME_JSON, NOME_TXT))
            dados = json.loads(caminho_json.read_text(encoding="utf-8"))
            texto = caminho_txt.read_text(encoding="utf-8")

        self.assertEqual(dados["total_pergaminhos"], 8)
        self.assertEqual(dados["total_fraudes"], 5)
        primeiro = dados["ranking"][0]
        self.assertEqual(set(primeiro), {"posicao", "guilda", "nome", "fraudes", "autenticos",
                                         "total", "taxa_fraude", "motivos"})
        self.assertEqual((primeiro["guilda"], primeiro["nome"], primeiro["taxa_fraude"]),
                         ("FOR", "Guilda dos Forjadores", 0.75))
        self.assertIn("1º  FOR", texto)
        self.assertIn("2º  ALQ", texto)
        self.assertIn("Decreto clonado", texto)


if __name__ == "__main__":
    unittest.main()
