# ELT VRA no PostgreSQL / DataGrip

Organização dos pacotes de 2019 na branch `integracao-elt`. Este guia prevalece sobre os caminhos e o estado histórico descritos nos READMEs originais copiados em `2019/`. Nenhum SQL foi executado nesta organização.

## Estrutura e origem

- `../database/00_schemas.sql`: schemas compartilhados `raw`, `staging` e `dw` (original integral).
- `../database/07_dw_schema.sql`: original histórico que repete a criação de `dw`; dispensável na sequência abaixo. Seu comentário sobre DW não implementado é anterior ao segundo ZIP.
- `../database/10_criacao_dw.sql`: somente as oito definições de tabelas do pacote DW, na ordem original (sete dimensões e fato), sem carga nem dependência da staging.
- `2019/01_raw.sql` a `2019/06_vra_tratada.sql`: criação da RAW anual, funções, transformação, deduplicação, rejeições e métricas; originais integrais.
- `2019/09_corrigir_atrasos_nulos.sql`: correção histórica opcional, preservada integralmente, fora da reprodução nova.
- `2019/10_carga_dw_2019.sql`: pré-validações, cargas dimensionais e carga da fato originais; apenas DDL, schema e resumo final foram deslocados.
- `../validacoes/08_validacao.sql`, `10_resumo_carga_dw_2019.sql` e `11_validacao_dw_2019.sql`: consultas de conferência.
- `2019/README_ORIGINAL_ELT.md`, `README_ORIGINAL_DW.md` e `IMPORTACAO_DATAGRIP_ORIGINAL.md`: documentação histórica integral; caminhos relativos nela apontam para a organização dos ZIPs.
- `2019/PROVENIENCIA.json`: correspondência de arquivos e SHA-256 das fontes; registra a separação do DW.
- `2020/.gitkeep` e `2021/.gitkeep`: somente reserva de diretórios, sem implementação SQL.

Fontes preservadas na raiz: `VRA_ELT_2019_scripts_GitHub.zip` e `VRA_DW_2019_scripts_GitHub.zip`. Extração de análise realizada em área temporária, fora do repositório. Não foi criada uma segunda cópia monolítica de `10_dw_2019.sql`: o original permanece no ZIP.

Os arquivos `sql/criacao_dw.sql`, `sql/carga_dimensoes.sql` e `sql/carga_fato.sql`, citados no README da raiz, não existem nesta cópia de trabalho. Não havia definições nesses caminhos para reutilizar ou comparar. `sql/transformacoes/elt_2020.sql` e `elt_2021.sql` já existiam e foram preservados; não pertencem à sequência de 2019. As pastas `notebooks/sql/database/`, `elt/`, `validacoes/` e `transformacoes/` estavam vazias, sem arquivos ou links. Sua origem não pôde ser confirmada; foram mantidas, e nenhum script foi colocado nelas.

## Pré-requisitos e limites

Usar PostgreSQL com suporte a colunas identity (10 ou superior), PL/pgSQL disponível e uma conexão DataGrip para um banco de trabalho novo, com permissão de criar schemas, tabelas, funções e inserir/atualizar registros. O nome histórico é `anac_dw`; nenhum script cria o banco. Conferir manualmente a conexão ativa antes de executar cada etapa.

Disponibilizar os 12 CSVs originais de 2019, conferir cabeçalhos, codificação e volumes. Não usar dados já tratados na RAW. Não publicar credenciais.

A sequência reproduz o experimento original de 2019, com limitações documentadas abaixo; não é uma migração nem uma certificação de aderência ao contrato. Os scripts `04_deduplicacao.sql` e `05_rejeicoes.sql` contêm `DELETE` na staging, após arquivar as linhas. Foram preservados por exigência de fidelidade, mas NÃO executados nesta tarefa. A reprodução completa original implica essas operações; não executar essas etapas onde houver proibição de comandos destrutivos. Não foi criada uma variante com regras diferentes.

