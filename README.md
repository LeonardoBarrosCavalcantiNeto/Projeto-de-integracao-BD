# Integração de Dados VRA/ANAC — ETL e ELT (2019–2021)

Projeto acadêmico de integração de dados de etapas de voo da **Agência Nacional de Aviação Civil (ANAC)**, utilizando **Python/Pandas** e **PostgreSQL 18**. O trabalho processa 36 arquivos CSV mensais, de janeiro de 2019 a dezembro de 2021, por dois caminhos independentes — ETL e ELT — e compara integralmente seus resultados.

O objetivo não é apenas carregar os dados, mas preservar sua origem, aplicar o [contrato de tratamento v1.1](documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf), construir dois Data Warehouses dimensionais e demonstrar que os dois métodos chegam ao mesmo resultado.

## 1. Visão geral

| Aspecto | Descrição |
|---|---|
| Fonte | 36 CSVs mensais de VRA/ANAC, 2019–2021 |
| Tecnologias | Python 3.11+, Pandas, PostgreSQL 18, SQL e `psql` |
| ETL | Extrair CSV → transformar com Pandas → carregar no PostgreSQL |
| ELT | Extrair CSV → carregar dados brutos no PostgreSQL → transformar com SQL |
| Armazenamento analítico | Dois schemas independentes: `dw_etl` e `dw_elt` |
| Modelo | Esquema estrela, com sete dimensões e uma tabela fato por DW |
| Qualidade | Deduplicação, conversão de tipos, rejeições justificadas, anomalias e rastreabilidade |
| Verificação final | Comparação integral dos dois pipelines, dimensões, chaves e conteúdo |

### Como funcionam os dois fluxos

```text
                   36 CSVs oficiais da ANAC
                              |
              +---------------+---------------+
              |                               |
              v                               v
         ETL (Python)                    ELT (PostgreSQL)
    Extração e tratamento          Carga do conteúdo bruto
        com Pandas                       no schema raw
              |                               |
              v                               v
      CSVs já tratados              Tratamento SQL no schema
      e auditados                    staging_elt
              |                               |
              v                               v
    raw_etl / staging_etl                    dw_elt
              |                               |
              v                               |
            dw_etl                            |
              |                               |
              +---------------+---------------+
                              |
                              v
                   Comparação integral
```

O ETL integrado dos três anos é coordenado por [`scripts/integracao_final.py`](scripts/integracao_final.py), que reutiliza as funções Pandas de [`scripts/etl_vra_anac_2021.py`](scripts/etl_vra_anac_2021.py). Para o ELT, [`scripts/integrar_anac.py`](scripts/integrar_anac.py) utiliza o template parametrizado de 2019/2020 e o SQL próprio de 2021. As implementações e os notebooks individuais permanecem no repositório como parte do desenvolvimento do grupo. Veja as [decisões técnicas](documentacao/DECISOES_TECNICAS.md).

**Importante:** os dois DWs armazenam o **mesmo conjunto de ocorrências tratadas** por métodos diferentes. Não se deve somar `dw_etl` e `dw_elt` como se representassem voos diferentes.

## 2. Resultados validados

A reprodução com os 36 CSVs reais foi concluída com sucesso: os dois scripts de carga retornaram **código de saída 0** e `COMMIT`; o comparador confirmou a equivalência do conteúdo e a integridade dimensional.

| Ano | Registros brutos | Duplicatas excedentes | Rejeições | Fatos no ETL | Fatos no ELT |
|---|---:|---:|---:|---:|---:|
| 2019 | 983.414 | 470 | 18 | 982.926 | 982.926 |
| 2020 | 483.545 | 124 | 1.512 | 481.909 | 481.909 |
| 2021 | 632.148 | 0 | 25.511 | 606.637 | 606.637 |
| **Total** | **2.099.107** | **594** | **27.041** | **2.071.472** | **2.071.472** |

Conciliação aplicada a cada ano: **brutos = duplicatas excedentes + rejeições + registros tratados**. As anomalias são registradas para auditoria e não implicam necessariamente exclusão.

Na validação final, os resultados esperados incluem:

```text
DIMENSOES_E_FKS_OK
COMPARACAO_EXATA_OK 2019 (...)
COMPARACAO_EXATA_OK 2020 (...)
COMPARACAO_EXATA_OK 2021 (...)
```

