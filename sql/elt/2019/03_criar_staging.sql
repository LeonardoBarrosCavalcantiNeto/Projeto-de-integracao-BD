-- 03 — Criação e padronização da STAGING a partir da RAW
-- Este script pressupõe que raw.voos_2019 já foi carregada.
-- Não modifica a RAW.

CREATE TABLE staging.vra_2019 AS
WITH base AS (
    SELECT
        r.id_raw,
        2019::INTEGER AS ano_origem,
        r.arquivo_origem,
        r.linha_origem,

        UPPER(NULLIF(BTRIM(r.sigla_icao_empresa_aerea), '')) AS companhia_icao,
        NULLIF(BTRIM(r.empresa_aerea), '') AS companhia_nome,
        NULLIF(BTRIM(r.numero_voo), '') AS numero_voo,
        UPPER(NULLIF(BTRIM(r.codigo_di), '')) AS codigo_di,
        UPPER(NULLIF(BTRIM(r.codigo_tipo_linha), '')) AS tipo_linha,
        UPPER(NULLIF(BTRIM(r.modelo_equipamento), '')) AS modelo_equipamento,
        staging.try_integer(r.numero_assentos) AS numero_assentos,
        UPPER(NULLIF(BTRIM(r.sigla_icao_aeroporto_origem), '')) AS aeroporto_origem,
        NULLIF(BTRIM(r.descricao_aeroporto_origem), '') AS descricao_origem,
        staging.try_timestamp_br(r.partida_prevista) AS partida_prevista,
        staging.try_timestamp_br(r.partida_real) AS partida_real,
        UPPER(NULLIF(BTRIM(r.sigla_icao_aeroporto_destino), '')) AS aeroporto_destino,
        NULLIF(BTRIM(r.descricao_aeroporto_destino), '') AS descricao_destino,
        staging.try_timestamp_br(r.chegada_prevista) AS chegada_prevista,
        staging.try_timestamp_br(r.chegada_real) AS chegada_real,
        UPPER(NULLIF(BTRIM(r.situacao_voo), '')) AS situacao_voo,
        NULLIF(BTRIM(r.justificativa), '') AS justificativa,
        staging.try_date_iso(r.referencia) AS referencia,
        UPPER(NULLIF(BTRIM(r.situacao_partida), '')) AS situacao_partida,
        UPPER(NULLIF(BTRIM(r.situacao_chegada), '')) AS situacao_chegada,

        (NULLIF(BTRIM(r.partida_prevista), '') IS NULL) AS partida_prevista_ausente,
        (NULLIF(BTRIM(r.partida_prevista), '') IS NOT NULL
            AND staging.try_timestamp_br(r.partida_prevista) IS NULL) AS partida_prevista_invalida,
        (NULLIF(BTRIM(r.chegada_prevista), '') IS NULL) AS chegada_prevista_ausente,
        (NULLIF(BTRIM(r.chegada_prevista), '') IS NOT NULL
            AND staging.try_timestamp_br(r.chegada_prevista) IS NULL) AS chegada_prevista_invalida,
        (NULLIF(BTRIM(r.partida_real), '') IS NOT NULL
            AND staging.try_timestamp_br(r.partida_real) IS NULL) AS partida_real_invalida,
        (NULLIF(BTRIM(r.chegada_real), '') IS NOT NULL
            AND staging.try_timestamp_br(r.chegada_real) IS NULL) AS chegada_real_invalida,
        (NULLIF(BTRIM(r.referencia), '') IS NOT NULL
            AND staging.try_date_iso(r.referencia) IS NULL) AS referencia_invalida,
        (NULLIF(BTRIM(r.numero_assentos), '') IS NOT NULL
            AND staging.try_integer(r.numero_assentos) IS NULL) AS numero_assentos_invalido,
        (NULLIF(BTRIM(r.sigla_icao_aeroporto_origem), '') IS NULL) AS aeroporto_origem_ausente,
        (NULLIF(BTRIM(r.sigla_icao_aeroporto_destino), '') IS NULL) AS aeroporto_destino_ausente
    FROM raw.voos_2019 r
)
SELECT
    b.*,
    (
        b.companhia_icao IS NULL
        OR b.aeroporto_origem IS NULL
        OR b.aeroporto_destino IS NULL
        OR b.partida_prevista IS NULL
        OR b.chegada_prevista IS NULL
        OR b.partida_prevista_invalida
        OR b.chegada_prevista_invalida
    ) AS rejeicao_flag,
    NULLIF(CONCAT_WS('; ',
        CASE WHEN b.companhia_icao IS NULL THEN 'COMPANHIA_ICAO_AUSENTE' END,
        CASE WHEN b.aeroporto_origem IS NULL THEN 'AEROPORTO_ORIGEM_AUSENTE' END,
        CASE WHEN b.aeroporto_destino IS NULL THEN 'AEROPORTO_DESTINO_AUSENTE' END,
        CASE WHEN b.partida_prevista_ausente THEN 'PARTIDA_PREVISTA_AUSENTE' END,
        CASE WHEN b.partida_prevista_invalida THEN 'PARTIDA_PREVISTA_INVALIDA' END,
        CASE WHEN b.chegada_prevista_ausente THEN 'CHEGADA_PREVISTA_AUSENTE' END,
        CASE WHEN b.chegada_prevista_invalida THEN 'CHEGADA_PREVISTA_INVALIDA' END
    ), '') AS motivo_rejeicao,
    FALSE AS duplicata_exata_flag,
    FALSE AS duplicata_exata_extra
FROM base b;

ALTER TABLE staging.vra_2019
    ADD CONSTRAINT pk_vra_2019 PRIMARY KEY (id_raw);

-- Conferência inicial: deve haver 983414 linhas antes da deduplicação/rejeições.
-- SELECT COUNT(*) FROM staging.vra_2019;
