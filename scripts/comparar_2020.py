"""Comparação somente de leitura entre dados já carregados ETL e ELT 2020."""
import argparse
import re
from sqlalchemy import text
from etl_vra_anac_2020 import CANONICAS, METRICAS, conectar, json_salvar


def comparar(engine, etl="etl_2020", elt="elt_2020"):
    for name in [etl, elt]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError("Schema inválido.")
    columns = CANONICAS + METRICAS + ["partida_atipica_flag", "chegada_atipica_flag"]
    diff = " OR ".join(f'e."{c}" IS DISTINCT FROM l."{c}"' for c in columns)
    join = "e.arquivo_origem=l.arquivo_origem AND e.linha_origem=l.linha_origem"
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        result = dict(conn.execute(text(f'''SELECT
          count(*) FILTER (WHERE l.arquivo_origem IS NULL) AS somente_etl,
          count(*) FILTER (WHERE e.arquivo_origem IS NULL) AS somente_elt,
          count(*) FILTER (WHERE e.arquivo_origem IS NOT NULL AND l.arquivo_origem IS NOT NULL AND ({diff})) AS registros_divergentes,
          count(*) FILTER (WHERE e.arquivo_origem IS NOT NULL AND l.arquivo_origem IS NOT NULL) AS comparados
          FROM "{etl}".vra_tratada e FULL JOIN "{elt}".vra_tratada l ON {join}''')).mappings().one())
        for table in ["vra_bruta", "vra_duplicatas_excluidas", "vra_rejeicoes", "vra_tratada"]:
            result[table] = {label: conn.execute(text(f'SELECT count(*) FROM "{schema}"."{table}"')).scalar_one() for label, schema in [("etl", etl), ("elt", elt)]}
        # Mesmo total não basta: confere a identidade dos brutos, rejeitados e descartados.
        for table in ["vra_bruta", "vra_duplicatas_excluidas", "vra_rejeicoes"]:
            result[f"origens_divergentes_{table}"] = conn.execute(text(f'''SELECT count(*) FROM (
              (SELECT arquivo_origem,linha_origem FROM "{etl}"."{table}" EXCEPT SELECT arquivo_origem,linha_origem FROM "{elt}"."{table}")
              UNION ALL
              (SELECT arquivo_origem,linha_origem FROM "{elt}"."{table}" EXCEPT SELECT arquivo_origem,linha_origem FROM "{etl}"."{table}")
            ) d''')).scalar_one()
        from etl_vra_anac_2020 import ORIGINAIS
        raw_diff = " OR ".join(f'e."{c}" IS DISTINCT FROM l."{c}"' for c in ORIGINAIS)
        result["brutos_valores_divergentes"] = conn.execute(text(f'''SELECT count(*) FROM "{etl}".vra_bruta e JOIN "{elt}".vra_bruta l ON {join} WHERE {raw_diff}''')).scalar_one()
    result["equivalente"] = (all(result[k] == 0 for k in ["somente_etl", "somente_elt", "registros_divergentes", "brutos_valores_divergentes"])
                             and all(v["etl"] == v["elt"] for v in result.values() if isinstance(v, dict))
                             and all(v == 0 for k, v in result.items() if k.startswith("origens_divergentes_")))
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--elt-schema", default="elt_2020")
    p.add_argument("--output", default="resultados/validacoes/comparacao_etl_elt_2020.json")
    args = p.parse_args()
    engine, schema = conectar()
    try:
        result = comparar(engine, schema, args.elt_schema)
        json_salvar(args.output, result)
        print(result)
    finally:
        engine.dispose()
