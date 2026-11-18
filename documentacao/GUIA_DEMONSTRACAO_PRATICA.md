# Guia de demonstração prática — VRA/ANAC

Use um **PostgreSQL já carregado** e ensaie em uma sessão com acesso de leitura aos schemas da entrega. As consultas ao vivo abaixo usam nomes explícitos de schema. O roteiro de instalação e carga está separado. [Reprodução](REPRODUCAO_MULTIPLATAFORMA.md) · [Modelo dimensional](MODELO_DIMENSIONAL_FINAL.md) · [Roteiro de apresentação](ROTEIRO_APRESENTACAO.md)

## Preparação

1. No DataGrip, abra a fonte PostgreSQL da avaliação, confira host, porta, banco e usuário e use **Test Connection**. Selecione `raw`, `raw_etl`, `staging_etl`, `staging_elt`, `dw_etl` e `dw_elt` no navegador de objetos. Se a lista estiver desatualizada, sincronize a introspecção. Abra uma única sessão para os comandos e a transação.
2. No terminal, defina os parâmetros de conexão do ambiente de avaliação conforme o guia, sem exibir segredos. A partir da raiz, abra `psql -X -v ON_ERROR_STOP=1`. Em `psql`, `\conninfo` mostra a conexão e `\i sql/comparacao/rastreabilidade.sql` roda o exemplo do repositório. No DataGrip, abra esse SQL e execute os SELECTs no console.
3. Antes da apresentação, abra as consultas escolhidas em abas ou separe as seleções. Confirme que o CSV de 2021 usado na amostra está acessível por nome ou deixe ao lado o manifesto e a evidência de identidade RAW. Evite expor caminhos pessoais e configurações.
4. Para a demonstração, inicie uma transação de leitura. Se houver erro ou timeout, execute `ROLLBACK` na mesma sessão e inicie outro bloco. Termine com `ROLLBACK`. Ajuste o limite durante o ensaio se uma agregação ultrapassar o tempo disponível.

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
```

**Contextos de resultado.** Os números de referência a seguir são da execução histórica com os CSVs reais. Nas fixtures recentes, a conferência adicional encontrou 3, 3 e 4 fatos por DW, em 2019–2021. Compare o resultado ao contexto da conexão. O guia usa exemplos extraídos dos SQLs atuais e consultas montadas com o DDL da entrega. A suíte PostgreSQL anterior testou a integração com fixtures. As consultas acrescentadas neste guia foram revistas estaticamente para o material. [Relatório de resultados](../relatorio/STATUS_FINAL_PROJETO.md) · [Teste com fixtures](INTEGRACAO_FINAL.md#validação-funcional-com-fixtures)

## Consultas para demonstrar e explicar

### Q0. Conexão e sessão

```sql
SELECT current_database() AS banco, current_user AS papel,
       inet_server_addr() AS endereco, inet_server_port() AS porta,
       current_setting('transaction_read_only') AS somente_leitura;
```

**Mostre.** A consulta lê informações da sessão. O banco deve ser o ambiente de avaliação e a última coluna deve indicar `on` depois de `BEGIN READ ONLY`. Em conexão local por socket, a função de endereço ou porta pode retornar nulo. **Se perguntarem.** “Confiro o destino antes de interpretar qualquer contagem.”

### Q1. Schemas e tabelas

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema IN ('raw', 'raw_etl', 'staging_etl', 'staging_elt', 'dw_etl', 'dw_elt')
  AND (table_name LIKE 'voos_%'
       OR table_name IN ('ocorrencias', 'vra_tratada', 'fato_voo')
       OR table_schema IN ('dw_etl', 'dw_elt'))
ORDER BY table_schema, table_name;
```

**Mostre.** O catálogo lista objetos visíveis ao papel atual. Abra um DW na interface e identifique suas sete dimensões e a fato. **Se perguntarem.** “Os DWs usam schemas distintos no mesmo banco. Os nomes iguais das tabelas representam a mesma estrutura em cada fluxo.” [DDL](../sql/database/10_criacao_dw.sql)

