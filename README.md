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
