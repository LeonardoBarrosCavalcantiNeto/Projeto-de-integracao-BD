# Relatório técnico — ETL VRA/ANAC 2019

> **Nota histórica.** As pendências e os testes descritos neste relatório correspondem à implementação individual de 2019. A execução com dados reais, a carga dimensional e a conciliação com o ELT foram validadas posteriormente no pipeline integrado dos três anos. Consulte o [relatório final do projeto](STATUS_FINAL_PROJETO.md).

**Contrato de referência:** Contrato Único de Dados e Tratamento VRA/ANAC, versão 1.1, atualizado em 11/11/2026  
**Pipeline:** ETL 2019  
**Situação desta entrega:** código e notebook corrigidos; teste sintético aprovado; execução com os 12 CSVs reais e carga no PostgreSQL ainda pendentes.

---

## 1. Objetivo e escopo

Este ETL processa exclusivamente os arquivos mensais VRA/ANAC de 2019. A implementação foi ajustada para seguir o contrato v1.1 do grupo, mantendo a equivalência das regras de qualidade com o pipeline ELT: preservação da origem, exclusão analítica somente das ocorrências excedentes de duplicatas exatas, rejeição dos registros sem os atributos obrigatórios, auditoria e modelo dimensional.

O fluxo é:

1. Conferir os 12 CSVs e seus 20 cabeçalhos originais.
2. Copiar os arquivos originais sem modificá-los e carregar seus valores como texto.
3. Identificar duplicatas exatas comparando os 20 campos originais, antes de `TRIM`, `UPPER` ou conversões.
4. Escolher como representante a primeira ocorrência na ordem estável de nome do arquivo e número do registro.
5. Padronizar e validar os dados. Apenas os representantes válidos seguem para a camada analítica.
6. Produzir auditorias, métricas, arquivos de saída e as sete dimensões com a Fato.
7. Opcionalmente, carregar a camada bruta, as saídas de tratamento, as auditorias e o esquema estrela no PostgreSQL.

O processo não implementa ELT e não consolida 2020 ou 2021.

## 2. Correções aplicadas em relação à implementação anterior

| Ponto | Implementação anterior | Implementação corrigida |
|---|---|---|
| Deduplicação | Depois da padronização, comparando valores canônicos | Antes da padronização, comparando os 20 valores brutos originais |
| Escolha do representante | Primeira linha do conjunto já padronizado | Primeira ocorrência por arquivo ordenado e `linha_origem` |
| Auditoria de duplicatas | Exportava ocorrências excedentes, mas sem reproduzir integralmente a regra v1.1 | Exporta os 20 campos brutos, ano, arquivo, linha, grupo e referência à ocorrência preservada |
| Possíveis duplicatas após limpeza | Não eram apresentadas separadamente | São sinalizadas em `vra_possiveis_duplicatas_padronizacao.csv.gz`, sem exclusão automática |
| Campos obrigatórios | Incluía `numero_voo`, `tipo_linha`, `situacao_voo` e `referencia` | Usa somente companhia ICAO, aeroporto de origem, aeroporto de destino, partida prevista e chegada prevista |
| Datas opcionais | Podiam ser tratadas como rejeição | Horários reais inválidos e `referencia` inválida viram anomalias; não rejeitam a linha por si só |
| Número de assentos | Aceitava números negativos | Aceita apenas inteiro não negativo; valor inválido vira `NULL` e anomalia |
| Fato | Armazenava flag de duplicata | Não armazena flags de duplicata; essas informações ficam na auditoria |
| Métricas de horário | Calculava diferenças e atrasos | Mantém as medidas e acrescenta as duas flags de horário atípico previstas no contrato |
| Preservação bruta | Staging já continha dados normalizados | Copia os CSVs byte a byte para `vra_bruta/` e também oferece a tabela `vra_bruta` no PostgreSQL |
| Conciliação | Não garantia claramente a equação atualizada | Confere `brutas = excedentes excluídas + rejeições remanescentes + Fato` |

