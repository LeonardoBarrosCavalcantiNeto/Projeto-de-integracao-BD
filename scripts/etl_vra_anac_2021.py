#!/usr/bin/env python3
"""ETL VRA/ANAC 2021: CSVs -> tratamento em Python -> evidências -> PostgreSQL opcional.

Contrato v1.1. Preserva a entrada e Codeshare, deduplica os 20 campos brutos,
audita rejeições/anomalias e calcula métricas antes de qualquer carga no banco.
Dimensões e Fato compartilhadas permanecem na integração do grupo.

Uso sem banco:
    python scripts/etl_vra_anac_2021.py --input-dir dados/brutos --output-dir dados/processados/2021/etl

Para carregar no banco configurado no .env, acrescente --load-db.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ano_origem = 2021

colunas_comuns = [
    "Sigla ICAO Empresa Aérea",
    "Empresa Aérea",
    "Número Voo",
    "Código DI",
    "Código Tipo Linha",
    "Modelo Equipamento",
    "Número de Assentos",
    "Sigla ICAO Aeroporto Origem",
    "Descrição Aeroporto Origem",
    "Partida Prevista",
    "Partida Real",
    "Sigla ICAO Aeroporto Destino",
    "Descrição Aeroporto Destino",
    "Chegada Prevista",
    "Chegada Real",
    "Situação Voo",
    "Justificativa",
    "Referência",
    "Situação Partida",
    "Situação Chegada",
]

mapa_colunas = {
    "Sigla ICAO Empresa Aérea": "companhia_icao",
    "Empresa Aérea": "companhia_nome",
    "Número Voo": "numero_voo",
    "Código DI": "codigo_di",
    "Código Tipo Linha": "tipo_linha",
    "Modelo Equipamento": "modelo_equipamento",
    "Número de Assentos": "numero_assentos",
    "Sigla ICAO Aeroporto Origem": "aeroporto_origem",
    "Descrição Aeroporto Origem": "descricao_origem",
    "Partida Prevista": "partida_prevista",
    "Partida Real": "partida_real",
    "Sigla ICAO Aeroporto Destino": "aeroporto_destino",
    "Descrição Aeroporto Destino": "descricao_destino",
    "Chegada Prevista": "chegada_prevista",
    "Chegada Real": "chegada_real",
    "Situação Voo": "situacao_voo",
    "Justificativa": "justificativa",
    "Referência": "referencia",
    "Situação Partida": "situacao_partida",
    "Situação Chegada": "situacao_chegada",
}

colunas_canonicas = list(mapa_colunas.values())

metadados = ["arquivo_origem", "linha_origem", "ano_origem",
             "data_carga", "pipeline", "versao_contrato"]

campos_maiusculos = [
    "companhia_icao", "codigo_di", "tipo_linha", "modelo_equipamento",
    "aeroporto_origem", "aeroporto_destino", "situacao_voo",
    "situacao_partida", "situacao_chegada",
]

PADRAO_DATAHORA = re.compile(r"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}")

PADRAO_DATA_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

PADRAO_REFERENCIA_BR = re.compile(r"[0-9]{2}/[0-9]{2}/[0-9]{4} 00:00:00")

def sha256_arquivo(caminho):
    digest = hashlib.sha256()
    with caminho.open("rb") as entrada:
        for bloco in iter(lambda: entrada.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()

def validar_entradas(arquivos):
    """Valida o CSV antes do Pandas; linha_origem conta registros lógicos."""
    cabecalhos, inventario = {}, []
    for arquivo in arquivos:
        hash_antes = sha256_arquivo(arquivo)
        with arquivo.open(encoding="utf-8-sig", newline="") as entrada:
            leitor = csv.reader(entrada, delimiter=";", strict=True)
            cabecalho = next(leitor, [])
            exigir(cabecalho in (colunas_comuns, colunas_comuns + ["Codeshare"]),
                   f"Cabeçalho inválido (nomes ou ordem) em {arquivo.name}.")
            quantidade = 0
            for numero, registro in enumerate(leitor, start=2):
                exigir(len(registro) == len(cabecalho),
                       f"{arquivo.name}, registro {numero}: esperados {len(cabecalho)} "
                       f"campos, encontrados {len(registro)}.")
                quantidade += 1
        exigir(sha256_arquivo(arquivo) == hash_antes,
               f"Arquivo alterado durante a validação: {arquivo.name}")
        cabecalhos[arquivo.name] = cabecalho
        inventario.append({
            "arquivo": arquivo.name, "mes": int(arquivo.stem[-2:]),
            "bytes": arquivo.stat().st_size, "sha256": hash_antes,
            "colunas_originais": len(cabecalho), "registros_csv": quantidade,
        })
    return cabecalhos, pd.DataFrame(inventario)


def preservar_brutos(arquivos, inventario, pasta_saida):
    """Copia bytes originais, inclusive BOM e quebras de linha, e verifica SHA-256."""
    destino = pasta_saida / "vra_bruta"
    destino.mkdir(parents=True, exist_ok=True)
    hashes = inventario.set_index("arquivo")["sha256"]
    manifesto = []
    for arquivo in arquivos:
        copia = destino / arquivo.name
        exigir(arquivo.resolve() != copia.resolve(), "A cópia bruta deve ter outro caminho.")
        shutil.copyfile(arquivo, copia)
        hash_copia = sha256_arquivo(copia)
        exigir(hash_copia == hashes[arquivo.name] == sha256_arquivo(arquivo),
               f"Hash divergente na cópia bruta: {arquivo.name}")
        manifesto.append({"arquivo": arquivo.name, "sha256_original": hashes[arquivo.name],
                          "sha256_copia": hash_copia, "bytes": copia.stat().st_size,
                          "hashes_iguais": True})
    pd.DataFrame(manifesto).to_csv(destino / "manifesto_sha256.csv", index=False)
    return inventario.assign(sha256_copia=inventario["sha256"], copia_bruta_verificada=True)

def padronizar_textos(base):
    saida = base[colunas_comuns + metadados].copy()
    saida.rename(columns=mapa_colunas, inplace=True)
    for campo in colunas_canonicas:
        texto = saida[campo].astype("string").str.strip()
        saida[campo] = texto.mask(texto.eq(""), pd.NA)
    for campo in campos_maiusculos:
        saida[campo] = saida[campo].str.upper()
    return saida

def datahora_segura(valor):
    if pd.isna(valor) or not PADRAO_DATAHORA.fullmatch(valor):
        return None
    try:
        return datetime(int(valor[6:10]), int(valor[3:5]), int(valor[0:2]),
                        int(valor[11:13]), int(valor[14:16]))
    except ValueError:
        return None

def referencia_segura(valor):
    if pd.isna(valor):
        return None
    try:
        if PADRAO_DATA_ISO.fullmatch(valor):
            return date(int(valor[0:4]), int(valor[5:7]), int(valor[8:10]))
        if PADRAO_REFERENCIA_BR.fullmatch(valor):
            return date(int(valor[6:10]), int(valor[3:5]), int(valor[0:2]))
    except ValueError:
        return None
    return None

def assentos_seguros(valor):
    if pd.isna(valor) or not re.fullmatch(r"[0-9]+", valor):
        return None
    digitos = valor.lstrip("0") or "0"
    if len(digitos) > 10:
        return None
    numero = int(digitos)
    return numero if numero <= 2147483647 else None

def converter_tipos(base):
    saida = base.copy()
    for campo in ["partida_prevista", "partida_real", "chegada_prevista", "chegada_real"]:
        saida[campo] = pd.Series(
            [datahora_segura(valor) for valor in base[campo]],
            index=base.index, dtype="datetime64[us]",
        )
    saida["referencia"] = pd.Series(
        [referencia_segura(valor) for valor in base["referencia"]],
        index=base.index, dtype=object,
    )
    saida["numero_assentos"] = pd.Series(
        [assentos_seguros(valor) for valor in base["numero_assentos"]],
        index=base.index, dtype="Int32",
    )
    return saida

def motivos_obrigatorios(textos, convertida):
    regras = {
        "COMPANHIA_AUSENTE": convertida["companhia_icao"].isna(),
        "AEROPORTO_ORIGEM_AUSENTE": convertida["aeroporto_origem"].isna(),
        "AEROPORTO_DESTINO_AUSENTE": convertida["aeroporto_destino"].isna(),
    }
    for campo, prefixo in [("partida_prevista", "PARTIDA_PREVISTA"),
                           ("chegada_prevista", "CHEGADA_PREVISTA")]:
        regras[prefixo + "_AUSENTE"] = textos[campo].isna()
        regras[prefixo + "_INVALIDA"] = textos[campo].notna() & convertida[campo].isna()
    motivos = [[] for _ in range(len(convertida))]
    for motivo, mascara in regras.items():
        for posicao in np.flatnonzero(mascara.to_numpy(dtype=bool)):
            motivos[posicao].append(motivo)
    return pd.Series(motivos, index=convertida.index, name="motivo_rejeicao", dtype=object)

def com_originais(convertida, bruta):
    """Anexa o retrato bruto com nomes canônicos prefixados; não altera a entrada."""
    campos = colunas_comuns + [c for c in ["Codeshare", "codeshare_presente_no_arquivo"] if c in bruta]
    originais = bruta[campos].rename(columns={
        c: "bruto__" + mapa_colunas.get(c, "codeshare" if c == "Codeshare" else c)
        for c in campos
    })
    return pd.concat([convertida, originais], axis=1)


def auditar_opcionais(bruta, textos, convertida):
    partes_anomalias = []
    retrato = com_originais(convertida, bruta)
    for original, canonico in [
        ("Partida Real", "partida_real"), ("Chegada Real", "chegada_real"),
        ("Número de Assentos", "numero_assentos"), ("Referência", "referencia"),
    ]:
        mascara = textos[canonico].notna() & convertida[canonico].isna()
        ocorrencias = pd.DataFrame(index=retrato.index[mascara])
        ocorrencias["campo"] = canonico
        ocorrencias["campo_original"] = original
        ocorrencias["valor_original"] = bruta.loc[mascara, original]
        ocorrencias["motivo"] = "VALOR_OPCIONAL_INVALIDO"
        partes_anomalias.append(ocorrencias)
    fora_ano = convertida["referencia"].map(
        lambda valor: valor is not None and valor.year != ano_origem
    ).astype(bool)
    ocorrencias = pd.DataFrame(index=retrato.index[fora_ano])
    ocorrencias["campo"] = "referencia"
    ocorrencias["campo_original"] = "Referência"
    ocorrencias["valor_original"] = bruta.loc[fora_ano, "Referência"]
    ocorrencias["motivo"] = "REFERENCIA_FORA_DE_2021"
    partes_anomalias.append(ocorrencias)
    detalhes = pd.concat(partes_anomalias)
    return retrato.loc[detalhes.index].reset_index(drop=True).join(detalhes.reset_index(drop=True))

def calcular_metricas(base):
    saida = base.copy()
    for evento in ["partida", "chegada"]:
        diferenca = (
            (saida[f"{evento}_real"] - saida[f"{evento}_prevista"])
            .dt.total_seconds().div(60).astype("Int64")
        )
        saida[f"diferenca_{evento}_min"] = diferenca
        saida[f"atraso_{evento}_min"] = diferenca.clip(lower=0)
        saida[f"{evento}_atipica_flag"] = diferenca.abs().gt(1440).fillna(False).astype(bool)
    return saida

def conflitos_descricao(base):
    partes = []
    for tipo, codigo, descricao in [
        ("companhia", "companhia_icao", "companhia_nome"),
        ("aeroporto", "aeroporto_origem", "descricao_origem"),
        ("aeroporto", "aeroporto_destino", "descricao_destino"),
    ]:
        pares = base[[codigo, descricao]].rename(
            columns={codigo: "codigo", descricao: "descricao"}
        )
        pares["tipo"] = tipo
        partes.append(pares)
    pares = pd.concat(partes, ignore_index=True)
    quantidades = pares.groupby(["tipo", "codigo"])["descricao"].nunique(dropna=False)
    chaves = quantidades.loc[quantidades > 1].reset_index()[["tipo", "codigo"]]
    variantes = pares.merge(chaves, on=["tipo", "codigo"], how="inner", validate="many_to_one")
    return (
        variantes.groupby(["tipo", "codigo", "descricao"], dropna=False).size()
        .rename("ocorrencias").reset_index()
        .sort_values(["tipo", "codigo", "descricao"], na_position="last")
    )

def exigir(condicao, mensagem):
    if not bool(condicao):
        raise ValueError(mensagem)

def carregar_postgresql(tabelas, *, schema="etl_2021", replace=False):
    """Carrega saídas já tratadas em uma transação; não transforma os dados."""
    project_dir = Path(__file__).resolve().parents[1]
    import os
    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL, make_url
    from sqlalchemy import types as sat
    from sqlalchemy.dialects.postgresql import ARRAY

    exigir(re.fullmatch(r"[a-z_][a-z0-9_]*", schema) is not None,
           "Nome de schema inválido.")
    exigir(schema == "etl_2021", "Este pipeline carrega somente o schema etl_2021.")
    load_dotenv(project_dir / ".env", override=False)
    if os.getenv("DATABASE_URL"):
        url = make_url(os.environ["DATABASE_URL"])
        exigir(url.get_backend_name() == "postgresql", "DATABASE_URL deve apontar para PostgreSQL.")
        url = url.set(drivername="postgresql+psycopg")
    else:
        exigir(bool(os.getenv("PGDATABASE")) and bool(os.getenv("PGUSER")),
               "Configure PGDATABASE e PGUSER no .env ou nas variáveis de ambiente.")
        url = URL.create(
            "postgresql+psycopg", username=os.getenv("PGUSER"),
            password=os.getenv("PGPASSWORD"), host=os.getenv("PGHOST", "localhost"),
            port=int(os.getenv("PGPORT", "5432")), database=os.getenv("PGDATABASE"),
        )
    engine = create_engine(url, echo=False, hide_parameters=True)
    def tipos_base(base):
        tipos = {campo: sat.Text() for campo in base.columns}
        for campo in ["partida_prevista", "partida_real", "chegada_prevista", "chegada_real"]:
            if campo in tipos:
                tipos[campo] = sat.DateTime(timezone=False)
        if "referencia" in tipos:
            tipos["referencia"] = sat.Date()
        if "data_carga" in tipos:
            tipos["data_carga"] = sat.DateTime(timezone=True)
        inteiros = {"linha_origem", "ano_origem", "linha_preservada", "numero_assentos", "mes",
                    "bytes", "colunas_originais", "registros_csv", "registros_pandas", "ocorrencias",
                    "quantidade_ocorrencias", "bruta", "duplicatas", "rejeicoes", "tratada",
                    "ocorrencias_anomalias", "excedentes_invalidos"}
        booleanos = {"codeshare_presente_no_arquivo", "invalido_diagnostico", "conciliada",
                     "copia_bruta_verificada", "partida_ano_diverge_flag",
                     "partida_atipica_flag", "chegada_atipica_flag"}
        for campo in base.columns:
            if campo in inteiros or (base[campo].dtype.kind in "iu" and campo not in colunas_canonicas):
                tipos[campo] = sat.BigInteger()
            if campo in booleanos or base[campo].dtype.kind == "b":
                tipos[campo] = sat.Boolean()
            if campo in {"diferenca_partida_min", "diferenca_chegada_min", "atraso_partida_min", "atraso_chegada_min"}:
                tipos[campo] = sat.Numeric(16, 2)
            if campo in {"motivo_rejeicao", "motivo_rejeicao_diagnostico"}:
                tipos[campo] = ARRAY(sat.Text())
        return tipos

    tabelas_carga = {nome: (base, tipos_base(base)) for nome, base in tabelas.items()}
    permitidas = {"vra_bruta", "vra_tratada", "vra_rejeicoes", "vra_duplicatas_excluidas",
                  "vra_anomalias", "vra_conflitos_codigo", "inventario_arquivos", "resumo_qualidade",
                  "vra_possiveis_duplicatas_padronizacao", "etl_log_arquivos"}
    exigir(set(tabelas_carga) == permitidas, "Conjunto inesperado de tabelas para a carga.")
    nomes_tabelas = list(tabelas_carga)
    try:
        with engine.begin() as conexao:
            conexao.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            existentes = set(conexao.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=:schema"
            ), {"schema": schema}).scalars())
            exigir(not existentes.intersection(nomes_tabelas) or replace,
                   "Há tabelas deste pipeline no schema; a substituição está desativada.")
            if replace:
                for nome in nomes_tabelas:
                    conexao.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{nome}"'))
            for nome, (base, tipos) in tabelas_carga.items():
                base.to_sql(nome, con=conexao, schema=schema, if_exists="fail",
                            index=False, dtype=tipos, chunksize=2000)
                quantidade = conexao.execute(text(
                    f'SELECT COUNT(*) FROM "{schema}"."{nome}"'
                )).scalar_one()
                exigir(quantidade == len(base), f"Contagem incorreta após carregar {nome}.")
            for nome in ["vra_bruta", "vra_tratada", "vra_rejeicoes", "vra_duplicatas_excluidas",
                         "vra_possiveis_duplicatas_padronizacao"]:
                conexao.execute(text(
                    f'ALTER TABLE "{schema}"."{nome}" '
                    'ADD PRIMARY KEY (arquivo_origem, linha_origem)'
                ))
            conexao.execute(text(
                f'ALTER TABLE "{schema}"."etl_log_arquivos" ADD PRIMARY KEY (arquivo_origem)'
            ))
        # Este ponto só é alcançado depois do COMMIT de engine.begin().
        status_carga_postgresql = {
            "status": "concluida", "schema": schema, "transacao_confirmada": True,
            "contagens": {nome: len(base) for nome, (base, _) in tabelas_carga.items()},
        }
        print("Carga e contagens PostgreSQL concluídas no schema", schema)
    finally:
        engine.dispose()
    return status_carga_postgresql


def _executar_etl(input_dir, output_dir, *, load_database=False, replace=False,
                  schema="etl_2021", export_raw=False, inicio_execucao=None):
    """Executa 2021 e retorna resumo, status da carga e caminhos das evidências.

    A carga é opcional e a substituição de tabelas precisa ser explícita.
    Os DataFrames ficam internos; os resultados são exportados para output_dir.
    """
    pasta_dados = Path(input_dir).resolve()
    PASTA_SAIDA = Path(output_dir).resolve()
    EXPORTAR_EVIDENCIAS = True
    EXPORTAR_BASE_BRUTA = export_raw
    SCHEMA_ETL = schema
    inicio_execucao = inicio_execucao or datetime.now(timezone.utc).isoformat()
    arquivos = [pasta_dados / f"VRA_2021_{mes:02d}.csv" for mes in range(1, 13)]
    faltantes = [arquivo.name for arquivo in arquivos if not arquivo.is_file()]
    if faltantes:
        raise FileNotFoundError(f"Arquivos não encontrados: {faltantes}")
    if {p.name for p in pasta_dados.glob("VRA_2021_*.csv")} != {p.name for p in arquivos}:
        raise ValueError("Esperados exatamente os 12 nomes mensais VRA_2021_MM.csv.")
    print("[ETL 2021] Extraindo e validando os 12 arquivos.")
    cabecalhos_por_arquivo, inventario = validar_entradas(arquivos)
    hashes_entrada = inventario.set_index("arquivo")["sha256"].to_dict()
    conferencia_cabecalhos = pd.DataFrame([
        {"arquivo": arquivo.name, "codeshare_presente": "Codeshare" in cabecalhos_por_arquivo[arquivo.name]}
        for arquivo in arquivos
    ])

    resumo_codeshare = []

    for arquivo in arquivos:
        if "Codeshare" not in cabecalhos_por_arquivo[arquivo.name]:
            continue

        dados_codeshare = pd.read_csv(
            arquivo,
            sep=";",
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=False,
            usecols=["Codeshare"],
        )

        coluna = dados_codeshare["Codeshare"]
        preenchidos = coluna.fillna("").str.strip().ne("")

        resumo_codeshare.append({
            "arquivo": arquivo.name,
            "registros": len(coluna),
            "codeshare_preenchido": int(preenchidos.sum()),
            "exemplos": coluna[preenchidos].drop_duplicates().head(5).tolist(),
        })

    resumo_codeshare = pd.DataFrame(
        resumo_codeshare,
        columns=["arquivo", "registros", "codeshare_preenchido", "exemplos"],
    )
    print("Total de registros com Codeshare preenchido:",
          int(resumo_codeshare["codeshare_preenchido"].sum()))

    partes = []

    for arquivo in arquivos:
        df_mes = pd.read_csv(
            arquivo,
            sep=";",
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=False,
        )

        df_mes["codeshare_presente_no_arquivo"] = (
            "Codeshare" in cabecalhos_por_arquivo[arquivo.name]
        )
        if "Codeshare" not in df_mes.columns:
            df_mes["Codeshare"] = pd.NA
        df_mes["arquivo_origem"] = arquivo.name
        df_mes["linha_origem"] = range(2, len(df_mes) + 2)
        df_mes["ano_origem"] = ano_origem
        df_mes["data_carga"] = pd.Timestamp(inicio_execucao)
        df_mes["pipeline"] = "ETL"
        df_mes["versao_contrato"] = "1.1"
        partes.append(df_mes)

    df_bruta = pd.concat(partes, ignore_index=True, sort=False)
    del partes, df_mes

    if df_bruta.duplicated(subset=["arquivo_origem", "linha_origem"]).any():
        raise ValueError("Existem identificadores de origem repetidos na extração.")

    print(f"Total de registros: {len(df_bruta):,}")
    print(f"Total de colunas, incluindo metadados: {len(df_bruta.columns)}")

    contagens_pandas = df_bruta.groupby("arquivo_origem").size()
    inventario["registros_pandas"] = inventario["arquivo"].map(contagens_pandas).fillna(0).astype("int64")
    exigir(inventario["registros_csv"].equals(inventario["registros_pandas"]),
           "Contagem divergente entre leitor CSV e Pandas.")
    print("Conferência estrutural e de contagens concluída.")

    auditoria_esquema = resumo_codeshare.copy()
    auditoria_esquema["ano_origem"] = ano_origem
    auditoria_esquema["tipo_ocorrencia"] = "VARIACAO_ESQUEMA_CODESHARE"
    auditoria_esquema["decisao"] = (
        "Preservar na base bruta e auditar; manter os 20 campos comuns do contrato"
    )

    mascara_duplicadas = df_bruta.duplicated(
        subset=colunas_comuns,
        keep=False,
    )
    candidatas_duplicatas = df_bruta.loc[mascara_duplicadas].copy()

    quantidade_excedentes = int(
        df_bruta.duplicated(subset=colunas_comuns, keep="first").sum()
    )

    comparacao_codeshare = (
        candidatas_duplicatas
        .groupby(colunas_comuns, dropna=False, sort=False)["Codeshare"]
        .nunique(dropna=False)
        .rename("quantidade_valores_codeshare")
        .reset_index()
    )
    variacoes_codeshare = comparacao_codeshare.loc[
        comparacao_codeshare["quantidade_valores_codeshare"] > 1
    ].copy()

    resumo_duplicatas = pd.DataFrame([{
        "ano_origem": ano_origem,
        "registros_brutos": len(df_bruta),
        "registros_envolvidos": len(candidatas_duplicatas),
        "grupos_repetidos": len(comparacao_codeshare),
        "ocorrencias_excedentes": quantidade_excedentes,
        "grupos_com_variacao_codeshare": len(variacoes_codeshare),
    }])

    print("Registros envolvidos em repetições:", len(candidatas_duplicatas))
    print("Grupos repetidos:", len(comparacao_codeshare))
    print("Ocorrências excedentes:", quantidade_excedentes)
    print("Grupos com variação em Codeshare:", len(variacoes_codeshare))

    if not variacoes_codeshare.empty:
        auditoria_variacoes_codeshare = candidatas_duplicatas.merge(
            variacoes_codeshare,
            on=colunas_comuns,
            how="inner",
            validate="many_to_one",
        )
        print("Revise estas variações antes de excluir ocorrências repetidas.")
    else:
        auditoria_variacoes_codeshare = candidatas_duplicatas.iloc[0:0].copy()
        print("Nenhum grupo repetido apresentou variação em Codeshare.")

    df_ordenada = df_bruta.sort_values(
        ["arquivo_origem", "linha_origem"],
        kind="stable",
    )

    mascara_excedentes = df_ordenada.duplicated(
        subset=colunas_comuns,
        keep="first",
    )

    df_sem_duplicatas = df_ordenada.loc[~mascara_excedentes].copy()

    # Grupos seguem a primeira origem na ordem estável. Codeshare não compõe a chave.
    grupos = df_ordenada.groupby(colunas_comuns, dropna=False, sort=False)
    df_ordenada["grupo_duplicata_id"] = grupos.ngroup().add(1).map(lambda n: f"2021-{n:07d}")
    df_ordenada["quantidade_ocorrencias"] = grupos["linha_origem"].transform("size")
    representantes = df_ordenada.loc[~mascara_excedentes,
        ["grupo_duplicata_id", "arquivo_origem", "linha_origem"]].rename(columns={
            "arquivo_origem": "arquivo_preservado", "linha_origem": "linha_preservada",
        })
    df_duplicatas = df_ordenada.loc[mascara_excedentes].merge(
        representantes, on="grupo_duplicata_id", how="left", validate="many_to_one",
    )
    textos_excedentes = padronizar_textos(df_duplicatas)
    motivos_excedentes = motivos_obrigatorios(textos_excedentes, converter_tipos(textos_excedentes))
    df_duplicatas["motivo_rejeicao_diagnostico"] = motivos_excedentes
    df_duplicatas["invalido_diagnostico"] = motivos_excedentes.map(bool).astype(bool)
    intersecao_excedentes_invalidos = int(df_duplicatas["invalido_diagnostico"].sum())

    if len(df_bruta) != len(df_sem_duplicatas) + len(df_duplicatas):
        raise ValueError("Falha na reconciliação da deduplicação.")

    print("Registros brutos:", len(df_bruta))
    print("Excedentes separados:", len(df_duplicatas))
    print("Registros após deduplicação:", len(df_sem_duplicatas))

    df_padronizada = padronizar_textos(df_sem_duplicatas)
    mascara_pos_trim_upper = df_padronizada.duplicated(
        subset=colunas_canonicas, keep=False
    )
    duplicatas_pos_trim_upper = df_padronizada.loc[mascara_pos_trim_upper].copy()
    excedentes_pos_trim_upper = int(df_padronizada.duplicated(
        subset=colunas_canonicas, keep="first"
    ).sum())

    print("Registros na camada padronizada:", len(df_padronizada))
    print("Excedentes potenciais somente após TRIM/UPPER:", excedentes_pos_trim_upper)
    print("Essas repetições são auditadas; não são removidas automaticamente.")

    df_convertida = converter_tipos(df_padronizada)
    perfil_conversoes = pd.DataFrame([
        {
            "campo": campo,
            "preenchidos_na_fonte": int(df_padronizada[campo].notna().sum()),
            "nulos_na_fonte": int(df_padronizada[campo].isna().sum()),
            "preenchidos_nao_convertidos": int((
                df_padronizada[campo].notna() & df_convertida[campo].isna()
            ).sum()),
        }
        for campo in ["partida_prevista", "partida_real", "chegada_prevista",
                      "chegada_real", "referencia", "numero_assentos"]
    ])

    motivos_rejeicao = motivos_obrigatorios(df_padronizada, df_convertida)
    mascara_rejeicao = motivos_rejeicao.map(bool).astype(bool)
    df_rejeicoes = com_originais(df_convertida, df_sem_duplicatas).loc[mascara_rejeicao].copy()
    df_rejeicoes["motivo_rejeicao"] = motivos_rejeicao.loc[mascara_rejeicao]
    df_tratada = df_convertida.loc[~mascara_rejeicao].copy()
    vra_anomalias = auditar_opcionais(df_sem_duplicatas, df_padronizada, df_convertida)

    motivos_detalhados = (
        df_rejeicoes[metadados + ["motivo_rejeicao"]]
        .explode("motivo_rejeicao")
        .rename(columns={"motivo_rejeicao": "motivo"})
    )
    contagem_motivos = (
        motivos_detalhados.groupby("motivo").size()
        .rename("quantidade").reset_index()
        .sort_values(["quantidade", "motivo"], ascending=[False, True])
    )

    print("Registros rejeitados:", len(df_rejeicoes))
    print("Registros elegíveis:", len(df_tratada))
    print("Ocorrências na auditoria de anomalias:", len(vra_anomalias))

    df_tratada = calcular_metricas(df_tratada)
    situacao_voo = (
        df_tratada.groupby("situacao_voo", dropna=False).size()
        .rename("quantidade").reset_index()
        .sort_values("quantidade", ascending=False)
    )
    mascara_atipicos = df_tratada["partida_atipica_flag"] | df_tratada["chegada_atipica_flag"]
    vra_atipicos = df_tratada.loc[
        mascara_atipicos,
        metadados + ["numero_voo", "partida_prevista", "partida_real", "chegada_prevista",
                     "chegada_real", "diferenca_partida_min", "diferenca_chegada_min"],
    ].copy()
    df_tratada["partida_ano_diverge_flag"] = df_tratada["partida_prevista"].dt.year.ne(ano_origem)
    mascara_fora_ano = df_tratada["partida_ano_diverge_flag"]
    partidas_previstas_fora_ano = df_tratada.loc[mascara_fora_ano].copy()

    print("Partidas com diferença absoluta >24h:", int(df_tratada["partida_atipica_flag"].sum()))
    print("Chegadas com diferença absoluta >24h:", int(df_tratada["chegada_atipica_flag"].sum()))

    vra_conflitos_codigo = conflitos_descricao(df_tratada)
    excedentes_apos_padronizacao = int(df_convertida.duplicated(
        subset=colunas_canonicas, keep="first"
    ).sum())
    duplicatas_apos_padronizacao = df_convertida.loc[
        df_convertida.duplicated(subset=colunas_canonicas, keep=False)
    ].copy()
    qualidade_colunas = pd.DataFrame({
        "campo": df_convertida.columns,
        "quantidade_nulos": df_convertida.isna().sum().to_numpy(),
    })
    print("Códigos com descrições conflitantes:",
          len(vra_conflitos_codigo[["tipo", "codigo"]].drop_duplicates()))
    print("Excedentes potenciais após conversão:", excedentes_apos_padronizacao)

    resumo_qualidade = pd.DataFrame([{
        "ano_origem": ano_origem,
        "bruta": len(df_bruta),
        "duplicatas_excedentes": len(df_duplicatas),
        "intersecao_excedentes_duplicados_invalidos": intersecao_excedentes_invalidos,
        "rejeicoes": len(df_rejeicoes),
        "tratada": len(df_tratada),
        "grupos_duplicados": len(comparacao_codeshare),
        "registros_envolvidos_duplicatas": len(candidatas_duplicatas),
        "duplicatas_apos_trim_upper": excedentes_pos_trim_upper,
        "duplicatas_apos_padronizacao": excedentes_apos_padronizacao,
        "partidas_atipicas": int(df_tratada["partida_atipica_flag"].sum()),
        "chegadas_atipicas": int(df_tratada["chegada_atipica_flag"].sum()),
        "partidas_reais_nulas": int(df_tratada["partida_real"].isna().sum()),
        "chegadas_reais_nulas": int(df_tratada["chegada_real"].isna().sum()),
        "ocorrencias_anomalias": len(vra_anomalias),
        "partidas_previstas_fora_do_ano": len(partidas_previstas_fora_ano),
        "codigos_com_conflito": len(vra_conflitos_codigo[["tipo", "codigo"]].drop_duplicates()),
        "arquivos_com_codeshare": int(conferencia_cabecalhos["codeshare_presente"].sum()),
        "codeshare_preenchido": int(resumo_codeshare["codeshare_preenchido"].sum()),
        "executado_em": datetime.now(timezone.utc).isoformat(),
    }])

    mensal = inventario[["arquivo", "registros_csv"]].rename(
        columns={"arquivo": "arquivo_origem", "registros_csv": "bruta"}
    ).copy()
    for nome, base in [("duplicatas", df_duplicatas), ("rejeicoes", df_rejeicoes), ("tratada", df_tratada)]:
        contagem = base.groupby("arquivo_origem").size()
        mensal[nome] = mensal["arquivo_origem"].map(contagem).fillna(0).astype("int64")
    mensal["conciliada"] = mensal["bruta"].eq(mensal["duplicatas"] + mensal["rejeicoes"] + mensal["tratada"])




    etl_log_arquivos = inventario.rename(columns={"arquivo": "arquivo_origem"}).merge(
        mensal.drop(columns="bruta"), on="arquivo_origem", validate="one_to_one",
    )
    for nome, base in [("ocorrencias_anomalias", vra_anomalias),
                       ("excedentes_invalidos", df_duplicatas.loc[df_duplicatas["invalido_diagnostico"]])]:
        contagens = base.groupby("arquivo_origem").size()
        etl_log_arquivos[nome] = etl_log_arquivos["arquivo_origem"].map(contagens).fillna(0).astype("int64")
    etl_log_arquivos["data_carga"] = inicio_execucao
    etl_log_arquivos["pipeline"] = "ETL"
    etl_log_arquivos["versao_contrato"] = "1.1"

    exigir(len(df_bruta) == len(df_duplicatas) + len(df_rejeicoes) + len(df_tratada),
           "A conciliação anual falhou.")
    exigir(mensal["conciliada"].all(), "A conciliação mensal falhou.")
    exigir(not df_tratada[["companhia_icao", "aeroporto_origem", "aeroporto_destino",
                           "partida_prevista", "chegada_prevista"]].isna().any().any(),
           "A camada tratada contém campos obrigatórios nulos.")

    chaves_tratada = pd.MultiIndex.from_frame(df_tratada[["arquivo_origem", "linha_origem"]])
    chaves_rejeicoes = pd.MultiIndex.from_frame(df_rejeicoes[["arquivo_origem", "linha_origem"]])
    chaves_duplicatas = pd.MultiIndex.from_frame(df_duplicatas[["arquivo_origem", "linha_origem"]])
    exigir(chaves_tratada.is_unique, "A camada tratada tem origem repetida.")
    exigir(chaves_tratada.intersection(chaves_rejeicoes).empty, "Há tratados também rejeitados.")
    exigir(chaves_tratada.intersection(chaves_duplicatas).empty, "Há excedentes na camada tratada.")
    exigir(chaves_rejeicoes.intersection(chaves_duplicatas).empty, "Há excedentes contados como rejeições.")

    for evento in ["partida", "chegada"]:
        diferenca = df_tratada[f"diferenca_{evento}_min"]
        atraso = df_tratada[f"atraso_{evento}_min"]
        sem_real = df_tratada[f"{evento}_real"].isna()
        exigir(diferenca.isna().equals(sem_real), f"Nulos inconsistentes na diferença de {evento}.")
        exigir(atraso.isna().equals(sem_real), f"Nulos inconsistentes no atraso de {evento}.")
        exigir((atraso.dropna() >= 0).all(), f"Atraso negativo em {evento}.")
        minutos = diferenca.to_numpy(dtype="int64", na_value=np.iinfo("int64").min)
        intervalos = pd.Series(
            minutos.astype("timedelta64[m]").astype("timedelta64[us]"),
            index=df_tratada.index,
        )
        reconstruida = df_tratada[f"{evento}_real"] - intervalos
        exigir(reconstruida.loc[~sem_real].equals(df_tratada.loc[~sem_real, f"{evento}_prevista"]),
               f"A diferença não reconstrói o horário previsto de {evento}.")

    exigir(df_padronizada["numero_voo"].equals(
        df_sem_duplicatas["Número Voo"].astype("string").str.strip().replace("", pd.NA)
    ), "O número do voo foi alterado além da padronização de espaços e vazios.")
    exigir(all(sha256_arquivo(arquivo) == hashes_entrada[arquivo.name] for arquivo in arquivos),
           "Algum CSV original foi alterado.")

    referencia_elt = pd.Series({"bruta": 632148, "duplicatas_excedentes": 0,
                                "rejeicoes": 25511, "tratada": 606637}, name="elt_informado")
    comparativo_elt = resumo_qualidade.iloc[0][referencia_elt.index].rename("etl_medido").to_frame()
    comparativo_elt["elt_informado"] = referencia_elt
    comparativo_elt["totais_iguais"] = comparativo_elt["etl_medido"].eq(comparativo_elt["elt_informado"])
    validacao_concluida = True

    print("Conciliações e verificações internas concluídas.")
    print("Comparação dos hashes e dos valores por registro com o ELT: pendente.")

    arquivos_exportados = []


    def exportar_tabela(nome, base, comprimir=True):
        destino = PASTA_SAIDA / (nome + (".csv.gz" if comprimir else ".csv"))
        tabela = base.copy()
        for campo in tabela.select_dtypes(include=["object"]).columns:
            if tabela[campo].map(lambda valor: isinstance(valor, list)).any():
                tabela[campo] = tabela[campo].map(
                    lambda valor: json.dumps(valor, ensure_ascii=False) if isinstance(valor, list) else valor
                )
        tabela.to_csv(destino, index=False, encoding="utf-8", na_rep="",
                      compression="gzip" if comprimir else None)
        arquivos_exportados.append(destino)


    if EXPORTAR_EVIDENCIAS:
        exigir(validacao_concluida, "Execute a validação antes de exportar.")
        PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
        inventario = preservar_brutos(arquivos, inventario, PASTA_SAIDA)
        etl_log_arquivos["sha256_copia"] = etl_log_arquivos["sha256"]
        etl_log_arquivos["copia_bruta_verificada"] = True
        for nome, base in [
            ("vra_tratada", df_tratada),
            ("vra_rejeicoes", df_rejeicoes),
            ("vra_duplicatas_excluidas", df_duplicatas),
            ("vra_anomalias", vra_anomalias),
            ("vra_atipicos", vra_atipicos),
            ("vra_possiveis_duplicatas_padronizacao", duplicatas_pos_trim_upper),
            ("duplicatas_apos_padronizacao", duplicatas_apos_padronizacao),
            ("partidas_previstas_fora_ano", partidas_previstas_fora_ano),
        ]:
            exportar_tabela(nome, base)
        # Remove somente o nome legado de uma auditoria gerada por este pipeline.
        legado = PASTA_SAIDA / "duplicatas_pos_trim_upper.csv.gz"
        if legado.is_file():
            legado.unlink()
        for nome, base in [
            ("inventario_arquivos", inventario), ("resumo_qualidade", resumo_qualidade),
            ("mensal", mensal), ("etl_log_arquivos", etl_log_arquivos),
            ("motivos_rejeicao", contagem_motivos),
            ("situacao_voo", situacao_voo), ("vra_conflitos_codigo", vra_conflitos_codigo),
            ("auditoria_esquema", auditoria_esquema), ("qualidade_colunas", qualidade_colunas),
            ("perfil_conversoes", perfil_conversoes),
            ("comparativo_totais_elt_informados", comparativo_elt.reset_index(names="indicador")),
        ]:
            exportar_tabela(nome, base, comprimir=False)
        if EXPORTAR_BASE_BRUTA:
            exportar_tabela("vra_bruta", df_bruta)

        resumo_dict = json.loads(resumo_qualidade.to_json(orient="records"))[0]
        etl_resumo = {
            "indicadores": resumo_dict,
            "conciliacao": {
                "equacao": "bruta = duplicatas_excedentes + rejeicoes + tratada",
                "bruta": len(df_bruta), "duplicatas_excedentes": len(df_duplicatas),
                "rejeicoes": len(df_rejeicoes), "tratada": len(df_tratada),
                "conciliada": True,
                "observacao": "Excedentes inválidos são diagnósticos; não são subtraídos outra vez.",
            },
        }
        (PASTA_SAIDA / "etl_resumo.json").write_text(
            json.dumps(etl_resumo, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        metadados_execucao = {
            "autor": "Arthur", "pipeline": "ETL", "ano_origem": ano_origem,
            "versao_contrato": "1.1", "inicio_utc": inicio_execucao,
            "fim_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version.split()[0],
            "pandas": pd.__version__, "transformacoes": "Python/Pandas antes da carga",
            "resumo": resumo_dict,
            "csvs_originais_intactos": True,
            "comparacao_elt": "Totais informados comparados; hashes e valores por registro pendentes.",
            "carga_postgresql": "A etapa seguinte informa se a carga foi executada.",
            "modelagem_dimensional": "Pendente da integração do grupo.",
        }
        (PASTA_SAIDA / "metadados_execucao.json").write_text(
            json.dumps(metadados_execucao, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        texto_explicacao = f"""# ETL VRA/ANAC 2021 — execução local

    Responsável: Arthur. Referências: contrato v1.1 e regras/saídas do ELT 2021 de Murilo Acioli.

    Os 12 originais são copiados byte a byte para vra_bruta/, com manifesto SHA-256.
    --export-raw adiciona uma tabela regenerada; ela não substitui as cópias originais.
    Rastreabilidade: arquivo, registro lógico (cabeçalho = 1), ano, data_carga UTC,
    pipeline=ETL e versao_contrato=1.1. Horários dos voos mantêm o fuso da fonte.
    Rejeições e anomalias incluem campos canônicos e valores originais bruto__*.
    motivo_rejeicao é uma lista JSON no CSV; anomalias identificam o campo problemático.
    partida_ano_diverge_flag sinaliza o cruzamento de ano sem excluir o registro.
    etl_log_arquivos.csv reúne as contagens e a conciliação por arquivo.

    O Python lê os CSVs como texto e compara os 20 campos brutos antes da padronização.
    Codeshare permanece na base bruta e sua presença é auditada por arquivo.
    As transformações, rejeições, métricas e conflitos são calculados em Python/Pandas.
    A carga opcional recebe os dados já tratados no schema {SCHEMA_ETL}.

    Reconciliação medida: {len(df_bruta)} brutos = {len(df_duplicatas)} excedentes +
    {len(df_rejeicoes)} rejeitados + {len(df_tratada)} tratados.

    Vazios tornam-se nulos; códigos e situações ficam em maiúsculas; descrições preservam a grafia.
    Número do voo continua texto. Referência aceita ISO e data brasileira à meia-noite.
    Somente problemas nos cinco campos obrigatórios provocam rejeição.
    Opcionais inválidos são auditados. Todos os motivos de cada rejeição são preservados.
    Diferenças usam minutos com sinal; atrasos são não negativos; sem real, métricas são nulas.
    Diferenças absolutas acima de 24 horas são sinalizadas e preservadas, sem correção automática.
    Não foi aplicada conversão de fuso. Conflitos de descrições são reportados sem escolher um nome.

    Limites: dimensões e Fato compartilhadas ainda dependem da integração do grupo.
    A igualdade dos totais com o ELT não comprova equivalência por registro.
    Compare os hashes do inventário e a saída tratada do parceiro antes de concluir a conciliação.
    O texto colado do ELT não incluía o corpo completo de suas funções SQL.
    As regras foram implementadas pelo contrato e pelo comportamento documentado.

    A etapa PostgreSQL permanece desativada por padrão. Veja status_carga_postgresql.json.
    Os CSVs originais não foram sobrescritos. Evidências completas ficam em dados/processados/2021/etl/.
    """
        (PASTA_SAIDA / "LEIA_ME.md").write_text(texto_explicacao, encoding="utf-8")
        print(f"Evidências exportadas para: {PASTA_SAIDA}")
        print("Tabelas exportadas:", len(arquivos_exportados))
    else:
        print("Exportação desativada na configuração.")

    status_carga_postgresql = {"status": "nao_executada", "schema": schema}
    if load_database:
        (PASTA_SAIDA / "status_carga_postgresql.json").write_text(json.dumps({
            "status": "em_execucao", "schema": schema, "execucao_id": inicio_execucao,
        }, indent=2), encoding="utf-8")
        status_carga_postgresql = carregar_postgresql({
            "vra_bruta": df_bruta,
            "vra_possiveis_duplicatas_padronizacao": duplicatas_pos_trim_upper,
            "etl_log_arquivos": etl_log_arquivos,
            "vra_tratada": df_tratada,
            "vra_rejeicoes": df_rejeicoes,
            "vra_duplicatas_excluidas": df_duplicatas,
            "vra_anomalias": vra_anomalias,
            "vra_conflitos_codigo": vra_conflitos_codigo,
            "inventario_arquivos": inventario,
            "resumo_qualidade": resumo_qualidade,
        }, schema=schema, replace=replace)
    else:
        print("Carga PostgreSQL não executada; use load_database=True para habilitar.")
    (PASTA_SAIDA / "status_carga_postgresql.json").write_text(
        json.dumps(status_carga_postgresql, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "resumo": json.loads(resumo_qualidade.to_json(orient="records"))[0],
        "carga_postgresql": status_carga_postgresql,
        "pasta_saida": str(PASTA_SAIDA),
        "arquivos": sorted(p.name for p in PASTA_SAIDA.iterdir() if p.is_file()),
    }

def run_etl(input_dir, output_dir, *, load_database=False, replace=False,
            schema="etl_2021", export_raw=False):
    """Executa o ETL e registra o status desta execução, inclusive em caso de falha."""
    exigir(not replace or load_database, "replace=True exige load_database=True.")
    exigir(schema == "etl_2021", "Este pipeline usa somente o schema etl_2021.")
    pasta = Path(output_dir).resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    inicio = datetime.now(timezone.utc).isoformat()
    status = {"status": "pendente" if load_database else "nao_executada",
              "schema": schema, "execucao_id": inicio, "transacao_confirmada": False}
    caminho_status = pasta / "status_carga_postgresql.json"
    caminho_meta = pasta / "metadados_execucao.json"

    def registrar(estado, erro_tipo=None):
        status["atualizado_em_utc"] = datetime.now(timezone.utc).isoformat()
        caminho_status.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        meta = json.loads(caminho_meta.read_text()) if caminho_meta.exists() else {}
        if meta.get("inicio_utc") != inicio:
            meta = {"pipeline": "ETL", "ano_origem": 2021, "versao_contrato": "1.1", "inicio_utc": inicio}
        meta.update(status_execucao=estado, carga_postgresql=status, fim_utc=status["atualizado_em_utc"])
        if erro_tipo:
            meta["erro_tipo"] = erro_tipo
        caminho_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    registrar("em_execucao")
    try:
        resultado = _executar_etl(input_dir, output_dir, load_database=load_database,
                                 replace=replace, schema=schema, export_raw=export_raw,
                                 inicio_execucao=inicio)
    except Exception as erro:
        atual = json.loads(caminho_status.read_text())
        status["status"] = ("falhou" if atual["status"] == "em_execucao" else
                            "nao_iniciada" if load_database else "nao_executada")
        status["erro_tipo"] = type(erro).__name__  # Não serializar mensagens/credenciais da conexão.
        registrar("falhou", type(erro).__name__)
        raise
    status.update(resultado["carga_postgresql"])
    registrar("concluida")
    resultado["carga_postgresql"] = status
    return resultado


def main():
    parser = argparse.ArgumentParser(description="ETL de 2021 com tratamento em Python/Pandas.")
    parser.add_argument("--input-dir", required=True, help="Pasta dos 12 CSVs VRA_2021_MM.csv")
    parser.add_argument("--output-dir", required=True, help="Pasta das evidências geradas")
    parser.add_argument("--load-db", action="store_true", help="Carrega no PostgreSQL configurado no .env")
    parser.add_argument("--replace", action="store_true", help="Substitui somente tabelas deste pipeline no schema etl_2021")
    parser.add_argument("--export-raw", action="store_true", help="Exporta também a tabela bruta regenerada com metadados (além das cópias originais)")
    args = parser.parse_args()
    if args.replace and not args.load_db:
        parser.error("--replace exige --load-db")
    resultado = run_etl(args.input_dir, args.output_dir, load_database=args.load_db,
                        replace=args.replace, export_raw=args.export_raw)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
