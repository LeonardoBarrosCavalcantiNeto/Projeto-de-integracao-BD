/* =====================================================================
   VRA / ANAC 2019 — DATA WAREHOUSE (ELT)
   Criação e carga das 7 dimensões e da tabela fato.

   Pré-requisitos:
     - PostgreSQL
     - schema staging já criado
     - staging.vra_tratada já preenchida e validada

   Importante:
     - Script não apaga tabelas nem schemas.
     - Dimensões usam chaves substitutas.
     - A tabela fato tem uma linha por id_raw elegível.
     - arquivo_origem e linha_origem são mantidos, mas podem estar NULL
       na carga atual conforme a limitação documentada da ingestão.
   ===================================================================== */

-- Schema compartilhado: executar sql/database/00_schemas.sql antes.

/* ---------------------------------------------------------------------
   0. PRÉ-VALIDAÇÃO DOS DADOS E CONFLITOS DESCRITIVOS
   --------------------------------------------------------------------- */

DO $$
BEGIN
    IF to_regclass('staging.vra_tratada') IS NULL THEN
        RAISE EXCEPTION 'A tabela staging.vra_tratada não existe. Execute primeiro o processo de Transform.';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM staging.vra_tratada) THEN
        RAISE EXCEPTION 'A tabela staging.vra_tratada está vazia.';
    END IF;

    -- Um código ICAO de companhia não pode ter nomes conflitantes.
    IF EXISTS (
        SELECT 1
        FROM staging.vra_tratada
        WHERE NULLIF(BTRIM(companhia_icao), '') IS NOT NULL
          AND NULLIF(BTRIM(companhia_nome), '') IS NOT NULL
        GROUP BY BTRIM(companhia_icao)
        HAVING COUNT(DISTINCT BTRIM(companhia_nome)) > 1
    ) THEN
        RAISE EXCEPTION 'Foram encontrados nomes conflitantes para uma mesma companhia ICAO. Resolva antes de carregar o DW.';
    END IF;

    -- Um código ICAO de aeroporto não pode ter descrições conflitantes.
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT BTRIM(aeroporto_origem) AS aeroporto_icao,
                   NULLIF(BTRIM(descricao_origem), '') AS descricao
            FROM staging.vra_tratada
            WHERE NULLIF(BTRIM(aeroporto_origem), '') IS NOT NULL

            UNION ALL

            SELECT BTRIM(aeroporto_destino) AS aeroporto_icao,
                   NULLIF(BTRIM(descricao_destino), '') AS descricao
            FROM staging.vra_tratada
            WHERE NULLIF(BTRIM(aeroporto_destino), '') IS NOT NULL
        ) a
        WHERE a.descricao IS NOT NULL
        GROUP BY a.aeroporto_icao
        HAVING COUNT(DISTINCT a.descricao) > 1
    ) THEN
        RAISE EXCEPTION 'Foram encontradas descrições conflitantes para um mesmo aeroporto ICAO. Resolva antes de carregar o DW.';
    END IF;
END $$;

/* ---------------------------------------------------------------------
   1. DIM_TEMPO
   Uma dimensão compartilhada pelos papéis de partida e chegada.
   id_tempo no formato AAAAMMDD.
   dia_semana: 1 = segunda-feira ... 7 = domingo.
   --------------------------------------------------------------------- */

-- Estrutura movida para sql/database/10_criacao_dw.sql.

INSERT INTO dw.dim_tempo (
    id_tempo, data, ano, trimestre, mes, dia, dia_semana
)
SELECT
    TO_CHAR(d.data, 'YYYYMMDD')::INTEGER,
    d.data,
    EXTRACT(YEAR FROM d.data)::INTEGER,
    EXTRACT(QUARTER FROM d.data)::INTEGER,
    EXTRACT(MONTH FROM d.data)::INTEGER,
    EXTRACT(DAY FROM d.data)::INTEGER,
    EXTRACT(ISODOW FROM d.data)::INTEGER