### Q2. Fatos por ano e por fluxo

```sql
SELECT 'ETL' AS fluxo, ano_origem, count(*) AS fatos
FROM dw_etl.fato_voo GROUP BY ano_origem
UNION ALL
SELECT 'ELT', ano_origem, count(*)
FROM dw_elt.fato_voo GROUP BY ano_origem
ORDER BY ano_origem, fluxo;
```

**Mostre.** `GROUP BY` conta etapas elegíveis por ano da fonte. `UNION ALL` empilha os resultados com seus rótulos. No recorte real validado, cada fluxo tem 982.926, 481.909 e 606.637 nas três linhas anuais, totalizando 2.071.472. **Se perguntarem.** “A igualdade dos totais é necessária, mas a Q13 mostra como conferimos o conteúdo. Para medir etapas, use um dos fluxos.” [Evidência integral](../resultados/validacoes/integracao_final/comparacao_integral.json)

### Q3. RAW e conciliação do tratamento

```sql
SELECT ano_origem, count(*) AS ocorrencias_raw
FROM raw.ocorrencias GROUP BY ano_origem ORDER BY ano_origem;

SELECT ano_origem, bruta, duplicatas_excedentes, rejeicoes, tratada,
       bruta = duplicatas_excedentes + rejeicoes + tratada AS conciliado
FROM staging_elt.resumo_qualidade ORDER BY ano_origem;
```

**Mostre.** A primeira consulta conta ocorrências no inventário de RAW. A segunda expõe a partição da população classificada pelo ELT. Na execução histórica, as RAW anuais têm 983.414, 483.545 e 632.148 ocorrências. **Se perguntarem.** “O inventário indexa as tabelas anuais brutas. A conciliação usa ocorrências exclusivas e a auditoria de anomalias fica fora da soma.” Para mostrar o inventário do ETL, troque `raw.ocorrencias` por `raw_etl.ocorrencias` na primeira consulta. [Qualidade anual](../resultados/validacoes/integracao_final/qualidade.csv)

### Q4. Excedentes e representantes

```sql
SELECT ano_origem, count(*) AS excedentes,
       count(DISTINCT (arquivo_preservado, linha_preservada)) AS grupos
FROM staging_elt.vra_duplicatas_excluidas
GROUP BY ano_origem ORDER BY ano_origem;

SELECT arquivo_origem, linha_origem, arquivo_preservado, linha_preservada,
       "Número Voo"
FROM staging_elt.vra_duplicatas_excluidas
WHERE ano_origem = 2019
ORDER BY id_raw LIMIT 5;
```

**Mostre.** A primeira consulta conta excedentes e representantes distintos. A segunda exibe a origem do excedente e a origem mantida. A evidência histórica registra 470/444 em 2019 e 124/124 em 2020, no formato excedentes/grupos. Em 2021 não houve excedentes e o agrupamento pode omitir esse ano. **Se perguntarem.** “A igualdade é dos 20 campos brutos. Uma representante ainda pode cair na regra de rejeição.” [Diagnósticos](../resultados/validacoes/integracao_final/diagnosticos_contrato_sql.csv)

### Q5. Rejeições e seus motivos

```sql
SELECT ano_origem, motivo, count(*) AS ocorrencias_com_o_motivo
FROM staging_elt.vra_rejeicoes r
CROSS JOIN LATERAL unnest(r.motivos_rejeicao) AS m(motivo)
GROUP BY ano_origem, motivo
ORDER BY ano_origem, ocorrencias_com_o_motivo DESC, motivo;
```

**Mostre.** `unnest` gera uma linha por motivo no array. Uma ocorrência pode contribuir para dois motivos, como partida e chegada previstas ausentes. O total de rejeitados vem da Q3. **Se perguntarem.** “A soma de motivos pode superar o número de rejeições, pois preservamos as causas de cada ocorrência.” [Implementação da transformação](../sql/transformacoes/elt_2019_2020.sql)

### Q6. Anomalias

