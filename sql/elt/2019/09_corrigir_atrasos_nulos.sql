-- 09 — Correção pontual para a tabela staging.vra_tratada já existente
-- Execute apenas se a tabela foi criada com GREATEST(diferenca, 0) sem CASE.
-- No PostgreSQL, GREATEST(NULL, 0) retorna 0; o contrato exige NULL quando
-- não existe horário real para calcular a diferença.

UPDATE staging.vra_tratada
SET atraso_partida_min = NULL
WHERE diferenca_partida_min IS NULL
  AND atraso_partida_min IS NOT NULL;

UPDATE staging.vra_tratada
SET atraso_chegada_min = NULL
WHERE diferenca_chegada_min IS NULL
  AND atraso_chegada_min IS NOT NULL;