Os scripts de transformação usam `CREATE TABLE` e não são reexecutáveis sobre tabelas existentes. Não repetir importações. Não limpar tabelas para tentar reiniciar. Para repetir o experimento, providenciar outro banco de trabalho vazio. `CREATE TABLE IF NOT EXISTS` no DW não verifica nem adapta uma definição preexistente; se houver estrutura diferente, interromper e comparar colunas, tipos, chaves e granularidade com o grupo antes de preparar uma migração separada. Não escolher uma definição arbitrariamente nem executar os dois modelos juntos.

## Ordem de execução manual

Executar arquivos individualmente no console PostgreSQL do DataGrip, acompanhando erros; não executar toda a pasta automaticamente. Caminhos abaixo relativos à raiz do repositório.

| Ordem | Arquivo / ação | Dependência e resultado |
|---|---|---|
| 1 | `sql/database/00_schemas.sql` | Cria os três schemas compartilhados. |
| 2 | `sql/elt/2019/01_raw.sql` | Cria `raw.voos_2019`, sem carga. |
| 3 | Importação manual dos 12 CSVs | Preenche somente a RAW; ver instruções abaixo. |
| 4 | `sql/elt/2019/02_funcoes_staging.sql` | Cria três funções de conversão no schema staging. |
| 5 | `sql/elt/2019/03_criar_staging.sql` | Lê `raw.voos_2019`, cria `staging.vra_2019` com campos canônicos e flags. |
| 6 | `sql/elt/2019/04_deduplicacao.sql` | Classifica e arquiva excedentes em `staging.vra_duplicatas_excluidas`; contém remoção na staging. |
| 7 | `sql/elt/2019/05_rejeicoes.sql` | Recalcula motivos e arquiva em `staging.vra_rejeicoes`; contém remoção na staging. |
| 8 | `sql/elt/2019/06_vra_tratada.sql` | Materializa `staging.vra_tratada`, métricas e flags; preserva atraso NULL. |
| 9 | `sql/validacoes/08_validacao.sql` | Confere as camadas antes da carga dimensional. |
| 10 | `sql/database/10_criacao_dw.sql` | Cria sete dimensões e fato, sem popular. |
| 11 | `sql/elt/2019/10_carga_dw_2019.sql` | Valida fonte/conflitos, popula dimensões, verifica correspondências e carrega fato. |
| 12 | `sql/validacoes/10_resumo_carga_dw_2019.sql` e `sql/validacoes/11_validacao_dw_2019.sql` | Confere totais, relacionamentos, chaves, medidas e proveniência. |

O script `database/07_dw_schema.sql` é redundante após a etapa 1. `2019/09_corrigir_atrasos_nulos.sql` destina-se somente à versão antiga de uma tabela já existente: não é necessário após `06_vra_tratada.sql` deste pacote. Avaliar separadamente antes de qualquer uso; não aplica correções à fato já carregada.

A carga DW mantém os blocos originais de pré-validação antes dos INSERTs, inclusive a interrupção por descrições conflitantes. Os INSERTs reservados das chaves 0 ficaram na carga original. CTAS (`CREATE TABLE AS SELECT`) de staging e auditorias continuam junto das transformações: dependem dos dados, do ano e da estrutura produzida, e não são DDL compartilhado independente. `01_raw.sql` também permanece anual por criar explicitamente `raw.voos_2019`.

### Importação manual no DataGrip

1. Selecionar `raw.voos_2019` e usar **Import Data from File** para cada CSV, de janeiro a dezembro.
2. Configurar `;`, UTF-8 (conferir BOM), cabeçalho e mapeamento dos 20 campos originais para as colunas TEXT da RAW. Não converter tipos, normalizar espaços, descartar linhas ou deduplicar. Verificar que vazios e valores textuais foram preservados pelo importador.
3. Não mapear `id_raw`, gerado por identity. Anexar os meses à tabela existente, sem substituir dados. Registrar externamente quais arquivos já foram importados para evitar carga duplicada.
4. O procedimento histórico deixou `arquivo_origem` e `linha_origem` NULL. Isso reproduz uma limitação, não atende ao contrato. Para uma execução aderente, é necessário definir e revisar um mecanismo de captura do nome do CSV e do número do registro lógico (cabeçalho = 1); esse mecanismo não está implementado nos ZIPs e não foi inventado nesta organização.
5. Conferir `SELECT COUNT(*) FROM raw.voos_2019;` com a soma das linhas dos 12 arquivos antes de continuar.

