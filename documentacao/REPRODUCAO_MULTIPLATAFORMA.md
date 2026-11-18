# Reprodução acadêmica pelo terminal

Execute os comandos na raiz do projeto. Os dois DWs são schemas do mesmo banco PostgreSQL 18. O ETL trata os CSVs com Python/Pandas e o ELT trata o RAW em SQL. Consulte o [modelo e o fluxo final](INTEGRACAO_FINAL.md) para detalhes.

Para clonar, siga o comando do [README](../README.md#preparar-e-executar) após a publicação da branch da entrega. Se recebeu um ZIP, abra a pasta que contém `README.md`. Um ZIP gerado por `git archive` inclui os arquivos do commit selecionado. Alterações locais pendentes precisam ser registradas para constar no clone ou no ZIP.

## 1. Instalar ferramentas e criar o ambiente Python

Use Python 3.11 ou superior e servidor e clientes da série 18. Confira qual instalação atende a porta escolhida, principalmente quando há mais de uma versão instalada. [Instaladores e pacotes PostgreSQL](https://www.postgresql.org/download/)

### Windows (PowerShell)

Instale o Python e o PostgreSQL 18 com as ferramentas de linha de comando selecionadas. Use o serviço criado pelo instalador e anote a porta e a senha da conta administrativa. Se necessário, inicie o serviço pelo aplicativo Serviços do Windows. Ajuste o caminho de instalação abaixo.

```powershell
$env:Path = 'C:\Program Files\PostgreSQL\18\bin;' + $env:Path
$env:PYTHONUTF8 = '1'
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Se a política do PowerShell impedir a ativação, use `& .\.venv\Scripts\python.exe` em cada comando que começa com `python`. A ativação é apenas um atalho de PATH.

### macOS (zsh ou Bash)

Com Homebrew instalado, use a fórmula abaixo. Se a fórmula estiver indisponível para sua versão ou arquitetura, use um instalador PostgreSQL 18 da página oficial e coloque seu diretório `bin` no PATH. A conta administrativa inicial do cluster Homebrew costuma ser o usuário que o criou. [Fórmula PostgreSQL 18](https://formulae.brew.sh/formula/postgresql@18)

```bash
brew install python@3.13 postgresql@18
export PATH="$(brew --prefix postgresql@18)/bin:$PATH"
brew services start postgresql@18
export PYTHONUTF8=1
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Linux (Bash)

Instale o servidor e os clientes PostgreSQL 18 usando o pacote da sua distribuição. No Fedora com PostgreSQL 18 nos repositórios nativos, use `sudo dnf install postgresql postgresql-server python3 python3-pip`. Em Debian/Ubuntu com o repositório adequado, os pacotes são `postgresql-18`, `postgresql-client-18`, `python3` e `python3-venv`. Siga o procedimento do pacote para iniciar o serviço. No Fedora nativo, `sudo systemctl start postgresql`. A inicialização por `sudo postgresql-setup --initdb` é apenas para uma instalação sem cluster. Em distribuições que usam `peer` para administração local, abra a primeira sessão administrativa com `sudo -u postgres psql -X -d postgres`.

```bash
export PYTHONUTF8=1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Nos três sistemas, confira `python --version`, `psql --version`, `createdb --version`, `pg_dump --version` e `pg_restore --version`. Para testes single-user, confira também `postgres --version` e `initdb --version` e coloque os binários 18 no PATH.

## 2. Obter e conferir os 36 CSVs

```text
python scripts/baixar_vra.py
python scripts/baixar_vra.py --apenas-verificar
```

O script usa os endereços HTTPS mensais do SIROS e organiza os arquivos em `dados/brutos/{2019,2020,2021}/VRA_ANO_MM.csv`. A pasta padrão e os artefatos de carga são ignorados pelo Git. O [manifesto de referência](../dados/manifesto_vra.json) fixa os tamanhos e SHA-256 das fontes da versão validada. O download é gravado em arquivo temporário e publicado após conferir tamanho e hash. Uma nova execução reutiliza arquivos íntegros. [Índice de 2019](https://siros.anac.gov.br/siros/registros/diversos/vra/2019/), [índice de 2020](https://siros.anac.gov.br/siros/registros/diversos/vra/2020/), [índice de 2021](https://siros.anac.gov.br/siros/registros/diversos/vra/2021/)

Se a ANAC republicar um mês com bytes diferentes ou houver divergência em um arquivo local, o script indica o arquivo e interrompe a execução, preservando o original local. Obtenha a cópia correspondente à versão validada com a equipe e rode `--apenas-verificar` antes de reproduzir a carga. Para usar outra pasta, mantenha a estrutura por ano, passe `--destino "CAMINHO"` e ajuste os três argumentos de `prepare`. Preserve os CSVs byte a byte, inclusive BOM e quebras de linha.

## 3. Criar o banco de avaliação

Para reconstruir, use um banco novo no serviço PostgreSQL 18. Para consultar um ambiente já carregado, pule as etapas de criação e carga e use os dados de conexão desse ambiente.

Abra `psql -X -h 127.0.0.1 -p 5432 -U postgres -d postgres` com o administrador real do serviço. No Homebrew, substitua `postgres` em `-U` pelo administrador local. Ajuste a porta conforme a instalação. No prompt do psql, execute o bloco abaixo.

```sql
SHOW server_version;
SHOW data_directory;
CREATE ROLE anac_avaliacao LOGIN;
SET password_encryption = 'scram-sha-256';
\password anac_avaliacao
CREATE DATABASE anac_repro OWNER anac_avaliacao TEMPLATE template0
    ENCODING 'UTF8' LOCALE_PROVIDER libc LOCALE 'C';
\q
```

Guarde a localização de `data_directory` para a conferência de disco. Se o papel já existe, use-o somente se for o papel destinado à avaliação, ou escolha outro nome. Se o banco já existe, escolha outro nome para uma reconstrução. Em uma instalação que exija ajuste de autenticação, o administrador pode consultar `SHOW hba_file;` e conferir se a primeira regra aplicável a esse usuário e banco em `127.0.0.1/32` usa `scram-sha-256`. Após um ajuste no serviço de avaliação, recarregue com `SELECT pg_reload_conf();`. [Autenticação no PostgreSQL 18](https://www.postgresql.org/docs/18/client-authentication.html)

Configure a conexão no PowerShell.

```powershell
$env:PGHOST = '127.0.0.1'
$env:PGPORT = '5432'
$env:PGUSER = 'anac_avaliacao'
$env:PGDATABASE = 'anac_repro'
$env:PGCLIENTENCODING = 'UTF8'
```

No macOS e Linux, configure a mesma conexão.

```bash
export PGHOST=127.0.0.1 PGPORT=5432 PGUSER=anac_avaliacao PGDATABASE=anac_repro PGCLIENTENCODING=UTF8
```

O psql pode pedir senha a cada nova conexão. Para automatizar a autenticação, use `%APPDATA%\postgresql\pgpass.conf` no Windows ou `~/.pgpass` no macOS e Linux, com `chmod 0600 ~/.pgpass` nestes dois sistemas. O formato é `127.0.0.1:5432:anac_repro:anac_avaliacao:SUA_SENHA`. Guarde o arquivo fora do repositório. As ferramentas usam o ambiente e a configuração libpq. [Arquivo de senhas PostgreSQL 18](https://www.postgresql.org/docs/18/libpq-pgpass.html)

```text
psql -X -v ON_ERROR_STOP=1 -c "SELECT current_database(), current_user, inet_server_addr(), inet_server_port(), version()"
```

## 4. Preparar, carregar e validar

Reserve **8 GiB livres além do pico estimado**, em cada volume usado. `prepare` verifica o volume de saída, com estimativa de quatro vezes os bytes das fontes mais 1 GiB. `check-load` usa a mesma estimativa da instalação isolada, 24 vezes o tamanho dos RAW preparados mais 2 GiB, para tabelas, índices, WAL e temporários. A partir do bundle validado, a segunda verificação exige aproximadamente 28 GiB livres. O cluster carregado ocupou aproximadamente 10,40 GiB em repouso. Os valores medem coisas diferentes. Em instalações com tablespaces, WAL ou temporários em volumes separados, confira também esses volumes. Se a verificação de espaço falhar, pare e use um destino com espaço suficiente.

Rode os comandos abaixo um por vez. Use um diretório de saída novo para uma reprodução independente. Substitua `CAMINHO_DO_VOLUME_PG` pelo diretório de dados ou por outra pasta existente no mesmo volume do servidor local. Pare ao primeiro erro. O caminho de saída fica embutido nos comandos `\copy`. Se mover o bundle ou o projeto, gere os arquivos novamente no destino.

```text
python scripts/integracao_final.py prepare --dados-2019 dados/brutos/2019 --dados-2020 dados/brutos/2020 --dados-2021 dados/brutos/2021 --output .local/reproducao
python scripts/integracao_final.py check-load --output .local/reproducao --volume-pg "CAMINHO_DO_VOLUME_PG"
psql -X -v ON_ERROR_STOP=1 -f .local/reproducao/01_elt.psql
psql -X -v ON_ERROR_STOP=1 -f .local/reproducao/02_etl.psql
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/validar_final.sql
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/validar_restauracao.sql
```

`prepare` gera `01_elt.psql`, `02_etl.psql` e `manifesto_final.json`. Antes de carregar, confira esses arquivos. Em ambiente com Bash, use também `python scripts/validar_guia.py --bundle .local/reproducao` para conferir os manifestos e as etapas geradas.

Se a conexão falhar, confira primeiro o serviço, a porta, os valores `PG*` e a autenticação da etapa anterior. Se `psql` informar que um arquivo de `\copy` não existe, confira se está usando o bundle preparado na máquina cliente e se o caminho continua acessível a quem executa `psql`. Se o erro indicar schema existente, confira o banco de destino e a situação da transação antes de repetir a carga.

Cada carga faz uma transação própria. Se a carga ELT terminou e a ETL falhou, corrija a causa, confira se `dw_etl` está ausente e retome a partir de `02_etl.psql`. Execute `validar_final.sql` antes de `validar_restauracao.sql`, pois ele cria as funções de comparação usadas pelo segundo arquivo. As validações esperam `COMPARACAO_EXATA_OK` para 2019, 2020 e 2021 e `RESTAURACAO_OK` para a conciliação de RAW, fatos, dimensões e chaves.

Em cada DW, as contagens esperadas são 982.926 fatos em 2019, 481.909 em 2020 e 606.637 em 2021, totalizando **2.071.472**. Em um banco já carregado, esta consulta confere os números sem reimportar dados.

```sql
SELECT 'ETL' fluxo, ano_origem, count(*) FROM dw_etl.fato_voo GROUP BY 1, 2
UNION ALL
SELECT 'ELT', ano_origem, count(*) FROM dw_elt.fato_voo GROUP BY 1, 2
ORDER BY 1, 2;
```

## 5. Conectar um cliente PostgreSQL

No pgAdmin, DBeaver, DataGrip ou outro cliente, escolha o driver PostgreSQL. Use os mesmos valores de host, porta, banco e usuário da conexão `psql`, por exemplo `127.0.0.1`, `5432`, `anac_repro` e `anac_avaliacao`. Informe a senha do papel no cliente e use a configuração SSL exigida pelo servidor. No navegador de objetos, selecione os schemas `dw_etl` e `dw_elt`. Os arquivos `.psql` da carga usam comandos específicos do psql, inclusive `\copy`.

## 6. Backup lógico e restauração

Use clientes 18 e um banco de restauração novo. Antes de copiar, consulte `SELECT pg_database_size(current_database());`. Reserve no volume do dump pelo menos o tamanho atual do banco como estimativa conservadora, e no volume do servidor espaço para os objetos restaurados, índices, WAL e temporários. Para dimensionar uma restauração com o bundle preparado, use também `check-load` como margem conservadora para o volume do servidor. Quando os destinos compartilham um volume, some as estimativas e preserve os 8 GiB de reserva. Para um caminho existente, confira bytes livres com `python -c "import shutil,sys; print(shutil.disk_usage(sys.argv[1]).free)" "CAMINHO"`.

Crie previamente a pasta local `backups` com acesso privado. Use um nome de arquivo novo e guarde o hash para conferir antes de restaurar.

```text
pg_dump --format=custom --file=backups/anac_repro.dump
python -c "from pathlib import Path; import hashlib; f=Path('backups/anac_repro.dump').open('rb'); print(hashlib.file_digest(f,'sha256').hexdigest())"
pg_restore --list backups/anac_repro.dump
```

O administrador pode criar o banco abaixo no servidor de destino, com um papel local proprietário. Ajuste as variáveis `PG*` para esse servidor e papel antes de restaurar. [Documentação de pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html)

```sql
CREATE DATABASE anac_repro_restore OWNER anac_avaliacao TEMPLATE template0
    ENCODING 'UTF8' LOCALE_PROVIDER libc LOCALE 'C';
```

```text
pg_restore --exit-on-error --single-transaction --no-owner --no-acl --dbname=anac_repro_restore backups/anac_repro.dump
psql -X -v ON_ERROR_STOP=1 -d anac_repro_restore -f sql/comparacao/validar_restauracao.sql
```

O dump lógico permite transportar ambos os DWs. Os papéis são provisionados no destino e permissões de acesso adicionais são aplicadas ali. O backup físico histórico em [INTEGRACAO_FINAL.md](INTEGRACAO_FINAL.md) serve à recuperação do ambiente original.

## 7. Testes e alcance

O comando `python -m unittest discover -s tests -v` usa CSVs sintéticos e cria clusters de teste pequenos, com `postgres` e `initdb` no PATH e sem privilégios de administrador. A suíte usa diretórios temporários novos e executa o PostgreSQL em modo single-user, sem abrir portas. Se necessário, aponte `TMPDIR` no macOS/Linux ou `TEMP` e `TMP` no Windows a uma pasta existente com espaço livre. A reserva de 8 GiB descrita na seção de preparação e carga é aplicada pela CLI ao reproduzir a integração com os dados reais.

No Windows, a suíte pula a comparação byte a byte das reexportações do utilitário single-user, pois o PostgreSQL grava CRLF ao exportar para um arquivo no servidor. A suíte conserva as verificações SQL de conteúdo e rastreabilidade. [Comportamento de COPY](https://www.postgresql.org/docs/18/sql-copy.html)

Veja [as verificações de portabilidade](../relatorio/PORTABILIDADE.md) e a [validação funcional mais recente no Fedora](INTEGRACAO_FINAL.md#validação-funcional-com-fixtures). Os passos para Windows e macOS foram preparados para avaliação e aguardam execução nesses sistemas.