```sql
SELECT ano_origem, campo, motivo, count(*) AS apontamentos
FROM staging_elt.vra_anomalias
GROUP BY ano_origem, campo, motivo
ORDER BY ano_origem, apontamentos DESC, campo;
```

**Mostre.** A consulta agrega notificações por campo e motivo. Uma consulta sem linhas para certo ano é compatível com ausência de apontamentos no recorte. Uma anomalia de opcional inválido não é causa de rejeição por si só. **Se perguntarem.** “A auditoria guarda campo e valor. Um registro pode ter mais de um apontamento, e o total conta apontamentos.” [Diagnóstico de qualidade](../relatorio/QUALIDADE_2019_2021.md)

### Q7. Juntar a fato às dimensões

```sql
SELECT f.ano_origem, f.id_raw, c.companhia_icao,
       o.aeroporto_icao AS origem, d.aeroporto_icao AS destino,
       t.data AS data_prevista, f.atraso_partida_min
FROM dw_etl.fato_voo f
JOIN dw_etl.dim_companhia_aerea c USING (id_companhia)
JOIN dw_etl.dim_aeroporto o ON o.id_aeroporto = f.id_aeroporto_origem
JOIN dw_etl.dim_aeroporto d ON d.id_aeroporto = f.id_aeroporto_destino
JOIN dw_etl.dim_tempo t ON t.id_tempo = f.id_tempo_partida
WHERE f.ano_origem = 2021
ORDER BY f.id_raw LIMIT 5;
```

**Mostre.** Uma mesma dimensão de aeroportos aparece duas vezes com aliases. A junção traduz os IDs locais em códigos compreensíveis. Selecione um ID para a pergunta seguinte. **Se perguntarem.** “A consulta retorna uma linha por ocorrência porque cada FK aponta para um único membro da dimensão.” [Modelo e chaves](MODELO_DIMENSIONAL_FINAL.md)

### Q8. Voltar da fato até o CSV

No terminal, a partir da raiz e com a mesma configuração de conexão do ensaio:

```bash
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/rastreabilidade.sql
```

Para investigar o ID selecionado na Q7, use o trecho abaixo no DataGrip ou em `psql`. Troque `1` pelo ID exibido na Q7. Se o ID escolhido estiver no ELT, use o segundo SELECT do arquivo versionado e aplique o mesmo filtro.

```sql
SELECT f.ano_origem, f.id_raw, r.arquivo_origem, r.linha_origem,
       r."Número Voo", r."Partida Prevista", r."Codeshare",
       s.numero_voo AS numero_tratado, s.partida_prevista AS prevista_tratada
FROM dw_etl.fato_voo f
JOIN staging_etl.vra_tratada s USING (ano_origem, id_raw)
JOIN raw_etl.ocorrencias o USING (ano_origem, id_raw)
JOIN raw_etl.voos_2021 r USING (ano_origem, id_raw)
WHERE f.ano_origem = 2021 AND f.id_raw = 1;
```

**Mostre.** Leia da esquerda para a direita as junções de fato, tratada, ocorrência e RAW. Localize `arquivo_origem` e o ordinal `linha_origem` no CSV original, contando o cabeçalho como 1. Um leitor CSV deve respeitar campos com quebra de linha. **Se perguntarem.** “A entrada foi preservada em texto. Posso comparar o horário antes e depois da conversão para timestamp. Este exemplo prova o percurso escolhido, e o comparador verifica a população completa.” [SQL de rastreabilidade](../sql/comparacao/rastreabilidade.sql)

Para abrir a ocorrência no terminal, substitua `NOME_DO_CSV` e `ORDINAL_LOGICO` pelos valores retornados. O comando lê o arquivo local até o registro selecionado.

```bash
python -c 'import csv, sys; from itertools import islice; from pathlib import Path; arquivo = Path("dados/brutos/2021") / sys.argv[1]; ordinal = int(sys.argv[2]); f = arquivo.open(encoding="utf-8-sig", newline=""); print(next(islice(csv.DictReader(f, delimiter=";"), ordinal - 2, None), "Registro ausente")); f.close()' NOME_DO_CSV ORDINAL_LOGICO
```

