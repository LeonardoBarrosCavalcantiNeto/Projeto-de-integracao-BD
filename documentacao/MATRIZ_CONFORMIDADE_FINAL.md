# Matriz de Conformidade Final — Projeto VRA/ANAC (2019–2021)

**Contrato de referência:** [`Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf`](Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf), versão **1.1**, aprovada em **11/11/2026**.  
**Escopo:** seis pipelines (ETL e ELT para 2019, 2020 e 2021), dois Data Warehouses, rastreabilidade, qualidade, validações e reprodução acadêmica.  
**Base da revisão da entrega:** `main` em `6fb9485`, que inclui o PR #11 de Arthur. A execução histórica dos dados completos foi registrada em `86ffb99`.

**Base das evidências:** [`relatorio/STATUS_FINAL_PROJETO.md`](../relatorio/STATUS_FINAL_PROJETO.md), [`relatorio/QUALIDADE_2019_2021.md`](../relatorio/QUALIDADE_2019_2021.md), [`relatorio/PORTABILIDADE.md`](../relatorio/PORTABILIDADE.md), arquivos em [`resultados/validacoes/integracao_final/`](../resultados/validacoes/integracao_final/), e verificações do DataGrip feitas pelo responsável.

> **Validado (carga real)** identifica evidências da execução histórica dos 36 CSVs completos. **Testado (Fedora)** identifica verificações automatizadas. O registro de portabilidade descreve os testes sintéticos adicionais da revisão e os cenários pendentes. [Revisão da entrega](../relatorio/PORTABILIDADE.md#revisão-da-entrega)

## 1. Resultado executivo da integração

| Ano de origem | CSVs | Registros RAW por fluxo | Duplicatas excedentes | Rejeições após deduplicação | Fatos no `dw_etl` | Fatos no `dw_elt` | Divergências da comparação integral |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019 | 12 | 983.414 | 470 | 18 | 982.926 | 982.926 | 0 |
| 2020 | 12 | 483.545 | 124 | 1.512 | 481.909 | 481.909 | 0 |
| 2021 | 12 | 632.148 | 0 | 25.511 | 606.637 | 606.637 | 0 |
| **Total** | **36** | **2.099.107** | **594** | **27.041** | **2.071.472** | **2.071.472** | **0** |

**Equação de conservação:** `RAW = duplicatas excedentes + rejeições dos representantes + registros válidos`. Cada DW representa as **mesmas ocorrências**, tratadas por tecnologia diferente; **não somar os fatos dos dois DWs** para obter quantidade de voos.

**Confirmação prática posterior:** o responsável conectou o DataGrip ao cluster preservado, encontrou as sete dimensões e a tabela `fato_voo` nos dois schemas e verificou `COUNT(*) = 2.071.472` em cada fato. Também informou sucesso na consulta por ano que verifica proveniência e chaves principais.

## 2. Conformidade dos seis pipelines e da arquitetura

| Requisito | ETL — Python/Pandas | ELT — PostgreSQL/SQL | Situação final | Principal evidência ou implementação |
|---|---|---|---|---|
| 2019, 12 CSVs originais | Tratamento pré-carga | Tratamento após carga bruta | **Validado (carga real)** | Totais de 2019 no relatório final e no DW |
| 2020, 12 CSVs originais | Tratamento pré-carga | Tratamento após carga bruta | **Validado (carga real)** | Totais de 2020 no relatório final e no DW |
| 2021, 12 CSVs originais | Tratamento pré-carga | Tratamento após carga bruta | **Validado (carga real)** | Totais de 2021 e layouts da fonte |
| Independência dos dois métodos | CSV tratado produzido por funções Pandas, carregado em `staging_etl` | RAW carregado antes da transformação SQL em `staging_elt` | **Validado (carga real)** | `scripts/integracao_final.py`, [`INTEGRACAO_FINAL.md`](INTEGRACAO_FINAL.md) |
| Isolamento do armazenamento | `raw_etl`, `staging_etl`, `dw_etl` | `raw`, `staging_elt`, `dw_elt` | **Validado (carga real)** | Esquemas distintos no PostgreSQL; instalação ETL sem ELT testada |
| Modelo dimensional | 7 dimensões + 1 fato | 7 dimensões + 1 fato | **Validado (carga real)** | [`MODELO_DIMENSIONAL_FINAL.md`](MODELO_DIMENSIONAL_FINAL.md) |
| Granularidade e unicidade | Uma ocorrência válida por ano e `id_raw` | Mesma regra | **Validado (carga real)** | `UNIQUE (ano_origem,id_raw)` e origem única, constraints |
| Reexecução idempotente | Carga dimensional sem duplicar | Carga dimensional sem duplicar | **Validado (carga real)** | Reexecução e verificações de quantidade/constraints |
| Comparação ETL × ELT | Conteúdo Pandas | Conteúdo SQL | **Validado (carga real)** | `sql/comparacao/validar_final.sql`; comparação em lotes por ocorrência |
| Análises produzidas | Contagens, atrasos, companhias, aeroportos, meses | Mesmas consultas e indicadores | **Validado (carga real)** | Relatório final e evidências analíticas |

**Implementações reutilizadas:** `scripts/integrar_anac.py` e SQL canônico 2019/2020; funções Pandas do ETL 2021 reutilizadas para os três anos; ELT 2021 incorporado; DDL e carga dimensional adaptados para ambos os DWs. Os scripts e notebooks originais permanecem como registro da participação dos integrantes. Não confundir o roteiro legado `integrar_anac.py apply` (2019/2020) com o ponto de entrada final `scripts/integracao_final.py` (2019–2021).

## 3. Matriz de aderência ao contrato de tratamento v1.1

| Nº | Regra do contrato | Implementação ETL / ELT | Situação / comprovação |
|---:|---|---|---|
| 1 | Conferir 12 arquivos por ano, nomes, cabeçalhos e formatos | Ingestão valida inventário e layouts; 2021 admite extensão `Codeshare` | **Validado:** 36 CSVs; manifesto da fonte |
| 2 | Preservar origem sem alterar CSVs originais | RAW separados preservam registros e atributos brutos | **Validado:** hashes das fontes e reexportação RAW |
| 3 | Guardar `ano_origem`, `arquivo_origem`, `linha_origem` | Metadados em ingestão, tratados, auditorias e fato | **Validado:** vínculos de proveniência; conferência local |
| 4 | Usar nomes canônicos e tipos definidos | Conversores Pandas e funções SQL equivalentes | **Validado:** comparação por conteúdo dos tratados |
| 5 | Manter `numero_voo` e `codigo_di` como texto | Sem conversão indevida para número | **Validado:** testes de zeros à esquerda e campos textuais |
| 6 | Normalizar códigos, categorias e espaços externos | Padronização consistente em Python e SQL | **Validado:** comparação dos valores tratados |
| 7 | Converter vazios em `NULL` somente na camada tratada | RAW preservado; tratado normalizado | **Validado:** qualidade e testes de ausência |
| 8 | Tratar assentos opcionais inválidos como `NULL` e auditar | Conversão segura, com anomalias | **Validado:** testes de conversão e auditoria |
| 9 | Validar datas por calendário; previstas inválidas rejeitam | Conversões estritas em ambos os fluxos | **Validado:** testes de datas inválidas e motivos de rejeição |
| 10 | Não usar horário real ausente para presumir cancelamento | Horários reais ausentes geram `NULL`; situação original preservada | **Validado:** indicadores e comparação |
| 11 | Deduplicar exatamente os 20 campos brutos, antes do tratamento | Pandas `duplicated` e SQL `ROW_NUMBER` | **Validado:** 594 excedentes e auditorias pareadas |
| 12 | Manter representante determinístico por ordem da origem | Primeira ocorrência, mantendo vínculo do excedente | **Validado:** registros e representantes conciliados |
| 13 | Excluir excedentes só da camada analítica | RAW completo; duplicatas em auditoria | **Validado:** equação de conservação por ano |
| 14 | Rejeitar registros sem companhia, origem, destino ou datas previstas válidas | Motivos múltiplos registrados por ocorrência | **Validado:** 27.041 registros rejeitados |
| 15 | Preservar todos os motivos, sem somá-los como pessoas/registros | Rejeições auditáveis, mesmo quando há mais de um motivo | **Validado:** relatório anual de qualidade |
| 16 | Medir diferença assinada em minutos | `diferenca_partida_min`, `diferenca_chegada_min` | **Validado:** comparação integral das métricas |
| 17 | Calcular atraso `max(diferença,0)` sem transformar `NULL` em zero | Mesma regra nos dois fluxos | **Validado:** testes de antecipação e `NULL` |
| 18 | Sinalizar diferenças absolutas acima de 1.440 min, sem eliminar | Flags de partida e chegada | **Validado:** totais de atípicos por ano |
| 19 | Registrar datas operacionais fora do ano da fonte sem exclusão automática | Diagnóstico separado por ano | **Validado:** 12 / 15 / 15 partidas previstas fora do ano |
| 20 | Resolver conflitos de nomes dimensionais sem perder histórico | Snapshot descritivo e variantes auditáveis; correções documentadas de aeroportos | **Validado:** cadastros, auditorias e comparações |
| 21 | Usar sete dimensões, chaves naturais estáveis e fato elegível | Mesma modelagem nos dois DWs | **Validado:** 7 dimensões + fato por schema |
| 22 | Evitar FKs órfãs e conflito de chaves técnicas | Constraints, chaves por ano e associação fato → staging | **Validado:** FKs, unicidade e testes |
| 23 | Conciliar totais, categorias e indicadores dos dois métodos | Comparação integral por ocorrência e chaves naturais | **Validado:** zero divergências relatadas |
| 24 | Disponibilizar auditorias e resultados reproduzíveis | `resultados/validacoes/integracao_final/`, relatórios e testes | **Validado no ambiente de referência** |

**Nota importante:** os 20 campos contratuais são a chave de duplicação. A extensão `Codeshare`, presente em parte dos CSVs de 2021, é preservada nos brutos e nas auditorias, sem mudar a política aprovada.

## 4. Qualidade e resultados verificáveis

| Indicador | 2019 | 2020 | 2021 |
|---|---:|---:|---:|
| Grupos de duplicatas exatas | 444 | 124 | 0 |
| Linhas envolvidas em duplicatas | 914 | 248 | 0 |
| Excedentes removidos da fato | 470 | 124 | 0 |
| Rejeições (linhas distintas) | 18 | 1.512 | 25.511 |
| Partidas previstas fora do ano do CSV | 12 | 15 | 15 |
| Partidas com diferença absoluta >24h | 684 | 286 | 371 |
| Chegadas com diferença absoluta >24h | 690 | 331 | 373 |

As quantidades de partidas/chegadas atípicas são as **contagens finais após deduplicação**, não as estimativas da implementação histórica. A comparação de grupos exatos, linhas envolvidas, sobreposição com inválidos, candidatos após `TRIM/UPPER` e datas fora do ano foi relatada como equivalente entre Pandas e PostgreSQL. Ver [`QUALIDADE_2019_2021.md`](../relatorio/QUALIDADE_2019_2021.md) e [`diagnosticos_contrato_sql.csv`](../resultados/validacoes/integracao_final/diagnosticos_contrato_sql.csv).

## 5. Testes, evidências e reprodução

| Verificação | Estado | Evidência / observação |
|---|---|---|
| Seis pipelines sobre os 36 CSVs reais | **Validado (carga real)** | Relatório final, logs/evidências da execução original |
| Dois DWs com 2.071.472 fatos cada | **Validado (carga real)** | Relatório final e conferência no DataGrip |
| Comparação completa por conteúdo e ocorrência | **Validado (carga real)** | [`comparacao_integral.json`](../resultados/validacoes/integracao_final/comparacao_integral.json), SQL de comparação |
| Rastreabilidade até o CSV original | **Validado (carga real)** | FKs, ocorrências RAW, manifesto e auditorias |
| Idempotência das cargas | **Validado (carga real)** | Reexecução das dimensões/fatos sem duplicação |
| Backup físico e teste de restauração | **Validado no ambiente de referência** | [`backup_isolado.json`](../resultados/validacoes/integracao_final/backup_isolado.json) |
| Roteiro manual SQL e instalação ETL isolada | **Testado no ambiente de referência** | Suíte de integração original e logs |
| Suíte após adaptações de portabilidade | **Testado (Fedora)** | **10 testes aprovados**, segundo a execução informada no commit `def47cc` |
| Suíte da revisão da entrega | **Testado (Fedora)** | 50 testes aprovados com fixtures e PostgreSQL 18.6. [Revisão](../relatorio/PORTABILIDADE.md#revisão-da-entrega) |
| 36 CSVs locais contra manifesto SHA-256 | **Testado (Fedora)** | **36 conferências aprovadas**, segundo relatório de portabilidade |
| Guia de Windows, macOS e Linux | **Testado com fixtures no Fedora** | Windows e macOS aguardam execução. [Guia](REPRODUCAO_MULTIPLATAFORMA.md) |
| Download automatizado da ANAC | **Testado com URLs locais** | Download HTTPS dos 36 CSVs pendente. [Portabilidade](../relatorio/PORTABILIDADE.md) |
| Fluxo por serviço PostgreSQL com autenticação, `psql` e backup lógico | **Testado com fixtures no Fedora** | Serviço descartável, SCRAM em loopback e restauração validada. [Revisão](../relatorio/PORTABILIDADE.md#revisão-da-entrega) |
| Cliente gráfico DataGrip na máquina do responsável | **Confirmado posteriormente** | Conexão local e consultas de schemas, fatos e distribuição anual |
| GitHub publicado | **Main consolidada no remoto** | PR #11 de Arthur incorporado. |

## 6. Limitações e decisões que devem ser explicadas na apresentação

1. **Fusos horários:** timestamps preservam data/hora conforme a fonte; não foram convertidos automaticamente entre fusos. Isso impede interpretar diferenças como tempo físico universal sem confirmação da semântica da ANAC.
2. **`referencia`:** seu significado operacional na fonte não foi estabelecido integralmente pelo contrato; não inventar uma interpretação.
3. **Pontualidade:** a implementação usa **atraso positivo (>0 min)** como critério uniforme de *voo atrasado* nas análises; o contrato não fixava um limiar institucional obrigatório.
4. **Conflitos de descrições ICAO:** o cadastro exibe a última descrição não nula observada (snapshot tipo 1), com variantes históricas no staging/auditorias; isso não certifica qual é o nome oficial atual da companhia ou do aeroporto.
5. **Portabilidade:** Windows/macOS e download oficial por HTTPS ainda precisam ser testados em ambiente real; não afirmar que esses testes já passaram.
6. **Execução reproduzível:** requer Python 3.11+, PostgreSQL 18 e os 36 arquivos oficiais conferidos pelo manifesto. O Git não transporta o cluster PostgreSQL nem os CSVs brutos; scripts e documentação permitem construí-los localmente.
7. **Execução segura:** o cluster PostgreSQL validado foi preservado; reproduzir a carga completa exige espaço extra considerável. Os controles de disco requerem margem de 8 GiB **além do pico estimado**.

## 7. Referências internas e pontos de entrada

- **Contrato normativo:** `documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf`.
- **Execução final:** `scripts/integracao_final.py` — `prepare`, `isolated`, `compare`, `validate`.
- **ETL Pandas:** `scripts/etl_vra_anac_2021.py`, reutilizado pelos três anos; implementações anteriores preservadas.
- **Ingestão e ELT:** `scripts/integrar_anac.py`, `sql/transformacoes/`, `sql/integracao/` e SQL específico de 2021.
- **Modelagem:** `documentacao/MODELO_DIMENSIONAL_FINAL.md` e `sql/database/10_criacao_dw.sql` (DDL adaptado pelo executor).
- **Comparação integral:** `sql/comparacao/validar_final.sql`.
- **Auditoria complementar:** `scripts/auditar_contrato_final.py`.
- **Reprodução multiplataforma:** `documentacao/REPRODUCAO_MULTIPLATAFORMA.md` e `scripts/baixar_vra.py`.
- **Relatórios de resultados:** `relatorio/STATUS_FINAL_PROJETO.md`, `relatorio/QUALIDADE_2019_2021.md`, `relatorio/PORTABILIDADE.md`.
- **Evidências compactas:** `resultados/validacoes/integracao_final/`.
- **Testes:** `tests/`, `python -m unittest discover -s tests -v`.

---

A execução histórica com dados reais comprovou a equivalência e a rastreabilidade no Fedora/PostgreSQL 18. A revisão da entrega conferiu o fluxo com dados sintéticos. A reprodução em Windows e macOS, a execução hospedada no Colab e o download integral por HTTPS aguardam verificação.
