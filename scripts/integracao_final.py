#!/usr/bin/env python3
"""Integração final: reutiliza ingestão/SQL canônicos e conversores Pandas do ETL 2021.

prepare gera etapas SQL/psql; isolated executa em cluster novo sem sockets.
Nunca abre nem modifica o PostgreSQL nativo ou containers.
"""
import argparse
import csv
import json
import re
import subprocess
from pathlib import Path
from integrar_anac import ROOT, ORIGINAIS, preparar, caminho_copy, identifier, sha256_file
from testar_integracao_isolada import executar
from espaco_disco import GIB, exigir_espaco

YEARS = (2019, 2020, 2021)
META = ['arquivo_origem', 'linha_origem', 'ano_origem', 'id_raw']
MEASURES = ['diferenca_partida_min','diferenca_chegada_min','atraso_partida_min',
            'atraso_chegada_min','partida_atipica_flag','chegada_atipica_flag']


def remap(sql, flow):
    return sql.replace('staging.',f'staging_{flow}.').replace("'dw'::regnamespace",f"'dw_{flow}'::regnamespace").replace('dw.',f'dw_{flow}.')


def dimension_sql(flow):
    sql=(ROOT/'sql/integracao/02_dimensoes.sql').read_text(encoding='utf-8')
    extension=(ROOT/'sql/integracao/02_resolver_descricoes_final.sql').read_text(encoding='utf-8')
    sql=sql.replace('DO $$ BEGIN',extension+'\nDO $$ BEGIN',1)
    sql=sql.replace('SELECT aeroporto_icao,max(descricao_resolvida) descricao_aeroporto\nFROM staging.aeroportos_resolvidos GROUP BY aeroporto_icao;',
        "SELECT codigo aeroporto_icao,descricao descricao_aeroporto FROM staging.snapshot_descricoes WHERE dimensao='aeroporto';")
    return remap(sql,flow)


def load_sql(flow):
    sql=remap((ROOT/'sql/integracao/03_carga_dw.sql').read_text(encoding='utf-8'),flow)
    if flow=='etl':
        sql=sql.replace("'ELT'", "'ETL'")
        sql=sql.replace("CASE\n        WHEN v.diferenca_partida_min IS NOT NULL\n        THEN GREATEST(v.diferenca_partida_min, 0)\n        ELSE NULL\n    END", "v.atraso_partida_min")
        sql=sql.replace("CASE\n        WHEN v.diferenca_chegada_min IS NOT NULL\n        THEN GREATEST(v.diferenca_chegada_min, 0)\n        ELSE NULL\n    END", "v.atraso_chegada_min")
        sql=sql.replace('COALESCE(ABS(v.diferenca_partida_min) > 1440, FALSE)', 'v.partida_atipica_flag')
        sql=sql.replace('COALESCE(ABS(v.diferenca_chegada_min) > 1440, FALSE)', 'v.chegada_atipica_flag')
    sql=re.sub(r"SELECT\s+BTRIM\(companhia_icao\),\s+MAX\(NULLIF\(BTRIM\(companhia_nome\), ''\)\)\s+FROM staging_"+flow+r"\.vra_tratada\s+WHERE NULLIF\(BTRIM\(companhia_icao\), ''\) IS NOT NULL\s+GROUP BY BTRIM\(companhia_icao\)",
        f"SELECT codigo,descricao FROM staging_{flow}.snapshot_descricoes WHERE dimensao='companhia'",sql)
    return sql


def write_csv_rows(columns, rows, path):
    import pandas as pd
    with Path(path).open('w',encoding='utf-8',newline='') as target:
        csv.writer(target,lineterminator='\n').writerow(columns)
        for row in rows:
            target.write(','.join('\\N' if pd.isna(v) else '"'+str(v).replace('"','""')+'"' for v in row)+'\n')


def export_csv(frame, path):
    write_csv_rows(frame.columns,frame.itertuples(index=False,name=None),path)


