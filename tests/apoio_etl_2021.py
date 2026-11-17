import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts import etl_vra_anac_2021 as etl


def registro(**alteracoes):
    valores = ['azU', 'Azul', '0035', '0', 'N', 'A320', '180',
               'SBGR', 'Guarulhos', '01/01/2021 23:50', '02/01/2021 00:00',
               'SBRF', 'Recife', '02/01/2021 02:50', '02/01/2021 02:45',
               'REALIZADO', '', '2021-01-01', 'Atrasado', 'Antecipado']
    dados = dict(zip(etl.colunas_comuns, valores))
    for campo, valor in alteracoes.items():
        original = next((k for k, v in etl.mapa_colunas.items() if v == campo), campo)
        dados[original] = valor
    return dados


class CenarioETL(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.entrada = self.raiz / 'entrada'
        self.saida = self.raiz / 'saida'
        self.entrada.mkdir()
        for mes in range(1, 13):
            self.mes(mes, [registro(numero_voo=f'{mes:04d}')])

    def mes(self, mes, registros, codeshare=False, cabecalho=None):
        caminho = self.entrada / f'VRA_2021_{mes:02d}.csv'
        campos = cabecalho or etl.colunas_comuns + (['Codeshare'] if codeshare else [])
        with caminho.open('w', encoding='utf-8-sig', newline='') as arquivo:
            escritor = csv.writer(arquivo, delimiter=';')
            escritor.writerow(campos)
            for dados in registros:
                escritor.writerow([dados.get(c, '') for c in campos])
        return caminho

    def executar(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return etl.run_etl(self.entrada, self.saida, **kwargs)

    def tabela(self, nome):
        return pd.read_csv(self.saida / f'{nome}.csv.gz', dtype=str, keep_default_na=False)
