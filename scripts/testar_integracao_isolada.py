#!/usr/bin/env python3
"""Executa bundle no PostgreSQL local em modo single-user (sem sockets).

Somente cluster novo de teste sob .local; não acessa o anac_dw do usuário.
Erros SQL também são detectados no log: backend single-user pode retornar zero.
"""
import argparse
import re
import subprocess
from pathlib import Path
from integrar_anac import ROOT, literal


def executar(cluster, sql, log):
    # -j: termina comandos com ponto e vírgula + linha vazia. O batch inteiro
    # é uma única entrada para preservar BEGIN/COMMIT e blocos PL/pgSQL.
    sql = '\n'.join(line for line in sql.splitlines() if line.strip())+'\n\n'
    with Path(log).open('w') as output:
        process = subprocess.run(['postgres','--single','-j','-D',str(cluster),
                                  '-c','logging_collector=off','postgres'],
                                 input=sql,text=True,stdout=output,stderr=subprocess.STDOUT)
    content=Path(log).read_text()
    if process.returncode or re.search(r'\b(?:ERROR|FATAL|PANIC):',content):
        raise RuntimeError(f'Falha PostgreSQL; consultar {log}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'.local/integracao/bundle')
    parser.add_argument('--cluster',type=Path,default=ROOT/'.local/integracao/postgres_teste')
    args=parser.parse_args()
    cluster=args.cluster.resolve(); bundle=args.bundle.resolve()
    if cluster.exists():
        raise ValueError('Cluster deve ser novo. Para consultas posteriores, usar executar().')
    cluster.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['initdb','-D',str(cluster),'-A','trust','--no-locale','-E','UTF8'],check=True,capture_output=True)
    sql=(bundle/'carga.sql').read_text()
    sql=re.sub(r'^\\copy (.*)$',r'COPY \1;',sql,flags=re.M)
    executar(cluster,sql,bundle/'postgres_carga.log')
    rerun='BEGIN;\n'+(ROOT/'sql/integracao/03_carga_dw.sql').read_text()+'\n'+(ROOT/'sql/integracao/04_validar.sql').read_text()+'\nCOMMIT;'
    executar(cluster,rerun,bundle/'postgres_reexecucao.log')
    for name in ['05_analises']:
        executar(cluster,(ROOT/f'sql/integracao/{name}.sql').read_text(),bundle/(name+'.log'))
    print(f'Integração e reexecução validadas em {cluster}. Logs em {bundle}')

if __name__=='__main__':
    main()
