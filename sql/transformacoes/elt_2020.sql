
-- ELT 2020. Executar depois da carga bruta; nunca altera os 20 campos brutos.
CREATE OR REPLACE FUNCTION elt_2020.limpar_texto(valor TEXT)
RETURNS TEXT LANGUAGE SQL IMMUTABLE STRICT AS $$
    SELECT NULLIF(regexp_replace(valor, '^\s+|\s+$', '', 'g'), '');
$$;

CREATE OR REPLACE FUNCTION elt_2020.datahora_segura(valor TEXT)
RETURNS TIMESTAMP LANGUAGE plpgsql IMMUTABLE STRICT AS $$
BEGIN
    IF valor !~ '^[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}$' THEN
        RETURN NULL;
    END IF;
    -- make_timestamp valida o calendário; não ajusta 31/02 silenciosamente.
    IF substring(valor,12,2)::INTEGER > 23 OR substring(valor,15,2)::INTEGER > 59 THEN
        RETURN NULL;
    END IF;
    RETURN make_timestamp(substring(valor,7,4)::INTEGER, substring(valor,4,2)::INTEGER,
                          substring(valor,1,2)::INTEGER, substring(valor,12,2)::INTEGER,
                          substring(valor,15,2)::INTEGER, 0);
EXCEPTION WHEN datetime_field_overflow OR invalid_datetime_format OR numeric_value_out_of_range THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION elt_2020.data_segura(valor TEXT)
RETURNS DATE LANGUAGE plpgsql IMMUTABLE STRICT AS $$
BEGIN
    IF valor !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN RETURN NULL; END IF;
    RETURN make_date(substring(valor,1,4)::INTEGER, substring(valor,6,2)::INTEGER,
                     substring(valor,9,2)::INTEGER);
EXCEPTION WHEN datetime_field_overflow OR invalid_datetime_format OR numeric_value_out_of_range THEN
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION elt_2020.inteiro_seguro(valor TEXT)
RETURNS INTEGER LANGUAGE plpgsql IMMUTABLE STRICT AS $$
BEGIN
    IF valor !~ '^[0-9]+$' THEN RETURN NULL; END IF;
    RETURN valor::INTEGER;
EXCEPTION WHEN numeric_value_out_of_range THEN RETURN NULL;
END;
$$;

DROP TABLE IF EXISTS elt_2020.resumo_qualidade;
DROP TABLE IF EXISTS elt_2020.vra_anomalias;
DROP TABLE IF EXISTS elt_2020.vra_tratada;
DROP TABLE IF EXISTS elt_2020.vra_rejeicoes;
DROP TABLE IF EXISTS elt_2020.vra_duplicatas_excluidas;
DROP TABLE IF EXISTS elt_2020.vra_avaliada;
DROP TABLE IF EXISTS elt_2020.vra_convertida;
DROP TABLE IF EXISTS elt_2020.vra_classificada;

CREATE TABLE elt_2020.vra_classificada AS
SELECT b.*,
       ROW_NUMBER() OVER w AS ocorrencia_num,
       FIRST_VALUE(arquivo_origem) OVER w AS arquivo_preservado,
       FIRST_VALUE(linha_origem) OVER w AS linha_preservada
FROM elt_2020.vra_bruta b
WINDOW w AS (
    PARTITION BY "Sigla ICAO Empresa Aérea" COLLATE "C", "Empresa Aérea" COLLATE "C", "Número Voo" COLLATE "C", "Código DI" COLLATE "C", "Código Tipo Linha" COLLATE "C", "Modelo Equipamento" COLLATE "C", "Número de Assentos" COLLATE "C", "Sigla ICAO Aeroporto Origem" COLLATE "C", "Descrição Aeroporto Origem" COLLATE "C", "Partida Prevista" COLLATE "C", "Partida Real" COLLATE "C", "Sigla ICAO Aeroporto Destino" COLLATE "C", "Descrição Aeroporto Destino" COLLATE "C", "Chegada Prevista" COLLATE "C", "Chegada Real" COLLATE "C", "Situação Voo" COLLATE "C", "Justificativa" COLLATE "C", "Referência" COLLATE "C", "Situação Partida" COLLATE "C", "Situação Chegada" COLLATE "C"
    ORDER BY arquivo_origem COLLATE "C", linha_origem
);

