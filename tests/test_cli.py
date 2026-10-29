"""Testes da interface de linha de comando."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from gaa import cli

PASTA_PERGAMINHOS = Path(__file__).resolve().parent.parent / "pergaminhos"


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.historico = Path(self.pasta.name) / "historico.json"
        self.saida_dir = Path(self.pasta.name) / "saida"

    def tearDown(self):
        self.pasta.cleanup()

    def executar(self, *argumentos):
        saida, erros = io.StringIO(), io.StringIO()
        with redirect_stderr(erros):
            codigo = cli.main(["--historico", str(self.historico), "--saida", str(self.saida_dir),
                               "--sem-cor", *argumentos], saida=saida)
        return codigo, saida.getvalue(), erros.getvalue()

    def test_auditar_gera_historico_e_ranking(self):
        codigo, texto, _ = self.executar("auditar", str(PASTA_PERGAMINHOS))
        self.assertEqual(codigo, cli.OK)
        self.assertIn("[AUTÊNTICO] ALQ-10492", texto)
        self.assertIn("[FRAUDE]", texto)
        self.assertIn("[IGNORADO]", texto)
        self.assertTrue(self.historico.exists())
        ranking = json.loads((self.saida_dir / "ranking_guildas.json").read_text(encoding="utf-8"))
        self.assertEqual(ranking["ranking"][0]["guilda"], "FOR")
        self.assertTrue((self.saida_dir / "ranking_guildas.txt").exists())

    def test_consultar(self):
        self.executar("auditar", str(PASTA_PERGAMINHOS))
        codigo, texto, _ = self.executar("consultar", "FOR-8001")
        self.assertEqual(codigo, cli.OK)
        self.assertIn("3 tentativa(s) registrada(s), 2 fraudulenta(s)", texto)
        self.assertIn("Decreto clonado", texto)
        codigo, texto, _ = self.executar("consultar", "XYZ-0000")
        self.assertEqual(codigo, cli.NAO_ENCONTRADO)
        self.assertIn("não consta", texto)

    def test_listar_por_guilda(self):
        self.executar("auditar", str(PASTA_PERGAMINHOS))
        codigo, texto, _ = self.executar("listar", "--guilda", "alq")
        self.assertEqual(codigo, cli.OK)
        linhas = [l for l in texto.splitlines() if l.startswith("  ")]
        self.assertTrue(linhas)
        self.assertTrue(all(l.strip().startswith("ALQ-") for l in linhas))
        self.assertNotIn("ALQ-١٢٣٤", texto)  # identificador inválido não pertence à guilda
        _, texto, _ = self.executar("listar", "--status", "autenticos")
        self.assertNotIn("✘", texto)

    def test_ranking(self):
        self.executar("auditar", str(PASTA_PERGAMINHOS))
        codigo, texto, _ = self.executar("ranking")
        self.assertEqual(codigo, cli.OK)
        self.assertIn("Guilda dos Forjadores", texto)

    def test_afd(self):
        codigo, texto, _ = self.executar("afd", "abacbc")
        self.assertEqual(codigo, cli.OK)
        self.assertIn("δ(q1, c) = q2", texto)
        self.assertIn("ACEITA", texto)
        codigo, texto, _ = self.executar("afd", "--tabela", "abx")
        self.assertEqual(codigo, cli.NAO_ENCONTRADO)
        self.assertIn("→ q0", texto)
        self.assertIn("fora de Σ", texto)

    def test_arvore(self):
        self.executar("auditar", str(PASTA_PERGAMINHOS))
        codigo, texto, _ = self.executar("arvore")
        self.assertEqual(codigo, cli.OK)
        self.assertIn("Invariantes AVL verificadas", texto)

    def test_modo_interativo(self):
        self.executar("auditar", str(PASTA_PERGAMINHOS))
        respostas = iter(["2", "ALQ-10492", "5", "abc", "3", "MAG", "9", "0"])
        args = cli.criar_parser().parse_args(["--historico", str(self.historico), "--saida",
                                              str(self.saida_dir), "--sem-cor", "interativo"])
        saida = io.StringIO()
        codigo = cli.comando_interativo(cli.Contexto(args, saida), entrada=lambda _: next(respostas))
        texto = saida.getvalue()
        self.assertEqual(codigo, cli.OK)
        self.assertIn("AUTÊNTICO", texto)
        self.assertIn("REJEITADA", texto)
        self.assertIn("MAG-777777", texto)
        self.assertIn("Opção desconhecida", texto)

    def test_modo_interativo_encerra_com_eof(self):
        args = cli.criar_parser().parse_args(["--historico", str(self.historico), "--sem-cor", "interativo"])

        def fim_de_arquivo(_):
            raise EOFError

        saida = io.StringIO()
        self.assertEqual(cli.comando_interativo(cli.Contexto(args, saida), entrada=fim_de_arquivo), cli.OK)

    def test_erros_sao_tratados(self):
        codigo, _, erros = self.executar("auditar", "nao/existe")
        self.assertEqual(codigo, cli.ERRO)
        self.assertIn("caminho não encontrado", erros)
        self.historico.write_text("{ corrompido", encoding="utf-8")
        codigo, _, erros = self.executar("consultar", "ALQ-10492")
        self.assertEqual(codigo, cli.ERRO)
        self.assertIn("corrompido", erros)


if __name__ == "__main__":
    unittest.main()
