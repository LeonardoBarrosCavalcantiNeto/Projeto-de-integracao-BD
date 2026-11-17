-- 02 — Funções auxiliares de conversão da STAGING
-- Datas previstas/reais: DD/MM/YYYY HH24:MI ou DD/MM/YYYY HH24:MI:SS.
-- Referência: YYYY-MM-DD. Valores inválidos retornam NULL.

CREATE OR REPLACE FUNCTION staging.try_timestamp_br(valor TEXT)
RETURNS TIMESTAMP WITHOUT TIME ZONE
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v TEXT;
    ano INTEGER;
    mes INTEGER;
    dia INTEGER;
    hora INTEGER;
    minuto INTEGER;
    segundo INTEGER := 0;
BEGIN
    v := NULLIF(BTRIM(valor), '');
    IF v IS NULL THEN
        RETURN NULL;
    END IF;

    IF v !~ '^[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}(:[0-9]{2})?$' THEN
        RETURN NULL;
    END IF;

    dia := SUBSTRING(v FROM 1 FOR 2)::INTEGER;
    mes := SUBSTRING(v FROM 4 FOR 2)::INTEGER;
    ano := SUBSTRING(v FROM 7 FOR 4)::INTEGER;
    hora := SUBSTRING(v FROM 12 FOR 2)::INTEGER;
    minuto := SUBSTRING(v FROM 15 FOR 2)::INTEGER;

    IF LENGTH(v) = 19 THEN
        segundo := SUBSTRING(v FROM 18 FOR 2)::INTEGER;
    END IF;

    RETURN MAKE_TIMESTAMP(ano, mes, dia, hora, minuto, segundo);
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION staging.try_date_iso(valor TEXT)
RETURNS DATE
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v TEXT;
BEGIN
    v := NULLIF(BTRIM(valor), '');
    IF v IS NULL OR v !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
        RETURN NULL;
    END IF;

    RETURN MAKE_DATE(
        SUBSTRING(v FROM 1 FOR 4)::INTEGER,
        SUBSTRING(v FROM 6 FOR 2)::INTEGER,
        SUBSTRING(v FROM 9 FOR 2)::INTEGER
    );
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION staging.try_integer(valor TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v TEXT;
BEGIN
    v := NULLIF(BTRIM(valor), '');
    IF v IS NULL OR v !~ '^[0-9]+$' THEN
        RETURN NULL;
    END IF;

    RETURN v::INTEGER;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$;