## 3. Entrada e preservação dos dados

O script exige exatamente estes arquivos:

`VRA_2019_01.csv` até `VRA_2019_12.csv`.

A leitura usa `sep=';'`, `encoding='utf-8-sig'`, `dtype=str`, `keep_default_na=False` e `na_filter=False`. O cabeçalho é comparado com os 20 nomes originais e na ordem esperada. A leitura não converte os campos de origem para números ou datas.

São adicionados os metadados:

- `ano_origem`: 2019;
- `arquivo_origem`: nome do CSV;
- `linha_origem`: sequência de registros do arquivo, iniciando em 2 porque o cabeçalho é a linha 1;
- `data_carga`, `pipeline` e `versao_contrato`: rastreabilidade da execução.

Os 12 arquivos originais são copiados sem regravação para `dados/processados/2019/vra_bruta/`. Um manifesto registra tamanho e SHA-256, permitindo verificar a integridade da cópia. Com a carga PostgreSQL habilitada, a tabela `dw_etl.vra_bruta` contém os 20 campos originais como `TEXT`, além dos metadados.

## 4. Mapeamento e padronização

Os 20 nomes tratados são os definidos na seção 3 do contrato:

| Coluna original | Nome tratado | Tipo tratado |
|---|---|---|
| Sigla ICAO Empresa Aérea | `companhia_icao` | TEXT |
| Empresa Aérea | `companhia_nome` | TEXT |
| Número Voo | `numero_voo` | TEXT |
| Código DI | `codigo_di` | TEXT |
| Código Tipo Linha | `tipo_linha` | TEXT |
| Modelo Equipamento | `modelo_equipamento` | TEXT |
| Número de Assentos | `numero_assentos` | INTEGER NULL |
| Sigla ICAO Aeroporto Origem | `aeroporto_origem` | TEXT |
| Descrição Aeroporto Origem | `descricao_origem` | TEXT |
| Partida Prevista | `partida_prevista` | TIMESTAMP NULL na camada tratada; obrigatória na Fato |
| Partida Real | `partida_real` | TIMESTAMP NULL |
| Sigla ICAO Aeroporto Destino | `aeroporto_destino` | TEXT |
| Descrição Aeroporto Destino | `descricao_destino` | TEXT |
| Chegada Prevista | `chegada_prevista` | TIMESTAMP NULL na camada tratada; obrigatória na Fato |
| Chegada Real | `chegada_real` | TIMESTAMP NULL |
| Situação Voo | `situacao_voo` | TEXT |
| Justificativa | `justificativa` | TEXT NULL |
| Referência | `referencia` | DATE NULL |
| Situação Partida | `situacao_partida` | TEXT NULL |
| Situação Chegada | `situacao_chegada` | TEXT NULL |

Regras aplicadas:

- Códigos ICAO, `codigo_di`, `tipo_linha`, `modelo_equipamento` e campos de situação: remover espaços externos e converter para maiúsculas.
- Nome de companhia, descrições de aeroportos e justificativa: remover espaços externos, preservando grafia e capitalização.
- Demais textos: remover espaços externos e preservar o conteúdo; `numero_voo` continua texto, mantendo zeros à esquerda.
- Texto vazio ou contendo apenas espaços: `NULL` na camada tratada.
- Não remover acentos, completar códigos, inventar descrições ou preencher horários ausentes.
- `numero_assentos`: aceitar somente inteiro não negativo; valor preenchido inválido vira `NULL` e é registrado como anomalia, sem rejeição por esse motivo.

## 5. Deduplicação e auditoria

A deduplicação é realizada sobre os **20 campos originais brutos**, antes da normalização. `arquivo_origem`, `linha_origem` e metadados não participam da comparação.

