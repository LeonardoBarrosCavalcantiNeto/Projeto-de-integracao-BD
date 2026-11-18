-- Asserções são executáveis: qualquer divergência aborta a transação.
DO $$ DECLARE q record; BEGIN
 FOR q IN SELECT * FROM staging.resumo_qualidade LOOP
  IF q.bruta <> q.duplicatas_excedentes+q.rejeicoes+q.tratada THEN
   RAISE EXCEPTION 'Conciliação inválida no ano %',q.ano_origem; END IF;
  IF q.tratada <> (SELECT count(*) FROM dw.fato_voo WHERE ano_origem=q.ano_origem) THEN
   RAISE EXCEPTION 'Fato divergente no ano %',q.ano_origem; END IF;
 END LOOP;
 IF EXISTS(SELECT FROM staging.vra_tratada WHERE companhia_icao IS NULL OR aeroporto_origem IS NULL
   OR aeroporto_destino IS NULL OR partida_prevista IS NULL OR chegada_prevista IS NULL) THEN
   RAISE EXCEPTION 'Obrigatórios ausentes'; END IF;
 IF EXISTS(SELECT FROM dw.fato_voo WHERE
   diferenca_partida_min IS DISTINCT FROM extract(epoch FROM(partida_real-partida_prevista))/60
   OR diferenca_chegada_min IS DISTINCT FROM extract(epoch FROM(chegada_real-chegada_prevista))/60
   OR atraso_partida_min IS DISTINCT FROM CASE WHEN partida_real IS NOT NULL THEN greatest(diferenca_partida_min,0) END
   OR atraso_chegada_min IS DISTINCT FROM CASE WHEN chegada_real IS NOT NULL THEN greatest(diferenca_chegada_min,0) END
   OR partida_atipica_flag IS DISTINCT FROM coalesce(abs(diferenca_partida_min)>1440,false)
   OR chegada_atipica_flag IS DISTINCT FROM coalesce(abs(diferenca_chegada_min)>1440,false)) THEN
   RAISE EXCEPTION 'Métricas temporais inconsistentes'; END IF;
 IF EXISTS(SELECT FROM raw.ocorrencias r LEFT JOIN (
    SELECT ano_origem,id_raw FROM staging.vra_tratada UNION ALL
    SELECT ano_origem,id_raw FROM staging.vra_rejeicoes UNION ALL
    SELECT ano_origem,id_raw FROM staging.vra_duplicatas_excluidas
   ) s USING(ano_origem,id_raw) GROUP BY r.ano_origem,r.id_raw HAVING count(s.id_raw)<>1) THEN
   RAISE EXCEPTION 'Origem sem classificação única'; END IF;
 IF EXISTS(SELECT FROM dw.fato_voo f JOIN staging.vra_tratada s USING(ano_origem,id_raw)
  WHERE (f.arquivo_origem,f.linha_origem) IS DISTINCT FROM(s.arquivo_origem,s.linha_origem)) THEN
  RAISE EXCEPTION 'Origem divergente na fato'; END IF;
 IF EXISTS(SELECT FROM raw.inventario i LEFT JOIN(
 SELECT ano_origem,arquivo_origem,count(*) registros FROM raw.ocorrencias GROUP BY 1,2
 ) r USING(ano_origem,arquivo_origem) WHERE i.registros IS DISTINCT FROM coalesce(r.registros,0)) THEN
 RAISE EXCEPTION 'Contagem por arquivo divergente'; END IF;
 IF EXISTS(SELECT FROM (
 SELECT ano_origem,id_raw,arquivo_origem,linha_origem FROM staging.vra_tratada UNION ALL
 SELECT ano_origem,id_raw,arquivo_origem,linha_origem FROM staging.vra_rejeicoes UNION ALL
 SELECT ano_origem,id_raw,arquivo_origem,linha_origem FROM staging.vra_duplicatas_excluidas
 ) s JOIN raw.ocorrencias r USING(ano_origem,id_raw)
 WHERE (s.arquivo_origem,s.linha_origem) IS DISTINCT FROM(r.arquivo_origem,r.linha_origem)) THEN
 RAISE EXCEPTION 'Proveniência divergente na STAGING'; END IF;
 IF EXISTS(SELECT FROM dw.fato_voo f JOIN staging.vra_tratada s USING(ano_origem,id_raw)
 JOIN dw.dim_companhia_aerea c USING(id_companhia)
 JOIN dw.dim_aeroporto ao ON ao.id_aeroporto=f.id_aeroporto_origem
 JOIN dw.dim_aeroporto ad ON ad.id_aeroporto=f.id_aeroporto_destino
 JOIN dw.dim_tempo tp ON tp.id_tempo=f.id_tempo_partida
 JOIN dw.dim_tempo tc ON tc.id_tempo=f.id_tempo_chegada
 LEFT JOIN dw.dim_situacao_voo sv USING(id_situacao)
 LEFT JOIN dw.dim_tipo_linha tl USING(id_tipo_linha)
 JOIN dw.dim_justificativa j USING(id_justificativa)
 JOIN dw.dim_equipamento e USING(id_equipamento)
 WHERE ROW(c.companhia_icao,ao.aeroporto_icao,ad.aeroporto_icao,tp.data,tc.data,sv.situacao_voo,
 tl.tipo_linha,j.justificativa,e.modelo_equipamento,f.numero_voo,f.codigo_di,f.referencia,
 f.situacao_partida,f.situacao_chegada,f.partida_prevista,f.partida_real,f.chegada_prevista,
 f.chegada_real,f.numero_assentos,f.quantidade_voos)
 IS DISTINCT FROM ROW(s.companhia_icao,s.aeroporto_origem,s.aeroporto_destino,
 s.partida_prevista::date,s.chegada_prevista::date,s.situacao_voo,s.tipo_linha,
 coalesce(s.justificativa,'DESCONHECIDO'),coalesce(s.modelo_equipamento,'DESCONHECIDO'),
 s.numero_voo,s.codigo_di,s.referencia,s.situacao_partida,s.situacao_chegada,
 s.partida_prevista,s.partida_real,s.chegada_prevista,s.chegada_real,s.numero_assentos,1::smallint)) THEN
 RAISE EXCEPTION 'Conteúdo ou relacionamento dimensional divergente na fato'; END IF;
 IF EXISTS(SELECT FROM pg_constraint WHERE connamespace='dw'::regnamespace AND contype='f' AND NOT convalidated) THEN
  RAISE EXCEPTION 'FK não validada'; END IF;
 IF EXISTS(SELECT FROM staging.conflitos_dimensoes) THEN RAISE EXCEPTION 'Conflitos dimensionais'; END IF;
END $$;
SELECT ano_origem,bruta,duplicatas_excedentes,rejeicoes,tratada,partidas_atipicas,chegadas_atipicas,
 partidas_reais_nulas,chegadas_reais_nulas FROM staging.resumo_qualidade ORDER BY ano_origem;
SELECT ano_origem,count(*) fato FROM dw.fato_voo GROUP BY ano_origem ORDER BY ano_origem;
SELECT count(*) total_fato FROM dw.fato_voo;
