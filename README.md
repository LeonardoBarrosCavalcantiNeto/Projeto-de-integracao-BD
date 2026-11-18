# Integração VRA/ANAC — ETL e ELT de 2019 a 2021

O projeto integra 36 CSVs mensais de etapas de voo da ANAC. Cada fluxo carrega um Data Warehouse com sete dimensões e uma tabela fato, seguindo o [contrato de tratamento v1.1](documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf).

| Fluxo | Transformação e destino |
|---|---|
| ETL | Python/Pandas trata os CSVs antes da carga. O PostgreSQL recebe os dados em `staging_etl` e carrega `dw_etl`. O schema `raw_etl` preserva a origem para auditoria. |
| ELT | O PostgreSQL recebe os CSVs em `raw`, trata os dados em `staging_elt` e carrega `dw_elt`. |

O ETL integrado dos três anos é coordenado por `scripts/integracao_final.py`, que reutiliza funções Pandas de `scripts/etl_vra_anac_2021.py` também para 2019 e 2020. Os scripts e notebooks individuais registram a implementação de cada integrante. No ELT, `scripts/integrar_anac.py` renderiza o template parametrizado `elt_2019_2020.sql` para os dois anos. `elt_2021.sql` tem regras próprias de layout e conversão. [Decisões técnicas](documentacao/DECISOES_TECNICAS.md)

A execução histórica com os 36 CSVs registrou **2.071.472 fatos em cada DW** e **zero divergências** na comparação integral. O ambiente de referência foi Fedora. O guia inclui instruções para Windows e macOS, que ainda aguardam validação nesses sistemas. [Resultados e verificações da entrega](relatorio/STATUS_FINAL_PROJETO.md) · [Portabilidade](relatorio/PORTABILIDADE.md)

## Preparar e executar

Use **Git, Python 3.11+ e PostgreSQL 18**, com `psql` no PATH. Para a carga dos dados reais, planeje cerca de **28 GiB livres no volume do PostgreSQL** após a preparação do bundle de referência. O volume de preparação também precisa de espaço. O comando `check-load` confere o requisito antes da carga. [Requisitos e dimensionamento](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#4-preparar-carregar-e-validar)

1. Clone o repositório. O clone padrão seleciona a `main`. Execute os comandos seguintes a partir da raiz do projeto.

   ```bash
   git clone https://github.com/LeonardoBarrosCavalcantiNeto/Projeto-de-integracao-BD.git
   cd Projeto-de-integracao-BD
   ```

2. Instale as dependências em um ambiente virtual. O exemplo abaixo é para Linux/macOS com Python 3 no PATH. [Instalação e ativação por sistema](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#1-instalar-ferramentas-e-criar-o-ambiente-python)

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

3. Crie um papel de avaliação e um banco vazio do qual esse papel seja proprietário. Configure `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` e `PGCLIENTENCODING=UTF8` no terminal e confira a conexão antes de carregar. Para executar os ETLs individuais via Python, ajuste `.env.example` numa cópia chamada `.env`. Os bundles finais usam a conexão de `psql`. [Criação do banco, autenticação e teste de conexão](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#3-criar-o-banco-de-avaliação)

4. Obtenha e confira os 36 CSVs oficiais. Se já tiver uma cópia, coloque os arquivos como `dados/brutos/ANO/VRA_ANO_MM.csv` e execute apenas o segundo comando. A verificação precisa aprovar todos os meses antes da carga. [Obtenção dos dados e verificação](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#2-obter-e-conferir-os-36-csvs) · [Manifesto](dados/manifesto_vra.json)

   ```bash
   python scripts/baixar_vra.py
   python scripts/baixar_vra.py --apenas-verificar
   ```

5. Gere os bundles, confira o espaço e carregue os dois DWs. Substitua `CAMINHO_DO_VOLUME_PG` por um diretório existente no volume de dados do servidor. Use uma pasta de saída nova e pare ao primeiro erro. [Procedimento completo](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#4-preparar-carregar-e-validar)

   ```bash
   python scripts/integracao_final.py prepare --dados-2019 dados/brutos/2019 --dados-2020 dados/brutos/2020 --dados-2021 dados/brutos/2021 --output .local/reproducao
   python scripts/integracao_final.py check-load --output .local/reproducao --volume-pg "CAMINHO_DO_VOLUME_PG"
   psql -X -v ON_ERROR_STOP=1 -f .local/reproducao/01_elt.psql
   psql -X -v ON_ERROR_STOP=1 -f .local/reproducao/02_etl.psql
   ```

## Validar e apresentar

A comparação integral confere RAW, tratamento, descartes, anomalias, fatos, dimensões e chaves. Ela retorna `COMPARACAO_EXATA_OK` para cada ano quando passa.

```bash
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/validar_final.sql
```

Os comandos opcionais abaixo apresentam as análises dos dois DWs e rastreiam ocorrências de 2021 até o CSV de origem.

```bash
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/analises_finais.sql
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/rastreabilidade.sql
```

O backup lógico e a validação de restauração são opcionais para a reprodução. O roteiro manual em cliente SQL e os notebooks dos integrantes também são opcionais. Para o ETL individual de 2021, use `dados/brutos/2021/` ou siga a preparação de ZIP no Colab hospedado. [Backup e restauração](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#6-backup-lógico-e-restauração) · [Demonstração prática](documentacao/GUIA_DEMONSTRACAO_PRATICA.md) · [Notebook ETL 2021](notebooks/etl/etl_vra_anac_2021.ipynb) · [Evidências históricas](resultados/validacoes/integracao_final/)

## Executar os testes

Execute a suíte na raiz com o ambiente Python ativo. Os testes de integração criam clusters sintéticos descartáveis quando encontram `initdb` e `postgres` no PATH. Os testes da carga individual de 2021 e da validação pós-carga do Colab exigem também `ETL_2021_TEST_DATABASE_URL` apontando para um banco descartável e vazio. [Configuração dos testes com PostgreSQL](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#7-testes-e-alcance)

```bash
python -m unittest discover -s tests -v
```

Para a seleção sem PostgreSQL, use `python -m unittest discover -s tests -p NOME_DO_ARQUIVO -v` uma vez para cada módulo.

- `test_baixar_vra.py`
- `test_espaco_disco.py`
- `test_ingestao.py`
- `test_template_elt.py`

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `scripts/` | Preparação, tratamento Pandas, execução e auditoria |
| `sql/{transformacoes,database,integracao,comparacao}/` | Templates ELT, DDL dimensional, cargas, consultas e comparação |
| `notebooks/` | Os notebooks ETL usam o ambiente de `requirements.txt` para execução local. Os notebooks ELT individuais usam o Colab hospedado. |
| `tests/` | Testes de ingestão, geração SQL, integridade e equivalência |
| `documentacao/`, `relatorio/` | Guias, modelo dimensional, decisões e resultados medidos |

Para detalhes sobre a implementação e a avaliação acadêmica, consulte a [arquitetura final](documentacao/INTEGRACAO_FINAL.md), o [modelo dimensional](documentacao/MODELO_DIMENSIONAL_FINAL.md) e a [matriz de conformidade](documentacao/MATRIZ_CONFORMIDADE_FINAL.md).