FROM (
    SELECT partida_prevista::DATE AS data
    FROM staging.vra_tratada
    WHERE partida_prevista IS NOT NULL

    UNION

    SELECT chegada_prevista::DATE AS data
    FROM staging.vra_tratada
    WHERE chegada_prevista IS NOT NULL
) d
ON CONFLICT (data) DO NOTHING;

/* ---------------------------------------------------------------------
   2. DIM_COMPANHIA_AEREA
   companhia_icao é a chave natural.
   --------------------------------------------------------------------- */

-- Estrutura movida para sql/database/10_criacao_dw.sql.

INSERT INTO dw.dim_companhia_aerea (
    companhia_icao, companhia_nome
)
SELECT
    BTRIM(companhia_icao),
    MAX(NULLIF(BTRIM(companhia_nome), ''))
FROM staging.vra_tratada
WHERE NULLIF(BTRIM(companhia_icao), '') IS NOT NULL
GROUP BY BTRIM(companhia_icao)
ON CONFLICT (companhia_icao) DO NOTHING;

/* ---------------------------------------------------------------------
   3. DIM_AEROPORTO
   Uma única dimensão para origem e destino.
   --------------------------------------------------------------------- */

-- Estrutura movida para sql/database/10_criacao_dw.sql.

INSERT INTO dw.dim_aeroporto (
    aeroporto_icao, descricao_aeroporto
)
SELECT
    a.aeroporto_icao,
    MAX(a.descricao_aeroporto)
FROM (
    SELECT
        NULLIF(BTRIM(aeroporto_origem), '') AS aeroporto_icao,
        NULLIF(BTRIM(descricao_origem), '') AS descricao_aeroporto
    FROM staging.vra_tratada

    UNION ALL

    SELECT
        NULLIF(BTRIM(aeroporto_destino), '') AS aeroporto_icao,
        NULLIF(BTRIM(descricao_destino), '') AS descricao_aeroporto
    FROM staging.vra_tratada
) a
WHERE a.aeroporto_icao IS NOT NULL
GROUP BY a.aeroporto_icao
ON CONFLICT (aeroporto_icao) DO NOTHING;

/* ---------------------------------------------------------------------
   4. DIM_SITUACAO_VOO
   Mantém REALIZADO, CANCELADO e NÃO INFORMADO distintos.
   --------------------------------------------------------------------- */

-- Estrutura movida para sql/database/10_criacao_dw.sql.

INSERT INTO dw.dim_situacao_voo (situacao_voo)
SELECT DISTINCT BTRIM(situacao_voo)
FROM staging.vra_tratada
WHERE NULLIF(BTRIM(situacao_voo), '') IS NOT NULL
ON CONFLICT (situacao_voo) DO NOTHING;

/* ---------------------------------------------------------------------
   5. DIM_JUSTIFICATIVA
   Chave 0 reservada para DESCONHECIDO.
   --------------------------------------------------------------------- */

-- Estrutura movida para sql/database/10_criacao_dw.sql.

INSERT INTO dw.dim_justificativa (
    id_justificativa, justificativa
)
OVERRIDING SYSTEM VALUE
VALUES (0, 'DESCONHECIDO')
ON CONFLICT DO NOTHING;

INSERT INTO dw.dim_justificativa (justificativa)
SELECT DISTINCT BTRIM(justificativa)
FROM staging.vra_tratada
WHERE NULLIF(BTRIM(justificativa), '') IS NOT NULL
ON CONFLICT (justificativa) DO NOTHING;

/* ---------------------------------------------------------------------
   6. DIM_TIPO_LINHA
   Preserva os códigos sem atribuir significado não documentado.
   --------------------------------------------------------------------- */

-- Estrutura movida para sql/database/10_criacao_dw.sql.

INSERT INTO dw.dim_tipo_linha (tipo_linha)
SELECT DISTINCT UPPER(BTRIM(tipo_linha))
FROM staging.vra_tratada
WHERE NULLIF(BTRIM(tipo_linha), '') IS NOT NULL
ON CONFLICT (tipo_linha) DO NOTHING;

