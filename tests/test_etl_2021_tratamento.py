import json
from datetime import date, datetime

from tests.apoio_etl_2021 import CenarioETL, etl, registro


class Tratamento2021(CenarioETL):
    def test_opcionais_invalidos_e_originais(self):
        self.mes(1, [registro(partida_real='31/02/2021 00:00', numero_assentos='-1',
                             referencia='invalida')])
        resumo = self.executar()['resumo']
        self.assertEqual(resumo['rejeicoes'], 0)
        self.assertEqual(resumo['ocorrencias_anomalias'], 3)
        anomalias = self.tabela('vra_anomalias')
        self.assertEqual(set(anomalias.campo), {'partida_real', 'numero_assentos', 'referencia'})
        self.assertEqual(set(anomalias.bruto__numero_assentos), {'-1'})
        voo = self.tabela('vra_tratada').iloc[0]
        self.assertEqual(voo.numero_assentos, '')
        self.assertEqual(voo.diferenca_partida_min, '')
        self.assertEqual(voo.partida_atipica_flag, 'False')

    def test_todos_motivos_e_todos_representantes_rejeitados(self):
        for mes in range(1, 13):
            self.mes(mes, [registro(companhia_icao=' ', aeroporto_origem='', aeroporto_destino='',
                                    partida_prevista='errada', chegada_prevista='')])
        resumo = self.executar()['resumo']
        self.assertEqual(resumo['tratada'], 0)
        rejeicao = self.tabela('vra_rejeicoes').iloc[0]
        self.assertEqual(len(json.loads(rejeicao.motivo_rejeicao)), 5)
        self.assertEqual(rejeicao.companhia_icao, '')
        self.assertEqual(rejeicao.bruto__companhia_icao, ' ')
        self.assertEqual(rejeicao.bruto__partida_prevista, 'errada')

    def test_rastreabilidade_zeros_referencias_e_cruzamento_ano(self):
        self.mes(1, [registro(numero_voo='0035', referencia='01/01/2021 00:00:00'),
                     registro(numero_voo='0036', referencia='2021-01-01',
                              partida_prevista='31/12/2020 23:50', partida_real='01/01/2021 00:05',
                              chegada_prevista='01/01/2021 02:50', chegada_real='')])
        self.executar()
        tratados = self.tabela('vra_tratada')
        self.assertEqual(tratados.iloc[0].numero_voo, '0035')
        self.assertEqual(list(tratados.iloc[:2].referencia), ['2021-01-01', '2021-01-01'])
        fora = tratados.iloc[1]
        self.assertEqual(fora.partida_ano_diverge_flag, 'True')
        self.assertEqual(fora.diferenca_partida_min, '15')
        self.assertEqual(fora.diferenca_chegada_min, '')
        self.assertEqual(fora.chegada_atipica_flag, 'False')
        self.assertEqual(fora.pipeline, 'ETL')
        self.assertEqual(fora.versao_contrato, '1.1')
        self.assertEqual(datetime.fromisoformat(fora.data_carga).utcoffset().total_seconds(), 0)
        self.assertEqual(len(self.tabela('partidas_previstas_fora_ano')), 1)
        self.assertTrue((self.saida / 'etl_log_arquivos.csv').exists())

    def test_datas_calendario_assentos_e_precisao(self):
        self.assertIsNone(etl.datahora_segura('29/02/2021 00:00'))
        self.assertIsNotNone(etl.datahora_segura('29/02/2020 00:00'))
        self.assertIsNone(etl.datahora_segura('01/01/2021 24:00'))
        self.assertEqual(etl.referencia_segura('2021-01-01'), date(2021, 1, 1))
        self.assertIsNone(etl.referencia_segura('01/01/2021 00:00:01'))
        for valor in ['-1', '1.5', '2147483648', '9' * 5000]:
            self.assertIsNone(etl.assentos_seguros(valor))
        self.assertEqual(etl.assentos_seguros('0' * 5000 + '2'), 2)
        self.mes(1, [registro(partida_prevista='01/01/0001 00:00', partida_real='02/01/0001 00:00',
                              chegada_prevista='30/12/9999 00:00', chegada_real='31/12/9999 00:01')])
        self.executar()
        voo = self.tabela('vra_tratada').iloc[0]
        self.assertEqual(voo.diferenca_partida_min, '1440')
        self.assertEqual(voo.partida_atipica_flag, 'False')
        self.assertEqual(voo.chegada_atipica_flag, 'True')

    def test_ano_inteiro_somente_cabecalhos(self):
        for mes in range(1, 13):
            self.mes(mes, [])
        self.assertEqual(self.executar()['resumo']['bruta'], 0)
