-- 04 — Deduplicação com auditoria
-- IMPORTANTE: esta versão reproduz a classificação feita na STAGING canônica,
-- particionando pelos 20 atributos padronizados. O desempate foi id_raw crescente.
-- Para aderência integral ao contrato atualizado, validar depois os grupos usando
-- os 20 valores originais da RAW e arquivo_origem/linha_origem preenchidos.

BEGIN;

WITH classificacao AS (
    SELECT
        id_raw,
        COUNT(*) OVER (
            PARTITION BY
                companhia_icao,
                companhia_nome,
                numero_voo,
                codigo_di,
                tipo_linha,
                modelo_equipamento,
                numero_assentos,
                aeroporto_origem,
                descricao_origem,
                partida_prevista,
                partida_real,
                aeroporto_destino,
                descricao_destino,
                chegada_prevista,
                chegada_real,
                situacao_voo,
                justificativa,
                referencia,
                situacao_partida,
                situacao_chegada
        ) AS quantidade_no_grupo,
        ROW_NUMBER() OVER (
            PARTITION BY
                companhia_icao,
                companhia_nome,
                numero_voo,
                codigo_di,
                tipo_linha,
                modelo_equipamento,
                numero_assentos,
                aeroporto_origem,
                descricao_origem,
                partida_prevista,
                partida_real,
                aeroporto_destino,
                descricao_destino,
                chegada_prevista,
                chegada_real,
                situacao_voo,
                justificativa,
                referencia,
                situacao_partida,
                situacao_chegada
            ORDER BY id_raw
        ) AS ordem_no_grupo
    FROM staging.vra_2019
)
UPDATE staging.vra_2019 AS v
SET
    duplicata_exata_flag = (c.quantidade_no_grupo > 1),
    duplicata_exata_extra = (c.quantidade_no_grupo > 1 AND c.ordem_no_grupo > 1)
FROM classificacao AS c
WHERE v.id_raw = c.id_raw;

CREATE TABLE staging.vra_duplicatas_excluidas AS
SELECT *
FROM staging.vra_2019
WHERE FALSE;

INSERT INTO staging.vra_duplicatas_excluidas
SELECT *
FROM staging.vra_2019
WHERE duplicata_exata_extra IS TRUE;

DELETE FROM staging.vra_2019
WHERE duplicata_exata_extra IS TRUE;

COMMIT;

-- Resultados observados: 444 grupos, 914 linhas envolvidas, 470 excedentes.
-- A tabela de auditoria deve conter 470 linhas; a STAGING deve ficar com 982944.
