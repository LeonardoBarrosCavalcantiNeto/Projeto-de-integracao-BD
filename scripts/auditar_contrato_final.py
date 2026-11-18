#!/usr/bin/env python3
"""Completa diagnósticos contratuais sem repetir tratamento ou carga dos voos."""
import argparse
import csv
import json
import sqlite3
from contextlib import closing
from tempfile import TemporaryDirectory
from pathlib import Path
from integrar_anac import ROOT,ORIGINAIS,caminho_copy,identifier
from integracao_final import exact_duplicate_stats,write_csv_rows
from testar_integracao_isolada import executar
from espaco_disco import GIB, exigir_espaco


def audit_pandas(output, year, original):
    import pandas as pd

    year_dir=output/f'etl/{year}'
    duplicates=pd.read_csv(year_dir/'vra_duplicatas_excluidas.csv',dtype=str,keep_default_na=False)
    stats=exact_duplicate_stats(duplicates,original)
    extra_ids=set(duplicates.id_raw)
    raw_columns=['id_raw']+ORIGINAIS+['Codeshare','arquivo_origem','linha_origem','ano_origem']
    origin=['arquivo_origem','linha_origem','ano_origem','id_raw']
    canonical=original.colunas_canonicas

    # Chave JSON reversível e exata com as 20 colunas normalizadas. A ordenação
    # global usa SQLite em disco. Pandas só mantém um lote da entrada em memória.
    with TemporaryDirectory(prefix='contrato_',dir=output) as temp:
        with closing(sqlite3.connect(Path(temp)/'grupos.sqlite')) as db:
            db.execute('PRAGMA temp_store=FILE')
            db.execute('PRAGMA cache_size=-16384')
            db.execute("CREATE TABLE ocorrencia (chave TEXT,id INTEGER,arquivo TEXT,linha INTEGER,PRIMARY KEY(chave,id)) WITHOUT ROWID")
            with pd.read_csv(output/f'elt/raw_{year}.csv',names=raw_columns,dtype=str,
                             keep_default_na=False,chunksize=25000) as batches:
                for batch in batches:
                    base=batch.loc[~batch.id_raw.isin(extra_ids)]
                    normalized=original.padronizar_textos(base)[canonical]
                    values=normalized.astype(object).where(normalized.notna(),None)
                    db.executemany('INSERT INTO ocorrencia VALUES(?,?,?,?)', (
                        (json.dumps(row,ensure_ascii=False,separators=(',',':')),int(i),name,int(line))
                        for row,(i,name,line) in zip(values.itertuples(index=False,name=None),
                            base[['id_raw','arquivo_origem','linha_origem']].itertuples(index=False,name=None),strict=True)))
                    db.commit()
            db.execute('CREATE TEMP TABLE grupos AS SELECT chave,count(*) n FROM ocorrencia GROUP BY chave HAVING count(*)>1')
            groups,involved=db.execute('SELECT count(*),coalesce(sum(n),0) FROM grupos').fetchone()
            matches=db.execute('SELECT o.chave,o.arquivo,o.linha,o.id FROM grupos g JOIN ocorrencia o USING(chave) ORDER BY o.id')
            write_csv_rows(canonical+origin,(
                [*json.loads(key),name,line,year,occurrence] for key,name,line,occurrence in matches
            ),year_dir/'vra_duplicatas_apos_padronizacao.csv')
    stats.update(grupos_apos_padronizacao=groups,linhas_envolvidas_apos_padronizacao=involved,
                 excedentes_apos_padronizacao=involved-groups)
    with pd.read_csv(year_dir/'vra_tratada.csv',usecols=['partida_prevista'],dtype=str,chunksize=25000) as batches:
        stats['partidas_previstas_fora_do_ano']=sum(
            int(batch.partida_prevista.str[:4].ne(str(year)).sum()) for batch in batches)
    return stats


