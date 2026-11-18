# Execução final dos três anos

O fluxo ETL lê os originais e aplica funções Pandas do integrante de 2021 (`scripts/etl_vra_anac_2021.py`, branch `origin/feat/etl-2021`, commit `65cf857`). O mesmo contrato é aplicado aos três anos por essa interface reutilizável. As versões individuais de 2019 e 2020 permanecem preservadas. O fluxo ELT reutiliza `integrar_anac.py`, o template parametrizado `sql/transformacoes/elt_2019_2020.sql` para 2019 e 2020 e `sql/transformacoes/elt_2021.sql` para 2021. Não há consumo de linhas tratadas do ELT pelo ETL. O bundle ETL define seus próprios tipos e pode ser instalado sozinho, sem tabelas ELT. As funções auxiliares de ingestão são compartilhadas: o CSV bruto de ingestão alimenta `raw` no ELT e `raw_etl` no ETL, sem tratamento de negócio. As linhas tratadas do ETL vêm exclusivamente dos CSVs Pandas.

Cada schema `dw_etl` e `dw_elt` possui sete dimensões e uma fato. São schemas separados no mesmo banco PostgreSQL. A granularidade é uma ocorrência válida de etapa de voo após deduplicação exata dos 20 campos contratuais, com chave `(ano_origem,id_raw)`. As dimensões usam chaves substitutas; a comparação as resolve para atributos naturais.

## Reprodução pelo terminal

Use o [guia para Windows, macOS e Linux](REPRODUCAO_MULTIPLATAFORMA.md) para baixar e verificar os 36 CSVs, carregar os dois DWs via psql, conectar clientes opcionais e transportar o banco por backup lógico.

## Modo single-user do ambiente Fedora original

Na raiz Git, com Python 3.11+ e PostgreSQL 18 (binários `postgres` e `initdb` no PATH):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/integracao_final.py prepare \
  --dados-2019 '/caminho/Base de dados 2019' \
  --dados-2020 '/caminho/Base de dados 2020' \
  --dados-2021 '/caminho/Base de dados 2021'
.venv/bin/python scripts/integracao_final.py isolated
```

`prepare` não conecta a nenhum banco. Produz CSVs tratados, duplicatas com representante, rejeições com motivos, anomalias, inventários e resumos em `.local/final/etl/ANO/`. Faz a extração original do ELT em `.local/final/elt/`. Não altera as entradas. Arquivos grandes e cluster ficam ignorados pelo Git. Reservar espaço para entradas, arquivos intermediários e PostgreSQL; a execução completa pode levar vários minutos.

`isolated` exige diretório de cluster inexistente. Cria PostgreSQL isolado e executa os dois bundles em modo single-user, sem rede. Aplica constraints, repete cargas dimensionais e compara o conteúdo por ocorrência em lotes. Nunca apontar essa opção para um cluster de outro projeto. Para repetir uma instalação completa, use novos `--output` e `--cluster`; o programa recusa substituir cluster existente.

```bash
.venv/bin/python scripts/integracao_final.py etl --ano 2021 \
  --input-dir '/caminho/Base de dados 2021' --output .local/etl_demonstracao_2021
.venv/bin/python scripts/integracao_final.py validate
```

O comando `etl` demonstra apenas Pandas e exportações; a carga dimensional faz parte dos bundles completos. `validate` consulta o cluster já carregado e repete cargas dimensionais idempotentes; não repete a importação RAW. Os testes usam amostras sintéticas; os resultados reais são documentados separadamente.

## Validação funcional com fixtures

Na revisão final da base de código do commit `c9618aa`, os 11 testes passaram no Fedora com Python 3.13.15 e PostgreSQL 18.6. Os dois testes PostgreSQL usaram cinco clusters descartáveis em diretórios temporários, em modo single-user, sem portas nem conexões ao serviço existente.

O teste dos seis fluxos comparou RAW, tratados, duplicatas, rejeições, anomalias e fatos por ocorrência, além de verificar sete dimensões e dez chaves estrangeiras válidas por fato. Também exercitou a instalação independente do ETL, a execução manual e a detecção de uma divergência introduzida de propósito. Uma conferência adicional contou 3, 3 e 4 fatos em cada DW para 2019, 2020 e 2021. Os testes usam dados sintéticos. As contagens dos CSVs reais pertencem à [execução histórica validada](../relatorio/STATUS_FINAL_PROJETO.md).

## Conectar ao cluster isolado original

O modo single-user mantém banco persistente, mas não disponibiliza conexão DataGrip enquanto estiver desligado. Com as validações terminadas e fora de um sandbox que bloqueie sockets, o proprietário pode iniciar o cluster:

```bash
pg_ctl -D "$PWD/.local/final/postgres" \
  -l "$PWD/.local/final/servidor.log" \
  -o '-h 127.0.0.1 -p 55439 -k /tmp' start
