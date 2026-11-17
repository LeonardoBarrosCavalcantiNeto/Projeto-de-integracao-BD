"""Constrói o cadastro compartilhado a partir de saídas tratadas dos três anos."""
import argparse
from pathlib import Path
import pandas as pd
from etl_vra_anac_2020 import aeroportos, ROOT, json_salvar


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tratadas", nargs="+", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--registro-existente", help="Cadastro anterior: mantém os IDs já atribuídos")
    p.add_argument("--experimental", action="store_true", help="Aceita uma amostra parcial; sem isso exige 2019, 2020 e 2021")
    args = p.parse_args()
    colunas = ["aeroporto_origem", "aeroporto_destino", "descricao_origem", "descricao_destino",
               "ano_origem", "arquivo_origem", "linha_origem"]
    tipos = {c: "string" for c in colunas}
    tipos.update(ano_origem="Int64", linha_origem="Int64")
    frames = [pd.read_csv(path, usecols=colunas, dtype=tipos) for path in args.tratadas]
    anos = sorted(set(int(y) for frame in frames for y in frame.ano_origem.dropna().unique()))
    if not args.experimental and anos != [2019, 2020, 2021]:
        raise ValueError(f"Consolidação requer 2019, 2020 e 2021. Anos encontrados: {anos}")
    registry = pd.read_csv(args.registro_existente) if args.registro_existente else None
    rules = pd.read_csv(ROOT / "documentacao/resolucoes_aeroportos_2020.csv", keep_default_na=False)
    dim, conflicts, observed, applied = aeroportos(frames, rules, registry)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    conflicts.to_csv(output / "conflitos_dim_aeroporto.csv", index=False)
    observed.to_csv(output / "origens_dim_aeroporto.csv.gz", index=False)
    applied.to_csv(output / "resolucoes_aplicadas.csv.gz", index=False)
    if dim is None:
        raise ValueError("Existem conflitos novos. Evidências exportadas; dimensão não publicada.")
    dim.to_csv(output / "dim_aeroporto.csv", index=False)
    json_salvar(output / "escopo.json", dict(anos=anos, consolidada=anos == [2019, 2020, 2021], aeroportos=len(dim)))


if __name__ == "__main__":
    main()
