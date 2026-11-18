-- Template para o bundle canônico com os schemas dw e staging.
-- Para os dois DWs da entrega, execute sql/comparacao/analises_finais.sql.
-- Ano de origem = ano do conjunto CSV; pode diferir da data operacional.
SELECT ano_origem,count(*) voos FROM dw.fato_voo GROUP BY 1 ORDER BY 1;
SELECT c.companhia_icao,c.companhia_nome,f.ano_origem,count(*) voos,
 round(avg(f.atraso_partida_min),2) atraso_medio_min,
 count(f.atraso_partida_min) voos_com_horario_real
FROM dw.fato_voo f JOIN dw.dim_companhia_aerea c USING(id_companhia)
GROUP BY 1,2,3 ORDER BY voos DESC;
-- Critério de apresentação: atraso positivo. Denominador = horários calculáveis.
SELECT ano_origem,count(*) total,count(atraso_partida_min) calculaveis,
 count(*) FILTER(WHERE atraso_partida_min IS NULL) desconhecidos,
 round(100.0*count(*) FILTER(WHERE atraso_partida_min>0)/nullif(count(atraso_partida_min),0),2) percentual_atrasados,
 round(avg(atraso_partida_min),2) atraso_medio_min,
 count(*) FILTER(WHERE partida_atipica_flag) partidas_atipicas
FROM dw.fato_voo GROUP BY 1 ORDER BY 1;
SELECT a.aeroporto_icao,a.descricao_aeroporto,count(*) movimentos
FROM (SELECT id_aeroporto_origem id_aeroporto FROM dw.fato_voo UNION ALL
 SELECT id_aeroporto_destino FROM dw.fato_voo) m JOIN dw.dim_aeroporto a USING(id_aeroporto)
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15;
SELECT f.ano_origem,t.ano ano_operacional,t.mes,count(*) voos
FROM dw.fato_voo f JOIN dw.dim_tempo t ON t.id_tempo=f.id_tempo_partida
GROUP BY 1,2,3 ORDER BY 1,2,3;
SELECT ano_origem,bruta,duplicatas_excedentes,rejeicoes,tratada FROM staging.resumo_qualidade ORDER BY 1;