```

Em qualquer cliente PostgreSQL, use host `127.0.0.1`, porta `55439`, banco `postgres`, papel proprietário criado por `initdb`. O cluster isolado usa autenticação local `trust`, acessível apenas em loopback quando iniciado com o comando acima. Para uso compartilhado, configurar senha e SCRAM antes de expor o serviço. Não alterar `pg_hba.conf` do servidor nativo para executar esse cluster.

Para voltar a `validate`, desligue o serviço com `pg_ctl -D "$PWD/.local/final/postgres" stop -m fast`. O PostgreSQL impede execução single-user simultânea a um servidor ativo.

## Demonstração manual

Em banco novo, sem schemas `raw_etl`, `raw`, `staging_elt`, `dw_elt`, `staging_etl` ou `dw_etl`:

1. Execute `prepare` no terminal: Pandas continua obrigatório para o ETL.
2. Use as etapas em `.local/final/elt/manual/`, em ordem lexicográfica: `01_raw.sql`, `02_importar_raw.psql`, `03_transformar_2019.sql`, `04_transformar_2020.sql`, `04b_transformar_2021.sql`, `05_consolidar_staging.sql`, `06_criar_dw.sql`, `07_dimensoes.sql`, `08_carga_dw.sql`, `09_validar_contrato.sql`, `10_analises.sql`, `11_diagnosticos.sql`. A etapa `.psql` usa `psql -X -v ON_ERROR_STOP=1 -f ARQUIVO`; SQL puro pode ser executado com psql ou no cliente gráfico de sua escolha. As etapas de carga e validação usam transações. As duas consultas finais são somente leitura.
3. No terminal, execute `psql -X -v ON_ERROR_STOP=1 -f .local/final/02_etl.psql` na mesma conexão. Cria RAW próprio, staging Pandas, dimensões e fato ETL. Também pode ser executado sozinho em banco vazio após `prepare`.
4. Execute `psql -X -v ON_ERROR_STOP=1 -f sql/comparacao/validar_final.sql`. Qualquer divergência lança exceção; sucesso retorna `COMPARACAO_EXATA_OK`.
5. Consulte as análises, substituindo `dw.` por `dw_etl.` ou `dw_elt.` e `staging.` por `staging_elt.` em `sql/integracao/05_analises.sql`.

Alternativa automatizada em banco novo: execute `01_elt.psql` e `02_etl.psql` por `psql`, nessa ordem. Ambos contêm `BEGIN/COMMIT`. Não são scripts de substituição de banco existente; `CREATE SCHEMA` recusa instalação sobre dados anteriores. O antigo `integrar_anac.py apply` continua sendo ferramenta de migração da arquitetura anterior, não é o comando da arquitetura final.

Para conferir o roteiro e os arquivos gerados antes de conectar ao banco, use `python scripts/validar_guia.py --bundle .local/final`. Informe o mesmo diretório passado a `prepare --output`, se tiver usado outro. O validador confere a ordem manual, os metacomandos e os hashes disponíveis no manifesto. Os hashes manuais do manifesto canônico descrevem a versão anterior ao remapeamento para os schemas finais.

Se uma etapa SQL falhar dentro de uma transação, execute `ROLLBACK` na mesma sessão antes de corrigir o erro. Em um cliente gráfico, execute os arquivos SQL puros completos e use o terminal para a etapa de importação `.psql`. Se o CSV informado em `\\copy` estiver ausente após mover o bundle, gere-o novamente no local de execução.

## Rastreabilidade e contrato

`linha_origem` é o ordinal lógico CSV começando em 2, incluindo cabeçalho como registro 1. Não é linha física quando campos contêm quebras. `id_raw` é atribuído na ingestão, arquivos ordenados por nome e registros por posição, reiniciado por ano. Nunca é reconstruído a partir de IDs históricos.

A fato referencia a tabela tratada por FK `(ano_origem,id_raw)`; esta referencia `raw_etl.ocorrencias` no ETL e `raw.ocorrencias` no ELT, que identificam arquivo e ordinal. Rejeições e duplicatas possuem as mesmas chaves de origem. A duplicata registra arquivo e ordinal preservados. Para localizar a origem:

```sql
SELECT f.ano_origem,f.id_raw,r.arquivo_origem,r.linha_origem
FROM dw_etl.fato_voo f JOIN raw_etl.ocorrencias r USING(ano_origem,id_raw)
ORDER BY f.ano_origem,f.id_raw LIMIT 10;
```

O manifesto registra SHA-256 das fontes e contagens de registros multilinha. Em 2021, `Codeshare` é preservado no RAW e nas auditorias; sua ausência nos outros meses é representada por vazio na estrutura unificada. O manifesto distingue os layouts originais. A deduplicação permanece sobre os 20 campos contratuais, sem normalizar antes de comparar.

O contrato não confirma fusos oficiais nem impõe limiar de pontualidade. Preservam-se timestamps locais sem conversão de fuso. As consultas usam atraso positivo como critério de apresentação, com denominador de horários calculáveis e exclusão de NULL da média. Antecipações são diferenças negativas e atraso zero; horário real desconhecido mantém diferença e atraso NULL. Diferenças absolutas maiores que 1440 minutos são sinalizadas, não excluídas.

## Descrições dimensionais entre anos

A integração de 2021 acrescenta renomeações e variantes textuais para códigos existentes. O complemento `02_resolver_descricoes_final.sql` aplica um snapshot descritivo do tipo 1: a última descrição não nula observada por `(ano_origem,arquivo_origem,linha_origem,papel)`, em ordem decrescente, após as duas correções aeroportuárias já documentadas na implementação canônica. Essa é uma escolha de representação do cadastro para a apresentação; não afirma que a descrição escolhida é um cadastro oficial atualizado. A entidade continua identificada pelo código ICAO.

`staging_etl.variantes_dimensoes` e `staging_elt.variantes_dimensoes` preservam os conjuntos conflitantes. `snapshot_descricoes` registra a descrição escolhida e a ocorrência que a forneceu. RAW e tratados mantêm todas as descrições históricas. Assim, mudanças como TWO TÁXI AÉREO → AZUL CONECTA não criam outra companhia com o mesmo código. O modelo não implementa SCD tipo 2 nem permite analisar as renomeações a partir da descrição corrente da dimensão; use as descrições na staging para essa análise histórica.

## Evidências e consultas

Depois da validação, execute `.venv/bin/python scripts/evidencias_final.py` no terminal. A ferramenta reexporta RAW com a mesma ordenação e representação da ingestão e compara SHA-256 antes de remover apenas essa exportação temporária. Exporta em `.local/final/evidencias/` contagens, motivos de rejeição, descrições dimensionais, constraints, totais por companhia, aeroportos de origem/destino e distribuição mensal para ambos os DWs. `identidade_raw.json` comprova a igualdade do RAW reexportado com o CSV de ingestão, incluindo os valores vazios e a multiplicidade.

`validate` também gera logs das análises e da comparação em `.local/final/evidencias/`. Esses artefatos são locais até serem selecionados como evidência de entrega. Testes sintéticos usam seus próprios diretórios temporários e não substituem evidências reais publicadas.

## Roteiro de apresentação

1. Mostre os 36 arquivos e os layouts de 2021 no manifesto, sem abrir milhões de linhas no editor.
2. Mostre a função Pandas de conversão e um CSV tratado, depois o SQL de conversão e a tabela RAW. Explique onde cada transformação ocorre.
3. Consulte contagens de RAW, duplicatas, rejeições e fato por ano; mostre um motivo de rejeição.
4. Abra as sete dimensões de cada schema no diagrama DataGrip e destaque as FKs da fato.
5. Use a consulta de rastreabilidade para localizar o arquivo e o ordinal de uma ocorrência da fato. Para CSV multilinha, conte registros CSV com um leitor, não linhas do editor.
6. Execute `sql/comparacao/validar_final.sql`, que aborta se houver diferenças no conteúdo ou na multiplicidade.
7. Apresente totais anuais, média de atraso com denominador calculável, distribuição mensal e aeroportos mais movimentados. Explique que horários desconhecidos são NULL.
8. Mostre as variantes dimensionais e o snapshot descritivo escolhido sem apagar nomes históricos.
9. Mostre os logs dos testes automatizados e da reexecução idempotente. Distinga testes sintéticos das execuções dos CSVs completos.

## Backup e recuperação do cluster final

Com todos os processos PostgreSQL do cluster final encerrados, o mecanismo de backup já existente pode ser usado com os parâmetros da integração final:

```bash
.venv/bin/python scripts/backup_cluster_isolado.py \
  --cluster .local/final/postgres \
  --validation sql/comparacao/validar_restauracao.sql \
  --evidence .local/final/evidencias \
  --prefix final_2019_2021
