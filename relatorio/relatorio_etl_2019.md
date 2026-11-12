# Relatório do processo ETL — VRA/ANAC 2019

**Status deste documento:** versão revisada do processo ETL. A execução definitiva no PostgreSQL deve ser realizada no ambiente do projeto; os números finais serão registrados em `dados/processados/2019/etl_resumo.json`.

## 1. Escopo e objetivo

Este artefato implementa a parte ETL referente exclusivamente ao ano de 2019, a partir dos 12 arquivos CSV mensais do conjunto Voo Regular Ativo (VRA), disponibilizado pela Agência Nacional de Aviação Civil (ANAC). O objetivo é transformar os dados para um formato consistente, validar os registros, construir um Data Warehouse em esquema estrela e carregar o resultado no PostgreSQL.

O projeto da disciplina prevê a integração de três períodos (2019, 2020 e 2021) e a comparação entre ETL e ELT. Portanto, este relatório não apresenta a etapa de 2019 como integração final dos três anos nem como implementação de ELT.

## 2. Fontes e ingestão

O pipeline espera os arquivos `VRA_2019_01.csv` a `VRA_2019_12.csv`, todos na pasta de entrada. O formato esperado é CSV com separador `;`, codificação UTF-8 e os 20 campos originais definidos no contrato de dados.

As colunas são lidas inicialmente como texto. Essa decisão preserva códigos e identificadores, especialmente `Número Voo`, que permanece como `TEXT` para conservar zeros à esquerda. Os arquivos de origem não são alterados.

A primeira exploração do conjunto registrou 983.414 linhas nos 12 arquivos. Essa contagem é uma referência da inspeção anterior; a execução atual registra novamente a quantidade efetivamente lida no arquivo `etl_resumo.json`.

## 3. Transformações aplicadas

1. **Mapeamento canônico:** os 20 campos originais são renomeados para os nomes definidos no contrato, como `companhia_icao`, `numero_voo`, `partida_prevista` e `referencia`.
2. **Padronização textual:** remoção de espaços externos, conversão de texto vazio em `NULL`, códigos ICAO em maiúsculas e categorias controladas em maiúsculas.
3. **Número do voo:** o campo `numero_voo` é mantido como texto; não é convertido para inteiro.
4. **Datas e horários:** os quatro timestamps são interpretados no formato `DD/MM/AAAA HH:MM`, e `referencia` no formato `AAAA-MM-DD`. Valores inválidos são enviados para rejeições com o motivo correspondente.
5. **Número de assentos:** conversão para inteiro anulável. Valores não numéricos ou fracionários são rejeitados; ausências permanecem nulas.
6. **Atrasos e antecipações:** `diferenca_partida_min` e `diferenca_chegada_min` são calculadas como horário real menos previsto, em minutos e com sinal. As medidas `atraso_*_min` são limitadas inferiormente a zero. Quando o horário real não existe, as medidas permanecem `NULL`.
7. **Fuso horário:** não é aplicada conversão de fuso, pois a convenção temporal precisa ser confirmada na documentação da fonte.
8. **Situação do voo:** `REALIZADO`, `CANCELADO` e `NÃO INFORMADO` permanecem categorias distintas. Cancelamentos não são excluídos; ausência de horário real não é tratada como prova de cancelamento.
9. **Proveniência:** são preservados `ano_origem`, `arquivo_origem`, `linha_origem`, `data_carga` e `pipeline` nas camadas de auditoria/staging. A fato mantém ano, arquivo e linha de origem.

## 4. Deduplicação e rejeições

### 4.1 Regra de deduplicação adotada

A regra foi alterada em relação à primeira versão do pipeline. Agora, a deduplicação é executada **depois da padronização**, comparando os 20 atributos canônicos em conjunto e considerando os 12 arquivos mensais como uma única entrada.

Quando todas as 20 colunas padronizadas coincidem, a primeira ocorrência (pela ordem dos arquivos mensais e pela ordem física da linha) é mantida e as ocorrências excedentes são removidas da carga da fato. A trilha dos registros removidos é exportada em `duplicatas_removidas.csv.gz`. A staging mantém todas as linhas e identifica o status `DUPLICATA_REMOVIDA`, preservando arquivo e linha de origem.

Essa regra não usa a combinação companhia + número do voo + partida prevista como chave única de negócio. A decisão é baseada na igualdade dos 20 atributos do contrato após normalização.

**Atenção ao contrato do grupo:** a versão 0.1 do contrato de dados registrava que duplicatas não deveriam ser removidas automaticamente. Como a decisão do grupo foi alterada, o contrato compartilhado precisa ser atualizado para a versão seguinte, registrando esta regra e sua justificativa.

### 4.2 Registros rejeitados

Registros com campos obrigatórios ausentes, datas inválidas, datas previstas ausentes ou número de assentos inválido são enviados para `rejeicoes.csv.gz`. O arquivo inclui os identificadores de proveniência e os motivos de rejeição. Registros rejeitados não entram na tabela fato.

## 5. Modelagem dimensional

O grão de `fato_voo` é uma ocorrência de voo da fonte que passou pelas regras de validação e deduplicação. `id_voo` é uma chave técnica gerada pelo ETL; não é um identificador original da ANAC.

A carga cria as seguintes dimensões:

