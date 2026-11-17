# Guia completo de instalação e execução — VRA/ANAC 2019 e 2020

## 1. Objetivo

Reconstruir um único Data Warehouse PostgreSQL a partir dos 24 CSVs originais de 2019/2020, preservando RAW, proveniência, duplicatas e rejeições. O roteiro parte de um Fedora novo com DataGrip e internet. Não processa 2021.

Base examinada: branch `integracao-2019-2020-canonica`, commit `a65f7e4`. Esta entrega acrescenta a geração de etapas manuais ao mesmo executor. Os arquivos em `.local/` são **gerados**, não vêm no clone. A tabela de referência rápida está em [ORDEM_DOS_SCRIPTS.md](ORDEM_DOS_SCRIPTS.md).

Há duas escolhas para uma **instalação limpa**:

- **A, recomendado:** Python prepara os arquivos; `apply` faz backup/restauração de teste, importa, transforma, carrega e valida tudo.
- **B, apresentação:** a mesma preparação Python; importação pelo terminal `psql`; tratamento e DW, por arquivos SQL gerados, no DataGrip. Não é um processo exclusivamente gráfico: a preservação da origem depende da preparação Python.

Escolha A **ou** B no banco novo. Não execute B depois de A sobre os mesmos schemas. A migração do banco existente está separada na seção 14; não exige reaplicar as etapas manuais.

**Disponibilidade do código:** os commits desta entrega são locais e nenhum push foi realizado. O clone da branch no GitHub só funcionará se ela já tiver sido publicada por um integrante autorizado. Se a branch não existir no remoto, use o Git bundle descrito na seção 4; não substitua silenciosamente por `main`, que pode não conter o executor.

## 2. Pré-requisitos

| Componente | Necessidade |
|---|---|
| Fedora Linux e terminal Bash | Ambiente principal do roteiro |
| Git | Obter a versão correta do código |
| Python **3.11 ou superior** | `hashlib.file_digest`, leitor CSV e geração SQL |
| PostgreSQL servidor | Armazena, transforma e consulta os dados |
| `psql`, `pg_dump`, `pg_restore`, `createdb` | Chamados pelo executor automatizado; precisam estar no PATH |
| DataGrip e driver JDBC PostgreSQL | Cliente para navegar e apresentar consultas |
| 24 CSVs mensais originais | Não estão versionados no Git |
| `curl` | Baixar os CSVs, se necessário |
| Permissão administrativa no Fedora | Instalar/iniciar serviços; não é usada para rodar o Python |

Reserve aproximadamente **20 GB livres** para uma instalação com dados, temporários e backup/restauração; uma migração pode exigir mais porque conserva schemas e banco restaurado. É uma margem operacional, não uma medição mínima garantida. O desenvolvimento foi feito em máquina com cerca de 8 GB de RAM e swap. Comparações opcionais em Pandas exigem mais memória que a preparação em streaming.

### 2.1 Versões PostgreSQL: o que foi verificado

**Execução real validada: PostgreSQL 18.6.** Use a versão principal 18 para seguir o ambiente de referência. A versão secundária disponível no Fedora ou na imagem `postgres:18` pode ser mais nova; confira a versão efetiva e execute os testes.

Foi realizada análise de compatibilidade com PostgreSQL 16: o projeto usa identity/`OVERRIDING SYSTEM VALUE`, PK/UNIQUE/FK/CHECK, `ON CONFLICT`, janelas, collation C, PL/pgSQL, `make_timestamp`, `make_date`, `EXTRACT`, `cardinality`, `array_remove` e comparação nula segura. Essas construções constam da documentação do 16. **Isso indica compatibilidade de linguagem, mas não certifica a execução integral no 16:** não havia binário/servidor 16 disponível nesta sessão. Versões 16/17 não foram testadas com o conjunto completo.

Use ferramentas de backup da **mesma versão principal do servidor**. Um `pg_dump` mais antigo não atende um servidor mais novo; dump gerado por cliente mais novo também não tem restauração garantida em servidor de versão principal anterior. O backup físico anterior é exclusivo da versão principal 18 e não é um instalador universal.

