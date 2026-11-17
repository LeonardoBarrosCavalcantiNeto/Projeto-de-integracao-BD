# Relatório de integração ANAC — 2019 e 2020

Execução: 17/11/2026. Branch local: `integracao-2019-2020-canonica`, criada a partir de `integracao-elt` (`b6c6b46`). Implementação e testes usam os 24 CSVs reais encontrados nas duas pastas de bases do diretório do projeto. Nenhum dado de 2021 foi processado.

## Alcance e bloqueio do ambiente

O DW integrado foi construído em um **cluster PostgreSQL 18.6 isolado**, em `.local/integracao/postgres_teste`, banco `postgres`. Não é o servidor original utilizado pelo DataGrip.

A sessão negou acesso ao socket Docker (`permission denied`) e aos sockets PostgreSQL (`Operation not permitted`). Também impediu a criação de sockets Unix mesmo em `/tmp`. A conexão TCP local não foi estabelecida. Portanto, **não foi possível identificar, inspecionar, fazer pg_dump, restaurar ou migrar o `anac_dw` original**. Nenhum dado desse servidor foi alterado. Seus resultados históricos foram usados somente como referências de comparação, não apresentados como medições novas do banco original.

Para não limitar a entrega a scripts, o PostgreSQL instalado localmente foi executado em modo single-user, sem sockets, em um cluster novo. Foram realizadas transformação SQL e carga efetiva do DW com os dados reais. Os scripts de migração convencional incluem backup customizado completo e restauração obrigatória antes de alterar schemas; essa orquestração de conexão ao servidor original permanece não executada por causa do bloqueio.

## Resultados reais da carga SQL

| Ano de origem | RAW | Excedentes exatos | Rejeitados após deduplicação | Tratada / fato |
|---|---:|---:|---:|---:|
| 2019 | 983.414 | 470 | 18 | 982.926 |
| 2020 | 483.545 | 124 | 1.512 | 481.909 |
| Total | 1.466.959 | 594 | 1.530 | **1.464.835** |

A contagem da fato foi obtida por SELECT no PostgreSQL após a carga, não inferida apenas pela soma das entradas. A conciliação RAW = duplicatas excedentes + rejeitados representantes + válidos foi executada. Cada origem deve aparecer exatamente em uma dessas três classes.

| Indicador entre os válidos | 2019 | 2020 |
|---|---:|---:|
| Partida real ausente | 17.982 | 21.845 |
| Chegada real ausente | 17.982 | 21.845 |
| Diferença de partida com ABS > 1.440 min | 684 | 286 |
| Diferença de chegada com ABS > 1.440 min | 690 | 331 |

Ausências reais mantêm diferenças e atrasos NULL. Antecipações mantêm diferença negativa e atraso zero. Atípicos são preservados integralmente. As referências anteriores do contrato de 687/693 atípicos de 2019 não foram impostas: a execução nova mediu 684/690, coincidentes com o pacote histórico integrado.

## Implementação entregue

- Ingestão canônica com biblioteca padrão Python, validação dos 12 meses de cada ano, cabeçalho, UTF-8 BOM opcional, separador e largura. Origem usa número do registro lógico, inclusive com quebras internas.
- Manifesto com SHA-256, tamanhos e contagens de cada arquivo; CSVs canônicos preservam os 20 valores brutos, sem limpeza anterior à carga ELT.
- Reutilização do tratamento SQL do integrante de 2020 para os dois anos. Deduplicação bruta exata ocorre antes de trim/upper e de rejeições.
- Auditorias compartilhadas com ano, ID, origem, valores brutos, representante da duplicata e todos os motivos da rejeição. PK composta e restrições de unicidade impedem colisões entre anos.
- Conversões seguras de calendário, horário e inteiro; anomalias de campos opcionais são auditadas sem excluir o voo.
- DW com sete dimensões, chave global `(ano_origem,id_raw)` e origem obrigatória. Dimensões compartilhadas resolvem companhia e aeroportos por códigos naturais; a fato referencia a tratada e as dimensões.
- Resoluções preexistentes de SBEG e SWHP reaproveitadas apenas no cadastro dimensional, preservando a descrição bruta e a tratada.
- Carga reexecutável com ON CONFLICT e validações SQL que abortam em divergências. Scripts analíticos com denominador de atrasos explícito.
- Procedimento convencional de backup, restauração e migração transacional, preservando schemas antigos e conciliando multiplicidades históricas antes do commit.

