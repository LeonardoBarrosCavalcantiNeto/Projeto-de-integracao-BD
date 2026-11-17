# Projeto de integração — VRA/ANAC

Projeto do grupo com dados de 2019, 2020 e 2021. Em 2021, Arthur implementa o
ETL e Murilo Acioli implementa o ELT. O contrato de tratamento é a versão 1.1,
em [documentacao/](documentacao/).

## Executar o ETL de 2021

Com os 12 arquivos `VRA_2021_01.csv` a `VRA_2021_12.csv` em `dados/brutos/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/etl_vra_anac_2021.py \
  --input-dir dados/brutos \
  --output-dir dados/processados/2021/etl
```

Alternativamente, execute as quatro células de
[etl_vra_anac_2021.ipynb](notebooks/ETL/etl_vra_anac_2021.ipynb), com o kernel da
`.venv`. O notebook contém as instruções para Google Colab; a reprodução no Colab
**ainda está pendente**.

O script transforma antes da carga, preserva os originais byte a byte em
`vra_bruta/` com manifesto SHA-256 e exporta tratamento, rejeições, auditorias e
conciliações. `--export-raw` adiciona uma **tabela regenerada** com metadados.
Os dados completos continuam fora do Git em `dados/processados/`.

## PostgreSQL opcional

Configure `DATABASE_URL` PostgreSQL ou `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`
e `PGPASSWORD` no ambiente ou `.env` local. O banco precisa existir. Acrescente
`--load-db` ao comando anterior. O schema é exclusivamente `etl_2021`;
`--replace` permite substituir as dez tabelas do pipeline em uma transação.
`status_carga_postgresql.json` e `metadados_execucao.json` registram o resultado
da execução atual. Sucesso exige a confirmação da transação.

As dez tabelas são `vra_bruta`, `vra_tratada`, `vra_rejeicoes`,
`vra_duplicatas_excluidas`, `vra_anomalias`, `vra_conflitos_codigo`,
`vra_possiveis_duplicatas_padronizacao`, `inventario_arquivos`,
`resumo_qualidade` e `etl_log_arquivos`. Dimensões e Fato dependem da integração
coletiva.

## Testes

```bash
python -m unittest discover -s tests -v
```

Os testes usam `unittest`. Para executar também a integração PostgreSQL, defina
`ETL_2021_TEST_DATABASE_URL` com uma URL PostgreSQL de teste dedicada, usando banco
chamado **`etl_test` ou `etl_2021_test`**, e repita o comando. Essa suíte remove o
schema `etl_2021` desse banco de teste antes e depois dos casos. Sem a variável,
esses três testes são explicitamente pulados.

A validação desta entrega usou PostgreSQL 17 em Docker isolado. A evidência está
em [validacao_postgresql_etl_2021.json](resultados/validacoes/validacao_postgresql_etl_2021.json).

## Comparar com o ELT do Murilo

O inventário do ELT já foi obtido de `origin/integracao-elt`, commit
`b6c6b463e0eadb76be86a72415d3eb288610d0d0`; os mesmos arquivos de 2021 também estão
na `origin/main` examinada. Os 12 hashes, tamanhos e contagens coincidem com o ETL.
A conferência está registrada em `comparacao_etl_elt_2021.json`, com a origem e os
hashes dos inventários. As cópias de consulta ficam fora do Git em
`dados/processados/2021/referencia_elt_murilo/`.

Ainda falta a **tabela tratada completa** do ELT. Para obtê-la, Murilo pode usar
`EXPORTAR_TRATADA_COMPLETA=True`; outra possibilidade é reproduzir o código dele
em um PostgreSQL isolado, identificando o resultado como reprodução local.

Para recuperar o inventário sem trocar de branch ou integrar arquivos:

```bash
git fetch origin
mkdir -p dados/processados/2021/elt_referencia
git show b6c6b463e0eadb76be86a72415d3eb288610d0d0:resultados/logs/inventario_arquivos_elt_2021.csv > dados/processados/2021/elt_referencia/inventario_arquivos_elt_2021.csv
```

Após obter a tratada completa, informe seu caminho no comando:

```bash
python scripts/comparar_etl_elt_2021.py \
  --inventario-etl dados/processados/2021/etl/inventario_arquivos.csv \
  --inventario-elt dados/processados/2021/elt_referencia/inventario_arquivos_elt_2021.csv \
  --tratada-etl dados/processados/2021/etl/vra_tratada.csv.gz \
  --tratada-elt CAMINHO_DA_TRATADA_ELT.csv \
  --output resultados/validacoes/comparacao_etl_elt_2021.json
```

O comparador verifica hashes dos 12 arquivos, presença por
`arquivo_origem + linha_origem` e atributos, métricas e flags. Normaliza datas,
números, booleanos e nulos; preserva zeros à esquerda no número do voo e
distingue nulo de zero. Usa SQLite temporário para manter as chaves fora da RAM.
Retorna código 0 para equivalência e 1 para divergência ou falha.
A comparação dos valores por registro com o ELT **ainda está pendente**; o JSON
registra essa condição separadamente da conferência já concluída dos inventários.

## Evidências e relatório

- [Relatório ETL 2021](relatorio/relatorio_etl_2021.md): decisões, conciliação,
  conflitos, testes e pendências.
- [Planejamento dos cinco commits](relatorio/planejamento_commits_etl_2021.md):
  escopo e arquivos de cada etapa; mensagens sujeitas à edição e autorização de Arthur.
- `resultados/logs/`: inventário e metadados pequenos da execução.
- `resultados/validacoes/`: qualidade, conciliação mensal, conflitos e validações.

Resultado medido: **632.148 = 0 excedentes + 25.511 rejeitados + 606.637 tratados**.
Os nove conflitos de descrição aguardam decisão coletiva antes das dimensões.
Credenciais, CSVs de entrada e dados completos permanecem fora do Git.
