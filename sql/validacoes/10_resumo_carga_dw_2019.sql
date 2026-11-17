/* ---------------------------------------------------------------------
   11. RESUMO DA CARGA
   --------------------------------------------------------------------- */

SELECT
    (SELECT COUNT(*) FROM staging.vra_tratada) AS total_tratada,
    (SELECT COUNT(*) FROM dw.fato_voo) AS total_fato;

SELECT 'dim_tempo' AS dimensao, COUNT(*) AS registros FROM dw.dim_tempo
UNION ALL SELECT 'dim_companhia_aerea', COUNT(*) FROM dw.dim_companhia_aerea
UNION ALL SELECT 'dim_aeroporto', COUNT(*) FROM dw.dim_aeroporto
UNION ALL SELECT 'dim_situacao_voo', COUNT(*) FROM dw.dim_situacao_voo
UNION ALL SELECT 'dim_justificativa', COUNT(*) FROM dw.dim_justificativa
UNION ALL SELECT 'dim_tipo_linha', COUNT(*) FROM dw.dim_tipo_linha
UNION ALL SELECT 'dim_equipamento', COUNT(*) FROM dw.dim_equipamento
UNION ALL SELECT 'fato_voo', COUNT(*) FROM dw.fato_voo
ORDER BY dimensao;
