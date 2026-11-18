"""Baixa e verifica o recorte VRA usado na entrega validada."""
import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

from espaco_disco import exigir_espaco
from integrar_anac import ROOT, sha256_file

MANIFESTO = ROOT / 'dados/manifesto_vra.json'
BLOCO = 1024**2


def verificar(path, item):
    if path.stat().st_size != item['bytes'] or sha256_file(path) != item['sha256']:
        raise ValueError(f'Tamanho ou SHA-256 divergente do manifesto: {path}')


def baixar(url, path, item):
    path.parent.mkdir(parents=True, exist_ok=True)
    parcial = None
    try:
        with urlopen(url, timeout=60) as resposta:
            with NamedTemporaryFile(dir=path.parent, suffix='.part', delete=False) as saida:
                parcial = Path(saida.name)
                total = 0
                while bloco := resposta.read(BLOCO):
                    total += len(bloco)
                    if total > item['bytes']:
                        raise ValueError(f'Arquivo maior que a versão validada: {url}')
                    saida.write(bloco)
        verificar(parcial, item)
        if path.exists():
            verificar(path, item)
        else:
            parcial.replace(path)
    finally:
        if parcial is not None:
            parcial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destino', type=Path, default=ROOT / 'dados/brutos')
    parser.add_argument('--apenas-verificar', action='store_true',
                        help='Verifica os 36 arquivos locais sem usar a rede')
    args = parser.parse_args()

    manifesto = json.loads(MANIFESTO.read_text(encoding='utf-8'))
    faltantes = []
    total = 0
    try:
        for item in manifesto['arquivos']:
            ano, nome = item['ano_origem'], item['arquivo_origem']
            path = args.destino / str(ano) / nome
            if path.exists():
                verificar(path, item)
                total += 1
                print(f'Conferido: {path}', flush=True)
            else:
                faltantes.append((f"{manifesto['fonte']}{ano}/{nome}", path, item))
        if args.apenas_verificar and faltantes:
            raise ValueError('Arquivos ausentes: ' + ', '.join(str(path) for _, path, _ in faltantes))
        if faltantes:
            exigir_espaco(args.destino, sum(item['bytes'] for _, _, item in faltantes),
                          'download dos CSVs VRA')
        for url, path, item in faltantes:
            # Reconfere o volume de cada ano, inclusive se houver montagem separada.
            exigir_espaco(path.parent, item['bytes'], 'download de ' + path.name)
            baixar(url, path, item)
            total += 1
            print(f'Baixado e conferido: {path}', flush=True)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'Verificação VRA interrompida: {error}\n')
    print(f'{total} CSVs conferidos por tamanho e SHA-256.')


if __name__ == '__main__':
    main()
