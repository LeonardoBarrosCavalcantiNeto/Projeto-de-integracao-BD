# Arquitetura integrada de 2019 e 2020

## Contrato e fluxo

Referência: contrato v1.1, de 11/11/2026. A extração Python somente interpreta CSV e acrescenta metadados; a transformação principal ocorre no PostgreSQL: CSV → RAW → STAGING → DW. Isso caracteriza ELT. Nos ETLs dos integrantes, Pandas transforma antes da carga. As duas saídas representam as mesmas observações e não devem ser somadas.

`prepare` exige os 12 nomes mensais de cada ano, cabeçalho exato, UTF-8 com BOM opcional, delimitador `;` e 20 campos por registro. O leitor CSV trata campos com novas linhas internas. A origem é o registro lógico: cabeçalho 1, primeiro registro 2. Campos vazios continuam strings vazias no RAW; nenhum texto como `NULL`, `NA` ou `\N` é convertido automaticamente em nulo. As cópias intermediárias usam aspas em todos os campos.

O manifesto guarda contagem, tamanho, SHA-256 e quantidade de registros multilinha por arquivo. O hash é conferido antes e depois da leitura. Também registra hashes do bundle SQL e dos CSVs canônicos; `apply` verifica esses hashes antes de conectar para migrar.

## Identidade e proveniência

Cada `raw.voos_ANO` tem `id_raw` local determinístico pela ordem de nome de arquivo e registro lógico, além de `ano_origem`, `arquivo_origem` e `linha_origem` obrigatórios. Os 20 campos originais mantêm os nomes oficiais entre aspas e tipo TEXT NOT NULL. Essa diferença em relação ao RAW histórico está documentada: as etapas antigas com nomes ASCII não devem ser executadas sobre o RAW novo.

`raw.ocorrencias` centraliza as chaves `(ano_origem,id_raw)` e a chave alternativa `(ano_origem,arquivo_origem,linha_origem)`. STAGING compartilhada e fato usam a mesma identidade composta. Um ID de 2019 pode coexistir com o mesmo ID de 2020 sem colisão.

Não existe associação inventada entre IDs históricos e linhas do CSV. Em duplicatas idênticas, a ocorrência histórica individual não é distinguível sem proveniência. A ingestão canônica reconstrói a origem confiável; schemas antigos e backup permitem comparar os conjuntos anteriores. `apply` mede igualdade multiconjunto dos 20 campos, desconsiderando IDs. Somente para essa conciliação, NULL histórico é comparado a string vazia, pois a importação manual pode ter convertido vazios em NULL. O RAW novo preserva a distinção entre vazio e texto literal.

## STAGING e qualidade

A transformação foi extraída do SQL original do ELT 2020, preservado em `sql/transformacoes/elt_2020.sql`. O executor parametriza ano, nomes das tabelas e metadados para ambos os anos; não mantém duas regras independentes. As funções de conversão são compartilhadas em `staging`.

1. Compara exatamente os 20 campos brutos, com collation C, dentro de cada ano e entre seus 12 meses. Ordena por arquivo e registro lógico; preserva a primeira ocorrência.
2. Excedentes ficam em `staging.vra_duplicatas_excluidas`, incluindo os valores brutos, a origem e a referência à representante.
3. Somente representantes passam pela elegibilidade analítica. Removem-se espaços externos, vazios viram NULL e os códigos/categorias são convertidos para maiúsculas. Número do voo permanece texto.
4. Rejeita ausência de companhia, origem, destino, partida prevista ou chegada prevista. Datas previstas preenchidas inválidas também rejeitam. Todos os motivos ficam em um array por registro em `staging.vra_rejeicoes`, junto dos dados brutos.
5. Datas reais, referência e assentos inválidos tornam-se NULL com auditoria em `staging.vra_anomalias`. Assentos devem ser inteiros não negativos de 32 bits. Datas são validadas por calendário e horário, sem ajuste silencioso.
6. Referência fora do ano é diagnosticada; partida prevista fora do ano não provoca exclusão. Ano de origem é o ano do CSV.
7. Válidos ficam em `staging.vra_tratada`. A partição RAW = excedentes + rejeitados representantes + válidos é verificada por registro e por ano.

