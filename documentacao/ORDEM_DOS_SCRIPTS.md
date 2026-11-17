# Ordem rápida dos scripts — integração ANAC 2019/2020

Referência: implementação baseada em `a65f7e4`, com gerador manual desta entrega, branch `integracao-2019-2020-canonica`. Guia completo: [GUIA_EXECUCAO_COMPLETA.md](GUIA_EXECUCAO_COMPLETA.md).

**Raiz dos comandos:** `Projeto-de-integracao-BD/`. Configure PostgreSQL/PG* e obtenha os CSVs conforme o guia. Escolha **A ou B** para um banco novo. Não misture com os SQLs históricos de `sql/elt/2019/` e `sql/validacoes/`. Não há pipeline canônico separado em `sql/elt/2020/`.

## A. Automatizado — recomendado

| Nº | Nome exato/comando | Local | Objetivo | Dependências | Resultado esperado |
|---|---|---|---|---|---|
| A0 | `python scripts/integrar_anac.py prepare --dados-2019 dados/brutos/2019 --dados-2020 dados/brutos/2020` | Terminal, raiz | Validar fontes, gerar RAW canônico, manifesto e ambos os roteiros | Python 3.11+, 24 CSVs originais | `.local/integracao/bundle/` com 2 CSVs, `manifesto.json`, `carga.sql`, `manual/` |
| A1 | `python scripts/integrar_anac.py apply --bundle .local/integracao/bundle --backup-dir backups` | Terminal, raiz | Backup/restauração, RAW → STAGING → DW, conciliação histórica quando houver, validação e reexecução | A0, banco criado, PG*, senha, CREATEDB, clientes PostgreSQL | 1464835 fatos no conjunto de referência; JSON de backup e relatórios |
| A2 | `sql/integracao/04_validar.sql` | DataGrip ou `psql -X -w -v ON_ERROR_STOP=1 -f ...` | Conferir asserções e contagens | A1 | Nenhuma exceção, fato 982926/481909 |
| A3 | `sql/integracao/05_analises.sql` | DataGrip ou psql | Apresentar indicadores | A1 | Grupos anuais, companhias, atrasos, aeroportos, meses e auditorias |

A1 já executa as validações/análises; A2/A3 servem para conferência e demonstração. `carga.sql` e `aplicar.sql` contêm `\copy`: não são arquivos SQL JDBC para abrir diretamente no DataGrip.

## B. Por etapas — DataGrip com preparação/importação no terminal

**B0:** execute o mesmo `prepare` de A0. Os caminhos abaixo **não existem no clone**: são gerados localmente em `.local/integracao/bundle/manual/`. Antes de B1, crie um banco vazio e conecte o DataGrip a ele. Se A já foi executado, use outro banco, por exemplo `anac_teste_apresentacao`.

| Nº | Nome exato do arquivo | Local de execução | Objetivo | Dependências | Resultado esperado |
|---|---|---|---|---|---|
| B1 | `.local/integracao/bundle/manual/01_raw.sql` | DataGrip, arquivo inteiro | Criar schemas, inventário e duas RAW | B0, banco vazio | 24 arquivos no inventário; 0 linhas nas RAW |
| B2 | `.local/integracao/bundle/manual/02_importar_raw.psql` | **Terminal psql**, comando abaixo | Importar os canônicos, com origem | B1 confirmado; PGDATABASE igual ao DataGrip; caminhos locais acessíveis | RAW 983414/483545; repetição bloqueada |
| B3 | `.local/integracao/bundle/manual/03_transformar_2019.sql` | DataGrip | Classificar duplicatas, converter, rejeitar, tratar e medir 2019 | B2 | 470 excedentes, 18 rejeitados, 982926 tratados |
| B4 | `.local/integracao/bundle/manual/04_transformar_2020.sql` | DataGrip | Mesmo tratamento para 2020 | B2/B3 | 124 excedentes, 1512 rejeitados, 481909 tratados |
| B5 | `.local/integracao/bundle/manual/05_consolidar_staging.sql` | DataGrip | Unir anos, auditorias, resumo e chaves globais de origem | B3/B4 | RAW = duplicatas + rejeitados + válidos; PK/FK compartilhadas |
| B6 | `.local/integracao/bundle/manual/06_criar_dw.sql` | DataGrip | Criar sete dimensões e fato, corrigindo chave por ano | B5 | Tabelas DW vazias, UNIQUE composta e FKs |
| B7 | `.local/integracao/bundle/manual/07_dimensoes.sql` | DataGrip | Preparar resoluções/cadastros e bloquear conflitos | B5/B6 | Views de cadastros; zero conflitos |
| B8 | `.local/integracao/bundle/manual/08_carga_dw.sql` | DataGrip | Alimentar dimensões e fato | B7 | 1464835 fatos; carga reexecutável |
| B9 | `.local/integracao/bundle/manual/09_validar_contrato.sql` | DataGrip | Validar, testar funções e adicionar restrições | B8 | Asserções aprovadas e NOT NULL/CHECK aplicados |
| B10 | `.local/integracao/bundle/manual/10_analises.sql` | DataGrip | Consultas analíticas | B9 | Resultados para apresentação |
| B11 | `.local/integracao/bundle/manual/11_diagnosticos.sql` | DataGrip | Grupos duplicados, interseção e motivos | B5 | Grupos 444/124 e interseção inválidos/excedentes 0/0 |

