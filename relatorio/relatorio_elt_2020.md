# ELT dos dados VRA/ANAC — 2020

> **Nota histórica.** Este relatório registra os procedimentos e resultados da entrega individual. A carga dimensional, a integração de 2019 a 2021 e a comparação integral entre ETL e ELT foram concluídas posteriormente pelo pipeline integrado. Consulte o [relatório final do projeto](STATUS_FINAL_PROJETO.md).

Responsável pela adaptação: Gustavo José Arraes de Queiroz.
Base: notebook ELT de 2019 desenvolvido pelo grupo.

## Objetivo e escopo

Implementar o processamento dos 12 arquivos mensais de 2020
pela abordagem ELT: extrair os registros dos CSVs, carregar
os valores originais no PostgreSQL e transformar os dados
dentro do banco usando SQL.

Esta etapa entrega a camada tratada e suas evidências de
auditoria. Não inclui a criação das dimensões e da tabela
fato compartilhadas entre os anos.

## Processo

O notebook foi executado no Google Colab, com PostgreSQL
instalado no ambiente temporário da sessão.

O Python confere os 12 arquivos e seus 20 cabeçalhos originais.
Os registros são carregados com COPY no schema elt_2020,
preservando os valores originais como texto.

As colunas arquivo_origem e linha_origem permitem localizar
cada registro no CSV de origem. O inventário registra as
quantidades e os hashes SHA-256 dos arquivos utilizados.

Após a carga, o SQL realiza a deduplicação, a padronização,
a conversão de tipos, a separação de rejeições e o cálculo
das métricas.

## Regras e decisões

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
| Registros brutos | 483.545 |
| Duplicatas excedentes | 124 |
| Registros rejeitados | 1.512 |
| Registros tratados | 481.909 |
| Partidas com diferença absoluta superior a 24 horas | 286 |
| Chegadas com diferença absoluta superior a 24 horas | 331 |
| Registros tratados sem partida real | 21.845 |
| Registros tratados sem chegada real | 21.845 |

A reconciliação foi satisfeita:

483.545 = 124 + 1.512 + 481.909

As 1.512 rejeições apresentaram ausência tanto de partida
prevista quanto de chegada prevista. Portanto, existem dois
motivos por registro, sem duplicar a contagem de rejeições.

Os registros tratados foram distribuídos em:
460.064 REALIZADO, 21.487 CANCELADO e 358 NÃO INFORMADO.

## Validação e auditoria

As verificações executadas confirmaram:

- Correspondência das contagens entre CSVs e carga bruta.
- Reconciliação total e por arquivo mensal.
- Preenchimento dos campos obrigatórios na tabela tratada.
- Separação entre registros tratados, rejeitados e
  duplicatas excedentes.
- Consistência dos cálculos de atraso.
- Tratamento de datas impossíveis, anos bissextos,
  horários inválidos e valores inteiros fora do limite.

A auditoria de conversões opcionais e de referência fora
de 2020 registrou zero ocorrências. Isso não significa
ausência de valores suspeitos: as diferenças de horário
atípicas são contabilizadas separadamente.

Por exemplo, foi encontrada uma chegada real no ano 2202.
Como a data é válida no calendário, foi preservada e sua
diferença de horário foi sinalizada como atípica.
Não foi presumida uma data correta para substituí-la.

## Reprodução e evidências

Executar [elt_2020.ipynb](../notebooks/elt/elt_2020.ipynb) no Colab, em ordem,
enviando o ZIP com os 12 CSVs originais de 2020.

O notebook preserva o SQL da execução individual nas suas células. A integração usa o [template compartilhado](../sql/transformacoes/elt_2019_2020.sql), parametrizado pelo Python para 2019 e 2020. A [decisão técnica](../documentacao/DECISOES_TECNICAS.md) descreve os parâmetros e a geração.

O notebook gera as evidências abaixo. Na entrega simplificada, os resumos individuais permanecem versionados e as exportações detalhadas são regeneradas pela execução das células de exportação. As orientações históricas dos notebooks para publicar CSVs correspondem à entrega individual. Consulte o [inventário e os comandos de regeneração](LIMPEZA_RESULTADOS.md).

Os destinos das exportações são:

- resultados/logs/: inventário e metadados da execução.
- resultados/rejeicoes/: rejeições, motivos e duplicatas.
- resultados/validacoes/: contagens e consultas de validação.

Como o banco no Colab é temporário, o notebook permite
reconstruir o processamento a partir dos arquivos originais.

## Pendências e limitações

A equivalência com o ETL de 2020 ainda precisa ser conferida,
comparando os arquivos de entrada, os critérios e os valores
produzidos por registro. A igualdade dos totais, isoladamente,
não comprova equivalência completa.

As diferenças atípicas podem distorcer médias de atraso.
Qualquer análise que filtre esses registros deve explicitar
esse critério.

A integração das dimensões e da tabela fato e as análises
conjuntas dos anos permanecem como etapas do grupo.
