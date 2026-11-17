"""ETL 2020, contrato v1.1. A carga é opcional e nunca substitui tabelas.

Python trata os dados antes da carga; CSVs originais permanecem intactos.
O DW experimental de 2020 não é o DW consolidado dos três anos.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pandas as pd

ANO = 2020
VERSAO = "1.1"
ROOT = Path(__file__).resolve().parents[1]
# Reutiliza somente o construtor de estrela já integrado pelo grupo, em uma
# instância independente do módulo; não modifica o pipeline/arquivo de 2019.
_spec = importlib.util.spec_from_file_location("estrela_experimental_2020", ROOT / "scripts/etl_vra_anac_2019.py")
_estrela = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_estrela)
_estrela.ANO = ANO
MAPA = _estrela.MAPA_COLUNAS
ORIGINAIS = list(MAPA)
CANONICAS = list(MAPA.values())
UPPER = _estrela.UPPER_COLS
META = _estrela.METADATA_COLS
CHAVE = ["ano_origem", "arquivo_origem", "linha_origem"]
DATAS = ["partida_prevista", "partida_real", "chegada_prevista", "chegada_real"]
METRICAS = [f"{m}_{e}_min" for e in ["partida", "chegada"] for m in ["diferenca", "atraso"]]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def texto(serie):
    s = serie.astype("string").str.strip()
    return s.mask(s.eq(""), pd.NA)


def extrair(input_dir):
    """Confere arquivos, cabeçalhos, largura CSV e hashes; não escreve na fonte."""
    pasta = Path(input_dir)
    files = sorted(pasta.glob("*.csv"))
    expected = [f"VRA_{ANO}_{m:02}.csv" for m in range(1, 13)]
    if [p.name for p in files] != expected:
        raise ValueError("A entrada deve conter exatamente VRA_2020_01.csv a VRA_2020_12.csv.")
    frames, inventory = [], []
    carga = pd.Timestamp.now(tz="UTC")
    for path in files:
        digest = sha256(path)
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, delimiter=";", strict=True)
            if next(reader, None) != ORIGINAIS:
                raise ValueError(f"Cabeçalho divergente: {path.name}")
            count = 0
            for count, row in enumerate(reader, 1):
                if len(row) != 20:
                    raise ValueError(f"Largura inválida: {path.name}, registro {count+1}")
        frame = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str,
                            na_filter=False, keep_default_na=False, skip_blank_lines=False)
        assert len(frame) == count
        frame["arquivo_origem"] = path.name
        frame["linha_origem"] = range(2, len(frame) + 2)
        frame["ano_origem"] = ANO
        frame["data_carga"] = carga
        frame["pipeline"] = "ETL"
        frame["versao_contrato"] = VERSAO
        frames.append(frame)
        inventory.append(dict(arquivo_origem=path.name, registros_brutos=count,
                              tamanho_bytes=path.stat().st_size, sha256=digest))
    return pd.concat(frames, ignore_index=True), pd.DataFrame(inventory)


def normalizar(raw):
    """Converte uma cópia; campos opcionais inválidos geram anomalias, não rejeições."""
    converted = raw[ORIGINAIS].rename(columns=MAPA).copy()
    for field in CANONICAS:
        converted[field] = texto(converted[field])
    for field in UPPER:
        converted[field] = converted[field].str.upper()
    # Chave de diagnóstico apenas textual, antes de datas/números.
    padronizados = converted.copy()
    rejected = pd.Series(False, index=raw.index)
    details = []

    def registrar(field, mask, reason, kind):
        nonlocal rejected
        mask = mask.fillna(False)
        if kind == "REJEICAO":
            rejected |= mask
        original = next(k for k, v in MAPA.items() if v == field)
        d = raw.loc[mask, CHAVE + [original]].rename(columns={original: "valor_original"}).copy()
        d["campo"] = field
        d["motivo"] = reason
        d["tipo"] = kind
        details.append(d)

    for field in ["companhia_icao", "aeroporto_origem", "aeroporto_destino"]:
        # Mesma política do ELT da dupla: ausência após padronização.
        registrar(field, converted[field].isna(), "CAMPO_OBRIGATORIO_AUSENTE", "REJEICAO")
    for field in DATAS + ["referencia"]:
        source = converted[field]
        pattern, fmt = (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "%Y-%m-%d") if field == "referencia" else (
            r"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}", "%d/%m/%Y %H:%M")
        parsed = pd.to_datetime(source.where(source.str.fullmatch(pattern, na=False)),
                                format=fmt, exact=True, errors="coerce")
        required = field in ["partida_prevista", "chegada_prevista"]
        registrar(field, source.notna() & parsed.isna(), "DATA_PREENCHIDA_INVALIDA",
                  "REJEICAO" if required else "ANOMALIA")
        if required:
            registrar(field, source.isna(), "CAMPO_OBRIGATORIO_AUSENTE", "REJEICAO")
        converted[field] = parsed.dt.date if field == "referencia" else parsed
    source = converted["numero_assentos"]
    n = pd.to_numeric(source.where(source.str.fullmatch(r"[0-9]+", na=False)), errors="coerce")
    ok = n.between(0, 2147483647).fillna(False)
    registrar("numero_assentos", source.notna() & ~ok, "ASSENTOS_INVALIDOS", "ANOMALIA")
    converted["numero_assentos"] = n.where(ok).astype("Int64")
    converted = pd.concat([converted, raw[META]], axis=1)
    converted["rejeitado"] = rejected
    audit = pd.concat(details, ignore_index=True)
    return converted, audit, padronizados


def metricas(base):
    result = base.drop(columns="rejeitado", errors="ignore").copy()
    for event in ["partida", "chegada"]:
        difference = (result[f"{event}_real"] - result[f"{event}_prevista"]).dt.total_seconds().div(60).astype("Float64")
        result[f"diferenca_{event}_min"] = difference
        result[f"atraso_{event}_min"] = difference.clip(lower=0)
        result[f"{event}_atipica_flag"] = difference.abs().gt(1440).fillna(False).astype(bool)
    result["partida_ano_diverge_flag"] = result.partida_prevista.dt.year.ne(result.ano_origem)
    result["quantidade_voos"] = 1
    return result


def preparar(raw):
    """Deduplica antes de padronizar; preserva todas as violações para auditoria."""
    extra = raw.duplicated(ORIGINAIS, keep="first")
    involved = raw.duplicated(ORIGINAIS, keep=False)
    representatives = raw.loc[involved & ~extra, ORIGINAIS + CHAVE].rename(columns={
        "ano_origem": "ano_preservado", "arquivo_origem": "arquivo_preservado", "linha_origem": "linha_preservada"})
    duplicates = raw.loc[extra].merge(representatives, on=ORIGINAIS, how="left", validate="many_to_one")
    converted, audit, normalized_text = normalizar(raw)
    duplicates = duplicates.merge(converted[CHAVE + ["rejeitado"]].rename(
        columns={"rejeitado": "duplicata_invalida_flag"}), on=CHAVE, validate="one_to_one")
    dedup = converted.loc[~extra]
    valid = dedup.loc[~dedup.rejeitado]
    treated = metricas(valid)
    reject = raw.loc[~extra & converted.rejeitado].copy()
    reason_rows = audit[audit.tipo.eq("REJEICAO")].copy()
    reasons_grouped = reason_rows.assign(detalhe=reason_rows.campo + ":" + reason_rows.motivo).groupby(CHAVE).agg(
        campos_invalidos=("campo", list), motivos_rejeicao=("detalhe", list)).reset_index()
    reject = reject.merge(reasons_grouped, on=CHAVE, how="left", validate="one_to_one")
    reason_rows = reason_rows.merge(raw.loc[~extra, CHAVE], on=CHAVE, validate="many_to_one")
    candidates = normalized_text.loc[~extra]
    candidate_mask = candidates.duplicated(CANONICAS, keep=False)
    possible = raw.loc[candidates.index[candidate_mask]].copy()
    anomalies = audit[audit.tipo.eq("ANOMALIA")].merge(raw.loc[~extra, CHAVE], on=CHAVE, validate="many_to_one")
    # O ano fora de 2020 é diagnóstico; não rejeita uma data válida.
    divergence = treated.loc[treated.partida_ano_diverge_flag, CHAVE + ["partida_prevista"]]
    yearly = raw.groupby("arquivo_origem").size().rename("brutos").to_frame()
    for label, frame in [("duplicatas", duplicates), ("rejeitados", reject), ("tratados", treated)]:
        yearly[label] = frame.groupby("arquivo_origem").size().reindex(yearly.index, fill_value=0)
    assert yearly.brutos.eq(yearly.duplicatas + yearly.rejeitados + yearly.tratados).all()
    assert len(raw) == len(duplicates) + len(reject) + len(treated)
    assert not treated.duplicated(CHAVE).any()
    assert treated[["companhia_icao", "aeroporto_origem", "aeroporto_destino", "partida_prevista", "chegada_prevista"]].notna().all().all()
    summary = {
        "ano_origem": ANO, "versao_contrato": VERSAO,
        "brutos": len(raw), "duplicatas_excedentes": len(duplicates),
        "grupos_duplicados": len(representatives), "linhas_envolvidas_duplicatas": int(involved.sum()),
        "rejeitados": len(reject), "tratados": len(treated), "motivos_rejeicao": len(reason_rows),
        "intersecao_excedentes_invalidos": int((extra & converted.rejeitado).sum()),
        "possiveis_duplicatas_apos_padronizacao": len(possible),
        "anomalias_opcionais": len(anomalies), "partidas_ano_divergente": len(divergence),
        "partidas_reais_nulas": int(treated.partida_real.isna().sum()),
        "chegadas_reais_nulas": int(treated.chegada_real.isna().sum()),
        "partidas_atipicas": int(treated.partida_atipica_flag.sum()),
        "chegadas_atipicas": int(treated.chegada_atipica_flag.sum()),
        "reconciliacao_ok": True,
    }
    frames = {"vra_bruta": raw, "vra_tratada": treated, "vra_duplicatas_excluidas": duplicates,
              "vra_rejeicoes": reject, "motivos_rejeicao": reason_rows, "vra_anomalias": anomalies,
              "vra_possiveis_duplicatas_padronizacao": possible,
              "partidas_ano_divergente": divergence, "mensal": yearly.reset_index()}
    return frames, summary


def aeroportos(tratadas, resolucoes=None, registro=None):
    """Combina origem/destino de vários anos; preserva IDs de um registro existente.

    Resoluções são exatas por código + descrição original e ficam documentadas.
    Conflitos novos bloqueiam a publicação, sem escolher a primeira descrição.
    """
    pairs = []
    for frame in tratadas:
        for role in ["origem", "destino"]:
            p = frame[[f"aeroporto_{role}", f"descricao_{role}"] + CHAVE].rename(columns={
                f"aeroporto_{role}": "aeroporto_icao", f"descricao_{role}": "descricao_aeroporto"}).copy()
            p["papel"] = role
            pairs.append(p)
    observed = pd.concat(pairs, ignore_index=True)
    corrected = observed.copy()
    applied = []
    if resolucoes is not None and len(resolucoes):
        if resolucoes.duplicated(["aeroporto_icao", "descricao_original"]).any():
            raise ValueError("Resoluções duplicadas para a mesma descrição.")
        for row in resolucoes.itertuples(index=False):
            if not row.fonte_url or not row.justificativa:
                raise ValueError("Resolução sem fonte ou justificativa.")
            mask = corrected.aeroporto_icao.eq(row.aeroporto_icao) & corrected.descricao_aeroporto.eq(row.descricao_original)
            d = corrected.loc[mask].copy()
            d["descricao_original"] = d.descricao_aeroporto
            d["descricao_resolvida"] = row.descricao_resolvida
            d["fonte_url"] = row.fonte_url
            applied.append(d)
            corrected.loc[mask, "descricao_aeroporto"] = row.descricao_resolvida
    distinct = corrected[["aeroporto_icao", "descricao_aeroporto"]].drop_duplicates()
    conflicts = distinct.groupby("aeroporto_icao").descricao_aeroporto.nunique().gt(1)
    conflicts = distinct[distinct.aeroporto_icao.isin(conflicts[conflicts].index)]
    if len(conflicts):
        return None, conflicts, observed, pd.concat(applied, ignore_index=True) if applied else pd.DataFrame()
    # Só uma descrição não nula por código após a conferência de conflitos.
    dim = distinct.sort_values("descricao_aeroporto", na_position="last").drop_duplicates("aeroporto_icao")
    dim = dim.sort_values("aeroporto_icao").reset_index(drop=True)
    registry = {} if registro is None else dict(zip(registro.aeroporto_icao, registro.id_aeroporto))
    if registro is not None and (registro.aeroporto_icao.duplicated().any() or registro.id_aeroporto.duplicated().any()):
        raise ValueError("Registro dimensional com chaves duplicadas.")
    next_id = max(registry.values(), default=0) + 1
    for code in dim.aeroporto_icao:
        if code not in registry:
            registry[code] = next_id
            next_id += 1
    dim.insert(0, "id_aeroporto", dim.aeroporto_icao.map(registry))
    return dim, conflicts, observed, pd.concat(applied, ignore_index=True) if applied else pd.DataFrame()


def construir_estrela(treated, dim_airport):
    """Estrela de teste 2020; a consolidação final continua sendo uma etapa do grupo."""
    base = treated.copy()
    lookup = dim_airport.set_index("aeroporto_icao").descricao_aeroporto
    for role in ["origem", "destino"]:
        base[f"descricao_{role}"] = base[f"aeroporto_{role}"].map(lookup)
    dims, fact, conflicts = _estrela._build_star(base)
    if len(conflicts):
        return None, None, conflicts
    # O cadastro fornecido pode ter IDs persistentes, diferentes da ordem alfabética.
    dims["dim_aeroporto"] = dim_airport
    ids = dim_airport.set_index("aeroporto_icao").id_aeroporto
    for role in ["origem", "destino"]:
        fact[f"id_aeroporto_{role}"] = base[f"aeroporto_{role}"].map(ids).reset_index(drop=True).astype("Int64")
    assert len(fact) == len(treated)
    for col, table, key, optional in relacionamentos():
        known = fact[col].dropna()
        assert known.isin(dims[table][key]).all(), col
        if not optional:
            assert fact[col].notna().all(), col
    return dims, fact, conflicts


def relacionamentos():
    return [
        ("id_companhia", "dim_companhia_aerea", "id_companhia", False),
        ("id_aeroporto_origem", "dim_aeroporto", "id_aeroporto", False),
        ("id_aeroporto_destino", "dim_aeroporto", "id_aeroporto", False),
        ("id_tempo_partida", "dim_tempo", "id_tempo", False),
        ("id_tempo_chegada", "dim_tempo", "id_tempo", False),
        ("id_situacao", "dim_situacao_voo", "id_situacao", True),
        ("id_justificativa", "dim_justificativa", "id_justificativa", False),
        ("id_tipo_linha", "dim_tipo_linha", "id_tipo_linha", True),
        ("id_equipamento", "dim_equipamento", "id_equipamento", False),
    ]


def json_salvar(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def executar(input_dir, output_dir, resolucoes=None, *, extraidos=None, preparados=None):
    raw, inventory = extraidos if extraidos is not None else extrair(input_dir)
    frames, summary = preparados if preparados is not None else preparar(raw)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rules_path = Path(resolucoes or ROOT / "documentacao/resolucoes_aeroportos_2020.csv")
    rules = pd.read_csv(rules_path, dtype=str, keep_default_na=False) if rules_path.exists() else None
    dim, conflicts, observed, applied = aeroportos([frames["vra_tratada"]], rules)
    conflicts.to_csv(output / "conflitos_aeroportos.csv", index=False)
    frames["resolucoes_aeroportos_aplicadas"] = applied
    dims, fact, star_conflicts = construir_estrela(frames["vra_tratada"], dim) if dim is not None else (None, None, conflicts)
    # Auditorias e dados tratados são exportados mesmo se houver conflito dimensional.
    for name, frame in frames.items():
        if name != "vra_bruta":
            frame.to_csv(output / f"{name}.csv.gz", index=False, na_rep="", compression={"method": "gzip", "mtime": 0})
    inventory.to_csv(output / "inventario_arquivos.csv", index=False)
    observed.drop_duplicates(["aeroporto_icao", "descricao_aeroporto"]).to_csv(output / "aeroportos_observados.csv", index=False)
    summary.update(carga_postgresql="nao_executada", estrela_pronta=dims is not None,
                   escopo_dimensoes="experimental_2020; integrar 2019 e 2021 antes da consolidacao")
    star_conflicts.to_csv(output / "conflitos_dimensoes.csv", index=False)
    if dims is not None:
        for name, frame in dims.items():
            frame.to_csv(output / f"{name}.csv", index=False)
        fact.to_csv(output / "fato_voo.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
        summary["dimensoes"] = {k: len(v) for k, v in dims.items()}
    fingerprint = hashlib.sha256(json.dumps({
        "fontes": inventory.to_dict("records"), "contrato": VERSAO,
        "codigo": sha256(__file__), "construtor_estrela": sha256(ROOT / "scripts/etl_vra_anac_2019.py"),
        "resolucoes": sha256(rules_path) if rules_path.exists() else None,
    }, sort_keys=True).encode()).hexdigest()
    summary["fingerprint"] = fingerprint
    summary["fontes_preservadas"] = all(sha256(Path(input_dir) / r.arquivo_origem) == r.sha256 for r in inventory.itertuples())
    assert summary["fontes_preservadas"]
    frames["resumo_qualidade"] = pd.DataFrame([
        {"indicador": k, "valor": json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else str(v)}
        for k, v in summary.items()
    ])
    frames["log_carga_arquivo"] = frames["mensal"].assign(ano_origem=ANO)
    frames["resumo_qualidade"].to_csv(output / "resumo_qualidade.csv", index=False)
    frames["log_carga_arquivo"].to_csv(output / "log_carga_arquivo.csv", index=False)
    json_salvar(output / "etl_resumo.json", summary)
    return dict(frames=frames, inventory=inventory, dims=dims, fact=fact, summary=summary, output=output)


def conectar(env_path=None):
    """Lê credenciais sem imprimir senha; não cria banco nem schema."""
    import os
    from dotenv import dotenv_values
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    config = {**dotenv_values(env_path or ROOT / ".env"), **os.environ}
    url = config.get("DATABASE_URL")
    if not url:
        required = [k for k in ["PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD"] if not config.get(k)]
        if required:
            raise ValueError("Configure no .env: " + ", ".join(required))
        url = URL.create("postgresql+psycopg", username=config["PGUSER"], password=config["PGPASSWORD"],
                         host=config["PGHOST"], port=int(config.get("PGPORT", 5432)), database=config["PGDATABASE"])
    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    schema = config.get("PGSCHEMA", "etl_2020")
    if not re.fullmatch(r"etl_2020(?:_[A-Za-z0-9_]+)?", schema):
        engine.dispose()
        raise ValueError("O ETL de teste exige PGSCHEMA=etl_2020 (ou etl_2020_<sufixo>).")
    return engine, schema


def salvar_evidencias(resultado, pasta=None):
    """Publica evidências pequenas; dados completos continuam em dados/processados."""
    import shutil
    destino = Path(pasta or ROOT / "resultados")
    for subdir in ["logs", "validacoes", "rejeicoes"]:
        (destino / subdir).mkdir(parents=True, exist_ok=True)
    resultado["inventory"].to_csv(destino / "logs/inventario_arquivos_etl_2020.csv", index=False)
    json_salvar(destino / "logs/metadados_execucao_etl_2020.json", resultado["summary"])
    frames = resultado["frames"]
    for name in ["vra_duplicatas_excluidas", "vra_rejeicoes", "motivos_rejeicao"]:
        shutil.copyfile(resultado["output"] / f"{name}.csv.gz", destino / f"rejeicoes/{name}_etl_2020.csv.gz")
    for name in ["vra_anomalias", "partidas_ano_divergente", "resolucoes_aeroportos_aplicadas"]:
        shutil.copyfile(resultado["output"] / f"{name}.csv.gz", destino / f"validacoes/{name}_etl_2020.csv.gz")
    frames["resumo_qualidade"].to_csv(destino / "validacoes/resumo_qualidade_etl_2020.csv", index=False)
    frames["mensal"].to_csv(destino / "validacoes/mensal_etl_2020.csv", index=False)
    treated = frames["vra_tratada"]
    situations = treated.groupby("situacao_voo", dropna=False).size().rename("registros")
    situations.to_csv(destino / "validacoes/situacao_voo_etl_2020.csv")
    suspicious = treated[treated.partida_atipica_flag | treated.chegada_atipica_flag]
    suspicious[CHAVE + DATAS + METRICAS + ["partida_atipica_flag", "chegada_atipica_flag"]].to_csv(
        destino / "validacoes/atipicos_etl_2020.csv", index=False)
    if resultado["dims"] is not None:
        resultado["dims"]["dim_aeroporto"].to_csv(destino / "validacoes/dim_aeroporto_experimental_2020.csv", index=False)
    # Análise conjunta proposta: mês do arquivo, sem confundir situação ausente com cancelamento.
    mensal = pd.crosstab(treated.arquivo_origem.str.slice(9, 11).astype(int).rename("mes_arquivo"), treated.situacao_voo)
    mensal = mensal.reindex(columns=["REALIZADO", "CANCELADO", "NÃO INFORMADO"], fill_value=0)
    mensal["voos_elegiveis"] = mensal.sum(axis=1)
    mensal["percentual_cancelados"] = (100 * mensal.CANCELADO / mensal.voos_elegiveis).round(2)
    mensal.to_csv(destino / "validacoes/analise_2_mensal_2020.csv")
    preliminary = dict(comparacao_por_registro_executada=False, status="aguardando_cargas_etl_e_elt")
    elt_inventory = destino / "logs/inventario_arquivos_elt_2020.csv"
    elt_quality = destino / "validacoes/resumo_qualidade_elt_2020.csv"
    if elt_inventory.exists() and elt_quality.exists():
        other = pd.read_csv(elt_inventory)
        joined = resultado["inventory"].merge(other, on="arquivo_origem", suffixes=("_etl", "_elt"), validate="one_to_one")
        preliminary["doze_hashes_iguais"] = len(joined) == 12 and bool(joined.sha256_etl.eq(joined.sha256_elt).all())
        old = pd.read_csv(elt_quality).iloc[0]
        mapping = {"brutos": "bruta", "duplicatas_excedentes": "duplicatas_excedentes", "rejeitados": "rejeicoes", "tratados": "tratada",
                   "partidas_atipicas": "partidas_atipicas", "chegadas_atipicas": "chegadas_atipicas",
                   "partidas_reais_nulas": "partidas_reais_nulas", "chegadas_reais_nulas": "chegadas_reais_nulas"}
        preliminary["indicadores_publicados_iguais"] = all(resultado["summary"][k] == int(old[v]) for k, v in mapping.items())
    json_salvar(destino / "validacoes/comparacao_preliminar_etl_elt_2020.json", preliminary)


def carregar(resultado, engine, schema="etl_2020"):
    """Transação única e reexecução idempotente. Não apaga/substitui tabelas existentes.

    Chamar somente por decisão explícita de quem executa o notebook.
    """
    from sqlalchemy import text as sql, Text, Integer, BigInteger, Date, DateTime, Numeric, Boolean
    from psycopg import sql as pgsql
    if not re.fullmatch(r"etl_2020(?:_[A-Za-z0-9_]+)?", schema):
        raise ValueError("Schema experimental inválido.")
    if resultado["dims"] is None:
        raise ValueError("Resolva os conflitos dimensionais antes da carga.")
    frames = {**resultado["frames"], **resultado["dims"], "fato_voo": resultado["fact"]}
    frames = {k: v for k, v in frames.items() if k not in ["mensal", "partidas_ano_divergente", "resolucoes_aeroportos_aplicadas"]}
    # Listas dos motivos viram JSON textual, sem perda da informação.
    frames = {k: v.copy() for k, v in frames.items()}
    for col in ["campos_invalidos", "motivos_rejeicao"]:
        if col in frames["vra_rejeicoes"]:
            frames["vra_rejeicoes"][col] = frames["vra_rejeicoes"][col].map(json.dumps)
    fingerprint = resultado["summary"]["fingerprint"]
    q = f'"{schema}"'
    with engine.begin() as conn:
        conn.execute(sql("SELECT pg_advisory_xact_lock(hashtext(:s))"), {"s": schema})
        conn.execute(sql(f"CREATE SCHEMA IF NOT EXISTS {q}"))
        conn.execute(sql(f"CREATE TABLE IF NOT EXISTS {q}.execucoes (fingerprint TEXT PRIMARY KEY, concluida_em TIMESTAMPTZ NOT NULL DEFAULT now())"))
        known = conn.execute(sql(f"SELECT fingerprint FROM {q}.execucoes")).scalars().all()
        existing = conn.execute(sql("SELECT table_name FROM information_schema.tables WHERE table_schema=:s AND table_name <> 'execucoes'"), {"s": schema}).scalars().all()
        if fingerprint in known:
            counts = {name: conn.execute(sql(f'SELECT count(*) FROM {q}."{name}"')).scalar_one() for name in frames}
            if any(counts[k] != len(v) for k, v in frames.items()):
                raise ValueError("Carga registrada mas contagens divergentes; investigar sem substituir dados.")
            return dict(status="ja_carregada", contagens=counts)
        if known or existing:
            raise ValueError("Schema contém dados de outra execução. Use outro schema experimental; nada foi substituído.")
        for name, frame in frames.items():
            types = {}
            for col in frame:
                if name == "vra_bruta" and col in ORIGINAIS:
                    types[col] = Text()
                elif col in DATAS:
                    types[col] = DateTime()
                elif col == "data_carga":
                    types[col] = DateTime(timezone=True)
                elif col in ["referencia", "data"]:
                    types[col] = Date()
                elif col in METRICAS:
                    types[col] = Numeric(12, 2)
                elif col.endswith("flag"):
                    types[col] = Boolean()
                elif pd.api.types.is_integer_dtype(frame[col]):
                    types[col] = BigInteger() if col == "id_voo" else Integer()
                else:
                    types[col] = Text()
            frame.head(0).to_sql(name, conn, schema=schema, if_exists="fail", index=False, dtype=types)
            safe = frame.astype(object).where(pd.notna(frame), None)
            statement = pgsql.SQL("COPY {}.{} ({}) FROM STDIN").format(pgsql.Identifier(schema), pgsql.Identifier(name), pgsql.SQL(", ").join(map(pgsql.Identifier, frame.columns)))
            with conn.connection.driver_connection.cursor() as cursor:
                with cursor.copy(statement) as copy:
                    for row in safe.itertuples(index=False, name=None):
                        copy.write_row(row)
        for name, frame in resultado["dims"].items():
            key = frame.columns[0]
            conn.execute(sql(f'ALTER TABLE {q}."{name}" ADD PRIMARY KEY ("{key}")'))
            natural = "data" if name == "dim_tempo" else frame.columns[1]
            conn.execute(sql(f'ALTER TABLE {q}."{name}" ADD UNIQUE ("{natural}")'))
        conn.execute(sql(f"ALTER TABLE {q}.fato_voo ADD PRIMARY KEY (id_voo), ADD UNIQUE (ano_origem, arquivo_origem, linha_origem), ADD CHECK (quantidade_voos=1)"))
        for col, table, key, optional in relacionamentos():
            conn.execute(sql(f'ALTER TABLE {q}.fato_voo ADD FOREIGN KEY ("{col}") REFERENCES {q}."{table}" ("{key}")'))
            if not optional:
                conn.execute(sql(f'ALTER TABLE {q}.fato_voo ALTER COLUMN "{col}" SET NOT NULL'))
        for col in ["partida_prevista", "chegada_prevista", *CHAVE]:
            conn.execute(sql(f'ALTER TABLE {q}.fato_voo ALTER COLUMN "{col}" SET NOT NULL'))
        for name in ["vra_bruta", "vra_tratada", "vra_rejeicoes", "vra_duplicatas_excluidas"]:
            conn.execute(sql(f'ALTER TABLE {q}."{name}" ADD UNIQUE (ano_origem, arquivo_origem, linha_origem)'))
        counts = {k: conn.execute(sql(f'SELECT count(*) FROM {q}."{k}"')).scalar_one() for k in frames}
        assert all(counts[k] == len(v) for k, v in frames.items())
        conn.execute(sql(f"INSERT INTO {q}.execucoes(fingerprint) VALUES (:f)"), {"f": fingerprint})
    report = dict(status="concluida", schema=schema, contagens=counts, foreign_key_orphans=0)
    json_salvar(resultado["output"] / "carga_postgresql.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default=str(ROOT / "dados/brutos/2020"))
    parser.add_argument("--output-dir", default=str(ROOT / "dados/processados/2020"))
    parser.add_argument("--carregar", action="store_true", help="Executar explicitamente a carga PostgreSQL após o tratamento")
    args = parser.parse_args()
    result = executar(args.input_dir, args.output_dir)
    salvar_evidencias(result)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    if args.carregar:
        engine, schema = conectar()
        try:
            print(carregar(result, engine, schema))
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
