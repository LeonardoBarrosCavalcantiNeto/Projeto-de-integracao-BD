# ETL VRA/ANAC 2020 — execução e material da entrega

**Contrato:** v1.1. **Validação:** 16/11/2026. O tratamento e a carga de 2020 foram executados; o notebook salvo no projeto contém o retorno `ja_carregada` e está com `EXECUTAR_CARGA = False`. As consultas de validação no PostgreSQL foram aprovadas. A comparação por registro com o ELT e a consolidação com 2019/2021 continuam pendentes.

## 1. Justificativa da base e das tecnologias — seção 3 do grupo

O grupo escolheu registros VRA da ANAC de 2019, 2020 e 2021. Os anos consecutivos permitem comparar o planejamento e a realização de etapas de voos por companhia, aeroporto e período. A fonte também permite demonstrar problemas de integração: arquivos mensais, códigos textuais, datas, valores ausentes, duplicatas e descrições conflitantes.

Uma ocorrência corresponde a uma etapa de voo da fonte, não a passageiros nem necessariamente a uma viagem completa com conexões. A camada analítica contém representantes elegíveis; excedentes e rejeições permanecem auditáveis.

| Tecnologia | Papel e justificativa |
|---|---|
| Python/Pandas | Extração e tratamento do ETL antes da carga; validação de campos, deduplicação e cálculo das medidas |
| PostgreSQL | Armazenamento das camadas e do esquema estrela; tipos, unicidade, chaves e consultas; transformação SQL no ELT |
| SQLAlchemy/psycopg | Conexão configurável e carga transacional, com verificação de reexecuções |
| pgAdmin | Administração da conexão e conferência do banco por SQL |
| Colab/Jupyter | Código acompanhado de explicações e resultados intermediários; Colab com ambiente local para acessar o PostgreSQL do Mac |
| Git/GitHub | Autoria, histórico do contrato, revisão cruzada e organização da entrega |

## 2. Extração, tratamento e auditorias

1. **Extração:** conferimos os 12 nomes mensais, os 20 cabeçalhos e a largura de cada registro. Todos os valores entram como texto, preservando vazios e zeros à esquerda. Acrescentamos ano, arquivo, registro lógico e metadados da execução. SHA-256 identifica os arquivos; os originais não são modificados.
2. **Deduplicação:** comparamos os 20 valores brutos antes da padronização e mantemos a primeira ocorrência por arquivo/linha. As excedentes ficam na auditoria, ligadas à representante. Igualdade que aparece somente após trim/upper é informada sem exclusão adicional.
3. **Padronização:** removemos espaços externos, convertemos vazios em nulos e códigos/situações em maiúsculas. Descrições mantêm grafia; número do voo e DI continuam texto.
4. **Validação:** companhia ICAO, origem, destino e os dois horários previstos são obrigatórios. Registramos todos os motivos de rejeição. Datas reais, referência e assentos inválidos ficam nulos com anomalia, sem rejeitar o voo por esse motivo. A interseção excedentes × inválidos é medida separadamente.
5. **Métricas:** diferença = real − previsto, em minutos e com sinal; atraso = máximo entre diferença e zero. Sem horário real, ambas são nulas. A flag indica diferença absoluta estritamente maior que 1.440 minutos; exatamente 24h não aciona a flag. Sem diferença calculável, a flag fica falsa.

Os timestamps completos preservam mudanças de dia/mês/ano. Datas suspeitas não recebem correção de ano por inferência. Não atribuímos fuso nem presumimos a semântica de referência ou um limiar de pontualidade ainda não definido pelo grupo.

## 3. Resultados de 2020

| Indicador | Resultado |
|---|---:|
| Arquivos / colunas originais | 12 / 20 |
| Brutos | 483.545 |
| Grupos duplicados / ocorrências envolvidas | 124 / 248 |
| Excedentes removidos | 124 |
| Após deduplicação | 483.421 |
| Rejeitados / motivos | 1.512 / 3.024 |
| Elegíveis na tratada e na fato | 481.909 |
| Interseção excedentes × inválidos | 0 |
| Possíveis duplicidades apenas após padronização | 0 |
| Anomalias opcionais de conversão | 0 |
| Partidas previstas em ano diferente de 2020 | 15 |
| Partidas / chegadas reais ausentes | 21.845 / 21.845 |
| Partidas / chegadas atípicas >24h | 286 / 331 |

**Reconciliação aprovada, total e por arquivo: 483.545 = 124 + 1.512 + 481.909.** Cada rejeitado está sem os dois horários previstos: são dois motivos por registro, sem duplicar a contagem de rejeições.

