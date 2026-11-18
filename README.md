# Integração VRA/ANAC — ETL e ELT de 2019 a 2021

O projeto integra 36 CSVs mensais de etapas de voo da ANAC. Cada fluxo carrega um Data Warehouse com sete dimensões e uma tabela fato, seguindo o [contrato de tratamento v1.1](documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf).

| Fluxo | Transformação e destino |
|---|---|
| ETL | Python/Pandas trata os CSVs antes da carga. O PostgreSQL recebe os dados em `staging_etl` e carrega `dw_etl`. O schema `raw_etl` preserva a origem para auditoria. |
| ELT | O PostgreSQL recebe os CSVs em `raw`, trata os dados em `staging_elt` e carrega `dw_elt`. |

O ETL integrado dos três anos é coordenado por `scripts/integracao_final.py`, que reutiliza funções Pandas de `scripts/etl_vra_anac_2021.py` também para 2019 e 2020. Os scripts e notebooks individuais registram a implementação de cada integrante. No ELT, `scripts/integrar_anac.py` renderiza o template parametrizado `elt_2019_2020.sql` para os dois anos. `elt_2021.sql` tem regras próprias de layout e conversão. [Decisões técnicas](documentacao/DECISOES_TECNICAS.md)

A execução validada registrou **2.071.472 fatos em cada DW** e **zero divergências** na comparação integral. O ambiente de referência foi Fedora. A execução em Windows e macOS ainda está pendente, e o guia inclui instruções para ambos. [Resultados finais](relatorio/STATUS_FINAL_PROJETO.md) · [Escopo dos testes de portabilidade](relatorio/PORTABILIDADE.md)

## Preparar e executar

Use **Git, Python 3.11+ e PostgreSQL 18**, com `psql` no PATH. Para a carga dos dados reais, planeje cerca de **28 GiB livres no volume do PostgreSQL** após a preparação do bundle de referência. O volume de preparação também precisa de espaço. O comando `check-load` confere o requisito antes da carga. [Requisitos e dimensionamento](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#4-preparar-carregar-e-validar)

1. Clone a branch da entrega quando estiver publicada e entre na pasta do projeto. Execute os comandos seguintes a partir dessa raiz.

   ```bash
   git clone --branch portabilidade-academica https://github.com/LeonardoBarrosCavalcantiNeto/Projeto-de-integracao-BD.git
   cd Projeto-de-integracao-BD
   ```

2. Instale as dependências em um ambiente virtual. O exemplo abaixo é para Linux/macOS com Python 3 no PATH. [Instalação e ativação por sistema](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#1-instalar-ferramentas-e-criar-o-ambiente-python)

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

3. Crie um papel de avaliação e um banco vazio do qual esse papel seja proprietário. Configure `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` e `PGCLIENTENCODING=UTF8` no terminal e confira a conexão antes de carregar. Para executar os ETLs individuais via Python, ajuste `.env.example` numa cópia chamada `.env`. Os bundles finais usam a conexão de `psql`. [Criação do banco, autenticação e teste de conexão](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#3-criar-o-banco-de-avaliação)

4. Obtenha e confira os 36 CSVs oficiais. Se já tiver uma cópia, coloque os arquivos em `dados/brutos/ANO/` e comece por `--apenas-verificar`. Esse comando precisa aprovar todos os meses antes de seguir. [Obtenção dos dados e verificação](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#2-obter-e-conferir-os-36-csvs) · [Manifesto](dados/manifesto_vra.json)

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

```bash
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/validar_final.sql
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/validar_restauracao.sql
```

O primeiro SQL instala o comparador e retorna `COMPARACAO_EXATA_OK` para cada ano quando a comparação passa. O segundo usa esse comparador para conferir contagens, dimensões e chaves e retorna `RESTAURACAO_OK`. Para apresentar as análises por ano, companhia e aeroporto em um cliente SQL, use `sql/integracao/05_analises.sql` com os nomes dos schemas indicados no roteiro. [Roteiro de análises, auditorias e evidências](documentacao/INTEGRACAO_FINAL.md) · [Evidências da validação](resultados/validacoes/integracao_final/)

Os testes usam `unittest`. A suíte completa requer `initdb` e `postgres` no PATH e cria clusters sintéticos temporários. Execute a suíte completa a partir da raiz.

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
| `notebooks/` | Implementações dos integrantes e exploração. Para executar notebooks localmente, instale Jupyter e ipykernel no ambiente de trabalho. |
| `tests/` | Testes de ingestão, geração SQL, integridade e equivalência |
| `documentacao/`, `relatorio/` | Guias, modelo dimensional, decisões e resultados medidos |

Para detalhes sobre a implementação e a avaliação acadêmica, consulte a [arquitetura final](documentacao/INTEGRACAO_FINAL.md), o [modelo dimensional](documentacao/MODELO_DIMENSIONAL_FINAL.md) e a [matriz de conformidade](documentacao/MATRIZ_CONFORMIDADE_FINAL.md).