```

Cria arquivo físico comprimido e privado em `backups/`, calcula SHA-256, restaura em diretório novo e confere os três anos, os totais de RAW e fatos, as dimensões e as chaves estrangeiras da cópia. Exige a mesma versão principal de PostgreSQL e espaço adicional para a restauração. O JSON `backup_isolado.json` identifica o arquivo recuperável, seu hash e o diretório restaurado. Esse backup protege o cluster isolado final; não é backup do banco nativo do usuário.

A ingestão RAW acontece uma vez por instalação; a reimportação manual é bloqueada para preservar a entrada. Para reexecutar cargas dimensionais e fatos sem duplicações, use `integracao_final.py validate`. Para reproduzir toda a extração e a instalação limpa, escolha outro diretório de saída e outro cluster; o programa preserva os anteriores.

`auditar_contrato_final.py` completa os diagnósticos contratuais: grupos exatos, linhas envolvidas, interseção entre excedentes e registros inválidos, partidas previstas fora do ano e repetições que aparecem apenas após TRIM/UPPER. Reutiliza as funções originais de padronização e não refaz tratamento ou carga de voos. Os resultados Pandas são confrontados com SQL sobre os 20 campos brutos, antes de conversões de tipos. O arquivo `vra_duplicatas_apos_padronizacao.csv` informa candidatos sem excluí-los da fato. O comando atualiza os resumos e gera `diagnosticos_contrato_sql.csv` e uma confirmação de equivalência em `.local/final/evidencias/`.


## Retomada da comparação

Se os dois DWs já estão carregados e a comparação foi interrompida, retome no cluster existente com o servidor desligado.

```bash
.venv/bin/python scripts/integracao_final.py compare
.venv/bin/python scripts/integracao_final.py compare --ano 2021
```

O primeiro comando verifica os três anos e o segundo permite retomar um ano específico. Ambos conferem dimensões e chaves estrangeiras. A comparação usa lotes de até 25 mil chaves de origem e 8 MB de `work_mem` por operação PostgreSQL. Em tabelas com chave única por ocorrência, compara todos os campos pelo par `(ano_origem,id_raw)`. As fatos são comparadas com valores naturais das dimensões. Anomalias múltiplas da mesma ocorrência são comparadas com multiplicidade. Os logs `validacao_ANO.log` registram confirmação por ano ou a primeira faixa divergente. A etapa `compare` consulta as cargas preservadas e atualiza apenas as funções e visões do schema `comparacao`.

A auditoria complementar lê os CSVs em lotes e agrupa no disco com SQLite, incluído no Python. Reserve espaço local para o agrupamento e as reexportações de RAW. Os comandos `evidencias_final.py` e `auditar_contrato_final.py` devem rodar em sequência com a comparação quando se usa o modo single-user.

## Armazenamento e retenção

Antes de preparar, carregar, comparar ou restaurar, confira `df -h .` e `df -i .`. Os comandos finais no terminal verificam a disponibilidade no volume de destino e exigem 8 GiB de reserva além do pico estimado. A instalação usa a soma dos CSVs brutos preparados para estimar os dois DWs, índices, WAL e áreas intermediárias. O backup estima a cópia e a restauração sem depender da compressão. Se a pré-verificação recusar, preserve o ambiente carregado e use outro volume com espaço comprovado para uma execução nova.

O cluster validado com os dois DWs ocupa aproximadamente 10,40 GiB em repouso. A reexportação dos RAWs verifica um arquivo temporário por vez e o descarta depois de comparar o hash. A auditoria complementar processa lotes e remove o banco SQLite criado para o agrupamento ao terminar. Os CSVs tratados, as auditorias, o cluster carregado e o backup validado permanecem disponíveis para a revisão.

A sequência manual no DataGrip executa SQL diretamente, então exige a conferência de espaço pelo operador. Para evitar crescimento acumulado, consulte o cluster existente durante a apresentação e use as evidências já produzidas. Antes de remover uma restauração de teste ou um cluster antigo, identifique sua finalidade, confirme desligamento limpo e confira a cópia preservada. Remova somente o diretório completo confirmado como redundante. Preserve os CSVs originais, os logs de validação e o backup recuperável. O relatório final lista os diretórios removidos nesta entrega.
