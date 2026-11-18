import csv
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest import mock

from scripts import colab_etl_2021 as colab
from tests.apoio_etl_2021 import CenarioETL


class EntradaColab2021(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.zip = self.raiz / "data_2021_anac.zip"
        self.entrada = self.raiz / "dados"
        self.inventario = self.raiz / "inventario.csv"
        # BOM, CRLF e zeros devem sobreviver à preparação do ZIP.
        self.conteudos = {nome: b"\xef\xbb\xbfcoluna;voo\r\n2021;0035\r\n" + nome.encode()
                          for nome in colab.ARQUIVOS_2021}
        with self.inventario.open("w", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(["arquivo", "sha256"])
            for nome, conteudo in self.conteudos.items():
                escritor.writerow([nome, hashlib.sha256(conteudo).hexdigest()])

    def criar_zip(self, *, pasta="", omitir=None, repetir=False, alterar=False):
        with zipfile.ZipFile(self.zip, "w") as arquivo:
            for nome, conteudo in self.conteudos.items():
                if nome != omitir:
                    arquivo.writestr(pasta + nome, conteudo + (b"alterado" if alterar else b""))
            arquivo.writestr("LEIA_ME.txt", "Arquivo auxiliar permitido.")
            if repetir:
                nome = colab.ARQUIVOS_2021[0]
                arquivo.writestr("outra_pasta/" + nome, self.conteudos[nome])

    def preparar(self):
        return colab.preparar_entrada_zip(self.zip, self.entrada, self.inventario)

    def test_zip_valido_preserva_bytes_e_pode_repetir(self):
        self.criar_zip()
        resultado = self.preparar()
        self.assertEqual(len(resultado["arquivos"]), 12)
        self.assertTrue(resultado["hashes_conferidos"])
        self.assertEqual(resultado["sha256_zip"], colab.sha256_arquivo(self.zip))
        for nome, conteudo in self.conteudos.items():
            self.assertEqual((self.entrada / nome).read_bytes(), conteudo)
        self.assertEqual(self.preparar(), resultado)

    def test_pasta_interna(self):
        self.criar_zip(pasta="dados/2021/")
        self.preparar()
        self.assertEqual({p.name for p in self.entrada.iterdir()}, set(colab.ARQUIVOS_2021))

    def test_manifesto_json_seleciona_os_12_meses_de_2021(self):
        self.criar_zip()
        self.inventario = self.raiz / "manifesto_vra.json"
        arquivos = [{"ano_origem": 2020, "arquivo_origem": "VRA_2020_01.csv", "sha256": "0" * 64}]
        arquivos.extend(
            {"ano_origem": 2021, "arquivo_origem": nome, "sha256": hashlib.sha256(conteudo).hexdigest()}
            for nome, conteudo in self.conteudos.items()
        )
        self.inventario.write_text(json.dumps({"arquivos": arquivos}), encoding="utf-8")
        resultado = self.preparar()
        self.assertTrue(resultado["hashes_conferidos"])
        self.assertEqual({item["arquivo"] for item in resultado["arquivos"]}, set(self.conteudos))

    def test_mes_ausente(self):
        self.criar_zip(omitir=colab.ARQUIVOS_2021[-1])
        with self.assertRaisesRegex(ValueError, "Meses ausentes"):
            self.preparar()
        self.assertFalse(self.entrada.exists())

    def test_mes_repetido(self):
        self.criar_zip(repetir=True)
        with self.assertRaisesRegex(ValueError, "Mês repetido"):
            self.preparar()

    def test_hash_divergente_nao_publica_entrada(self):
        self.criar_zip(alterar=True)
        with self.assertRaisesRegex(ValueError, "SHA-256 diferente"):
            self.preparar()
        self.assertFalse(self.entrada.exists())

    def test_arquivo_local_diferente_e_preservado(self):
        self.criar_zip()
        self.entrada.mkdir()
        original = self.entrada / colab.ARQUIVOS_2021[0]
        original.write_bytes(b"arquivo local anterior")
        with self.assertRaisesRegex(ValueError, "preservado sem sobrescrever"):
            self.preparar()
        self.assertEqual(original.read_bytes(), b"arquivo local anterior")


class PreparacaoBancoColab2021(unittest.TestCase):
    def test_fora_colab_nao_instala_nem_configura(self):
        with mock.patch.object(colab, "em_colab_hospedado", return_value=False), \
                mock.patch.object(colab.subprocess, "run") as executar:
            with self.assertRaisesRegex(RuntimeError, "sessão hospedada"):
                colab.preparar_postgresql_temporario()
            executar.assert_not_called()

    def test_configuracao_temporaria_sem_expor_credenciais(self):
        segredo = "segredo_temporario_123"
        with mock.patch.object(colab, "em_colab_hospedado", return_value=True), \
                mock.patch.object(colab.subprocess, "run") as executar, \
                mock.patch.object(colab, "_psql_administrativo", side_effect=["", "", ""]) as admin, \
                mock.patch.object(colab.secrets, "token_urlsafe", return_value=segredo), \
                mock.patch("psycopg.connect") as conectar, \
                mock.patch.dict(os.environ, {"ETL_2021_COLAB_PASSWORD": ""}), \
                contextlib.redirect_stdout(io.StringIO()) as saida:
            conectar.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = ("16.test",)
            resultado = colab.preparar_postgresql_temporario()
            self.assertEqual(resultado["banco"], "etl_2021_colab")
            self.assertEqual(resultado["versao_postgresql"], "16.test")
            self.assertIn(segredo, os.environ["DATABASE_URL"])
            self.assertNotIn(segredo, repr(resultado) + saida.getvalue() + repr(executar.call_args_list))
            self.assertTrue(any("CREATE DATABASE etl_2021_colab" in c.args[0] for c in admin.call_args_list))

    def test_erro_administrativo_nao_expoe_stderr(self):
        processo = mock.Mock(returncode=1, stdout="", stderr="senha que não deve aparecer")
        with mock.patch.object(colab.subprocess, "run", return_value=processo):
            with self.assertRaisesRegex(RuntimeError, "Falha ao configurar") as erro:
                colab._psql_administrativo("comando de configuração")
            self.assertNotIn(processo.stderr, str(erro.exception))


class IntegracaoColab2021(CenarioETL):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        url = os.environ.get("ETL_2021_TEST_DATABASE_URL")
        if not url:
            raise unittest.SkipTest("Defina ETL_2021_TEST_DATABASE_URL para verificar os auxiliares no PostgreSQL real.")
        parsed = make_url(url).set(drivername="postgresql+psycopg")
        if parsed.database not in {"etl_test", "etl_2021_test"}:
            raise ValueError("Use um banco dedicado etl_test ou etl_2021_test.")
        cls.url = parsed.render_as_string(hide_password=False)
        cls.engine = create_engine(parsed, hide_parameters=True)

    @classmethod
    def tearDownClass(cls):
        from sqlalchemy import text
        with cls.engine.begin() as conexao:
            conexao.execute(text("DROP SCHEMA IF EXISTS etl_2021 CASCADE"))
        cls.engine.dispose()

    def setUp(self):
        super().setUp()
        from sqlalchemy import text
        patch = mock.patch.dict(os.environ, {"DATABASE_URL": self.url})
        patch.start()
        self.addCleanup(patch.stop)
        with self.engine.begin() as conexao:
            conexao.execute(text("DROP SCHEMA IF EXISTS etl_2021 CASCADE"))
        self.codigo = Path(__file__).resolve().parents[1]

    def informacoes_zip(self):
        caminho = self.raiz / "data_2021_anac.zip"
        inventario = self.raiz / "inventario.csv"
        with zipfile.ZipFile(caminho, "w") as arquivo, inventario.open("w", newline="") as dados:
            escritor = csv.writer(dados)
            escritor.writerow(["arquivo", "sha256"])
            for p in sorted(self.entrada.glob("*.csv")):
                arquivo.write(p, "pasta/" + p.name)
                escritor.writerow([p.name, colab.sha256_arquivo(p)])
        return colab.preparar_entrada_zip(caminho, self.entrada, inventario)

    def test_validacao_pos_commit_e_exportacao(self):
        zip_info = self.informacoes_zip()
        resultado = self.executar(load_database=True)
        validacao = colab.validar_carga_postgresql(resultado, self.codigo)
        self.assertEqual(validacao["contagens_apos_commit"]["vra_bruta"], 12)
        self.assertTrue(all(validacao["origens_unicas"].values()))
        self.assertEqual(validacao["ambiente"], "local")
        publicado = colab.exportar_evidencias_colab(resultado, zip_info)
        self.assertFalse(publicado["colab_executado"])
        self.assertFalse(publicado["regressao"]["bruta"]["igual"])
        self.assertTrue((self.saida / "vra_tratada.csv.gz").exists())
        with zipfile.ZipFile(publicado["zip"]) as arquivo:
            nomes = arquivo.namelist()
            self.assertIn("resultados/logs/metadados_execucao_etl_2021_colab.json", nomes)
            self.assertIn("dados/processados/2021/etl/vra_bruta/manifesto_sha256.csv", nomes)
            self.assertNotIn("dados/processados/2021/etl/vra_tratada.csv.gz", nomes)
            self.assertFalse(any(n.endswith("VRA_2021_01.csv") for n in nomes))
            self.assertFalse(any(n.endswith(".env") for n in nomes))
            meta = json.loads(arquivo.read("resultados/logs/metadados_execucao_etl_2021_colab.json"))
            self.assertFalse(meta["colab_executado"])
        completo = colab.exportar_evidencias_colab(resultado, zip_info, incluir_tratada=True)
        with zipfile.ZipFile(completo["zip"]) as arquivo:
            self.assertIn("dados/processados/2021/etl/vra_tratada.csv.gz", arquivo.namelist())

    def test_detecta_banco_alterado_depois_carga(self):
        from sqlalchemy import text
        resultado = self.executar(load_database=True)
        with self.engine.begin() as conexao:
            conexao.execute(text("DELETE FROM etl_2021.vra_tratada WHERE arquivo_origem='VRA_2021_01.csv'"))
        with self.assertRaisesRegex(ValueError, "Contagem divergente após COMMIT"):
            colab.validar_carga_postgresql(resultado, self.codigo)

    def test_exportacao_recusa_validacao_antiga_e_etl_falhado(self):
        zip_info = self.informacoes_zip()
        resultado = self.executar(load_database=True)
        colab.validar_carga_postgresql(resultado, self.codigo)
        resultado_novo = self.executar(load_database=True, replace=True)
        with self.assertRaisesRegex(ValueError, "não corresponde à execução atual"):
            colab.exportar_evidencias_colab(resultado_novo, zip_info)
        (self.entrada / "VRA_2021_01.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            self.executar(load_database=True)
        with self.assertRaisesRegex(ValueError, "execução atual"):
            colab.exportar_evidencias_colab(resultado_novo, zip_info)
