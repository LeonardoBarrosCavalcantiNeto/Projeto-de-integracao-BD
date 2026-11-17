import json
import os
from unittest import SkipTest, mock

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.apoio_etl_2021 import CenarioETL, etl, registro


class StatusExecucao2021(CenarioETL):
    def test_falha_de_entrada_invalida_status_anterior(self):
        self.executar()
        (self.entrada / 'VRA_2021_01.csv').unlink()
        with self.assertRaises(FileNotFoundError):
            self.executar(load_database=True)
        status = json.loads((self.saida / 'status_carga_postgresql.json').read_text())
        meta = json.loads((self.saida / 'metadados_execucao.json').read_text())
        self.assertEqual(status['status'], 'nao_iniciada')
        self.assertFalse(status['transacao_confirmada'])
        self.assertEqual(meta['status_execucao'], 'falhou')
        self.assertEqual(meta['inicio_utc'], status['execucao_id'])


class CargaPostgreSQL2021(CenarioETL):
    """Integração real: exige URL de um banco dedicado chamado etl_2021_test ou etl_test."""
    @classmethod
    def setUpClass(cls):
        url = os.environ.get('ETL_2021_TEST_DATABASE_URL')
        if not url:
            raise SkipTest('Defina ETL_2021_TEST_DATABASE_URL para executar no PostgreSQL real.')
        parsed = make_url(url).set(drivername='postgresql+psycopg')
        if parsed.database not in {'etl_test', 'etl_2021_test'}:
            raise ValueError('Use um banco de teste dedicado: etl_test ou etl_2021_test.')
        cls.url = parsed.render_as_string(hide_password=False)
        cls.engine = create_engine(parsed, hide_parameters=True)

    @classmethod
    def tearDownClass(cls):
        with cls.engine.begin() as conn:
            conn.execute(text('DROP SCHEMA IF EXISTS etl_2021 CASCADE'))
        cls.engine.dispose()

    def setUp(self):
        super().setUp()
        self.env = mock.patch.dict(os.environ, {'DATABASE_URL': self.url})
        self.env.start()
        self.addCleanup(self.env.stop)
        with self.engine.begin() as conn:
            conn.execute(text('DROP SCHEMA IF EXISTS etl_2021 CASCADE'))

    def contagem(self, tabela):
        with self.engine.connect() as conn:
            return conn.execute(text(f'SELECT COUNT(*) FROM etl_2021."{tabela}"')).scalar_one()

    def test_contagens_bloqueio_repeticao_substituicao(self):
        resultado = self.executar(load_database=True)
        status = resultado['carga_postgresql']
        self.assertTrue(status['transacao_confirmada'])
        self.assertEqual(len(status['contagens']), 10)
        for tabela, quantidade in status['contagens'].items():
            self.assertEqual(self.contagem(tabela), quantidade)
        with self.assertRaisesRegex(ValueError, 'substituição está desativada'):
            self.executar(load_database=True)
        self.mes(1, [registro(numero_voo='0042'), registro(numero_voo='0043')])
        self.executar(load_database=True, replace=True)
        self.assertEqual(self.contagem('vra_tratada'), 13)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text('SELECT count(*) FROM etl_2021.vra_bruta GROUP BY arquivo_origem, linha_origem HAVING count(*)>1')).all(), [])

    def test_rollback_preserva_carga_anterior_e_status_falhou(self):
        self.executar(load_database=True)
        self.mes(1, [registro(numero_voo='0042'), registro(numero_voo='0043')])
        original = pd.DataFrame.to_sql
        def falhar(base, nome, *args, **kwargs):
            if nome == 'vra_rejeicoes':
                raise RuntimeError('Falha injetada após duas tabelas.')
            return original(base, nome, *args, **kwargs)
        with mock.patch.object(pd.DataFrame, 'to_sql', falhar):
            with self.assertRaisesRegex(RuntimeError, 'Falha injetada'):
                self.executar(load_database=True, replace=True)
        self.assertEqual(self.contagem('vra_tratada'), 12)
        self.assertEqual(self.contagem('vra_bruta'), 12)
        status = json.loads((self.saida / 'status_carga_postgresql.json').read_text())
        self.assertEqual(status['status'], 'falhou')
        self.assertFalse(status['transacao_confirmada'])

    def test_auditorias_nao_vazias_e_tipos(self):
        invalida = registro(numero_voo='0042', partida_prevista='', chegada_prevista='')
        self.mes(1, [invalida, registro(numero_voo='0043', numero_assentos='-1'),
                     registro(numero_voo='0044', companhia_icao=' azu '),
                     registro(numero_voo='0044', companhia_icao='AZU')])
        self.mes(2, [invalida])
        self.executar(load_database=True)
        self.assertEqual(self.contagem('vra_duplicatas_excluidas'), 1)
        self.assertEqual(self.contagem('vra_anomalias'), 1)
        self.assertEqual(self.contagem('vra_possiveis_duplicatas_padronizacao'), 2)
        with self.engine.connect() as conn:
            motivos = conn.execute(text('SELECT motivo_rejeicao FROM etl_2021.vra_rejeicoes')).scalar_one()
            self.assertEqual(len(motivos), 2)
            tipo = conn.execute(text("SELECT data_type FROM information_schema.columns WHERE table_schema='etl_2021' AND table_name='vra_tratada' AND column_name='data_carga'")).scalar_one()
            self.assertEqual(tipo, 'timestamp with time zone')