A ordenação é estável: nome do arquivo em ordem crescente e, dentro dele, `linha_origem` crescente. A primeira ocorrência do grupo é a representante. As demais são excedentes excluídas da camada analítica.

O arquivo `vra_duplicatas_excluidas.csv.gz` registra cada excedente com os 20 valores originais, `ano_origem`, `arquivo_origem`, `linha_origem`, identificador do grupo, quantidade de ocorrências e arquivo/linha da ocorrência representante. Também são anexados motivos diagnósticos de validação para permitir medir a interseção duplicatas × inválidos.

O contrato também determina que possíveis duplicidades que só aparecem depois de `TRIM`/`UPPER` sejam informadas, sem exclusão adicional. Por isso, `vra_possiveis_duplicatas_padronizacao.csv.gz` sinaliza os grupos que ficam iguais depois dessas operações. Esses registros continuam na camada tratada e na Fato, caso sejam elegíveis.

A validação diagnóstica das ocorrências excedentes existe apenas para medir a interseção com inválidos. A rejeição analítica é contada sobre o conjunto deduplicado, evitando subtrair a mesma linha duas vezes.

## 6. Rejeições, anomalias e campos obrigatórios

Uma linha só entra na Fato quando tiver valor válido em todos os cinco campos obrigatórios definidos na seção 6 do contrato:

1. `companhia_icao`;
2. `aeroporto_origem`;
3. `aeroporto_destino`;
4. `partida_prevista`;
5. `chegada_prevista`.

Ausência de campo obrigatório ou data prevista preenchida inválida gera rejeição com todos os motivos identificados. A linha continua preservada na camada bruta. A tabela/arquivo de rejeições contém os valores canônicos, proveniência, `motivo_rejeicao` e uma cópia dos valores originais com prefixo `bruto__`.

Campos opcionais não causam rejeição por si só: horários reais, justificativa, equipamento, código DI, assentos, `numero_voo`, `tipo_linha`, situação e `referencia`. Data real inválida, `referencia` inválida e número de assentos inválido são registrados em `vra_anomalias.csv.gz`; os valores tratados são nulos. O relatório de anomalias também conserva os valores de origem com prefixo `bruto__`.

`REALIZADO`, `CANCELADO` e `NÃO INFORMADO` são preservados como categorias distintas. Um horário real nulo não é interpretado como cancelamento.

## 7. Métricas temporais

Quando ambos os horários existem:

- `diferenca_partida_min = partida_real - partida_prevista`, em minutos e com sinal;
- `diferenca_chegada_min = chegada_real - chegada_prevista`, em minutos e com sinal;
- `atraso_partida_min = max(diferenca_partida_min, 0)`;
- `atraso_chegada_min = max(diferenca_chegada_min, 0)`.

Quando o horário real não existe ou não é válido, a diferença e o atraso ficam `NULL`, não zero.

São geradas `partida_atipica_flag` e `chegada_atipica_flag` quando o valor absoluto da diferença supera 1.440 minutos. Quando a diferença não pode ser calculada, a flag fica `FALSE`. Os valores atípicos são sinalizados, não corrigidos, truncados ou removidos.

`partida_ano_diverge_flag` registra quando o ano de `partida_prevista` difere de `ano_origem` (2019). O registro não é excluído por essa diferença. Nenhuma conversão de fuso horário é aplicada.

## 8. Esquema estrela

A granularidade da Fato é uma etapa de voo elegível, depois da exclusão das ocorrências excedentes exatas e da aplicação das regras de campos obrigatórios.

Dimensões geradas:

- `dim_tempo`;
- `dim_companhia_aerea`;
- `dim_aeroporto`;
- `dim_situacao_voo`;
- `dim_justificativa`;
- `dim_tipo_linha`;
- `dim_equipamento`.

As chaves técnicas são criadas no ETL. `dim_justificativa` e `dim_equipamento` têm membro de chave 0 com valor `DESCONHECIDO` para ausências. `id_situacao` e `id_tipo_linha` podem ser nulos quando a categoria não estiver presente, pois esses campos não fazem parte dos cinco obrigatórios. Os códigos ICAO são as chaves naturais de companhia e aeroporto.

