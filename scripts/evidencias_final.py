#!/usr/bin/env python3
"""Evidências compactas e identidade exata entre a preparação CSV e o RAW real."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from integrar_anac import ROOT,caminho_copy,sha256_file
from testar_integracao_isolada import executar
from espaco_disco import GIB, exigir_espaco


def evidence(output,cluster):
    output=Path(output).resolve();cluster=Path(cluster).resolve()
    target=output/'evidencias';target.mkdir(exist_ok=True)
    statements=[]
    queries={
      'qualidade':'SELECT * FROM staging_elt.resumo_qualidade ORDER BY ano_origem',
      'servidor':'SELECT current_database(),current_user,version()',
      'dimensoes':"SELECT 'etl' fluxo,table_name FROM information_schema.tables WHERE table_schema='dw_etl' UNION ALL SELECT 'elt',table_name FROM information_schema.tables WHERE table_schema='dw_elt' ORDER BY 1,2",
      'origem_arquivo':'SELECT ano_origem,arquivo_origem,count(*) registros,min(linha_origem) primeira,max(linha_origem) ultima FROM raw.ocorrencias GROUP BY 1,2 ORDER BY 1,2',
      'motivos_rejeicao':'SELECT ano_origem,unnest(motivos_rejeicao) motivo,count(*) registros FROM staging_elt.vra_rejeicoes GROUP BY 1,2 ORDER BY 1,2',
      'variantes_dimensoes':'SELECT * FROM staging_elt.variantes_dimensoes ORDER BY 1,2',
      'snapshot_descricoes':'SELECT * FROM staging_elt.snapshot_descricoes ORDER BY 1,2',
      'restricoes':"SELECT n.nspname,c.conrelid::regclass tabela,c.conname,c.contype,c.convalidated FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname IN('dw_etl','dw_elt','raw','raw_etl','staging_etl','staging_elt') ORDER BY 1,2,3",
    }
    for flow in ['etl','elt']:
        queries[f'dimensoes_{flow}']=' UNION ALL '.join(f"SELECT '{name}' dimensao,count(*) membros FROM dw_{flow}.{name}" for name in ['dim_tempo','dim_companhia_aerea','dim_aeroporto','dim_situacao_voo','dim_justificativa','dim_tipo_linha','dim_equipamento'])+' ORDER BY 1'
        from etl_vra_anac_2021 import colunas_canonicas
        from integracao_final import MEASURES
        counts=','.join(f'count(*)-count({c}) AS {c}' for c in colunas_canonicas+MEASURES)
        queries[f'nulos_{flow}']=f'SELECT ano_origem,{counts} FROM staging_{flow}.vra_tratada GROUP BY 1 ORDER BY 1'
        queries[f'fato_{flow}']=f'SELECT ano_origem,count(*) registros FROM dw_{flow}.fato_voo GROUP BY 1 ORDER BY 1'
        queries[f'indicadores_{flow}']=f'''SELECT ano_origem,count(*) voos,count(atraso_partida_min) calculaveis,
        count(*) FILTER(WHERE atraso_partida_min IS NULL) desconhecidos,
        count(*) FILTER(WHERE atraso_partida_min>0) atrasados,
        count(*) FILTER(WHERE diferenca_partida_min<0) antecipados,
        count(*) FILTER(WHERE partida_atipica_flag) partidas_atipicas,
        count(*) FILTER(WHERE chegada_atipica_flag) chegadas_atipicas,
        round(avg(atraso_partida_min),2) atraso_medio_min FROM dw_{flow}.fato_voo GROUP BY 1 ORDER BY 1'''
        queries[f'companhias_{flow}']=f'''SELECT ano_origem,c.companhia_icao,c.companhia_nome,count(*) voos,
        round(avg(f.atraso_partida_min),2) atraso_medio_min FROM dw_{flow}.fato_voo f JOIN dw_{flow}.dim_companhia_aerea c USING(id_companhia) GROUP BY 1,2,3 ORDER BY 1,2'''
        queries[f'mensal_{flow}']=f'''SELECT f.ano_origem,t.ano,t.mes,count(*) voos FROM dw_{flow}.fato_voo f JOIN dw_{flow}.dim_tempo t ON t.id_tempo=f.id_tempo_partida GROUP BY 1,2,3 ORDER BY 1,2,3'''
        for role in ['origem','destino']:
            queries[f'aeroportos_{role}_{flow}']=f'''SELECT f.ano_origem,a.aeroporto_icao,count(*) voos FROM dw_{flow}.fato_voo f JOIN dw_{flow}.dim_aeroporto a ON a.id_aeroporto=f.id_aeroporto_{role} GROUP BY 1,2 ORDER BY 1,voos DESC,2'''
    for name,query in queries.items():
        statements.append(f'COPY ({query}) TO {caminho_copy(target/(name+".csv"))} WITH(FORMAT CSV,HEADER);')
    executar(cluster,'\n'.join(statements),output/'extracao_evidencias.log')
    identities={}
    # Uma reexportação por vez. O arquivo dura apenas até a verificação do hash.
    with TemporaryDirectory(prefix='raw_evidencia_',dir=output) as temp:
        exported=Path(temp)/'raw.csv'
        for year in (2019,2020,2021):
            source=sha256_file(output/f'elt/raw_{year}.csv')
            for schema in ('raw','raw_etl'):
                query=f'COPY (SELECT * FROM {schema}.voos_{year} ORDER BY id_raw) TO {caminho_copy(exported)} WITH(FORMAT CSV,FORCE_QUOTE *);'
                executar(cluster,query,output/f'raw_evidencia_{schema}_{year}.log')
                actual=sha256_file(exported)
                identities[f'{schema}_{year}']=dict(sha256_ingestao=source,sha256_raw=actual,iguais=source==actual)
                if source!=actual:
                    raise ValueError(f'RAW divergente em {schema}/{year}')
                exported.unlink()
    analytics={name:sha256_file(target/f'{name}_etl.csv')==sha256_file(target/f'{name}_elt.csv')
               for name in ['fato','indicadores','companhias','mensal','aeroportos_origem','aeroportos_destino','nulos','dimensoes']}
    if not all(analytics.values()):raise ValueError('Agregações analíticas divergentes')
    (target/'comparacao_analitica.json').write_text(json.dumps(analytics,indent=2)+'\n', encoding='utf-8')
    (target/'identidade_raw.json').write_text(json.dumps(identities,indent=2)+'\n', encoding='utf-8')
    (target/'manifesto_fontes.json').write_text((output/'elt/manifesto.json').read_text(encoding='utf-8'), encoding='utf-8')
    print(json.dumps(identities,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'.local/final')
    p.add_argument('--cluster',type=Path,default=ROOT/'.local/final/postgres')
    a=p.parse_args()
    largest=max((a.output/f'elt/raw_{year}.csv').stat().st_size for year in (2019,2020,2021))
    exigir_espaco(a.output,2*largest+GIB,'reexportação sequencial dos RAWs')
    exigir_espaco(a.cluster,2*GIB,'consultas analíticas')
    evidence(a.output,a.cluster)
