from tests.apoio_etl_2021 import CenarioETL, etl, registro


class Entrada2021(CenarioETL):
    def test_layouts_e_copias_byte_a_byte(self):
        self.mes(1, [registro(Codeshare='ETD/4375')], codeshare=True)
        resultado = self.executar(export_raw=True)
        self.assertEqual(resultado['resumo']['bruta'], 12)
        for original in self.entrada.iterdir():
            copia = self.saida / 'vra_bruta' / original.name
            self.assertEqual(original.read_bytes(), copia.read_bytes())
            self.assertEqual(etl.sha256_arquivo(original), etl.sha256_arquivo(copia))
        self.assertTrue((self.saida / 'vra_bruta.csv.gz').is_file())
        self.assertTrue((self.saida / 'vra_bruta' / 'manifesto_sha256.csv').is_file())

    def test_mes_somente_cabecalho(self):
        self.mes(4, [])
        self.assertEqual(self.executar()['resumo']['bruta'], 11)

    def test_arquivo_ausente(self):
        (self.entrada / 'VRA_2021_03.csv').unlink()
        with self.assertRaises(FileNotFoundError):
            self.executar()

    def test_cabecalhos_invalidos(self):
        for cabecalho in [list(reversed(etl.colunas_comuns)),
                          etl.colunas_comuns[:-1],
                          ['Codeshare'] + etl.colunas_comuns,
                          etl.colunas_comuns + ['Extra']]:
            with self.subTest(cabecalho=cabecalho):
                self.mes(1, [], cabecalho=cabecalho)
                with self.assertRaisesRegex(ValueError, 'Cabeçalho inválido'):
                    self.executar()
        (self.entrada / 'VRA_2021_01.csv').write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'Cabeçalho inválido'):
            self.executar()

    def test_largura_incorreta(self):
        for registro_csv in ['x;y\n', ';'.join(['x'] * 21) + '\n']:
            self.mes(1, [])
            with (self.entrada / 'VRA_2021_01.csv').open('a') as arquivo:
                arquivo.write(registro_csv)
            with self.assertRaisesRegex(ValueError, 'campos, encontrados'):
                self.executar()