## Comparação com o trabalho dos integrantes

Foram examinados os notebooks ETL/ELT de 2019/2020, scripts Python, SQL original de transformação, SQL histórico de 2019, relatórios, contrato e branches locais/remotas disponíveis. O histórico remoto não foi atualizado nesta sessão; não se afirma que as referências locais contenham alterações publicadas posteriormente.

O ELT original de 2020 já dispõe de deduplicação bruta, conversão segura e atraso nulo correto. O notebook desse integrante usa `reader.line_num`, posição física, para a origem; a integração usa registro lógico conforme o contrato. Nos CSVs sem novas linhas internas, as duas contagens coincidem.

O SQL histórico integrado de 2019 deduplica atributos já normalizados e preserva a ocorrência por ID local, enquanto o contrato exige campos brutos e ordem de arquivo/registro. A nova ingestão não tenta recuperar uma ordem histórica que não foi capturada. O notebook ELT 2019 contém rejeição com motivo prioritário único e conversões com TO_TIMESTAMP/TO_DATE; a integração registra todos os motivos e usa validação estrita de calendário. Os scripts históricos e os notebooks foram preservados.

O ETL 2020 original foi executado com os CSVs reais. Gerou 483.545 brutos, 124 excedentes, 1.512 rejeitados e 481.909 tratados; interseção excedentes/invalidade zero; nenhuma possível duplicata adicional somente após padronização; 15 partidas previstas fora do ano de origem, preservadas.

Para 2019 foram executadas as funções originais de extração, deduplicação e transformação, com 983.414 brutos, 444 grupos exatos, 914 linhas envolvidas, 470 excedentes, 18 rejeitados e 982.926 tratados. O notebook Colab e a publicação do DW ETL 2019 não foram executados. O construtor dimensional original bloqueia descrições conflitantes; a integração aplica as resoluções compartilhadas sem alterar a saída tratada usada na comparação.

As comparações por conteúdo usam 20 campos canônicos, quatro medidas, duas flags e as origens únicas, sem comparar chaves substitutas. As origens de excedentes e rejeitados também são conciliadas. Resultados detalhados são registrados nas evidências ao final da execução.

O SQL registrou 25 anomalias opcionais em 2019: números de assentos negativos (valores de −83 a −93), mantidos no RAW e convertidos para NULL na tratada. Não geraram rejeição do voo. A lista com arquivo e registro está em `resultados/validacoes/integracao_2019_2020/anomalias.csv`. Em 2020 não houve anomalias opcionais.

Os motivos de rejeição dos ETLs e do ELT usam formatos textuais distintos. A comparação comprova equivalência das origens rejeitadas e de todos os valores tratados; não afirma identidade literal das mensagens ou das estruturas das auditorias. O diagnóstico de possíveis duplicatas após padronização de 2019 não foi executado separadamente nesta sessão; nenhuma exclusão adicional por padronização foi aplicada.

## Rastreabilidade

A reconstrução canônica cria origem verificável para todos os registros dos dois anos e a propaga à STAGING e à fato. Os IDs novos são determinísticos dentro de cada ano. Não há associação individual entre duplicatas antigas idênticas e linhas de arquivo: essa informação histórica não existe e não foi inventada.

A igualdade com o RAW histórico do `anac_dw` original ainda depende de conexão. O executor implementa comparação multiconjunto dos 20 campos antes do commit; nessa comparação exclusivamente histórica, trata NULL antigo como vazio, porque a importação manual pode ter perdido essa distinção. Divergências interrompem a migração.

## Reprodução e apresentação

O [README](../README.md) contém os comandos principais. A [documentação técnica](../documentacao/integracao_2019_2020.md) detalha contratos, ferramentas, segurança, recuperação e comparação. Os arquivos grandes ficam ignorados pelo Git.

