-- Resoluções já documentadas pelo integrante de 2020. Não alteram RAW/STAGING.
CREATE TABLE staging.resolucoes_aeroportos (
 aeroporto_icao text, descricao_original text, descricao_resolvida text,
 fonte_url text NOT NULL, justificativa text NOT NULL,
 PRIMARY KEY(aeroporto_icao,descricao_original)
);
INSERT INTO staging.resolucoes_aeroportos VALUES ('SBEG','LÁBREA - LÁBREA - AM - BRASIL','EDUARDO GOMES - MANAUS - AM - BRASIL','https://www.anac.gov.br/assuntos/legislacao/legislacao-1/portarias/2020/portaria-no-3204-sia-10-11-2020/@@display-file/arquivo_norma/PA2020-3204.pdf','Portaria ANAC de 2020 associa SBEG a Eduardo Gomes; resolução apenas da descrição dimensional sem alterar código ou fonte bruta.');
INSERT INTO staging.resolucoes_aeroportos VALUES ('SWHP','OLHOS D´ÁGUA - ÁGUA BOA - MG - BRASIL','OLHOS D´ÁGUA - ÁGUA BOA - MT - BRASIL','https://www.anac.gov.br/assuntos/setor-regulado/aerodromos/localizacao-geografica-arquivos/aerodromos/publicos-todas-as-regioes/download.table','Cadastro ANAC associa SWHP a Olhos D’Água em Água Boa MT; preservado o nome histórico da fonte.');
CREATE VIEW staging.aeroportos_observados AS
SELECT ano_origem,id_raw,arquivo_origem,linha_origem,'origem'::text papel,
 aeroporto_origem aeroporto_icao,descricao_origem descricao_original FROM staging.vra_tratada
UNION ALL
SELECT ano_origem,id_raw,arquivo_origem,linha_origem,'destino',
 aeroporto_destino,descricao_destino FROM staging.vra_tratada;
CREATE VIEW staging.aeroportos_resolvidos AS
SELECT o.*,coalesce(r.descricao_resolvida,o.descricao_original) descricao_resolvida,
 r.fonte_url,r.justificativa
FROM staging.aeroportos_observados o LEFT JOIN staging.resolucoes_aeroportos r
USING(aeroporto_icao,descricao_original);
CREATE VIEW staging.conflitos_dimensoes AS
SELECT 'aeroporto'::text dimensao,aeroporto_icao codigo,
 array_agg(DISTINCT descricao_resolvida ORDER BY descricao_resolvida) descricoes
FROM staging.aeroportos_resolvidos GROUP BY aeroporto_icao
HAVING count(DISTINCT descricao_resolvida)>1
UNION ALL
SELECT 'companhia',companhia_icao,array_agg(DISTINCT companhia_nome ORDER BY companhia_nome)
FROM staging.vra_tratada GROUP BY companhia_icao HAVING count(DISTINCT companhia_nome)>1;
DO $$ BEGIN
 IF EXISTS(SELECT FROM staging.conflitos_dimensoes) THEN
 RAISE EXCEPTION 'Conflitos dimensionais sem resolução; publicação bloqueada'; END IF;
END $$;
-- A seleção por MAX é segura apenas após provar que há no máximo uma descrição.
CREATE VIEW staging.cadastro_aeroportos AS
SELECT aeroporto_icao,max(descricao_resolvida) descricao_aeroporto
FROM staging.aeroportos_resolvidos GROUP BY aeroporto_icao;
