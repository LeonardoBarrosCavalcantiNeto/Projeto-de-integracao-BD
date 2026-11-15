#!/usr/bin/env python3
"""ETL VRA/ANAC 2019: CSV -> padronização/validação -> PostgreSQL (esquema estrela).

A deduplicação é feita depois da padronização, considerando os 20 atributos
canônicos e os 12 arquivos mensais em conjunto. A primeira ocorrência é mantida;
as ocorrências excedentes são exportadas para duplicatas_removidas.csv.gz.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import gc
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ANO = 2019
PIPELINE = "ETL"
SEPARADOR = ";"
ENCODING = "utf-8-sig"
BATCH_SIZE = 500  # 500 x 30 colunas = 15.000 parâmetros por INSERT multi-row.

MAPA_COLUNAS = {
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
CANONICAL_COLS = list(MAPA_COLUNAS.values())
TIMESTAMP_COLS = ["partida_prevista", "partida_real", "chegada_prevista", "chegada_real"]
REQUIRED_COLS = [
    "companhia_icao", "numero_voo", "tipo_linha", "aeroporto_origem",
    "aeroporto_destino", "partida_prevista", "chegada_prevista",
    "situacao_voo", "referencia",
]
TABLES = [
    "fato_voo", "rejeicoes", "log_carga_arquivo", "dim_equipamento",
    "dim_tipo_linha", "dim_justificativa", "dim_situacao_voo",
    "dim_aeroporto", "dim_companhia_aerea", "dim_tempo",
]


def _safe_str_series(series: pd.Series) -> pd.Series:
    """Remove espaços externos e transforma texto vazio em NA."""
    values = series.astype("string").str.strip()
    return values.mask(values.eq(""), pd.NA)


def _to_iso_timestamp(series: pd.Series) -> pd.Series:
    return series.dt.strftime("%Y-%m-%d %H:%M:%S").astype("string")


def _to_iso_date(series: pd.Series) -> pd.Series:
    return series.dt.strftime("%Y-%m-%d").astype("string")


def _build_dimension(values: Iterable[str], id_name: str, value_name: str,
                     unknown: bool = False) -> pd.DataFrame:
    vals = sorted({str(v) for v in values if pd.notna(v)})
    rows: list[tuple[int, str]] = []
    if unknown:
        if "DESCONHECIDO" in vals:
            raise ValueError(f"O valor reservado DESCONHECIDO já existe em {value_name}.")
        rows.append((0, "DESCONHECIDO"))
    rows.extend((i, val) for i, val in enumerate(vals, start=1))
    return pd.DataFrame(rows, columns=[id_name, value_name])


def _resolve_code_description(
    pairs: pd.DataFrame, code_col: str, desc_col: str, dimension_name: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monta dimensão por chave natural e retorna conflitos sem escolher ao acaso."""
    pairs = pairs[[code_col, desc_col]].copy()
    pairs[code_col] = _safe_str_series(pairs[code_col]).str.upper()
    pairs[desc_col] = _safe_str_series(pairs[desc_col])
    pairs = pairs[pairs[code_col].notna()]
    non_null = pairs.dropna(subset=[desc_col])
    counts = non_null.groupby(code_col, sort=False)[desc_col].nunique()
    conflict_codes = set(counts[counts > 1].index.tolist())
    if conflict_codes:
        conflicts = (
            non_null[non_null[code_col].isin(conflict_codes)]
            .drop_duplicates([code_col, desc_col])
            .rename(columns={code_col: "codigo_natural", desc_col: "descricao_conflitante"})
        )
        conflicts.insert(0, "dimensao", dimension_name)
    else:
        conflicts = pd.DataFrame(columns=["dimensao", "codigo_natural", "descricao_conflitante"])
    codes = pairs[[code_col]].drop_duplicates().sort_values(code_col).reset_index(drop=True)
    desc_map = non_null.drop_duplicates([code_col, desc_col]).drop_duplicates(code_col).set_index(code_col)[desc_col]
    codes[desc_col] = codes[code_col].map(desc_map).fillna("DESCONHECIDO")
    return codes.rename(columns={code_col: "codigo_natural", desc_col: "descricao"}), conflicts