def exact_duplicate_stats(duplicates, original):
    groups=len(duplicates[['arquivo_preservado','linha_preservada']].drop_duplicates())
    invalid=0
    if len(duplicates):
        normalized=original.padronizar_textos(duplicates)
        converted=original.converter_tipos(normalized)
        invalid=int(original.motivos_obrigatorios(normalized,converted).map(bool).sum())
    return dict(grupos_duplicados=groups,linhas_envolvidas_duplicatas=len(duplicates)+groups,
                intersecao_excedentes_invalidos=invalid)


def duplicate_stats(raw, duplicates, text, original, output):
    candidates=text.duplicated(original.colunas_canonicas,keep=False)
    audit=text.loc[candidates].copy()
    audit['id_raw']=raw.loc[audit.index,'id_raw']
    export_csv(audit,output/'vra_duplicatas_apos_padronizacao.csv')
    return dict(exact_duplicate_stats(duplicates,original),
        grupos_apos_padronizacao=len(text.loc[candidates].drop_duplicates(original.colunas_canonicas)),
        linhas_envolvidas_apos_padronizacao=int(candidates.sum()),
        excedentes_apos_padronizacao=int(text.duplicated(original.colunas_canonicas).sum()))


def etl(year, directory, output):
    """Transformações exclusivamente Pandas. Origem atribuída antes do tratamento."""
    import pandas as pd
    import etl_vra_anac_2021 as original
    original.ano_origem = year
    output.mkdir(parents=True, exist_ok=True)
    files = sorted(Path(directory).glob('*.csv'))
    if [f.name for f in files] != [f'VRA_{year}_{m:02}.csv' for m in range(1,13)]:
        raise ValueError(f'Arquivos mensais incompletos: {year}')
    parts, inventory = [], []
    for file in files:
        before = sha256_file(file)
        with file.open(encoding='utf-8-sig', newline='') as source:
            reader = csv.reader(source, delimiter=';', strict=True)
            header = next(reader)
            if header not in [ORIGINAIS, ORIGINAIS+['Codeshare']]:
                raise ValueError(f'Cabeçalho inesperado: {file}')
            rows = []
            for logical, row in enumerate(reader,2):
                if len(row)!=len(header) or any('\x00' in v for v in row):
                    raise ValueError(f'Registro inválido: {file}:{logical}')
                rows.append(row)
        frame = pd.DataFrame(rows, columns=header)
        del rows
        if 'Codeshare' not in frame:
            frame['Codeshare']=''
        frame['arquivo_origem']=file.name
        frame['linha_origem']=range(2,len(frame)+2)
        frame['ano_origem']=year
        parts.append(frame)
        if before != sha256_file(file):
            raise ValueError('Fonte mudou durante leitura')
        inventory.append(dict(arquivo_origem=file.name,sha256=before,registros=len(frame)))
    raw=pd.concat(parts,ignore_index=True)
    del parts, frame
    raw['id_raw']=range(1,len(raw)+1)
    extra=raw.duplicated(ORIGINAIS,keep='first')
    # Mesma chave exata de 20 campos do contrato. Codeshare é extensão preservada.
    representatives=raw.loc[~extra,ORIGINAIS+['arquivo_origem','linha_origem']].rename(columns={
        'arquivo_origem':'arquivo_preservado','linha_origem':'linha_preservada'})
    duplicates=raw.loc[extra].merge(representatives,on=ORIGINAIS,validate='many_to_one')
    del representatives
    base=raw.loc[~extra]
    text=original.padronizar_textos(base)
    converted=original.converter_tipos(text)
    if year!=2021:
        # Os dois layouts de referência são extensão específica da fonte 2021.
        converted.loc[~text.referencia.str.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',na=False),'referencia']=None
    converted['id_raw']=base.id_raw
    reasons=original.motivos_obrigatorios(text,converted)
    invalid=reasons.map(bool)
    rejected=base.loc[invalid].copy()
    rejected['motivos_rejeicao']=reasons.loc[invalid].map(lambda v:'{'+','.join(v)+'}')
    anomalies=original.auditar_opcionais(base,text,converted)
    anomalies['motivo']=anomalies.motivo.str.replace('FORA_DE_2021',f'FORA_DE_{year}',regex=False)
    treated=original.calcular_metricas(converted.loc[~invalid])
    columns=original.colunas_canonicas+META+MEASURES
    treated=treated[columns]
    for name,frame in [('vra_tratada',treated),('vra_rejeicoes',rejected),
                       ('vra_duplicatas_excluidas',duplicates),('vra_anomalias',anomalies)]:
        export_csv(frame,output/f'{name}.csv')
    summary=dict(ano_origem=year,bruta=len(raw),duplicatas_excedentes=len(duplicates),
                 rejeicoes=len(rejected),tratada=len(treated),
                 partidas_atipicas=int(treated.partida_atipica_flag.sum()),
                 chegadas_atipicas=int(treated.chegada_atipica_flag.sum()),
                 partidas_reais_nulas=int(treated.partida_real.isna().sum()),
                 chegadas_reais_nulas=int(treated.chegada_real.isna().sum()))
    summary.update(duplicate_stats(raw,duplicates,text,original,output))
    summary['partidas_previstas_fora_do_ano']=int(treated.partida_prevista.dt.year.ne(year).sum())
    if summary['bruta']!=sum(summary[k] for k in ['duplicatas_excedentes','rejeicoes','tratada']):
        raise ValueError('Classificação incompleta')
    if treated.duplicated(META[:3]).any():
        raise ValueError('Origem repetida')
    (output/'resumo.json').write_text(json.dumps(summary,indent=2)+'\n', encoding='utf-8')
    (output/'inventario.json').write_text(json.dumps(inventory,indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary),flush=True)
    return columns


def prepare(inputs, output):
    output=Path(output).resolve()
    canonical=preparar(inputs,output/'elt')
    sql=(canonical/'carga.sql').read_text(encoding='utf-8')
    sql=remap(sql,'elt').replace('CREATE SCHEMA staging;','CREATE SCHEMA staging_elt;').replace('CREATE SCHEMA dw;','CREATE SCHEMA dw_elt;')
    sql=sql.replace(remap((ROOT/'sql/integracao/02_dimensoes.sql').read_text(encoding='utf-8'),'elt'),dimension_sql('elt'))
    sql=sql.replace(remap((ROOT/'sql/integracao/03_carga_dw.sql').read_text(encoding='utf-8'),'elt'),load_sql('elt'))
    (output/'01_elt.psql').write_text(sql, encoding='utf-8')
    # Existing manual generator retained, with renamed independent schemas.
    for f in (canonical/'manual').iterdir():
        body=remap(f.read_text(encoding='utf-8'),'elt').replace('CREATE SCHEMA staging;','CREATE SCHEMA staging_elt;').replace('CREATE SCHEMA dw;','CREATE SCHEMA dw_elt;')
        body=body.replace(remap((ROOT/'sql/integracao/02_dimensoes.sql').read_text(encoding='utf-8'),'elt'),dimension_sql('elt')).replace(remap((ROOT/'sql/integracao/03_carga_dw.sql').read_text(encoding='utf-8'),'elt'),load_sql('elt'))
        f.write_text(body, encoding='utf-8')
    for year,directory in sorted(inputs.items()):
        etl(year,directory,output/f'etl/{year}')
    build_etl_bundle(inputs,output)


def treated_ddl(table):
    from etl_vra_anac_2021 import colunas_canonicas
    types={c:'text' for c in colunas_canonicas}
    types.update({c:'timestamp' for c in ['partida_prevista','partida_real','chegada_prevista','chegada_real']})
    types.update(numero_assentos='integer',referencia='date',id_raw='bigint',arquivo_origem='text',linha_origem='bigint',ano_origem='integer')
    types.update({c:'boolean' if c.endswith('_flag') else 'numeric' for c in MEASURES})
    required={'companhia_icao','aeroporto_origem','aeroporto_destino','partida_prevista','chegada_prevista',*META,*[c for c in MEASURES if c.endswith('_flag')]}
    return f'CREATE TABLE {table} ('+','.join(c+' '+t+(' NOT NULL' if c in required else '') for c,t in types.items())+', PRIMARY KEY(ano_origem,id_raw),UNIQUE(ano_origem,arquivo_origem,linha_origem));'


def build_etl_bundle(inputs, output):
    canonical=output/'elt'
    pandas_sql=['BEGIN;','CREATE SCHEMA raw_etl;','CREATE SCHEMA staging_etl;','CREATE SCHEMA dw_etl;',
        'CREATE TABLE raw_etl.ocorrencias (ano_origem integer,id_raw bigint,arquivo_origem text NOT NULL,linha_origem bigint NOT NULL,PRIMARY KEY(ano_origem,id_raw),UNIQUE(ano_origem,arquivo_origem,linha_origem));']
    # Ingestão bruta compartilhada como auxiliar, sem dependência de SQL tratado.
    # O bundle ETL pode ser instalado sozinho em banco vazio.
    for year in sorted(inputs):
        fields=','.join(identifier(c)+' TEXT NOT NULL' for c in ORIGINAIS+['Codeshare'])
        pandas_sql += [f'CREATE TABLE raw_etl.voos_{year} (id_raw bigint PRIMARY KEY,{fields},arquivo_origem text NOT NULL,linha_origem bigint NOT NULL,ano_origem integer NOT NULL CHECK(ano_origem={year}),UNIQUE(arquivo_origem,linha_origem));',
            f"\\copy raw_etl.voos_{year} FROM {caminho_copy(output/f'elt/raw_{year}.csv')} WITH(FORMAT CSV,NULL '\\N')",
            f'INSERT INTO raw_etl.ocorrencias SELECT ano_origem,id_raw,arquivo_origem,linha_origem FROM raw_etl.voos_{year};']
    ddl=(ROOT/'sql/database/10_criacao_dw.sql').read_text(encoding='utf-8').replace('id_raw BIGINT NOT NULL UNIQUE','id_raw BIGINT NOT NULL')
    ddl=ddl.replace("DEFAULT 'ELT'","DEFAULT 'ETL'").replace('arquivo_origem TEXT,','arquivo_origem TEXT NOT NULL,').replace('linha_origem BIGINT,','linha_origem BIGINT NOT NULL,')
    pandas_sql += [remap(ddl,'etl'), 'ALTER TABLE dw_etl.fato_voo ADD UNIQUE(ano_origem,id_raw), ADD UNIQUE(ano_origem,arquivo_origem,linha_origem);']
    for year,directory in sorted(inputs.items()):
        with (output/f'etl/{year}/vra_tratada.csv').open(encoding='utf-8', newline='') as source:
            columns=next(csv.reader(source))
        # Reuse only the structure, never SQL-treated data, for Pandas output.
        pandas_sql += [treated_ddl(f'staging_etl.vra_tratada_{year}'),
            f"\\copy staging_etl.vra_tratada_{year} ({','.join(columns)}) FROM {caminho_copy(output/f'etl/{year}/vra_tratada.csv')} WITH (FORMAT CSV, HEADER, NULL '\\N')"]
        for name in ['vra_rejeicoes','vra_duplicatas_excluidas']:
            # Audits retain original columns and canonical occurrence IDs.
            extra = ', motivos_rejeicao text[]' if name=='vra_rejeicoes' else ', arquivo_preservado text, linha_preservada bigint'
            fields=','.join(identifier(c)+' text' for c in ORIGINAIS+['Codeshare'])
            pandas_sql.append(f'CREATE TABLE staging_etl.{name}_{year} ({fields}, arquivo_origem text, linha_origem bigint, ano_origem integer, id_raw bigint{extra}, PRIMARY KEY(ano_origem,id_raw));')
            with (output/f'etl/{year}/{name}.csv').open(encoding='utf-8', newline='') as source:
                header=next(csv.reader(source))
            pandas_sql.append(f"\\copy staging_etl.{name}_{year} ({','.join(map(identifier,header))}) FROM {caminho_copy(output/f'etl/{year}/{name}.csv')} WITH (FORMAT CSV, HEADER, NULL '\\N')")
    for year in sorted(inputs):
        pandas_sql.append(f'CREATE TABLE staging_etl.vra_anomalias_{year} (arquivo_origem text,linha_origem bigint,ano_origem integer,campo text,valor_original text,motivo text);')
        pandas_sql.append(f"\\copy staging_etl.vra_anomalias_{year} FROM {caminho_copy(output/f'etl/{year}/vra_anomalias.csv')} WITH (FORMAT CSV, HEADER, NULL '\\N')")
    pandas_sql.append('CREATE TABLE staging_etl.vra_anomalias AS '+' UNION ALL '.join(f'SELECT * FROM staging_etl.vra_anomalias_{y}' for y in inputs)+';')
    for name in ['vra_tratada','vra_rejeicoes','vra_duplicatas_excluidas']:
        pandas_sql.append(f'CREATE TABLE staging_etl.{name} AS '+' UNION ALL '.join(f'SELECT * FROM staging_etl.{name}_{y}' for y in inputs)+';')
        pandas_sql += [f'ALTER TABLE staging_etl.{name} ADD PRIMARY KEY(ano_origem,id_raw), ADD UNIQUE(ano_origem,arquivo_origem,linha_origem), ADD FOREIGN KEY(ano_origem,id_raw) REFERENCES raw_etl.ocorrencias;']
    fact_checks='ALTER TABLE dw.fato_voo'+(ROOT/'sql/integracao/08_restricoes.sql').read_text(encoding='utf-8').split('ALTER TABLE dw.fato_voo',1)[1]
    pandas_sql.append(remap(fact_checks,'etl'))
    pandas_sql.append('ALTER TABLE dw_etl.fato_voo ADD FOREIGN KEY(ano_origem,id_raw) REFERENCES staging_etl.vra_tratada;')
    pandas_sql += [dimension_sql('etl'),
                   load_sql('etl'),'COMMIT;']
    (output/'02_etl.psql').write_text('\n'.join(pandas_sql), encoding='utf-8')
    # Regenerable manifests include code, source and artifact fingerprints.
    (output/'manifesto_final.json').write_text(json.dumps({
        'fontes':json.loads((canonical/'manifesto.json').read_text(encoding='utf-8')),
        'codigo':{str(p.relative_to(ROOT)):sha256_file(p) for p in [Path(__file__),ROOT/'scripts/etl_vra_anac_2021.py',ROOT/'scripts/integrar_anac.py',ROOT/'scripts/testar_integracao_isolada.py',*sorted((ROOT/'sql').rglob('*.sql'))]},
        'saidas':{str(p.relative_to(output)):sha256_file(p) for p in output.rglob('*.csv')},
    },indent=2,ensure_ascii=False)+'\n', encoding='utf-8')


def isolated(output,cluster):
    output=Path(output).resolve();cluster=Path(cluster).resolve()
    if cluster.exists():
        raise ValueError('Cluster deve ser novo; dados existentes preservados')
    cluster.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['initdb','-D',str(cluster),'-A','trust','--no-locale','-E','UTF8'],check=True,capture_output=True)
    for name in ['01_elt','02_etl']:
        sql=(output/f'{name}.psql').read_text(encoding='utf-8')
        sql=re.sub(r'^\\copy (.*)$',r'COPY \1;',sql,flags=re.M)
        executar(cluster,sql,output/f'{name}.log')
        print(name,'executado',flush=True)
    validate(output,cluster)


