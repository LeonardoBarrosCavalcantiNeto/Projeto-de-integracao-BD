# Entrega final VRA/ANAC — 2019, 2020 e 2021

**Execução histórica dos seis pipelines com 36 CSVs reais no PostgreSQL 18.6 isolado.** Os dois DWs registraram 2.071.472 fatos cada. A comparação integral de ocorrência e conteúdo encontrou zero divergências entre ETL e ELT. A revisão atual verificou a reprodução com fixtures em clusters descartáveis. [Verificações da revisão](PORTABILIDADE.md#revisão-da-entrega)

| Ano | ETL Pandas | ELT PostgreSQL | RAW por fluxo | Excedentes | Rejeições | `dw_etl` | `dw_elt` | Divergências |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2019 | Validado | Validado | 983.414 | 470 | 18 | 982.926 | 982.926 | 0 |
| 2020 | Validado | Validado | 483.545 | 124 | 1.512 | 481.909 | 481.909 | 0 |
| 2021 | Validado | Validado | 632.148 | 0 | 25.511 | 606.637 | 606.637 | 0 |
| **Total** | | | **2.099.107** | **594** | **27.041** | **2.071.472** | **2.071.472** | **0** |

As saídas Pandas de cada ano estão em `.local/final/etl/ANO/`. Incluem CSV tratado, duplicatas com ocorrência representante, rejeições com todos os motivos, anomalias, possíveis repetições após padronização, inventário e resumo. A pasta [de evidências versionáveis](../resultados/validacoes/integracao_final/) contém somente resultados compactos.

## Arquitetura e componentes

O ETL transforma os CSVs originais no Pandas, exporta os tratados e carrega `staging_etl` e `dw_etl`. O ELT carrega `raw`, transforma em SQL em `staging_elt` e carrega `dw_elt`. O ETL tem `raw_etl` para rastreabilidade e pode ser instalado sozinho. Cada DW possui sete dimensões e uma fato. A granularidade é uma ocorrência válida de etapa de voo depois da deduplicação exata.

A integração reutilizou a ingestão e os ELTs canônicos de 2019/2020, o ELT original de 2021, as funções Pandas de tratamento do integrante de 2021 e o DDL e a carga dimensionais existentes. Os scripts e notebooks experimentais de 2019/2020 foram preservados. O script e o notebook de 2021 foram incorporados com o conteúdo e autoria do commit original `65cf857`, via `5fddf68`. O gerador manual, o executor isolado e o mecanismo de backup foram reaproveitados.

As adaptações deram aos dois fluxos schemas independentes, unificaram o tratamento conforme o [contrato v1.1](../documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf) e incorporaram os dois formatos de referência de 2021. `Codeshare` ocorre em sete arquivos de 2021, tem 112.479 valores preenchidos e permanece no RAW. A chave de deduplicação usa os 20 campos contratuais. O cadastro dimensional adota a descrição não nula da ocorrência mais recente para cada código. As variantes ficam auditadas e as descrições históricas continuam no staging. As consultas classificam atraso positivo como atrasado, em todos os anos.

## Comparação, rastreabilidade e qualidade

O SQL compara os campos completos de RAW, tratados, duplicatas, rejeições, anomalias e fatos em cada ano. A chave `(ano_origem,id_raw)` preserva a multiplicidade de registros de negócio iguais. Para as fatos, as chaves de cada DW são resolvidas para os valores naturais das dimensões. As sete dimensões coincidiram, e cada fato tem dez chaves estrangeiras validadas, incluindo sua ligação ao staging.

A rastreabilidade foi verificada da fato até o CSV original, passando pela ocorrência bruta de cada fluxo. `linha_origem` é o ordinal lógico do registro, com cabeçalho contado como 1. Cada ocorrência bruta recebeu exatamente uma classificação. O teste conferiu o conteúdo e a origem de rejeições e duplicatas, a ocorrência preservada de cada duplicata e os vínculos das anomalias. A reexportação dos seis RAWs coincidiu em SHA-256 com os respectivos CSVs de ingestão. O manifesto registra os hashes e o layout dos 36 arquivos originais.

As auditorias Pandas e SQL coincidiram para grupos repetidos, registros envolvidos, interseção duplicata × rejeição, repetições após padronização e partidas previstas fora do ano de origem. Datas inválidas e horários reais ausentes preservam as regras de rejeição ou NULL do contrato. Diferenças absolutas acima de 24 h são sinalizadas. Veja [qualidade anual](QUALIDADE_2019_2021.md), [matriz de conformidade](../documentacao/MATRIZ_CONFORMIDADE_FINAL.md) e [resultado da comparação](../resultados/validacoes/integracao_final/comparacao_integral.json).

## Análises verificadas

Os resultados dos dois DWs coincidiram no total anual, perfil de NULLs, contagem dimensional, atrasos e antecipações, agregação por companhia, aeroportos de origem e destino e distribuição mensal. A média de atraso usa somente partidas com duração calculável. Um voo atípico pode permanecer na média e tem sua flag disponível para filtros de apresentação.

| Ano | Partidas calculáveis | Atrasadas | Antecipadas | Partidas >24h | Chegadas >24h | Média de atraso (min) |
|---|---:|---:|---:|---:|---:|---:|
| 2019 | 964.944 | 290.292 | 413.735 | 684 | 690 | 9,80 |
| 2020 | 460.064 | 127.339 | 250.332 | 286 | 331 | 9,76 |
| 2021 | 580.498 | 180.235 | 366.323 | 371 | 373 | 9,51 |

Nos três anos, SBGR teve o maior total de partidas e chegadas e AZU teve o maior total de ocorrências por companhia. O script [evidencias_final.py](../scripts/evidencias_final.py) regenera as tabelas com os totais por ano, aeroportos e companhias em `.local/final/evidencias/`. Os CSVs analíticos redundantes foram retirados da árvore versionada conforme o [inventário da limpeza](LIMPEZA_RESULTADOS.md).

## Recuperação, testes e reexecução

A carga dos 36 CSVs foi executada em cluster novo. Os logs da execução anterior registram o commit das duas cargas e as duas reexecuções. Após a interrupção da comparação, a recuperação WAL retornou o cluster a um encerramento limpo. A conferência seguinte encontrou a quantidade esperada de fatos em cada ano, por schema. Os DWs recuperados foram reutilizados na comparação final em lotes de 25 mil ocorrências. Ela levou 9min09s e atingiu cerca de 344 MiB de memória residente. O 143 relatado é compatível com SIGTERM, sem evidência que o atribua a OOM. O status 2 visível no histórico veio de uma listagem de logs analíticos ainda inexistentes.

Na entrega original no Fedora, sete testes automatizados passaram com o comando `.venv/bin/python -m unittest discover -s tests -v`. Dois verificam a reserva de armazenamento simulando o espaço disponível. As fixtures foram executadas em clusters vazios e cobriram os seis fluxos, a instalação do ETL sem ELT, o roteiro manual, a reexecução, datas inválidas, CSV multilinha, valores ausentes, variáveis de layout, auditorias e uma divergência proposital. Os totais e evidências da tabela principal correspondem aos CSVs reais. A [verificação posterior de portabilidade](PORTABILIDADE.md) registra os testes adicionais no Fedora e os cenários ainda pendentes. A recuperação de backup foi verificada em uma segunda cópia do cluster com conferência de anos, RAW, fatos, dimensões e FKs. O arquivo compactado foi conferido novamente pelo hash antes de remover a cópia restaurada, que serviu somente ao teste. O arquivo e o hash estão registrados na [evidência de backup](../resultados/validacoes/integracao_final/backup_isolado.json).

## Reprodução e apresentação

A partir da raiz Git, use Python 3.11 ou superior, as dependências de `requirements.txt` e os binários PostgreSQL 18. O [guia de integração](../documentacao/INTEGRACAO_FINAL.md) contém instalação, ordem das doze etapas manuais do ELT, carga ETL, validações, recuperação e roteiro de apresentação. O [modelo dimensional](../documentacao/MODELO_DIMENSIONAL_FINAL.md) detalha as relações.

```bash
.venv/bin/python scripts/integracao_final.py prepare \
  --dados-2019 '/caminho/Base de dados 2019' \
  --dados-2020 '/caminho/Base de dados 2020' \
  --dados-2021 '/caminho/Base de dados 2021'
.venv/bin/python scripts/integracao_final.py isolated
.venv/bin/python scripts/evidencias_final.py
.venv/bin/python scripts/auditar_contrato_final.py
.venv/bin/python -m unittest discover -s tests -v
```

Com os dois DWs já carregados em um cluster single-user, `.venv/bin/python scripts/integracao_final.py compare` refaz a comparação. `--ano` permite retomar um ano. O checkpoint e os logs da execução original foram mantidos no ambiente histórico.

O modo single-user foi usado na validação original. A sequência SQL manual foi testada. Em uma conferência posterior, o responsável consultou o cluster preservado no DataGrip e confirmou a presença dos dois DWs e as contagens por ano. Para reproduzir a conexão, consulte o [guia multiplataforma](../documentacao/REPRODUCAO_MULTIPLATAFORMA.md#5-conectar-um-cliente-postgresql).

## Arquivos, Git e publicação

A retomada atualizou `scripts/integracao_final.py`, `scripts/evidencias_final.py`, `scripts/testar_integracao_isolada.py`, `sql/comparacao/validar_final.sql`, `scripts/backup_cluster_isolado.py`, os testes e os guias. Acrescentou `scripts/auditar_contrato_final.py`, `sql/comparacao/validar_restauracao.sql`, `scripts/espaco_disco.py`, `tests/test_espaco_disco.py`, os relatórios e evidências compactas.

A execução histórica foi registrada no commit `86ffb99`. A validação em lotes está no commit `1bebb0e` e as verificações de espaço estão no commit `a25a7ff`. O repositório público consolida o trabalho do grupo na `main`, incluindo as validações e os testes do PR #11.

Dados brutos e tratados completos, credenciais, logs temporários, clusters, ZIPs locais e backups ficam fora do Git.

## Armazenamento na execução histórica

O volume da entrega tinha **9,38 GiB livres** no início da verificação de disco e **20,80 GiB livres** ao consolidar os resultados. Foram removidos **11,42 GiB** de dados regeneráveis. O repositório ocupava 44,26 GiB na primeira medição, ou 44,91 GiB incluindo as bases irmãs do projeto. Havia 6.826.501 inodes livres.

| Diretório removido | Espaço alocado | Verificação |
|---|---:|---|
| `.local/final/restauracao_20261117_195714_156109` | 10,40 GiB | Cópia do teste de restauração com RESTAURACAO_OK. O ambiente carregado e o arquivo físico validado foram preservados. |
| `.local/final/postgres_tentativa_sem_resolucao` | 1,02 GiB | Cluster desligado da tentativa com rollback. O log da falha foi preservado e a instalação seguinte foi validada. |

Ao concluir a execução histórica, os maiores consumidores preservados eram o cluster funcional `.local/final/postgres` (10,40 GiB), os ambientes `.local/integracao` (12,28 GiB) e `.local/guia_validacao` (5,90 GiB), os backups (2,47 GiB, incluindo o backup final restaurável de 1,64 GiB), o RAW preparado (0,74 GiB) e os arquivos Pandas (0,71 GiB). O cluster funcional terminou com checkpoint limpo.

As operações pesadas no terminal agora verificam a reserva de 8 GiB além do pico estimado. A exportação de evidências usa um único CSV RAW temporário por vez. Depois da revisão, avalie separadamente os ambientes históricos e intermediários. Confirme que estão desligados ou sem uso, registre quais evidências precisam continuar acessíveis e preserve uma cópia recuperável antes de remover um diretório comprovadamente redundante. Consulte as medições em bytes e as justificativas no [registro de armazenamento](../resultados/validacoes/integracao_final/armazenamento.json).
