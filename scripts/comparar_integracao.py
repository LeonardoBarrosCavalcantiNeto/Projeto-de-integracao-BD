#!/usr/bin/env python3
"""Compara ETLs originais com ELT integrado por TODOS os campos canônicos.

Exporta ETLs antes da carga e gera SQL EXCEPT ALL bidirecional. Não compara SKs.
Usa funções originais dos integrantes; não precisa conectar ao banco para tratar.
"""
import argparse
import csv
import gzip
import json
from pathlib import Path
import pandas as pd
import etl_vra_anac_2019 as etl19
import etl_vra_anac_2020 as etl20
from integrar_anac import ROOT, literal, identifier


def executar_etl_2019(directory, output):
    output.mkdir(parents=True,exist_ok=True)
    files=sorted(Path(directory).glob('VRA_2019_*.csv'))
    if [x.name for x in files] != [f'VRA_2019_{m:02d}.csv' for m in range(1,13)]:
        raise ValueError('Esperados os 12 CSVs de 2019')
    raw=etl19._read_raw_files(files,pd.Timestamp.now(tz='UTC'))
    _,extra,duplicates,metrics=etl19._deduplicate_raw(raw)
    normalized=etl19._normalize_and_validate(raw)
    dedup=normalized.loc[~extra]
    treated=etl19._make_treated(dedup.loc[dedup.status_validacao.eq('VALIDO')])
    rejected=dedup.loc[dedup.status_validacao.eq('REJEITADO')]
    # Transformação do integrante preservada. Dimensões são publicadas pelo ELT
    # integrado após as resoluções documentadas, em vez de contornar conflitos.
    for name,frame in [('vra_tratada',treated),('vra_rejeicoes',rejected),('vra_duplicatas_excluidas',duplicates)]:
        frame.to_csv(output/(name+'.csv.gz'),index=False,compression='gzip',na_rep='')
    summary={**metrics,'brutos':len(raw),'rejeitados':len(rejected),'tratados':len(treated),
             'escopo':'funções originais de extração, deduplicação e transformação; sem publicação do DW ETL'}
    (output/'resumo_comparacao.json').write_text(json.dumps(summary,indent=2)+'\n')


def gerar_sql(year, directory, output):
    canonical=etl19.CANONICAL_COLS
    metrics=['diferenca_partida_min','diferenca_chegada_min','atraso_partida_min','atraso_chegada_min',
             'partida_atipica_flag','chegada_atipica_flag']
    columns=canonical+metrics+['ano_origem','arquivo_origem','linha_origem']
    prepared=output/f'etl_comparar_{year}.csv'
    source=directory/'vra_tratada.csv.gz'
    # CSV intermediário com todos os textos entre aspas; NULL usa marcador sem
    # aspas. Preserva strings literais como "NULL" e "\\N".
    with gzip.open(source,'rt',newline='') as inp,prepared.open('w',newline='') as out:
        reader=csv.DictReader(inp)
        for row in reader:
            parts=[]
            for column in columns:
                value=row[column]
                if value=='':parts.append('\\N')
                else:parts.append('"'+value.replace('"','""')+'"')
            out.write(','.join(parts)+'\n')
    cols=','.join(map(identifier,columns))
    differences=' OR '.join('e.'+identifier(c)+' IS DISTINCT FROM s.'+identifier(c) for c in canonical+metrics)
    statements=[f'CREATE TABLE staging.etl_comparar_{year} AS SELECT {cols} FROM staging.vra_tratada WITH NO DATA;',
                f"\\copy staging.etl_comparar_{year} FROM {literal(prepared.resolve())} WITH (FORMAT CSV, NULL '\\N')",
                f'ALTER TABLE staging.etl_comparar_{year} ADD PRIMARY KEY(ano_origem,arquivo_origem,linha_origem);',
                f'''CREATE TABLE staging.comparacao_{year} AS
SELECT {year} ano_origem,count(*) divergencias_conteudo FROM staging.etl_comparar_{year} e
FULL JOIN (SELECT * FROM staging.vra_tratada WHERE ano_origem={year}) s
USING(ano_origem,arquivo_origem,linha_origem)
WHERE e.arquivo_origem IS NULL OR s.arquivo_origem IS NULL OR ({differences});''',
                f'SELECT * FROM staging.comparacao_{year};']
    for table in ['vra_duplicatas_excluidas','vra_rejeicoes']:
        path=output/f'etl_{table}_{year}.csv'
        with gzip.open(directory/(table+'.csv.gz'),'rt',newline='') as inp,path.open('w',newline='') as out:
            writer=csv.writer(out,quoting=csv.QUOTE_ALL)
            for row in csv.DictReader(inp):writer.writerow([year,row['arquivo_origem'],row['linha_origem']])
        target=f'staging.etl_{table}_{year}'
        statements += [f'CREATE TABLE {target}(ano_origem integer,arquivo_origem text,linha_origem bigint);',
                       f"\\copy {target} FROM {literal(path.resolve())} WITH (FORMAT CSV)",
                       f'''SELECT {year} ano_origem,{literal(table)} auditoria,count(*) divergencias_origens FROM (
 (SELECT * FROM {target} EXCEPT ALL SELECT ano_origem,arquivo_origem,linha_origem FROM staging.{table} WHERE ano_origem={year})
 UNION ALL
 (SELECT ano_origem,arquivo_origem,linha_origem FROM staging.{table} WHERE ano_origem={year} EXCEPT ALL SELECT * FROM {target})
) d;''']
        result_table=f'staging.comparacao_{table}_{year}'
        statements[-1]='CREATE TABLE '+result_table+' AS '+statements[-1]
        statements.append('SELECT * FROM '+result_table+';')
    statements.append(f"DO $$ BEGIN IF EXISTS(SELECT FROM staging.comparacao_{year} WHERE divergencias_conteudo<>0) THEN RAISE EXCEPTION 'ETL/ELT divergem em {year}'; END IF; END $$;")
    for table in ['vra_duplicatas_excluidas','vra_rejeicoes']:
        statements.append(f"DO $$ BEGIN IF EXISTS(SELECT FROM staging.comparacao_{table}_{year} WHERE divergencias_origens<>0) THEN RAISE EXCEPTION 'Auditoria ETL/ELT diverge em {year}'; END IF; END $$;")
    (output/f'comparar_{year}.sql').write_text('BEGIN;\n'+'\n'.join(statements)+'\nCOMMIT;\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ano',type=int,choices=[2019,2020],required=True)
    parser.add_argument('--dados',type=Path)
    parser.add_argument('--etl-output',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,default=ROOT/'.local/integracao/bundle')
    args=parser.parse_args()
    if args.dados:
        if args.ano==2019:executar_etl_2019(args.dados,args.etl_output)
        else:etl20.executar(args.dados,args.etl_output)
    gerar_sql(args.ano,args.etl_output,args.bundle)

if __name__=='__main__':main()
