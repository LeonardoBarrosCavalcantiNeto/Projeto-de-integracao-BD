#!/usr/bin/env python3
"""Backup físico OFFLINE do cluster de teste; não acessa o banco do DataGrip.

Arquivo completo comprimido, SHA-256, extração em outro diretório e validação
SQL do cluster restaurado. Exige a mesma versão principal de PostgreSQL.
"""
import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from integrar_anac import ROOT, sha256_file
from espaco_disco import exigir_espaco
from testar_integracao_isolada import executar


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster',type=Path,default=ROOT/'.local/integracao/postgres_teste')
    parser.add_argument('--validation',type=Path,default=ROOT/'sql/integracao/04_validar.sql')
    parser.add_argument('--evidence',type=Path,default=ROOT/'resultados/validacoes/integracao_2019_2020')
    parser.add_argument('--prefix',default='isolado_2019_2020')
    args=parser.parse_args()
    if not args.prefix.replace('_','').isalnum():raise ValueError('Prefixo inválido')
    cluster=args.cluster.resolve();local=cluster.parent
    if not cluster.is_relative_to(ROOT/'.local'):raise ValueError('Apenas clusters locais do projeto')
    if (cluster/'postmaster.pid').exists():
        raise RuntimeError('Cluster ativo. Aguarde todos os testes terminarem antes do backup offline.')
    if not (cluster/'PG_VERSION').is_file():raise RuntimeError('Cluster de teste ausente')
    backup=ROOT/'backups'
    files=[p.stat() for p in cluster.rglob('*') if p.is_file() and not p.is_symlink()]
    # Não depende da taxa de compressão. Margem para blocos, cabeçalhos e WAL
    # potencial da verificação PostgreSQL na cópia restaurada.
    size=sum(entry.st_size for entry in files)
    archive_peak=size+8192*len(files)+64*1024**2
    restore_peak=size+8192*len(files)+1024**3
    backup_volume=backup if backup.exists() else backup.parent
    if backup_volume.stat().st_dev==local.stat().st_dev:
        exigir_espaco(local,archive_peak+restore_peak,'backup com teste de restauração')
    else:
        exigir_espaco(backup,archive_peak,'criação do backup')
        exigir_espaco(local,restore_peak,'teste de restauração')
    backup.mkdir(exist_ok=True)
    os.chmod(backup,0o700)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    dump=backup/f'{args.prefix}_{stamp}.tar.gz'
    restored=local/f'restauracao_{stamp}';restored.mkdir()
    subprocess.run(['tar','-I','gzip -1','-cf',str(dump),'-C',str(local),cluster.name],check=True,capture_output=True)
    os.chmod(dump,0o600)
    exigir_espaco(local,restore_peak,'extração do backup de teste')
    subprocess.run(['tar','-xzf',str(dump),'-C',str(restored)],check=True,capture_output=True)
    checks=args.validation.read_text()
    log=backup/f'{args.prefix}_{stamp}_restauracao.log'
    executar(restored/cluster.name,checks,log)
    report=dict(tipo='backup_fisico_offline_cluster_isolado',
                bancos_nativos_acessados=False,database='postgres',
                pg_version=(cluster/'PG_VERSION').read_text().strip(),
                arquivo=str(dump),sha256=sha256_file(dump),bytes=dump.stat().st_size,
                restaurado_em=str(restored/cluster.name),validacao_restauracao=str(log),
                restauracao_validada=True)
    (backup/f'{args.prefix}_{stamp}.json').write_text(json.dumps(report,indent=2)+'\n')
    evidence=args.evidence
    evidence.mkdir(parents=True,exist_ok=True)
    (evidence/'backup_isolado.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