def audit(output,cluster):
    import etl_vra_anac_2021 as original
    output=Path(output).resolve();dest=output/'evidencias';dest.mkdir(exist_ok=True)
    queries=[]
    for year in [2019,2020,2021]:
        original.ano_origem=year
        summary_path=output/f'etl/{year}/resumo.json'
        summary=json.loads(summary_path.read_text(encoding='utf-8'))
        stats=audit_pandas(output,year,original)
        summary.update(stats)
        summary_path.write_text(json.dumps(summary,indent=2)+'\n', encoding='utf-8')
        expressions=[]
        for field,canonical in original.mapa_colunas.items():
            expr=f'staging_elt.limpar_texto({identifier(field)})'
            if canonical in original.campos_maiusculos:expr=f'upper({expr})'
            expressions.append(expr+' AS '+canonical)
        cols=','.join(original.colunas_canonicas)
        q=f'''WITH normalizada AS (SELECT {','.join(expressions)} FROM staging_elt.vra_classificada_{year} WHERE ocorrencia_num=1),
        normalizados AS (SELECT count(*) n FROM normalizada GROUP BY {cols} HAVING count(*)>1),
        exatos AS (SELECT arquivo_preservado,linha_preservada,count(*) n FROM staging_elt.vra_duplicatas_excluidas_{year} GROUP BY 1,2)
        SELECT {year} ano_origem,(SELECT count(*) FROM exatos) grupos_duplicados,
        (SELECT coalesce(sum(n+1),0) FROM exatos) linhas_envolvidas_duplicatas,
        (SELECT count(*) FROM staging_elt.vra_duplicatas_excluidas_{year} WHERE
        staging_elt.limpar_texto("Sigla ICAO Empresa Aérea") IS NULL OR
        staging_elt.limpar_texto("Sigla ICAO Aeroporto Origem") IS NULL OR
        staging_elt.limpar_texto("Sigla ICAO Aeroporto Destino") IS NULL OR
        staging_elt.datahora_segura(staging_elt.limpar_texto("Partida Prevista")) IS NULL OR
        staging_elt.datahora_segura(staging_elt.limpar_texto("Chegada Prevista")) IS NULL) intersecao_excedentes_invalidos,
        (SELECT count(*) FROM normalizados) grupos_apos_padronizacao,
        (SELECT coalesce(sum(n),0) FROM normalizados) linhas_envolvidas_apos_padronizacao,
        (SELECT coalesce(sum(n-1),0) FROM normalizados) excedentes_apos_padronizacao,
        (SELECT count(*) FROM staging_elt.vra_tratada_{year} WHERE extract(year FROM partida_prevista)<>{year}) partidas_previstas_fora_do_ano'''
        queries.append(q)
        print(year,stats,flush=True)
    query=' UNION ALL '.join('('+q+')' for q in queries)+' ORDER BY ano_origem'
    path=dest/'diagnosticos_contrato_sql.csv'
    executar(cluster,f'COPY ({query}) TO {caminho_copy(path)} WITH(FORMAT CSV,HEADER);',output/'diagnosticos_contrato.log')
    with path.open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            year=int(row.pop('ano_origem'))
            summary=json.loads((output/f'etl/{year}/resumo.json').read_text(encoding='utf-8'))
            for field,value in row.items():
                if summary[field]!=int(value):raise ValueError(f'Diagnóstico divergente: {year}/{field}')
            (dest/f'etl_{year}.json').write_text(json.dumps(summary,indent=2)+'\n', encoding='utf-8')
    (dest/'diagnosticos_contrato.json').write_text(json.dumps(dict(anos=[2019,2020,2021],diagnosticos_pandas_sql_iguais=True),indent=2)+'\n', encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'.local/final')
    p.add_argument('--cluster',type=Path,default=ROOT/'.local/final/postgres')
    a=p.parse_args()
    largest=max((a.output/f'elt/raw_{year}.csv').stat().st_size for year in (2019,2020,2021))
    exigir_espaco(a.output,3*largest+GIB,'auditorias Pandas em disco')
    exigir_espaco(a.cluster,2*GIB,'auditorias SQL')
    audit(a.output,a.cluster)