As [consultas analíticas](../sql/integracao/05_analises.sql) demonstram contagem por ano, companhia, atraso médio, percentual de atrasados entre horários calculáveis, aeroportos, meses e auditorias. O critério de apresentação é atraso positivo, sem converter horários desconhecidos em pontualidade.

## Pendências externas e extensão para 2021

A migração do banco do DataGrip exige disponibilizar uma conexão autorizada ao PostgreSQL correto, ferramentas compatíveis e espaço para backup/restauração. Depois disso, o comando `apply` executa a migração protegida; não é necessário repetir comandos manuais de tratamento no DataGrip. O procedimento de pg_dump/pg_restore deve ser confirmado nesse ambiente, pois não foi executado contra o servidor bloqueado.

A interpretação dos fusos e da referência e a aprovação acadêmica do limiar de pontualidade continuam questões documentais. Os indicadores mantêm a semântica disponível sem converter fusos.

A estrutura de chaves, dimensões e transformação compartilhada suporta um novo ano. A CLI limita deliberadamente esta entrega a 2019/2020. Para 2021, conferir arquivos, layout, conflitos e resultados antes de ampliar os anos aceitos. Nenhuma carga de 2021 foi realizada.

## Evidências finais executadas

A [pasta de evidências](../resultados/validacoes/integracao_2019_2020/) contém saídas reais do PostgreSQL e metadados de execução:

| Verificação | Resultado medido |
|---|---|
| Carga da fato por ano | 982.926 / 481.909 |
| Reexecução da carga dimensional/fato | total permanece 1.464.835 |
| ETL × ELT: conteúdo tratado | 0 divergências nos dois anos |
| ETL × ELT: origens de duplicatas | 0 divergências nos dois anos |
| ETL × ELT: origens de rejeições | 0 divergências nos dois anos |
| RAW reexportado × ingestão canônica | SHA-256 idêntico em ambos os anos |
| Origem ausente ou classificação sobreposta | asserções SQL aprovadas |
| Obrigatórios e conteúdo da fato × STAGING | asserções SQL aprovadas |
| FKs dimensionais e FK da fato para a tratada | criadas, validadas e carga aprovada |
| Nulos reais convertidos indevidamente em atraso | 0 nos dois anos |
| Duplicatas excedentes também inválidas | 0 nos dois anos |
| Testes de ingestão e integração sintética SQL | 4 testes aprovados |

Os hashes de reexportação do RAW foram:

- 2019: `22777918e6f1ad639d908c63cc9430847ccd7b8186635268655c732a8f54ce32`.
- 2020: `a5b2b7e5b7a666e1b534637e208f557e7bbd9c0518380ac441520beb95c35631`.

São hashes dos CSVs canônicos que incluem IDs e origem; os hashes de cada CSV mensal original estão no manifesto. A comparação byte a byte por hash da reexportação cobre todas as colunas e ocorrências carregadas. A equivalência com a interpretação dos CSVs originais é assegurada pelo leitor CSV estrito que gerou esses arquivos, com hashes antes/depois para detectar mudanças durante a leitura.

Dimensões integradas medidas: 117 companhias, 483 aeroportos, 733 datas, 3 situações, 47 justificativas, 9 tipos de linha e 67 equipamentos. Não são a soma de dimensões experimentais anuais: são membros compartilhados por chave natural.

O teste sintético executa os mesmos SQLs no PostgreSQL, com duplicata inválida entre meses, diferença apenas de espaços que não deve ser deduplicada, calendário inválido, assentos acima do limite, antecipação, horário ausente e diferença superior a 24 horas. A validação de meses vazios foi corrigida a partir desse teste. As restrições finais de obrigatoriedade e medidas foram aplicadas também ao banco real isolado. O bundle final de reprodução inclui essas restrições na transação inicial; a versão inicial efetivamente executada está arquivada localmente em `.local/integracao/bundle/carga_inicial_executada.sql`.

## Interpretação de consultas executadas

