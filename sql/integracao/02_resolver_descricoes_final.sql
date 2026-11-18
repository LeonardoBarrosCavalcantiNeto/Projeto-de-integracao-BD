-- Complemento ao 02_dimensoes canônico. Snapshot descritivo SCD tipo 1.
-- Não altera códigos, RAW ou tratados. A escolha é última descrição não nula
-- observada na ordem (ano, arquivo, ordinal, papel), após correções documentadas.
-- Todas as variantes e suas contagens continuam disponíveis para auditoria.
ALTER VIEW staging.conflitos_dimensoes RENAME TO variantes_dimensoes;
CREATE TABLE staging.snapshot_descricoes AS
SELECT DISTINCT ON (dimensao,codigo) dimensao,codigo,descricao,ano_origem,arquivo_origem,linha_origem
FROM (
 SELECT 'aeroporto'::text dimensao,aeroporto_icao codigo,descricao_resolvida descricao,
 ano_origem,arquivo_origem,linha_origem,papel
 FROM staging.aeroportos_resolvidos
 UNION ALL
 SELECT 'companhia',companhia_icao,companhia_nome,ano_origem,arquivo_origem,linha_origem,'companhia'
 FROM staging.vra_tratada
) o
ORDER BY dimensao,codigo,(descricao IS NOT NULL) DESC,ano_origem DESC,arquivo_origem COLLATE "C" DESC,linha_origem DESC,papel DESC;
ALTER TABLE staging.snapshot_descricoes ADD PRIMARY KEY(dimensao,codigo);
CREATE VIEW staging.conflitos_dimensoes AS
SELECT v.* FROM staging.variantes_dimensoes v
LEFT JOIN staging.snapshot_descricoes s ON s.dimensao=v.dimensao AND s.codigo=v.codigo
WHERE s.codigo IS NULL;