## Resultados de referência e verificações

Os ZIPs relatam RAW = 983.414; excedentes = 470; rejeições = 18; tratada e fato = 982.926; partidas/chegadas atípicas = 684/690. São números históricos, não medidos nesta tarefa e não garantidos para outra entrada. Conferir a identidade `RAW = excedentes + rejeições remanescentes + tratada`, igualdade tratada/fato e zero problemas referenciais. A igualdade de contagens sozinha não prova equivalência de registros. As consultas originais não cobrem todos os critérios do contrato.

## Pendências técnicas, sem correção de regras

Referência examinada: `documentacao/Contrato_Tratamento_VRA_ANAC_2019_2021_ATUALIZADO.pdf`, versão 1.1 (11/11/2026).

- **Rastreabilidade:** arquivo e linha nulos no carregamento histórico são propagados até a fato. `id_raw` é local à carga e não substitui proveniência. Falta controle persistente de arquivos/lotes, versão do contrato e reconciliação por arquivo/ano (`resumo_qualidade` não é criado por estes pacotes).
- **Deduplicação:** compara os 20 atributos já padronizados, com desempate por `id_raw`. O contrato exige os 20 valores brutos exatos em todos os meses e ordenação estável por arquivo/linha. Normalização e conversões podem juntar valores originalmente distintos; contagens iguais não comprovam equivalência. Auditoria mantém campos canônicos e id_raw, mas depende da RAW para recuperar valores originais.
- **Rejeições:** reavaliar a interseção com duplicatas e reconciliar motivos por registro. O script 05 pode registrar ausência e invalidade juntas para a mesma data inválida. Não corrigido.
- **NULL e datas:** `06` e a carga da fato protegem atrasos com CASE; a correção histórica `09` não deve ser aplicada automaticamente. Validar separadamente zero versus ausência, comportamento de calendário/horário das funções, limites aceitos, overflow de assentos e flags de campos opcionais inválidos. Flags existem, mas não há tabela dedicada de anomalias neste pacote. `WHEN OTHERS` converte qualquer erro de conversão em NULL e merece revisão.
- **Dimensões:** a pré-validação verifica conflitos dentro da fonte atual; ainda é necessário comparar descrições com dimensões já carregadas e outros anos. `MAX` escolhe uma descrição após a pré-validação e `ON CONFLICT DO NOTHING` não atualiza descrições. Não constitui política de integração interanual.
- **Integração 2020/2021:** schemas e DDL dimensional são compartilháveis; a carga ainda lê a tabela genérica `staging.vra_tratada`, sem filtro por ano. Auditorias também têm nomes genéricos. Não executar outro ano sobre estas tabelas sem definir isolamento/integração. Os scripts existentes de 2020/2021 usam schemas anuais `elt_2020`/`elt_2021`, que não são criados por `00_schemas.sql`; a compatibilidade exige revisão futura.
- **Chave da fato:** `UNIQUE(id_raw)` e `ON CONFLICT(id_raw)` podem colidir entre RAWs anuais com identities independentes, omitindo registros. Definir estratégia global de identificação/proveniência com o grupo antes de integrar anos. Não alterado nesta tarefa.
- **Conciliação e contrato:** comparar ETL/ELT por códigos naturais, registros, categorias e métricas; confirmar os indicadores atípicos (contrato cita 687/693 de versão anterior, pacote relata 684/690), datas fora do ano e semântica de referência/fusos. Não somar ETL e ELT da mesma observação.

## Verificação desta organização

Conferência estática: cópias comparadas byte a byte com os ZIPs; oito CREATE TABLE deslocados na ordem original; reconstituição exata do texto do DW ao reinserir os blocos movidos. Consultas finais deslocadas integralmente. Nenhuma transformação, condição, JOIN ou INSERT foi reescrito. Originais continuam nos ZIPs. Nenhum banco foi acessado; execução e resultados continuam pendentes de validação em ambiente apropriado.