Abra o arquivo em modo de leitura. O cabeçalho é consumido por `DictReader`, então o primeiro registro de dados tem deslocamento zero e ordinal 2. Se o arquivo estiver em outra pasta, ajuste o caminho para a cópia conferida pelo manifesto.

### Q9. Nulos e qualidade das medidas

```sql
SELECT ano_origem, count(*) AS fatos,
       count(*) FILTER (WHERE partida_real IS NULL) AS sem_partida_real,
       count(*) FILTER (WHERE chegada_real IS NULL) AS sem_chegada_real,
       count(atraso_partida_min) AS atraso_partida_calculavel,
       count(*) FILTER (WHERE partida_atipica_flag) AS partidas_atipicas
FROM dw_elt.fato_voo GROUP BY ano_origem ORDER BY ano_origem;
```

**Mostre.** `count(*)` conta todas as linhas selecionadas, enquanto `count(coluna)` exclui os nulos. Compare com o relatório de qualidade. **Se perguntarem.** “Horário real ausente não vira zero nem determina cancelamento. Atípicos são marcados e continuam auditáveis.” [Qualidade real](../relatorio/QUALIDADE_2019_2021.md)

### Q10. Atraso médio de partida por companhia

```sql
SELECT c.companhia_icao, c.companhia_nome, count(*) AS etapas,
       count(f.atraso_partida_min) AS calculaveis,
       round(avg(f.atraso_partida_min), 2) AS atraso_medio_min
FROM dw_elt.fato_voo f
JOIN dw_elt.dim_companhia_aerea c USING (id_companhia)
WHERE f.ano_origem = 2021
GROUP BY c.companhia_icao, c.companhia_nome
ORDER BY etapas DESC, c.companhia_icao LIMIT 10;
```

**Mostre.** É a análise por companhia de `05_analises.sql` adaptada ao DW ELT e a um ano. `AVG` ignora nulos, inclui zeros de antecipações e, nesta consulta, mantém atrasos atípicos. A ordenação é por volume de etapas, não por média. **Se perguntarem.** “É a média do atraso não negativo por etapa calculável. Para antecipação, a medida correta é a diferença com sinal.” A referência histórica identifica AZU como a maior companhia por total de ocorrências em cada ano. [Consulta base](../sql/integracao/05_analises.sql) · [Resultados](../relatorio/STATUS_FINAL_PROJETO.md)

### Q11. Cancelamentos por companhia

```sql
SELECT c.companhia_icao, count(*) AS etapas_elegiveis,
       count(*) FILTER (WHERE s.situacao_voo = 'CANCELADO') AS canceladas,
       count(*) FILTER (WHERE s.situacao_voo IS NULL
                           OR s.situacao_voo = 'NÃO INFORMADO') AS sem_situacao_conhecida,
       round(100.0 * count(*) FILTER (WHERE s.situacao_voo = 'CANCELADO')
             / nullif(count(*), 0), 2) AS pct_canceladas_sobre_elegiveis
FROM dw_etl.fato_voo f
JOIN dw_etl.dim_companhia_aerea c USING (id_companhia)
LEFT JOIN dw_etl.dim_situacao_voo s USING (id_situacao)
WHERE f.ano_origem = 2020
GROUP BY c.companhia_icao
ORDER BY canceladas DESC, c.companhia_icao LIMIT 10;
```

**Mostre.** O `LEFT JOIN` mantém etapas sem situação relacionada. A taxa usa todas as etapas elegíveis da companhia naquele ano como denominador. A categoria ausente ou não informada é exibida à parte. **Se perguntarem.** “Esta é a nossa taxa no recorte elegível, com esse denominador. Uma taxa sobre situações conhecidas ou sobre outro universo exige outra definição.” Não antecipe valores por companhia sem executar a consulta.

### Q12. Integridade referencial