- `dim_tempo`: data, ano, trimestre, mês, dia e dia da semana. É referenciada pelos papéis de partida prevista e chegada prevista.
- `dim_companhia_aerea`: companhia identificada pelo código ICAO.
- `dim_aeroporto`: aeroporto identificado pelo código ICAO, compartilhado entre origem e destino.
- `dim_situacao_voo`: situação do voo.
- `dim_justificativa`: justificativa, com membro técnico `DESCONHECIDO` (chave 0) para ausências.
- `dim_tipo_linha`: classificação do tipo de linha.
- `dim_equipamento`: modelo do equipamento, com membro técnico `DESCONHECIDO` (chave 0) para ausências.

A tabela `fato_voo` contém as chaves estrangeiras das dimensões, os atributos operacionais, os horários previstos e reais, as medidas de diferença/atraso, `quantidade_voos = 1` e a proveniência.

## 6. Destino e carga no PostgreSQL

O destino esperado é o banco PostgreSQL `vra_dw_2019`, no schema `dw_etl` (configurável). O script cria as tabelas dimensionais, a fato, a tabela de rejeições e o log por arquivo. Também cria índices para consultas por referência, tempo de partida, companhia, situação e rota.

O script não cria o banco de dados PostgreSQL. Antes da execução, o banco `vra_dw_2019` deve existir e as credenciais devem estar configuradas em um arquivo `.env` local ou em variáveis de ambiente. A senha não deve ser incluída no código ou no GitHub.

Por segurança, o script não substitui tabelas já existentes por padrão. Para refazer uma carga no mesmo schema, é necessário usar explicitamente `--replace`; essa opção apaga e recria as tabelas ETL desse schema.

## 7. Saídas e indicadores da execução

O pipeline gera os seguintes arquivos na pasta de saída:

| Arquivo/pasta | Conteúdo |
|---|---|
| `staging/` | 12 partições mensais padronizadas, com proveniência e status de tratamento |
| `fato_voo.csv.gz` | Exportação da tabela fato |
| `dim_*.csv.gz` | Exportações das sete dimensões |
| `rejeicoes.csv.gz` | Registros rejeitados e seus motivos |
| `duplicatas_removidas.csv.gz` | Ocorrências excedentes removidas na deduplicação |
| `etl_log_arquivos.csv` | Contagens e auditoria por CSV mensal |
| `qualidade_colunas.csv` | Nulos por coluna na staging |
| `conflitos_dimensoes.csv.gz` | Divergências de descrição por chave natural, quando encontradas |
| `etl_resumo.json` | Resumo final da execução, dimensões, contagens e status da carga PostgreSQL |

Os valores finais de linhas lidas, duplicatas removidas, rejeições, registros carregados e contagens dimensionais devem ser copiados do `etl_resumo.json` produzido pela execução no ambiente do projeto. Não são repetidos aqui os resultados da versão anterior em SQLite, pois ela preservava duplicatas e usava uma regra diferente.

## 8. Verificações realizadas nesta revisão

- Compilação sintática do script Python (`py_compile`): concluída sem erro.
- Teste funcional com CSVs sintéticos: confirmou a remoção de uma duplicata exata distribuída entre dois meses, a preservação da primeira ocorrência, a geração de uma rejeição por data prevista ausente e a carga das linhas válidas para os arquivos tabulares.
- O teste sintético foi executado com `--skip-db`; portanto, ele valida o tratamento e as exportações, mas **não equivale a uma execução da base real de 2019 nem a uma validação de conexão com o PostgreSQL local do usuário**.

## 9. Reprodução no Windows / VS Code

1. Instalar as dependências listadas em `requirements.txt` em um ambiente virtual.
2. Criar o banco `vra_dw_2019` no PostgreSQL.
3. Copiar `.env.example` para `.env` e informar a senha local do PostgreSQL em `PGPASSWORD`.
4. Colocar os 12 CSVs em `dados/brutos/2019/`.
5. Executar a partir da raiz do projeto:

```powershell
python etl_vra_anac_2019.py --input-dir "dados/brutos/2019" --output-dir "dados/processados/2019"
```

Para refazer uma carga já existente no schema `dw_etl`, executar explicitamente:

```powershell
python etl_vra_anac_2019.py --input-dir "dados/brutos/2019" --output-dir "dados/processados/2019" --replace
```

Para testar apenas o processamento e as exportações, sem conexão ao PostgreSQL:

```powershell
python etl_vra_anac_2019.py --input-dir "dados/brutos/2019" --output-dir "dados/processados/2019" --skip-db
```

O notebook `etl_vra_anac_2019.ipynb` chama o mesmo script para evitar que existam duas implementações diferentes da regra ETL.

## 10. Limitações e próximas etapas

1. Executar o pipeline completo com os 12 CSVs reais e registrar os indicadores finais no relatório após consultar `etl_resumo.json`.
2. Atualizar o contrato de dados do grupo para refletir formalmente a deduplicação aprovada.
3. Conferir os cabeçalhos, formatos e domínios de 2020 e 2021 antes da integração dos anos.
4. Confirmar, com documentação da fonte, a convenção de fuso horário e a semântica da coluna `referencia`.
5. Implementar o pipeline ELT separadamente, com camada RAW e transformações SQL no banco.
6. Reconciliar ETL e ELT e consolidar análises dos três anos para a entrega final do grupo.

### Observação sobre Google Colab

O notebook pode ser aberto no Colab, mas uma instância Colab não consegue acessar automaticamente o PostgreSQL instalado em `localhost` no computador do usuário. Para executar a carga a partir do Colab, é necessário um PostgreSQL acessível pela rede (por exemplo, uma instância remota configurada para esse uso) e credenciais armazenadas nos Secrets do Colab. Para a instalação PostgreSQL local, execute o notebook no VS Code/Jupyter local.
