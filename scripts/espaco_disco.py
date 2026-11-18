"""Pré-verificação de armazenamento para operações pesadas do projeto."""
import shutil
from pathlib import Path

GIB = 1024**3
RESERVA = 8 * GIB


def existente(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    return path


def exigir_espaco(path, pico_estimado, operacao):
    destino = existente(path)
    livre = shutil.disk_usage(destino).free
    necessario = RESERVA + pico_estimado
    if livre < necessario:
        raise RuntimeError(
            f'Espaço insuficiente para {operacao} em {destino}: '
            f'{livre/GIB:.2f} GiB livres, {necessario/GIB:.2f} GiB necessários '
            f'({pico_estimado/GIB:.2f} GiB estimados e 8 GiB de reserva).'
        )