```sql
SELECT n.nspname AS fluxo, count(*) AS fks,
       count(*) FILTER (WHERE c.convalidated) AS fks_validadas
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname IN ('dw_etl', 'dw_elt') AND t.relname = 'fato_voo'
  AND c.contype = 'f'
GROUP BY n.nspname ORDER BY n.nspname;
```

**Mostre.** O catálogo identifica FKs da fato e seu estado de validação. Na arquitetura verificada, são dez válidas por fato. **Se perguntarem.** “São nove relações dimensionais, contando os papéis repetidos, mais uma FK composta para a tratada do mesmo fluxo. Isso comprova a integridade referencial, enquanto a validação integral também compara os valores.” [Validação de dimensões e FKs](../sql/comparacao/validar_final.sql)

### Q13. Comparação ETL × ELT

A prova integral está registrada no JSON de evidência. Para mostrar o mecanismo ao vivo em tempo controlado, compare um **intervalo de dez IDs de 2021** na staging tratada. Esse intervalo pode conter menos de dez ocorrências elegíveis. Um intervalo totalmente vazio também pode dar zero, por isso a consulta mostra quantas chaves foram cotejadas.

```sql
WITH etl AS (
    SELECT id_raw, to_jsonb(t) AS conteudo
    FROM staging_etl.vra_tratada t
    WHERE ano_origem = 2021 AND id_raw BETWEEN 1 AND 10
), elt AS (
    SELECT id_raw, to_jsonb(t) - 'ocorrencia_num' AS conteudo
    FROM staging_elt.vra_tratada t
    WHERE ano_origem = 2021 AND id_raw BETWEEN 1 AND 10
)
SELECT count(*) AS chaves_cotejadas,
       count(*) FILTER (WHERE etl.conteudo IS DISTINCT FROM elt.conteudo)
           AS divergencias_na_faixa
FROM etl FULL JOIN elt USING (id_raw);
```

**Mostre.** `FULL JOIN` mantém chaves ausentes de qualquer lado. `IS DISTINCT FROM` trata nulos de forma explícita, e a coluna técnica de classificação SQL é excluída como no comparador. **Se perguntarem.** “Isto demonstra o mecanismo na tratada. O procedimento completo também verifica RAW, rejeições, duplicatas, dimensões, fatos, anomalias e rastreabilidade. O resultado real registrado foi zero divergências nos três anos.” [Resultados da comparação](../resultados/validacoes/integracao_final/comparacao_integral.json)

A execução integral fica para o ensaio em um banco de avaliação já carregado, com autorização de criação de objetos e fora da transação de leitura do palco. Na raiz, o comando oficial abaixo **cria ou atualiza o schema, views e funções de comparação** antes de executar as validações. O resultado histórico levou mais de nove minutos, então reserve o tempo de apresentação para a amostra e a evidência.

```bash
psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/validar_final.sql
```

Em um banco em que o comparador já esteja instalado, `SELECT comparacao.validar_dimensoes();` e `SELECT comparacao.validar_ano(2021);` chamam as funções existentes. A validação de ano varre a população do recorte e também deve ser ensaiada antes de incluí-la no roteiro. [SQL integral](../sql/comparacao/validar_final.sql)

### Q14. Movimentos por aeroporto

```sql
WITH movimentos AS (
    SELECT id_aeroporto_origem AS id_aeroporto
    FROM dw_elt.fato_voo WHERE ano_origem = 2021
    UNION ALL
    SELECT id_aeroporto_destino
    FROM dw_elt.fato_voo WHERE ano_origem = 2021
)
SELECT a.aeroporto_icao, a.descricao_aeroporto, count(*) AS movimentos
FROM movimentos m JOIN dw_elt.dim_aeroporto a USING (id_aeroporto)
GROUP BY a.aeroporto_icao, a.descricao_aeroporto
ORDER BY movimentos DESC, a.aeroporto_icao LIMIT 10;
```

