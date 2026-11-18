-- Exemplo executável: ocorrência da fato ETL 2021 até o conteúdo do CSV original.
-- linha_origem = ordinal lógico do registro CSV; cabeçalho contado como 1.
SELECT f.id_voo,f.ano_origem,f.id_raw,f.arquivo_origem,f.linha_origem,
       r."Sigla ICAO Empresa Aérea",r."Número Voo",r."Partida Prevista",r."Codeshare"
FROM dw_etl.fato_voo f
JOIN staging_etl.vra_tratada s USING(ano_origem,id_raw)
JOIN raw_etl.ocorrencias o USING(ano_origem,id_raw)
JOIN raw_etl.voos_2021 r ON r.id_raw=o.id_raw AND r.ano_origem=o.ano_origem
WHERE f.ano_origem=2021
ORDER BY f.id_raw LIMIT 10;
-- Mesmo percurso independente no fluxo ELT.
SELECT f.id_voo,f.ano_origem,f.id_raw,f.arquivo_origem,f.linha_origem,
       r."Sigla ICAO Empresa Aérea",r."Número Voo",r."Partida Prevista",r."Codeshare"
FROM dw_elt.fato_voo f
JOIN staging_elt.vra_tratada s USING(ano_origem,id_raw)
JOIN raw.ocorrencias o USING(ano_origem,id_raw)
JOIN raw.voos_2021 r ON r.id_raw=o.id_raw AND r.ano_origem=o.ano_origem
WHERE f.ano_origem=2021
ORDER BY f.id_raw LIMIT 10;