Conflitos de descrição para o mesmo código natural são exportados para `conflitos_dimensoes.csv` e interrompem a publicação da dimensão, evitando escolha arbitrária. A Fato não recebe as flags de duplicata; elas permanecem nas auditorias.

## 9. Saídas geradas

Na pasta `dados/processados/2019/`:

| Saída | Conteúdo |
|---|---|
| `vra_bruta/` | Cópias byte a byte dos 12 CSVs e manifesto SHA-256 |
| `vra_tratada.csv.gz` | Registros válidos, únicos por igualdade bruta exata, com nomes canônicos e métricas |
| `fato_voo.csv.gz` | Fato com chaves técnicas, atributos, métricas e proveniência |
| `vra_duplicatas_excluidas.csv.gz` | Ocorrências excedentes de duplicatas exatas e referência à representante |
| `vra_possiveis_duplicatas_padronizacao.csv.gz` | Possíveis duplicidades somente após trim/upper; não são excluídas |
| `vra_rejeicoes.csv.gz` | Representantes rejeitados, motivos, proveniência e valores originais |
| `vra_anomalias.csv.gz` | Anomalias não bloqueantes e valores originais |
| `dim_*.csv` | Exportação das sete dimensões |
| `resumo_qualidade.csv` / `etl_resumo.json` | Indicadores gerais, interseção e equação de conciliação |
| `etl_log_arquivos.csv` | Contagens e informações por arquivo mensal |
| `conflitos_dimensoes.csv` | Conflitos de descrição, quando encontrados |

Com a carga PostgreSQL habilitada, o schema padrão é `dw_etl` e contém também `vra_bruta`, `vra_tratada`, `vra_duplicatas_excluidas`, `vra_possiveis_duplicatas_padronizacao`, `vra_rejeicoes`, `vra_anomalias`, `resumo_qualidade`, `log_carga_arquivo`, dimensões e Fato.

## 10. Execução

Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

Crie o banco `vra_dw_2019` no PostgreSQL/pgAdmin antes da primeira carga. Configure um arquivo `.env` na raiz do projeto, usando `.env.example` como modelo. Exemplo de variáveis:

```dotenv
PGHOST=localhost
PGPORT=5432
PGDATABASE=vra_dw_2019
PGUSER=postgres
PGPASSWORD=sua_senha_local
PGSCHEMA=dw_etl
```

A partir da raiz do projeto:

```powershell
python etl_vra_anac_2019.py --input-dir "dados/brutos/2019" --output-dir "dados/processados/2019"
```

Para testar apenas a transformação e gerar os arquivos, sem PostgreSQL:

```powershell
python etl_vra_anac_2019.py --input-dir "dados/brutos/2019" --output-dir "dados/processados/2019" --skip-db
```

Por segurança, uma carga não substitui tabelas já existentes. Para apagar e recriar somente as tabelas ETL listadas no schema configurado, use `--replace` conscientemente:

```powershell
python etl_vra_anac_2019.py --input-dir "dados/brutos/2019" --output-dir "dados/processados/2019" --replace
```

O notebook [etl_2019.ipynb](../notebooks/etl/etl_2019.ipynb) executa o mesmo `run_etl` e apresenta as etapas de conferência.

## 11. Testes realizados nesta entrega

Foram realizados testes locais com arquivos CSV sintéticos, contendo 12 arquivos mensais (alguns sem registros) e casos preparados para validar as regras. O teste verificou:

- duplicata exata entre dois meses é reduzida a uma representante;
- registros que só ficam iguais após remover espaços/maiúsculas são sinalizados, mas continuam no resultado;
- os cinco campos obrigatórios definem a rejeição;
- horário real inválido, referência inválida e assentos negativos geram anomalias, não rejeição por si só;
- zeros à esquerda de `numero_voo` permanecem no CSV exportado;
- a cópia bruta é idêntica ao arquivo de origem;
- a equação de conciliação fecha.

