import csv
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from scripts.comparar_etl_elt_2021 import CAMPOS, comparar


class Comparacao2021(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.inventarios = [self.raiz / f'inventario_{lado}.csv' for lado in ['etl', 'elt']]
        for lado in range(2):
            self.inventario(lado)
        self.tratadas = [self.raiz / 'etl.csv.gz', self.raiz / 'elt.csv']
        self.linha = {c: '' for c in CAMPOS}
        self.linha.update(arquivo_origem='VRA_2021_01.csv', linha_origem='2', ano_origem='2021',
                          companhia_icao='AZU', numero_voo='0035', aeroporto_origem='SBGR',
                          aeroporto_destino='SBRF', partida_prevista='2021-01-01 10:00:00',
                          chegada_prevista='2021-01-01 13:00:00', referencia='2021-01-01',
                          partida_atipica_flag='False', chegada_atipica_flag='False', partida_ano_diverge_flag='False')
        for lado in range(2):
            self.tratada(lado, [self.linha])

    def inventario(self, lado, diferente=False):
        with self.inventarios[lado].open('w', newline='') as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(['arquivo' if lado == 0 else 'arquivo_origem', 'sha256'])
            for mes in range(1, 13):
                escritor.writerow([f'VRA_2021_{mes:02d}.csv', ('b' if diferente and mes == 1 else 'a') * 64])

    def tratada(self, lado, linhas, sem_flag=False):
        abrir = gzip.open if lado == 0 else open
        campos = ['arquivo_origem', 'linha_origem'] + [c for c in CAMPOS if not (sem_flag and c == 'partida_ano_diverge_flag')]
        with abrir(self.tratadas[lado], 'wt', encoding='utf-8', newline='') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction='ignore')
            escritor.writeheader()
            escritor.writerows(linhas)

    def comparar(self):
        return comparar(*self.inventarios, *self.tratadas)

    def test_mesmos_totais_valores_divergentes(self):
        self.tratada(1, [dict(self.linha, numero_voo='35')])
        resultado = self.comparar()
        self.assertEqual(resultado['registros_etl'], resultado['registros_elt'])
        self.assertEqual(resultado['status'], 'divergentes')
        self.assertEqual(resultado['divergencias_por_campo'], {'numero_voo': 1})

    def test_hashes_diferentes(self):
        self.inventario(1, diferente=True)
        resultado = self.comparar()
        self.assertFalse(resultado['hashes_entrada_equivalentes'])
        self.assertEqual(resultado['status'], 'divergentes')

    def test_nulo_e_zero_distintos(self):
        self.tratada(1, [dict(self.linha, atraso_partida_min='0')])
        self.assertEqual(self.comparar()['divergencias_por_campo'], {'atraso_partida_min': 1})

    def test_normaliza_representacoes_e_flag_derivada(self):
        self.tratada(0, [dict(self.linha, numero_assentos='180', diferenca_partida_min='0')])
        self.tratada(1, [dict(self.linha, numero_assentos='180.00', diferenca_partida_min='0.00',
                              partida_prevista='2021-01-01T10:00:00.000000', referencia='2021-01-01 00:00:00',
                              partida_real=r'\N', partida_atipica_flag='f', ano_origem='2021.0')], sem_flag=True)
        self.assertEqual(self.comparar()['status'], 'equivalentes')

    def test_presenca_por_origem(self):
        self.tratada(1, [dict(self.linha, linha_origem='3')])
        resultado = self.comparar()
        self.assertEqual((resultado['somente_etl'], resultado['somente_elt']), (1, 1))

    def test_rejeita_origem_duplicada(self):
        self.tratada(1, [self.linha, self.linha])
        with self.assertRaisesRegex(ValueError, 'Origem repetida no ELT'):
            self.comparar()

    def test_campos_ausentes_nao_comprovam_equivalencia(self):
        self.tratadas[1].write_text('arquivo_origem,linha_origem\nVRA_2021_01.csv,2\n')
        with self.assertRaisesRegex(ValueError, 'campos ausentes'):
            self.comparar()