/* ---------------------------------------------------------------------
   7. DIM_EQUIPAMENTO
   Chave 0 reservada para DESCONHECIDO.
   --------------------------------------------------------------------- */

-- Estrutura movida para sql/database/10_criacao_dw.sql.

INSERT INTO dw.dim_equipamento (
    id_equipamento, modelo_equipamento
)
OVERRIDING SYSTEM VALUE
VALUES (0, 'DESCONHECIDO')
ON CONFLICT DO NOTHING;

INSERT INTO dw.dim_equipamento (modelo_equipamento)
SELECT DISTINCT UPPER(BTRIM(modelo_equipamento))
FROM staging.vra_tratada
WHERE NULLIF(BTRIM(modelo_equipamento), '') IS NOT NULL
ON CONFLICT (modelo_equipamento) DO NOTHING;

/* ---------------------------------------------------------------------
   8. PRÉ-VALIDAÇÃO DOS RELACIONAMENTOS
   Evita perder silenciosamente uma categoria ou chave dimensional.
   --------------------------------------------------------------------- */

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM staging.vra_tratada v
        LEFT JOIN dw.dim_companhia_aerea d
          ON d.companhia_icao = BTRIM(v.companhia_icao)
        WHERE d.id_companhia IS NULL
    ) THEN
        RAISE EXCEPTION 'Há companhia ICAO sem correspondência em dw.dim_companhia_aerea.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM staging.vra_tratada v
        LEFT JOIN dw.dim_aeroporto d
          ON d.aeroporto_icao = BTRIM(v.aeroporto_origem)
        WHERE d.id_aeroporto IS NULL
    ) THEN
        RAISE EXCEPTION 'Há aeroporto de origem sem correspondência em dw.dim_aeroporto.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM staging.vra_tratada v
        LEFT JOIN dw.dim_aeroporto d
          ON d.aeroporto_icao = BTRIM(v.aeroporto_destino)
        WHERE d.id_aeroporto IS NULL
    ) THEN
        RAISE EXCEPTION 'Há aeroporto de destino sem correspondência em dw.dim_aeroporto.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM staging.vra_tratada v
        LEFT JOIN dw.dim_tempo d
          ON d.data = v.partida_prevista::DATE
        WHERE d.id_tempo IS NULL
    ) THEN
        RAISE EXCEPTION 'Há data de partida prevista sem correspondência em dw.dim_tempo.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM staging.vra_tratada v
        LEFT JOIN dw.dim_tempo d
          ON d.data = v.chegada_prevista::DATE
        WHERE d.id_tempo IS NULL
    ) THEN
        RAISE EXCEPTION 'Há data de chegada prevista sem correspondência em dw.dim_tempo.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM staging.vra_tratada v
        LEFT JOIN dw.dim_situacao_voo d
          ON d.situacao_voo = BTRIM(v.situacao_voo)
        WHERE NULLIF(BTRIM(v.situacao_voo), '') IS NOT NULL
          AND d.id_situacao IS NULL
    ) THEN
        RAISE EXCEPTION 'Há situação de voo sem correspondência em dw.dim_situacao_voo.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM staging.vra_tratada v
        LEFT JOIN dw.dim_tipo_linha d
          ON d.tipo_linha = UPPER(BTRIM(v.tipo_linha))
        WHERE NULLIF(BTRIM(v.tipo_linha), '') IS NOT NULL
          AND d.id_tipo_linha IS NULL
    ) THEN
        RAISE EXCEPTION 'Há tipo de linha sem correspondência em dw.dim_tipo_linha.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM dw.dim_justificativa
        WHERE id_justificativa = 0 AND justificativa = 'DESCONHECIDO'
    ) THEN
        RAISE EXCEPTION 'A chave 0 / DESCONHECIDO não existe em dw.dim_justificativa.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM dw.dim_equipamento
        WHERE id_equipamento = 0 AND modelo_equipamento = 'DESCONHECIDO'
    ) THEN
        RAISE EXCEPTION 'A chave 0 / DESCONHECIDO não existe em dw.dim_equipamento.';
    END IF;
