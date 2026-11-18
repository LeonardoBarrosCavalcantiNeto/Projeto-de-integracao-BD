"""Regressão da geração dos SQLs anuais."""
import contextlib
import csv
import hashlib
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from integrar_anac import ORIGINAIS, preparar
from integracao_final import remap


class TemplateElt(unittest.TestCase):
    def test_sql_anual_corresponde_aos_hashes_de_referencia(self):
        # 2019/2020: antes da parametrização. 2021: após a correção da auditoria.
        references = {
            2019: ('03_transformar_2019.sql', 'e0819a46f337ed7e8cac879b0eaf8b96cbab9a1afefba0604321fd9a9ab181a6'),
            2020: ('04_transformar_2020.sql', 'f6a81073ab99a4c678e82109197ff74be0e8e50fe41b5b82812187d2ed21550b'),
            2021: ('04b_transformar_2021.sql', 'b686cda775ceb34b2cb12ff2dac15422348b069b6c56d798227050c5349d924f'),
        }
        with tempfile.TemporaryDirectory(prefix='anac_template_test_') as temporary:
            base = Path(temporary)
            inputs = {}
            for year in references:
                directory = base / str(year)
                directory.mkdir()
                inputs[year] = directory
                for month in range(1, 13):
                    with (directory / f'VRA_{year}_{month:02d}.csv').open('w', encoding='utf-8-sig', newline='') as stream:
                        csv.writer(stream, delimiter=';').writerow(ORIGINAIS)
            with contextlib.redirect_stdout(io.StringIO()):
                preparar(inputs, base / 'bundle')
            for year, (filename, expected) in references.items():
                with self.subTest(year=year):
                    generated = remap((base / 'bundle/manual' / filename).read_text(encoding='utf-8'), 'elt').encode('utf-8')
                    self.assertEqual(hashlib.sha256(generated).hexdigest(), expected)
                    sql = generated.decode('utf-8')
                    self.assertIsNone(re.search(r'__[A-Z_]+__', sql))
                    self.assertIn(f'raw.voos_{year}', sql)
                    self.assertIn(f'{year}::INTEGER AS ano_origem', sql)
                    self.assertIn(f'REFERENCIA_FORA_DE_{year}', sql)
                    if year == 2019:
                        self.assertNotIn('2020', sql)