Entre os voos com horário de partida calculável, houve 30,08% com atraso positivo em 2019 e 27,68% em 2020. As médias de atraso não negativo foram 9,80 e 9,76 minutos. O denominador foi 964.944 em 2019 e 460.064 em 2020; os 17.982 e 21.845 horários desconhecidos não foram tratados como pontuais. Atípicos permanecem nessas médias e podem influenciá-las; são indicadores descritivos da fonte sem ajuste de fuso.

Guarulhos (SBGR) liderou a movimentação integrada com 427.351 movimentos, seguido por Congonhas (SBSP), com 239.525. Nessa consulta, movimento significa aparição em um dos papéis origem/destino; não é o número de passageiros. As consultas mensais usam a data operacional da dimensão tempo e conservam o ano de origem do CSV como outro atributo.

Foram preservadas 12 partidas previstas de 2019 e 15 de 2020 fora de seus respectivos anos de origem. Não houve exclusão por esse motivo.

## Arquivos e controle de versão

Arquivos de implementação: `scripts/integrar_anac.py`, `scripts/testar_integracao_isolada.py`, `scripts/auditar_integracao_isolada.py`, `scripts/comparar_integracao.py`, `scripts/backup_cluster_isolado.py`.

SQLs novos: `sql/integracao/02_dimensoes.sql`, `03_carga_dw.sql`, `04_validar.sql`, `05_analises.sql`, `06_casos_limite.sql`, `07_diagnosticos.sql`, `08_restricoes.sql`.

Testes novos: `tests/test_ingestao.py` e `tests/test_pipeline_postgresql.py`. Documentação nova: este relatório e `documentacao/integracao_2019_2020.md`. Atualizados: `README.md`, `sql/elt/README.md`, `.gitignore` e `.env.example`. As evidências pequenas estão versionadas na pasta de validações; bancos, backups e saídas grandes dos ETLs permanecem locais e ignorados. Os ZIPs preexistentes não foram incorporados ao commit.

Os logs completos permanecem em `.local/integracao/bundle/`: carga inicial, reexecução, validações, análises, aplicação das restrições, comparações e exportações. A migração convencional do servidor original não está declarada aprovada: falta executar seu backup/restauração, inspecionar seu catálogo e confirmar a conciliação histórica quando a conexão estiver disponível.

## Backup recuperável efetivamente produzido

Foi criado e testado um backup físico **do cluster isolado integrado**, não do banco original:

- Arquivo, relativo à raiz do repositório: `backups/isolado_2019_2020_20261117_155534_874204.tar.gz`.
- Tamanho: 891.923.437 bytes, aproximadamente 851 MiB.
- SHA-256: `7a54d1d486cf6432c87cf034f375049ac99cd0249d8aa591d51ebbd44cdb92b7`.
- PostgreSQL: versão principal 18; banco `postgres`.
- Cópia restaurada e validada: `.local/integracao/restauracao_20261117_155534_874204/postgres_teste`.
- Log de restauração: `backups/isolado_2019_2020_20261117_155534_874204_restauracao.log`.
- Resultado SQL na restauração: 982.926 fatos de 2019, 481.909 de 2020, total 1.464.835; todas as asserções de validação aprovadas.

O arquivo foi extraído em diretório novo; o PostgreSQL abriu a cópia restaurada e executou as consultas, incluindo integridade, proveniência, medidas e conteúdo dimensional. O registro legível por máquina está em [backup_isolado.json](../resultados/validacoes/integracao_2019_2020/backup_isolado.json). O arquivo grande não foi adicionado ao Git.

Restauração manual em outro diretório, na raiz do repositório:

```bash
mkdir -p .local/recuperacao_manual
tar -xzf backups/isolado_2019_2020_20261117_155534_874204.tar.gz \
  -C .local/recuperacao_manual
```

A documentação técnica explica como iniciar essa cópia em porta própria fora do ambiente que bloqueia sockets. Nenhuma operação destrutiva foi realizada no PostgreSQL original. Seu backup customizado e sua migração continuam pendentes de acesso real, com o executor pronto para exigir a restauração antes da alteração.
