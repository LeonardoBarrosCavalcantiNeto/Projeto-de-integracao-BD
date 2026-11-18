#!/usr/bin/env python3
"""Valida os guias e um bundle final preparado, sem conectar ao PostgreSQL."""
import argparse
import ast
import json
import re
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path
from urllib.parse import unquote, urlsplit

from integrar_anac import ROOT, sha256_file

GUIDES = [
    'README.md',
    'documentacao/INTEGRACAO_FINAL.md',
    'documentacao/REPRODUCAO_MULTIPLATAFORMA.md',
]
MANUAL_STEPS = (
    '01_raw.sql 02_importar_raw.psql 03_transformar_2019.sql '
    '04_transformar_2020.sql 04b_transformar_2021.sql 05_consolidar_staging.sql '
    '06_criar_dw.sql 07_dimensoes.sql 08_carga_dw.sql 09_validar_contrato.sql '
    '10_analises.sql 11_diagnosticos.sql'
).split()


def check_guides(errors):
    help_text = {}
    for name in GUIDES:
        doc = ROOT / name
        source = doc.read_text(encoding='utf-8')
        prose = re.sub(r'^[ \t]*```[^\n]*\n.*?^[ \t]*```[^\n]*', '', source, flags=re.M | re.S)
        for link in re.findall(r'\]\(([^)]+)\)', prose):
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            target = doc.parent / unquote(url.path) if url.path else doc
            if not target.exists():
                errors.append(f'{name}: link ausente {link}')
            elif url.fragment and target.suffix == '.md':
                headings = re.findall(r'^#{1,6}\s+(.+)$', target.read_text(encoding='utf-8'), re.M)
                anchors = {re.sub(r'[^\w -]', '', h.lower()).replace(' ', '-') for h in headings}
                if unquote(url.fragment) not in anchors:
                    errors.append(f'{name}: âncora ausente {link}')
        for ref in set(re.findall(r'(?<![\w/])(?:scripts|sql|tests)/[\w./-]+\.(?:py|sql)\b', source)):
            if not (ROOT / ref).is_file():
                errors.append(f'{name}: caminho ausente {ref}')
        blocks = re.findall(r'^[ \t]*```(bash|text|python)\n(.*?)\n[ \t]*```', source, re.S | re.M)
        bash_count = 0
        for index, (language, block) in enumerate(blocks, 1):
            if language == 'python':
                ast.parse(textwrap.dedent(block), filename=f'{name}, bloco {index}')
                continue
            if language == 'bash':
                bash_count += 1
                check = subprocess.run(['bash', '-n'], input=textwrap.dedent(block), text=True, capture_output=True)
                if check.returncode:
                    errors.append(f'{name}, bloco Bash {index}: {check.stderr.strip()}')
            for line in block.replace(chr(92) + '\n', ' ').splitlines():
                if not re.match(r'^\s*(?:\.venv/bin/)?python(?:3(?:\.\d+)?)?\s+', line):
                    continue
                command = shlex.split(line, comments=True)
                if len(command) > 2 and command[1] == '-c':
                    ast.parse(command[2])
                if not command[1].startswith('scripts/') or not (ROOT / command[1]).is_file():
                    continue
                script = command[1]
                if script not in help_text:
                    help_text[script] = subprocess.check_output(
                        [sys.executable, str(ROOT / script), '--help'], text=True, cwd=ROOT
                    )
                options = set(re.findall(r'--[\w-]+', help_text[script]))
                invalid = {arg.split('=')[0] for arg in command[2:] if arg.startswith('--')} - options
                if invalid:
                    errors.append(f'{name}: opções ausentes em {script}: {sorted(invalid)}')
                if script == 'scripts/integracao_final.py':
                    modes = re.search(r'\{(prepare,[^{}]+)\}', help_text[script])
                    if not modes or len(command) < 3 or command[2] not in modes[1].split(','):
                        errors.append(f'{name}: subcomando inválido em {line.strip()}')
        print(f'{name}: {bash_count} blocos Bash conferidos')


def check_bundle(bundle, errors):
    manifest = json.loads((bundle / 'manifesto_final.json').read_text(encoding='utf-8'))
    canonical = manifest['fontes']
    if canonical != json.loads((bundle / 'elt/manifesto.json').read_text(encoding='utf-8')):
        errors.append('Inventário canônico divergente do manifesto final.')
    expected_sources = {(y, f'VRA_{y}_{m:02}.csv') for y in (2019, 2020, 2021) for m in range(1, 13)}
    sources = [(item['ano_origem'], item['arquivo_origem']) for item in canonical['arquivos']]
    if len(sources) != len(expected_sources) or set(sources) != expected_sources:
        errors.append('O inventário deve conter os 36 CSVs mensais, sem repetições.')
    checks = [
        (ROOT, manifest['codigo']),
        (ROOT, canonical['fontes_codigo_sha256']),
        (bundle, manifest['saidas']),
        (bundle / 'elt', {**canonical['raw_sha256'], 'carga.sql': canonical['bundle_sha256']}),
    ]
    for root, hashes in checks:
        for name, expected in hashes.items():
            path = root / name
            if not path.is_file() or sha256_file(path) != expected:
                errors.append(f'Hash divergente ou arquivo ausente: {path}')
    print(f'{sum(len(hashes) for _, hashes in checks)} verificações de SHA-256')
    manual = bundle / 'elt/manual'
    if sorted(path.name for path in manual.iterdir()) != MANUAL_STEPS:
        errors.append('O bundle deve conter as 12 etapas manuais finais em ordem.')
        return
    guide = (ROOT / GUIDES[1]).read_text(encoding='utf-8')
    documented = re.findall(r'`([\w]+\.(?:sql|psql))`', guide.split('## Demonstração manual')[1].split('\n## ')[0])
    if [name for name in documented if name in MANUAL_STEPS] != MANUAL_STEPS:
        errors.append('A ordem manual documentada diverge do bundle final.')
    # manual_sha256 descreve o SQL canônico anterior ao remapeamento dos schemas.
    for name in MANUAL_STEPS:
        sql = (manual / name).read_text(encoding='utf-8')
        commands = re.findall(r'^\s*(\\\w+)', sql, re.M)
        expected = [r'\copy'] * 3 if name.endswith('.psql') else []
        if commands != expected:
            errors.append(f'Metacomandos inesperados em {name}: {commands}')
        if '_transformar_' in name:
            year = name[-8:-4]
            if f'raw.voos_{year}' not in sql or f'staging_elt.vra_tratada_{year}' not in sql:
                errors.append(f'Origem ou destino anual inesperado em {name}')
    for name, schema in [('01_elt.psql', 'dw_elt'), ('02_etl.psql', 'dw_etl')]:
        sql = (bundle / name).read_text(encoding='utf-8')
        if f'CREATE SCHEMA {schema};' not in sql or f'INSERT INTO {schema}.fato_voo' not in sql:
            errors.append(f'Schema ou carga dimensional ausente em {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=ROOT / '.local/final')
    args = parser.parse_args()
    errors = []
    try:
        check_guides(errors)
        check_bundle(args.bundle, errors)
    except (OSError, ValueError, KeyError, IndexError, SyntaxError, subprocess.CalledProcessError) as error:
        errors.append(str(error))
    if errors:
        parser.exit(1, '\n'.join(errors) + '\n')
    print('Guias e bundle final verificados.')


if __name__ == '__main__':
    main()
