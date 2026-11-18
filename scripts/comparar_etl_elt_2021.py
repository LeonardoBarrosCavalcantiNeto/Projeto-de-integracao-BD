#!/usr/bin/env python3
"""Compara inventários SHA-256 e valores por origem sem carregar as duas bases na RAM.

Aceita CSV UTF-8 (com ou sem BOM), separado por vírgula, opcionalmente gzip.
Datas, números, booleanos e nulos são normalizados; códigos e nomes continuam texto.
Um SQLite temporário mantém as chaves. Nenhum arquivo de entrada é modificado.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import json
from pathlib import Path
import re
import sqlite3
import sys
import tempfile

try:
    from .etl_vra_anac_2021 import colunas_canonicas
except ImportError:  # Execução direta: python scripts/comparar_etl_elt_2021.py
    from etl_vra_anac_2021 import colunas_canonicas

METRICAS = ['diferenca_partida_min', 'atraso_partida_min',
            'diferenca_chegada_min', 'atraso_chegada_min']
FLAGS = ['partida_atipica_flag', 'chegada_atipica_flag', 'partida_ano_diverge_flag']
CAMPOS = colunas_canonicas + ['ano_origem'] + METRICAS + FLAGS
NUMEROS = set(METRICAS + ['numero_assentos', 'ano_origem'])
DATAS_HORAS = {'partida_prevista', 'partida_real', 'chegada_prevista', 'chegada_real'}
NULOS = {'', 'NULL', 'null', 'None', 'NaN', 'NaT', '<NA>', r'\N'}
CHAVES = ['arquivo_origem', 'linha_origem']


def abrir_csv(caminho):
    caminho = Path(caminho)
    abrir = gzip.open if caminho.suffix == '.gz' else open
    return abrir(caminho, 'rt', encoding='utf-8-sig', newline='')


def inventario_hashes(caminho):
    hashes = {}
    with abrir_csv(caminho) as entrada:
        leitor = csv.DictReader(entrada)
        campos = leitor.fieldnames or []
        arquivo = 'arquivo_origem' if 'arquivo_origem' in campos else 'arquivo'
        if arquivo not in campos or 'sha256' not in campos:
            raise ValueError('Inventário deve ter arquivo/arquivo_origem e sha256.')
        for linha in leitor:
            nome, digest = linha[arquivo], linha['sha256'].strip().lower()
            if nome in hashes or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError(f'Inventário com arquivo repetido ou SHA-256 inválido: {nome}')
            hashes[nome] = digest
    esperados = {f'VRA_2021_{mes:02d}.csv' for mes in range(1, 13)}
    if set(hashes) != esperados:
        raise ValueError('O inventário deve identificar exatamente os 12 arquivos mensais de 2021.')
    return hashes


def normalizar(campo, valor):
    if valor is None or valor in NULOS:
        return None
    if campo in NUMEROS:
        try:
            numero = Decimal(valor)
            if not numero.is_finite():
                raise ValueError(f'Número não finito em {campo}.')
            return str(numero.normalize()) if numero else '0'
        except InvalidOperation as erro:
            raise ValueError(f'Número inválido em {campo}.') from erro
    if campo in FLAGS:
        if valor.lower() in {'true', 't', '1'}:
            return True
        if valor.lower() in {'false', 'f', '0'}:
            return False
        raise ValueError(f'Booleano inválido em {campo}.')
    if campo in DATAS_HORAS:
        try:
            return datetime.fromisoformat(valor).isoformat(timespec='microseconds')
        except ValueError:
            return datetime.strptime(valor, '%d/%m/%Y %H:%M').isoformat(timespec='microseconds')
    if campo == 'referencia':
        try:
            return date.fromisoformat(valor).isoformat()
        except ValueError:
            try:
                instante = datetime.fromisoformat(valor)
            except ValueError:
                instante = datetime.strptime(valor, '%d/%m/%Y %H:%M:%S')
            if instante.time().isoformat() != '00:00:00':
                raise ValueError('Referência com horário diferente de meia-noite.')
            return instante.date().isoformat()
    return valor  # Não converter numero_voo: os zeros à esquerda são significativos.


def ler_tratada(caminho, hashes):
    with abrir_csv(caminho) as entrada:
        leitor = csv.DictReader(entrada)
        campos = leitor.fieldnames or []
        obrigatorios = set(CHAVES + CAMPOS) - {'partida_ano_diverge_flag'}
        ausentes = obrigatorios - set(campos)
        if len(campos) != len(set(campos)) or ausentes:
            raise ValueError(f'Cabeçalho tratado inválido; campos ausentes: {sorted(ausentes)}')
        for linha in leitor:
            if None in linha or any(v is None for v in linha.values()):
                raise ValueError('Registro tratado com largura incorreta.')
            arquivo, numero = linha['arquivo_origem'], linha['linha_origem']
            try:
                numero = Decimal(numero)
                if not numero.is_finite() or numero != numero.to_integral_value() or numero < 2:
                    raise ValueError('linha_origem deve ser um inteiro >= 2.')
                numero = int(numero)
            except InvalidOperation as erro:
                raise ValueError('linha_origem inválida.') from erro
            if arquivo not in hashes:
                raise ValueError(f'Origem ausente do inventário: {arquivo}')
            valores = {c: normalizar(c, linha.get(c)) for c in CAMPOS}
            if 'partida_ano_diverge_flag' not in campos:
                # Campo derivado novo do ETL; o ELT pode exportar apenas seus componentes.
                partida, ano = valores['partida_prevista'], valores['ano_origem']
                valores['partida_ano_diverge_flag'] = (
                    None if partida is None or ano is None else int(partida[:4]) != Decimal(ano)
                )
            yield (arquivo, numero), valores


def comparar(inventario_etl, inventario_elt, tratada_etl, tratada_elt):
    """Retorna evidência completa de presença e valores; totais iguais não bastam."""
    hashes_etl, hashes_elt = inventario_hashes(inventario_etl), inventario_hashes(inventario_elt)
    arquivos_divergentes = [
        {'arquivo_origem': nome, 'sha256_etl': hashes_etl[nome], 'sha256_elt': hashes_elt[nome]}
        for nome in sorted(hashes_etl) if hashes_etl[nome] != hashes_elt[nome]
    ]
    contagem_etl = contagem_elt = somente_elt = divergentes = 0
    campos_divergentes = Counter()
    exemplos_valores, exemplos_somente_elt = [], []
    with tempfile.TemporaryDirectory(prefix='comparacao-vra-2021-') as temporario:
        with closing(sqlite3.connect(Path(temporario) / 'origens.sqlite')) as conexao, conexao:
            conexao.execute('CREATE TABLE etl (arquivo TEXT, linha INTEGER, valores TEXT, visto INTEGER DEFAULT 0, PRIMARY KEY (arquivo, linha)) WITHOUT ROWID')
            conexao.execute('CREATE TABLE elt (arquivo TEXT, linha INTEGER, PRIMARY KEY (arquivo, linha)) WITHOUT ROWID')
            for chave, valores in ler_tratada(tratada_etl, hashes_etl):
                try:
                    conexao.execute('INSERT INTO etl (arquivo, linha, valores) VALUES (?, ?, ?)',
                                    (*chave, json.dumps(valores, ensure_ascii=False)))
                except sqlite3.IntegrityError as erro:
                    raise ValueError(f'Origem repetida no ETL: {chave}') from erro
                contagem_etl += 1
            for chave, valores_elt in ler_tratada(tratada_elt, hashes_elt):
                try:
                    conexao.execute('INSERT INTO elt VALUES (?, ?)', chave)
                except sqlite3.IntegrityError as erro:
                    raise ValueError(f'Origem repetida no ELT: {chave}') from erro
                contagem_elt += 1
                origem = conexao.execute('SELECT valores FROM etl WHERE arquivo=? AND linha=?', chave).fetchone()
                if origem is None:
                    somente_elt += 1
                    if len(exemplos_somente_elt) < 20:
                        exemplos_somente_elt.append(dict(zip(CHAVES, chave)))
                    continue
                conexao.execute('UPDATE etl SET visto=1 WHERE arquivo=? AND linha=?', chave)
                valores_etl = json.loads(origem[0])
                diferencas = {c: {'etl': valores_etl[c], 'elt': valores_elt[c]}
                              for c in CAMPOS if valores_etl[c] != valores_elt[c]}
                if diferencas:
                    divergentes += 1
                    campos_divergentes.update(diferencas.keys())
                    if len(exemplos_valores) < 20:
                        exemplos_valores.append({**dict(zip(CHAVES, chave)), 'diferencas': diferencas})
            somente_etl = conexao.execute('SELECT count(*) FROM etl WHERE visto=0').fetchone()[0]
            exemplos_somente_etl = [dict(zip(CHAVES, row)) for row in conexao.execute(
                'SELECT arquivo, linha FROM etl WHERE visto=0 ORDER BY arquivo, linha LIMIT 20')]
    iguais = not (arquivos_divergentes or somente_etl or somente_elt or divergentes)
    return {
        'status': 'equivalentes' if iguais else 'divergentes', 'comparacao_executada': True,
        'executado_em_utc': datetime.now(timezone.utc).isoformat(),
        'hashes_entrada_equivalentes': not arquivos_divergentes,
        'arquivos_com_hash_divergente': arquivos_divergentes,
        'registros_etl': contagem_etl, 'registros_elt': contagem_elt,
        'somente_etl': somente_etl, 'somente_elt': somente_elt,
        'registros_com_valores_divergentes': divergentes,
        'divergencias_por_campo': dict(campos_divergentes),
        'exemplos_divergencias': exemplos_valores,
        'exemplos_somente_etl': exemplos_somente_etl, 'exemplos_somente_elt': exemplos_somente_elt,
        'campos_comparados': CAMPOS,
        'observacao': 'data_carga/pipeline/versao_contrato não entram na igualdade; flag anual é derivada se ausente no ELT.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for nome in ['inventario-etl', 'inventario-elt', 'tratada-etl', 'tratada-elt', 'output']:
        parser.add_argument('--' + nome, required=True, type=Path)
    args = parser.parse_args()
    try:
        resultado = comparar(args.inventario_etl, args.inventario_elt, args.tratada_etl, args.tratada_elt)
    except (ValueError, OSError, csv.Error) as erro:
        resultado = {'status': 'falhou', 'comparacao_executada': False, 'erro': str(erro)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado['status'] == 'equivalentes' else 1


if __name__ == '__main__':
    sys.exit(main())
