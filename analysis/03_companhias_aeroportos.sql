-- Companhias com mais ocorrências válidas, por ano e fluxo.
-- Os rankings exibem dez posições, com todos os empates.
WITH companhias AS (
    SELECT 'ETL' AS fluxo, f.ano_origem, c.companhia_icao, c.companhia_nome,
           count(*) AS ocorrencias
    FROM dw_etl.fato_voo AS f
    JOIN dw_etl.dim_companhia_aerea AS c USING (id_companhia)
    WHERE f.ano_origem BETWEEN 2019 AND 2021
    GROUP BY f.ano_origem, c.companhia_icao, c.companhia_nome

    UNION ALL

    SELECT 'ELT', f.ano_origem, c.companhia_icao, c.companhia_nome, count(*)
    FROM dw_elt.fato_voo AS f
    JOIN dw_elt.dim_companhia_aerea AS c USING (id_companhia)
    WHERE f.ano_origem BETWEEN 2019 AND 2021
    GROUP BY f.ano_origem, c.companhia_icao, c.companhia_nome
),
ranking AS (
    SELECT *, dense_rank() OVER (PARTITION BY fluxo, ano_origem ORDER BY ocorrencias DESC) AS posicao
    FROM companhias
)
SELECT fluxo, ano_origem, posicao, companhia_icao, companhia_nome, ocorrencias
FROM ranking
WHERE posicao <= 10
ORDER BY ano_origem, fluxo, posicao, companhia_icao;

-- Aeroportos com mais movimentos registrados, por ano, fluxo e tipo de movimento.
-- Cada ocorrência contribui uma partida na origem e uma chegada no destino.
-- Estas contagens descrevem os papéis no registro do voo.
WITH aeroportos AS (
    SELECT 'ETL' AS fluxo, f.ano_origem, a.aeroporto_icao, a.descricao_aeroporto,
           m.movimento, count(*) AS ocorrencias
    FROM dw_etl.fato_voo AS f
    CROSS JOIN LATERAL (VALUES
        (f.id_aeroporto_origem, 'partida'), (f.id_aeroporto_destino, 'chegada')
    ) AS m(id_aeroporto, movimento)
    JOIN dw_etl.dim_aeroporto AS a USING (id_aeroporto)
    WHERE f.ano_origem BETWEEN 2019 AND 2021
    GROUP BY f.ano_origem, a.aeroporto_icao, a.descricao_aeroporto, m.movimento

    UNION ALL

    SELECT 'ELT', f.ano_origem, a.aeroporto_icao, a.descricao_aeroporto, m.movimento, count(*)
    FROM dw_elt.fato_voo AS f
    CROSS JOIN LATERAL (VALUES
        (f.id_aeroporto_origem, 'partida'), (f.id_aeroporto_destino, 'chegada')
    ) AS m(id_aeroporto, movimento)
    JOIN dw_elt.dim_aeroporto AS a USING (id_aeroporto)
    WHERE f.ano_origem BETWEEN 2019 AND 2021
    GROUP BY f.ano_origem, a.aeroporto_icao, a.descricao_aeroporto, m.movimento
),
ranking AS (
    SELECT *, dense_rank() OVER (
        PARTITION BY fluxo, ano_origem, movimento ORDER BY ocorrencias DESC
    ) AS posicao
    FROM aeroportos
)
SELECT fluxo, ano_origem, movimento, posicao, aeroporto_icao, descricao_aeroporto, ocorrencias
FROM ranking
WHERE posicao <= 10
ORDER BY ano_origem, fluxo, movimento, posicao, aeroporto_icao;
