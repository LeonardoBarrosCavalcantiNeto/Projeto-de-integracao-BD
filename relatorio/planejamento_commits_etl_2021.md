# Revisão dos cinco commits — ETL 2021

**Registro da preparação:** os quatro primeiros blocos já foram commitados na
branch `feat/etl-2021`; este documento acompanha a revisão do quinto. A mensagem
do quinto continua sujeita à edição e autorização de Arthur.
Os cinco recortes locais estão em
`dados/processados/2021/revisao_commits/`, fora do Git. Eles preservam as versões
intermediárias do script, que aparece em mais de um bloco.

Edite `mensagem_01.txt` a `mensagem_05.txt` nessa pasta. Os títulos abaixo são
sugestões iniciais, copiadas do plano. Autorizar implementação não autoriza commit.
Os patches são para a base `65cf857`; precisam de revisão caso a base mude.
A criação dos commits usará as mensagens editadas apenas depois da autorização.

## 1 — Entrada e originais

Sugestão: `fix: valida e preserva os arquivos brutos de 2021`

- Alterar `scripts/etl_vra_anac_2021.py`.
- Criar `tests/__init__.py`, `tests/apoio_etl_2021.py` e
  `tests/test_etl_2021_entrada.py`.
- Testes: layouts ordenados, mês vazio, arquivo ausente, cabeçalho inválido,
  largura incorreta e cópia byte a byte/SHA-256.
- Saídas locais: `vra_bruta/VRA_2021_MM.csv`, `vra_bruta/manifesto_sha256.csv` e inventário.

## 2 — Duplicatas

Sugestão: `fix: completa a auditoria de duplicatas de 2021`

- Alterar `scripts/etl_vra_anac_2021.py`.
- Criar `tests/test_etl_2021_duplicatas.py`.
- Testes: repetição entre meses, representante estável, excedente inválido sem
  contagem dupla e preservação dos iguais somente após padronização.
- Saídas locais: auditorias de duplicatas, qualidade e `etl_resumo.json`.

## 3 — Tratamento e rastreabilidade

Sugestão: `fix: padroniza as saídas de tratamento e rastreabilidade`

- Alterar `scripts/etl_vra_anac_2021.py` e instruções do notebook.
- Criar `tests/test_etl_2021_tratamento.py`.
- Testes: opcionais inválidos, todos os motivos, todos rejeitados, zeros,
  referências, nulos, calendário, datas extremas e cruzamento de ano.
- Saídas locais: tratados, rejeições, anomalias, partidas fora do ano,
  `etl_log_arquivos.csv`, metadados e `LEIA_ME.md`.

## 4 — Carga PostgreSQL

Sugestão: `feat: valida a carga PostgreSQL da camada tratada de 2021`

- Alterar `scripts/etl_vra_anac_2021.py` e configuração documentada no notebook.
- Criar `tests/test_carga_etl_2021.py`.
- Testes reais: dez tabelas, contagens, chaves, repetição bloqueada,
  substituição explícita e rollback preservando a carga anterior.
- Saídas locais: status e metadados; `.env` permanece fora do Git.
- A evidência pequena da carga completa acompanha o quinto bloco documental.

## 5 — Comparação, relatório e evidências

Sugestão: `docs: registra a conciliação e as evidências do ETL 2021`

- Criar `scripts/comparar_etl_elt_2021.py` e `tests/test_comparacao_etl_elt_2021.py`.
- Criar `relatorio/relatorio_etl_2021.md` e este planejamento.
- Atualizar `README.md`, instruções Colab e saídas do notebook.
- Criar em `resultados/logs/`: `inventario_arquivos_etl_2021.csv` e
  `metadados_execucao_etl_2021.json`.
- Criar em `resultados/validacoes/`: `resumo_qualidade_etl_2021.csv`,
  `mensal_etl_2021.csv`, `comparacao_etl_elt_2021.json`,
  `conflitos_codigo_etl_2021.csv` e `validacao_postgresql_etl_2021.json`.
- Testes: diferença de valores com totais iguais, hashes divergentes, nulo versus
  zero, normalização, presença, origens repetidas e campos ausentes.

**Ainda não fecha os critérios finais do plano:** o inventário do ELT já foi
obtido do commit `b6c6b463e0eadb76be86a72415d3eb288610d0d0` e os 12 hashes,
tamanhos e contagens coincidem. Faltam a tabela tratada completa para comparar os
valores por registro e a reprodução no Google Colab. O JSON e o relatório
registram separadamente o que foi conferido e o que permanece pendente. A regressão com o ETL anterior passou nos
606.637 registros tratados, sem divergências de valores ou hashes; isso é uma
verificação diferente da comparação com Murilo.

## Conferência antes de autorizar

Revise código, relatório e mensagens. Os dados completos e os patches ficam fora
do Git. A suíte completa executada com PostgreSQL temporário passou em 24 testes.
Sem `ETL_2021_TEST_DATABASE_URL`, a execução comum pula a classe dos três testes
de integração, como documentado no README.
