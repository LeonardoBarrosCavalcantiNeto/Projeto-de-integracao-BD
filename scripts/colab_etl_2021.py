"""Preparação e evidências do Colab; o tratamento continua no ETL existente.

Importar este módulo não instala pacotes, conecta ao banco nem modifica arquivos.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone


ARQUIVOS_2021 = tuple(f"VRA_2021_{mes:02d}.csv" for mes in range(1, 13))
TABELAS_CARGA = (
    "vra_bruta", "vra_tratada", "vra_rejeicoes", "vra_duplicatas_excluidas",
    "vra_anomalias", "vra_conflitos_codigo", "vra_possiveis_duplicatas_padronizacao",
    "inventario_arquivos", "resumo_qualidade", "etl_log_arquivos",
)
TABELAS_COM_ORIGEM = (
    "vra_bruta", "vra_tratada", "vra_rejeicoes", "vra_duplicatas_excluidas",
    "vra_possiveis_duplicatas_padronizacao",
)


def sha256_arquivo(caminho):
    digest = hashlib.sha256()
    with Path(caminho).open("rb") as entrada:
        for bloco in iter(lambda: entrada.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def preparar_entrada_zip(caminho_zip, pasta_dados, inventario_referencia):
    """Confere todo o ZIP antes de copiar os 12 CSVs, sem conversão de bytes.

    Aceita o manifesto JSON do projeto ou o inventário CSV da execução individual.
    Pastas internas são permitidas. CSVs inesperados, meses repetidos/ausentes e
    hashes diferentes bloqueiam a preparação. Arquivos locais diferentes também
    são preservados: nenhuma substituição de brutos é feita implicitamente.
    """
    caminho_zip, pasta_dados = Path(caminho_zip), Path(pasta_dados)
    inventario_referencia = Path(inventario_referencia)
    with inventario_referencia.open(encoding="utf-8-sig", newline="") as entrada:
        if inventario_referencia.suffix.lower() == ".json":
            chave = "arquivo_origem"
            linhas = [item for item in json.load(entrada)["arquivos"] if item["ano_origem"] == 2021]
        else:
            leitor = csv.DictReader(entrada)
            campos = leitor.fieldnames or []
            chave = "arquivo" if "arquivo" in campos else "arquivo_origem"
            if chave not in campos or "sha256" not in campos:
                raise ValueError("Inventário deve conter arquivo/arquivo_origem e sha256.")
            linhas = list(leitor)
    hashes = {linha[chave]: linha["sha256"] for linha in linhas}
    if len(linhas) != 12 or set(hashes) != set(ARQUIVOS_2021):
        raise ValueError("Inventário deve conter os 12 meses de 2021 uma única vez.")
    if any(not re.fullmatch(r"[0-9a-f]{64}", valor) for valor in hashes.values()):
        raise ValueError("Inventário com SHA-256 inválido.")
    extras = {p.name for p in pasta_dados.glob("VRA_2021_*.csv")} - set(ARQUIVOS_2021)
    if extras:
        raise ValueError(f"CSVs de 2021 inesperados na pasta de entrada: {sorted(extras)}")

    with zipfile.ZipFile(caminho_zip) as arquivo_zip:
        membros = {}
        for item in arquivo_zip.infolist():
            caminho = PurePosixPath(item.filename.replace("\\", "/"))
            if item.is_dir() or "__MACOSX" in caminho.parts or caminho.suffix.lower() != ".csv":
                continue
            nome = caminho.name
            if nome not in hashes:
                raise ValueError(f"CSV inesperado no ZIP: {nome}")
            if nome in membros:
                raise ValueError(f"Mês repetido no ZIP: {nome}")
            membros[nome] = item
        faltantes = set(ARQUIVOS_2021) - set(membros)
        if faltantes:
            raise ValueError(f"Meses ausentes no ZIP: {sorted(faltantes)}")

        relatorio = []
        with tempfile.TemporaryDirectory(prefix="entrada-vra-2021-") as temporario:
            temporario = Path(temporario)
            for nome in ARQUIVOS_2021:
                copia = temporario / nome
                with arquivo_zip.open(membros[nome]) as origem, copia.open("wb") as saida:
                    shutil.copyfileobj(origem, saida)
                digest = sha256_arquivo(copia)
                if digest != hashes[nome]:
                    raise ValueError(f"SHA-256 diferente do inventário: {nome}")
                existente = pasta_dados / nome
                if existente.exists() and sha256_arquivo(existente) != digest:
                    raise ValueError(f"Arquivo local diferente; preservado sem sobrescrever: {nome}")
                relatorio.append({"arquivo": nome, "bytes": copia.stat().st_size, "sha256": digest})
            pasta_dados.mkdir(parents=True, exist_ok=True)
            for nome in ARQUIVOS_2021:
                copia = pasta_dados / nome
                if not copia.exists():
                    shutil.copyfile(temporario / nome, copia)
                if sha256_arquivo(copia) != hashes[nome]:
                    raise ValueError(f"Falha na conferência da cópia de {nome}.")
    return {
        "zip": caminho_zip.name, "sha256_zip": sha256_arquivo(caminho_zip),
        "sha256_inventario": sha256_arquivo(inventario_referencia),
        "hashes_conferidos": True, "arquivos": relatorio,
    }


def em_colab_hospedado():
    """Exige a shell do Colab e um marcador da sessão hospedada."""
    try:
        from IPython import get_ipython
        shell = get_ipython()
        return (shell is not None and type(shell).__module__.startswith("google.colab.")
                and bool(os.environ.get("COLAB_RELEASE_TAG")))
    except ImportError:
        return False


def _psql_administrativo(comando):
    # A senha aleatória só trafega por stdin, sem aparecer no comando ou na saída.
    processo = subprocess.run(
        ["runuser", "-u", "postgres", "--", "psql", "-v", "ON_ERROR_STOP=1", "-tA", "-d", "postgres"],
        input=comando, text=True, capture_output=True,
    )
    if processo.returncode:
        raise RuntimeError("Falha ao configurar o PostgreSQL temporário da sessão.")
    return processo.stdout.strip()


def preparar_postgresql_temporario():
    """Instala/configura o banco somente no Colab hospedado; nunca no PC local."""
    if not em_colab_hospedado():
        raise RuntimeError("A instalação automática exige uma sessão hospedada do Colab.")
    subprocess.run(["apt-get", "update", "-qq"], check=True)
    subprocess.run(["apt-get", "install", "-y", "postgresql", "postgresql-contrib", "-qq"], check=True)
    subprocess.run(["service", "postgresql", "start"], check=True)
    senha = os.environ.get("ETL_2021_COLAB_PASSWORD") or secrets.token_urlsafe(32)
    # A senha vem exclusivamente de token_urlsafe: nunca interpolar entrada do usuário.
    if not re.fullmatch(r"[A-Za-z0-9_-]+", senha):
        raise ValueError("Credencial temporária inválida; inicie uma sessão nova.")
    nome = "etl_2021_colab"
    _psql_administrativo(f"""DO $$ BEGIN
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{nome}') THEN
            ALTER ROLE {nome} WITH LOGIN PASSWORD '{senha}';
        ELSE
            CREATE ROLE {nome} WITH LOGIN PASSWORD '{senha}';
        END IF;
    END $$;""")
    if _psql_administrativo(f"SELECT 1 FROM pg_database WHERE datname = '{nome}';") != "1":
        _psql_administrativo(f"CREATE DATABASE {nome} OWNER {nome};")

    import psycopg
    from sqlalchemy.engine import URL
    with psycopg.connect(dbname=nome, user=nome, password=senha, host="127.0.0.1", port=5432,
                         connect_timeout=10) as conexao:
        versao = conexao.execute("SHOW server_version").fetchone()[0]
    os.environ["ETL_2021_COLAB_PASSWORD"] = senha
    os.environ["DATABASE_URL"] = URL.create(
        "postgresql+psycopg", username=nome, password=senha, host="127.0.0.1", port=5432,
        database=nome,
    ).render_as_string(hide_password=False)
    return {"banco": nome, "usuario": nome, "host": "127.0.0.1", "porta": 5432,
            "versao_postgresql": versao}


def _metadados_atuais(resultado):
    pasta = Path(resultado["pasta_saida"])
    meta = json.loads((pasta / "metadados_execucao.json").read_text(encoding="utf-8"))
    status = json.loads((pasta / "status_carga_postgresql.json").read_text(encoding="utf-8"))
    execucao = resultado["carga_postgresql"].get("execucao_id")
    if (not execucao or meta.get("inicio_utc") != execucao or status.get("execucao_id") != execucao
            or meta.get("status_execucao") != "concluida" or status.get("status") != "concluida"
            or status.get("transacao_confirmada") is not True):
        raise ValueError("Exigida carga confirmada e metadados da execução atual; execute o ETL novamente.")
    if status.get("contagens") != resultado["carga_postgresql"].get("contagens"):
        raise ValueError("Contagens do resultado não correspondem ao status atual.")
    return pasta, meta


def validar_carga_postgresql(resultado, raiz):
    """Consulta o banco em nova transação somente de leitura, após o COMMIT da carga."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL, make_url

    pasta, meta = _metadados_atuais(resultado)
    esperadas = resultado["carga_postgresql"]["contagens"]
    if set(esperadas) != set(TABELAS_CARGA):
        raise ValueError("A carga deve conter exatamente as dez tabelas do ETL 2021.")
    if os.environ.get("DATABASE_URL"):
        url = make_url(os.environ["DATABASE_URL"])
    else:
        if not os.environ.get("PGDATABASE") or not os.environ.get("PGUSER"):
            raise ValueError("Configure DATABASE_URL ou PGDATABASE/PGUSER antes de validar o banco.")
        url = URL.create("postgresql+psycopg", username=os.environ["PGUSER"],
                         password=os.environ.get("PGPASSWORD"), host=os.environ.get("PGHOST", "localhost"),
                         port=int(os.environ.get("PGPORT", "5432")), database=os.environ["PGDATABASE"])
    if url.get_backend_name() != "postgresql":
        raise ValueError("A validação exige PostgreSQL.")
    engine = create_engine(url.set(drivername="postgresql+psycopg"), hide_parameters=True)
    contagens, origens_unicas = {}, {}
    try:
        with engine.begin() as conexao:
            conexao.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            banco = conexao.execute(text("SELECT current_database()")).scalar_one()
            versao = conexao.execute(text("SHOW server_version")).scalar_one()
            for nome in TABELAS_CARGA:
                contagens[nome] = conexao.execute(text(f'SELECT count(*) FROM etl_2021."{nome}"')).scalar_one()
                if contagens[nome] != esperadas[nome]:
                    raise ValueError(f"Contagem divergente após COMMIT: {nome}.")
            for nome in (*TABELAS_COM_ORIGEM, "etl_log_arquivos"):
                campos = "arquivo_origem" if nome == "etl_log_arquivos" else "arquivo_origem, linha_origem"
                duplicadas = conexao.execute(text(
                    f'SELECT count(*) FROM (SELECT {campos} FROM etl_2021."{nome}" '
                    f'GROUP BY {campos} HAVING count(*) > 1) repetidas'
                )).scalar_one()
                nulos = "arquivo_origem IS NULL" + ("" if nome == "etl_log_arquivos" else " OR linha_origem IS NULL")
                sem_origem = conexao.execute(text(
                    f'SELECT count(*) FROM etl_2021."{nome}" WHERE {nulos}'
                )).scalar_one()
                origens_unicas[nome] = duplicadas == sem_origem == 0
                if not origens_unicas[nome]:
                    raise ValueError(f"Origem nula ou repetida após COMMIT: {nome}.")
            inventario = conexao.execute(text(
                "SELECT arquivo, registros_csv FROM etl_2021.inventario_arquivos ORDER BY mes"
            )).all()
            if len(inventario) != 12 or {a for a, _ in inventario} != set(ARQUIVOS_2021):
                raise ValueError("Inventário no banco não contém os 12 arquivos esperados.")
            mensal = {nome: dict(conexao.execute(text(
                f'SELECT arquivo_origem, count(*) FROM etl_2021."{nome}" GROUP BY arquivo_origem'
            )).all()) for nome in ("vra_bruta", "vra_tratada", "vra_rejeicoes", "vra_duplicatas_excluidas")}
            for arquivo, quantidade in inventario:
                bruta = mensal["vra_bruta"].get(arquivo, 0)
                destinos = sum(mensal[nome].get(arquivo, 0) for nome in mensal if nome != "vra_bruta")
                if bruta != quantidade or bruta != destinos:
                    raise ValueError(f"Conciliação mensal divergente no banco: {arquivo}.")
    finally:
        engine.dispose()
    codigo = subprocess.check_output(["git", "-C", str(raiz), "rev-parse", "HEAD"], text=True).strip()
    evidencia = {
        "status": "concluida", "execucao_id": meta["inicio_utc"],
        "ambiente": "google_colab_hospedado" if em_colab_hospedado() else "local",
        "banco": banco, "schema": "etl_2021", "versao_postgresql": versao,
        "commit_codigo": codigo, "sha256_script_etl": sha256_arquivo(Path(raiz) / "scripts/etl_vra_anac_2021.py"),
        "sha256_script_colab": sha256_arquivo(Path(__file__)),
        "verificado_em_utc": datetime.now(timezone.utc).isoformat(),
        "transacao_carga_confirmada": True, "consulta_somente_leitura": True,
        "contagens_apos_commit": contagens, "origens_unicas": origens_unicas,
        "conciliacao_mensal": True,
    }
    (pasta / "validacao_postgresql_colab.json").write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return evidencia


