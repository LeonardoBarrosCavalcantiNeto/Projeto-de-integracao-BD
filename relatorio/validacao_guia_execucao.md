# Validação do guia completo de execução

Referência inicial auditada: `a65f7e4`, branch local `integracao-2019-2020-canonica`. Os dois documentos e o gerador manual foram acrescentados nesta entrega. Nenhuma migração ou alteração no banco original foi executada.

## O que foi conferido

- Leitura do executor, template ELT, DDL, SQLs integrados/históricos, README, testes, relatório e evidências anteriores.
- `prepare --help`, `apply --help`, `testar_integracao_isolada.py --help` e `postgresql-setup --help` executados para conferir parâmetros.
- Quatro testes automatizados aprovados; o teste PostgreSQL passou pelos modos automatizado e manual, em clusters sintéticos novos e distintos, com os mesmos resultados.
- `prepare` executado novamente com os 24 CSVs reais, gerando bundle em `.local/guia_validacao/bundle` e onze etapas manuais.
- Execução limpa da sequência manual em cluster novo, sem sockets, em `.local/guia_validacao/postgres_manual`. O executor converte apenas os metacomandos de importação para COPY servidor e executa cada arquivo em uma sessão PostgreSQL separada, respeitando os commits entre etapas.

Os resultados finais do teste integral estão registrados abaixo. A interface gráfica do DataGrip não faz parte desse teste: os arquivos SQL são os mesmos a abrir no cliente.

## O que depende de execução na máquina do leitor

Instalação de pacotes Fedora, sudo/systemd, criação do serviço/usuário por administração, autenticação TCP, driver JDBC e cliques no DataGrip, Docker, instalação pip com internet e os 24 downloads não foram executados nesta sessão. As instruções foram conferidas nas documentações oficiais indicadas no guia. A orquestração `apply` com pg_dump/pg_restore contra um serviço continua não testada aqui porque os sockets estão bloqueados.

PostgreSQL efetivamente usado: 18.6. O SQL foi analisado em relação aos recursos documentados do PostgreSQL 16, mas não foi executado no 16/17. Não se declara compatibilidade integral testada nessas versões. A imagem Docker `postgres:18` também não foi executada; sua versão secundária pode ser diferente de 18.6.

Os commits são locais. Não foi feito push. A existência da branch da entrega no GitHub não é presumida; o guia fornece a alternativa Git bundle para distribuição do código sem publicar.

## Ajustes implementados

- `scripts/integrar_anac.py`: `prepare` agora gera onze etapas em `manual/`, com os mesmos blocos SQL da carga automatizada. Acrescenta hashes dessas etapas ao manifesto. A importação tem guarda de RAW vazia e transação própria. Mensagens de erro capturadas dos clientes PostgreSQL são apresentadas no terminal, sem colocar senha na linha de comando.
- `scripts/testar_integracao_isolada.py`: opção `--manual` executa as etapas geradas separadamente em um cluster novo e depois testa reexecução/validação da carga.
- `tests/test_pipeline_postgresql.py`: compara os resultados dos dois modos em clusters sintéticos diferentes.
- `scripts/validar_guia.py`: verifica referências locais, caminhos dos arquivos gerados, sintaxe de todos os blocos Bash, Python embutido e ausência de metacomandos psql nos arquivos SQL destinados ao DataGrip. Não executa os comandos administrativos escritos no manual.
- `README.md`: links para o guia completo e a ordem rápida.

A sequência manual requer Python para preparar a ingestão e psql para importar, pois o protocolo SQL do DataGrip não executa `\copy`. Não foi criada uma dependência de COPY servidor para a execução normal: o psql lê arquivos locais do usuário. A substituição por COPY servidor é exclusiva do executor isolado de testes.

## Equivalência com a carga automatizada anterior

Foi comparado o novo `carga.sql` com o bundle automatizado real da entrega anterior: são iguais após normalizar somente o caminho absoluto do bundle e linhas vazias. Os dois CSVs canônicos têm SHA-256 iguais aos já validados na entrega anterior. Portanto, a geração manual não introduziu outra regra de transformação para o modo automatizado.

Evidência local: `.local/guia_validacao/equivalencia_bundle.json`. Os hashes dos 24 originais e dos arquivos gerados estão em `.local/guia_validacao/bundle/manifesto.json`. A preparação não alterou os originais.

## Resultado da reconstrução limpa com dados reais

A sequência **01 a 11** foi concluída com sucesso em PostgreSQL **18.6**, a partir de cluster vazio e dos 24 CSVs reais. O cluster novo ficou em `.local/guia_validacao/postgres_manual`, banco `postgres`, independente do servidor do DataGrip. Cada etapa foi executada em sessão separada, incluindo commits e importação, reproduzindo a ordem documentada.

| Ano | RAW | Excedentes | Rejeitados | Tratada/fato |
|---|---:|---:|---:|---:|
| 2019 | 983414 | 470 | 18 | 982926 |
| 2020 | 483545 | 124 | 1512 | 481909 |
| Total | 1466959 | 594 | 1530 | **1464835** |

Após as onze etapas, a carga dimensional/fato foi executada novamente e validada: o total permaneceu **1464835**. As asserções de proveniência, classificação, conteúdo da fato, medidas temporais e integridade dimensional passaram. Os casos limite de conversão e as restrições NOT NULL/CHECK também foram executados sobre o banco reconstruído.

As dez consultas SQL copiadas diretamente da seção 11 do guia foram executadas nesse cluster. As saídas estão em `resultados/validacoes/guia_execucao/consulta_01.csv` a `consulta_10.csv`, e o SQL efetivamente extraído está em `consultas_executadas.sql` na mesma pasta. A ausência de rastreabilidade, duplicação e conflito deve ser lida como resultados vazios, não como consultas omitidas. A validação dos arquivos/documentos também conferiu 14 hashes do bundle e 35 blocos Bash, sem erros.

Evidências pequenas versionadas: [pasta de validação do guia](../resultados/validacoes/guia_execucao/). Os logs grandes de análises e os CSVs canônicos ficam locais. O banco original e seus schemas não foram modificados, nem foi executada a migração.

## Distribuição e demonstração

Os documentos principais são `documentacao/GUIA_EXECUCAO_COMPLETA.md` e `documentacao/ORDEM_DOS_SCRIPTS.md`. A sequência SQL de apresentação é gerada por `prepare` e deve ser aberta no DataGrip depois da preparação dos arquivos. Somente `02_importar_raw.psql` vai ao terminal. Não se afirma que a interface gráfica tenha sido automatizada/testada; o conteúdo SQL dos arquivos foi executado integralmente.

A entrega inclui um Git bundle local em `.local/entrega/integracao-2019-2020-canonica.bundle` para permitir distribuição sem push. Ele leva código e histórico, não leva CSVs de entrada, cluster ou backups locais. O clone no GitHub depende da publicação autorizada da branch; o manual não presume que os commits locais já estejam no remoto.
