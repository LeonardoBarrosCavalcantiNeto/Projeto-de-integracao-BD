# Qualidade medida nos CSVs reais — 2019, 2020 e 2021

Resultados dos 36 CSVs reais tratados conforme o contrato v1.1. As contagens e o conteúdo foram conferidos na execução Pandas, na execução SQL e nos dois DWs. Consulte a [evidência das contagens](../resultados/validacoes/integracao_final/qualidade.csv) e a [comparação integral por ano](../resultados/validacoes/integracao_final/comparacao_integral.json).

| Ano | Brutos | Excedentes | Rejeitados | Válidos | Rejeição (%) |
|---|---:|---:|---:|---:|---:|
| 2019 | 983414 | 470 | 18 | 982926 | 0.0018 |
| 2020 | 483545 | 124 | 1512 | 481909 | 0.3127 |
| 2021 | 632148 | 0 | 25511 | 606637 | 4.0356 |

A conservação por ano é `brutos = excedentes + rejeitados remanescentes + válidos`. As rejeições são avaliadas depois da deduplicação exata dos 20 campos. Repetições que surgem apenas depois da padronização não são excluídas automaticamente.

| Ano | Partida real NULL | Chegada real NULL | Partida >24h | Chegada >24h |
|---|---:|---:|---:|---:|
| 2019 | 17982 | 17982 | 684 | 690 |
| 2020 | 21845 | 21845 | 286 | 331 |
| 2021 | 26139 | 26141 | 371 | 373 |

As flags usam o valor absoluto da diferença em minutos. Antecipações continuam negativas na diferença e têm atraso zero. Horários reais desconhecidos têm atraso NULL. Em 2019, a deduplicação reduz as contagens de atípicos da referência anterior à deduplicação; não se força o resultado antigo de 687/693.

## Motivos de rejeição

Uma ocorrência pode ter vários motivos; a soma por motivo pode superar o total de linhas rejeitadas.

| Ano | Motivo | Ocorrências |
|---|---|---:|
| 2019 | AEROPORTO_DESTINO_AUSENTE | 14 |
| 2019 | CHEGADA_PREVISTA_AUSENTE | 18 |
| 2019 | PARTIDA_PREVISTA_AUSENTE | 18 |
| 2020 | CHEGADA_PREVISTA_AUSENTE | 1512 |
| 2020 | PARTIDA_PREVISTA_AUSENTE | 1512 |
| 2021 | CHEGADA_PREVISTA_AUSENTE | 25511 |
| 2021 | PARTIDA_PREVISTA_AUSENTE | 25511 |

## Esquema e preservação

Todos os 36 arquivos tiveram seus SHA-256 comparados entre ingestão ETL, ingestão ELT e originais após o processamento. Sete arquivos de 2021 possuem 21 colunas, incluindo `Codeshare`; os demais têm 20. Foram contados 112479 registros de 2021 com Codeshare preenchido. A coluna é preservada bruta e não integra a chave dos 20 campos do contrato. As duas representações da referência são convertidas especificamente em 2021.

Artefatos completos: `.local/final/etl/ANO/`. Evidências de entrega: `resultados/validacoes/integracao_final/`. As descrições dimensionais variantes não são rejeições: permanecem auditáveis e são representadas pelo snapshot descrito no modelo dimensional.

## Duplicatas e datas fora do ano

Os diagnósticos Pandas e PostgreSQL coincidiram nos três anos.

| Ano | Grupos exatos | Registros envolvidos | Excedentes inválidos | Excedentes após TRIM/UPPER | Partidas previstas fora do ano |
|---|---:|---:|---:|---:|---:|
| 2019 | 444 | 914 | 0 | 0 | 12 |
| 2020 | 124 | 248 | 0 | 0 | 15 |
| 2021 | 0 | 0 | 0 | 0 | 15 |

As partidas fora do ano de origem permaneceram elegíveis quando cumpriram o contrato. A deduplicação separou 594 excedentes sem sobreposição com rejeições. Consulte [os diagnósticos medidos](../resultados/validacoes/integracao_final/diagnosticos_contrato_sql.csv).
