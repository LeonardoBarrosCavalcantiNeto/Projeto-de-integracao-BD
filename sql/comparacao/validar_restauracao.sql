-- Verificação do banco restaurado a partir de um backup já validado na origem.
DO $$
BEGIN
 IF (SELECT array_agg(ano_origem ORDER BY ano_origem) FROM staging_elt.resumo_qualidade)
    IS DISTINCT FROM ARRAY[2019,2020,2021] THEN
  RAISE EXCEPTION 'Anos ausentes na restauração';
 END IF;
 IF EXISTS (
  SELECT 1 FROM staging_elt.resumo_qualidade q
  LEFT JOIN (SELECT ano_origem,count(*) n FROM dw_etl.fato_voo GROUP BY 1) a USING(ano_origem)
  LEFT JOIN (SELECT ano_origem,count(*) n FROM dw_elt.fato_voo GROUP BY 1) b USING(ano_origem)
  LEFT JOIN (SELECT ano_origem,count(*) n FROM raw_etl.ocorrencias GROUP BY 1) r USING(ano_origem)
  LEFT JOIN (SELECT ano_origem,count(*) n FROM raw.ocorrencias GROUP BY 1) s USING(ano_origem)
  -- Um ano só com rejeições ou descartes tem zero fatos e não aparece no GROUP BY.
  WHERE coalesce(a.n, 0) IS DISTINCT FROM q.tratada
     OR coalesce(b.n, 0) IS DISTINCT FROM q.tratada
     OR r.n IS DISTINCT FROM q.bruta OR s.n IS DISTINCT FROM q.bruta
 ) THEN RAISE EXCEPTION 'Contagens divergentes na restauração'; END IF;
END $$;
SELECT comparacao.validar_dimensoes();
SELECT 'RESTAURACAO_OK' resultado;