As intermediárias recebem sufixo anual; as tabelas consolidadas são compartilhadas. Auditorias e tratada têm PK composta, unicidade de origem e FK para `raw.ocorrencias`. A RAW permanece integral. O diagnóstico adicional mede grupos, linhas envolvidas e interseção de excedentes inválidos. Possíveis duplicidades somente após padronização são diagnósticos dos ETLs, sem exclusão adicional automática.

## Indicadores temporais

Timestamps preservam data e hora, sem conversão de fuso. Diferença assinada = realizado − previsto em minutos. Antecipações têm diferença negativa e atraso zero. Ausência de realizado mantém diferença e atraso NULL. O SQL usa CASE antes de GREATEST para impedir a conversão de NULL em zero.

Atípico significa valor absoluto da diferença maior que 1.440 minutos. A métrica não é truncada nem excluída. A flag é FALSE quando não se calcula a diferença. Nas consultas de apresentação, atrasado significa atraso positivo; o denominador do percentual considera somente registros com horário calculável. Desconhecidos são exibidos separadamente. Essa escolha de apresentação está explícita; o contrato não fixa um limiar único aprovado pelo grupo.

A semântica temporal da fonte e de `referencia` permanece uma limitação documental. Não interpretar as diferenças como durações físicas corrigidas por fusos nem inferir cancelamento de um horário real ausente.

## Modelo dimensional

Granularidade: uma etapa de voo representante válida por ano de origem. Sete dimensões: tempo, companhia, aeroporto, situação, justificativa, tipo de linha e equipamento. Tempo e aeroporto têm dois papéis na fato: partida/chegada e origem/destino.

Companhia e aeroporto têm códigos ICAO como chave natural única; categorias têm valores naturais únicos. As SKs são identidades, exceto tempo, que usa AAAAMMDD. Justificativa e equipamento usam chave 0 para DESCONHECIDO quando ausentes. Situação e tipo de linha podem ter FK nula. A fato guarda proveniência obrigatória, medidas e atributos operacionais; tem nove relações dimensionais e FK para a tratada por ano e ID.

Conflitos de descrição bloqueiam a carga. As duas resoluções existentes de SBEG e SWHP são reaproveitadas de `documentacao/resolucoes_aeroportos_2020.csv`, com fonte e justificativa. São aplicadas apenas no cadastro dimensional; `staging.aeroportos_resolvidos` conserva descrição original, resolvida, papel e proveniência. Não se escolhe arbitrariamente o nome mais frequente.

A carga `03_carga_dw.sql` é reutilizável com ON CONFLICT nas chaves naturais e `(ano_origem,id_raw)`. A reexecução mantém as SKs existentes e não acrescenta fatos. A reconstrução completa via `apply` cria novas dimensões, cujas SKs não devem ser comparadas às de outros bancos: comparar por códigos naturais.

## Execução e recuperação

Veja os comandos principais no README. `prepare` não altera PostgreSQL. `apply` exige destino `anac_dw` ou `anac_teste_*` e ferramentas PostgreSQL acessíveis. Não descobre containers automaticamente nem troca de servidor. As variáveis PG* precisam apontar para a instância correta.

Antes de migrar, produz `backups/BANCO_TIMESTAMP.dump` em formato customizado, verifica o catálogo e restaura tudo em `anac_teste_restore_TIMESTAMP` com `--exit-on-error`. O diretório recebe permissão 0700 e o dump 0600. O JSON associado identifica o dump, seu hash, o banco restaurado e os schemas preservados. Sem restauração bem-sucedida, nenhuma renomeação de schema ocorre.

A transação usa advisory lock, renomeia schemas antigos, cria os novos, carrega dados, verifica conciliação histórica e executa asserções antes do commit. Erro SQL causa rollback. Nenhum schema antigo é apagado. Um administrador deve controlar outras escritas no banco durante essa operação; o lock coordena este executor, não clientes externos do DataGrip.

Para recuperação completa, restaure primeiro em outro banco e inspecione:

```bash
createdb -w anac_teste_recuperacao
pg_restore -w --exit-on-error -d anac_teste_recuperacao backups/ARQUIVO.dump
```

Não usar `--clean` no banco principal para testar. Depois de validar o banco restaurado, pode-se apontar o DataGrip para ele. Os schemas `_antes_*` também ficam disponíveis para inspeção. O backup físico do cluster isolado, quando informado no relatório, exige a mesma versão principal de PostgreSQL e não substitui o backup do banco original.

## Teste limpo e comparação