def validate(output,cluster):
    output=Path(output).resolve();cluster=Path(cluster).resolve()
    for flow in ['etl','elt']:
        load=load_sql(flow)
        executar(cluster,'BEGIN;'+load+'COMMIT;',output/f'reexecucao_{flow}.log')
    compare(output,cluster)
    for flow in ['etl','elt']:
        query=remap((ROOT/'sql/integracao/05_analises.sql').read_text(encoding='utf-8'),flow)
        if flow=='etl':
            query=query[:query.index('SELECT ano_origem,bruta')]
        executar(cluster,query,output/f'analises_{flow}.log')
    evidence=output/'evidencias';evidence.mkdir(parents=True,exist_ok=True)
    for path in output.glob('*.log'):
        (evidence/path.name).write_text(path.read_text(encoding='utf-8'), encoding='utf-8')
    for y in YEARS:
        (evidence/f'etl_{y}.json').write_text((output/f'etl/{y}/resumo.json').read_text(encoding='utf-8'), encoding='utf-8')
    print('Comparação, reexecução e análises executadas',flush=True)


def compare(output, cluster, years=YEARS):
    output=Path(output).resolve()
    cluster=Path(cluster).resolve()
    output.mkdir(parents=True,exist_ok=True)
    sql=(ROOT/'sql/comparacao/validar_final.sql').read_text(encoding='utf-8')
    definitions,_,_=sql.partition('-- Execução manual completa.')
    executar(cluster,definitions+'\nSELECT comparacao.validar_dimensoes();',output/'validacao_dimensoes.log')
    print('Dimensões e chaves estrangeiras conferidas',flush=True)
    for year in years:
        log=output/f'validacao_{year}.log'
        executar(cluster,f'SELECT comparacao.validar_ano({year});',log)
        if f'COMPARACAO_EXATA_OK {year}' not in log.read_text(encoding='utf-8'):
            raise RuntimeError(f'Comparação sem confirmação: {log}')
        print(f'{year}: igualdade de conteúdo e rastreabilidade confirmadas',flush=True)