END $$;

/* ---------------------------------------------------------------------
   9. FATO_VOO
   Granularidade: uma ocorrência elegível de etapa de voo.
   id_raw identifica a linha da origem dentro deste experimento ELT.
   --------------------------------------------------------------------- */

-- Estrutura movida para sql/database/10_criacao_dw.sql.

/* ---------------------------------------------------------------------
   10. CARGA DA FATO
   LEFT JOINs + pré-validação impedem perda silenciosa de correspondências.
   O CASE preserva NULL quando não existe diferença calculável.
   ON CONFLICT evita duplicar id_raw em uma reexecução.
   --------------------------------------------------------------------- */

INSERT INTO dw.fato_voo (
    id_raw,
    id_companhia,
    id_aeroporto_origem,
    id_aeroporto_destino,
    id_tempo_partida,
    id_tempo_chegada,
    id_situacao,
    id_justificativa,
    id_tipo_linha,
    id_equipamento,
    numero_voo,
    codigo_di,
    referencia,
    situacao_partida,
    situacao_chegada,
    partida_prevista,
    partida_real,
    chegada_prevista,
    chegada_real,
    numero_assentos,
    quantidade_voos,
    diferenca_partida_min,
    diferenca_chegada_min,
    atraso_partida_min,
    atraso_chegada_min,
    partida_atipica_flag,
    chegada_atipica_flag,
    ano_origem,
    arquivo_origem,
    linha_origem,
    pipeline
)
SELECT
    v.id_raw,
    c.id_companhia,
    ao.id_aeroporto,
    ad.id_aeroporto,
    tp.id_tempo,
    tc.id_tempo,
    s.id_situacao,
    j.id_justificativa,
    tl.id_tipo_linha,
    e.id_equipamento,
    v.numero_voo,
    v.codigo_di,
    v.referencia,
    v.situacao_partida,
    v.situacao_chegada,
    v.partida_prevista,
    v.partida_real,
    v.chegada_prevista,
    v.chegada_real,
    v.numero_assentos,
    1,
    v.diferenca_partida_min,
    v.diferenca_chegada_min,
    CASE
        WHEN v.diferenca_partida_min IS NOT NULL
        THEN GREATEST(v.diferenca_partida_min, 0)
        ELSE NULL
    END,
    CASE
        WHEN v.diferenca_chegada_min IS NOT NULL
        THEN GREATEST(v.diferenca_chegada_min, 0)
        ELSE NULL
    END,
    COALESCE(ABS(v.diferenca_partida_min) > 1440, FALSE),
    COALESCE(ABS(v.diferenca_chegada_min) > 1440, FALSE),
    v.ano_origem,
    v.arquivo_origem,
    v.linha_origem,
    'ELT'
FROM staging.vra_tratada v
JOIN dw.dim_companhia_aerea c
  ON c.companhia_icao = BTRIM(v.companhia_icao)
JOIN dw.dim_aeroporto ao
  ON ao.aeroporto_icao = BTRIM(v.aeroporto_origem)
JOIN dw.dim_aeroporto ad
  ON ad.aeroporto_icao = BTRIM(v.aeroporto_destino)
JOIN dw.dim_tempo tp
  ON tp.data = v.partida_prevista::DATE
JOIN dw.dim_tempo tc
  ON tc.data = v.chegada_prevista::DATE
LEFT JOIN dw.dim_situacao_voo s
  ON s.situacao_voo = BTRIM(v.situacao_voo)
JOIN dw.dim_justificativa j
  ON j.justificativa = COALESCE(NULLIF(BTRIM(v.justificativa), ''), 'DESCONHECIDO')
LEFT JOIN dw.dim_tipo_linha tl
  ON tl.tipo_linha = UPPER(BTRIM(v.tipo_linha))
JOIN dw.dim_equipamento e
  ON e.modelo_equipamento = COALESCE(
      UPPER(NULLIF(BTRIM(v.modelo_equipamento), '')),
      'DESCONHECIDO'
  )
ON CONFLICT (id_raw) DO NOTHING;

