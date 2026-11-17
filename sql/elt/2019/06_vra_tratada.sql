-- 06 — Materialização da camada tratada com métricas de horário
-- Esta versão mantém atraso como NULL quando não há horário real para comparar.
-- A diferença assinada é preservada; atraso é limitado ao mínimo de zero.

CREATE TABLE staging.vra_tratada AS
WITH calculos AS (
    SELECT
        v.*,
        CASE
            WHEN v.partida_real IS NOT NULL AND v.partida_prevista IS NOT NULL
            THEN EXTRACT(EPOCH FROM (v.partida_real - v.partida_prevista)) / 60.0
            ELSE NULL
        END AS diferenca_partida_min,
        CASE
            WHEN v.chegada_real IS NOT NULL AND v.chegada_prevista IS NOT NULL
            THEN EXTRACT(EPOCH FROM (v.chegada_real - v.chegada_prevista)) / 60.0
            ELSE NULL
        END AS diferenca_chegada_min
    FROM staging.vra_2019 v
)
SELECT
    c.*,
    CASE
        WHEN c.diferenca_partida_min IS NULL THEN NULL
        ELSE GREATEST(c.diferenca_partida_min, 0)
    END AS atraso_partida_min,
    CASE
        WHEN c.diferenca_chegada_min IS NULL THEN NULL
        ELSE GREATEST(c.diferenca_chegada_min, 0)
    END AS atraso_chegada_min,
    COALESCE(ABS(c.diferenca_partida_min) > 1440, FALSE) AS partida_atipica_flag,
    COALESCE(ABS(c.diferenca_chegada_min) > 1440, FALSE) AS chegada_atipica_flag
FROM calculos c;

-- Resultado observado: 982926 linhas; 684 partidas e 690 chegadas atípicas.