def exportar_evidencias_colab(resultado, informacoes_zip, *, incluir_tratada=False):
    """Prepara arquivos para revisão e um ZIP; não publica nada no GitHub."""
    import pandas as pd
    import psycopg

    pasta, meta = _metadados_atuais(resultado)
    validacao = json.loads((pasta / "validacao_postgresql_colab.json").read_text(encoding="utf-8"))
    if (validacao.get("execucao_id") != meta["inicio_utc"] or validacao.get("status") != "concluida"
            or validacao.get("contagens_apos_commit") != resultado["carga_postgresql"]["contagens"]):
        raise ValueError("Validação PostgreSQL não corresponde à execução atual.")
    if not informacoes_zip or informacoes_zip.get("hashes_conferidos") is not True:
        raise ValueError("Confira o ZIP e seus hashes antes de exportar as evidências.")
    hashes_zip = {a["arquivo"]: a["sha256"] for a in informacoes_zip["arquivos"]}
    with (pasta / "inventario_arquivos.csv").open(encoding="utf-8", newline="") as arquivo:
        hashes_etl = {a["arquivo"]: a["sha256"] for a in csv.DictReader(arquivo)}
    if len(hashes_zip) != 12 or hashes_etl != hashes_zip:
        raise ValueError("O ZIP conferido não corresponde aos arquivos processados pelo ETL.")
    referencia = {"bruta": 632148, "duplicatas_excedentes": 0, "rejeicoes": 25511, "tratada": 606637}
    regressao = {nome: {"referencia": valor, "medido": resultado["resumo"][nome],
                       "igual": valor == resultado["resumo"][nome]} for nome, valor in referencia.items()}
    meta.update({
        "ambiente": validacao["ambiente"], "colab_executado": validacao["ambiente"] == "google_colab_hospedado",
        "commit_codigo": validacao["commit_codigo"], "python": sys.version.split()[0],
        "pandas": pd.__version__, "psycopg": psycopg.__version__,
        "entrada_zip": informacoes_zip, "regressao": regressao,
        "validacao_postgresql": validacao, "exportado_em_utc": datetime.now(timezone.utc).isoformat(),
    })
    publicar = pasta / "publicar_no_git"
    logs, verificacoes = publicar / "resultados/logs", publicar / "resultados/validacoes"
    logs.mkdir(parents=True, exist_ok=True)
    verificacoes.mkdir(parents=True, exist_ok=True)
    (logs / "metadados_execucao_etl_2021_colab.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copyfile(pasta / "validacao_postgresql_colab.json", verificacoes / "validacao_postgresql_etl_2021_colab.json")
    for origem, destino in [("resumo_qualidade.csv", "resumo_qualidade_etl_2021_colab.csv"),
                            ("mensal.csv", "mensal_etl_2021_colab.csv")]:
        shutil.copyfile(pasta / origem, verificacoes / destino)
    destino = pasta.parent / "evidencias_etl_2021_colab.zip"
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as arquivo:
        for item in sorted(pasta.iterdir()):
            if not item.is_file() or item.name == "vra_bruta.csv.gz":
                continue
            if item.name == "vra_tratada.csv.gz" and not incluir_tratada:
                continue
            if item.name.endswith((".csv", ".csv.gz", ".json", ".md")):
                arquivo.write(item, "dados/processados/2021/etl/" + item.name)
        arquivo.write(pasta / "vra_bruta/manifesto_sha256.csv", "dados/processados/2021/etl/vra_bruta/manifesto_sha256.csv")
        for item in sorted(publicar.rglob("*")):
            if item.is_file():
                arquivo.write(item, item.relative_to(publicar).as_posix())
        arquivo.writestr("LEIA_ME_COLAB.md", (
            f"# Evidências ETL 2021\n\nAmbiente registrado: {validacao['ambiente']}.\n"
            "Revise os quatro arquivos de resultados/ antes de adicioná-los ao Git.\n"
            "O notebook executado deve ser baixado separadamente pelo menu Arquivo do Colab.\n"
            "O banco é temporário e pode desaparecer ao terminar a sessão.\n"
            "A execução no Colab e a regressão só podem ser dadas como concluídas após conferir os metadados.\n"
        ))
    return {"zip": str(destino), "pasta_publicacao": str(publicar), "regressao": regressao,
            "colab_executado": meta["colab_executado"]}
