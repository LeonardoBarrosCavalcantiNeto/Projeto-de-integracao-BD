# Relatório técnico — ETL VRA/ANAC 2021

**Responsável ETL:** Arthur. **Responsável ELT:** Murilo Acioli.
**Contrato:** VRA/ANAC 2019–2021, versão 1.1.
**Escopo:** camada tratada, auditorias, rastreabilidade e carga PostgreSQL opcional.
Dimensões e Fato serão integradas coletivamente.

## Resultado medido

| Etapa | Registros |
|---|---:|
| Extração bruta | 632.148 |
| Excedentes de duplicação exata | 0 |
| Rejeitados após deduplicação | 25.511 |
| Tratados | 606.637 |
| Excedentes inválidos, apenas diagnóstico | 0 |

A conciliação anual e as 12 conciliações mensais passaram:
**bruta = excedentes + rejeições + tratada**. Os números de referência são
comparados ao resultado, sem impor contagens ao processamento.
Os 25.511 rejeitados apresentam ausência dos dois horários previstos; cada
registro guarda os dois motivos. Isso não transforma 25.511 rejeições em 51.022.

As evidências locais versionadas foram geradas com IPython e Python da `.venv`.
O notebook atual tem nove células de código e prepara também uma sessão Colab.
Arthur compartilhou as saídas de uma execução hospedada em 17/11/2026:
PostgreSQL 16.15, commit `e910c58`, dez contagens confirmadas após COMMIT,
origens únicas e conciliação mensal aprovadas. O notebook executado e os quatro
arquivos de evidências dessa sessão ainda precisam ser incorporados à entrega;
nenhum arquivo de execução local é apresentado como evidência do Colab.

## Extração e preservação

`scripts/etl_vra_anac_2021.py` concentra a implementação; o notebook apenas
configura, executa e apresenta evidências. `run_etl()` mantém sua assinatura.

A leitura exige exatamente os 12 nomes mensais de 2021. São aceitos os 20 campos
comuns, na ordem do contrato, ou esses mesmos campos seguidos de `Codeshare`.
Mês com apenas cabeçalho é válido. Arquivo sem cabeçalho, cabeçalho divergente,
registro incompleto e registro com campos excedentes provocam falha.
A leitura por `csv.reader` e a leitura pelo Pandas precisam conciliar.

Os 12 CSVs são copiados byte a byte para `vra_bruta/`, com verificação dos hashes
antes e depois. `manifesto_sha256.csv` registra os hashes dos originais e das
cópias. `--export-raw` produz adicionalmente `vra_bruta.csv.gz`, uma representação
tabular regenerada com metadados; ela não substitui os originais.

`Codeshare` existe em janeiro, fevereiro, março, julho, setembro, novembro e
dezembro; soma 112.479 valores preenchidos. Trata-se de uma variação de esquema
preservada e auditada. A simples presença dessa coluna não demonstra deslocamento
das demais: larguras e contagens dos arquivos foram verificadas. Ela não compõe
os 20 atributos comuns usados no tratamento.

## Deduplicação e auditoria

A chave de duplicação são os 20 campos **brutos**, antes de TRIM, UPPER ou conversão.
Preserva-se a primeira origem em ordem estável por arquivo e registro lógico.
`Codeshare` e metadados não participam dessa comparação.

Cada excedente registra `grupo_duplicata_id`, `quantidade_ocorrencias`,
`arquivo_preservado`, `linha_preservada`, `invalido_diagnostico` e
`motivo_rejeicao_diagnostico`. O identificador é determinístico para a mesma
entrada ordenada; não é uma chave dimensional permanente. A quantidade inclui
o representante. A interseção dos excedentes com inválidos é apenas diagnóstica;
não entra novamente como rejeição na equação.