Fontes: [CREATE TABLE no PostgreSQL 16](https://www.postgresql.org/docs/16/sql-createtable.html), [INSERT no 16](https://www.postgresql.org/docs/16/sql-insert.html), [datas no 16](https://www.postgresql.org/docs/16/functions-datetime.html), [arrays no 16](https://www.postgresql.org/docs/16/functions-array.html) e [compatibilidade do pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html).

## 3. Arquitetura e arquivos efetivamente utilizados

```text
CSVs originais (20 campos, intactos)
   └─ Python prepare: valida formato + acrescenta ID, arquivo, registro lógico e ano
       └─ .local/integracao/bundle/raw_2019.csv e raw_2020.csv (24 campos)
           └─ PostgreSQL raw.voos_2019 / raw.voos_2020
               └─ STAGING anual: classificar → converter → rejeitar → medir
                   └─ STAGING compartilhada + auditorias + raw.ocorrencias
                       └─ sete dimensões e dw.fato_voo
```

| Caminho versionado | Papel real |
|---|---|
| `scripts/integrar_anac.py` | CLI principal; `prepare` e `apply`; também gera a sequência manual |
| `sql/transformacoes/elt_2020.sql` | Template de transformação reutilizado pelo Python para ambos os anos; não executar diretamente no banco canônico |
| `sql/database/10_criacao_dw.sql` | DDL de referência; o gerador corrige a unicidade histórica de `id_raw` para `(ano_origem,id_raw)` |
| `sql/integracao/02_dimensoes.sql` | Resoluções de descrições e cadastros dimensionais; **não** cria sozinho as sete dimensões |
| `sql/integracao/03_carga_dw.sql` | Insere membros dimensionais e fatos com prevenção de duplicação |
| `sql/integracao/04_validar.sql` | Asserções de conciliação, origem, conteúdo, indicadores e relacionamentos |
| `sql/integracao/05_analises.sql` | Consultas para apresentação |
| `sql/integracao/06_casos_limite.sql` | Testes das funções de conversão |
| `sql/integracao/07_diagnosticos.sql` | Grupos duplicados, interseção de inválidos e quantidade de motivos |
| `sql/integracao/08_restricoes.sql` | Reforça NOT NULL e CHECK após carga validada |
| `scripts/testar_integracao_isolada.py` | Testa carga limpa em cluster novo sem sockets; aceita `--manual` |
| `scripts/comparar_integracao.py` | Comparação opcional com os ETLs originais; depende de Pandas |
| `tests/` | Casos de ingestão e execução SQL sintética automatizada/manual |

`sql/database/00_schemas.sql`, `07_dw_schema.sql`, `sql/elt/2019/` e `sql/validacoes/` pertencem ao fluxo histórico. **Não os misture com o roteiro canônico.** Em particular, o DDL histórico sem adaptação mantém unicidade só em `id_raw`, incompatível com os dois anos. Não existe sequência canônica pronta em `sql/elt/2020/`; os arquivos corretos são gerados com base no template de transformação. Os notebooks são preservados para estudo/comparação e não precisam ser executados para criar o DW integrado.

## 4. Instalação das ferramentas e obtenção do código

### 4.1 Fedora novo — terminal, qualquer diretório

```bash
sudo dnf install git python3 python3-pip curl postgresql postgresql-server
python3 --version
psql --version
pg_dump --version
pg_restore --version
createdb --version
postgres --version
```

Python deve ser pelo menos 3.11. Para a rota validada, confira **18.x** nos binários PostgreSQL. Os pacotes fornecidos variam com a versão do Fedora; se vierem 16/17, não considere essa instalação equivalente à testada. Use um Fedora com pacotes 18 ou a alternativa Docker da seção 6.3, mantendo clientes 18. Não misture os nomes de serviço e caminhos da instalação nativa com os de repositórios externos PGDG, que não são utilizados neste roteiro.

### 4.2 Clonar a branch — terminal, pasta onde ficará o projeto

```bash
mkdir -p "$HOME/Projetos"
cd "$HOME/Projetos"
git clone --branch integracao-2019-2020-canonica \
  https://github.com/LeonardoBarrosCavalcantiNeto/Projeto-de-integracao-BD.git
cd Projeto-de-integracao-BD
git branch --show-current
git log -1 --oneline
test -f scripts/integrar_anac.py
```

**Diretório padrão dos comandos seguintes:** raiz `Projeto-de-integracao-BD`, onde estão `README.md`, `scripts/` e `sql/`. Não execute os comandos da raiz da pasta maior que contém as bases locais do desenvolvimento.

Se o GitHub informar que a branch não existe, obtenha do responsável o arquivo de entrega `integracao-2019-2020-canonica.bundle` e clone em uma pasta nova:

```bash
cd "$HOME/Projetos"
git clone --branch integracao-2019-2020-canonica \
  /caminho/recebido/integracao-2019-2020-canonica.bundle Projeto-de-integracao-BD
cd Projeto-de-integracao-BD
git branch --show-current
```

O caminho `/caminho/recebido/...` deve ser substituído pelo arquivo recebido. O bundle é gerado localmente em `.local/entrega/integracao-2019-2020-canonica.bundle`; contém o código/commits, **não os CSVs e nem o banco**. Não fixe `git checkout a65f7e4` para o modo manual: esse commit é a base anterior, sem o gerador das etapas manuais incluído nesta entrega.

### 4.3 Python — terminal, raiz do repositório

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
python scripts/integrar_anac.py --help
python scripts/integrar_anac.py prepare --help
python scripts/integrar_anac.py apply --help
```

A criação de ambientes virtuais segue a [documentação Python do Fedora](https://developer.fedoraproject.org/tech/languages/python/python-installation.html).

A integração principal e seus testes usam **somente a biblioteca padrão Python**. Não é preciso instalar Pandas/Jupyter para A ou B. Se for executar a comparação opcional ETL × ELT ou notebooks:

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` contém Pandas, NumPy, SQLAlchemy, Psycopg, python-dotenv, Jupyter e ipykernel. O executor principal **não lê `.env` e não usa `DATABASE_URL`**; use as variáveis `PG*`. A instalação via pip com internet não foi executada nesta sessão restrita.

## 5. Obtenção, organização e conferência dos CSVs

### 5.1 Diretórios — terminal, raiz do repositório

```bash
mkdir -p dados/brutos/2019 dados/brutos/2020
```

Coloque os arquivos originais nessas pastas:

```text
dados/brutos/2019/VRA_2019_01.csv ... VRA_2019_12.csv
dados/brutos/2020/VRA_2020_01.csv ... VRA_2020_12.csv
```

São **12 por pasta**, sem outros `.csv`. Os nomes têm ano com quatro dígitos e mês com dois, respeitando maiúsculas. Os CSVs não estão versionados: `.gitignore` exclui `dados/brutos/`. Também não é necessário copiar para o projeto os backups gigantes do desenvolvimento.

Use os arquivos disponibilizados pelo grupo ou baixe da fonte oficial. Os índices consultados têm os 12 arquivos com os nomes esperados: [ANAC 2019](https://siros.anac.gov.br/siros/registros/diversos/vra/2019/) e [ANAC 2020](https://siros.anac.gov.br/siros/registros/diversos/vra/2020/). Informações do conjunto: [VRA/ANAC](https://www.anac.gov.br/acesso-a-informacao/dados-abertos/areas-de-atuacao/voos-e-operacoes-aereas/voo-regular-ativo-vra).

Download opcional, em diretórios ainda vazios, na raiz do repositório:

```bash
for ano_anac in 2019 2020; do
  for mes_anac in {01..12}; do
    curl --fail --location --retry 3 \
      "https://siros.anac.gov.br/siros/registros/diversos/vra/${ano_anac}/VRA_${ano_anac}_${mes_anac}.csv" \
      --output "dados/brutos/${ano_anac}/VRA_${ano_anac}_${mes_anac}.csv" || break 2
  done
done
```

Não execute o download sobre arquivos já existentes: o comando `--output` os substitui. Falha de download exige conferir novamente os 24 arquivos; o `prepare` também verifica ausência/formato. Os índices e tamanhos foram consultados, mas os 24 downloads não foram repetidos nesta sessão. A fonte pode revisar arquivos no futuro; use o manifesto histórico para confirmar que é o mesmo conjunto.

### 5.2 Formato exigido

- Originais: `;`, UTF-8 com BOM opcional, cabeçalho obrigatório com os 20 nomes e ordem exatos.
- Não abrir e salvar no Excel/LibreOffice antes da ingestão: isso pode converter datas, zeros ou codificação.
- Número do voo e código DI começam como texto; vazios permanecem vazios na RAW.
- O primeiro nome do cabeçalho é `Sigla ICAO Empresa Aérea`; os 20 nomes estão em `ORIGINAIS` no executor. Cabeçalho diferente interrompe a preparação.
- O contador de origem é **registro lógico**, não a linha física: cabeçalho 1, primeiro registro 2. Campos entre aspas podem conter quebras internas; por isso `wc -l` não é validação suficiente.

Conferência rápida de nomes e contagem, sem alterar dados:

```bash
python - <<'PY'
import csv
from pathlib import Path
for year in (2019, 2020):
    files = sorted(Path(f'dados/brutos/{year}').glob('*.csv'))
    expected = [f'VRA_{year}_{m:02d}.csv' for m in range(1, 13)]
    assert [p.name for p in files] == expected, f'Arquivos divergentes em {year}'
    total = 0
    for path in files:
        with path.open(encoding='utf-8-sig', newline='') as source:
            reader = csv.reader(source, delimiter=';', strict=True)
            assert len(next(reader)) == 20
            count = sum(1 for _ in reader)
        print(path.name, count)
        total += count
    print('TOTAL', year, total)
PY
```

Referências para os arquivos validados: **2019 = 983414**, **2020 = 483545**. A validação completa de todos os cabeçalhos e larguras vem no `prepare`.

### 5.3 Preparar ingestão e origem — obrigatório nos dois modos

Terminal, raiz do repositório, venv ativo:

```bash
python scripts/integrar_anac.py prepare \
  --dados-2019 dados/brutos/2019 \
  --dados-2020 dados/brutos/2020
```

Também aceita caminhos externos por esses mesmos parâmetros. O comando não conecta ao PostgreSQL nem altera os originais. Ele cria:

```text
.local/integracao/bundle/
  manifesto.json
  raw_2019.csv
  raw_2020.csv
  carga.sql
  manual/01_raw.sql ... manual/11_diagnosticos.sql
```

Nos `raw_ANO.csv` **gerados**, o separador é vírgula, todos os campos ficam entre aspas e **não há cabeçalho**. Há 24 colunas, nesta ordem: `id_raw`, os 20 campos originais, `arquivo_origem`, `linha_origem`, `ano_origem`. Eles não são iguais aos CSVs originais. A carga usa `NULL '\N'`; como os textos estão entre aspas, valores literais e vazios não são confundidos com NULL.

`id_raw` reinicia por ano. A identidade compartilhada é `(ano_origem,id_raw)`; a origem alternativa é `(ano_origem,arquivo_origem,linha_origem)`. A escolha da representante de duplicatas é estável por arquivo/registro. O manifesto registra SHA-256, tamanho, contagem e registros multilinha; no modo automatizado, os hashes do bundle e dos RAW gerados são verificados antes da aplicação.

Confira o manifesto:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path
m = json.loads(Path('.local/integracao/bundle/manifesto.json').read_text())
t = Counter()
for f in m['arquivos']:
    t[f['ano_origem']] += f['registros']
print('arquivos:', len(m['arquivos']))
print('registros:', dict(t))
print('etapas manuais:', len(m['manual_sha256']))
PY
```

Esperado: 24 arquivos, `{2019: 983414, 2020: 483545}` e 11 etapas manuais. Os caminhos absolutos de importação são gerados para esta máquina; se mover o repositório/bundle, execute `prepare` novamente no novo local.

## 6. Configuração do PostgreSQL — instalação limpa

### 6.1 Servidor nativo Fedora

**Somente em computador novo, sem cluster existente**, terminal, qualquer diretório:

```bash
sudo postgresql-setup --initdb --unit postgresql
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
sudo -u postgres psql -X -d postgres
```

No prompt SQL de administração:

```sql
SELECT version();
SHOW port;
SHOW listen_addresses;
SHOW hba_file;
SHOW password_encryption;
CREATE ROLE anac_app LOGIN CREATEDB;
\password anac_app
\q
```

`\password` solicita a senha sem gravá-la em uma instrução SQL no histórico. Guarde-a para o terminal e o DataGrip. O papel tem CREATEDB porque `apply` cria um banco temporário para testar o backup; não precisa ser superusuário para a instalação limpa.

Terminal, qualquer diretório:

```bash
sudo -u postgres createdb --owner=anac_app --encoding=UTF8 anac_dw
```

Se papel ou banco já existir, **pare** e identifique a instalação; não apague nada para repetir esta seção. O roteiro nativo segue a [instalação documentada pelo Fedora](https://developer.fedoraproject.org/tech/database/postgresql/about.html).

### 6.2 Autenticação e conexão local

Localize e abra o arquivo real, no terminal (qualquer diretório):

```bash
hba_anac=$(sudo -u postgres psql -X -At -d postgres -c 'SHOW hba_file')
sudoedit "$hba_anac"
```

Acrescente **antes das regras genéricas concorrentes**:

```text
host    all    anac_app    127.0.0.1/32    scram-sha-256
```

`all` permite autenticar também nos bancos temporários de restauração e na base de manutenção. Não restringir essa regra apenas a `anac_dw`. As regras são lidas na ordem; uma regra anterior de `ident` pode impedir a senha TCP. Use o caminho retornado pelo servidor, não um caminho presumido. [Regras oficiais de pg_hba.conf](https://www.postgresql.org/docs/18/auth-pg-hba-conf.html).

Terminal:

```bash
sudo systemctl reload postgresql
```

`listen_addresses` deve permitir `localhost` e a porta deve ser a mostrada pelo servidor; na instalação limpa usual, 5432. Se alterar `listen_addresses` ou porta, é necessário reiniciar o serviço. Não abra o servidor para a rede externa para este projeto.

Terminal, raiz do repositório, mesmo shell que executará Python:

```bash
export PGHOST=127.0.0.1
export PGPORT=5432
export PGUSER=anac_app
export PGDATABASE=anac_dw
read -r -s -p 'Senha PostgreSQL: ' PGPASSWORD
printf '\n'
export PGPASSWORD
psql -X -w -v ON_ERROR_STOP=1 -c \
  'SELECT current_database(), current_user, inet_server_addr(), inet_server_port(), version();'
```

Esperado: `anac_dw`, `anac_app`, endereço local, porta escolhida e PostgreSQL 18.x. A senha digitada não aparece no comando. `-w` impede prompts ocultos nos subprocessos do executor. Ao terminar a sessão, pode usar `unset PGPASSWORD`.

Alternativa persistente: `.pgpass`, permissão 0600, com linha `127.0.0.1:5432:*:anac_app:SENHA`. O `*` no banco cobre as restaurações temporárias. Escape `:` e `\` na senha conforme o formato libpq; não versione esse arquivo. Nesse caso, não exporte `PGPASSWORD`. O DataGrip recebe a senha em sua própria configuração, não herda necessariamente o shell.

### 6.3 Alternativa separada: servidor em Docker

Esta alternativa substitui **6.1 e a edição de pg_hba nativa**. Python, Git e clientes PostgreSQL continuam no Fedora. Não inicie dois servidores na mesma porta. Use a porta **55432** para o projeto Docker.

Em um Fedora novo suportado pelo Docker, sem instalação Docker concorrente, terminal:

```bash
sudo dnf install dnf-plugins-core
sudo dnf config-manager addrepo --from-repofile \
  https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
```

Se houver Docker/Podman já instalado, examine a [documentação oficial de instalação no Fedora](https://docs.docker.com/engine/install/fedora/) antes de trocar pacotes. Esta tarefa não executou instalação de pacotes nem Docker.

Terminal, qualquer diretório, defina as credenciais sem gravar a senha no comando:

```bash
export POSTGRES_USER=anac_app POSTGRES_DB=anac_dw
read -r -s -p 'Senha do novo PostgreSQL Docker: ' POSTGRES_PASSWORD
printf '\n'
export POSTGRES_PASSWORD
sudo docker volume create anac_projeto_pg18
sudo --preserve-env=POSTGRES_USER,POSTGRES_DB,POSTGRES_PASSWORD docker run -d \
  --name anac-projeto-pg18 \
  -p 127.0.0.1:55432:5432 \
  -e POSTGRES_USER -e POSTGRES_DB -e POSTGRES_PASSWORD \
  -v anac_projeto_pg18:/var/lib/postgresql \
  postgres:18
sudo docker logs anac-projeto-pg18
sudo docker exec anac-projeto-pg18 pg_isready -U anac_app -d anac_dw
```

Aguarde `accepting connections`. O volume de PostgreSQL **18** fica em `/var/lib/postgresql`, conforme a [imagem oficial](https://hub.docker.com/_/postgres); não use por engano a montagem `/var/lib/postgresql/data` do padrão de versões anteriores. As variáveis POSTGRES_* inicializam apenas um volume vazio. Alterá-las depois não troca automaticamente usuário/senha/banco de um volume já criado. O usuário de inicialização da imagem é administrador do cluster: utilize essa instância dedicada ao projeto.

No terminal do Fedora, raiz do repositório:

```bash
export PGHOST=127.0.0.1 PGPORT=55432 PGUSER=anac_app PGDATABASE=anac_dw
export PGPASSWORD="$POSTGRES_PASSWORD"
unset POSTGRES_PASSWORD
psql --version
pg_dump --version
psql -X -w -c 'SELECT current_database(), current_user, version();'
```

Clientes devem ser 18.x, assim como o servidor. A imagem `postgres:18` acompanha atualizações secundárias; não se afirma que ela reproduza exatamente 18.6. Os comandos Docker foram conferidos na documentação, mas não executados nesta sessão. Depois desta conexão, A e B usam os mesmos comandos do Fedora: os arquivos são lidos pelo `psql` **no host**, sem necessidade de montar CSVs no container. No DataGrip, use porta 55432. Não use `docker rm -v` nem apague o volume para “reiniciar” uma execução.

## 7. Configuração do DataGrip

PostgreSQL é o servidor que mantém os dados; DataGrip é apenas o cliente. Abrir o DataGrip não instala nem inicia o servidor e não cria automaticamente `anac_dw`.

1. Abra **File → New → Data Source → PostgreSQL** (ou `+` no Database Explorer).
2. Preencha host `127.0.0.1`, porta `5432` nativa ou `55432` Docker, banco `anac_dw`, usuário `anac_app` e a senha criada.
3. Se solicitado, use **Download missing driver files** para instalar o JDBC PostgreSQL.
4. Clique **Test Connection** e depois **Apply/OK**. Antes de importar, execute o SELECT de identificação da seção 6.2 e confira a instância.
5. Na seleção **Schemas** da fonte, marque `raw`, `staging` e `dw` quando existirem. Use **Refresh/Synchronize** depois das cargas; antes de criá-los, é normal que não apareçam.
6. Para um console/arquivo de consulta, selecione a fonte e use **Jump to Query Console / New Query File** ou F4, conforme a versão. Vincule o arquivo à fonte `anac_dw` e dialeto PostgreSQL.
7. Abra um `.sql` pelo editor ou **SQL Scripts → Run SQL Script…** na fonte. Execute **o arquivo inteiro**, não só a instrução em que o cursor está. Confirme a conexão de destino antes de Run.
8. Os SELECTs apresentam resultados em abas/grades. Os blocos DO aprovados normalmente não retornam linhas: verifique ausência de erros e as tabelas de resultados seguintes.

No modo B, use gerenciamento **Auto** de transações do DataGrip e respeite o `BEGIN/COMMIT` já presente nos arquivos gerados. Não acrescente um BEGIN externo que se estenda entre vários arquivos. Configure execução para parar em erro, quando essa opção estiver disponível. Em erro, interrompa a etapa e execute `ROLLBACK;` na mesma sessão antes de tentar de novo. Não continue até o fim do roteiro após um erro.

Referências: [conexão PostgreSQL no DataGrip](https://www.jetbrains.com/help/datagrip/postgresql.html) e [execução de arquivos SQL](https://www.jetbrains.com/help/datagrip/run-sql-files.html). Os menus foram conferidos na documentação; os cliques na interface não foram testados nesta sessão.

## 8. Modo A — execução automatizada recomendada

Pré-requisitos: banco criado e conexão testada (6), CSVs preparados (5.3), shell com PG* e senha válida. Na instalação limpa, os schemas `raw`, `staging`, `dw` ainda não devem existir.

Terminal, raiz do repositório:

```bash
python scripts/integrar_anac.py apply \
  --bundle .local/integracao/bundle \
  --backup-dir backups
```

O comando faz, nesta ordem:

1. Verifica hashes do SQL e dos RAW canônicos; confere que o banco é `anac_dw` ou começa com `anac_teste_`.
2. Faz `pg_dump -Fc`, verifica o catálogo e restaura o backup em `anac_teste_restore_TIMESTAMP` usando `createdb`/`pg_restore --exit-on-error`. Mesmo instalação vazia passa por essa proteção. Precisa de CREATEDB e autenticação nos bancos temporários.
3. Monta `.local/integracao/bundle/aplicar.sql`. Se encontrar schemas antigos, renomeia para `raw_antes_TIMESTAMP`, `staging_antes_TIMESTAMP`, `dw_antes_TIMESTAMP`, sem apagá-los.
4. Em uma transação: cria schemas/tabelas RAW, importa os canônicos com `\copy`, transforma os dois anos, consolida auditorias/STAGING, cria DW, resolve descrições, carrega dimensões/fato, valida e aplica restrições.
5. Se houver RAW anterior reconhecido, compara os 20 campos e multiplicidades com os CSVs; divergência cancela o commit. NULL histórico é comparado a vazio apenas nessa conciliação.
6. Confirma a transação; grava contagens e estado no JSON do backup, validações em `validacao.txt` e análises em `analises.txt` dentro do bundle.
7. Repete a carga dimensional/fato e valida novamente para comprovar que não acrescentou registros duplicados.

Não execute antes os SQLs de criação históricos: o executor cria as estruturas. Não é necessário importar nada pelo DataGrip nem executar um tratamento por ano manualmente neste modo. O professor pode acompanhar as tabelas e executar as análises pelo DataGrip ao final.

O JSON do backup inclui caminho, hash e banco restaurado. As bases temporárias e schemas antigos ficam preservados; sua remoção não faz parte deste roteiro. O processo não depende de rodar o servidor como superusuário de sistema, mas o papel PostgreSQL precisa ser dono dos objetos que pretende migrar.

**Verificação obrigatória:** não considerar apenas a mensagem `integracao_confirmada` uma certificação final se houver erro posterior; confira também o término bem-sucedido do comando e os SELECTs da seção 11. O código registra o commit antes das verificações pós-carga; uma falha posterior não desfaz uma carga já confirmada.

## 9. Modo B — execução por etapas no DataGrip

### 9.1 Escopo realmente disponível

A partir desta entrega, `prepare` gera onze arquivos em `.local/integracao/bundle/manual/`. SQL puro vai para o DataGrip; `02_importar_raw.psql` é executado no terminal. **Não abra `carga.sql` nem `aplicar.sql` como se fossem SQL JDBC:** contêm `\copy`.

A pasta `.local` é oculta: habilite a exibição de arquivos ocultos no navegador do editor ou abra o arquivo pelo caminho completo. No terminal, `realpath .local/integracao/bundle/manual` mostra esse caminho.

Antes de iniciar, confira os arquivos preparados, no terminal da raiz:

```bash
python scripts/validar_guia.py --bundle .local/integracao/bundle
```

O resultado deve ter `erros: []`, incluindo hashes conferidos. Não edite os CSVs canônicos nem os SQLs gerados entre essa conferência e a execução.

Use um banco **novo**. Se já concluiu A em `anac_dw`, crie outro banco para demonstrar B, sem apagar o primeiro:

```bash
# Terminal, PG* autenticado; anac_app tem CREATEDB.
createdb -w --owner=anac_app --encoding=UTF8 anac_teste_apresentacao
export PGDATABASE=anac_teste_apresentacao
psql -X -w -c 'SELECT current_database(), current_user;'
```

Crie outra fonte DataGrip apontando para esse nome. Se B é sua única instalação, use diretamente o `anac_dw` vazio preparado na seção 6. Não rode `apply` nesse banco durante a sequência B.

### 9.2 Sequência de execução

Os caminhos completos e dependências estão na seção 10. Execute os arquivos inteiros em ordem:

1. **DataGrip:** `01_raw.sql`. Cria os três schemas, manifesto no banco e tabelas RAW ainda vazias. Depois de COMMIT, o terminal passa a enxergá-las.
2. **Terminal, raiz do repositório e PGDATABASE igual ao DataGrip:**

   ```bash
   psql -X -w -v ON_ERROR_STOP=1 \
     -f .local/integracao/bundle/manual/02_importar_raw.psql
   ```

   Importa os dois arquivos preparados pelo Python. Há uma guarda de RAW vazia: repetição é bloqueada. A importação é uma transação; erro deve impedir carga parcial. Os arquivos gerados não têm cabeçalho, usam vírgula e já incluem origem.
3. **DataGrip:** `03_transformar_2019.sql`, depois `04_transformar_2020.sql`. Classificam duplicatas brutas, convertem dados, registram rejeições/anomalias e geram tratada anual e resumo de qualidade.
4. **DataGrip:** `05_consolidar_staging.sql`. Une as saídas anuais, cria PKs/FKs e registro compartilhado das ocorrências.
5. **DataGrip:** `06_criar_dw.sql`. Cria as sete dimensões e fato com a chave composta corrigida.
6. **DataGrip:** `07_dimensoes.sql`. Registra resoluções SBEG/SWHP e cria os cadastros/views que bloqueiam conflitos. Ainda não insere todos os membros nas dimensões.
7. **DataGrip:** `08_carga_dw.sql`. Alimenta as sete dimensões e a fato com ON CONFLICT.
8. **DataGrip:** `09_validar_contrato.sql`. Valida conteúdo, origem e métricas, testa conversões e adiciona restrições.
9. **DataGrip:** `10_analises.sql`, depois `11_diagnosticos.sql`.

A importação direta dos CSVs **originais** pelo assistente do DataGrip não é o procedimento suportado: ela não reproduz automaticamente os metadados de ocorrência. Também não se exige configurar um importador gráfico para interpretar os CSVs canônicos: o `psql` já tem a especificação exata e evita ambiguidades entre vazios e NULL.

O modo B não faz backup nem migração automática; seus scripts iniciais recusam schemas existentes em vez de limpá-los. Ele é destinado a instalação limpa ou banco de apresentação. Transformações anuais contêm DROP das suas tabelas intermediárias, herdado do template; **não devem ser repetidas depois da consolidação**, quando há dependências/copias compartilhadas.

## 10. Ordem exata dos arquivos SQL

Prefixo da sequência B: `.local/integracao/bundle/manual/`. Cada `.sql` de criação, transformação e carga tem BEGIN/COMMIT próprio. Os arquivos 10/11 são consultas. Todos os arquivos abaixo são **gerados por prepare**, e não arquivos que se espera encontrar no clone.

| Etapa/arquivo | Onde | Pré-requisito e resultado esperado | Reexecutar? |
|---|---|---|---|
| `01_raw.sql` | DataGrip | Banco vazio; cria schemas, `raw.inventario` com 24 arquivos e RAW com 0 registros | Não; schema existente provoca erro/rollback |
| `02_importar_raw.psql` | Terminal psql | 01 confirmado + arquivos canônicos no caminho gerado; RAW 983414/483545 | Não; guarda bloqueia RAW preenchida |
| `03_transformar_2019.sql` | DataGrip | RAW 2019 importada; 470 excedentes, 18 rejeitados, 982926 tratados | Não repetir após consolidar |
| `04_transformar_2020.sql` | DataGrip | RAW 2020 importada; 124 excedentes, 1512 rejeitados, 481909 tratados | Não repetir após consolidar |
| `05_consolidar_staging.sql` | DataGrip | 03/04; três tabelas compartilhadas, anomalias, resumo e `raw.ocorrencias` | Não; cria objetos |
| `06_criar_dw.sql` | DataGrip | 05; sete dimensões vazias + fato com UNIQUE por ano/ID e origem | Não; não é migração de DDL existente |
| `07_dimensoes.sql` | DataGrip | 05/06; resoluções, cadastros e checagem de conflitos | Não; cria tabela/views |
| `08_carga_dw.sql` | DataGrip | 07; membros dimensionais e fato com 1464835 registros | Sim; mesmas entradas, ON CONFLICT |
| `09_validar_contrato.sql` | DataGrip | 08; asserções, testes de funções e restrições aplicados | Não repetir o arquivo completo: recria CHECKs; use `sql/integracao/04_validar.sql` para validar novamente |
| `10_analises.sql` | DataGrip | 09; SELECTs analíticos | Sim, somente leitura |
| `11_diagnosticos.sql` | DataGrip | STAGING consolidada; diagnósticos de auditoria | Sim, somente leitura |

Verificação por etapa: após 01, `SELECT count(*) FROM raw.voos_2019` retorna 0; após 02, as contagens brutas; após 03/04, `SELECT * FROM staging.resumo_qualidade_2019` e `_2020`; após 05, `SELECT * FROM staging.resumo_qualidade`; após 06, `SELECT count(*) FROM dw.fato_voo` retorna 0; após 07, `SELECT * FROM staging.conflitos_dimensoes` retorna zero linhas; após 08/09, as consultas da seção 11.

Os SQLs versionados 02/03/04/06/08 são embutidos/adaptados na geração. O DDL do DW histórico não deve ser executado isoladamente como substituto de `06_criar_dw.sql`.

## 11. Verificação e testes

### 11.1 Contagens de referência — DataGrip ou terminal psql

```sql
SELECT 2019 ano_origem, count(*) brutos FROM raw.voos_2019
UNION ALL
SELECT 2020, count(*) FROM raw.voos_2020;

SELECT ano_origem, bruta, duplicatas_excedentes, rejeicoes, tratada
FROM staging.resumo_qualidade ORDER BY ano_origem;

SELECT ano_origem, count(*) fatos FROM dw.fato_voo GROUP BY 1 ORDER BY 1;
SELECT count(*) total_fato FROM dw.fato_voo;
```

| Ano | RAW | Duplicatas excedentes | Rejeitados representantes | Tratada/fato |
|---|---:|---:|---:|---:|
| 2019 | 983414 | 470 | 18 | 982926 |
| 2020 | 483545 | 124 | 1512 | 481909 |
| TOTAL | 1466959 | 594 | 1530 | **1464835** |

Esses valores foram medidos nos arquivos do desenvolvimento e são referência para o mesmo conjunto, não metas impostas à transformação. Se os arquivos da ANAC mudaram, confronte os SHA-256 com `resultados/validacoes/integracao_2019_2020/manifesto_fontes.json` antes de atribuir diferença ao código.

### 11.2 Rastreabilidade, duplicação e NULL — DataGrip

```sql
SELECT ano_origem, count(*) sem_origem
FROM raw.ocorrencias
WHERE arquivo_origem IS NULL OR linha_origem IS NULL OR linha_origem < 2
GROUP BY 1;

SELECT ano_origem, id_raw, count(*)
FROM dw.fato_voo GROUP BY 1,2 HAVING count(*) > 1;

SELECT ano_origem, arquivo_origem, linha_origem, count(*)
FROM staging.vra_tratada GROUP BY 1,2,3 HAVING count(*) > 1;

SELECT ano_origem,
 count(*) FILTER (WHERE partida_real IS NULL) partidas_sem_real,
 count(*) FILTER (WHERE partida_real IS NULL AND atraso_partida_min IS NOT NULL) nulos_incorretos,
 count(*) FILTER (WHERE chegada_real IS NULL AND atraso_chegada_min IS NOT NULL) nulos_chegada_incorretos
FROM dw.fato_voo GROUP BY 1 ORDER BY 1;
```

As três primeiras consultas retornam **zero linhas**. A última retorna 17982/21845 partidas sem horário real e zero nulos incorretos nos dois anos. Antecipações têm diferença negativa e atraso zero; ausência de realizado não significa voo pontual nem cancelado.

```sql
SELECT * FROM staging.conflitos_dimensoes;
SELECT conrelid::regclass tabela, conname, convalidated
FROM pg_constraint
WHERE connamespace = 'dw'::regnamespace AND contype = 'f'
ORDER BY 1,2;
```

Conflitos: zero linhas. São dez FKs na fato, todas `convalidated=true`: nove papéis dimensionais e uma para a tratada. NOT NULL impede ausência das relações obrigatórias; FKs impedem órfãos. Para verificar também conteúdo dos relacionamentos e das medidas, execute o **arquivo inteiro** `sql/integracao/04_validar.sql` no DataGrip ou:

```bash
psql -X -w -v ON_ERROR_STOP=1 -f sql/integracao/04_validar.sql
psql -X -w -v ON_ERROR_STOP=1 -f sql/integracao/07_diagnosticos.sql
```

O bloco DO não deve lançar exceção. Diagnóstico de duplicatas: 444 grupos/914 linhas envolvidas em 2019, 124 grupos/248 linhas em 2020; interseção excedentes/obrigatórios inválidos = 0 em ambos. Auditoria opcional: 25 registros de assentos negativos de 2019 convertidos para NULL; em 2020, zero anomalias opcionais.

### 11.3 Testes locais e teste limpo sem serviço

Terminal, raiz, usuário comum:

```bash
python -m unittest discover -s tests
python scripts/validar_guia.py --bundle .local/integracao/bundle
```

O validador do guia confere referências locais, hashes do bundle/RAW/etapas manuais, os onze arquivos gerados e a sintaxe dos blocos Bash/Python, sem executar comandos administrativos. Execute-o depois de `prepare`.

O teste SQL precisa de `initdb` e `postgres` no PATH e não pode ser executado como root. Na ausência desses binários, esse teste é **SKIPPED**, não uma certificação de PostgreSQL. A execução esperada com binários locais é `Ran 4 tests ... OK`; o teste SQL agora executa o fluxo automatizado e o manual em clusters sintéticos separados e compara seus resultados.

Para reconstrução integral em um cluster novo, sem tocar no servidor configurado em PG*:

```bash
python scripts/testar_integracao_isolada.py \
  --bundle .local/integracao/bundle \
  --cluster .local/teste_novo_automatico
```

Ou para verificar a sequência manual, cada arquivo separado:

```bash
python scripts/testar_integracao_isolada.py --manual \
  --bundle .local/integracao/bundle \
  --cluster .local/teste_novo_manual
```

O diretório do cluster deve **não existir**. Essa modalidade usa PostgreSQL single-user e COPY servidor, substituindo `\copy` somente no executor de testes. O banco é `postgres` dentro do cluster novo, e não `anac_dw` do DataGrip. Não certifica a autenticação TCP, os cliques da interface ou pg_dump/pg_restore contra um serviço. É uma opção de teste de SQL, não substitui a configuração do DataGrip nas seções anteriores.

### 11.4 Comparação opcional ETL × ELT

A integração já tem evidências anteriores de equivalência por conteúdo. Para recalcular em outra máquina, após instalar `requirements.txt`, execute em sequência para reduzir memória:

```bash
python scripts/comparar_integracao.py --ano 2019 \
  --dados dados/brutos/2019 --etl-output .local/integracao/etl_2019
python scripts/comparar_integracao.py --ano 2020 \
  --dados dados/brutos/2020 --etl-output .local/integracao/etl_2020
psql -X -w -v ON_ERROR_STOP=1 -f .local/integracao/bundle/comparar_2019.sql
psql -X -w -v ON_ERROR_STOP=1 -f .local/integracao/bundle/comparar_2020.sql
```

Esses SQLs de comparação também contêm `\copy`: **terminal**, não DataGrip. Criam tabelas de comparação em STAGING; use um banco de teste já carregado e com backup. Não são reexecutáveis sem preparar outro banco ou avaliar as tabelas existentes. Esperado: zero divergências de conteúdo, duplicatas e rejeições para o mesmo conjunto. Não alteram a fato. Não são obrigatórios para reconstruir o DW.

## 12. Consultas analíticas e demonstração

No DataGrip, execute `sql/integracao/05_analises.sql`, ou o gerado `manual/10_analises.sql`. No terminal:

```bash
psql -X -w -v ON_ERROR_STOP=1 -f sql/integracao/05_analises.sql
```

As consultas mostram voos por ano/companhia, atraso médio, percentual de partidas atrasadas, movimentação de aeroportos, distribuição mensal e auditorias. Critério declarado: **atraso positivo**, entre registros com horário calculável; desconhecidos aparecem separadamente. Não há conversão de fusos.

Referência medida: 30,08% de partidas atrasadas em 2019 e 27,68% em 2020; atraso médio não negativo 9,80/9,76 minutos, incluindo atípicos. SBGR teve 427351 movimentos somando origem/destino. Não interpretar isso como passageiros.

Sugestão de apresentação:

1. Mostrar `raw.inventario` e uma origem com arquivo/registro.
2. Mostrar `staging.resumo_qualidade` e as tabelas de auditoria.
3. Mostrar a fato e suas FKs, explicando `(ano_origem,id_raw)`.
4. Executar contagem por ano e a análise de atrasos, destacando NULL.
5. Reexecutar somente a carga idempotente e repetir a contagem.

Para demonstrar a construção ao vivo, prepare os CSVs e o banco de apresentação antes da aula; depois percorra os arquivos 01–11. Transformações do conjunto completo podem levar vários minutos. Não dependa de baixar 24 arquivos ou instalar drivers durante a apresentação.

## 13. Reexecução e idempotência

**Reexecutar carga dimensional/fato** com a mesma STAGING:

```bash
psql -X -w -v ON_ERROR_STOP=1 --single-transaction \
  -f sql/integracao/03_carga_dw.sql \
  -f sql/integracao/04_validar.sql
```

DataGrip: repetir `manual/08_carga_dw.sql` e depois `sql/integracao/04_validar.sql`. Resultado esperado: 982926/481909 fatos, total 1464835, nenhuma chave duplicada. Identidades podem apresentar lacunas após ON CONFLICT; isso não indica perda de registros.

**Reconstruir tudo**: no modo A, `apply` faz novo backup e preserva os schemas anteriores, reconstruindo a partir do bundle; isso pode mudar SKs, mas mantém o conteúdo natural. No modo B, use um novo banco vazio. Não repita a importação para tentar corrigir uma etapa posterior; não use DELETE/TRUNCATE/DROP sobre o banco existente como atalho.

`prepare` pode ser repetido para regerar arquivos locais, mas substitui o bundle de saída: não o regenere enquanto uma carga estiver lendo os arquivos. Se já tiver saídas importantes, use `--output .local/outro_bundle` e passe esse mesmo caminho para `apply --bundle` ou para o executor de testes. A ordem dos dados deve continuar estável.

## 14. Migração, backup e restauração — banco já existente

### 14.1 Identificar a instância antes de qualquer alteração

**Não executar `initdb`, recriar usuário/banco ou editar o serviço presumindo que é o mesmo servidor.** Use a conexão que funciona no DataGrip e consulte:

```sql
SELECT current_database(), current_user, inet_server_addr(), inet_server_port(), version();
SELECT nspname FROM pg_namespace WHERE nspname IN ('raw','staging','dw');
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_schema IN ('raw','staging','dw') ORDER BY 1,2;
```

Com conta administrativa, `SHOW data_directory; SHOW port;` ajuda a identificar instalação. Uma conexão Unix pode mostrar endereço/porta de servidor nulos nas funções inet; compare também a configuração da fonte DataGrip. Se estiver em Docker, a porta interna retornada pelo SQL normalmente é 5432, e a porta do host pode ser outra.

Terminal, somente leitura administrativa:

```bash
sudo systemctl status postgresql --no-pager
sudo docker ps --format '{{.Names}} {{.Image}} {{.Ports}}'
```

Se não usa Docker, o segundo comando não se aplica. Para um container identificado, `sudo docker port NOME_REAL` mostra o mapeamento. Não use `docker inspect` completo em relatórios, pois pode revelar variáveis com senha. Copie host/porta/usuário **da instância identificada**, não dos exemplos de instalação limpa.

Configure PG* no terminal como em 6.2, usando o dono/administrador dos objetos existentes. Faça um SELECT de identificação pelo `psql` e confronte com o DataGrip. Se não conseguir conectar, pare: não é seguro migrar uma instância diferente para “resolver” a conexão.

### 14.2 Backup preliminar e teste de restauração

Pare outras escritas do grupo no banco durante a manutenção. O advisory lock do executor coordena apenas execuções dele, não clientes DataGrip externos. Não envie dumps completos para o GitHub.

Terminal, raiz do repositório, PG* já apontando para o banco correto e usuário com permissões:

```bash
umask 077
mkdir -p backups
stamp_anac=$(date -u +%Y%m%d_%H%M%S)
dump_anac="$PWD/backups/anac_dw_antes_manual_${stamp_anac}.dump"
pg_dump -w --format=custom --dbname="$PGDATABASE" --file="$dump_anac"
test -s "$dump_anac"
pg_restore --list "$dump_anac" > "${dump_anac}.lista.txt"
sha256sum "$dump_anac" > "${dump_anac}.sha256"
restore_anac="anac_teste_restore_manual_${stamp_anac}"
createdb -w "$restore_anac"
pg_restore -w --exit-on-error --dbname="$restore_anac" "$dump_anac"
psql -X -w -v ON_ERROR_STOP=1 --dbname="$restore_anac" \
  -c 'SELECT count(*) FROM raw.voos_2019;'
```

Execute uma linha por vez e **pare ao primeiro erro**. O `--list` verifica se o catálogo é legível; só a restauração efetiva demonstra que o dump pode ser usado. Consulte também os objetos e contagens de 2020/DW que já existiam no original. Não execute as validações do modelo novo no banco histórico como se ele já tivesse migrado. O restore precisa dos papéis e privilégios referenciados pelo dump: use a conta administrativa adequada, não tente contornar erros ignorando objetos.

O dump de banco não inclui todos os objetos globais do cluster, como criação de roles. A restauração testada no mesmo cluster reutiliza os papéis existentes; para outra máquina, recrie os roles/proprietários necessários com administração local antes da restauração. Não publique dumps globais de credenciais.

### 14.3 Migrar com o executor

Prepare um bundle dos CSVs originais como em 5.3. Com a conexão ainda conferida:

```bash
python scripts/integrar_anac.py apply --bundle .local/integracao/bundle --backup-dir backups
```

O executor faz **outro backup e outra restauração obrigatórios**, independentemente do backup preliminar. Mantém schemas anteriores com sufixo UTC incluindo microssegundos, e registra o sufixo exato no JSON; não tente adivinhar o nome.

Após sucesso, no DataGrip:

```sql
SELECT * FROM staging.reconciliacao_historica ORDER BY ano_origem;
SELECT nspname FROM pg_namespace
WHERE nspname LIKE 'raw_antes_%' OR nspname LIKE 'staging_antes_%' OR nspname LIKE 'dw_antes_%'
ORDER BY 1;
```

Para cada RAW histórico reconhecido, `diferencas_multiconjunto` deve ser 0. Em instalação limpa, a tabela existe, mas pode ter zero linhas. As contagens antigas devem corresponder às medidas preliminares. Use os nomes **reais** registrados no JSON para consultar os schemas anteriores; compare os SELECTs da seção 11 no novo DW. A conciliação não inventa correspondência de ID histórico com linhas de arquivo idênticas.

### 14.4 Falha e recuperação

- Erro antes do commit da migração: a transação do `psql` é revertida; schemas anteriores permanecem com os nomes originais. Inspecione antes de qualquer nova execução.
- Erro após commit em validação/análise/reexecução: não presuma rollback da carga inteira. Verifique o estado e preserve o backup.
- Em ambos os casos, o caminho de recuperação preferido é **restaurar em outro banco**, não sobrescrever `anac_dw`:

```bash
# Use o caminho real do dump e um nome de banco ainda inexistente.
createdb -w anac_teste_recuperacao
pg_restore -w --exit-on-error \
  --dbname=anac_teste_recuperacao /caminho/real/backup.dump
```

Abra esse banco em uma fonte DataGrip separada e confira os dados. Não usar `--clean` no banco principal para testar recuperação. A troca definitiva da conexão deve ocorrer somente depois dessa conferência.

O backup físico de referência do desenvolvimento é descrito em [integração 2019/2020](integracao_2019_2020.md) e [backup_isolado.json](../resultados/validacoes/integracao_2019_2020/backup_isolado.json). Ele é local, cerca de 851 MiB, PostgreSQL 18, banco `postgres`, não vem no clone e **não é backup do `anac_dw` original**. Não é necessário para instalar do zero.

## 15. Solução de erros comuns

| Mensagem/sintoma | Causa provável e ação |
|---|---|
| Branch remota não encontrada | Commits locais ainda não publicados; obtenha o Git bundle. Não execute scripts de outra branch supondo equivalência |
| `python: command not found` | Ative `.venv`; antes disso use `python3` |
| `file_digest` ausente | Python anterior a 3.11; atualize o ambiente |
| `psql/pg_dump/createdb` não encontrado | Instale os clientes e confira PATH |
| `connection refused` | Serviço parado, porta errada ou container ainda iniciando; confira status/logs e o mapeamento |
| `Operation not permitted`/Docker permission denied | Restrição da sessão ou acesso ao daemon; use terminal autorizado. Não representa erro no SQL nem autoriza trocar de instância |
| `Ident authentication failed` | Regra HBA anterior à regra scram; confira caminho, ordem e recarregue |
| `no password supplied` | O executor usa `-w`; configure PGPASSWORD ou `.pgpass` com permissão e wildcard de banco adequados |
| `permission denied to create database` | Papel sem CREATEDB; necessário para testar restauração. Ajuste o papel correto com administrador |
| `must be owner`/restore falha em owners | Migração com usuário sem direitos sobre objetos históricos; usar dono/administrador e testar backup |
| `server version mismatch` | Clientes PostgreSQL de versão principal incompatível; alinhe antes de migrar |
| Mês/cabeçalho divergente | Nomes, número de arquivos, codificação ou layout incorretos; obtenha os originais. Não renomear colunas à força |
| `schema raw already exists` em 01 | Banco não está vazio ou A já foi executado; use banco novo para B |
| `syntax error at or near "\\"` | Arquivo psql aberto no DataGrip; execute `02_importar_raw.psql`, `carga.sql` e comparadores no terminal apropriado |
| Arquivo CSV canônico não encontrado | Bundle movido ou gerado em outro computador; regerar com `prepare` e os caminhos atuais |
| RAW não vazia em 02 | Importação repetida; não repetir. Verifique contagens e prossiga na etapa correta |
| `current transaction is aborted` | Houve erro SQL; interrompa e rode ROLLBACK na mesma sessão; corrija antes de continuar |
| Conflitos dimensionais | Inspecione `staging.conflitos_dimensoes`; não escolher arbitrariamente uma descrição |
| Conciliação histórica divergente | CSVs não correspondem ao RAW anterior, ou formato histórico não reconhecido; migração cancela. Preserve evidências e compare fontes |
| Contagem distinta da referência | Confira primeiro manifesto/hashes, arquivo faltante ou repetido, base/ano e execução completa |
| Teste diz cluster já existe | Escolha outro `--cluster`; não apague o cluster existente como atalho |
| Schemas não aparecem no DataGrip | Selecione na aba Schemas e atualize após COMMIT; confira também banco/porta |
| Falta de espaço/demora | Há várias camadas e backup/restauração; confira disco/memória e aguarde o término, sem iniciar carga concorrente |

## 16. Checklist final e alcance da validação deste guia

- [ ] Código da branch correta, incluindo geração de `manual/`.
- [ ] PostgreSQL e clientes da versão principal 18 identificados.
- [ ] Banco/usuário criados e conexão terminal/DataGrip conferida.
- [ ] 24 originais no formato esperado, manifesto produzido.
- [ ] Escolhido apenas A ou B para cada banco novo.
- [ ] RAW 983414/483545, com origem completa.
- [ ] Auditorias 470/124 excedentes e 18/1512 rejeitados.
- [ ] Tratada/fato 982926/481909; total 1464835.
- [ ] Sem conflitos dimensionais, FKs validadas e asserções aprovadas.
- [ ] Horários reais ausentes com atrasos NULL, sem substituir por zero.
- [ ] Reexecução da carga sem novos fatos.
- [ ] Consultas analíticas executadas com denominadores explicados.
- [ ] Backup recuperável e restauração testada, quando usando apply/migração.
- [ ] Banco original preservado; 2021 não processado.

A validação executada para esta entrega está em [validacao_guia_execucao.md](../relatorio/validacao_guia_execucao.md). Ela distingue os testes PostgreSQL realmente executados das instruções conferidas na documentação externa. Instalação por dnf, systemd/sudo, Docker, downloads completos, instalação pip e interface gráfica dependem de ações locais e não foram executados nesta sessão restrita. A rota SQL pode ser validada por single-user mesmo quando sockets estão bloqueados; isso não prova que a autenticação ou o backup lógico via serviço já funcionem na máquina do leitor.
