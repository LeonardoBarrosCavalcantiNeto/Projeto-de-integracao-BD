"""A reserva fica disponível mesmo após o pico estimado."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from espaco_disco import GIB, exigir_espaco


class EspacoDisco(unittest.TestCase):
    def test_bloqueia_quando_pico_invade_reserva(self):
        with patch('espaco_disco.shutil.disk_usage', return_value=SimpleNamespace(free=10*GIB-1)):
            with self.assertRaisesRegex(RuntimeError, '8 GiB de reserva'):
                exigir_espaco(Path.cwd() / 'saida_ainda_inexistente', 2*GIB, 'teste')

    def test_aceita_quando_pico_preserva_reserva(self):
        with patch('espaco_disco.shutil.disk_usage', return_value=SimpleNamespace(free=10*GIB)):
            exigir_espaco(Path.cwd(), 2*GIB, 'teste')
