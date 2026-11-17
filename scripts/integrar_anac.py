#!/usr/bin/env python3
"""Ingestão canônica 2019/2020. Biblioteca padrão + ferramentas PostgreSQL.

prepare gera bundle local; apply exige backup restaurado antes de migrar schemas.
IDs históricos não são associados artificialmente às novas ocorrências.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAIS = ['Sigla ICAO Empresa Aérea','Empresa Aérea','Número Voo','Código DI',
 'Código Tipo Linha','Modelo Equipamento','Número de Assentos',
 'Sigla ICAO Aeroporto Origem','Descrição Aeroporto Origem','Partida Prevista',
 'Partida Real','Sigla ICAO Aeroporto Destino','Descrição Aeroporto Destino',
 'Chegada Prevista','Chegada Real','Situação Voo','Justificativa','Referência',
 'Situação Partida','Situação Chegada']


def sha256_file(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def preparar(inputs, output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'versao_contrato': '1.1', 'gerado_em': datetime.now(timezone.utc).isoformat(), 'arquivos': []}
    statements = ['BEGIN;', "SELECT pg_advisory_xact_lock(20192020);",
                  'CREATE SCHEMA raw;', 'CREATE SCHEMA staging;', 'CREATE SCHEMA dw;',
                  'CREATE TABLE raw.inventario (ano_origem integer, arquivo_origem text, registros bigint, bytes bigint, sha256 text, PRIMARY KEY(ano_origem,arquivo_origem));']
    for year, directory in sorted(inputs.items()):
        files = sorted(Path(directory).glob('*.csv'))
        expected = [f'VRA_{year}_{month:02d}.csv' for month in range(1, 13)]
        if [f.name for f in files] != expected:
            raise ValueError(f'{year}: esperados exatamente os 12 CSVs mensais: {expected}')
        raw_csv = output / f'raw_{year}.csv'
        raw_id = 0
        with raw_csv.open('w', encoding='utf-8', newline='') as target:
            writer = csv.writer(target, quoting=csv.QUOTE_ALL, lineterminator='\n')
            for file in files:
                before = sha256_file(file)
                count = multiline = 0
                with file.open(encoding='utf-8-sig', newline='') as source:
                    reader = csv.reader(source, delimiter=';', strict=True)
                    if next(reader, None) != ORIGINAIS:
                        raise ValueError(f'Cabeçalho divergente: {file.name}')
                    physical = reader.line_num
                    for logical, row in enumerate(reader, 2):
                        if len(row) != 20 or any('\x00' in field for field in row):
                            raise ValueError(f'CSV inválido: {file.name}, registro {logical}')
                        multiline += reader.line_num - physical > 1
                        physical = reader.line_num
                        raw_id += 1
                        count += 1
                        writer.writerow([raw_id] + row + [file.name, logical, year])
                after = sha256_file(file)
                if before != after:
                    raise ValueError(f'Arquivo mudou durante a leitura: {file}')
                item = dict(ano_origem=year, arquivo_origem=file.name, registros=count,
                            bytes=file.stat().st_size, sha256=before, registros_multilinha=multiline)
                manifest['arquivos'].append(item)
                statements.append(f'INSERT INTO raw.inventario VALUES ({year},{literal(file.name)},{count},{item["bytes"]},{literal(before)});')
                print(year, file.name, count, flush=True)
        columns = ','.join(identifier(c) + ' TEXT NOT NULL' for c in ORIGINAIS)
        statements += [f'CREATE TABLE raw.voos_{year} (id_raw BIGINT PRIMARY KEY,{columns}, arquivo_origem TEXT NOT NULL, linha_origem BIGINT NOT NULL CHECK(linha_origem>=2), ano_origem INTEGER NOT NULL CHECK(ano_origem={year}), UNIQUE(ano_origem,id_raw), UNIQUE(arquivo_origem,linha_origem));',
                       f"\\copy raw.voos_{year} FROM {literal(raw_csv)} WITH (FORMAT CSV, NULL '\\N')"]
        template = (ROOT/'sql/transformacoes/elt_2020.sql').read_text()
        template = template.replace('elt_2020.', 'staging.').replace('2020', str(year))
        template = template.replace('arquivo_origem, linha_origem, '+str(year)+'::INTEGER AS ano_origem', 'id_raw, arquivo_origem, linha_origem, '+str(year)+'::INTEGER AS ano_origem')
        # Os brutos são compartilhados por contrato; intermediárias recebem sufixo anual.
        template = template.replace('staging.vra_bruta', f'raw.voos_{year}')
        tables = ['vra_duplicatas_excluidas','vra_classificada','vra_convertida','vra_avaliada',
                  'vra_rejeicoes','vra_tratada','vra_anomalias','resumo_qualidade']
        for table in tables:
            template = template.replace('staging.'+table, f'staging.{table}_{year}')
        statements.append(template)
        statements.append(f'CREATE VIEW staging.vra_{year} AS SELECT * FROM staging.vra_convertida_{year};')
    years = sorted(inputs)
    for table in ['vra_duplicatas_excluidas', 'vra_rejeicoes', 'vra_tratada', 'vra_anomalias']:
        statements.append('CREATE TABLE staging.'+table+' AS '+' UNION ALL '.join(f'SELECT '+('*, '+str(y)+'::integer AS ano_origem' if table=='vra_anomalias' else '*')+f' FROM staging.{table}_{y}' for y in years)+';')
        if table != 'vra_anomalias':
            statements += [f'ALTER TABLE staging.{table} ADD PRIMARY KEY (ano_origem,id_raw);',
                           f'ALTER TABLE staging.{table} ADD UNIQUE (ano_origem,arquivo_origem,linha_origem);']
    statements.append('CREATE VIEW staging.resumo_qualidade AS '+' UNION ALL '.join(f'SELECT {y}::integer ano_origem,* FROM staging.resumo_qualidade_{y}' for y in years)+';')
    # Chave global da origem e auditorias referenciadas a RAW unificada, sem perder IDs locais.
    statements.append('CREATE TABLE raw.ocorrencias (ano_origem integer, id_raw bigint, arquivo_origem text NOT NULL, linha_origem bigint NOT NULL, PRIMARY KEY(ano_origem,id_raw), UNIQUE(ano_origem,arquivo_origem,linha_origem));')
    for year in years:
        statements.append(f'INSERT INTO raw.ocorrencias SELECT ano_origem,id_raw,arquivo_origem,linha_origem FROM raw.voos_{year};')
    for table in ['vra_duplicatas_excluidas','vra_rejeicoes','vra_tratada']:
        statements.append(f'ALTER TABLE staging.{table} ADD FOREIGN KEY(ano_origem,id_raw) REFERENCES raw.ocorrencias;')
    ddl = (ROOT/'sql/database/10_criacao_dw.sql').read_text().replace('id_raw BIGINT NOT NULL UNIQUE', 'id_raw BIGINT NOT NULL')
    ddl = ddl.replace('arquivo_origem TEXT,', 'arquivo_origem TEXT NOT NULL,').replace('linha_origem BIGINT,','linha_origem BIGINT NOT NULL,')
    statements += [ddl, 'ALTER TABLE dw.fato_voo ADD UNIQUE(ano_origem,id_raw);',
                   'ALTER TABLE dw.fato_voo ADD UNIQUE(ano_origem,arquivo_origem,linha_origem);',
                   'ALTER TABLE dw.fato_voo ADD FOREIGN KEY(ano_origem,id_raw) REFERENCES staging.vra_tratada;']
    statements.append((ROOT/'sql/integracao/02_dimensoes.sql').read_text())
    statements.append((ROOT/'sql/integracao/03_carga_dw.sql').read_text())
    statements.append((ROOT/'sql/integracao/04_validar.sql').read_text())
    statements.append((ROOT/'sql/integracao/06_casos_limite.sql').read_text())
    statements.append((ROOT/'sql/integracao/08_restricoes.sql').read_text())
    statements.append('COMMIT;')
    (output/'carga.sql').write_text('\n'.join(statements), encoding='utf-8')
    manifest['fontes_codigo_sha256'] = {str(f.relative_to(ROOT)): sha256_file(f) for f in [Path(__file__), ROOT/'sql/transformacoes/elt_2020.sql', ROOT/'sql/database/10_criacao_dw.sql', *sorted((ROOT/'sql/integracao').glob('*.sql'))]}
    manifest['bundle_sha256'] = hashlib.sha256((output/'carga.sql').read_bytes()).hexdigest()
    manifest['raw_sha256'] = {f.name: sha256_file(f) for f in output.glob('raw_*.csv')}
    (output/'manifesto.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return output


def psql(query=None, file=None, database=None):
    cmd = ['psql','-X','-w','-v','ON_ERROR_STOP=1']
    if database:
        cmd += ['-d',database]
    cmd += ['-At','-c',query] if query is not None else ['-f',str(file)]
    return subprocess.run(cmd, check=True, text=True, capture_output=True).stdout


LEGADO = ['sigla_icao_empresa_aerea','empresa_aerea','numero_voo','codigo_di',
 'codigo_tipo_linha','modelo_equipamento','numero_assentos','sigla_icao_aeroporto_origem',
 'descricao_aeroporto_origem','partida_prevista','partida_real','sigla_icao_aeroporto_destino',
 'descricao_aeroporto_destino','chegada_prevista','chegada_real','situacao_voo',
 'justificativa','referencia','situacao_partida','situacao_chegada']


def reconciliar_legado(stamp):
    statements = ['CREATE TABLE staging.reconciliacao_historica (ano_origem integer PRIMARY KEY, registros_legado bigint, registros_csv bigint, diferencas_multiconjunto bigint, politica text);']
    for year in [2019,2020]:
        columns=psql(f"SELECT column_name FROM information_schema.columns WHERE table_schema='raw' AND table_name='voos_{year}' ORDER BY ordinal_position").splitlines()
        if not columns:
            continue
        available=set(columns)
        names=[]
        for original, legacy in zip(ORIGINAIS,LEGADO):
            name=original if original in available else legacy
            if name not in available:
                raise ValueError(f'Coluna histórica não reconhecida em {year}: {legacy}. Nenhum schema foi alterado.')
            names.append(name)
        old=','.join('coalesce('+identifier(c)+",'')" for c in names)
        new=','.join('coalesce('+identifier(c)+",'')" for c in ORIGINAIS)
        table=f'raw_antes_{stamp}.voos_{year}'
        statements.append(f"""INSERT INTO staging.reconciliacao_historica SELECT {year},
 (SELECT count(*) FROM {table}), (SELECT count(*) FROM raw.voos_{year}),
 (SELECT count(*) FROM ((SELECT {old} FROM {table} EXCEPT ALL SELECT {new} FROM raw.voos_{year})
 UNION ALL (SELECT {new} FROM raw.voos_{year} EXCEPT ALL SELECT {old} FROM {table})) d),
 '20 campos exatos; NULL histórico comparado a vazio; IDs não associados';""")
    statements.append("DO $$ BEGIN IF EXISTS(SELECT FROM staging.reconciliacao_historica WHERE diferencas_multiconjunto<>0) THEN RAISE EXCEPTION 'RAW histórico diverge dos CSVs. Migração cancelada; backup e restauração preservados.'; END IF; END $$;")
    return '\n'.join(statements)


def aplicar(bundle, backup_dir):
    bundle = Path(bundle).resolve()
    manifest = json.loads((bundle/'manifesto.json').read_text())
    for name, expected in {**manifest['raw_sha256'], 'carga.sql':manifest['bundle_sha256']}.items():
        if sha256_file(bundle/name) != expected:
            raise ValueError(f'Bundle alterado: {name}')
    # Todas as ferramentas usam a mesma conexão PG*; não imprimir credenciais.
    db = psql('SELECT current_database()').strip()
    if db != 'anac_dw' and not db.startswith('anac_teste_'):
        raise ValueError('Destino permitido: anac_dw ou anac_teste_*. Configure PGDATABASE.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    backup_dir = Path(backup_dir).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    dump = backup_dir/f'{db}_{stamp}.dump'
    subprocess.run(['pg_dump','-w','-Fc','-d',db,'-f',str(dump)],check=True, capture_output=True)
    os.chmod(dump, 0o600)
    if not dump.stat().st_size:
        raise RuntimeError('Backup vazio')
    subprocess.run(['pg_restore','--list',str(dump)],check=True,capture_output=True)
    temp = f'anac_teste_restore_{stamp}'
    subprocess.run(['createdb','-w',temp],check=True,capture_output=True)
    # Não apagar o banco temporário: fica disponível para recuperação e inspeção.
    subprocess.run(['pg_restore','-w','--exit-on-error','--dbname',temp,str(dump)],check=True,capture_output=True)
    reconciliation = reconciliar_legado(stamp)
    existing = psql("SELECT nspname FROM pg_namespace WHERE nspname IN ('raw','staging','dw') ORDER BY 1").split()
    rename = '\n'.join(f'ALTER SCHEMA {s} RENAME TO {s}_antes_{stamp};' for s in existing)
    sqlfile = bundle/'aplicar.sql'
    sqlfile.write_text((bundle/'carga.sql').read_text().replace('CREATE SCHEMA raw;',rename+'\nCREATE SCHEMA raw;',1).replace('COMMIT;', reconciliation+'\nCOMMIT;'))
    report = dict(database=db, backup=str(dump), backup_sha256=sha256_file(dump),
                  restauracao_testada=temp, schemas_preservados=[s+'_antes_'+stamp for s in existing], status='backup_restaurado')
    reportfile = backup_dir/f'{db}_{stamp}.json'
    reportfile.write_text(json.dumps(report,indent=2)+'\n')
    # Registrar backup ANTES de iniciar migração. ON_ERROR_STOP + transação fazem rollback.
    psql(file=sqlfile)
    report['status']='integracao_confirmada'
    report['contagens']=psql('SELECT ano_origem,count(*) FROM dw.fato_voo GROUP BY 1 ORDER BY 1')
    reportfile.write_text(json.dumps(report,indent=2)+'\n')
    (bundle/'validacao.txt').write_text(psql(file=ROOT/'sql/integracao/04_validar.sql'))
    (bundle/'analises.txt').write_text(psql(file=ROOT/'sql/integracao/05_analises.sql'))
    # Reexecução da carga com mesmas chaves, conferida por asserções SQL.
    psql(query='BEGIN;\n'+(ROOT/'sql/integracao/03_carga_dw.sql').read_text()+'\n'+(ROOT/'sql/integracao/04_validar.sql').read_text()+'\nCOMMIT;')
    print(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare')
    p.add_argument('--dados-2019',type=Path,required=True)
    p.add_argument('--dados-2020',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'.local/integracao/bundle')
    p=sub.add_parser('apply')
    p.add_argument('--bundle',type=Path,default=ROOT/'.local/integracao/bundle')
    p.add_argument('--backup-dir',type=Path,default=ROOT/'backups')
    args=parser.parse_args()
    if args.command=='prepare':
        print(preparar({2019:args.dados_2019,2020:args.dados_2020},args.output))
    else:
        aplicar(args.bundle,args.backup_dir)

if __name__=='__main__':
    main()