A comparação não verifica somente as contagens: confere conteúdo bruto, dados tratados, duplicatas, rejeições, tabela fato, rastreabilidade e dimensões. Consulte [resultados finais](relatorio/STATUS_FINAL_PROJETO.md), [qualidade dos dados](relatorio/QUALIDADE_2019_2021.md) e [matriz de conformidade](documentacao/MATRIZ_CONFORMIDADE_FINAL.md).

## 3. Pré-requisitos

- **Git**, para obter o repositório.
- **Python 3.11 ou superior**, com `venv` e `pip`.
- **PostgreSQL 18**, servidor e cliente `psql` acessível no terminal.
- Conexão com a internet para baixar os CSVs, caso ainda não estejam disponíveis localmente.
- Espaço livre para os CSVs, os arquivos de preparação e o banco. Para o bundle real de referência, o verificador de carga exige cerca de **28 GiB livres no volume do PostgreSQL**; o volume da preparação também precisa de espaço. Use `check-load` antes de carregar.

Confira as versões:

```bash
python3 --version
psql --version
pg_isready
```

O comando `pg_isready` confirma que o servidor responde, **não** que o usuário consegue se autenticar. Caso haja mais de uma instalação PostgreSQL (por exemplo, servidor local e container Docker), confira qual está recebendo as conexões. A configuração e os procedimentos para **Fedora/Linux, Windows e macOS** estão no [guia de reprodução multiplataforma](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#1-instalar-ferramentas-e-criar-o-ambiente-python).

## 4. Reprodução completa — passo a passo

> **Execute os comandos a partir da raiz do repositório, na ordem apresentada.** Para reconstruir do zero, use um banco PostgreSQL **novo e vazio**.

### 4.1. Clonar e instalar dependências

```bash
git clone https://github.com/LeonardoBarrosCavalcantiNeto/Projeto-de-integracao-BD.git
cd Projeto-de-integracao-BD

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Esses comandos de ambiente virtual são para **Linux/macOS**. No **Windows/PowerShell**, a criação e ativação são diferentes; consulte a [seção correspondente do guia](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#1-instalar-ferramentas-e-criar-o-ambiente-python).

### 4.2. Criar e selecionar um banco de avaliação

Use o procedimento de [criação do banco de avaliação](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#3-criar-o-banco-de-avaliação) para configurar um papel com acesso ao banco, preferencialmente `anac_avaliacao` em um banco vazio chamado `anac_repro`. Não é necessário usar o usuário administrador `postgres` para executar todas as cargas.

No Linux/macOS, **após** criar o banco e o papel, configure a conexão TCP prevista pelo guia:

```bash
export PGHOST=127.0.0.1
export PGPORT=5432
export PGUSER=anac_avaliacao
export PGDATABASE=anac_repro
export PGCLIENTENCODING=UTF8
```

O PostgreSQL pode solicitar a senha do papel. Para uso prolongado, o guia explica como configurar `.pgpass`, sem armazenar senha no repositório.

Confirme a conexão e o destino **antes de executar qualquer carga**:

```bash
psql -X -v ON_ERROR_STOP=1 -c \
  "SELECT current_database(), current_user, current_setting('server_version');"
```

O banco indicado deve ser o de avaliação, e a versão do servidor deve ser PostgreSQL 18. Também confira se não há tabelas próprias:

```bash
psql -X -v ON_ERROR_STOP=1 -c \
  "SELECT schemaname, tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2;"
```

**Caso particular do Fedora/Linux:** se a conexão com `-h localhost` falhar por `Ident`, teste uma conexão por socket Unix (sem `-h` e sem `PGHOST`) usando um papel já configurado no servidor, por exemplo:

```bash
env -u PGHOST psql -U "$(whoami)" -d postgres -c \
  "SELECT current_user, current_database();"
```

Essa alternativa **só funciona se o papel correspondente existir e estiver autorizado**. Em uma instalação local, o administrador pode acessar a conta PostgreSQL com `sudo -u postgres psql -d postgres` e seguir o guia de configuração. Não altere `pg_hba.conf` às cegas: primeiro confira a autenticação e a porta reais. Ver [solução de problemas](#7-solução-de-problemas).

### 4.3. Baixar e verificar os 36 CSVs

```bash
python scripts/baixar_vra.py
python scripts/baixar_vra.py --apenas-verificar
```

Os arquivos são organizados em `dados/brutos/2019/`, `dados/brutos/2020/` e `dados/brutos/2021/`, com os nomes `VRA_ANO_MM.csv`. A saída esperada informa que **36 CSVs foram conferidos por tamanho e SHA-256**.

O [manifesto](dados/manifesto_vra.json) define o conjunto de arquivos esperado. Se os CSVs já estiverem presentes, você pode executar somente `--apenas-verificar`. Divergências de tamanho ou hash devem ser corrigidas antes de continuar; não altere manualmente o conteúdo bruto para fazê-lo passar.

### 4.4. Preparar ETL e ELT

```bash
python scripts/integracao_final.py prepare \
  --dados-2019 dados/brutos/2019 \
  --dados-2020 dados/brutos/2020 \
  --dados-2021 dados/brutos/2021 \
  --output .local/reproducao
```

Essa etapa:

1. Confere e lê os arquivos de cada ano.
2. **Executa o tratamento ETL em Python/Pandas** e gera os dados tratados e as auditorias.
3. Prepara os arquivos brutos e comandos necessários ao ELT em SQL.
4. Gera, entre outros artefatos, `manifesto_final.json`, `01_elt.psql` e `02_etl.psql` dentro de `.local/reproducao/`.

**Atenção à diferença:** finalizar `prepare` **não** significa que os dois DWs já foram carregados. Os comandos `.psql` da etapa 4.6 ainda precisam ser executados.

Se quiser conferir a preparação e os arquivos gerados, rode:

```bash
python scripts/validar_guia.py --bundle .local/reproducao
```

### 4.5. Verificar espaço no volume do PostgreSQL

Identifique o diretório de dados do servidor:

```bash
psql -X -v ON_ERROR_STOP=1 -At -c "SHOW data_directory;"
```

Utilize um **diretório existente no mesmo volume** desse local como argumento de `--volume-pg`:

```bash
python scripts/integracao_final.py check-load \
  --output .local/reproducao \
  --volume-pg "CAMINHO_DO_VOLUME_PG"
```

Substitua `CAMINHO_DO_VOLUME_PG` pelo caminho adequado à sua instalação. O espaço livre em `dados/` ou `.local/reproducao/` pode ser diferente do espaço livre onde o banco armazena tabelas, índices, arquivos temporários e WAL. Se a verificação falhar, resolva o armazenamento **antes** de iniciar a carga.

### 4.6. Carregar os dois Data Warehouses no PostgreSQL

Execute **um comando de cada vez** no banco vazio já selecionado pelas variáveis `PG*`:

**Primeiro: ELT (transformações em SQL dentro do PostgreSQL).**

```bash
psql -X -v ON_ERROR_STOP=1 \
  -f .local/reproducao/01_elt.psql
```

**Depois: ETL (carga do conteúdo previamente tratado com Pandas).**

```bash
psql -X -v ON_ERROR_STOP=1 \
  -f .local/reproducao/02_etl.psql
```

Ambas as cargas devem terminar sem erros e com `COMMIT`. O `ON_ERROR_STOP=1` interrompe o `psql` ao detectar erro em um script. Os arquivos gerados incluem caminhos de importação `\copy`: se você mover o repositório ou a pasta de saída após `prepare`, gere o bundle novamente.

### 4.7. Validar a equivalência ETL × ELT

```bash
psql -X -v ON_ERROR_STOP=1 \
  -f sql/comparacao/validar_final.sql
```

Confira `DIMENSOES_E_FKS_OK` e `COMPARACAO_EXATA_OK` para **2019, 2020 e 2021**. Uma execução do script sem erro é importante, mas a aprovação dessas verificações é a confirmação dos resultados.

Para conferir as contagens das fatos sem refazer a carga:

```sql
SELECT 'ETL' AS fluxo, ano_origem, count(*) AS fatos
FROM dw_etl.fato_voo GROUP BY ano_origem
UNION ALL
SELECT 'ELT', ano_origem, count(*)
FROM dw_elt.fato_voo GROUP BY ano_origem
ORDER BY ano_origem, fluxo;
```

O resultado esperado tem **seis linhas**, com **982.926**, **481.909** e **606.637** fatos, uma vez para cada DW.

## 5. Consultas e apresentação

Com os Data Warehouses carregados, as consultas podem ser executadas pelo `psql`, DataGrip, DBeaver ou pgAdmin. Use sempre a conexão do **mesmo banco** em que realizou a carga.

### Consultas de comparação e rastreabilidade

```bash
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/analises_finais.sql
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/rastreabilidade.sql
```

### Análises do relatório

```bash
psql -X -v ON_ERROR_STOP=1 -f analysis/01_evolucao_voos.sql
psql -X -v ON_ERROR_STOP=1 -f analysis/02_atrasos_partida.sql
psql -X -v ON_ERROR_STOP=1 -f analysis/03_companhias_aeroportos.sql
```

Essas consultas apresentam a evolução anual de voos, a frequência e duração dos atrasos, e os principais aeroportos e companhias. Os resultados são identificados por `ETL` e `ELT`; **não some os dois fluxos** ao analisar as ocorrências.

Para explorar a arquitetura, os indicadores e os exemplos de rastreabilidade durante a apresentação, veja o [guia de demonstração prática](documentacao/GUIA_DEMONSTRACAO_PRATICA.md) e o [modelo dimensional](documentacao/MODELO_DIMENSIONAL_FINAL.md).

## 6. Estrutura do repositório

| Diretório / arquivo | Conteúdo |
|---|---|
| `scripts/` | Download, ingestão, transformação Pandas, preparação e validação dos bundles |
| `sql/transformacoes/` | Templates e regras SQL do ELT |
| `sql/database/` | Modelo dimensional e definição do DW |
| `sql/integracao/` | Etapas SQL de integração e demonstração |
| `sql/comparacao/` | Comparação final, análises e rastreabilidade |
| `analysis/` | Três consultas SQL das análises do relatório |
| `dados/manifesto_vra.json` | Manifesto de integridade dos CSVs oficiais |
| `notebooks/` | Notebooks das implementações individuais |
| `tests/` | Testes automatizados de ingestão, regras, geração e integração |
| `documentacao/` | Contrato, modelo, decisões e guias de reprodução |
| `relatorio/` | Qualidade, resultados, portabilidade e documentação de apoio |
| `resultados/validacoes/` | Evidências compactas versionadas |
| `.local/` | Saídas temporárias geradas localmente (não versionadas) |

Cada DW usa as dimensões `dim_tempo`, `dim_companhia_aerea`, `dim_aeroporto`, `dim_situacao_voo`, `dim_justificativa`, `dim_tipo_linha` e `dim_equipamento`, além de `fato_voo`. A granularidade da fato é **uma ocorrência válida de etapa de voo**, mantendo `ano_origem`, identificação da origem e atributos necessários para auditoria. Consulte o [modelo dimensional](documentacao/MODELO_DIMENSIONAL_FINAL.md).

## 7. Solução de problemas

| Sintoma | O que verificar / como resolver |
|---|---|
| `Ident authentication failed` ao usar `-h localhost` | O servidor respondeu, mas a autenticação TCP falhou. Confira o usuário e as regras do servidor. No Linux, teste uma conexão por socket sem `-h` e sem `PGHOST`, somente com um papel autorizado. Use o guia para configurar o acesso definitivo. |
| `pg_isready` aceita conexões, mas `psql` falha | `pg_isready` não valida suas credenciais. Teste `psql` com o banco, porta, papel e método de autenticação corretos. |
| `database ... does not exist` ou `role ... does not exist` | Crie o banco e o papel de avaliação conforme a seção 4.2. Não presuma que toda instalação possui um papel igual ao usuário do sistema. |
| `schema ... already exists` ou objetos duplicados | O banco provavelmente não está vazio, ou houve uma carga anterior. Verifique o banco atual e os schemas, e utilize outro banco novo para uma reconstrução integral. |
| `\copy` não encontra o arquivo | Confira o bundle em `.local/reproducao/`, os caminhos absolutos embutidos e a existência dos CSVs preparados. Não mova o bundle depois do `prepare` sem regenerá-lo. |
| Verificação de SHA-256 falha | Confira se os CSVs são exatamente os da versão registrada no manifesto. Não modifique o arquivo original; obtenha a versão correspondente antes de continuar. |
| Falta de espaço | Confirme o volume de dados do PostgreSQL e rode `check-load` com um diretório no volume correto. O espaço da pasta do projeto não garante espaço no banco. |
| `NOTICE: table ... does not exist, skipping` | Normal em uma carga inicial quando `DROP TABLE IF EXISTS` encontra uma tabela ainda não criada. É um aviso, não um erro. |
| Execução parece parada | Pode estar processando milhões de registros. Se a saída foi direcionada para um log, acompanhe-o no segundo terminal, sem interromper o principal. |
| Erro durante o ETL após ELT concluído | Confirme o estado do banco e a transação; o guia descreve como corrigir a falha e retomar só a carga ETL quando o schema correspondente estiver ausente. |
| Validação retorna divergência | Não considere a entrega aprovada. Consulte a primeira divergência reportada, o manifesto e as auditorias; compare as regras do contrato e os registros identificados por ano, arquivo e linha. |

### Observação: acompanhar logs (opcional)

Se quiser acompanhar a execução em tempo real, redirecione a saída do **comando de carga** a um arquivo. Exemplo para o ELT:

```bash
psql -X -v ON_ERROR_STOP=1 \
  -f .local/reproducao/01_elt.psql \
  > .local/reproducao/execucao_elt.log 2>&1

echo "Código de saída: $?"
```

Em **outro terminal** (Linux/macOS), use:

```bash
tail -f .local/reproducao/execucao_elt.log
```

Para o ETL, substitua o script por `02_etl.psql` e o nome do log por `execucao_etl.log`. O `tail -f` apenas acompanha o arquivo; `Ctrl+C` **nesse segundo terminal** encerra a visualização, não a carga. Esse acompanhamento não é obrigatório para reproduzir o projeto.

**Como interpretar a saída:** `INSERT 0 2071472` significa que uma operação inseriu 2.071.472 linhas; não significa que o arquivo de origem tinha apenas essa quantidade. A diferença para os 2.099.107 brutos decorre de **594 duplicatas excedentes** e **27.041 rejeições**. `COMMIT` indica a confirmação da transação, mas o comparador final ainda deve ser executado.

## 8. Testes automatizados (opcional)

Com o ambiente Python ativado, execute:

```bash
python -m unittest discover -s tests -v
```

Os testes de integração usam dados sintéticos e podem necessitar dos binários `initdb` e `postgres` no `PATH` para criar clusters temporários. Algumas verificações opcionais do ETL 2021 exigem `ETL_2021_TEST_DATABASE_URL` apontando para **um banco descartável e vazio**, nunca para a instalação da entrega. Detalhes em [testes e alcance](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#7-testes-e-alcance).

## 9. Backup e restauração (opcional)

Não é necessário subir backups ou arquivos CSV pesados ao GitHub para reproduzir a avaliação. O [guia de reprodução](documentacao/REPRODUCAO_MULTIPLATAFORMA.md#6-backup-lógico-e-restauração) descreve como criar um backup lógico com `pg_dump`, restaurá-lo em **um banco novo** e conferir a restauração com `sql/comparacao/validar_restauracao.sql`.

**Atenção:** `validar_restauracao.sql` é destinado à etapa de restauração. Na execução padrão, após ETL e ELT, utilize `sql/comparacao/validar_final.sql`.

## 10. Documentação complementar

- [Reprodução multiplataforma](documentacao/REPRODUCAO_MULTIPLATAFORMA.md): instalação, autenticação, preparação, carga, armazenamento, backups e testes.
- [Guia de demonstração prática](documentacao/GUIA_DEMONSTRACAO_PRATICA.md): roteiro de consultas para apresentação.
- [Integração final](documentacao/INTEGRACAO_FINAL.md): detalhes do funcionamento dos scripts e das etapas SQL.
- [Modelo dimensional](documentacao/MODELO_DIMENSIONAL_FINAL.md): dimensões, fato, chaves e rastreabilidade.
- [Contrato de tratamento v1.1](documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf): regras oficiais adotadas pelos pipelines.
- [Matriz de conformidade](documentacao/MATRIZ_CONFORMIDADE_FINAL.md): atendimento aos requisitos e critérios de qualidade.
- [Resultados finais](relatorio/STATUS_FINAL_PROJETO.md) e [qualidade](relatorio/QUALIDADE_2019_2021.md): evidências, totais e análises.
- [Portabilidade](relatorio/PORTABILIDADE.md): ambientes efetivamente testados e cenários ainda pendentes.

---

**Resumo da reprodução:** clonar → instalar dependências → configurar banco vazio → baixar/verificar 36 CSVs → `prepare` → `check-load` → `01_elt.psql` → `02_etl.psql` → `validar_final.sql`. Quando a validação retorna `DIMENSOES_E_FKS_OK` e `COMPARACAO_EXATA_OK` para os três anos, os pipelines foram conciliados conforme os critérios do projeto.
