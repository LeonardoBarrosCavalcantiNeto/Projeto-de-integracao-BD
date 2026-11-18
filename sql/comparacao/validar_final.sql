-- Compara cada ocorrência por chave de origem em lotes indexados.
CREATE SCHEMA IF NOT EXISTS comparacao;
CREATE OR REPLACE VIEW comparacao.fatos_por_origem AS
SELECT 'etl' fluxo, f.ano_origem, f.id_raw, to_jsonb(f)-ARRAY['id_voo','id_companhia','id_aeroporto_origem','id_aeroporto_destino',
 'id_tempo_partida','id_tempo_chegada','id_situacao','id_justificativa','id_tipo_linha','id_equipamento','pipeline']
 || jsonb_build_object('companhia',c.companhia_icao,'origem',ao.aeroporto_icao,'destino',ad.aeroporto_icao,
 'data_partida',tp.data,'data_chegada',tc.data,'situacao',sv.situacao_voo,'justificativa',j.justificativa,
 'tipo_linha',tl.tipo_linha,'equipamento',e.modelo_equipamento) conteudo
FROM dw_etl.fato_voo f
JOIN dw_etl.dim_companhia_aerea c USING(id_companhia)
JOIN dw_etl.dim_aeroporto ao ON ao.id_aeroporto=f.id_aeroporto_origem
JOIN dw_etl.dim_aeroporto ad ON ad.id_aeroporto=f.id_aeroporto_destino
JOIN dw_etl.dim_tempo tp ON tp.id_tempo=f.id_tempo_partida
JOIN dw_etl.dim_tempo tc ON tc.id_tempo=f.id_tempo_chegada
LEFT JOIN dw_etl.dim_situacao_voo sv USING(id_situacao)
JOIN dw_etl.dim_justificativa j USING(id_justificativa)
LEFT JOIN dw_etl.dim_tipo_linha tl USING(id_tipo_linha)
JOIN dw_etl.dim_equipamento e USING(id_equipamento)
UNION ALL
SELECT 'elt',f.ano_origem,f.id_raw,to_jsonb(f)-ARRAY['id_voo','id_companhia','id_aeroporto_origem','id_aeroporto_destino',
 'id_tempo_partida','id_tempo_chegada','id_situacao','id_justificativa','id_tipo_linha','id_equipamento','pipeline']
 || jsonb_build_object('companhia',c.companhia_icao,'origem',ao.aeroporto_icao,'destino',ad.aeroporto_icao,
 'data_partida',tp.data,'data_chegada',tc.data,'situacao',sv.situacao_voo,'justificativa',j.justificativa,
 'tipo_linha',tl.tipo_linha,'equipamento',e.modelo_equipamento)
FROM dw_elt.fato_voo f
JOIN dw_elt.dim_companhia_aerea c USING(id_companhia)
JOIN dw_elt.dim_aeroporto ao ON ao.id_aeroporto=f.id_aeroporto_origem
JOIN dw_elt.dim_aeroporto ad ON ad.id_aeroporto=f.id_aeroporto_destino
JOIN dw_elt.dim_tempo tp ON tp.id_tempo=f.id_tempo_partida
JOIN dw_elt.dim_tempo tc ON tc.id_tempo=f.id_tempo_chegada
LEFT JOIN dw_elt.dim_situacao_voo sv USING(id_situacao)
JOIN dw_elt.dim_justificativa j USING(id_justificativa)
LEFT JOIN dw_elt.dim_tipo_linha tl USING(id_tipo_linha)
JOIN dw_elt.dim_equipamento e USING(id_equipamento);
CREATE OR REPLACE VIEW comparacao.fatos AS
SELECT fluxo, conteudo FROM comparacao.fatos_por_origem;

CREATE OR REPLACE FUNCTION comparacao.validar_ano(ano integer)
RETURNS text LANGUAGE plpgsql SET work_mem='8MB' SET hash_mem_multiplier=1 AS $$
DECLARE
 etapa text;
 fluxo text;
 schema_raw text;
 tabela_raw text := 'voos_' || ano;
 inicio bigint;
 ultimo bigint;
 limite bigint;
 divergentes bigint;
 exemplo bigint;
 qtd_raw bigint;
