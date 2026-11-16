#!/usr/bin/env python3
"""ETL VRA/ANAC 2019 conforme ao Contrato Único de Dados v1.1.

Fluxo: CSVs originais -> deduplicação exata dos 20 campos brutos ->
normalização/validação -> auditorias e métricas -> esquema estrela PostgreSQL.

A camada bruta é preservada por cópia byte a byte dos CSVs e, quando habilitada,
na tabela vra_bruta. Duplicatas excedentes e rejeições não são carregadas na Fato.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, SmallInteger, Text, create_engine, text
from sqlalchemy.engine import URL

ANO = 2019
PIPELINE = "ETL"
VERSAO_CONTRATO = "1.1"
SEPARADOR = ";"
ENCODING = "utf-8-sig"
BATCH_SIZE = 500

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
ORIGINAL_COLS = list(MAPA_COLUNAS.keys())
CANONICAL_COLS = list(MAPA_COLUNAS.values())
TIMESTAMP_COLS = ["partida_prevista", "partida_real", "chegada_prevista", "chegada_real"]
PLANNED_COLS = ["partida_prevista", "chegada_prevista"]
REQUIRED_TEXT_COLS = ["companhia_icao", "aeroporto_origem", "aeroporto_destino"]
UPPER_COLS = [
    "companhia_icao", "aeroporto_origem", "aeroporto_destino", "codigo_di",
    "tipo_linha", "modelo_equipamento", "situacao_voo", "situacao_partida",
    "situacao_chegada",
]
METADATA_COLS = [
    "ano_origem", "arquivo_origem", "linha_origem", "data_carga", "pipeline",
    "versao_contrato",
]
TABLES = [
    "fato_voo", "dim_tempo", "dim_companhia_aerea", "dim_aeroporto",
    "dim_situacao_voo", "dim_justificativa", "dim_tipo_linha", "dim_equipamento",
    "vra_bruta", "vra_tratada", "vra_duplicatas_excluidas", "vra_rejeicoes",
    "vra_anomalias", "vra_possiveis_duplicatas_padronizacao", "resumo_qualidade", "log_carga_arquivo",
]
DIMENSION_ORDER = [
    "dim_tempo", "dim_companhia_aerea", "dim_aeroporto", "dim_situacao_voo",
    "dim_justificativa", "dim_tipo_linha", "dim_equipamento",
]


def _safe_str_series(series: pd.Series) -> pd.Series:
    """Padroniza texto tratado: trim e vazio -> NA, sem alterar a camada bruta."""
    values = series.astype("string").str.strip()
    return values.mask(values.eq(""), pd.NA)


def _append_reason(target: pd.Series, mask: pd.Series, reason: str) -> None:
    """Acrescenta um motivo a cada registro indicado pela máscara."""
    if not bool(mask.any()):
        return
    current = target.loc[mask].fillna("")
    target.loc[mask] = current.where(current.eq(""), current + ";") + reason


def _read_raw_files(files: list[Path], carga_utc: pd.Timestamp) -> pd.DataFrame:
    """Lê os 12 CSVs preservando strings e valores brutos dos 20 campos."""
    frames: list[pd.DataFrame] = []
    expected = ORIGINAL_COLS
    for path in files:
        print(f"[ETL] Lendo bruto: {path.name}", flush=True)
        raw = pd.read_csv(
            path,
            sep=SEPARADOR,
            encoding=ENCODING,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            low_memory=False,
        )
        if list(raw.columns) != expected:
            missing = sorted(set(expected) - set(raw.columns))
            extra = sorted(set(raw.columns) - set(expected))
            raise ValueError(
                f"Cabeçalho divergente em {path.name}. Ausentes={missing}; extras={extra}. "
                "A ordem e os 20 nomes originais devem corresponder ao contrato."
            )
        # Os CSVs de origem são ordenados por nome; a linha 2 é o primeiro registro,
        # pois a linha 1 contém o cabeçalho. O contador representa registros lógicos.
        raw["ano_origem"] = ANO
        raw["arquivo_origem"] = path.name
        raw["linha_origem"] = np.arange(2, len(raw) + 2, dtype=np.int64)
        raw["data_carga"] = carga_utc
        raw["pipeline"] = PIPELINE
        raw["versao_contrato"] = VERSAO_CONTRATO
        frames.append(raw)
        print(f"[ETL] {len(raw):,} registros em {path.name}", flush=True)
    if not frames:
        raise ValueError("Nenhum CSV foi lido.")
    return pd.concat(frames, ignore_index=True, copy=False)


def _deduplicate_raw(raw: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.DataFrame, dict]:
    """Deduplica pela igualdade exata dos 20 campos originais, antes de limpar texto."""
    if raw.empty:
        raise ValueError("Os 12 arquivos foram encontrados, mas não há registros para processar.")
    print("[ETL] Identificando duplicatas nos 20 campos brutos...", flush=True)
    raw_index = pd.MultiIndex.from_frame(raw[ORIGINAL_COLS], names=ORIGINAL_COLS)
    group_codes, _ = pd.factorize(raw_index, sort=False)
    group_sizes = np.bincount(group_codes)
    first_index = np.full(len(group_sizes), len(raw), dtype=np.int64)
    np.minimum.at(first_index, group_codes, np.arange(len(raw), dtype=np.int64))
    row_group_size = group_sizes[group_codes]
    row_first_index = first_index[group_codes]
    exact_flag = pd.Series(row_group_size > 1, index=raw.index, dtype=bool)
    extra_flag = pd.Series(np.arange(len(raw), dtype=np.int64) != row_first_index, index=raw.index, dtype=bool)

    duplicate_positions = np.flatnonzero(extra_flag.to_numpy())
    audit_cols = ORIGINAL_COLS + METADATA_COLS
    audit = raw.iloc[duplicate_positions][audit_cols].copy()
    audit["grupo_duplicata_id"] = [f"2019-{int(group_codes[pos]) + 1:07d}" for pos in duplicate_positions]
    audit["tamanho_grupo"] = row_group_size[duplicate_positions].astype(np.int64)
    audit["arquivo_representante"] = raw.iloc[row_first_index[duplicate_positions]]["arquivo_origem"].to_numpy()
    audit["linha_representante"] = raw.iloc[row_first_index[duplicate_positions]]["linha_origem"].to_numpy()
    audit["duplicata_exata_flag"] = True
    audit["duplicata_exata_extra"] = True

    repeated_groups = int((group_sizes > 1).sum())
    involved_rows = int(group_sizes[group_sizes > 1].sum())
    summary = {
        "grupos_duplicados": repeated_groups,
        "linhas_envolvidas_duplicatas_exatas": involved_rows,
        "ocorrencias_excedentes_excluidas": int(extra_flag.sum()),
        "linhas_apos_deduplicacao": int((~extra_flag).sum()),
    }
    return exact_flag, extra_flag, audit, summary


def _find_post_trim_upper_duplicates(raw: pd.DataFrame, extra_flag: pd.Series) -> tuple[pd.DataFrame, dict]:
    """Sinaliza igualdade apenas após trim/upper, sem excluir nenhuma linha.

    A análise usa somente representantes após a deduplicação bruta exata.
    Não converte datas nem números: compara os 20 textos após trim/upper, como
    distinção diagnóstica prevista na seção 5 do contrato.
    """
    representative_positions = np.flatnonzero((~extra_flag).to_numpy())
    representative_raw = raw.iloc[representative_positions]
    key = representative_raw[ORIGINAL_COLS].rename(columns=MAPA_COLUNAS).copy()
    for col in CANONICAL_COLS:
        values = key[col].astype("string").str.strip()
        key[col] = values.mask(values.eq(""), pd.NA)
    for col in UPPER_COLS:
        key[col] = key[col].str.upper()
    # Um sentinela explícito faz valores ausentes iguais participarem da chave.
    key = key.fillna("\x00NULL\x00")
    normalized_index = pd.MultiIndex.from_frame(key, names=CANONICAL_COLS)
    group_codes, _ = pd.factorize(normalized_index, sort=False)
    group_sizes = np.bincount(group_codes)
    row_sizes = group_sizes[group_codes]
    is_candidate = row_sizes > 1
    candidate_positions = representative_positions[np.flatnonzero(is_candidate)]
    candidate_codes = group_codes[is_candidate]
    candidate_sizes = row_sizes[is_candidate]
    audit = raw.iloc[candidate_positions][ORIGINAL_COLS + METADATA_COLS].copy()
    audit["grupo_pos_trim_upper_id"] = [f"2019-N{int(code) + 1:07d}" for code in candidate_codes]
    audit["tamanho_grupo_pos_trim_upper"] = candidate_sizes.astype(np.int64)
    audit["possivel_duplicata_pos_trim_upper"] = True
    metrics = {
        "grupos_pos_trim_upper": int((group_sizes > 1).sum()),
        "registros_envolvidos_pos_trim_upper": int(is_candidate.sum()),
    }
    return audit, metrics


def _normalize_and_validate(raw: pd.DataFrame) -> pd.DataFrame:
    """Cria dados canônicos a partir do bruto e identifica rejeições/anomalias.

    Esta função também é aplicada às excedentes apenas para medir a interseção
    duplicatas x inválidos; somente representantes entram na validação analítica.
    """
    df = raw[ORIGINAL_COLS].rename(columns=MAPA_COLUNAS).copy()
    for col in CANONICAL_COLS:
        df[col] = _safe_str_series(df[col])
    for col in UPPER_COLS:
        df[col] = df[col].str.upper()

    reasons = pd.Series(pd.NA, index=df.index, dtype="string")
    anomalies = pd.Series(pd.NA, index=df.index, dtype="string")

    # Os únicos campos obrigatórios para entrada na Fato são os cinco indicados
    # expressamente na seção 6 do contrato v1.1.
    for col in REQUIRED_TEXT_COLS:
        missing = df[col].isna()
        _append_reason(reasons, missing, f"campo_obrigatorio_ausente:{col}")

    parsed_timestamps: dict[str, pd.Series] = {}
    timestamp_pattern = r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}"
    for col in TIMESTAMP_COLS:
        source = df[col]
        nonempty = source.notna()
        format_ok = source.str.fullmatch(timestamp_pattern, na=False)
        parsed = pd.to_datetime(source.where(format_ok), format="%d/%m/%Y %H:%M", errors="coerce")
        invalid = nonempty & parsed.isna()
        parsed_timestamps[col] = parsed
        if col in PLANNED_COLS:
            missing = source.isna()
            _append_reason(reasons, missing, f"campo_obrigatorio_ausente:{col}")
            _append_reason(reasons, invalid, f"timestamp_invalido:{col}")
        else:
            _append_reason(anomalies, invalid, f"timestamp_opcional_invalido:{col}")

    # Referência é DATE NULL segundo o contrato. Erros são registrados como
    # anomalia, sem rejeitar a linha por esse motivo.
    ref_source = df["referencia"]
    ref_format_ok = ref_source.str.fullmatch(r"\d{4}-\d{2}-\d{2}", na=False)
    parsed_ref = pd.to_datetime(ref_source.where(ref_format_ok), format="%Y-%m-%d", errors="coerce")
    invalid_ref = ref_source.notna() & parsed_ref.isna()
    _append_reason(anomalies, invalid_ref, "data_referencia_invalida")

    # Assentos: somente inteiro não negativo. Qualquer valor preenchido fora do
    # padrão vira NULL tratado e anomalia; não é motivo de rejeição.
    seats_source = df["numero_assentos"]
    seats_format_ok = seats_source.str.fullmatch(r"\d+", na=False)
    seats_numeric = pd.to_numeric(seats_source.where(seats_format_ok), errors="coerce")
    # INTEGER do PostgreSQL é um inteiro assinado de 32 bits. Valores acima do
    # limite também são tratados como inválidos, em vez de falhar na carga.
    invalid_seats = seats_source.notna() & (
        ~seats_format_ok | seats_numeric.isna() | seats_numeric.gt(2_147_483_647)
    )
    _append_reason(anomalies, invalid_seats, "numero_assentos_invalido")
    seats_numeric = seats_numeric.mask(invalid_seats)
    df["numero_assentos"] = seats_numeric.astype("Int64")

    for col, parsed in parsed_timestamps.items():
        df[col] = parsed
    df["referencia"] = parsed_ref.dt.date

    metadata = raw[METADATA_COLS].copy()
    result = pd.concat([df, metadata], axis=1)
    result["motivo_rejeicao"] = reasons
    result["motivo_anomalia"] = anomalies
    result["status_validacao"] = reasons.isna().map({True: "VALIDO", False: "REJEITADO"})
    return result


def _build_dimension(
    values: Iterable[str], id_name: str, value_name: str, unknown: bool = False
) -> pd.DataFrame:
    vals = sorted({str(v) for v in values if pd.notna(v) and str(v) != ""})
    rows: list[tuple[int, str]] = []
    if unknown:
        # O membro 0 representa valores ausentes, conforme as seções 8 do contrato.
        rows.append((0, "DESCONHECIDO"))
        vals = [value for value in vals if value != "DESCONHECIDO"]
    rows.extend((i, val) for i, val in enumerate(vals, start=1))
    return pd.DataFrame(rows, columns=[id_name, value_name])


def _resolve_code_description(
    pairs: pd.DataFrame, code_col: str, desc_col: str, dimension_name: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resolve dimensão por código natural e expõe conflitos sem escolha arbitrária."""
    data = pairs[[code_col, desc_col]].copy()
    data[code_col] = _safe_str_series(data[code_col]).str.upper()
    data[desc_col] = _safe_str_series(data[desc_col])
    data = data[data[code_col].notna()]
    non_null = data.dropna(subset=[desc_col])
    counts = non_null.groupby(code_col, sort=False)[desc_col].nunique()
    conflicting_codes = set(counts[counts > 1].index.tolist())
    if conflicting_codes:
        conflicts = (
            non_null[non_null[code_col].isin(conflicting_codes)]
            .drop_duplicates([code_col, desc_col])
            .rename(columns={code_col: "codigo_natural", desc_col: "descricao_conflitante"})
        )
        conflicts.insert(0, "dimensao", dimension_name)
    else:
        conflicts = pd.DataFrame(columns=["dimensao", "codigo_natural", "descricao_conflitante"])
    codes = data[[code_col]].drop_duplicates().sort_values(code_col).reset_index(drop=True)
    if len(non_null):
        # Sem conflito, há no máximo uma descrição não nula para cada código.
        desc_map = non_null.drop_duplicates([code_col]).set_index(code_col)[desc_col]
        codes[desc_col] = codes[code_col].map(desc_map)
    else:
        codes[desc_col] = pd.NA
    return codes.rename(columns={code_col: "codigo_natural", desc_col: "descricao"}), conflicts