Sem serviço PostgreSQL, `testar_integracao_isolada.py` cria um cluster novo e usa `postgres --single`. Precisa de `initdb` e `postgres` locais. Nunca usa o servidor do DataGrip. Detecta erros no log além do código de saída. Aborta se o diretório de cluster já existe.

```bash
python3 scripts/testar_integracao_isolada.py
python3 scripts/auditar_integracao_isolada.py
python3 -m unittest discover -s tests
```

O teste executa a carga e repete `03_carga_dw.sql` com asserções. A auditoria reexporta o RAW em ordem canônica e compara SHA-256 ao bundle original: isso cobre os 20 valores e multiplicidades, não só contagens. Também exporta consultas reais para arquivos pequenos em `resultados/validacoes/integracao_2019_2020/`.

Para os ETLs, instale `requirements.txt` em um venv e execute separadamente para controlar memória:

```bash
python scripts/comparar_integracao.py --ano 2019 \
  --dados '/caminho/2019' --etl-output .local/integracao/etl_2019
python scripts/comparar_integracao.py --ano 2020 \
  --dados '/caminho/2020' --etl-output .local/integracao/etl_2020
```

Isso executa os tratamentos existentes e gera `comparar_ANO.sql` no bundle. Na execução convencional, execute os SQLs no mesmo banco integrado com `psql -X -v ON_ERROR_STOP=1 -f ...`. Eles criam tabelas de comparação em STAGING: usar uma base de teste ou o banco já protegido por backup. Comparam todos os atributos canônicos, quatro medidas, duas flags e proveniência por junção completa nas chaves de origem únicas e comparação nula segura; comparam também origens de rejeições e excedentes por EXCEPT ALL bidirecional. Não alteram os fatos. As tabelas de comparação não devem existir na primeira execução desses SQLs.

O comparador 2019 invoca as funções originais de extração, deduplicação e tratamento; não afirma ter executado o notebook Colab nem publicado o DW ETL 2019. O construtor de dimensão original bloqueia conflitos de descrição, que são resolvidos pela integração compartilhada.

## Extensão futura

As chaves e dimensões comportam 2021. O tratamento base está centralizado; basta ampliar a seleção explícita dos anos após conferir layout, dados, resoluções e contrato. A CLI desta entrega aceita somente 2019 e 2020, de forma deliberada. Nenhum CSV ou pipeline de 2021 foi executado. Não remover esse limite antes da validação específica do novo conjunto.

## Backup e demonstração do cluster isolado

`scripts/backup_cluster_isolado.py` cria um backup físico comprimido do cluster de teste desligado, extrai em outro diretório e executa as validações sobre a cópia restaurada. Recusa execução quando existe `postmaster.pid`. O JSON em `resultados/validacoes/integracao_2019_2020/backup_isolado.json` informa caminho, hash, tamanho, versão e teste de restauração. Esse arquivo não contém o banco original do DataGrip.

Para repetir somente a restauração física, com PostgreSQL 18, escolha um diretório novo e extraia o arquivo indicado no JSON:

```bash
mkdir -p .local/recuperacao_manual
# Substitua ARQUIVO pelo caminho exato registrado no JSON.
tar -xzf backups/ARQUIVO.tar.gz -C .local/recuperacao_manual
```

Depois, num terminal que permita sockets, o cluster restaurado pode ser iniciado em porta própria:

```bash
pg_ctl -D .local/recuperacao_manual/postgres_teste \
  -l .local/recuperacao_manual/servidor.log \
  -o '-p 55439 -h 127.0.0.1 -k /tmp' start
psql -h 127.0.0.1 -p 55439 -U "$USER" -d postgres \
  -v ON_ERROR_STOP=1 -f sql/integracao/04_validar.sql
```

O cluster foi criado pelo usuário local `efsr`; uma cópia física mantém esse papel. Se o usuário do terminal for diferente, informe `-U efsr`. O banco desse cluster é `postgres`, contendo os schemas integrados. Esses comandos de servidor são instruções de demonstração; o ambiente restrito desta sessão não permitiu iniciá-lo por sockets. Não apontam para o `anac_dw` original nem substituem seu backup.

Para exportar também os resultados comparativos depois dos SQLs de comparação, use `python3 scripts/auditar_integracao_isolada.py --comparar-etl`. Sem essa opção, a auditoria funciona sem as tabelas de comparação ETL.
