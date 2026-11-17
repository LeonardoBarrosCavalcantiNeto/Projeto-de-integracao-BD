SELECT 2019 ano_origem, count(*) brutos FROM raw.voos_2019
UNION ALL
SELECT 2020, count(*) FROM raw.voos_2020;

SELECT ano_origem, bruta, duplicatas_excedentes, rejeicoes, tratada
FROM staging.resumo_qualidade ORDER BY ano_origem;

SELECT ano_origem, count(*) fatos FROM dw.fato_voo GROUP BY 1 ORDER BY 1;

SELECT count(*) total_fato FROM dw.fato_voo;

SELECT ano_origem, count(*) sem_origem
FROM raw.ocorrencias
WHERE arquivo_origem IS NULL OR linha_origem IS NULL OR linha_origem < 2
GROUP BY 1;

SELECT ano_origem, id_raw, count(*)
FROM dw.fato_voo GROUP BY 1,2 HAVING count(*) > 1;

SELECT ano_origem, arquivo_origem, linha_origem, count(*)
FROM staging.vra_tratada GROUP BY 1,2,3 HAVING count(*) > 1;

SELECT ano_origem,
 count(*) FILTER (WHERE partida_real IS NULL) partidas_sem_real,
 count(*) FILTER (WHERE partida_real IS NULL AND atraso_partida_min IS NOT NULL) nulos_incorretos,
 count(*) FILTER (WHERE chegada_real IS NULL AND atraso_chegada_min IS NOT NULL) nulos_chegada_incorretos
FROM dw.fato_voo GROUP BY 1 ORDER BY 1;

SELECT * FROM staging.conflitos_dimensoes;

SELECT conrelid::regclass tabela, conname, convalidated
FROM pg_constraint
WHERE connamespace = 'dw'::regnamespace AND contype = 'f'
ORDER BY 1,2;