`vra_possiveis_duplicatas_padronizacao.csv.gz` reúne registros que ficam iguais
após TRIM/UPPER. Eles são preservados. A auditoria adicional após conversão
continua em `duplicatas_apos_padronizacao.csv.gz`. Nenhuma das duas remove linhas.
No conjunto real, as duas contagens de excedentes potenciais são zero.

## Transformações e rastreabilidade

- Vazios tornam-se nulos e espaços externos são removidos. Códigos e situações
  ficam em maiúsculas; nomes e descrições preservam a grafia.
- `numero_voo` permanece texto, inclusive com zeros à esquerda.
- Os quatro horários aceitam `dd/mm/aaaa HH:MM` com validação de calendário.
  A precisão em microssegundos preserva anos válidos fora do intervalo de
  timestamps em nanossegundos. Nenhuma conversão de fuso é aplicada aos voos.
- `referencia` aceita `aaaa-mm-dd` ou `dd/mm/aaaa 00:00:00`.
- Assentos aceitam somente inteiros não negativos no intervalo de inteiro de 32 bits.
- Somente companhia ICAO, aeroportos de origem e destino e os dois horários
  previstos são obrigatórios. Cada rejeição guarda **todos** os motivos.
- Opcionais inválidos tornam-se nulos e geram anomalias por campo; não rejeitam
  sozinhos o registro. Referências fora do ano também são auditadas.

Rejeições e anomalias incluem os campos canônicos e o retrato original com
prefixo `bruto__` e nomes canônicos, por exemplo `bruto__partida_prevista`.
A presença de Codeshare na fonte também é preservada. `motivo_rejeicao` é uma
lista JSON no CSV e um array de texto no PostgreSQL. Anomalias identificam
`campo`, `campo_original`, `valor_original` e `motivo`.

Cada registro carrega `arquivo_origem`, `linha_origem`, `ano_origem`,
`data_carga` UTC, `pipeline=ETL` e `versao_contrato=1.1`. `linha_origem` conta
registros lógicos do CSV, com cabeçalho na posição 1. `etl_log_arquivos.csv`
reúne hashes, contagens, diagnóstico e conciliação por mês.

## Métricas e casos preservados

Para partida e chegada, diferença em minutos é **real − prevista**;
atraso é `max(diferença, 0)`. Sem horário real, ambas as métricas permanecem
nulas. A flag atípica é verdadeira somente para diferença absoluta **maior**
que 1.440 minutos; sem real, a flag é falsa.

Foram preservadas 371 partidas e 373 chegadas atípicas. Há 26.139 partidas
reais nulas e 26.141 chegadas reais nulas. São 15 partidas previstas fora de
2021, preservadas com `partida_ano_diverge_flag=True` e também exportadas na
auditoria própria. Não há ocorrências na auditoria de opcionais nesta execução.

## Conflitos de descrição

Nove códigos apresentam duas descrições cada, totalizando 18 variantes:

| Tipo | Códigos |
|---|---|
| Aeroporto | KAEX, SWHP, SYEC |
| Companhia | CQB, DTA, ETH, ETR, OWT, QTR |

A auditoria combina os papéis de origem e destino dos aeroportos e contabiliza
as ocorrências de cada descrição. Nenhum nome foi escolhido arbitrariamente.
A resolução deve ser coletiva antes da publicação das dimensões.
As variantes estão em `resultados/validacoes/conflitos_codigo_etl_2021.csv`.

## PostgreSQL

A carga recebe as dez tabelas já preparadas em Python. Usa exclusivamente o
schema `etl_2021`, verifica contagens e cria chaves primárias de origem onde
cada registro deve ser único. O log tem chave pelo arquivo. Anomalias podem
conter vários campos do mesmo voo e, por isso, repetem a origem legitimamente.

Sem substituição explícita, a presença de qualquer tabela deste pipeline bloqueia
a carga. Com substituição, remoção e recriação ocorrem na mesma transação.
Uma falha reverte a transação e preserva a carga anterior. O status só informa
sucesso após o COMMIT; cada chamada reinicializa o status e os metadados para
não reaproveitar sucesso antigo. Falhas registram o tipo do erro, sem credenciais.

