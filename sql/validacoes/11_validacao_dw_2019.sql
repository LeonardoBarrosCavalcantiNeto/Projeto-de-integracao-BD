/* VRA / ANAC 2019 — validações finais do Data Warehouse */

-- 1. Total da camada tratada versus tabela fato.
SELECT
    (SELECT COUNT(*) FROM staging.vra_tratada) AS total_tratada,
    (SELECT COUNT(*) FROM dw.fato_voo) AS total_fato;

-- 2. Validação das nove relações dimensionais.
SELECT 'Companhia aérea' AS dimensao, COUNT(*) AS problemas
FROM dw.fato_voo f
LEFT JOIN dw.dim_companhia_aerea d ON f.id_companhia = d.id_companhia
WHERE d.id_companhia IS NULL
UNION ALL
SELECT 'Aeroporto de origem', COUNT(*)
FROM dw.fato_voo f
LEFT JOIN dw.dim_aeroporto d ON f.id_aeroporto_origem = d.id_aeroporto
WHERE d.id_aeroporto IS NULL
UNION ALL
SELECT 'Aeroporto de destino', COUNT(*)
FROM dw.fato_voo f
LEFT JOIN dw.dim_aeroporto d ON f.id_aeroporto_destino = d.id_aeroporto
WHERE d.id_aeroporto IS NULL
UNION ALL
SELECT 'Tempo de partida', COUNT(*)
FROM dw.fato_voo f
LEFT JOIN dw.dim_tempo d ON f.id_tempo_partida = d.id_tempo
WHERE d.id_tempo IS NULL
UNION ALL
SELECT 'Tempo de chegada', COUNT(*)
FROM dw.fato_voo f
LEFT JOIN dw.dim_tempo d ON f.id_tempo_chegada = d.id_tempo
WHERE d.id_tempo IS NULL
UNION ALL
SELECT 'Situação do voo', COUNT(*)
FROM dw.fato_voo f
LEFT JOIN dw.dim_situacao_voo d ON f.id_situacao = d.id_situacao
WHERE f.id_situacao IS NOT NULL AND d.id_situacao IS NULL
UNION ALL
SELECT 'Justificativa', COUNT(*)
FROM dw.fato_voo f
LEFT JOIN dw.dim_justificativa d ON f.id_justificativa = d.id_justificativa
WHERE d.id_justificativa IS NULL
UNION ALL
SELECT 'Tipo de linha', COUNT(*)
FROM dw.fato_voo f
LEFT JOIN dw.dim_tipo_linha d ON f.id_tipo_linha = d.id_tipo_linha
WHERE f.id_tipo_linha IS NOT NULL AND d.id_tipo_linha IS NULL
UNION ALL
SELECT 'Equipamento', COUNT(*)
FROM dw.fato_voo f
LEFT JOIN dw.dim_equipamento d ON f.id_equipamento = d.id_equipamento
WHERE d.id_equipamento IS NULL;

-- 3. Verificar chaves naturais duplicadas nas dimensões.
SELECT companhia_icao, COUNT(*)
FROM dw.dim_companhia_aerea
GROUP BY companhia_icao
HAVING COUNT(*) > 1;

SELECT aeroporto_icao, COUNT(*)
FROM dw.dim_aeroporto
GROUP BY aeroporto_icao
HAVING COUNT(*) > 1;

SELECT data, COUNT(*)
FROM dw.dim_tempo
GROUP BY data
HAVING COUNT(*) > 1;

-- 4. Verificar se todos os voos têm quantidade_voos igual a 1.
SELECT COUNT(*) AS quantidade_incorreta
FROM dw.fato_voo
WHERE quantidade_voos <> 1;

-- 5. Resumo das métricas e flags na fato.
SELECT
    COUNT(*) AS total_voos,
    COUNT(*) FILTER (WHERE atraso_partida_min > 0) AS voos_com_atraso_partida,
    COUNT(*) FILTER (WHERE atraso_chegada_min > 0) AS voos_com_atraso_chegada,
    COUNT(*) FILTER (WHERE partida_atipica_flag) AS partidas_atipicas,
    COUNT(*) FILTER (WHERE chegada_atipica_flag) AS chegadas_atipicas,
    COUNT(*) FILTER (WHERE atraso_partida_min IS NULL) AS sem_atraso_partida_calculavel,
    COUNT(*) FILTER (WHERE atraso_chegada_min IS NULL) AS sem_atraso_chegada_calculavel
FROM dw.fato_voo;

-- 6. Verificar quantos registros têm metadados de proveniência ausentes.
-- No carregamento atual, esses campos foram importados como NULL.
SELECT
    COUNT(*) FILTER (WHERE arquivo_origem IS NULL) AS sem_arquivo_origem,
    COUNT(*) FILTER (WHERE linha_origem IS NULL) AS sem_linha_origem
FROM dw.fato_voo;
