-- 08 — Consultas de validação

-- Visão geral das quatro contagens principais.
SELECT
    (SELECT COUNT(*) FROM raw.voos_2019) AS raw,
    (SELECT COUNT(*) FROM staging.vra_2019) AS staging,
    (SELECT COUNT(*) FROM staging.vra_duplicatas_excluidas) AS duplicatas_excluidas,
    (SELECT COUNT(*) FROM staging.vra_rejeicoes) AS rejeicoes,
    (SELECT COUNT(*) FROM staging.vra_tratada) AS total_tratada;

-- Indicadores temporais da camada tratada.
SELECT
    COUNT(*) AS total_tratada,
    COUNT(*) FILTER (WHERE partida_atipica_flag) AS partidas_atipicas,
    COUNT(*) FILTER (WHERE chegada_atipica_flag) AS chegadas_atipicas,
    COUNT(*) FILTER (WHERE atraso_partida_min > 0) AS voos_com_atraso_partida,
    COUNT(*) FILTER (WHERE atraso_chegada_min > 0) AS voos_com_atraso_chegada
FROM staging.vra_tratada;

-- Quantidade de registros remanescentes marcados como pertencentes a grupo duplicado.
-- Após remover os excedentes, espera-se manter um representante por grupo.
SELECT COUNT(*) AS representantes_de_grupos_duplicados
FROM staging.vra_2019
WHERE duplicata_exata_flag IS TRUE;

-- Conferência dos metadados de proveniência: no carregamento executado ficaram NULL.
SELECT
    COUNT(*) FILTER (WHERE arquivo_origem IS NULL) AS sem_arquivo_origem,
    COUNT(*) FILTER (WHERE linha_origem IS NULL) AS sem_linha_origem
FROM raw.voos_2019;
