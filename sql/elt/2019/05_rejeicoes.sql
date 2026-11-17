-- 05 — Atualização das rejeições após a deduplicação
-- Campos obrigatórios para elegibilidade na Fato: companhia ICAO,
-- aeroporto origem/destino, partida prevista e chegada prevista.

BEGIN;

UPDATE staging.vra_2019
SET
    rejeicao_flag = (
        NULLIF(BTRIM(companhia_icao), '') IS NULL
        OR NULLIF(BTRIM(aeroporto_origem), '') IS NULL
        OR NULLIF(BTRIM(aeroporto_destino), '') IS NULL
        OR partida_prevista IS NULL
        OR chegada_prevista IS NULL
        OR COALESCE(partida_prevista_invalida, FALSE)
        OR COALESCE(chegada_prevista_invalida, FALSE)
    ),
    motivo_rejeicao = NULLIF(CONCAT_WS('; ',
        CASE WHEN NULLIF(BTRIM(companhia_icao), '') IS NULL
            THEN 'COMPANHIA_ICAO_AUSENTE' END,
        CASE WHEN NULLIF(BTRIM(aeroporto_origem), '') IS NULL
            THEN 'AEROPORTO_ORIGEM_AUSENTE' END,
        CASE WHEN NULLIF(BTRIM(aeroporto_destino), '') IS NULL
            THEN 'AEROPORTO_DESTINO_AUSENTE' END,
        CASE WHEN partida_prevista IS NULL
            THEN 'PARTIDA_PREVISTA_AUSENTE' END,
        CASE WHEN chegada_prevista IS NULL
            THEN 'CHEGADA_PREVISTA_AUSENTE' END,
        CASE WHEN COALESCE(partida_prevista_invalida, FALSE)
            THEN 'PARTIDA_PREVISTA_INVALIDA' END,
        CASE WHEN COALESCE(chegada_prevista_invalida, FALSE)
            THEN 'CHEGADA_PREVISTA_INVALIDA' END
    ), '')
WHERE id_raw IS NOT NULL;

CREATE TABLE staging.vra_rejeicoes AS
SELECT *
FROM staging.vra_2019
WHERE FALSE;

INSERT INTO staging.vra_rejeicoes
SELECT *
FROM staging.vra_2019
WHERE rejeicao_flag IS TRUE;

DELETE FROM staging.vra_2019
WHERE rejeicao_flag IS TRUE;

COMMIT;

-- Resultado observado: 18 rejeições e 982926 linhas restantes na STAGING.
