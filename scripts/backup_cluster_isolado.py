#!/usr/bin/env python3
"""Backup físico OFFLINE do cluster de teste; não acessa o banco do DataGrip.

Arquivo completo comprimido, SHA-256, extração em outro diretório e validação
SQL do cluster restaurado. Exige a mesma versão principal de PostgreSQL.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from integrar_anac import ROOT, sha256_file
from testar_integracao_isolada import executar


def main():
    local=ROOT/'.local/integracao';cluster=local/'postgres_teste'
    if (cluster/'postmaster.pid').exists():
        raise RuntimeError('Cluster ativo. Aguarde todos os testes terminarem antes do backup offline.')
    if not (cluster/'PG_VERSION').is_file():raise RuntimeError('Cluster de teste ausente')
    backup=ROOT/'backups';backup.mkdir(exist_ok=True);os.chmod(backup,0o700)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    dump=backup/f'isolado_2019_2020_{stamp}.tar.gz'
    restored=local/f'restauracao_{stamp}';restored.mkdir()
    subprocess.run(['tar','-I','gzip -1','-cf',str(dump),'-C',str(local),'postgres_teste'],check=True,capture_output=True)
    os.chmod(dump,0o600)
    subprocess.run(['tar','-xzf',str(dump),'-C',str(restored)],check=True,capture_output=True)
    checks=(ROOT/'sql/integracao/04_validar.sql').read_text()
    log=backup/f'isolado_2019_2020_{stamp}_restauracao.log'
    executar(restored/'postgres_teste',checks,log)
    report=dict(tipo='backup_fisico_offline_cluster_isolado',
                banco_original_anac_dw_acessado=False,database='postgres',
                pg_version=(cluster/'PG_VERSION').read_text().strip(),
                arquivo=str(dump),sha256=sha256_file(dump),bytes=dump.stat().st_size,
                restaurado_em=str(restored/'postgres_teste'),validacao_restauracao=str(log),
                restauracao_validada=True)
    (backup/f'isolado_2019_2020_{stamp}.json').write_text(json.dumps(report,indent=2)+'\n')
    evidence=ROOT/'resultados/validacoes/integracao_2019_2020'
    evidence.mkdir(parents=True,exist_ok=True)
    (evidence/'backup_isolado.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
