#!/usr/bin/env python3
"""Extrai evidências reais do cluster isolado já integrado (sem serviço/socket)."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from integrar_anac import ROOT, literal, sha256_file
from testar_integracao_isolada import executar


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparar-etl',action='store_true',help='Exportar resultados após executar os SQLs de comparação')
    args=parser.parse_args()
    local=ROOT/'.local/integracao'
    bundle=local/'bundle';cluster=local/'postgres_teste'
    output=ROOT/'resultados/validacoes/integracao_2019_2020'
    output.mkdir(parents=True,exist_ok=True)
    statements=[]
    for year in [2019,2020]:
        target=bundle/f'raw_reexportado_{year}.csv'
        statements.append(f"COPY (SELECT * FROM raw.voos_{year} ORDER BY id_raw) TO {literal(target)} WITH(FORMAT CSV, FORCE_QUOTE *);")
    queries={
      'comparacao_etl_elt': 'SELECT c.*,d.divergencias_origens divergencias_duplicatas,r.divergencias_origens divergencias_rejeicoes FROM staging.comparacao_2019 c CROSS JOIN staging.comparacao_vra_duplicatas_excluidas_2019 d CROSS JOIN staging.comparacao_vra_rejeicoes_2019 r UNION ALL SELECT c.*,d.divergencias_origens,r.divergencias_origens FROM staging.comparacao_2020 c CROSS JOIN staging.comparacao_vra_duplicatas_excluidas_2020 d CROSS JOIN staging.comparacao_vra_rejeicoes_2020 r',
      'grupos_duplicados': 'SELECT ano_origem,count(*) grupos,sum(tamanho) linhas_envolvidas,sum(tamanho-1) excedentes FROM (SELECT ano_origem,arquivo_preservado,linha_preservada,max(ocorrencia_num) tamanho FROM staging.vra_duplicatas_excluidas GROUP BY 1,2,3) d GROUP BY 1 ORDER BY 1',
      'servidor_teste': 'SELECT current_database() banco,version() versao',
      'anomalias':'SELECT * FROM staging.vra_anomalias ORDER BY ano_origem,arquivo_origem,linha_origem,campo',
      'qualidade':'SELECT * FROM staging.resumo_qualidade ORDER BY ano_origem',
      'fato_por_ano':'SELECT ano_origem,count(*) voos FROM dw.fato_voo GROUP BY 1 ORDER BY 1',
      'dimensoes':"SELECT 'companhia' dimensao,count(*) membros FROM dw.dim_companhia_aerea UNION ALL SELECT 'aeroporto',count(*) FROM dw.dim_aeroporto UNION ALL SELECT 'tempo',count(*) FROM dw.dim_tempo UNION ALL SELECT 'situacao',count(*) FROM dw.dim_situacao_voo UNION ALL SELECT 'justificativa',count(*) FROM dw.dim_justificativa UNION ALL SELECT 'tipo_linha',count(*) FROM dw.dim_tipo_linha UNION ALL SELECT 'equipamento',count(*) FROM dw.dim_equipamento",
      'motivos_rejeicao':'SELECT ano_origem,unnest(motivos_rejeicao) motivo,count(*) registros FROM staging.vra_rejeicoes GROUP BY 1,2 ORDER BY 1,2',
      'resolucoes_aplicadas':'SELECT ano_origem,aeroporto_icao,descricao_original,descricao_resolvida,fonte_url,count(*) ocorrencias FROM staging.aeroportos_resolvidos WHERE fonte_url IS NOT NULL GROUP BY 1,2,3,4,5 ORDER BY 1,2',
      'origem_por_arquivo':'SELECT ano_origem,arquivo_origem,count(*) registros,min(linha_origem) primeira,max(linha_origem) ultima FROM raw.ocorrencias GROUP BY 1,2 ORDER BY 1,2',
      'qualidade_adicional':'''SELECT ano_origem,count(*) FILTER(WHERE extract(year FROM partida_prevista)<>ano_origem) partidas_fora_ano,
        count(*) FILTER(WHERE diferenca_partida_min<0) antecipacoes_partida,
        count(*) FILTER(WHERE diferenca_chegada_min<0) antecipacoes_chegada,
        count(*) FILTER(WHERE partida_real IS NULL AND atraso_partida_min IS NOT NULL) nulos_partida_incorretos,
        count(*) FILTER(WHERE chegada_real IS NULL AND atraso_chegada_min IS NOT NULL) nulos_chegada_incorretos
        FROM dw.fato_voo GROUP BY 1 ORDER BY 1''',
      'restricoes':"SELECT n.nspname schema,c.conrelid::regclass tabela,c.conname,c.contype,c.convalidated FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname IN('dw','staging','raw') ORDER BY 1,2,3",
    }
    if not args.comparar_etl:queries.pop('comparacao_etl_elt')
    analyses='\n'.join(x for x in (ROOT/'sql/integracao/05_analises.sql').read_text().splitlines() if not x.lstrip().startswith('--'))
    for i,q in enumerate(filter(str.strip,analyses.split(';')),1):queries[f'analise_{i:02d}']=q
    for name,query in queries.items():
        statements.append(f'COPY ({query}) TO {literal(output/(name+".csv"))} WITH(FORMAT CSV,HEADER);')
    executar(cluster,'\n'.join(statements),bundle/'postgres_evidencias.log')
    matches={}
    for year in [2019,2020]:
        original=sha256_file(bundle/f'raw_{year}.csv')
        exported=sha256_file(bundle/f'raw_reexportado_{year}.csv')
        matches[str(year)]={'sha256_ingestao':original,'sha256_reexportacao':exported,'iguais':original==exported}
        if original!=exported:raise AssertionError(f'RAW diverge do bundle em {year}')
    (output/'identidade_csv_raw.json').write_text(json.dumps(matches,indent=2)+'\n')
    # Registra somente manifesto, nunca os CSVs brutos ou dados grandes.
    (output/'manifesto_fontes.json').write_text((bundle/'manifesto.json').read_text())
    for source,name in [(local/'etl_2019/resumo_comparacao.json','etl_2019_resumo.json'),
                        (local/'etl_2020/etl_resumo.json','etl_2020_resumo.json'),
                        (local/'tests.log','testes.log')]:
        if source.is_file():(output/name).write_text(source.read_text())
    print(json.dumps(matches,indent=2))

if __name__=='__main__':main()
