-- Diagnósticos adicionais: cada grupo inclui a representante e as excedentes.
SELECT ano_origem,count(*) grupos,sum(tamanho) linhas_envolvidas,sum(tamanho-1) excedentes
FROM (
 SELECT ano_origem,arquivo_preservado,linha_preservada,max(ocorrencia_num) tamanho
 FROM staging.vra_duplicatas_excluidas GROUP BY 1,2,3
) d GROUP BY 1 ORDER BY 1;
-- Interseção de excedentes com obrigatórios inválidos (não somar às rejeições).
SELECT ano_origem,count(*) FILTER(WHERE
 staging.limpar_texto("Sigla ICAO Empresa Aérea") IS NULL
 OR staging.limpar_texto("Sigla ICAO Aeroporto Origem") IS NULL
 OR staging.limpar_texto("Sigla ICAO Aeroporto Destino") IS NULL
 OR staging.datahora_segura(staging.limpar_texto("Partida Prevista")) IS NULL
 OR staging.datahora_segura(staging.limpar_texto("Chegada Prevista")) IS NULL
) duplicatas_invalidas FROM staging.vra_duplicatas_excluidas GROUP BY 1 ORDER BY 1;
SELECT ano_origem,count(*) registros,cardinality(motivos_rejeicao) quantidade_motivos
FROM staging.vra_rejeicoes GROUP BY 1,3 ORDER BY 1,3;
