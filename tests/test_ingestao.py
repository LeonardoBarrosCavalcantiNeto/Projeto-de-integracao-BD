"""Casos de ingestão que as contagens dos CSVs reais não cobrem."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from integrar_anac import preparar, ORIGINAIS


class Ingestao(unittest.TestCase):
    def fixture(self, base):
        inputs={}
        for year in [2019,2020]:
            directory=base/str(year);directory.mkdir();inputs[year]=directory
            for month in range(1,13):
                with (directory/f'VRA_{year}_{month:02d}.csv').open('w',encoding='utf-8-sig',newline='') as h:
                    writer=csv.writer(h,delimiter=';');writer.writerow(ORIGINAIS)
                    if month==1:
                        row=['']*20;row[0]=' AZU ';row[1]='Nome\ncom quebra';row[2]='0035';row[3]='\\N';row[16]='NULL'
                        writer.writerow(row);writer.writerow(row)
        return inputs

    def test_preserva_campos_e_registro_logico(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);inputs=self.fixture(base);out=preparar(inputs,base/'bundle')
            with (out/'raw_2019.csv').open(newline='') as h:rows=list(csv.reader(h))
            self.assertEqual([r[-2] for r in rows],['2','3'])
            self.assertEqual(rows[0][1:5],[' AZU ','Nome\ncom quebra','0035','\\N'])
            self.assertEqual(rows[0][17],'NULL')
            self.assertEqual(rows[0][5],'')
            manifest=json.loads((out/'manifesto.json').read_text())
            self.assertEqual(len(manifest['arquivos']),24)
            self.assertEqual(manifest['arquivos'][0]['registros_multilinha'],2)

    def test_mes_ausente_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);inputs=self.fixture(base)
            (inputs[2020]/'VRA_2020_12.csv').unlink()
            with self.assertRaises(ValueError):preparar(inputs,base/'bundle')

    def test_cabecalho_alterado_aborta(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);inputs=self.fixture(base)
            (inputs[2019]/'VRA_2019_01.csv').write_text('cabecalho;errado\n')
            with self.assertRaises(ValueError):preparar(inputs,base/'bundle')

if __name__=='__main__':unittest.main()
