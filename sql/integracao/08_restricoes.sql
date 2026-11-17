-- Aplicar após a carga validada. Reforça o contrato para futuras escritas.
ALTER TABLE staging.vra_tratada
 ALTER COLUMN companhia_icao SET NOT NULL,
 ALTER COLUMN aeroporto_origem SET NOT NULL,
 ALTER COLUMN aeroporto_destino SET NOT NULL,
 ALTER COLUMN partida_prevista SET NOT NULL,
 ALTER COLUMN chegada_prevista SET NOT NULL,
 ALTER COLUMN arquivo_origem SET NOT NULL,
 ALTER COLUMN linha_origem SET NOT NULL;
ALTER TABLE staging.vra_rejeicoes
 ALTER COLUMN arquivo_origem SET NOT NULL, ALTER COLUMN linha_origem SET NOT NULL,
 ALTER COLUMN motivos_rejeicao SET NOT NULL,
 ADD CHECK (cardinality(motivos_rejeicao)>0);
ALTER TABLE staging.vra_duplicatas_excluidas
 ALTER COLUMN arquivo_origem SET NOT NULL, ALTER COLUMN linha_origem SET NOT NULL,
 ADD CHECK (ocorrencia_num>1);
ALTER TABLE dw.fato_voo
 ALTER COLUMN partida_prevista SET NOT NULL,
 ALTER COLUMN chegada_prevista SET NOT NULL,
 ADD CHECK (quantidade_voos=1),
 ADD CHECK (numero_assentos IS NULL OR numero_assentos>=0),
 ADD CHECK (atraso_partida_min IS NOT DISTINCT FROM
   CASE WHEN diferenca_partida_min IS NOT NULL THEN greatest(diferenca_partida_min,0) END),
 ADD CHECK (atraso_chegada_min IS NOT DISTINCT FROM
   CASE WHEN diferenca_chegada_min IS NOT NULL THEN greatest(diferenca_chegada_min,0) END),
 ADD CHECK (diferenca_partida_min IS NOT DISTINCT FROM extract(epoch FROM(partida_real-partida_prevista))/60),
 ADD CHECK (diferenca_chegada_min IS NOT DISTINCT FROM extract(epoch FROM(chegada_real-chegada_prevista))/60),
 ADD CHECK (partida_atipica_flag=coalesce(abs(diferenca_partida_min)>1440,false)),
 ADD CHECK (chegada_atipica_flag=coalesce(abs(diferenca_chegada_min)>1440,false));