def verificar_espaco_carga(output, destino):
    raw_bytes = sum((output / f'elt/raw_{ano}.csv').stat().st_size for ano in YEARS)
    exigir_espaco(destino, 24 * raw_bytes + 2 * GIB, 'instalação completa dos dois DWs')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','isolated','validate','etl','compare','check-load'])
    for y in YEARS:p.add_argument(f'--dados-{y}',type=Path)
    p.add_argument('--ano',type=int,choices=YEARS)
    p.add_argument('--input-dir',type=Path)
    p.add_argument('--output',type=Path,default=ROOT/'.local/final')
    p.add_argument('--cluster',type=Path,default=ROOT/'.local/final/postgres')
    p.add_argument('--volume-pg', type=Path,
                   help='Diretório existente no volume de dados do servidor para check-load')
    a=p.parse_args()
    if a.command=='prepare':
        inputs={y:getattr(a,f'dados_{y}') for y in YEARS}
        if not all(inputs.values()):p.error('Informe --dados-2019, --dados-2020 e --dados-2021')
        source_size=sum(f.stat().st_size for folder in inputs.values() for f in folder.glob('*.csv'))
        exigir_espaco(a.output,4*source_size+GIB,'preparação dos CSVs e auditorias')
        prepare(inputs,a.output)
    elif a.command=='etl':
        if not a.ano or not a.input_dir:p.error('Informe --ano e --input-dir')
        source_size=sum(path.stat().st_size for path in a.input_dir.glob('*.csv'))
        exigir_espaco(a.output,3*source_size+GIB,'exportação ETL anual')
        etl(a.ano,a.input_dir,a.output)
    elif a.command=='isolated':
        verificar_espaco_carga(a.output, a.cluster)
        isolated(a.output,a.cluster)
    elif a.command=='check-load':
        if not a.volume_pg or not a.volume_pg.is_dir():
            p.error('Informe um diretório existente no volume PostgreSQL com --volume-pg')
        try:
            verificar_espaco_carga(a.output, a.volume_pg)
        except (OSError, RuntimeError) as error:
            p.exit(1, f'{error}\n')
        print('Espaço para a carga conferido, incluindo a reserva de 8 GiB.')
    else:
        exigir_espaco(a.cluster,2*GIB,'comparação e validação em lotes')
        if a.command=='compare':
            compare(a.output,a.cluster,(a.ano,) if a.ano else YEARS)
        else:
            validate(a.output,a.cluster)

if __name__=='__main__':main()
