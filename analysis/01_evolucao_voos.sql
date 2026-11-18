-- Volume de ocorrências válidas antes e durante a pandemia, por ano do CSV.
-- Cada DW contém o mesmo conjunto de ocorrências. Compare os fluxos sem somá-los.
WITH totais AS (
    SELECT 'ETL' AS fluxo, ano_origem, count(*) AS ocorrencias_validas
    FROM dw_etl.fato_voo
    WHERE ano_origem BETWEEN 2019 AND 2021
    GROUP BY ano_origem

    UNION ALL

    SELECT 'ELT', ano_origem, count(*)
    FROM dw_elt.fato_voo
    WHERE ano_origem BETWEEN 2019 AND 2021
    GROUP BY ano_origem
)
-- A variação fica nula quando não há um ano anterior no recorte.
SELECT atual.fluxo, atual.ano_origem, atual.ocorrencias_validas,
       anterior.ano_origem AS ano_base,
       round(100.0 * (atual.ocorrencias_validas - anterior.ocorrencias_validas) /
             nullif(anterior.ocorrencias_validas, 0), 2) AS variacao_pct
FROM totais AS atual
LEFT JOIN totais AS anterior
    ON anterior.fluxo = atual.fluxo AND anterior.ano_origem = atual.ano_origem - 1
ORDER BY atual.ano_origem, atual.fluxo;