def _write_gzip_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        path, index=False, encoding="utf-8",
        compression={"method": "gzip", "compresslevel": 1, "mtime": 1}, na_rep=""
    )


def _normalizar_arquivo(path: Path, carga_utc: str) -> pd.DataFrame:
    raw = pd.read_csv(
        path, sep=SEPARADOR, encoding=ENCODING, dtype="string",
        keep_default_na=False, low_memory=False,
    )
    expected = list(MAPA_COLUNAS.keys())
    if list(raw.columns) != expected:
        missing = sorted(set(expected) - set(raw.columns))
        extra = sorted(set(raw.columns) - set(expected))
        raise ValueError(f"Cabeçalho divergente em {path.name}. Ausentes={missing}; extras={extra}.")

    df = raw.rename(columns=MAPA_COLUNAS).copy()
    for col in CANONICAL_COLS:
        df[col] = _safe_str_series(df[col])

    for col in ["companhia_icao", "aeroporto_origem", "aeroporto_destino"]:
        df[col] = df[col].str.upper()
    for col in ["tipo_linha", "situacao_voo", "situacao_partida", "situacao_chegada"]:
        df[col] = df[col].str.upper()

    reasons: list[list[str]] = [[] for _ in range(len(df))]
    parsed_dates: dict[str, pd.Series] = {}
    for col in TIMESTAMP_COLS:
        parsed = pd.to_datetime(df[col], format="%d/%m/%Y %H:%M", errors="coerce")
        invalid = df[col].notna() & parsed.isna()
        for pos in invalid[invalid].index:
            reasons[pos].append(f"timestamp_invalido:{col}")
        parsed_dates[col] = parsed

    parsed_ref = pd.to_datetime(df["referencia"], format="%Y-%m-%d", errors="coerce")
    invalid_ref = df["referencia"].notna() & parsed_ref.isna()
    for pos in invalid_ref[invalid_ref].index:
        reasons[pos].append("data_referencia_invalida")

    for col in ["partida_prevista", "chegada_prevista"]:
        missing = parsed_dates[col].isna()
        for pos in missing[missing].index:
            reasons[pos].append(f"data_prevista_ausente:{col}")
    for col in REQUIRED_COLS:
        if col not in TIMESTAMP_COLS:
            missing = df[col].isna()
            for pos in missing[missing].index:
                reasons[pos].append(f"campo_obrigatorio_ausente:{col}")

    seats = pd.to_numeric(df["numero_assentos"], errors="coerce")
    bad_seats = df["numero_assentos"].notna() & seats.isna()
    for pos in bad_seats[bad_seats].index:
        reasons[pos].append("numero_assentos_invalido")
    # Não aceitar assentos fracionários.
    fractional_seats = seats.notna() & (seats % 1 != 0)
    for pos in fractional_seats[fractional_seats].index:
        reasons[pos].append("numero_assentos_nao_inteiro")
    seats = seats.mask(fractional_seats)

    for col in TIMESTAMP_COLS:
        df[col] = _to_iso_timestamp(parsed_dates[col])
    df["referencia"] = _to_iso_date(parsed_ref)
    df["numero_assentos"] = seats.astype("Int64")

    df["ano_origem"] = ANO
    df["arquivo_origem"] = path.name
    df["linha_origem"] = range(2, len(df) + 2)
    df["data_carga"] = carga_utc
    df["pipeline"] = PIPELINE
    df["motivo_rejeicao"] = [";".join(items) if items else pd.NA for items in reasons]
    df["status_validacao"] = df["motivo_rejeicao"].isna().map({True: "VALIDO", False: "REJEITADO"})
    return df


