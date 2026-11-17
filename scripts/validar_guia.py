#!/usr/bin/env python3
"""Valida referências locais, sintaxe Bash e Python embutido no manual.

Não instala ferramentas, não executa comandos administrativos nem conecta ao DB.
O parâmetro --bundle identifica os arquivos manuais gerados por prepare.
"""
import argparse
import ast
import json
import re
import subprocess
import textwrap
from pathlib import Path
from integrar_anac import ROOT, sha256_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'.local/integracao/bundle')
    args=parser.parse_args()
    result={'documentos':{},'erros':[]}
    for name in ['GUIA_EXECUCAO_COMPLETA','ORDEM_DOS_SCRIPTS']:
        doc=ROOT/f'documentacao/{name}.md'
        source=doc.read_text()
        refs=set(re.findall(r'(?<![\w/])(?:scripts|sql|tests|documentacao|relatorio)/[\w./-]+\.(?:py|sql|md|psql)\b',source))
        missing=[ref for ref in refs if not (ROOT/ref).is_file()]
        for target in re.findall(r'\]\(([^)]+)\)',source):
            if not re.match(r'https?://',target) and not (doc.parent/target.split('#')[0]).exists():
                missing.append(target)
        blocks=re.findall(r'^[ \t]*```bash\n(.*?)\n[ \t]*```',source,flags=re.S|re.M)
        for index,block in enumerate(blocks,1):
            block=textwrap.dedent(block)
            checked=subprocess.run(['bash','-n'],input=block,text=True,capture_output=True)
            if checked.returncode:result['erros'].append(f'{name}, bash {index}: {checked.stderr}')
            for python in re.findall(r"python - <<'PY'\n(.*?)\nPY",block,flags=re.S):
                ast.parse(python)
        generated=set(re.findall(r'\.local/integracao/bundle/manual/([\w.-]+\.(?:sql|psql))',source))
        missing += [f'manual/{file}' for file in generated if not (args.bundle/'manual'/file).is_file()]
        result['documentos'][name]={'referencias_versionadas':len(refs),'blocos_bash':len(blocks),
                                   'arquivos_gerados_referenciados':len(generated),'ausentes':missing}
        result['erros'].extend(f'{name}: {file}' for file in missing)
    manifest=json.loads((args.bundle/'manifesto.json').read_text())
    files={**manifest['raw_sha256'],'carga.sql':manifest['bundle_sha256']}
    files.update({'manual/'+name:digest for name,digest in manifest.get('manual_sha256',{}).items()})
    result['hashes_conferidos']=len(files)
    for name,expected in files.items():
        file=args.bundle/name
        if not file.is_file() or sha256_file(file)!=expected:
            result['erros'].append('Hash divergente ou arquivo ausente: '+name)
    manual=sorted((args.bundle/'manual').glob('*'))
    if len(manual)!=11:result['erros'].append('Esperados 11 arquivos manuais')
    for file in manual:
        if file.suffix=='.sql' and re.search(r'^\s*\\',file.read_text(),flags=re.M):
            result['erros'].append(f'Metacomando psql em SQL para DataGrip: {file.name}')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['erros']:raise SystemExit(1)

if __name__=='__main__':main()