BEGIN
 IF ano NOT IN (2019,2020,2021) THEN RAISE EXCEPTION 'Ano inválido: %',ano; END IF;
 EXECUTE format('SELECT count(*),max(id_raw) FROM raw.%I',tabela_raw) INTO qtd_raw,ultimo;
 IF qtd_raw=0 OR ultimo<>qtd_raw THEN RAISE EXCEPTION 'Sequência RAW incompleta em %',ano; END IF;

 -- Cada tabela grande tem chave única por ocorrência. Comparar por chave preserva
 -- multiplicidade mesmo quando duas ocorrências têm os mesmos valores de negócio.
 FOREACH etapa IN ARRAY ARRAY['raw','vra_tratada','vra_rejeicoes','vra_duplicatas_excluidas','fato'] LOOP
  inicio := 1;
  WHILE inicio<=ultimo LOOP
   limite := inicio+25000;
   IF etapa='raw' THEN
    EXECUTE format($q$
     WITH a AS MATERIALIZED (SELECT * FROM raw.%1$I WHERE id_raw >= $1 AND id_raw < $2),
          b AS MATERIALIZED (SELECT * FROM raw_etl.%1$I WHERE id_raw >= $1 AND id_raw < $2)
     SELECT count(*),min(coalesce(a.id_raw,b.id_raw)) FROM a FULL JOIN b USING(id_raw)
     WHERE to_jsonb(a) IS DISTINCT FROM to_jsonb(b)$q$,tabela_raw)
    INTO divergentes,exemplo USING inicio,limite;
   ELSIF etapa='fato' THEN
    WITH a AS MATERIALIZED (SELECT id_raw,conteudo FROM comparacao.fatos_por_origem v
     WHERE v.fluxo='etl' AND ano_origem=ano AND id_raw>=inicio AND id_raw<limite),
         b AS MATERIALIZED (SELECT id_raw,conteudo FROM comparacao.fatos_por_origem v
     WHERE v.fluxo='elt' AND ano_origem=ano AND id_raw>=inicio AND id_raw<limite)
    SELECT count(*),min(coalesce(a.id_raw,b.id_raw)) INTO divergentes,exemplo
    FROM a FULL JOIN b USING(id_raw) WHERE a.conteudo IS DISTINCT FROM b.conteudo;
   ELSE
    EXECUTE format($q$
     WITH a AS MATERIALIZED
       (SELECT * FROM staging_etl.%1$I WHERE ano_origem=$3 AND id_raw >= $1 AND id_raw < $2),
          b AS MATERIALIZED
       (SELECT * FROM staging_elt.%1$I WHERE ano_origem=$3 AND id_raw >= $1 AND id_raw < $2)
     SELECT count(*),min(coalesce(a.id_raw,b.id_raw)) FROM a FULL JOIN b USING(id_raw)
     WHERE to_jsonb(a) IS DISTINCT FROM (to_jsonb(b)-'ocorrencia_num')$q$,etapa)
    INTO divergentes,exemplo USING inicio,limite,ano;
   END IF;
   IF divergentes<>0 THEN
    RAISE EXCEPTION 'Ano %, etapa %, faixa [%,%): % divergências, primeiro id_raw=%',
     ano,etapa,inicio,limite,divergentes,exemplo;
   END IF;
   inicio := limite;
  END LOOP;
  RAISE NOTICE 'Ano %: % sem divergências de conteúdo',ano,etapa;
 END LOOP;

 -- Anomalias podem ter vários motivos por ocorrência. Compara também multiplicidade.
 SELECT count(*) INTO divergentes FROM (
   (SELECT to_jsonb(a) FROM staging_etl.vra_anomalias a WHERE ano_origem=ano
    EXCEPT ALL SELECT to_jsonb(b) FROM staging_elt.vra_anomalias b WHERE ano_origem=ano)
   UNION ALL
   (SELECT to_jsonb(b) FROM staging_elt.vra_anomalias b WHERE ano_origem=ano
    EXCEPT ALL SELECT to_jsonb(a) FROM staging_etl.vra_anomalias a WHERE ano_origem=ano)) d;
 IF divergentes<>0 THEN RAISE EXCEPTION 'Ano %: % anomalias divergentes',ano,divergentes; END IF;

 FOREACH fluxo IN ARRAY ARRAY['etl','elt'] LOOP
  schema_raw := CASE fluxo WHEN 'etl' THEN 'raw_etl' ELSE 'raw' END;
  -- Contagens totais cobrem ocorrências extras fora da faixa de RAW.
  EXECUTE format($q$SELECT abs((SELECT count(*) FROM %1$I.%2$I)-$2)
   + abs((SELECT count(*) FROM %1$I.ocorrencias WHERE ano_origem=$1)-$2)$q$,schema_raw,tabela_raw)
  INTO divergentes USING ano,qtd_raw;
  IF divergentes<>0 THEN RAISE EXCEPTION 'Inventário de ocorrências divergente: %/%',fluxo,ano; END IF;
  EXECUTE format($q$SELECT (SELECT count(*) FROM dw_%1$s.fato_voo WHERE ano_origem=$1)
   - (SELECT count(*) FROM staging_%1$s.vra_tratada WHERE ano_origem=$1)$q$,fluxo)
  INTO divergentes USING ano;
  IF divergentes<>0 THEN RAISE EXCEPTION 'Quantidade da fato divergente: %/%',fluxo,ano; END IF;

  inicio := 1;
  WHILE inicio<=ultimo LOOP
   limite := inicio+25000;
   EXECUTE format($q$
    WITH r AS MATERIALIZED (SELECT * FROM %1$I.%2$I WHERE id_raw >= $1 AND id_raw < $2),
    o AS MATERIALIZED (SELECT * FROM %1$I.ocorrencias WHERE ano_origem=$4 AND id_raw >= $1 AND id_raw < $2),
    t AS MATERIALIZED (SELECT id_raw,arquivo_origem,linha_origem FROM staging_%3$s.vra_tratada WHERE ano_origem=$4 AND id_raw >= $1 AND id_raw < $2),
    j AS MATERIALIZED (SELECT * FROM staging_%3$s.vra_rejeicoes WHERE ano_origem=$4 AND id_raw >= $1 AND id_raw < $2),
    d AS MATERIALIZED (SELECT * FROM staging_%3$s.vra_duplicatas_excluidas WHERE ano_origem=$4 AND id_raw >= $1 AND id_raw < $2),
    f AS MATERIALIZED (SELECT id_raw,arquivo_origem,linha_origem,pipeline,quantidade_voos FROM dw_%3$s.fato_voo WHERE ano_origem=$4 AND id_raw >= $1 AND id_raw < $2)
    SELECT count(*),min(r.id_raw) FROM r
    LEFT JOIN o USING(id_raw) LEFT JOIN t USING(id_raw) LEFT JOIN j USING(id_raw)
    LEFT JOIN d USING(id_raw) LEFT JOIN f USING(id_raw)
    WHERE (
      ROW(r.arquivo_origem,r.linha_origem) IS DISTINCT FROM ROW(o.arquivo_origem,o.linha_origem)
      OR num_nonnulls(t.id_raw,j.id_raw,d.id_raw)<>1
      OR (t.id_raw IS NOT NULL AND (
          ROW(r.arquivo_origem,r.linha_origem) IS DISTINCT FROM ROW(t.arquivo_origem,t.linha_origem)
          OR ROW(t.arquivo_origem,t.linha_origem,upper($3),1::smallint)
             IS DISTINCT FROM ROW(f.arquivo_origem,f.linha_origem,f.pipeline,f.quantidade_voos)))
      OR (j.id_raw IS NOT NULL AND (cardinality(j.motivos_rejeicao) IS NULL OR cardinality(j.motivos_rejeicao)=0
          OR to_jsonb(r) IS DISTINCT FROM (to_jsonb(j)-'motivos_rejeicao')))
      OR (d.id_raw IS NOT NULL AND to_jsonb(r) IS DISTINCT FROM
          (to_jsonb(d)-ARRAY['ocorrencia_num','arquivo_preservado','linha_preservada'])))$q$,
    schema_raw,tabela_raw,fluxo)
   INTO divergentes,exemplo USING inicio,limite,fluxo,ano;
   IF divergentes<>0 THEN
    RAISE EXCEPTION 'Origem/classificação divergente: %/%, faixa [%,%), % casos, primeiro id_raw=%',
     fluxo,ano,inicio,limite,divergentes,exemplo;
   END IF;
   inicio := limite;
  END LOOP;
  EXECUTE format($q$
   SELECT count(*) FROM staging_%1$s.vra_duplicatas_excluidas d
   LEFT JOIN %2$I.%3$I r ON (r.arquivo_origem,r.linha_origem)=(d.arquivo_preservado,d.linha_preservada)
   LEFT JOIN staging_%1$s.vra_duplicatas_excluidas x ON (x.ano_origem,x.id_raw)=(r.ano_origem,r.id_raw)
   WHERE d.ano_origem=$1 AND (
    r.id_raw IS NULL OR r.id_raw>=d.id_raw OR x.id_raw IS NOT NULL
    OR (to_jsonb(r)-ARRAY['id_raw','arquivo_origem','linha_origem','Codeshare'])
       IS DISTINCT FROM (to_jsonb(d)-ARRAY['id_raw','arquivo_origem','linha_origem','Codeshare',
          'ocorrencia_num','arquivo_preservado','linha_preservada']))$q$,fluxo,schema_raw,tabela_raw)
  INTO divergentes USING ano;
  IF divergentes<>0 THEN RAISE EXCEPTION 'Representantes inválidos: %/%',fluxo,ano; END IF;
  EXECUTE format($q$
   SELECT count(*) FROM staging_%1$s.vra_anomalias a
   LEFT JOIN %2$I.ocorrencias o USING(ano_origem,arquivo_origem,linha_origem)
   WHERE a.ano_origem=$1 AND o.id_raw IS NULL$q$,fluxo,schema_raw)
  INTO divergentes USING ano;
  IF divergentes<>0 THEN RAISE EXCEPTION 'Anomalias sem origem: %/%',fluxo,ano; END IF;
  RAISE NOTICE 'Ano %: rastreabilidade % e classificação exclusivas conferidas',ano,fluxo;
 END LOOP;
 RETURN format('COMPARACAO_EXATA_OK %s (%s ocorrências brutas)',ano,qtd_raw);
