# ELT dos dados VRA/ANAC — 2021

> **Nota histórica.** Este relatório registra os procedimentos e resultados da entrega individual. A carga dimensional, a integração de 2019 a 2021 e a comparação integral entre ETL e ELT foram concluídas posteriormente pelo pipeline integrado. Consulte o [relatório final do projeto](STATUS_FINAL_PROJETO.md).

Responsável: Murilo Acioli.
Base: notebook ELT de 2020 (Gustavo José Arraes de Queiroz),
derivado do ELT de 2019 do grupo.

## Objetivo e escopo

Implementar o processamento dos 12 arquivos mensais de 2021
pela abordagem ELT: extrair os registros dos CSVs, carregar
os valores originais no PostgreSQL e transformar os dados
dentro do banco usando SQL.

Esta etapa entrega a camada tratada e suas evidências de
auditoria. Não inclui a criação das dimensões e da tabela
fato compartilhadas entre os anos.

## Fonte

Arquivos mensais do VRA publicados pela ANAC em
`https://siros.anac.gov.br/siros/registros/diversos/vra/2021/`
(`VRA_2021_01.csv` a `VRA_2021_12.csv`).

É a mesma origem usada em 2020: os tamanhos dos arquivos de
2020 publicados nesse endereço coincidem byte a byte com o
inventário do ELT 2020. O inventário de 2021 registra a
quantidade de registros e o SHA-256 de cada CSV, para que o
ETL de 2021 confira que usou exatamente os mesmos arquivos.

## Processo

O notebook foi executado no Google Colab em 16/11/2026, com
PostgreSQL 16 instalado no ambiente temporário da sessão. Uma
execução de conferência fora do Colab, com os mesmos CSVs,
produziu resultados idênticos.

O notebook baixa os CSVs direto da ANAC, sem alterar nenhum
byte; também aceita o envio manual de `data_2021_anac.zip`.

O Python confere os 12 arquivos e seus cabeçalhos. Os registros
são carregados com COPY no schema `elt_2021`, preservando os
valores originais como texto, com `arquivo_origem` e
`linha_origem`.

Após a carga, o SQL realiza a deduplicação, a padronização,
a conversão de tipos, a separação de rejeições e o cálculo
das métricas.

## Diferenças de 2021 em relação a 2019 e 2020

**1. Dois layouts no mesmo ano.** Sete meses (01, 02, 03, 07,
09, 11 e 12) estão publicados com uma 21ª coluna, `Codeshare`,
e quebra de linha CRLF. Os outros cinco (04, 05, 06, 08 e 10)
têm as 20 colunas de sempre, com quebra LF. As 20 primeiras
colunas são idênticas ao contrato.

| Layout | Arquivos | Registros |
|---|---:|---:|
| 20 colunas | 5 | 227.732 |
| 21 colunas (com `Codeshare`) | 7 | 404.416 |

Decisão: `Codeshare` é preservada na camada bruta, mas não
entra na comparação de duplicatas nem na camada tratada, porque
o contrato define as 20 colunas originais. Na camada bruta,
`NULL` indica que o arquivo do mês não tem a coluna; texto
vazio indica que ela existe, mas veio em branco
(291.937 vazios e 112.479 preenchidos, como `GLO/3801`).

Com ou sem `Codeshare`, não há duplicatas exatas em 2021,
então a decisão não altera nenhuma contagem.

**2. Dois formatos de `Referência`.** Nos meses com 21 colunas,
o valor vem como `DD/MM/AAAA 00:00:00`; nos demais, como
`AAAA-MM-DD`. A função `data_segura` foi ampliada para aceitar
os dois e converter para `DATE`. Nenhuma referência ficou sem
conversão.

**3. Volume de voos sem horário previsto.** 25.511 registros
(4,0% do ano) não têm partida nem chegada previstas. Todos
são voos `REALIZADO`, com horários reais preenchidos: etapas
operadas fora da programação. Pelo contrato, horário previsto
é obrigatório, então eles vão para `vra_rejeicoes`. Em 2020
foram 1.512 registros sem as duas datas previstas.

Isso deve ser lembrado nas análises: a camada tratada mede
voos programados; quem quiser contar todas as operações
realizadas precisa considerar também a tabela de rejeições.

## Regras e decisões (iguais às de 2020)

- Duplicatas são identificadas pela igualdade dos 20 campos
  originais, antes de qualquer padronização.
- A primeira ocorrência, ordenada por arquivo e linha, é
  preservada. As excedentes ficam em uma tabela de auditoria.
- Campos textuais vazios tornam-se NULL na camada tratada.
  Códigos são padronizados em maiúsculas; nomes e descrições
  mantêm sua grafia.
- Companhia, aeroportos de origem e destino e horários
  previstos de partida e chegada são obrigatórios.