Os testes de integração foram executados em PostgreSQL 17 real, num contêiner
Docker temporário isolado. Cobrem contagens, repetição bloqueada, substituição,
rollback após falha injetada e tipos das auditorias não vazias. A carga completa
também é registrada na evidência PostgreSQL, com contagens consultadas após o
COMMIT. Esse banco temporário não é o banco compartilhado da entrega.

No notebook, a carga fica desabilitada por padrão na execução local e habilitada
no Colab. A instalação automática do PostgreSQL exige uma sessão hospedada.
Os testes locais de integração usam um banco temporário separado.

## Testes e comparação com ELT

A suíte usa `unittest`, sem dependência nova. Execute
`python -m unittest discover -s tests -v`. Os seis testes de integração PostgreSQL exigem
`ETL_2021_TEST_DATABASE_URL` para um banco dedicado `etl_test` ou `etl_2021_test`;
sem essa variável são explicitamente pulados. O README descreve a configuração.

O comparador verifica hashes dos 12 arquivos e presença e valores por
`arquivo_origem + linha_origem`, sem presumir equivalência por totais.
Compara os 20 atributos canônicos, ano, quatro métricas e três flags.
Normaliza datas, números, booleanos e marcadores de nulo; nulo continua
diferente de zero e `0035` continua diferente de `35`. Se a flag anual não vier
no ELT, deriva-a de partida prevista e ano de origem, registrando essa decisão.
`data_carga`, `pipeline` e `versao_contrato` não entram na igualdade dos valores.
O SQLite temporário evita manter as duas bases completas na RAM.

Os testes do comparador cobrem valores divergentes com totais iguais, hashes
diferentes, nulo versus zero, normalização, origens ausentes, origens repetidas e
campos ausentes. A regressão antes/depois usa somente a própria base ETL anterior;
ela **não** comprova equivalência com o ELT do Murilo.

**Inventários conferidos:** o inventário do ELT foi recuperado do commit
`b6c6b463e0eadb76be86a72415d3eb288610d0d0`, referência `origin/integracao-elt`, sem
trocar de branch ou fazer merge. Os arquivos de ELT 2021 examinados também são
iguais aos da `origin/main` consultada. Nos 12 meses, SHA-256, tamanho em bytes e
quantidade de registros coincidem com o inventário do ETL.

`comparacao_etl_elt_2021.json` registra o commit de origem, os hashes dos dois
inventários e a conferência por mês. Os metadados incluem o horário dessa
verificação posterior, preservando os horários da execução original do ETL.

**Comparação dos valores com Murilo: pendente.** A tabela tratada completa não
está versionada nas branches examinadas. O notebook dele contém
`EXPORTAR_TRATADA_COMPLETA=False`. É preciso obter a exportação completa ou
reproduzir o ELT num banco isolado, identificando essa saída como reprodução
local. A igualdade dos inventários e dos totais não fecha a comparação por
registro; essa etapa continua explicitamente pendente no JSON.

## Pendências de fechamento

1. Obter a tabela tratada completa do ELT e executar o comparador por origem e
   valores; o inventário com hashes já foi obtido e conferido.
2. Incorporar e conferir o notebook executado e o ZIP de evidências da sessão
   Colab cujas saídas foram compartilhadas por Arthur. O relato confirma a carga;
   os artefatos completos da reprodução ainda não foram incorporados.
3. Resolver os nove conflitos e integrar dimensões e Fato com o grupo.
4. Revisar a integração com a `main` e a mensagem do commit antes da publicação.
   A branch original `feat/etl-2021` mantém os commits individuais de Arthur.

A comparação dos valores com o ELT e a incorporação das evidências completas
do Colab continuam pendentes. As saídas compartilhadas da sessão hospedada
não substituem o arquivamento dos artefatos dessa execução.