CREATE TABLE elt_2020.vra_duplicatas_excluidas AS
SELECT * FROM elt_2020.vra_classificada WHERE ocorrencia_num > 1;

-- Só após identificar duplicatas EXATAS é feita a padronização.
CREATE TABLE elt_2020.vra_convertida AS
SELECT UPPER(elt_2020.limpar_texto("Sigla ICAO Empresa Aérea")) AS companhia_icao,
       elt_2020.limpar_texto("Empresa Aérea") AS companhia_nome,
       elt_2020.limpar_texto("Número Voo") AS numero_voo,
       UPPER(elt_2020.limpar_texto("Código DI")) AS codigo_di,
       UPPER(elt_2020.limpar_texto("Código Tipo Linha")) AS tipo_linha,
       UPPER(elt_2020.limpar_texto("Modelo Equipamento")) AS modelo_equipamento,
       elt_2020.inteiro_seguro(elt_2020.limpar_texto("Número de Assentos")) AS numero_assentos,
       UPPER(elt_2020.limpar_texto("Sigla ICAO Aeroporto Origem")) AS aeroporto_origem,
       elt_2020.limpar_texto("Descrição Aeroporto Origem") AS descricao_origem,
       elt_2020.datahora_segura(elt_2020.limpar_texto("Partida Prevista")) AS partida_prevista,
       elt_2020.datahora_segura(elt_2020.limpar_texto("Partida Real")) AS partida_real,
       UPPER(elt_2020.limpar_texto("Sigla ICAO Aeroporto Destino")) AS aeroporto_destino,
       elt_2020.limpar_texto("Descrição Aeroporto Destino") AS descricao_destino,
       elt_2020.datahora_segura(elt_2020.limpar_texto("Chegada Prevista")) AS chegada_prevista,
       elt_2020.datahora_segura(elt_2020.limpar_texto("Chegada Real")) AS chegada_real,
       UPPER(elt_2020.limpar_texto("Situação Voo")) AS situacao_voo,
       elt_2020.limpar_texto("Justificativa") AS justificativa,
       elt_2020.data_segura(elt_2020.limpar_texto("Referência")) AS referencia,
       UPPER(elt_2020.limpar_texto("Situação Partida")) AS situacao_partida,
       UPPER(elt_2020.limpar_texto("Situação Chegada")) AS situacao_chegada,
       arquivo_origem, linha_origem, 2020::INTEGER AS ano_origem
FROM elt_2020.vra_classificada
WHERE ocorrencia_num = 1;

CREATE TABLE elt_2020.vra_avaliada AS
SELECT c.*, ARRAY_REMOVE(ARRAY[
    CASE WHEN companhia_icao IS NULL THEN 'COMPANHIA_AUSENTE' END,
    CASE WHEN aeroporto_origem IS NULL THEN 'AEROPORTO_ORIGEM_AUSENTE' END,
    CASE WHEN aeroporto_destino IS NULL THEN 'AEROPORTO_DESTINO_AUSENTE' END,
    CASE WHEN partida_prevista IS NULL THEN
        CASE WHEN elt_2020.limpar_texto(b."Partida Prevista") IS NULL
             THEN 'PARTIDA_PREVISTA_AUSENTE' ELSE 'PARTIDA_PREVISTA_INVALIDA' END END,
    CASE WHEN chegada_prevista IS NULL THEN
        CASE WHEN elt_2020.limpar_texto(b."Chegada Prevista") IS NULL
             THEN 'CHEGADA_PREVISTA_AUSENTE' ELSE 'CHEGADA_PREVISTA_INVALIDA' END END
], NULL) AS motivos_rejeicao
FROM elt_2020.vra_convertida c
JOIN elt_2020.vra_bruta b USING (arquivo_origem, linha_origem);