**Mostre.** Adaptação da consulta de movimentos existente. Cada etapa elegível contribui uma vez como origem e uma vez como destino. Os dois papéis são preservados por `UNION ALL`. **Se perguntarem.** “A medida é presença como origem ou destino no recorte. Para obter decolagens efetivas, precisaríamos definir e aplicar critérios de realização.” [Consulta base](../sql/integracao/05_analises.sql)

### Q15. Distribuição por mês previsto de partida

```sql
SELECT f.ano_origem, t.ano AS ano_operacional, t.mes, count(*) AS etapas
FROM dw_elt.fato_voo f
JOIN dw_elt.dim_tempo t ON t.id_tempo = f.id_tempo_partida
GROUP BY f.ano_origem, t.ano, t.mes
ORDER BY f.ano_origem, t.ano, t.mes;
```

**Mostre.** A dimensão tempo fornece o mês de partida prevista. O ano do conjunto CSV permanece em outra coluna, de modo que uma data operacional de outro ano fique visível. **Se perguntarem.** “O mês do arquivo e o mês esperado da partida são recortes diferentes. Esta análise escolhe a data prevista.” [Consulta base](../sql/integracao/05_analises.sql)

## Sequência de 5–8 minutos

| Tempo | Mostrar | O que dizer |
|---|---|---|
| 0:00–0:45 | CSV e conexão Q0–Q1 | “Este cabeçalho traz valores originais. Os dois fluxos guardam RAW e staging separadas.” |
| 0:45–1:40 | Q3 e o trecho de deduplicação no código | “Extraímos a origem antes de tratar. O contrato separa brutos em excedentes, rejeitados e tratados.” |
| 1:40–2:25 | Q7 e Q8 | “A fato liga os atributos da estrela e o identificador da origem. Vamos voltar ao campo bruto.” |
| 2:25–3:25 | Q2 e Q10 | “Os totais são por fluxo. Esta média tem como denominador as etapas com atraso calculável.” |
| 3:25–5:00 | Q13 e o JSON histórico | “A amostra é uma demonstração da comparação. A prova completa incluiu as duas estrelas e as auditorias.” |
| Até 8:00 | Q4 ou Q5, Q11 e Q14 ou Q15 | Responda sobre qualidade, denominadores e recortes. Escolha uma análise adicional em vez de executar todas as consultas. |

Se o banco ficar indisponível, mostre o diagrama, abra a consulta Q8, indique a chave usada nas junções e mostre a evidência de identidade RAW. Passe da qualidade anual ao JSON de comparação. Identifique os arquivos como registro da execução anterior. Para comprovar a execução sintética recente, abra a seção de testes do guia final. [Identidade RAW](../resultados/validacoes/integracao_final/identidade_raw.json) · [Contagens e qualidade](../resultados/validacoes/integracao_final/qualidade.csv) · [Comparação integral](../resultados/validacoes/integracao_final/comparacao_integral.json) · [Testes](INTEGRACAO_FINAL.md#validação-funcional-com-fixtures)

## Checklist por papel

- **2019 ETL.** [ ] Explicar a leitura e `duplicated()`. [ ] Diferenciar o ETL individual do integrado. [ ] Conferir o arquivo e o ordinal que serão mostrados.
- **2019 ELT.** [ ] Mostrar a RAW de um ano e a janela do template. [ ] Explicar ordem da deduplicação e carga.
- **2020 ETL.** [ ] Explicar uma rejeição e uma anomalia. [ ] Conferir o denominador de atrasos e cancelamentos.
- **2020 ELT.** [ ] Nomear as sete dimensões. [ ] Explicar dois papéis de aeroporto e tempo. [ ] Revisar Q7 e Q12.
- **2021 ETL.** [ ] Explicar `Codeshare` e as duas formas de referência. [ ] Ter prontos o JSON e a validação sintética para distinguir as provas.
- **2021 ELT.** [ ] Ensaiar Q0, Q2, Q7, Q8 e Q13 na ordem. [ ] Conhecer o plano alternativo e fechar com os limites da reprodução.

Antes de apresentar, cada dupla deve explicar o percurso do outro integrante e responder quais evidências aparecerão na sua fala.
