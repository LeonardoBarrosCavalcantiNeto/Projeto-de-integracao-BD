# Verificação de portabilidade

A árvore de trabalho estava limpa antes das alterações. A branch local `portabilidade-academica` partiu de `86ffb99de2cb89f458012303a48f3b584a9a8409`, a entrega do Fedora que registrou **2.071.472 fatos em cada DW**. Os 12 CSVs de 2019 saíram da árvore versionada da nova branch e continuam no disco local e no histórico. Um ZIP gerado com `git archive` da branch entrega apenas a árvore atual.

## Execução medida

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

## Cenários pendentes

| Cenário | Alcance da verificação |
| --- | --- |
| Windows e macOS | Guias preparados. Instalação, preparação, carga e validação ainda precisam ser executadas em cada sistema real. |
| Fedora com serviço TCP | A sessão bloqueou sockets TCP e Unix. A validação SQL nesta adaptação usou single-user. A execução dos bundles diretamente via psql, a autenticação libpq e o ciclo `pg_dump` / `pg_restore` via serviço aguardam teste com sockets disponíveis. |
| Download HTTPS pelo script | A resolução de DNS falhou na sessão de execução. Os resultados registrados são a consulta dos índices oficiais, a conferência das cópias locais e os testes com URLs de arquivos locais. |
| Clientes gráficos | Os parâmetros de conexão estão no guia. pgAdmin, DBeaver e DataGrip aguardam teste nesta adaptação. |
