-- Cada fluxo representa o mesmo conjunto de ocorrências em seu próprio DW.
-- ano_origem identifica o conjunto CSV, mesmo que a data prevista caia em outro ano.
SELECT 'ETL' AS fluxo, ano_origem, count(*) AS ocorrencias
FROM dw_etl.fato_voo GROUP BY ano_origem
UNION ALL
SELECT 'ELT', ano_origem, count(*) FROM dw_elt.fato_voo GROUP BY ano_origem
ORDER BY ano_origem, fluxo;

-- A diferença com sinal distingue atrasos, antecipações e pontualidade.
-- Horários desconhecidos ficam fora do denominador do percentual de atrasos.
WITH fatos AS (
    SELECT 'ETL' AS fluxo, ano_origem, diferenca_partida_min, diferenca_chegada_min,
           partida_atipica_flag, chegada_atipica_flag
    FROM dw_etl.fato_voo
    UNION ALL
    SELECT 'ELT', ano_origem, diferenca_partida_min, diferenca_chegada_min,
           partida_atipica_flag, chegada_atipica_flag
    FROM dw_elt.fato_voo
)
SELECT fluxo, ano_origem, operacao,
       count(*) FILTER (WHERE diferenca > 0) AS atrasos,
       count(*) FILTER (WHERE diferenca < 0) AS antecipacoes,
       count(*) FILTER (WHERE diferenca = 0) AS pontuais,
       count(*) FILTER (WHERE diferenca IS NULL) AS horarios_desconhecidos,
       count(*) FILTER (WHERE atipica) AS horarios_atipicos,
       round(100.0 * count(*) FILTER (WHERE diferenca > 0) /
             nullif(count(diferenca), 0), 2) AS percentual_atrasados
FROM fatos
CROSS JOIN LATERAL (VALUES
    ('partida', diferenca_partida_min, partida_atipica_flag),
    ('chegada', diferenca_chegada_min, chegada_atipica_flag)
) AS horarios(operacao, diferenca, atipica)
GROUP BY fluxo, ano_origem, operacao
ORDER BY ano_origem, operacao, fluxo;

SELECT 'ETL' AS fluxo, f.ano_origem, s.situacao_voo, count(*) AS ocorrencias
FROM dw_etl.fato_voo f LEFT JOIN dw_etl.dim_situacao_voo s USING (id_situacao)
GROUP BY f.ano_origem, s.situacao_voo
UNION ALL
SELECT 'ELT', f.ano_origem, s.situacao_voo, count(*)
FROM dw_elt.fato_voo f LEFT JOIN dw_elt.dim_situacao_voo s USING (id_situacao)
GROUP BY f.ano_origem, s.situacao_voo
ORDER BY ano_origem, ocorrencias DESC, situacao_voo, fluxo;

SELECT 'ETL' AS fluxo, f.ano_origem, c.companhia_icao, c.companhia_nome, count(*) AS ocorrencias
FROM dw_etl.fato_voo f JOIN dw_etl.dim_companhia_aerea c USING (id_companhia)
GROUP BY f.ano_origem, c.companhia_icao, c.companhia_nome
UNION ALL
SELECT 'ELT', f.ano_origem, c.companhia_icao, c.companhia_nome, count(*)
FROM dw_elt.fato_voo f JOIN dw_elt.dim_companhia_aerea c USING (id_companhia)
GROUP BY f.ano_origem, c.companhia_icao, c.companhia_nome
ORDER BY ano_origem, ocorrencias DESC, companhia_icao, fluxo;

-- Cada ocorrência contribui uma vez como origem e uma vez como destino.
SELECT 'ETL' AS fluxo, f.ano_origem, a.aeroporto_icao, a.descricao_aeroporto, m.papel,
       count(*) AS ocorrencias
FROM dw_etl.fato_voo f
CROSS JOIN LATERAL (VALUES
    (f.id_aeroporto_origem, 'origem'), (f.id_aeroporto_destino, 'destino')
) AS m(id_aeroporto, papel)
JOIN dw_etl.dim_aeroporto a USING (id_aeroporto)
GROUP BY f.ano_origem, a.aeroporto_icao, a.descricao_aeroporto, m.papel
UNION ALL
SELECT 'ELT', f.ano_origem, a.aeroporto_icao, a.descricao_aeroporto, m.papel, count(*)
FROM dw_elt.fato_voo f
CROSS JOIN LATERAL (VALUES
    (f.id_aeroporto_origem, 'origem'), (f.id_aeroporto_destino, 'destino')
) AS m(id_aeroporto, papel)
JOIN dw_elt.dim_aeroporto a USING (id_aeroporto)
GROUP BY f.ano_origem, a.aeroporto_icao, a.descricao_aeroporto, m.papel
ORDER BY ano_origem, papel, ocorrencias DESC, aeroporto_icao, fluxo;
