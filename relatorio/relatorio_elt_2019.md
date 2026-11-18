# ELT dos dados VRA/ANAC — 2019

> **Nota histórica.** O notebook individual termina na tabela tratada. A carga dimensional e a comparação com o ETL foram registradas posteriormente na integração dos três anos. [Relatório final do projeto](STATUS_FINAL_PROJETO.md)

## Objetivo e fonte

Processar os registros de Voos Regulares Ativos (VRA) da ANAC de 2019. A unidade de análise é a ocorrência de uma etapa de voo. A entrada consiste nos 12 CSVs mensais, de `VRA_2019_01.csv` a `VRA_2019_12.csv`. O notebook recebe esses arquivos em um ZIP no Colab. O manifesto identifica as fontes utilizadas pelo projeto. [Manifesto VRA](../dados/manifesto_vra.json) · [Notebook ELT 2019](../notebooks/elt/elt_2019.ipynb)

## Processo

1. **RAW.** O notebook confere os 20 cabeçalhos, lê os valores como texto, acrescenta `arquivo_origem` e `linha_origem` e usa `COPY` em lotes para carregar `elt_2019.vra_bruta` no PostgreSQL. As consultas seguintes conferem o total carregado e a distribuição pelas 12 origens.
2. **STAGING.** No notebook, a tabela classificada, as auditorias e `vra_tratada` ficam no schema `elt_2019`. O PostgreSQL faz a deduplicação, a classificação de rejeições e a conversão de tipos. Na integração final, o fluxo usa os schemas `raw` e `staging_elt`, com o template SQL compartilhado de 2019 e 2020.
3. **DW.** Na integração final, as ocorrências tratadas alimentam `dw_elt.fato_voo`. A carga resolve as chaves das sete dimensões de tempo, companhia, aeroporto, situação do voo, justificativa, tipo de linha e equipamento. Tempo e aeroporto exercem papéis distintos na partida e na chegada. A fato representa uma ocorrência válida após a deduplicação, com vínculo de origem para rastrear o registro até o CSV.

[Notebook ELT 2019](../notebooks/elt/elt_2019.ipynb) · [Template de transformação](../sql/transformacoes/elt_2019_2020.sql) · [Criação do DW](../sql/database/10_criacao_dw.sql) · [Carga dimensional](../sql/integracao/03_carga_dw.sql) · [Integração final](../documentacao/INTEGRACAO_FINAL.md)

## Regras e decisões

- A classificação usa `ROW_NUMBER()` sobre a partição pelos 20 campos brutos e ordena as ocorrências pela origem. A primeira é a representante do grupo. As excedentes ficam na auditoria e todas as ocorrências permanecem no RAW.
- Após a deduplicação, a elegibilidade exige companhia, aeroportos de origem e destino e horários previstos de partida e chegada válidos. As rejeições permanecem vinculadas à origem. Uma linha pode ter mais de um motivo.
- O SQL padroniza textos, converte vazios em `NULL` e tipa datas e assentos. O número do voo permanece textual, com seus zeros à esquerda. Os horários são tratados sem conversão de fuso.
- A diferença temporal é calculada em minutos entre o horário real e o previsto. Antecipações mantêm a diferença negativa e têm atraso igual a zero. Horário real ausente produz métricas temporais nulas. Diferenças absolutas acima de 24 horas recebem flags e permanecem na camada tratada.

[Contrato de tratamento v1.1](../documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf) · [Qualidade anual](QUALIDADE_2019_2021.md)

## Resultados da execução e validação

| Indicador | Resultado do notebook |
|---|---:|
| Registros brutos no PostgreSQL | 983.414 |
| Ocorrências duplicadas excedentes | 470 |
| Ocorrências rejeitadas após deduplicação | 18 |
| Registros tratados | 982.926 |
| Partidas com diferença absoluta acima de 24 h | 684 |
| Chegadas com diferença absoluta acima de 24 h | 690 |

A saída salva do notebook registra a conciliação `983.414 = 470 + 18 + 982.926`. Na auditoria SQL integrada, as 470 excedentes vieram de 444 grupos que envolveram 914 ocorrências. A interseção entre excedentes e inválidos foi zero. Entre as 18 rejeições, todas tinham partida e chegada previstas ausentes e 14 também tinham aeroporto de destino ausente.

A comparação integral registrou **982.926 fatos de 2019 em cada DW**, rastreabilidade verificada nos dois fluxos e **zero divergências de conteúdo** para 2019. Esse resultado é da carga integrada. [Notebook ELT 2019](../notebooks/elt/elt_2019.ipynb) · [Diagnóstico SQL](../resultados/validacoes/integracao_final/diagnosticos_contrato_sql.csv) · [Qualidade anual](QUALIDADE_2019_2021.md) · [Comparação integral](../resultados/validacoes/integracao_final/comparacao_integral.json)

## Considerações finais

A execução individual comprova a carga bruta e a transformação SQL até `vra_tratada`. A evidência da fato e da equivalência com o ETL pertence à integração final. As contagens de atípicos acima são as medidas depois da deduplicação e da seleção dos registros tratados. O contrato também traz números históricos da exploração anterior à deduplicação. [Qualidade anual](QUALIDADE_2019_2021.md)
