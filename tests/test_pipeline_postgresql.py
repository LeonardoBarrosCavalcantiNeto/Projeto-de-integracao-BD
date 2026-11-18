"""Teste SQL real: interseção inválido/duplicata, NULL, antecipação e >24h."""
import contextlib
import csv
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from integrar_anac import ORIGINAIS, ROOT, preparar, caminho_copy
from testar_integracao_isolada import executar


@unittest.skipUnless(shutil.which('postgres') and shutil.which('initdb'),'PostgreSQL local indisponível')
class PipelinePostgreSQL(unittest.TestCase):
    def test_contrato_e_reexecucao(self):
        with tempfile.TemporaryDirectory(prefix='anac_test_') as tmp:
            base=Path(tmp);inputs={}
            for year in [2019,2020]:
                directory=base/str(year);directory.mkdir();inputs[year]=directory
                a=['AZU','AZUL','0035','0','N','A320','180','SBGR','GUARULHOS',
                   f'01/01/{year} 10:00',f'01/01/{year} 09:45','SBRF','RECIFE',
                   f'01/01/{year} 12:00',f'03/01/{year} 13:00','REALIZADO','',f'{year}-01-01','','']
                b=a.copy();b[2]='0036';b[10]='';b[14]='';b[6]='2147483648'
                c=a.copy();c[9]=f'31/02/{year} 10:00';c[11]=' '
                d=a.copy();d[0]=' AZU '
                for month in range(1,13):
                    with (directory/f'VRA_{year}_{month:02d}.csv').open('w',encoding='utf-8-sig',newline='') as h:
                        writer=csv.writer(h,delimiter=';');writer.writerow(ORIGINAIS)
                        if month==1:writer.writerows([a,b,c,d])
                        if month==2:writer.writerow(c)
            with contextlib.redirect_stdout(io.StringIO()):preparar(inputs,base/'bundle')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/testar_integracao_isolada.py'),
                                   '--bundle',str(base/'bundle'),'--cluster',str(base/'postgres')],
                                  text=True,capture_output=True)
            if result.returncode:
                logs='\n'.join(f.read_text(encoding='utf-8')[-5000:] for f in (base/'bundle').glob('postgres*.log'))
                self.fail(result.stdout+result.stderr+logs)
            manual=subprocess.run([sys.executable,str(ROOT/'scripts/testar_integracao_isolada.py'),
                                   '--bundle',str(base/'bundle'),'--cluster',str(base/'postgres_manual'),'--manual'],
                                  text=True,capture_output=True)
            if manual.returncode:
                logs='\n'.join(f.read_text(encoding='utf-8')[-5000:] for f in (base/'bundle').glob('manual*.log'))
                self.fail(manual.stdout+manual.stderr+logs)
            exported=base/'result.csv'
            query=f'''COPY (SELECT ano_origem,count(*),count(atraso_partida_min),
            count(*) FILTER(WHERE diferenca_partida_min=-15 AND atraso_partida_min=0),
            count(*) FILTER(WHERE chegada_atipica_flag),
            count(*) FILTER(WHERE numero_voo='0035') FROM dw.fato_voo GROUP BY 1 ORDER BY 1)
            TO {caminho_copy(exported)} WITH (FORMAT CSV);'''
            executar(base/'postgres',query,base/'conferencia.log')
            with exported.open(encoding='utf-8', newline='') as h:rows=list(csv.reader(h))
            executar(base/'postgres_manual',query,base/'conferencia_manual.log')
            with exported.open(encoding='utf-8', newline='') as h:manual_rows=list(csv.reader(h))
            self.assertEqual(rows,manual_rows)
            self.assertEqual(rows,[['2019','3','2','2','2','2'],['2020','3','2','2','2','2']])

if __name__=='__main__':unittest.main()
