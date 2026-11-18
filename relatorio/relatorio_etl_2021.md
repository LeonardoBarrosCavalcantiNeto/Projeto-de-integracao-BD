# ETL dos dados VRA/ANAC — 2021

> **Nota histórica.** A execução salva no notebook abrange a extração, a transformação e a exportação das saídas. A carga no PostgreSQL e a comparação integral entre os DWs são comprovadas pelas evidências da integração final. [Relatório final do projeto](STATUS_FINAL_PROJETO.md)

## Objetivo e fonte

Tratar os registros de etapas de voo dos 12 CSVs mensais do VRA/ANAC, de `VRA_2021_01.csv` a `VRA_2021_12.csv`, segundo o contrato v1.1. O script individual usa Python e Pandas para extrair e transformar os dados. O notebook configura a execução e apresenta as auditorias. [Manifesto VRA](../dados/manifesto_vra.json) · [Notebook ETL 2021](../notebooks/etl/etl_vra_anac_2021.ipynb) · [Script ETL 2021](../scripts/etl_vra_anac_2021.py)

## Extração, tratamento e auditorias

1. **Leitura.** O script verifica os arquivos mensais e seus cabeçalhos, lê os CSVs com separador `;` e codificação `utf-8-sig` e mantém os campos como texto na entrada. O inventário registra os hashes. Ano, arquivo e posição lógica do registro identificam a origem.
2. **Layout.** Sete arquivos têm a coluna adicional `Codeshare`. A execução individual registrou 112.479 valores preenchidos. O campo é preservado na base bruta e o critério de duplicata exata usa os 20 campos do contrato. Repetições potenciais após a normalização são auditadas, sem exclusão automática.
3. **Padronização.** O Pandas aplica o mapeamento canônico, remove espaços nas extremidades, normaliza a caixa dos campos previstos e converte vazios em nulos. O número do voo continua textual. A conversão valida horários e assentos e aceita `AAAA-MM-DD` e `DD/MM/AAAA 00:00:00` para `Referência`.
4. **Elegibilidade.** Companhia, aeroportos de origem e destino e horários previstos válidos são obrigatórios. O script mantém os motivos associados a cada ocorrência rejeitada. Problemas em campos opcionais são tratados e auditados sem provocar rejeição por si sós.
5. **Métricas.** A diferença entre horário real e previsto conserva o sinal. O atraso é zero em antecipações e nulo quando falta o horário real. Diferenças absolutas acima de 24 horas são sinalizadas e preservadas. Partidas previstas fora do ano de origem e descrições conflitantes por código também são auditadas.

[Contrato de tratamento v1.1](../documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf) · [Implementação em Python](../scripts/etl_vra_anac_2021.py) · [Layout de 2021](../resultados/validacoes/integracao_final/layout_2021.json)

## Resultados e validação de qualidade

| Indicador | Resultado do notebook |
|---|---:|
| Registros brutos | 632.148 |
| Ocorrências duplicadas excedentes | 0 |
| Registros rejeitados | 25.511 |
| Registros tratados | 606.637 |
| Partidas com diferença absoluta acima de 24 h | 371 |
| Chegadas com diferença absoluta acima de 24 h | 373 |
| Partidas reais nulas | 26.139 |
| Chegadas reais nulas | 26.141 |
| Partidas previstas fora de 2021 | 15 |

A saída salva registra conciliação por arquivo e no ano, com `632.148 = 0 + 25.511 + 606.637`. As 25.511 rejeições têm os dois motivos de ausência de horário previsto. São duas contagens de motivos para o mesmo conjunto de registros rejeitados. O notebook conferiu a igualdade dos totais com os valores informados para o ELT de 2021. A verificação por ocorrência ficou para a integração final. [Notebook ETL 2021](../notebooks/etl/etl_vra_anac_2021.ipynb) · [Qualidade anual](QUALIDADE_2019_2021.md)

## Carga PostgreSQL e modelo dimensional

O script individual prevê carga transacional via SQLAlchemy e driver psycopg das tabelas tratadas e de auditoria no schema `etl_2021`. A saída salva registra `PostgreSQL: nao_executada`, portanto a execução individual comprova até a exportação local. A construção da fato e das dimensões ficou a cargo da integração do grupo. [Script ETL 2021](../scripts/etl_vra_anac_2021.py) · [Notebook ETL 2021](../notebooks/etl/etl_vra_anac_2021.ipynb)

Na integração, o tratamento continua no Pandas. O PostgreSQL preserva a origem em `raw_etl`, recebe as saídas tratadas em `staging_etl` e carrega `dw_etl.fato_voo`. A fato referencia sete dimensões compartilhadas pelos três anos e representa uma ocorrência elegível de etapa de voo. A comparação integral registra **606.637 fatos de 2021 em cada DW**, rastreabilidade verificada e **zero divergências de conteúdo** no ano. [Integração final](../documentacao/INTEGRACAO_FINAL.md) · [Modelo dimensional](../documentacao/MODELO_DIMENSIONAL_FINAL.md) · [Comparação integral](../resultados/validacoes/integracao_final/comparacao_integral.json)

## Considerações finais

A execução individual documenta as particularidades de layout e a conciliação dos CSVs de 2021 após a aplicação do contrato. A carga opcional pelo notebook permanece sem confirmação nas saídas salvas. A carga dimensional integrada e sua equivalência com o ELT têm evidências próprias. [Qualidade anual](QUALIDADE_2019_2021.md) · [Relatório final do projeto](STATUS_FINAL_PROJETO.md)