B2, no terminal da raiz, com PG* e autenticação já configurados:

```bash
psql -X -w -v ON_ERROR_STOP=1 \
  -f .local/integracao/bundle/manual/02_importar_raw.psql
```

Cada arquivo SQL B1/B3–B9 contém sua própria transação; no DataGrip execute o arquivo inteiro com parada em erro. Em falha, interrompa e execute ROLLBACK na mesma sessão. B10/B11 são somente leitura. B8 pode ser repetido; B1/B2/B5/B6/B7/B9 não devem ser repetidos integralmente. Não repetir B3/B4 após consolidar. Para nova validação use `sql/integracao/04_validar.sql`, sem recriar os CHECKs de B9.

## Fonte de cada bloco gerado

| Arquivos gerados | Código/SQL real de origem |
|---|---|
| B1/B2 | `scripts/integrar_anac.py`: DDL e ingestão com metadados |
| B3/B4 | `sql/transformacoes/elt_2020.sql`, adaptado pelo executor em schema/tabelas/ano e inclusão de `id_raw` |
| B5 | `scripts/integrar_anac.py`: união e restrições compartilhadas |
| B6 | `sql/database/10_criacao_dw.sql`, adaptado para a identidade composta e origem obrigatória |
| B7 | `sql/integracao/02_dimensoes.sql` |
| B8 | `sql/integracao/03_carga_dw.sql` |
| B9 | `sql/integracao/04_validar.sql` + `06_casos_limite.sql` + `08_restricoes.sql` |
| B10/B11 | `sql/integracao/05_analises.sql` / `07_diagnosticos.sql` |

Não execute o DDL histórico nem o template de transformação sem adaptação. Os gerados são os artefatos concretos a abrir no DataGrip.

## Verificação rápida e reexecução

No DataGrip:

```sql
SELECT ano_origem,bruta,duplicatas_excedentes,rejeicoes,tratada
FROM staging.resumo_qualidade ORDER BY 1;
SELECT ano_origem,count(*) FROM dw.fato_voo GROUP BY 1 ORDER BY 1;
SELECT count(*) FROM dw.fato_voo;
```

Esperado: `2019: 983414 / 470 / 18 / 982926`; `2020: 483545 / 124 / 1512 / 481909`; total da fato `1464835`.

Terminal, carga idempotente com validação na mesma transação:

```bash
psql -X -w -v ON_ERROR_STOP=1 --single-transaction \
  -f sql/integracao/03_carga_dw.sql \
  -f sql/integracao/04_validar.sql
```

## Testes sem tocar no banco principal

| Comando na raiz | Finalidade |
|---|---|
| `python -m unittest discover -s tests` | Ingestão + pipeline sintético automatizado e manual em clusters novos |
| `python scripts/testar_integracao_isolada.py --bundle .local/integracao/bundle --cluster .local/teste_novo_automatico` | Carga completa automatizada em cluster isolado |
| `python scripts/testar_integracao_isolada.py --manual --bundle .local/integracao/bundle --cluster .local/teste_novo_manual` | Mesmas etapas B1–B11, executadas separadamente em PostgreSQL single-user |

Os dois últimos exigem diretórios de cluster inexistentes e binários `initdb`/`postgres`. Não iniciam servidor JDBC nem validam cliques do DataGrip. Consulte o [relatório de validação do guia](../relatorio/validacao_guia_execucao.md) para distinguir o que foi executado do que exige uma máquina com permissões administrativas/rede.

## Migração

Não é B1–B11. Identifique a conexão existente, teste um backup restaurado e só depois execute A1 com PG* corretos. O executor faz outro backup obrigatório, conserva schemas anteriores e concilia o RAW histórico antes do commit. Os comandos detalhados de identificação, backup e recuperação estão na seção 14 do guia. **Nenhuma migração do banco original foi executada nesta entrega.**
