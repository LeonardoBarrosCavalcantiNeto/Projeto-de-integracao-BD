import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from baixar_vra import MANIFESTO, baixar, verificar


class DownloadVra(unittest.TestCase):
    def test_manifesto_cobre_os_36_meses_da_entrega(self):
        manifesto = json.loads(MANIFESTO.read_text(encoding='utf-8'))
        referencia = MANIFESTO.parents[1] / 'resultados/validacoes/integracao_final/fontes_inalteradas.json'
        auditados = json.loads(referencia.read_text(encoding='utf-8'))['arquivos']
        self.assertEqual(
            [(item['ano_origem'], item['arquivo_origem'], item['sha256'])
             for item in manifesto['arquivos']],
            [(item['ano'], item['arquivo'], item['sha256']) for item in auditados],
        )
        self.assertEqual(
            [item['arquivo_origem'] for item in manifesto['arquivos']],
            [f'VRA_{ano}_{mes:02}.csv' for ano in (2019, 2020, 2021) for mes in range(1, 13)],
        )

    def test_publica_so_arquivos_integros_e_preserva_destino(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fonte = base / 'fonte.csv'
            destino = base / '2019' / 'VRA_2019_01.csv'
            fonte.write_bytes(b'original\r\n')
            item = dict(bytes=fonte.stat().st_size, sha256=hashlib.sha256(fonte.read_bytes()).hexdigest())

            for invalido in (b'diferente\n', b'curto', b'arquivo muito maior'):
                original = fonte.read_bytes()
                fonte.write_bytes(invalido)
                with self.assertRaises(ValueError):
                    baixar(fonte.as_uri(), destino, item)
                self.assertEqual(list(destino.parent.iterdir()), [])
                fonte.write_bytes(original)

            baixar(fonte.as_uri(), destino, item)
            verificar(destino, item)
            destino.write_bytes(b'preservar\n')
            with self.assertRaises(ValueError):
                baixar(fonte.as_uri(), destino, item)
            self.assertEqual(destino.read_bytes(), b'preservar\n')
            self.assertEqual(list(destino.parent.iterdir()), [destino])