Os elegíveis incluem 460.064 realizados, 21.487 cancelados e 358 NÃO INFORMADO. Os dois horários reais faltam nos mesmos 21.845 registros. Nulo não foi convertido em zero nem interpretado automaticamente como cancelamento.

As chegadas de 04/02/2022 (fevereiro, registro lógico 28.805) e 23/12/2202 (dezembro, registro 19.916) são válidas no calendário e foram preservadas, sinalizadas e conferidas no banco. As 15 partidas previstas fora do ano do arquivo também não foram excluídas.

## 4. Dimensão de aeroportos e estrela experimental

A dimensão combina os papéis origem e destino e utiliza ICAO como chave natural. Há 385 aeroportos no teste de 2020. Duas descrições conflitantes foram resolvidas somente na dimensão, preservando os códigos e descrições dos voos:

- **SBEG:** Eduardo Gomes / Manaus, conforme [Portaria ANAC de 2020](https://www.anac.gov.br/assuntos/legislacao/legislacao-1/portarias/2020/portaria-no-3204-sia-10-11-2020/@@display-file/arquivo_norma/PA2020-3204.pdf).
- **SWHP:** Olhos D’Água / Água Boa, MT, conforme [cadastro ANAC](https://www.anac.gov.br/assuntos/setor-regulado/aerodromos/localizacao-geografica-arquivos/aerodromos/publicos-todas-as-regioes/download.table), preservando o nome histórico observado na fonte.

O mapeamento exato e suas justificativas estão em [resolucoes_aeroportos_2020.csv](../documentacao/resolucoes_aeroportos_2020.csv). Revisar essas decisões no PR; novos conflitos bloqueiam a dimensão e a carga.

Reutilizamos o construtor de estrela integrado pelo ETL 2019 em uma instância configurada para 2020, sem modificar o arquivo do integrante. Isso permite testar as relações sem criar outra definição da fato. Os IDs são experimentais, não definitivos do DW consolidado.

| Dimensão experimental | Registros |
|---|---:|
| Tempo | 368 |
| Companhia aérea | 115 |
| Aeroporto | 385 |
| Situação do voo | 3 |
| Justificativa | 46 |
| Tipo de linha | 9 |
| Equipamento | 62 |

Justificativa/equipamento ausentes usam membro 0; situação/tipo de linha opcionais ausentes mantêm FK nula. As nove relações foram verificadas em memória e no PostgreSQL, sem órfãos.

Para consolidar aeroportos quando as três saídas estiverem disponíveis:

```bash
python scripts/dim_aeroporto.py --tratadas dados/processados/2019/vra_tratada.csv.gz dados/processados/2020/vra_tratada.csv.gz dados/processados/2021/vra_tratada.csv.gz --output-dir dados/processados/compartilhado
```

O modo final exige os três anos. `--experimental` permite uma entrada parcial. Se existir cadastro com IDs já utilizados, passe `--registro-existente caminho/dim_aeroporto.csv` para preservá-los; não concatene IDs experimentais independentes.

## 5. Execução e carga PostgreSQL

Na raiz do projeto, instale `requirements.txt` e coloque os 12 CSVs em `dados/brutos/2020/`. Execute [etl_2020.ipynb](../notebooks/etl/etl_2020.ipynb) ou:

```bash
python scripts/etl_vra_anac_2020.py
```

O tratamento exporta as saídas completas para `dados/processados/2020/`, fora do Git. O comando acima não carrega dados no banco.

Para a carga, crie `vra_dw_2020` no PostgreSQL e configure o `.env` local com PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD e `PGSCHEMA=etl_2020`. Use o usuário, senha e porta de sua instalação; não publique o arquivo. Se houver DATABASE_URL, ela tem precedência sobre os outros parâmetros de conexão.

Execute [configuracao_banco.ipynb](../notebooks/configuracao_banco.ipynb), que apenas testa a conexão. Depois de conferir o tratamento, ative `EXECUTAR_CARGA` na última célula do ETL. O script oferece a alternativa explícita `--carregar`. Ao terminar, volte a variável para `False` antes de salvar o notebook.

A carga usa transação única, dimensões antes da fato e medidas NUMERIC(12,2). Mantém os 20 campos brutos em TEXT e impõe PKs, unicidade e FKs. Uma execução reconhecida retorna `ja_carregada` sem inserir novamente; um schema de outra execução é recusado. Não há substituição automática de tabelas. A verificação de reexecução confere identidade e contagens, não toda alteração manual possível no conteúdo do banco.

Para acessar o PostgreSQL do computador pelo Colab, use um [ambiente de execução local](https://research.google.com/colaboratory/local-runtimes.html). Em uma sessão hospedada, `localhost` é a máquina do Google.

## 6. Validação e evidências

A carga foi executada pelo integrante no Colab com ambiente local. A cópia executada está salva no projeto, com o retorno `ja_carregada` e a carga desativada. A consulta posterior ao banco `vra_dw_2020`, schema `etl_2020`, utilizou transação somente de leitura e confirmou:

- 481.909 registros na fato e reconciliação aprovada.
- Zero origens duplicadas e zero órfãos nas nove FKs.
- Zero inconsistências ao recalcular diferenças, atrasos e flags por SQL.
- Fingerprint registrado compatível com a execução e anomalias de 2022/2202 preservadas.

A confirmação da reexecução veio do integrante e também aparece na saída salva do notebook. A evidência da consulta é [validacao_postgresql_etl_2020.json](../resultados/validacoes/validacao_postgresql_etl_2020.json). As consultas reutilizáveis estão na seção **7. Validação SQL da carga** do [notebook ETL](../notebooks/etl/etl_2020.ipynb). Elas são executadas em transação somente de leitura e não fazem carga.

A entrega versiona somente o inventário dos CSVs, o resumo de qualidade da fase de tratamento e a validação posterior do PostgreSQL. As saídas completas e auditorias de rejeições, motivos, duplicatas e anomalias continuam em `dados/processados/2020/` e no banco. Cópias históricas de evidências detalhadas ficam em `dados/processados/2020/evidencias_locais/`, fora do Git. O resumo da fase de tratamento antecede a carga; sua linha de status não substitui o JSON de validação posterior. O notebook reúne as consultas SQL e suas saídas.

Durante o desenvolvimento, oito testes sintéticos foram executados sobre opcionais inválidos, interseção duplicatas × inválidos, igualdade após padronização sem nova exclusão, limites de 24h, antecipação, ano 2202, conflitos e estabilidade de IDs, múltiplos motivos, todas as linhas rejeitadas e resolução das nove FKs. O arquivo de apoio desses testes não integra a entrega atual; as verificações reproduzíveis da carga e das métricas estão no notebook e na evidência PostgreSQL.

## 7. Proposta da Análise 2 — cancelamentos mensais

**Pergunta:** como variam volume e proporção de cancelamentos nos arquivos mensais de 2020? O denominador é o total elegível de cada arquivo após deduplicação/rejeições. O mês vem do CSV, não da partida prevista; NÃO INFORMADO permanece categoria separada. A análise não representa passageiros nem inclui os rejeitados.

Os resultados foram calculados em Python e reproduzidos em PostgreSQL por consultas somente de leitura. A seção **8. Análise 2** do [notebook ETL](../notebooks/etl/etl_2020.ipynb) reúne as consultas e as saídas, separadamente das validações da seção 7. O JSON histórico da execução SQL permanece na pasta local de evidências; não é necessário publicá-lo em paralelo às saídas do notebook.

| Mês do arquivo | Elegíveis | Realizados | Cancelados | Não informado | Cancelados (%) |
|---|---:|---:|---:|---:|---:|
| Janeiro | 92.386 | 91.079 | 1.307 | 0 | 1,41 |
| Fevereiro | 80.889 | 79.086 | 1.801 | 2 | 2,23 |
| Março | 64.428 | 60.220 | 4.203 | 5 | 6,52 |
| Abril | 7.551 | 6.161 | 1.376 | 14 | 18,22 |
| Maio | 9.444 | 8.103 | 1.330 | 11 | 14,08 |
| Junho | 12.636 | 11.332 | 1.294 | 10 | 10,24 |
| Julho | 19.597 | 18.156 | 1.440 | 1 | 7,35 |
| Agosto | 24.547 | 23.094 | 1.208 | 245 | 4,92 |
| Setembro | 30.418 | 29.192 | 1.225 | 1 | 4,03 |
| Outubro | 40.455 | 38.396 | 2.058 | 1 | 5,09 |
| Novembro | 45.399 | 43.390 | 2.006 | 3 | 4,42 |
| Dezembro | 54.159 | 51.855 | 2.239 | 65 | 4,13 |

Abril tem o menor volume elegível e a maior proporção de cancelamentos (18,22%). Março tem o maior número absoluto de cancelamentos (4.203). O volume cresce de abril a dezembro, mas dezembro ainda fica abaixo de janeiro. Esses padrões não comprovam causas por si só. Agosto concentra 245 dos 358 NÃO INFORMADO e requer atenção à qualidade/categoria da fonte.

A média de atraso nas chegadas medidas é 221,41 minutos com todas as medições e 8,29 minutos ao filtrar explicitamente `NOT chegada_atipica_flag`. O filtro desconsidera as 331 chegadas atípicas na consulta, sem alterar a base. A análise deve ser revisada com o parceiro e estendida aos três anos com definições comuns.

## 8. Conteúdo para slides e reflexão

Roteiro para inserir na apresentação do grupo; não é um deck final:

1. **Escolha da base:** VRA/ANAC, anos 2019–2021, perguntas sobre operação aérea e desafios de qualidade; uma linha representa uma etapa de voo.
2. **Tecnologias:** Python/Pandas tratam o ETL; PostgreSQL armazena o modelo e transforma o ELT; pgAdmin inspeciona; Colab documenta a execução; GitHub registra autoria/revisões.
3. **Evidência de 2020:** reconciliação 483.545 = 124 + 1.512 + 481.909; nulos preservados; 286/331 flags; carga validada e sem órfãos. Incluir prints da execução.
4. **Aeroportos e integração:** uma dimensão nos papéis origem/destino, 385 aeroportos experimentais, conflitos documentados e cadastro final dependente dos três anos.

No quadro final de contribuição, registrar ETL 2020, preparação da dimensão de aeroportos, configuração do banco, seção 3 e participação na Análise 2. Marcar a revisão do parceiro como concluída somente depois do PR.

**Reflexão — rascunho a personalizar antes da entrega:**

Ao trabalhar no ETL de 2020, um desafio foi distinguir ausência permitida, erro em campo obrigatório e valor temporal suspeito. Aprendi que manter os dados brutos e a origem de cada registro permite explicar por que uma ocorrência foi rejeitada ou sinalizada, sem inventar correções. A necessidade de comparar ETL e ELT evidenciou que totais iguais não bastam: atributos e medidas também precisam seguir o mesmo contrato. As descrições conflitantes de aeroportos mostraram a importância das chaves naturais e das decisões documentadas do grupo.

## 9. Comparação com o ELT e pendências

Os 12 hashes e os oito indicadores comparáveis publicados pelo ELT coincidem com o ETL. A equivalência por registro ainda não foi verificada porque o schema do parceiro não está disponível no banco de comparação. Quando estiver:

```bash
python scripts/comparar_2020.py --elt-schema elt_2020
```

O comando é somente de leitura: compara os 20 atributos tratados, medidas, flags, valores brutos e identidades de rejeitados/excedentes, sem comparar IDs técnicos. Ele não executa nem carrega o pipeline do parceiro.

Pontos preparados para a revisão cruzada, ainda não enviados ao PR:

- Conferir diagnóstico de igualdade apenas após trim/upper e interseção excedentes × inválidos.
- Verificar as 15 partidas previstas fora de 2020; o SQL do parceiro verifica ano de referência, que é outro indicador.
- Comparar os valores por arquivo/linha, além dos totais.
- Corrigir no relatório do parceiro o caminho `notebooks/ELT/elt_2020.ipynb` para o caminho versionado `notebooks/elt/elt_2020.ipynb`.

Restam a revisão cruzada no GitHub, a integração dimensional dos três anos, a revisão conjunta da análise e a inserção destes conteúdos no relatório/apresentação final. Revisar o parágrafo pessoal e registrar autoria e evidências antes dos commits do integrante.

## 10. Organização da entrega após a revisão dos arquivos

Os dois arquivos SQL de validação/análise foram incorporados ao notebook e retirados como arquivos separados. O SQL de transformação do ELT e os demais arquivos dos parceiros foram preservados. As auditorias detalhadas permanecem locais e no PostgreSQL; sua retirada do Git não elimina a rastreabilidade.

| Arquivos mantidos | Motivo |
|---|---|
| Notebook de exploração de 2020 | Diagnóstico inicial da fonte; já estava na branch |
| Notebook ETL 2020 | Pipeline executado, carga, validações SQL e análise com resultados |
| Notebook de configuração do banco | Item atribuído ao integrante; teste de conexão sem carga |
| Script ETL 2020 | Implementação usada pelo notebook; evita duplicar as regras |
| Script de aeroportos | Consolidação dos três anos e manutenção de IDs existentes |
| Script de comparação | Conferência ETL × ELT quando o parceiro disponibilizar as tabelas |
| Resoluções de aeroportos | Entrada utilizada pelo código para os dois conflitos documentados |
| Este relatório | Texto único para explicações, resultados e material da entrega |
| Inventário dos CSVs | Identidade dos arquivos de entrada para comparação da dupla |
| Resumo de qualidade | Indicadores da fase de tratamento |
| Validação PostgreSQL | Evidência independente da carga e dos relacionamentos |

O script continua podendo gerar diagnósticos locais. O `.gitignore` exclui da entrega as cópias detalhadas regeneráveis, sem ocultar os arquivos do ELT do parceiro. Nenhum dado do banco foi alterado por esta reorganização.