END $$;

CREATE OR REPLACE FUNCTION comparacao.validar_dimensoes()
RETURNS text LANGUAGE plpgsql AS $$
DECLARE dim record; divergentes bigint; schema_dw text;
BEGIN
 FOR dim IN SELECT * FROM (VALUES ('dim_tempo','id_tempo'),('dim_companhia_aerea','id_companhia'),
 ('dim_aeroporto','id_aeroporto'),('dim_situacao_voo','id_situacao'),('dim_justificativa','id_justificativa'),
 ('dim_tipo_linha','id_tipo_linha'),('dim_equipamento','id_equipamento')) d(tabela,chave) LOOP
  EXECUTE format($q$SELECT count(*) FROM (
   (SELECT to_jsonb(a)-%1$L FROM dw_etl.%2$I a EXCEPT ALL SELECT to_jsonb(b)-%1$L FROM dw_elt.%2$I b)
   UNION ALL
   (SELECT to_jsonb(b)-%1$L FROM dw_elt.%2$I b EXCEPT ALL SELECT to_jsonb(a)-%1$L FROM dw_etl.%2$I a)
  ) d$q$,dim.chave,dim.tabela) INTO divergentes;
  IF divergentes<>0 THEN RAISE EXCEPTION 'Dimensão divergente: %',dim.tabela; END IF;
 END LOOP;
 FOREACH schema_dw IN ARRAY ARRAY['dw_etl','dw_elt'] LOOP
  IF (SELECT count(*) FROM pg_constraint WHERE conrelid=(schema_dw||'.fato_voo')::regclass
      AND contype='f' AND convalidated)<>10 THEN
   RAISE EXCEPTION 'Esperadas 10 FKs válidas na fato de %',schema_dw;
  END IF;
 END LOOP;
 RETURN 'DIMENSOES_E_FKS_OK';
END $$;

-- Execução manual completa. O comando compare pode retomar por ano.
SELECT comparacao.validar_dimensoes();
SELECT comparacao.validar_ano(2019);
SELECT comparacao.validar_ano(2020);
SELECT comparacao.validar_ano(2021);
SELECT ano_origem,bruta,duplicatas_excedentes,rejeicoes,tratada FROM staging_elt.resumo_qualidade ORDER BY 1;
SELECT 'etl' fluxo,ano_origem,count(*) fato FROM dw_etl.fato_voo GROUP BY 2
UNION ALL SELECT 'elt',ano_origem,count(*) FROM dw_elt.fato_voo GROUP BY 2 ORDER BY 1,2;