def _build_star(valid: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """Cria dimensões e fato a partir somente dos registros válidos e não duplicados."""
    company_pairs = valid[["companhia_icao", "companhia_nome"]].drop_duplicates().rename(
        columns={"companhia_icao": "codigo", "companhia_nome": "descricao"}
    )
    company_dim, c1 = _resolve_code_description(company_pairs, "codigo", "descricao", "dim_companhia_aerea")

    airport_pairs = pd.concat([
        valid[["aeroporto_origem", "descricao_origem"]].drop_duplicates().rename(
            columns={"aeroporto_origem": "codigo", "descricao_origem": "descricao"}),
        valid[["aeroporto_destino", "descricao_destino"]].drop_duplicates().rename(
            columns={"aeroporto_destino": "codigo", "descricao_destino": "descricao"}),
    ], ignore_index=True)
    airport_dim, c2 = _resolve_code_description(airport_pairs, "codigo", "descricao", "dim_aeroporto")
    conflicts = pd.concat([c1, c2], ignore_index=True)

    date_values = pd.concat([
        valid["partida_prevista"].str.slice(0, 10),
        valid["chegada_prevista"].str.slice(0, 10),
    ], ignore_index=True).dropna().unique()
    date_values = sorted(date_values.tolist())
    time_dim = pd.DataFrame({"data": pd.to_datetime(date_values, format="%Y-%m-%d").date})
    time_dt = pd.to_datetime(time_dim["data"])
    time_dim.insert(0, "id_tempo", time_dt.dt.strftime("%Y%m%d").astype("int64"))
    time_dim["ano"] = time_dt.dt.year.astype("int64")
    time_dim["trimestre"] = time_dt.dt.quarter.astype("int64")
    time_dim["mes"] = time_dt.dt.month.astype("int64")
    time_dim["dia"] = time_dt.dt.day.astype("int64")
    time_dim["dia_semana"] = time_dt.dt.isocalendar().day.astype("int64")
    time_dim = time_dim[["id_tempo", "data", "ano", "trimestre", "mes", "dia", "dia_semana"]]

    company_dim = company_dim.sort_values("codigo_natural").reset_index(drop=True)
    company_dim.insert(0, "id_companhia", range(1, len(company_dim) + 1))
    company_dim = company_dim.rename(columns={"codigo_natural": "companhia_icao", "descricao": "companhia_nome"})
    airport_dim = airport_dim.sort_values("codigo_natural").reset_index(drop=True)
    airport_dim.insert(0, "id_aeroporto", range(1, len(airport_dim) + 1))
    airport_dim = airport_dim.rename(columns={"codigo_natural": "aeroporto_icao", "descricao": "descricao_aeroporto"})

    situation_dim = _build_dimension(valid["situacao_voo"], "id_situacao", "situacao_voo")
    justification_dim = _build_dimension(valid["justificativa"], "id_justificativa", "justificativa", unknown=True)
    line_dim = _build_dimension(valid["tipo_linha"], "id_tipo_linha", "tipo_linha")
    equipment_dim = _build_dimension(valid["modelo_equipamento"], "id_equipamento", "modelo_equipamento", unknown=True)
    dimensions = {
        "dim_tempo": time_dim,
        "dim_companhia_aerea": company_dim,
        "dim_aeroporto": airport_dim,
        "dim_situacao_voo": situation_dim,
        "dim_justificativa": justification_dim,
        "dim_tipo_linha": line_dim,
        "dim_equipamento": equipment_dim,
    }

    company_map = dict(zip(company_dim["companhia_icao"], company_dim["id_companhia"]))
    airport_map = dict(zip(airport_dim["aeroporto_icao"], airport_dim["id_aeroporto"]))
    situation_map = dict(zip(situation_dim["situacao_voo"], situation_dim["id_situacao"]))
    justification_map = dict(zip(justification_dim["justificativa"], justification_dim["id_justificativa"]))
    line_map = dict(zip(line_dim["tipo_linha"], line_dim["id_tipo_linha"]))
    equipment_map = dict(zip(equipment_dim["modelo_equipamento"], equipment_dim["id_equipamento"]))
    time_map = dict(zip(time_dim["data"].astype(str), time_dim["id_tempo"]))

    fact = valid[CANONICAL_COLS + [
        "ano_origem", "arquivo_origem", "linha_origem", "duplicata_exata_flag"
    ]].copy().reset_index(drop=True)
    fact.insert(0, "id_voo", range(1, len(fact) + 1))
    fact["id_companhia"] = fact["companhia_icao"].map(company_map).astype("int64")
    fact["id_aeroporto_origem"] = fact["aeroporto_origem"].map(airport_map).astype("int64")
    fact["id_aeroporto_destino"] = fact["aeroporto_destino"].map(airport_map).astype("int64")
    fact["id_tempo_partida"] = fact["partida_prevista"].str.slice(0, 10).map(time_map).astype("int64")
    fact["id_tempo_chegada"] = fact["chegada_prevista"].str.slice(0, 10).map(time_map).astype("int64")
    fact["id_situacao"] = fact["situacao_voo"].map(situation_map).astype("int64")
    fact["id_justificativa"] = fact["justificativa"].astype("string").fillna("DESCONHECIDO").map(justification_map).astype("int64")
    fact["id_tipo_linha"] = fact["tipo_linha"].map(line_map).astype("int64")
    fact["id_equipamento"] = fact["modelo_equipamento"].astype("string").fillna("DESCONHECIDO").map(equipment_map).astype("int64")

    for col in TIMESTAMP_COLS:
        fact[col] = pd.to_datetime(fact[col], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    for prefix, planned, actual in [
        ("partida", "partida_prevista", "partida_real"),
        ("chegada", "chegada_prevista", "chegada_real"),
    ]:
        difference = (fact[actual] - fact[planned]).dt.total_seconds() / 60
        fact[f"diferenca_{prefix}_min"] = difference.round().astype("Int64")
        fact[f"atraso_{prefix}_min"] = difference.clip(lower=0).round().astype("Int64")
    fact["referencia"] = pd.to_datetime(fact["referencia"], format="%Y-%m-%d").dt.date
    fact["quantidade_voos"] = 1
    fact = fact[[
        "id_voo", "id_companhia", "id_aeroporto_origem", "id_aeroporto_destino",
        "id_tempo_partida", "id_tempo_chegada", "id_situacao", "id_justificativa",
        "id_tipo_linha", "id_equipamento", "numero_voo", "codigo_di", "referencia",
        "partida_prevista", "partida_real", "chegada_prevista", "chegada_real",
        "quantidade_voos", "numero_assentos", "diferenca_partida_min", "diferenca_chegada_min",
        "atraso_partida_min", "atraso_chegada_min", "situacao_partida", "situacao_chegada",
        "ano_origem", "arquivo_origem", "linha_origem", "duplicata_exata_flag",
    ]]
    return dimensions, fact, conflicts


def _sql_safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Converte NA/NaT para None, preservando valores tipados para o driver PostgreSQL."""
    safe = frame.astype(object).where(pd.notna(frame), None)
    return safe


def _postgres_engine():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return create_engine(database_url, pool_pre_ping=True, future=True)
    password = os.getenv("PGPASSWORD")
    if not password:
        raise RuntimeError(
            "Senha do PostgreSQL não encontrada. Defina PGPASSWORD no arquivo .env "
            "ou configure DATABASE_URL. Não coloque a senha diretamente no código."
        )
    sslmode = os.getenv("PGSSLMODE")
    url = URL.create(
        "postgresql+psycopg",
        username=os.getenv("PGUSER", "postgres"),
        password=password,
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        database=os.getenv("PGDATABASE", "vra_dw_2019"),
        query={"sslmode": sslmode} if sslmode else {},
    )
    return create_engine(url, pool_pre_ping=True, future=True)


def _create_postgres_database(
    engine, schema: str, dimensions: dict[str, pd.DataFrame], fact: pd.DataFrame,
    rejects: pd.DataFrame, file_log: pd.DataFrame, replace: bool = False,
) -> dict:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise ValueError("Nome de schema inválido. Use letras, números e underscore; não comece com número.")
    schema_q = f'"{schema}"'
    ddl = f"""
    CREATE TABLE {schema_q}.dim_tempo (
        id_tempo INTEGER PRIMARY KEY, data DATE NOT NULL UNIQUE,
        ano INTEGER NOT NULL, trimestre INTEGER NOT NULL, mes INTEGER NOT NULL,
        dia INTEGER NOT NULL, dia_semana INTEGER NOT NULL
    );
    CREATE TABLE {schema_q}.dim_companhia_aerea (
        id_companhia INTEGER PRIMARY KEY, companhia_icao TEXT NOT NULL UNIQUE,
        companhia_nome TEXT NOT NULL
    );
    CREATE TABLE {schema_q}.dim_aeroporto (
        id_aeroporto INTEGER PRIMARY KEY, aeroporto_icao TEXT NOT NULL UNIQUE,
        descricao_aeroporto TEXT NOT NULL
    );
    CREATE TABLE {schema_q}.dim_situacao_voo (
        id_situacao INTEGER PRIMARY KEY, situacao_voo TEXT NOT NULL UNIQUE
    );
    CREATE TABLE {schema_q}.dim_justificativa (
        id_justificativa INTEGER PRIMARY KEY, justificativa TEXT NOT NULL UNIQUE
    );
    CREATE TABLE {schema_q}.dim_tipo_linha (
        id_tipo_linha INTEGER PRIMARY KEY, tipo_linha TEXT NOT NULL UNIQUE
    );
    CREATE TABLE {schema_q}.dim_equipamento (
        id_equipamento INTEGER PRIMARY KEY, modelo_equipamento TEXT NOT NULL UNIQUE
    );
    CREATE TABLE {schema_q}.fato_voo (
        id_voo BIGINT PRIMARY KEY,
        id_companhia INTEGER NOT NULL REFERENCES {schema_q}.dim_companhia_aerea(id_companhia),
        id_aeroporto_origem INTEGER NOT NULL REFERENCES {schema_q}.dim_aeroporto(id_aeroporto),
        id_aeroporto_destino INTEGER NOT NULL REFERENCES {schema_q}.dim_aeroporto(id_aeroporto),
        id_tempo_partida INTEGER NOT NULL REFERENCES {schema_q}.dim_tempo(id_tempo),
        id_tempo_chegada INTEGER NOT NULL REFERENCES {schema_q}.dim_tempo(id_tempo),
        id_situacao INTEGER NOT NULL REFERENCES {schema_q}.dim_situacao_voo(id_situacao),
        id_justificativa INTEGER NOT NULL REFERENCES {schema_q}.dim_justificativa(id_justificativa),
        id_tipo_linha INTEGER NOT NULL REFERENCES {schema_q}.dim_tipo_linha(id_tipo_linha),
        id_equipamento INTEGER NOT NULL REFERENCES {schema_q}.dim_equipamento(id_equipamento),
        numero_voo TEXT NOT NULL, codigo_di TEXT, referencia DATE NOT NULL,
        partida_prevista TIMESTAMP NOT NULL, partida_real TIMESTAMP,
        chegada_prevista TIMESTAMP NOT NULL, chegada_real TIMESTAMP,
        quantidade_voos SMALLINT NOT NULL CHECK (quantidade_voos = 1),
        numero_assentos INTEGER, diferenca_partida_min INTEGER,
        diferenca_chegada_min INTEGER, atraso_partida_min INTEGER,
        atraso_chegada_min INTEGER, situacao_partida TEXT, situacao_chegada TEXT,
        ano_origem INTEGER NOT NULL, arquivo_origem TEXT NOT NULL, linha_origem INTEGER NOT NULL,
        duplicata_exata_flag BOOLEAN NOT NULL
    );
    CREATE TABLE {schema_q}.rejeicoes (
        arquivo_origem TEXT NOT NULL, linha_origem BIGINT NOT NULL,
        ano_origem INTEGER NOT NULL, motivo_rejeicao TEXT NOT NULL,
        numero_voo TEXT, companhia_icao TEXT, partida_prevista TEXT,
        chegada_prevista TEXT, referencia TEXT, situacao_voo TEXT
    );
    CREATE TABLE {schema_q}.log_carga_arquivo (
        arquivo_origem TEXT PRIMARY KEY, ano_origem INTEGER NOT NULL,
        linhas_lidas BIGINT NOT NULL, linhas_validas BIGINT NOT NULL,
        linhas_rejeitadas BIGINT NOT NULL, duplicados_sinalizados BIGINT NOT NULL,
        duplicados_removidos BIGINT NOT NULL, cancelados BIGINT NOT NULL,
        nao_informados BIGINT NOT NULL, linhas_carregadas BIGINT NOT NULL,
        tamanho_bytes BIGINT NOT NULL, data_carga TIMESTAMPTZ NOT NULL, pipeline TEXT NOT NULL
    );
    """
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_q}"))
        existing = conn.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = ANY(:tables)"
        ), {"schema": schema, "tables": TABLES}).scalar_one()
        if existing and not replace:
            raise RuntimeError(
                f"Já existem {existing} tabelas ETL no schema {schema}. "
                "Para recriá-las e substituir a carga anterior, execute com --replace."
            )
        if replace:
            for table in TABLES:
                conn.execute(text(f"DROP TABLE IF EXISTS {schema_q}.\"{table}\" CASCADE"))
        conn.execute(text(ddl))

        dimension_order = [
            "dim_tempo", "dim_companhia_aerea", "dim_aeroporto", "dim_situacao_voo",
            "dim_justificativa", "dim_tipo_linha", "dim_equipamento",
        ]
        for table in dimension_order:
            _sql_safe_frame(dimensions[table]).to_sql(
                table, con=conn, schema=schema, if_exists="append", index=False,
                method="multi", chunksize=BATCH_SIZE,
            )
        _sql_safe_frame(fact).to_sql(
            "fato_voo", con=conn, schema=schema, if_exists="append", index=False,
            method="multi", chunksize=BATCH_SIZE,
        )
        reject_cols = [
            "arquivo_origem", "linha_origem", "ano_origem", "motivo_rejeicao",
            "numero_voo", "companhia_icao", "partida_prevista", "chegada_prevista",
            "referencia", "situacao_voo",
        ]
        if len(rejects):
            _sql_safe_frame(rejects[reject_cols]).to_sql(
                "rejeicoes", con=conn, schema=schema, if_exists="append", index=False,
                method="multi", chunksize=BATCH_SIZE,
            )
        _sql_safe_frame(file_log).to_sql(
            "log_carga_arquivo", con=conn, schema=schema, if_exists="append", index=False,
            method="multi", chunksize=BATCH_SIZE,
        )
        for index_sql in [
            f"CREATE INDEX idx_fato_referencia ON {schema_q}.fato_voo(referencia)",
            f"CREATE INDEX idx_fato_tempo_partida ON {schema_q}.fato_voo(id_tempo_partida)",
            f"CREATE INDEX idx_fato_companhia ON {schema_q}.fato_voo(id_companhia)",
            f"CREATE INDEX idx_fato_situacao ON {schema_q}.fato_voo(id_situacao)",
            f"CREATE INDEX idx_fato_rota ON {schema_q}.fato_voo(id_aeroporto_origem, id_aeroporto_destino)",
        ]:
            conn.execute(text(index_sql))

        counts = {}
        for table in [*dimension_order, "fato_voo", "rejeicoes", "log_carga_arquivo"]:
            counts[table] = conn.execute(text(f"SELECT COUNT(*) FROM {schema_q}.\"{table}\"")).scalar_one()
        orphan_count = conn.execute(text(f"""
            SELECT
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_companhia_aerea d ON f.id_companhia=d.id_companhia WHERE d.id_companhia IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_aeroporto d ON f.id_aeroporto_origem=d.id_aeroporto WHERE d.id_aeroporto IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_aeroporto d ON f.id_aeroporto_destino=d.id_aeroporto WHERE d.id_aeroporto IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_tempo d ON f.id_tempo_partida=d.id_tempo WHERE d.id_tempo IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_tempo d ON f.id_tempo_chegada=d.id_tempo WHERE d.id_tempo IS NULL)
        """)).scalar_one()
        if orphan_count:
            raise RuntimeError(f"Foram encontradas {orphan_count} referências órfãs nas FKs principais.")
    return {"contagens_postgresql": counts, "foreign_key_orphans": int(orphan_count), "schema_postgresql": schema}


def run_etl(
    input_dir: str | Path, output_dir: str | Path, *,
    load_database: bool = True, replace: bool = False, schema: str | None = None,
) -> dict:
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.glob(f"VRA_{ANO}_*.csv"))
    if len(files) != 12:
        raise FileNotFoundError(
            f"Esperados 12 arquivos VRA_{ANO}_MM.csv; encontrados {len(files)} em {input_dir}."
        )
    carga_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    frames = []
    for path in files:
        print(f"[ETL] Lendo e padronizando {path.name}...", flush=True)
        frame = _normalizar_arquivo(path, carga_utc)
        frames.append(frame)
        print(f"[ETL] {len(frame):,} linhas lidas.", flush=True)

    print("[ETL] Consolidando os 12 meses e removendo duplicatas exatas...", flush=True)
    stage = pd.concat(frames, ignore_index=True)
    del frames
    gc.collect()
    duplicates_flag = stage.duplicated(subset=CANONICAL_COLS, keep=False)
    duplicates_extra = stage.duplicated(subset=CANONICAL_COLS, keep="first")
    stage["duplicata_exata_flag"] = duplicates_flag.astype("bool")
    stage["duplicata_exata_extra"] = duplicates_extra.astype("bool")
    stage["status_tratamento"] = stage["status_validacao"].astype("string")
    stage.loc[duplicates_extra, "status_tratamento"] = "DUPLICATA_REMOVIDA"

    staging_dir = output_dir / "staging"
    for filename, part in stage.groupby("arquivo_origem", sort=False, observed=True):
        month = Path(filename).stem
        _write_gzip_csv(part, staging_dir / f"stg_{month}.csv.gz")

    valid_mask = stage["status_validacao"].eq("VALIDO") & ~stage["duplicata_exata_extra"]
    reject_mask = stage["status_validacao"].eq("REJEITADO") & ~stage["duplicata_exata_extra"]
    duplicate_mask = stage["duplicata_exata_extra"]
    valid = stage.loc[valid_mask].copy()
    rejects = stage.loc[reject_mask].copy()
    duplicates_removed = stage.loc[duplicate_mask].copy()

    log_rows = []
    for filename, part in stage.groupby("arquivo_origem", sort=True, observed=True):
        log_rows.append({
            "arquivo_origem": filename,
            "ano_origem": ANO,
            "linhas_lidas": int(len(part)),
            "linhas_validas": int(part["status_validacao"].eq("VALIDO").sum()),
            "linhas_rejeitadas": int((part["status_validacao"].eq("REJEITADO") & ~part["duplicata_exata_extra"]).sum()),
            "duplicados_sinalizados": int(part["duplicata_exata_flag"].sum()),
            "duplicados_removidos": int(part["duplicata_exata_extra"].sum()),
            "cancelados": int(part["situacao_voo"].eq("CANCELADO").sum()),
            "nao_informados": int(part["situacao_voo"].eq("NÃO INFORMADO").sum()),
            "linhas_carregadas": int((part["status_validacao"].eq("VALIDO") & ~part["duplicata_exata_extra"]).sum()),
            "tamanho_bytes": (input_dir / filename).stat().st_size,
            "data_carga": pd.to_datetime(carga_utc, utc=True),
            "pipeline": PIPELINE,
        })
    file_log = pd.DataFrame(log_rows)

    if len(valid) == 0:
        raise ValueError("Nenhuma linha válida restou após a validação e a deduplicação.")

    print("[ETL] Construindo dimensões e fato...", flush=True)
    dimensions, fact, conflicts = _build_star(valid)
    _write_gzip_csv(conflicts, output_dir / "conflitos_dimensoes.csv.gz")
    if len(conflicts):
        raise ValueError(
            "Foram encontrados conflitos de descrição por chave natural. "
            "Consulte conflitos_dimensoes.csv.gz; nenhuma descrição foi escolhida automaticamente."
        )

    # Exportações e trilhas de auditoria independentes do SGBD.
    for col in TIMESTAMP_COLS:
        if col in fact.columns:
            fact[col] = pd.to_datetime(fact[col])
    _write_gzip_csv(fact, output_dir / "fato_voo.csv.gz")
    reject_cols = [
        "arquivo_origem", "linha_origem", "ano_origem", "motivo_rejeicao",
        "numero_voo", "companhia_icao", "partida_prevista", "chegada_prevista",
        "referencia", "situacao_voo",
    ]
    _write_gzip_csv(rejects[reject_cols], output_dir / "rejeicoes.csv.gz")
    _write_gzip_csv(duplicates_removed, output_dir / "duplicatas_removidas.csv.gz")
    for name, dimension in dimensions.items():
        _write_gzip_csv(dimension, output_dir / f"{name}.csv.gz")
    file_log.to_csv(output_dir / "etl_log_arquivos.csv", index=False, encoding="utf-8")

    quality = pd.DataFrame([{
        "coluna": col,
        "tipo_logico_contrato": (
            "TIMESTAMP" if col in TIMESTAMP_COLS else
            "DATE" if col == "referencia" else
            "INTEGER" if col == "numero_assentos" else "TEXT"
        ),
        "nulos_staging": int(stage[col].isna().sum()),
        "percentual_nulos_staging": round(float(stage[col].isna().mean() * 100), 4),
    } for col in CANONICAL_COLS])
    quality.to_csv(output_dir / "qualidade_colunas.csv", index=False, encoding="utf-8")

    db_result: dict = {"carga_postgresql": "nao_executada"}
    if load_database:
        db_schema = schema or os.getenv("PGSCHEMA", "dw_etl")
        print(f"[ETL] Carregando PostgreSQL (schema={db_schema})...", flush=True)
        engine = _postgres_engine()
        try:
            db_result = _create_postgres_database(engine, db_schema, dimensions, fact, rejects, file_log, replace)
        finally:
            engine.dispose()
    else:
        print("[ETL] Carga no PostgreSQL ignorada (--skip-db).", flush=True)

    total_read = int(len(stage))
    total_removed = int(len(duplicates_removed))
    total_rejected = int(len(rejects))
    total_loaded = int(len(fact))
    assert total_read == total_removed + total_rejected + total_loaded
    assert fact["id_voo"].is_unique
    assert int(file_log["duplicados_removidos"].sum()) == total_removed
    summary = {
        "ano_origem": ANO,
        "pipeline": PIPELINE,
        "data_carga_utc": carga_utc,
        "arquivos_lidos": len(files),
        "linhas_lidas": total_read,
        "duplicatas_exatas_removidas": total_removed,
        "linhas_rejeitadas_apos_deduplicacao": total_rejected,
        "linhas_validas_carregadas": total_loaded,
        "linhas_com_duplicidade_exata_sinalizadas": int(duplicates_flag.sum()),
        "voos_cancelados_na_fonte": int(stage["situacao_voo"].eq("CANCELADO").sum()),
        "voos_nao_informados_na_fonte": int(stage["situacao_voo"].eq("NÃO INFORMADO").sum()),
        "horarios_reais_partida_ausentes_na_fato": int(fact["partida_real"].isna().sum()),
        "horarios_reais_chegada_ausentes_na_fato": int(fact["chegada_real"].isna().sum()),
        "numero_voo_tipo": "TEXT (preserva zeros à esquerda)",
        "dimensoes": {name: int(len(dimension)) for name, dimension in dimensions.items()},
        "diferenca_partida_abs_maior_24h": int((fact["diferenca_partida_min"].abs() > 1440).sum()),
        "diferenca_chegada_abs_maior_24h": int((fact["diferenca_chegada_min"].abs() > 1440).sum()),
        **db_result,
    }
    (output_dir / "etl_resumo.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("[ETL] Execução concluída.")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa o ETL VRA/ANAC de 2019 para PostgreSQL.")
    parser.add_argument("--input-dir", required=True, help="Pasta com os 12 CSVs VRA_2019_MM.csv")
    parser.add_argument("--output-dir", required=True, help="Pasta onde os resultados do ETL serão salvos")
    parser.add_argument("--schema", default=None, help="Schema PostgreSQL (padrão: dw_etl)")
    parser.add_argument("--replace", action="store_true", help="Apaga e recria as tabelas ETL existentes no schema informado")
    parser.add_argument("--skip-db", action="store_true", help="Gera CSVs e logs sem carregar no PostgreSQL")
    args = parser.parse_args()
    result = run_etl(
        args.input_dir, args.output_dir,
        load_database=not args.skip_db, replace=args.replace, schema=args.schema,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
