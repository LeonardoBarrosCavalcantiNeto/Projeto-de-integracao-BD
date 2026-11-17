# Integração VRA / ANAC — 2019 e 2020

Projeto universitário de Banco de Dados. A implementação integrada lê os 24 CSVs originais, executa ELT no PostgreSQL, preserva auditorias e carrega um único esquema estrela com sete dimensões. Não processa 2021.

A execução principal é `scripts/integrar_anac.py`. Os notebooks e scripts dos integrantes foram preservados como implementações experimentais e referências de comparação. Os scripts históricos de `sql/elt/2019/` não são pré-requisito da nova execução.

## Execução

Requisitos: Python 3.11+ e ferramentas PostgreSQL (`psql`, `pg_dump`, `pg_restore`, `createdb`) compatíveis com a versão do servidor. A integração usa apenas a biblioteca padrão Python. As comparações com ETL usam as dependências de `requirements.txt`.

Na raiz do repositório:

```bash
python3 scripts/integrar_anac.py prepare \
  --dados-2019 '/caminho/Base de dados 2019' \
  --dados-2020 '/caminho/Base de dados 2020'
```

Configure `PGHOST`, `PGPORT`, `PGUSER` e `PGDATABASE=anac_dw` no ambiente. Use `.pgpass` com permissão 0600 ou `PGPASSWORD` localmente. A aplicação não lê `.env` automaticamente e não imprime senhas. O banco deve existir. Para teste, são permitidos bancos cujo nome começa com `anac_teste_`.

```bash
export PGHOST=127.0.0.1 PGPORT=5432 PGUSER=postgres PGDATABASE=anac_dw
python3 scripts/integrar_anac.py apply
```

`apply` faz backup completo, restaura em banco temporário e só então migra `raw`, `staging` e `dw` em transação. Os schemas anteriores são preservados com sufixo `_antes_AAAAMMDD_HHMMSS`. Compara os 20 campos do RAW histórico com os CSVs, incluindo multiplicidades; divergência impede o commit. O banco temporário de restauração também é preservado. É necessário espaço para o backup, a restauração e as camadas novas, além de permissão para criar um banco de teste.

As validações e as análises são executadas automaticamente. A carga da fato é repetida e validada para verificar idempotência. Os arquivos grandes ficam em `.local/` e `backups/`, ignorados pelo Git.

## Documentação e evidências

- [Arquitetura, regras, execução e recuperação](documentacao/integracao_2019_2020.md).
- [Relatório da execução e limitações reais](relatorio/integracao_2019_2020.md).
- [Backup isolado e restauração testada](resultados/validacoes/integracao_2019_2020/backup_isolado.json).
- [Consultas para apresentação](sql/integracao/05_analises.sql).
- [Asserções de validação](sql/integracao/04_validar.sql).
- [Evidências compactas medidas](resultados/validacoes/integracao_2019_2020/).
- Contrato acadêmico: `documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf`.

A situação do banco original e a do banco isolado são descritas separadamente no relatório. Não presumir que executar os testes isolados atualiza o PostgreSQL usado no DataGrip.

## Organização

```text
scripts/integrar_anac.py                 preparação + backup/restauração + migração
scripts/testar_integracao_isolada.py      teste PostgreSQL sem sockets
scripts/auditar_integracao_isolada.py     extração de evidências e identidade CSV/RAW
scripts/comparar_integracao.py           ETLs originais × ELT por conteúdo
sql/integracao/                          dimensão, carga, validações e análises
sql/transformacoes/elt_2020.sql           transformação original reutilizada
sql/elt/2019/                            experimento histórico preservado
sql/database/                           DDL histórico reutilizado na geração
notebooks/{etl,elt}/                     implementações dos integrantes
resultados/validacoes/integracao_2019_2020/  evidências pequenas versionáveis
tests/                                  testes de ingestão
.local/integracao/                       bundles, saídas ETL e cluster de teste
backups/                                dumps completos e registros de recuperação
```