def _build_star(valid: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    """Gera as sete dimensões e a Fato somente com representantes elegíveis."""
    company_pairs = valid[["companhia_icao", "companhia_nome"]].drop_duplicates().rename(
        columns={"companhia_icao": "codigo", "companhia_nome": "descricao"}
    )
    company_dim, company_conflicts = _resolve_code_description(
        company_pairs, "codigo", "descricao", "dim_companhia_aerea"
    )

    airport_pairs = pd.concat([
        valid[["aeroporto_origem", "descricao_origem"]].rename(
            columns={"aeroporto_origem": "codigo", "descricao_origem": "descricao"}),
        valid[["aeroporto_destino", "descricao_destino"]].rename(
            columns={"aeroporto_destino": "codigo", "descricao_destino": "descricao"}),
    ], ignore_index=True)
    airport_dim, airport_conflicts = _resolve_code_description(
        airport_pairs, "codigo", "descricao", "dim_aeroporto"
    )
    conflicts = pd.concat([company_conflicts, airport_conflicts], ignore_index=True)

    date_values = pd.concat([
        valid["partida_prevista"].dt.normalize(),
        valid["chegada_prevista"].dt.normalize(),
    ], ignore_index=True).dropna().drop_duplicates().sort_values()
    time_dim = pd.DataFrame({"data": date_values.dt.date.to_numpy()})
    time_dt = pd.to_datetime(time_dim["data"])
    time_dim.insert(0, "id_tempo", time_dt.dt.strftime("%Y%m%d").astype("int64"))
    time_dim["ano"] = time_dt.dt.year.astype("int64")
    time_dim["trimestre"] = time_dt.dt.quarter.astype("int64")
    time_dim["mes"] = time_dt.dt.month.astype("int64")
    time_dim["dia"] = time_dt.dt.day.astype("int64")
    time_dim["dia_semana"] = time_dt.dt.isocalendar().day.astype("int64")
    time_dim = time_dim[["id_tempo", "data", "ano", "trimestre", "mes", "dia", "dia_semana"]]

    company_dim = company_dim.sort_values("codigo_natural").reset_index(drop=True)
    company_dim.insert(0, "id_companhia", np.arange(1, len(company_dim) + 1, dtype=np.int64))
    company_dim = company_dim.rename(columns={"codigo_natural": "companhia_icao", "descricao": "companhia_nome"})
    airport_dim = airport_dim.sort_values("codigo_natural").reset_index(drop=True)
    airport_dim.insert(0, "id_aeroporto", np.arange(1, len(airport_dim) + 1, dtype=np.int64))
    airport_dim = airport_dim.rename(columns={"codigo_natural": "aeroporto_icao", "descricao": "descricao_aeroporto"})

    situation_dim = _build_dimension(valid["situacao_voo"], "id_situacao", "situacao_voo")
    justification_dim = _build_dimension(
        valid["justificativa"], "id_justificativa", "justificativa", unknown=True
    )
    line_dim = _build_dimension(valid["tipo_linha"], "id_tipo_linha", "tipo_linha")
    equipment_dim = _build_dimension(
        valid["modelo_equipamento"], "id_equipamento", "modelo_equipamento", unknown=True
    )
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

    fact = valid[CANONICAL_COLS + METADATA_COLS].copy().reset_index(drop=True)
    fact.insert(0, "id_voo", np.arange(1, len(fact) + 1, dtype=np.int64))
    fact["id_companhia"] = fact["companhia_icao"].map(company_map).astype("Int64")
    fact["id_aeroporto_origem"] = fact["aeroporto_origem"].map(airport_map).astype("Int64")
    fact["id_aeroporto_destino"] = fact["aeroporto_destino"].map(airport_map).astype("Int64")
    fact["id_tempo_partida"] = fact["partida_prevista"].dt.strftime("%Y-%m-%d").map(time_map).astype("Int64")
    fact["id_tempo_chegada"] = fact["chegada_prevista"].dt.strftime("%Y-%m-%d").map(time_map).astype("Int64")
    fact["id_situacao"] = fact["situacao_voo"].map(situation_map).astype("Int64")
    fact["id_justificativa"] = (
        fact["justificativa"].astype("string").fillna("DESCONHECIDO").map(justification_map).astype("Int64")
    )
    fact["id_tipo_linha"] = fact["tipo_linha"].map(line_map).astype("Int64")
    fact["id_equipamento"] = (
        fact["modelo_equipamento"].astype("string").fillna("DESCONHECIDO").map(equipment_map).astype("Int64")
    )

    for prefix, planned, actual in [
        ("partida", "partida_prevista", "partida_real"),
        ("chegada", "chegada_prevista", "chegada_real"),
    ]:
        difference = (fact[actual] - fact[planned]).dt.total_seconds() / 60
        fact[f"diferenca_{prefix}_min"] = difference.round().astype("Int64")
        fact[f"atraso_{prefix}_min"] = difference.clip(lower=0).round().astype("Int64")
        fact[f"{prefix}_atipica_flag"] = (difference.notna() & (difference.abs() > 1440)).astype(bool)

    fact["partida_ano_diverge_flag"] = fact["partida_prevista"].dt.year.ne(ANO).astype(bool)
    fact["quantidade_voos"] = np.int16(1)
    fact = fact[[
        "id_voo", "id_companhia", "id_aeroporto_origem", "id_aeroporto_destino",
        "id_tempo_partida", "id_tempo_chegada", "id_situacao", "id_justificativa",
        "id_tipo_linha", "id_equipamento", "numero_voo", "codigo_di", "referencia",
        "situacao_partida", "situacao_chegada", "partida_prevista", "partida_real",
        "chegada_prevista", "chegada_real", "quantidade_voos", "numero_assentos",
        "diferenca_partida_min", "diferenca_chegada_min", "atraso_partida_min",
        "atraso_chegada_min", "partida_atipica_flag", "chegada_atipica_flag",
        "partida_ano_diverge_flag", "ano_origem", "arquivo_origem", "linha_origem",
        "data_carga", "pipeline", "versao_contrato",
    ]]
    return dimensions, fact, conflicts


def _make_treated(valid: pd.DataFrame) -> pd.DataFrame:
    """Cria vra_tratada: 20 nomes canônicos, proveniência e medidas do contrato."""
    treated = valid[CANONICAL_COLS + METADATA_COLS].copy()
    for prefix, planned, actual in [
        ("partida", "partida_prevista", "partida_real"),
        ("chegada", "chegada_prevista", "chegada_real"),
    ]:
        difference = (treated[actual] - treated[planned]).dt.total_seconds() / 60
        treated[f"diferenca_{prefix}_min"] = difference.round().astype("Int64")
        treated[f"atraso_{prefix}_min"] = difference.clip(lower=0).round().astype("Int64")
        treated[f"{prefix}_atipica_flag"] = (difference.notna() & (difference.abs() > 1440)).astype(bool)
    treated["partida_ano_diverge_flag"] = treated["partida_prevista"].dt.year.ne(ANO).astype(bool)
    treated["quantidade_voos"] = np.int16(1)
    return treated


def _sql_safe_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Converte valores ausentes do Pandas para None, aceito pelo driver PostgreSQL."""
    return frame.astype(object).where(pd.notna(frame), None)


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


def _load_postgres(
    engine,
    schema: str,
    raw: pd.DataFrame,
    treated: pd.DataFrame,
    duplicates: pd.DataFrame,
    rejects: pd.DataFrame,
    anomalies: pd.DataFrame,
    post_normalization_duplicates: pd.DataFrame,
    dimensions: dict[str, pd.DataFrame],
    fact: pd.DataFrame,
    quality: pd.DataFrame,
    file_log: pd.DataFrame,
    replace: bool,
) -> dict:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise ValueError("Nome de schema inválido. Use letras, números e underscore; não comece com número.")
    schema_q = f'"{schema}"'
    ddl_statements = [
        f"""CREATE TABLE {schema_q}.dim_tempo (
            id_tempo INTEGER PRIMARY KEY, data DATE NOT NULL UNIQUE,
            ano INTEGER NOT NULL, trimestre INTEGER NOT NULL, mes INTEGER NOT NULL,
            dia INTEGER NOT NULL, dia_semana INTEGER NOT NULL
        )""",
        f"""CREATE TABLE {schema_q}.dim_companhia_aerea (
            id_companhia INTEGER PRIMARY KEY, companhia_icao TEXT NOT NULL UNIQUE,
            companhia_nome TEXT NULL
        )""",
        f"""CREATE TABLE {schema_q}.dim_aeroporto (
            id_aeroporto INTEGER PRIMARY KEY, aeroporto_icao TEXT NOT NULL UNIQUE,
            descricao_aeroporto TEXT NULL
        )""",
        f"""CREATE TABLE {schema_q}.dim_situacao_voo (
            id_situacao INTEGER PRIMARY KEY, situacao_voo TEXT NOT NULL UNIQUE
        )""",
        f"""CREATE TABLE {schema_q}.dim_justificativa (
            id_justificativa INTEGER PRIMARY KEY, justificativa TEXT NOT NULL UNIQUE
        )""",
        f"""CREATE TABLE {schema_q}.dim_tipo_linha (
            id_tipo_linha INTEGER PRIMARY KEY, tipo_linha TEXT NOT NULL UNIQUE
        )""",
        f"""CREATE TABLE {schema_q}.dim_equipamento (
            id_equipamento INTEGER PRIMARY KEY, modelo_equipamento TEXT NOT NULL UNIQUE
        )""",
        f"""CREATE TABLE {schema_q}.fato_voo (
            id_voo BIGINT PRIMARY KEY,
            id_companhia INTEGER NOT NULL REFERENCES {schema_q}.dim_companhia_aerea(id_companhia),
            id_aeroporto_origem INTEGER NOT NULL REFERENCES {schema_q}.dim_aeroporto(id_aeroporto),
            id_aeroporto_destino INTEGER NOT NULL REFERENCES {schema_q}.dim_aeroporto(id_aeroporto),
            id_tempo_partida INTEGER NOT NULL REFERENCES {schema_q}.dim_tempo(id_tempo),
            id_tempo_chegada INTEGER NOT NULL REFERENCES {schema_q}.dim_tempo(id_tempo),
            id_situacao INTEGER NULL REFERENCES {schema_q}.dim_situacao_voo(id_situacao),
            id_justificativa INTEGER NOT NULL REFERENCES {schema_q}.dim_justificativa(id_justificativa),
            id_tipo_linha INTEGER NULL REFERENCES {schema_q}.dim_tipo_linha(id_tipo_linha),
            id_equipamento INTEGER NOT NULL REFERENCES {schema_q}.dim_equipamento(id_equipamento),
            numero_voo TEXT NULL, codigo_di TEXT NULL, referencia DATE NULL,
            situacao_partida TEXT NULL, situacao_chegada TEXT NULL,
            partida_prevista TIMESTAMP NOT NULL, partida_real TIMESTAMP NULL,
            chegada_prevista TIMESTAMP NOT NULL, chegada_real TIMESTAMP NULL,
            quantidade_voos SMALLINT NOT NULL CHECK (quantidade_voos = 1),
            numero_assentos INTEGER NULL, diferenca_partida_min INTEGER NULL,
            diferenca_chegada_min INTEGER NULL, atraso_partida_min INTEGER NULL,
            atraso_chegada_min INTEGER NULL, partida_atipica_flag BOOLEAN NOT NULL,
            chegada_atipica_flag BOOLEAN NOT NULL, partida_ano_diverge_flag BOOLEAN NOT NULL,
            ano_origem INTEGER NOT NULL, arquivo_origem TEXT NOT NULL,
            linha_origem INTEGER NOT NULL, data_carga TIMESTAMPTZ NOT NULL,
            pipeline TEXT NOT NULL, versao_contrato TEXT NOT NULL
        )""",
    ]
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_q}"))
        existing_names = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"
        ), {"schema": schema}).scalars().all()
        existing = sum(name in set(existing_names) for name in TABLES)
        if existing and not replace:
            raise RuntimeError(
                f"Já existem {existing} tabelas/artefatos ETL no schema {schema}. "
                "Use --replace somente quando desejar substituir essa carga."
            )
        if replace:
            for table in TABLES:
                conn.execute(text(f'DROP TABLE IF EXISTS {schema_q}."{table}" CASCADE'))
        for statement in ddl_statements:
            conn.execute(text(statement))

        # Raw database table: os 20 campos originais ficam TEXT e sem normalização.
        raw_db = raw[ORIGINAL_COLS + METADATA_COLS].copy()
        raw_dtype = {col: Text() for col in ORIGINAL_COLS}
        raw_dtype.update({
            "ano_origem": Integer(), "arquivo_origem": Text(), "linha_origem": Integer(),
            "data_carga": DateTime(timezone=True), "pipeline": Text(), "versao_contrato": Text(),
        })
        _sql_safe_frame(raw_db).to_sql(
            "vra_bruta", con=conn, schema=schema, if_exists="append", index=False,
            method="multi", chunksize=BATCH_SIZE, dtype=raw_dtype,
        )

        for table in DIMENSION_ORDER:
            _sql_safe_frame(dimensions[table]).to_sql(
                table, con=conn, schema=schema, if_exists="append", index=False,
                method="multi", chunksize=BATCH_SIZE,
            )
        _sql_safe_frame(fact).to_sql(
            "fato_voo", con=conn, schema=schema, if_exists="append", index=False,
            method="multi", chunksize=BATCH_SIZE,
        )

        # Artefatos operacionais de tratamento e auditoria, além do esquema estrela.
        canonical_types = {col: Text() for col in CANONICAL_COLS}
        for col in TIMESTAMP_COLS:
            canonical_types[col] = DateTime(timezone=False)
        canonical_types["referencia"] = Date()
        canonical_types["numero_assentos"] = Integer()
        metadata_types = {
            "ano_origem": Integer(), "arquivo_origem": Text(), "linha_origem": Integer(),
            "data_carga": DateTime(timezone=True), "pipeline": Text(), "versao_contrato": Text(),
        }
        treated_types = {**canonical_types, **metadata_types,
            "diferenca_partida_min": Integer(), "diferenca_chegada_min": Integer(),
            "atraso_partida_min": Integer(), "atraso_chegada_min": Integer(),
            "partida_atipica_flag": Boolean(), "chegada_atipica_flag": Boolean(),
            "partida_ano_diverge_flag": Boolean(), "quantidade_voos": SmallInteger()}
        audit_types = {**{col: Text() for col in ORIGINAL_COLS}, **metadata_types,
            "grupo_duplicata_id": Text(), "tamanho_grupo": Integer(),
            "arquivo_representante": Text(), "linha_representante": Integer(),
            "duplicata_exata_flag": Boolean(), "duplicata_exata_extra": Boolean(),
            "motivos_validacao_diagnostica": Text(), "anomalias_diagnosticas": Text(),
            "duplicata_invalida_flag": Boolean()}
        post_dup_types = {**{col: Text() for col in ORIGINAL_COLS}, **metadata_types,
            "grupo_pos_trim_upper_id": Text(), "tamanho_grupo_pos_trim_upper": Integer(),
            "possivel_duplicata_pos_trim_upper": Boolean()}
        reject_anomaly_types = {**canonical_types, **metadata_types,
            "motivo_rejeicao": Text(), "motivo_anomalia": Text(),
            **{f"bruto__{col}": Text() for col in ORIGINAL_COLS}}
        log_types = {
            "arquivo_origem": Text(), "ano_origem": Integer(), "versao_contrato": Text(),
            "linhas_brutas": BigInteger(), "linhas_em_grupos_duplicados": BigInteger(),
            "duplicatas_excedentes": BigInteger(), "linhas_rejeitadas_pos_deduplicacao": BigInteger(),
            "linhas_carregadas_fato": BigInteger(), "cancelados_na_fonte": BigInteger(),
            "nao_informados_na_fonte": BigInteger(), "tamanho_bytes": BigInteger(),
            "data_carga": DateTime(timezone=True), "pipeline": Text(),
        }
        artifact_rows = [
            ("vra_tratada", treated, treated_types),
            ("vra_duplicatas_excluidas", duplicates, audit_types),
            ("vra_rejeicoes", rejects, reject_anomaly_types),
            ("vra_anomalias", anomalies, reject_anomaly_types),
            ("vra_possiveis_duplicatas_padronizacao", post_normalization_duplicates, post_dup_types),
            ("resumo_qualidade", quality, {"indicador": Text(), "valor": Text()}),
            ("log_carga_arquivo", file_log, log_types),
        ]
        for table, frame, type_map in artifact_rows:
            dtype = {col: type_map[col] for col in frame.columns if col in type_map}
            _sql_safe_frame(frame).to_sql(
                table, con=conn, schema=schema, if_exists="append", index=False,
                method="multi", chunksize=BATCH_SIZE, dtype=dtype,
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
        for table in [*DIMENSION_ORDER, "fato_voo", *TABLES[8:]]:
            counts[table] = int(conn.execute(
                text(f'SELECT COUNT(*) FROM {schema_q}."{table}"')
            ).scalar_one())
        fk_check = conn.execute(text(f"""
            SELECT
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_companhia_aerea d ON f.id_companhia=d.id_companhia WHERE d.id_companhia IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_aeroporto d ON f.id_aeroporto_origem=d.id_aeroporto WHERE d.id_aeroporto IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_aeroporto d ON f.id_aeroporto_destino=d.id_aeroporto WHERE d.id_aeroporto IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_tempo d ON f.id_tempo_partida=d.id_tempo WHERE d.id_tempo IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_tempo d ON f.id_tempo_chegada=d.id_tempo WHERE d.id_tempo IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_situacao_voo d ON f.id_situacao=d.id_situacao WHERE f.id_situacao IS NOT NULL AND d.id_situacao IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_justificativa d ON f.id_justificativa=d.id_justificativa WHERE d.id_justificativa IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_tipo_linha d ON f.id_tipo_linha=d.id_tipo_linha WHERE f.id_tipo_linha IS NOT NULL AND d.id_tipo_linha IS NULL) +
              (SELECT COUNT(*) FROM {schema_q}.fato_voo f LEFT JOIN {schema_q}.dim_equipamento d ON f.id_equipamento=d.id_equipamento WHERE d.id_equipamento IS NULL)
        """)).scalar_one()
        if int(fk_check):
            raise RuntimeError(f"Foram encontradas {fk_check} referências órfãs na Fato.")
    return {"contagens_postgresql": counts, "foreign_key_orphans": int(fk_check), "schema_postgresql": schema}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_raw_files(files: list[Path], output_dir: Path) -> pd.DataFrame:
    raw_dir = output_dir / "vra_bruta"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for path in files:
        destination = raw_dir / path.name
        shutil.copy2(path, destination)
        source_digest = _sha256_file(path)
        copy_digest = _sha256_file(destination)
        manifest_rows.append({
            "arquivo_origem": path.name,
            "tamanho_bytes": path.stat().st_size,
            "sha256_copia": copy_digest,
            "copia_verificada": path.stat().st_size == destination.stat().st_size
                and source_digest == copy_digest,
        })
    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(raw_dir / "manifesto_arquivos.csv", index=False, encoding="utf-8")
    if not manifest["copia_verificada"].all():
        raise RuntimeError("A verificação de integridade da cópia bruta falhou.")
    return manifest


def _quality_frame(metrics: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {"indicador": key, "valor": json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)}
        for key, value in metrics.items()
    ])


def run_etl(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    load_database: bool = True,
    replace: bool = False,
    schema: str | None = None,
) -> dict:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Pasta de entrada não encontrada: {input_dir}")

    expected_names = [f"VRA_{ANO}_{month:02d}.csv" for month in range(1, 13)]
    files = sorted(input_dir.glob(f"VRA_{ANO}_*.csv"), key=lambda p: p.name)
    found_names = [p.name for p in files]
    if found_names != expected_names:
        missing = sorted(set(expected_names) - set(found_names))
        extra = sorted(set(found_names) - set(expected_names))
        raise FileNotFoundError(
            f"Esperados os 12 arquivos mensais de 2019. Ausentes={missing}; extras={extra}."
        )

    carga_utc = pd.Timestamp(datetime.now(timezone.utc))
    manifest = _copy_raw_files(files, output_dir)
    raw = _read_raw_files(files, carga_utc)
    lines_read = int(len(raw))

    # Primeira decisão analítica: deduplicação exata dos valores brutos.
    exact_flag, extra_flag, duplicates_audit, duplicate_metrics = _deduplicate_raw(raw)
    post_normalization_duplicates, post_normalization_metrics = _find_post_trim_upper_duplicates(raw, extra_flag)
    normalized = _normalize_and_validate(raw)

    extra_positions = np.flatnonzero(extra_flag.to_numpy())
    duplicate_diagnostics = normalized.iloc[extra_positions]
    duplicates_audit["motivos_validacao_diagnostica"] = duplicate_diagnostics["motivo_rejeicao"].fillna("").to_numpy()
    duplicates_audit["anomalias_diagnosticas"] = duplicate_diagnostics["motivo_anomalia"].fillna("").to_numpy()
    duplicates_audit["duplicata_invalida_flag"] = duplicate_diagnostics["status_validacao"].eq("REJEITADO").to_numpy()
    duplicate_invalid_overlap = int(duplicates_audit["duplicata_invalida_flag"].sum())

    # Só representantes são avaliados para elegibilidade analítica.
    deduplicated = normalized.loc[~extra_flag].copy()
    rejects = deduplicated.loc[deduplicated["status_validacao"].eq("REJEITADO")].copy()
    valid = deduplicated.loc[deduplicated["status_validacao"].eq("VALIDO")].copy()
    anomalies = deduplicated.loc[deduplicated["motivo_anomalia"].notna()].copy()
    # Mesmo que nenhum representante seja elegível, as rejeições e auditorias
    # devem ser exportadas; dimensões e Fato podem ser vazias nessa execução.
    dimensions, fact, conflicts = _build_star(valid)
    conflicts.to_csv(output_dir / "conflitos_dimensoes.csv", index=False, encoding="utf-8")
    if len(conflicts):
        raise ValueError(
            "Foram encontrados códigos ICAO com descrições distintas. Consulte "
            "conflitos_dimensoes.csv e resolva os conflitos antes de publicar as dimensões."
        )

    treated = _make_treated(valid)
    # CSVs tipados: timestamps seguem em formato ISO; DATE segue AAAA-MM-DD.
    _write_frame = lambda frame, path: frame.to_csv(
        path, index=False, encoding="utf-8", compression={"method": "gzip", "compresslevel": 1, "mtime": 1}, na_rep=""
    )
    _write_frame(treated, output_dir / "vra_tratada.csv.gz")
    _write_frame(fact, output_dir / "fato_voo.csv.gz")
    _write_frame(duplicates_audit, output_dir / "vra_duplicatas_excluidas.csv.gz")
    _write_frame(
        post_normalization_duplicates,
        output_dir / "vra_possiveis_duplicatas_padronizacao.csv.gz",
    )

    reject_columns = CANONICAL_COLS + METADATA_COLS + ["motivo_rejeicao", "motivo_anomalia"]
    reject_output = pd.concat([
        rejects[reject_columns].copy(),
        raw.loc[rejects.index, ORIGINAL_COLS].add_prefix("bruto__"),
    ], axis=1)
    _write_frame(reject_output, output_dir / "vra_rejeicoes.csv.gz")
    anomaly_output = pd.concat([
        anomalies[CANONICAL_COLS + METADATA_COLS + ["motivo_anomalia", "motivo_rejeicao"]].copy(),
        raw.loc[anomalies.index, ORIGINAL_COLS].add_prefix("bruto__"),
    ], axis=1)
    _write_frame(anomaly_output, output_dir / "vra_anomalias.csv.gz")

    for name, dimension in dimensions.items():
        dimension.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8")

    # Logs por arquivo. A contagem de linhas carregadas considera somente Fato.
    file_rows = []
    for filename, part in normalized.groupby("arquivo_origem", sort=True):
        part_indexes = part.index
        is_extra_part = extra_flag.loc[part_indexes]
        is_representative = ~is_extra_part
        part_raw = raw.loc[part_indexes]
        file_rows.append({
            "arquivo_origem": filename,
            "ano_origem": ANO,
            "versao_contrato": VERSAO_CONTRATO,
            "linhas_brutas": int(len(part)),
            "linhas_em_grupos_duplicados": int(exact_flag.loc[part_indexes].sum()),
            "duplicatas_excedentes": int(is_extra_part.sum()),
            "linhas_rejeitadas_pos_deduplicacao": int((is_representative & part["status_validacao"].eq("REJEITADO")).sum()),
            "linhas_carregadas_fato": int((is_representative & part["status_validacao"].eq("VALIDO")).sum()),
            "cancelados_na_fonte": int(part["situacao_voo"].eq("CANCELADO").sum()),
            "nao_informados_na_fonte": int(part["situacao_voo"].eq("NÃO INFORMADO").sum()),
            "tamanho_bytes": int((input_dir / filename).stat().st_size),
            "data_carga": carga_utc,
            "pipeline": PIPELINE,
        })
    file_log = pd.DataFrame(file_rows)
    file_log.to_csv(output_dir / "etl_log_arquivos.csv", index=False, encoding="utf-8")

    total_removed = int(extra_flag.sum())
    total_rejected = int(len(rejects))
    total_loaded = int(len(fact))
    assert lines_read == total_removed + total_rejected + total_loaded, (
        "A conciliação falhou: brutas devem ser iguais a excedentes + rejeições "
        "remanescentes + registros carregados na Fato."
    )
    assert fact["id_voo"].is_unique
    assert int(duplicates_audit.shape[0]) == total_removed

    metrics = {
        "ano_origem": ANO,
        "pipeline": PIPELINE,
        "versao_contrato": VERSAO_CONTRATO,
        "data_carga_utc": carga_utc.isoformat(),
        "arquivos_esperados": 12,
        "arquivos_lidos": len(files),
        "colunas_originais": len(ORIGINAL_COLS),
        "linhas_brutas": lines_read,
        **duplicate_metrics,
        **post_normalization_metrics,
        "intersecao_excedentes_duplicados_invalidos": duplicate_invalid_overlap,
        "linhas_rejeitadas_pos_deduplicacao": total_rejected,
        "linhas_elegiveis_fato": total_loaded,
        "voos_cancelados_na_fonte": int(normalized["situacao_voo"].eq("CANCELADO").sum()),
        "voos_cancelados_na_fato": int(valid["situacao_voo"].eq("CANCELADO").sum()),
        "voos_nao_informados_na_fonte": int(normalized["situacao_voo"].eq("NÃO INFORMADO").sum()),
        "voos_nao_informados_na_fato": int(valid["situacao_voo"].eq("NÃO INFORMADO").sum()),
        "horarios_reais_partida_ausentes_na_fato": int(fact["partida_real"].isna().sum()),
        "horarios_reais_chegada_ausentes_na_fato": int(fact["chegada_real"].isna().sum()),
        "partidas_atipicas_abs_maior_24h": int(fact["partida_atipica_flag"].sum()),
        "chegadas_atipicas_abs_maior_24h": int(fact["chegada_atipica_flag"].sum()),
        "partidas_previstas_com_ano_diferente_de_2019": int(fact["partida_ano_diverge_flag"].sum()),
        "linhas_com_anomalias_na_camada_deduplicada": int(len(anomalies)),
        "numero_voo_tipo": "TEXT (preserva zeros à esquerda)",
        "codigo_di_tipo": "TEXT",
        "dimensoes": {name: int(len(dimension)) for name, dimension in dimensions.items()},
        "manifesto_copias_brutas_verificado": bool(manifest["copia_verificada"].all()),
        "equacao_conciliacao": {
            "brutas": lines_read,
            "excedentes_excluidas": total_removed,
            "rejeicoes_remanescentes": total_rejected,
            "fato": total_loaded,
            "conciliada": lines_read == total_removed + total_rejected + total_loaded,
        },
    }
    quality = _quality_frame(metrics)
    quality.to_csv(output_dir / "resumo_qualidade.csv", index=False, encoding="utf-8")

    db_result: dict = {"carga_postgresql": "nao_executada"}
    if load_database:
        db_schema = schema or os.getenv("PGSCHEMA", "dw_etl")
        print(f"[ETL] Carregando PostgreSQL no schema {db_schema}...", flush=True)
        engine = _postgres_engine()
        try:
            db_result = _load_postgres(
                engine, db_schema, raw, treated, duplicates_audit, reject_output,
                anomaly_output, post_normalization_duplicates, dimensions, fact, quality, file_log, replace,
            )
            db_result["carga_postgresql"] = "concluida"
        finally:
            engine.dispose()
    else:
        print("[ETL] Carga no PostgreSQL ignorada (--skip-db).", flush=True)

    metrics.update(db_result)
    (output_dir / "etl_resumo.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print("[ETL] Processo concluído. Resumo:")
    print(json.dumps(metrics, ensure_ascii=False, indent=2, default=str))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETL VRA/ANAC 2019 conforme o Contrato Único de Dados v1.1."
    )
    parser.add_argument("--input-dir", required=True, help="Pasta com VRA_2019_01.csv a VRA_2019_12.csv")
    parser.add_argument("--output-dir", required=True, help="Pasta dos resultados e cópia da camada bruta")
    parser.add_argument("--schema", default=None, help="Schema PostgreSQL (padrão: dw_etl)")
    parser.add_argument("--replace", action="store_true", help="Apaga e recria somente as tabelas ETL listadas no schema")
    parser.add_argument("--skip-db", action="store_true", help="Executa tratamento e exportações sem carregar PostgreSQL")
    args = parser.parse_args()
    result = run_etl(
        args.input_dir,
        args.output_dir,
        load_database=not args.skip_db,
        replace=args.replace,
        schema=args.schema,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
