"""Seis fluxos reais em fixture: variação 2021, duplicatas, rejeição e origem multilinha."""
import contextlib
import csv
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from integrar_anac import ORIGINAIS,ROOT,caminho_copy
from testar_integracao_isolada import executar
from integracao_final import prepare, isolated
from auditar_contrato_final import audit as auditar_contrato
from evidencias_final import evidence


class Final(unittest.TestCase):
    def preparar_fixture(self, base):
        referencias_2021 = (
            ('01/01/2020 00:00:00', 'REFERENCIA_FORA_DE_2021', '2020-01-01'),
            ('2020-01-01', 'REFERENCIA_FORA_DE_2021', '2020-01-01'),
            ('01/01/2020', 'VALOR_OPCIONAL_INVALIDO', ''),
        )
        inputs={}
        for y in [2019,2020,2021]:
            folder=base/str(y);folder.mkdir();inputs[y]=folder
            a=['AZU',f'AZUL\nLINHAS {y}','0035','0','N','A320','180','SBGR','GUARULHOS',
               f'01/01/{y} 10:00',f'01/01/{y} 09:45','SBRF','RECIFE',
               f'01/01/{y} 12:00',f'03/01/{y} 13:00','REALIZADO','',f'{y}-01-01','','']
            b=a.copy();b[0]='ZZZ';b[1]='';b[7]='ZZZZ';b[8]='';b[3]='\\N';b[16]='texto, com \"aspas\"';b[2]='0036';b[10]='';b[14]='';b[6]='2147483648'
            if y!=2021:b[17]=f'01/01/{y} 00:00:00'
            e=a.copy();e[0]=' AZU '
            c=a.copy();c[9]=f'31/02/{y} 10:00';c[11]=' '
            for m in range(1,13):
                extra=y==2021 and m==1
                with (folder/f'VRA_{y}_{m:02}.csv').open('w',encoding='utf-8-sig',newline='') as h:
                    w=csv.writer(h,delimiter=';');w.writerow(ORIGINAIS+(['Codeshare'] if extra else []))
                    for row in ([a,b,c,c,e] if m==1 else [a] if m==2 else []):
                        row=row.copy()
                        if extra:row[17]=f'01/01/{y} 00:00:00'
                        w.writerow(row+([''] if extra else []))
                    if y == 2021 and m == 3:
                        for original, _, _ in referencias_2021:
                            row = a.copy()
                            row[2] = '0099'
                            row[17] = original
                            w.writerow(row)
        return inputs, referencias_2021

    def test_preparacao_sem_postgresql(self):
        with tempfile.TemporaryDirectory(prefix='anac_preparacao_') as tmp:
            base=Path(tmp)
            inputs, referencias_2021 = self.preparar_fixture(base)
            with contextlib.redirect_stdout(io.StringIO()):
                prepare(inputs,base/'out')
            for year in (2019,2020,2021):
                with self.subTest(ano=year):
                    folder=base/f'out/etl/{year}'
                    summary=json.loads((folder/'resumo.json').read_text(encoding='utf-8'))
                    self.assertEqual(summary['bruta'],9 if year==2021 else 6)
                    # Janeiro/2021 usa referência BR; fevereiro usa ISO.
                    # Essas duas ocorrências não são duplicatas brutas exatas.
                    self.assertEqual(summary['duplicatas_excedentes'],1 if year==2021 else 2)
                    self.assertEqual(summary['rejeicoes'],1)
                    self.assertEqual(summary['tratada'],7 if year==2021 else 3)
                    self.assertEqual(summary['intersecao_excedentes_invalidos'],1)
                    with (folder/'vra_tratada.csv').open(encoding='utf-8',newline='') as stream:
                        treated=list(csv.DictReader(stream))
                    opcional=next(row for row in treated if row['numero_voo']=='0036')
                    self.assertEqual(opcional['numero_assentos'],r'\N')
                    self.assertEqual(opcional['atraso_partida_min'],r'\N')
                    with (folder/'vra_anomalias.csv').open(encoding='utf-8',newline='') as stream:
                        reader=csv.DictReader(stream)
                        self.assertEqual(reader.fieldnames,
                            ['arquivo_origem','linha_origem','ano_origem','campo','valor_original','motivo'])
                        anomalies=list(reader)
                    if year==2021:
                        actual=[(row['linha_origem'],row['campo'],row['valor_original'],row['motivo'])
                                for row in anomalies if row['arquivo_origem']=='VRA_2021_03.csv']
                        expected=[(str(line),'Referência',original,motivo)
                                  for line,(original,motivo,_) in enumerate(referencias_2021,2)]
                        self.assertCountEqual(actual,expected)

    @unittest.skipUnless(shutil.which('postgres') and shutil.which('initdb'),
                         'PostgreSQL local indisponível; preparação validada no teste sem PostgreSQL')
    def test_seis_fluxos_independentes(self):
        with tempfile.TemporaryDirectory(prefix='anac_final_') as tmp:
            base=Path(tmp)
            inputs, referencias_2021 = self.preparar_fixture(base)
            with contextlib.redirect_stdout(io.StringIO()):
                prepare(inputs,base/'out')
                try:
                    isolated(base/'out',base/'cluster')
                    auditar_contrato(base/'out',base/'cluster')
                    # Windows server-side COPY adds CRLF between rows.
                    if sys.platform != 'win32':
                        evidence(base/'out',base/'cluster')
                except Exception:
                    for log in (base/'out').glob('*.log'):
                        print(log.name,log.read_text(encoding='utf-8')[-18000:],file=sys.stderr)
                    raise
            for year in [2019,2020,2021]:
                summary=json.loads((base/f'out/etl/{year}/resumo.json').read_text(encoding='utf-8'))
                self.assertEqual(summary['excedentes_apos_padronizacao'],1)
                self.assertEqual(summary['intersecao_excedentes_invalidos'],1)
            # A sequência de março deve ter três fatos e exatamente uma anomalia
            # de referência por ocorrência, com o texto bruto e a mesma origem.
            expected = [
                ['2021', 'VRA_2021_03.csv', str(line), 'Referência', original, motivo, data]
                for line, (original, motivo, data) in enumerate(referencias_2021, 2)
            ]
            for flow in ('etl', 'elt'):
                with self.subTest(referencia=flow):
                    exported = base / f'referencias_{flow}.csv'
                    query = f"""
                        SELECT f.ano_origem, f.arquivo_origem, f.linha_origem,
                               a.campo, a.valor_original, a.motivo, f.referencia
                        FROM dw_{flow}.fato_voo f
                        FULL JOIN staging_{flow}.vra_anomalias a
                        USING (ano_origem, arquivo_origem, linha_origem)
                        WHERE coalesce(f.arquivo_origem, a.arquivo_origem) = 'VRA_2021_03.csv'
                        ORDER BY coalesce(f.linha_origem, a.linha_origem)
                    """
                    executar(base/'cluster', f'COPY ({query}) TO {caminho_copy(exported)} WITH (FORMAT CSV);',
                             base / f'referencias_{flow}.log')
                    with exported.open(encoding='utf-8', newline='') as stream:
                        self.assertEqual(list(csv.reader(stream)), expected)
                    executar(base/'cluster', f"""
                        DO $$ BEGIN
                            IF EXISTS (SELECT FROM staging_{flow}.vra_rejeicoes
                                       WHERE arquivo_origem = 'VRA_2021_03.csv')
                               OR EXISTS (SELECT FROM staging_{flow}.vra_duplicatas_excluidas
                                          WHERE arquivo_origem = 'VRA_2021_03.csv')
                            THEN RAISE EXCEPTION 'Referência opcional gerou rejeição ou duplicata';
                            END IF;
                        END $$;
                    """, base / f'classificacao_referencias_{flow}.log')
            standalone=base/'cluster_etl_independente'
            subprocess.run(['initdb','-D',str(standalone),'-A','trust','--no-locale','-E','UTF8'],check=True,capture_output=True)
            sql=re.sub(r'^\\copy (.*)$',r'COPY \1;',(base/'out/02_etl.psql').read_text(encoding='utf-8'),flags=re.M)
            executar(standalone,sql,base/'etl_independente.log')
            executar(standalone,"DO $$ BEGIN IF EXISTS(SELECT FROM pg_namespace WHERE nspname IN('raw','staging_elt','dw_elt')) OR NOT EXISTS(SELECT FROM dw_etl.fato_voo) THEN RAISE EXCEPTION 'ETL depende do ELT'; END IF; END $$;",base/'independencia.log')
            manual=base/'cluster_manual'
            subprocess.run(['initdb','-D',str(manual),'-A','trust','--no-locale','-E','UTF8'],check=True,capture_output=True)
            for f in sorted((base/'out/elt/manual').iterdir()):
                sql=re.sub(r'^\\copy (.*)$',r'COPY \1;',f.read_text(encoding='utf-8'),flags=re.M)
                executar(manual,sql,base/(f.stem+'.log'))
            sql=re.sub(r'^\\copy (.*)$',r'COPY \1;',(base/'out/02_etl.psql').read_text(encoding='utf-8'),flags=re.M)
            executar(manual,sql,base/'etl_manual.log')
            executar(manual,(ROOT/'sql/comparacao/validar_final.sql').read_text(encoding='utf-8'),base/'comparacao_manual.log')
            executar(manual,(ROOT/'sql/comparacao/validar_restauracao.sql').read_text(encoding='utf-8'),base/'restauracao.log')
            with self.assertRaisesRegex(RuntimeError,r'etapa vra_tratada.*primeiro id_raw=1'):
                executar(manual,"BEGIN; UPDATE staging_etl.vra_tratada SET numero_voo='9999' "
                         "WHERE ano_origem=2019 AND id_raw=1; SELECT comparacao.validar_ano(2019); ROLLBACK;",
                         base/'divergencia_esperada.log')
            self.assertIn('v.atraso_partida_min',(base/'out/02_etl.psql').read_text(encoding='utf-8'))
            for year in [2019,2020,2021]:
                self.assertIn(f'COMPARACAO_EXATA_OK {year}',(base/f'out/validacao_{year}.log').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
