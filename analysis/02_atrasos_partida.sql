-- A medida contratual vale zero para antecipações e pontualidade.
-- Horários desconhecidos são nulos e ficam fora da média e do denominador.
-- Partidas com atraso positivo entram no numerador, inclusive as atípicas.
WITH partidas AS (
    SELECT 'ETL' AS fluxo, ano_origem, atraso_partida_min
    FROM dw_etl.fato_voo
    WHERE ano_origem BETWEEN 2019 AND 2021

    UNION ALL

    SELECT 'ELT', ano_origem, atraso_partida_min
    FROM dw_elt.fato_voo
    WHERE ano_origem BETWEEN 2019 AND 2021
)
SELECT fluxo, ano_origem,
       count(atraso_partida_min) AS partidas_calculaveis,
       count(*) FILTER (WHERE atraso_partida_min > 0) AS partidas_atrasadas,
       round(100.0 * count(*) FILTER (WHERE atraso_partida_min > 0) /
             nullif(count(atraso_partida_min), 0), 2) AS percentual_atrasadas,
       round(avg(atraso_partida_min), 2) AS atraso_medio_min
FROM partidas
GROUP BY fluxo, ano_origem
ORDER BY ano_origem, fluxo;
