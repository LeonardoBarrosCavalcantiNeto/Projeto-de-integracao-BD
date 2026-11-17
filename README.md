## 📁 Estrutura do Projeto

```text
Projeto-de-integracao-BD/
├── README.md
├── .gitignore
├── requirements.txt
├── .env.example
│
├── dados/
│   ├── brutos/
│   │   ├── 2019/
│   │   │   ├── VRA_2019_01.csv
│   │   │   ├── VRA_2019_02.csv
│   │   │   └── ... VRA_2019_12.csv
│   │   ├── 2020/
│   │   │   ├── VRA_2020_01.csv
│   │   │   └── ... VRA_2020_12.csv
│   │   └── 2021/
│   │       ├── VRA_2021_01.csv
│   │       └── ... VRA_2021_12.csv
│   │
│   └── processados/
│       ├── 2019/
│       ├── 2020/
│       └── 2021/
│
├── notebooks/
│   ├── exploracao/
│   │   ├── exploracao_2019.ipynb
│   │   ├── exploracao_2020.ipynb
│   │   └── exploracao_2021.ipynb
│   │
│   ├── etl/
│   │   ├── etl_2019.ipynb
│   │   ├── etl_2020.ipynb
│   │   └── etl_2021.ipynb
│   │
│   └── elt/
│       ├── elt_2019.ipynb
│       ├── elt_2020.ipynb
│       └── elt_2021.ipynb
│
├── scripts/
│   └── etl_vra_2019.py
│
├── sql/
│   ├── criacao_dw.sql
│   ├── carga_dimensoes.sql
│   ├── carga_fato.sql
│   ├── analises.sql
│   └── transformacoes/
│
├── documentacao/
│   ├── contrato_dados.md
│   ├── dicionario_dados.md
│   └── esquema_estrela.drawio
│
├── resultados/
│   ├── logs/
│   ├── rejeicoes/
│   └── validacoes/
│
└── relatorio/
    └── relatorio_etl_2019.md
```

## ETL 2021 — Arthur

A implementação transforma os dados em Python antes da carga PostgreSQL;
Murilo Acioli é responsável pelo ELT do mesmo ano. O contrato é a versão 1.1.
O notebook configura e apresenta os resultados; a implementação fica em scripts.

- Notebook: [ETL 2021](notebooks/ETL/etl_vra_anac_2021.ipynb).
- Relatório: [decisões, resultados e pendências](relatorio/relatorio_etl_2021.md).
- Evidências pequenas: `resultados/logs/*etl_2021*` e
  `resultados/validacoes/*etl_2021*`.

### Execução local

Coloque os 12 CSVs `VRA_2021_01.csv` a `VRA_2021_12.csv` em `dados/brutos/`.
No ambiente virtual com as dependências de `requirements.txt`:

```bash
python scripts/etl_vra_anac_2021.py \
  --input-dir dados/brutos \
  --output-dir dados/processados/2021/etl
```

A carga é opcional: configure `DATABASE_URL` PostgreSQL ou as variáveis `PG*`
no ambiente/`.env` local e acrescente `--load-db`. O banco precisa existir.
O schema é `etl_2021`; repetir a carga exige `--replace` explícito.
As dez tabelas são carregadas em uma transação, com conferência das contagens.
Os brutos são preservados byte a byte com manifesto SHA-256; `--export-raw`
acrescenta uma representação tabular regenerada.

### Google Colab

Abra o notebook da branch publicada em uma sessão hospedada CPU nova e execute
as nove células em ordem. A preparação obtém `feat/etl-2021`, instala as
dependências e recebe `data_2021_anac.zip` com os 12 CSVs. Pastas internas são
permitidas e os hashes devem coincidir com o inventário versionado.
O PostgreSQL é instalado somente na sessão hospedada, com credenciais temporárias
mantidas no ambiente. Após a carga, outra transação confere contagens e origens.
Baixe o ZIP de evidências e o notebook executado antes de encerrar a sessão.
A tabela tratada completa é opcional no download, desativada por padrão.

Arthur compartilhou as saídas de uma execução hospedada em 17/11/2026,
com PostgreSQL 16.15 e código `e910c58`, confirmando a carga e a conciliação.
A incorporação do notebook executado e do pacote de evidências dessa sessão
continua pendente; os arquivos já versionados registram a execução local anterior.

### Validação e limites

```bash
python -m unittest discover -s tests -v
```

A suíte usa `unittest`. Para incluir os seis testes de integração PostgreSQL,
configure `ETL_2021_TEST_DATABASE_URL` para um banco dedicado `etl_test` ou
`etl_2021_test`. Eles removem o schema `etl_2021` desse banco de teste;
sem a variável, as duas classes de integração são explicitamente puladas.

Resultado medido: **632.148 brutos = 0 excedentes + 25.511 rejeitados +
606.637 tratados**. Os nove conflitos de descrição aguardam decisão coletiva.
Os inventários ETL/ELT coincidem; a comparação dos valores por registro depende
da tabela tratada completa de Murilo. O comparador está em
`scripts/comparar_etl_elt_2021.py` (`--help` apresenta os argumentos).
Dimensões e Fato ficam para a integração coletiva. Credenciais, ZIPs, CSVs brutos
e bases completas permanecem fora do Git.