- Registros sem esses campos ou com datas previstas inválidas
  são separados, com todos os motivos de rejeição.
- Campos opcionais inválidos são auditados sem provocar,
  por si só, a rejeição do registro.
- As diferenças entre horários reais e previstos são
  calculadas em minutos, mantendo o sinal.
- O atraso é o máximo entre a diferença e zero.
  Sem horário real, a diferença e o atraso permanecem NULL.
- Diferenças absolutas superiores a 24 horas são sinalizadas.
  Esses valores são preservados, sem correção automática.
- Os horários são armazenados sem conversão de fuso.
- As transformações não alteram a tabela bruta.

## Resultados da execução

| Indicador | Quantidade |
|---|---:|
| Arquivos mensais | 12 |
| Registros brutos | 632.148 |
| Duplicatas excedentes | 0 |
| Registros rejeitados | 25.511 |
| Registros tratados | 606.637 |
| Partidas com diferença absoluta superior a 24 horas | 371 |
| Chegadas com diferença absoluta superior a 24 horas | 373 |
| Registros tratados sem partida real | 26.139 |
| Registros tratados sem chegada real | 26.141 |
| Anomalias em campos opcionais | 0 |

A reconciliação foi satisfeita, no total e em cada mês:

632.148 = 0 + 25.511 + 606.637

As 25.511 rejeições têm os dois motivos (partida e chegada
previstas ausentes); contam como 25.511 registros, não 51.022.

Os registros tratados foram distribuídos em:
580.498 REALIZADO, 25.962 CANCELADO e 177 NÃO INFORMADO.

Comparação com 2020: 481.909 registros tratados em 2020 contra
606.637 em 2021 (+25,9%), coerente com a retomada após o pior
período da pandemia.

## Auditorias adicionais do contrato v1.1

Estas verificações não alteram a camada tratada; só registram
pontos para a integração.

- **Duplicatas que só aparecem após TRIM/UPPER:** 0.
- **Partidas previstas fora de 2021:** 15 registros
  (mantidos, como manda o contrato).
- **Códigos ICAO com mais de uma descrição:** 9 códigos,
  em `vra_conflitos_codigo`. Exemplos: `OWT` aparece como
  "TWO TÁXI AÉREO LTDA." e como "AZUL CONECTA LTDA. (EX TWO
  TAXI AEREO LTDA)"; `SWHP` aparece com UF MG e com UF MT.
  O contrato pede que o grupo resolva esses conflitos antes de
  publicar as dimensões compartilhadas; nenhuma descrição foi
  escolhida aqui.

## Validação

As verificações executadas confirmaram:

- Correspondência das contagens entre CSVs e carga bruta.
- Preservação de `Codeshare` conforme o layout de cada mês.
- Reconciliação total e por arquivo mensal.
- Preenchimento dos campos obrigatórios na tabela tratada.
- Separação entre registros tratados, rejeitados e
  duplicatas excedentes.
- Consistência dos cálculos de atraso.
- Tratamento de datas impossíveis, anos bissextos, horários
  inválidos, valores inteiros fora do limite e os dois
  formatos de `Referência`.

## Reprodução e evidências

Executar `notebooks/elt/elt_2021.ipynb` no Colab, em ordem
(Ambiente de execução → Executar tudo).

O SQL separado está em `sql/transformacoes/elt_2021.sql`
e pressupõe a carga bruta criada pelo notebook.

O notebook gera as evidências abaixo. Na entrega simplificada, os resumos individuais permanecem versionados e as exportações detalhadas são regeneradas pela execução das células de exportação. As orientações históricas dos notebooks para publicar CSVs correspondem à entrega individual. Consulte o [inventário e os comandos de regeneração](LIMPEZA_RESULTADOS.md).

Os destinos das exportações são:

- `resultados/logs/`: inventário (com SHA-256) e metadados.
- `resultados/rejeicoes/`: motivos de rejeição e duplicatas. O CSV
  completo das 25.511 rejeições (8 MB) não foi versionado; ele é
  gerado pelo notebook dentro de `evidencias_elt_2021.zip`.
- `resultados/validacoes/`: contagens, layouts, conflitos e
  consultas de validação.

## Pendências e limitações

A equivalência com o ETL de 2021 ainda precisa ser conferida,
comparando os hashes dos CSVs, os critérios e os valores
produzidos por registro. O ETL precisa tratar as mesmas duas
particularidades (coluna `Codeshare` e dois formatos de
`Referência`) para chegar aos mesmos números.

Os conflitos de descrição dos códigos ICAO precisam de uma
regra comum do grupo antes da criação das dimensões.

As diferenças atípicas podem distorcer médias de atraso.
Qualquer análise que filtre esses registros deve explicitar
esse critério.