-- Preserva todos os campos originais e todos os motivos (uma linha por registro).
CREATE TABLE elt_2020.vra_rejeicoes AS
SELECT b.*, a.motivos_rejeicao
FROM elt_2020.vra_bruta b
JOIN elt_2020.vra_avaliada a USING (arquivo_origem, linha_origem)
WHERE cardinality(a.motivos_rejeicao) > 0;

CREATE TABLE elt_2020.vra_tratada AS
WITH medidas AS (
    SELECT a.*,
           EXTRACT(EPOCH FROM (partida_real - partida_prevista))/60 AS diferenca_partida_min,
           EXTRACT(EPOCH FROM (chegada_real - chegada_prevista))/60 AS diferenca_chegada_min
    FROM elt_2020.vra_avaliada a
    WHERE cardinality(motivos_rejeicao) = 0
)
SELECT *,
       CASE WHEN diferenca_partida_min IS NOT NULL THEN GREATEST(diferenca_partida_min,0) END AS atraso_partida_min,
       CASE WHEN diferenca_chegada_min IS NOT NULL THEN GREATEST(diferenca_chegada_min,0) END AS atraso_chegada_min,
       COALESCE(ABS(diferenca_partida_min)>1440,FALSE) AS partida_atipica_flag,
       COALESCE(ABS(diferenca_chegada_min)>1440,FALSE) AS chegada_atipica_flag
FROM medidas;

ALTER TABLE elt_2020.vra_tratada DROP COLUMN motivos_rejeicao;
ALTER TABLE elt_2020.vra_tratada ADD PRIMARY KEY (arquivo_origem, linha_origem);
ALTER TABLE elt_2020.vra_rejeicoes ADD PRIMARY KEY (arquivo_origem, linha_origem);

-- Campos opcionais inválidos não excluem o voo; ficam registrados para auditoria.
CREATE TABLE elt_2020.vra_anomalias AS
SELECT c.arquivo_origem, c.linha_origem, v.campo, v.valor_original,
       'VALOR_OPCIONAL_INVALIDO'::TEXT AS motivo
FROM elt_2020.vra_convertida c
JOIN elt_2020.vra_bruta b USING (arquivo_origem, linha_origem)
CROSS JOIN LATERAL (VALUES
    ('Partida Real', b."Partida Real", c.partida_real IS NULL),
    ('Chegada Real', b."Chegada Real", c.chegada_real IS NULL),
    ('Número de Assentos', b."Número de Assentos", c.numero_assentos IS NULL),
    ('Referência', b."Referência", c.referencia IS NULL)
) AS v(campo, valor_original, falhou)
WHERE elt_2020.limpar_texto(v.valor_original) IS NOT NULL AND v.falhou;

INSERT INTO elt_2020.vra_anomalias
SELECT arquivo_origem, linha_origem, 'Referência', referencia::TEXT, 'REFERENCIA_FORA_DE_2020'
FROM elt_2020.vra_convertida
WHERE referencia IS NOT NULL AND EXTRACT(YEAR FROM referencia) <> 2020;

CREATE TABLE elt_2020.resumo_qualidade AS
SELECT
    (SELECT COUNT(*) FROM elt_2020.vra_bruta) AS bruta,
    (SELECT COUNT(*) FROM elt_2020.vra_duplicatas_excluidas) AS duplicatas_excedentes,
    (SELECT COUNT(*) FROM elt_2020.vra_rejeicoes) AS rejeicoes,
    (SELECT COUNT(*) FROM elt_2020.vra_tratada) AS tratada,
    (SELECT COUNT(*) FROM elt_2020.vra_tratada WHERE partida_atipica_flag) AS partidas_atipicas,
    (SELECT COUNT(*) FROM elt_2020.vra_tratada WHERE chegada_atipica_flag) AS chegadas_atipicas,
    (SELECT COUNT(*) FROM elt_2020.vra_tratada WHERE partida_real IS NULL) AS partidas_reais_nulas,
    (SELECT COUNT(*) FROM elt_2020.vra_tratada WHERE chegada_real IS NULL) AS chegadas_reais_nulas,
    (SELECT COUNT(*) FROM elt_2020.vra_anomalias) AS ocorrencias_anomalias,
    CURRENT_TIMESTAMP AS executado_em;
