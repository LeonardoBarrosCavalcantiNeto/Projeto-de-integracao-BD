import json

from tests.apoio_etl_2021 import CenarioETL, registro


class Duplicatas2021(CenarioETL):
    def test_entre_meses_e_representante_estavel(self):
        igual = registro(numero_voo='0042')
        self.mes(1, [igual], codeshare=True)
        self.mes(2, [dict(igual, Codeshare='OUTRO/42')], codeshare=True)
        self.mes(12, [igual])
        resumo = self.executar()['resumo']
        self.assertEqual(resumo['duplicatas_excedentes'], 2)
        duplicatas = self.tabela('vra_duplicatas_excluidas')
        self.assertEqual(set(duplicatas.arquivo_preservado), {'VRA_2021_01.csv'})
        self.assertEqual(set(duplicatas.linha_preservada), {'2'})
        self.assertEqual(set(duplicatas.quantidade_ocorrencias), {'3'})
        ids = duplicatas.grupo_duplicata_id.tolist()
        self.executar()
        self.assertEqual(ids, self.tabela('vra_duplicatas_excluidas').grupo_duplicata_id.tolist())

    def test_duplicata_invalida_nao_e_contada_duas_vezes(self):
        invalida = registro(partida_prevista='', chegada_prevista='')
        for mes in range(1, 13):
            self.mes(mes, [invalida])
        resumo = self.executar()['resumo']
        self.assertEqual((resumo['bruta'], resumo['duplicatas_excedentes'],
                          resumo['rejeicoes'], resumo['tratada']), (12, 11, 1, 0))
        self.assertEqual(resumo['intersecao_excedentes_duplicados_invalidos'], 11)
        auditoria = self.tabela('vra_duplicatas_excluidas')
        self.assertEqual(json.loads(auditoria.iloc[0].motivo_rejeicao_diagnostico),
                         ['PARTIDA_PREVISTA_AUSENTE', 'CHEGADA_PREVISTA_AUSENTE'])
        conciliacao = json.loads((self.saida / 'etl_resumo.json').read_text())['conciliacao']
        self.assertTrue(conciliacao['conciliada'])

    def test_iguais_apenas_apos_padronizacao_sao_preservados(self):
        self.mes(1, [registro(companhia_icao=' azu ', numero_voo='0042'),
                     registro(companhia_icao='AZU', numero_voo='0042')])
        self.saida.mkdir(exist_ok=True)
        legado = self.saida / 'duplicatas_pos_trim_upper.csv.gz'
        legado.write_bytes(b'auditoria antiga')
        resumo = self.executar()['resumo']
        self.assertFalse(legado.exists())
        self.assertEqual(resumo['duplicatas_excedentes'], 0)
        self.assertEqual(resumo['duplicatas_apos_trim_upper'], 1)
        self.assertEqual(resumo['tratada'], 13)
        self.assertEqual(len(self.tabela('vra_possiveis_duplicatas_padronizacao')), 2)