**Resultado do teste sintético:** 5 registros brutos, 1 ocorrência excedente removida, 1 registro rejeitado e 3 registros na Fato; 1 grupo exato repetido; 2 linhas sinalizadas como possíveis duplicatas após trim/upper e mantidas; conciliação aprovada. Esses valores são exclusivamente do conjunto sintético de teste, não dos CSVs reais da ANAC.

Também foi executado `python -m py_compile` no script. A estrutura do notebook foi validada como JSON e as células Python foram verificadas quanto à sintaxe, desconsiderando as linhas de instalação `%pip`.

Foi executado um segundo cenário sintético específico para a interseção: uma linha inválida repetida exatamente em dois meses e uma linha válida adicional. O teste confirmou que a excedente inválida fica na auditoria de duplicatas, a representante inválida é contada uma única vez em rejeições e a equação não subtrai a linha duas vezes. Um cenário com todos os representantes rejeitados também foi testado para confirmar que as auditorias ainda são geradas com a Fato vazia.

**Ainda não foi executado nesta entrega:** o processamento dos 12 CSVs reais e a conexão/carga no PostgreSQL do computador do usuário. Portanto, nenhum número final de 2019 é declarado como resultado medido desta versão.

## 12. Referências de contagem do contrato e conciliação real pendente

A seção 10 do contrato v1.1 apresenta referências da exploração de 2019: 983.414 linhas brutas, 914 linhas envolvidas em duplicatas exatas, 444 grupos repetidos e 470 ocorrências excedentes. A deduplicação levaria a 982.944 linhas antes das rejeições. O contrato indica até 18 rejeições e 982.926 linhas na Fato como estimativa sujeita à interseção.

Esses números são referências para conferência, não valores impostos pelo script. A implementação atual recalcula todos os indicadores a partir dos arquivos efetivamente fornecidos. A equação que deve fechar é:

```text
linhas brutas = ocorrências excedentes excluídas
              + rejeições remanescentes após deduplicação
              + linhas elegíveis carregadas na Fato
```

A interseção entre excedentes duplicados e inválidos é apresentada separadamente em `intersecao_excedentes_duplicados_invalidos`, evitando dupla subtração.

## 13. Observação operacional

Para aplicar a regra de duplicidade global entre os 12 meses, o script concatena os arquivos do ano em memória durante o processamento. A execução deve ser feita em uma máquina com memória disponível suficiente para o conjunto completo e as estruturas intermediárias do Pandas. A cópia bruta é feita em blocos para calcular os hashes sem carregar o arquivo inteiro de uma vez.

## 14. Pendências antes da publicação

1. Executar o notebook ou script com os 12 CSVs reais de 2019.
2. Conferir `etl_resumo.json`, `resumo_qualidade.csv`, `vra_duplicatas_excluidas.csv.gz` e `vra_rejeicoes.csv.gz` contra as referências do contrato.
3. Executar a carga PostgreSQL e verificar as contagens e `foreign_key_orphans = 0`.
4. Resolver eventuais conflitos de descrição ICAO antes da publicação.
5. Confrontar amostras e totais com o ELT 2019 e registrar a conciliação do grupo.
6. Manter a investigação de fuso horário, semântica de `referencia` e limiar de pontualidade como pendências do grupo; o script não presume respostas para essas questões.

---

**Conclusão:** a implementação foi ajustada para a política v1.1, incluindo deduplicação bruta exata, auditoria de excedentes, sinalização separada de possíveis duplicidades após trim/upper, rejeições pelos cinco campos obrigatórios, métricas temporais, anomalias e preservação da origem. A aceitação final depende da execução com os arquivos reais e da conciliação com o pipeline ELT.
