# Verificação de portabilidade

Na adaptação histórica de portabilidade, o trabalho partiu de `86ffb99de2cb89f458012303a48f3b584a9a8409`, a entrega do Fedora que registrou **2.071.472 fatos em cada DW**. Os 12 CSVs de 2019 foram retirados da árvore versionada. A entrega atual obtém os arquivos brutos pelo procedimento do [guia de reprodução](../documentacao/REPRODUCAO_MULTIPLATAFORMA.md).

## Execução anterior de portabilidade

- No Fedora 44, com Python 3.13.15, Pandas 2.3.3 e PostgreSQL 18.6, os **10 testes passaram**. Os testes SQL usaram clusters sintéticos descartáveis em modo single-user. Exercitaram ETL e ELT, cargas independentes, reexecução idempotente, auditorias e detecção de divergência. O teste de formatação de caminho Windows usa `PureWindowsPath` no Fedora.
- Os 36 arquivos locais, totalizando 622.042.381 bytes, passaram por verificação de tamanho e SHA-256. Os hashes correspondem à [auditoria de fontes da entrega](../resultados/validacoes/integracao_final/fontes_inalteradas.json). Os testes do downloader usaram arquivos pequenos servidos pelo leitor de URL local e verificaram publicação, rejeição por hash ou tamanho e preservação de arquivo existente.
- Os índices oficiais exibiam os 36 nomes e tamanhos registrados. [2019](https://siros.anac.gov.br/siros/registros/diversos/vra/2019/), [2020](https://siros.anac.gov.br/siros/registros/diversos/vra/2020/), [2021](https://siros.anac.gov.br/siros/registros/diversos/vra/2021/)
- `check-load` aceitou a amostra pequena e recusou o volume real com cerca de 14,3 GiB livres. Para o bundle validado, calculou 19,86 GiB de pico estimado e 8 GiB de reserva, totalizando 27,86 GiB.
- O cluster existente foi preservado. As contagens completas permanecem documentadas na [validação anterior](STATUS_FINAL_PROJETO.md). A carga integral e a restauração física foram dispensadas nesta adaptação.

Para reexecutar a suíte no Fedora, com a venv ativa, execute os comandos abaixo. Os testes de integração criam clusters PostgreSQL sintéticos temporários. As instruções de instalação e reprodução estão no [guia multiplataforma](../documentacao/REPRODUCAO_MULTIPLATAFORMA.md). O diretório temporário usado nesta validação ficou no SSD do projeto, com mais de 8 GiB livres.

```bash
mkdir -p .local/portabilidade-tmp
LC_ALL=C PYTHONUTF8=1 TMPDIR="$PWD/.local/portabilidade-tmp" python -m unittest discover -s tests -v
```

## Revisão da entrega

A revisão partiu da `main` em `6fb9485`, que inclui o PR #11 de Arthur. Uma nova venv no Fedora 44, com Python 3.13.15, instalou `requirements.txt` e passou em `python -m pip check`. A suíte `python -m unittest discover -s tests -v` aprovou os 50 testes dos 12 módulos, com zero falhas e zero omissões. Os testes integrados usaram fixtures em clusters PostgreSQL 18.6 descartáveis. A suíte usou também um socket Unix privado para a carga individual de 2021 e a verificação pós-carga das funções do Colab.

- Um serviço temporário em loopback aceitou autenticação SCRAM, os dois bundles via `psql`, os scripts de comparação, análise e rastreabilidade e as 16 consultas do guia de demonstração. Cada DW gerou 3, 3 e 7 fatos para 2019, 2020 e 2021, com `COMPARACAO_EXATA_OK` nos três anos. O ciclo `pg_dump` e `pg_restore` em banco vazio retornou `RESTAURACAO_OK`. Um teste de regressão também verificou a validação da restauração quando um ano tem registros brutos e zero fatos.
- O validador de guias e bundles conferiu 53 hashes e a ordem das 12 etapas manuais. Os notebooks ETL dos três anos rodaram em Jupyter com fixtures e foram inicializados tanto na raiz quanto em `notebooks/etl/`. Os notebooks ELT foram validados quanto à sintaxe e à proteção de execução local. A preparação do ETL 2021 no Colab foi simulada, incluindo a conferência de um ZIP sintético.
- O volume do projeto tinha cerca de 7,4 GiB livres e o volume temporário, cerca de 3 GiB. As verificações de espaço de `prepare` e `check-load` recusaram o destino temporário pela reserva exigida. O teste de carga usou bundles gerados pela função de preparação com entradas sintéticas. Os 36 CSVs reais estavam ausentes em `dados/brutos/`. Os resultados de carga completa continuam sendo os da execução histórica.

## Cenários pendentes

| Cenário | Alcance da verificação |
| --- | --- |
| Windows e macOS | Guias preparados. Instalação, preparação, carga e validação ainda precisam ser executadas em cada sistema real. |
| Download HTTPS pelo script | A adaptação anterior verificou os índices oficiais e as cópias locais. Os testes automatizados exercitam downloads com URLs de arquivos locais. O download dos 36 CSVs via HTTPS segue pendente. |
| Colab hospedado | A suíte verifica os auxiliares de entrada e pós-carga. A execução hospedada permanece pendente nesta revisão. |
| Clientes gráficos | A revisão usou o terminal. O responsável relatou uma conexão anterior via DataGrip com o cluster histórico. |
