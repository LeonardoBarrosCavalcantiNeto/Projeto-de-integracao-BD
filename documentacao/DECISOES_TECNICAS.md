# Decisões técnicas

## Template compartilhado para ELT 2019/2020

### Contexto e problema

O arquivo anteriormente chamado `sql/transformacoes/elt_2020.sql` também fornecia as transformações de 2019. O gerador adaptava ano, schemas, origem, nomes das tabelas e metadados por substituições de texto. O nome dificultava identificar a implementação de 2019, e referências específicas de 2020 estavam espalhadas pelo SQL.

### Decisão e justificativa

O arquivo foi renomeado para [elt_2019_2020.sql](../sql/transformacoes/elt_2019_2020.sql) e recebeu marcadores explícitos. Um único template mantém as regras compartilhadas e evita duplicar transformações. O [template de 2021](../sql/transformacoes/elt_2021.sql) e sua sequência de adaptação foram preservados.

### Funcionamento

O [gerador canônico](../scripts/integrar_anac.py) preenche os parâmetros abaixo para cada ano. O [executor final](../scripts/integracao_final.py) remapeia os schemas para staging_elt e dw_elt, monta o bundle ELT e suas etapas manuais. O PostgreSQL executa o SQL gerado após a ingestão bruta.

| Marcador | Valor preenchido pelo gerador |
|---|---|
| `__SCHEMA_ELT__` | `staging`, posteriormente remapeado para `staging_elt` na integração final |
| `__ANO__` | Ano processado, incluindo comentário, metadados, motivo de anomalia e validação da referência |
| `__TABELA_ORIGEM__` | `raw.voos_2019` ou `raw.voos_2020` |
| `__SUFIXO_ANUAL__` | `_2019` ou `_2020` nas tabelas intermediárias e auditorias |
| `__COLUNA_ID_RAW__` | Fragmento `id_raw, ` para a projeção de proveniência usada pela integração |

Os nomes contratuais de funções, tabelas, schemas e motivos de rejeição continuam iguais aos produzidos anteriormente. O template deve ser renderizado pelo Python antes da execução. O notebook individual de 2020 mantém seu SQL nas células e exporta sua própria versão da transformação.

### Compatibilidade e validações

Antes da edição, foram gerados os bundles completos com 36 CSVs sintéticos mínimos, contendo apenas três registros no total, um por ano. A referência foi salva em um diretório temporário exclusivo fora do Git. Após a refatoração, foram regenerados os mesmos artefatos nos mesmos caminhos temporários.

Os 15 arquivos SQL e psql gerados foram comparados byte a byte e permaneceram idênticos, incluindo os bundles ETL/ELT e as etapas anuais de 2019, 2020 e 2021. Os manifestos de código passam a refletir o novo caminho e hash do template.

O [teste de regressão](../tests/test_template_elt.py) conserva os hashes anteriores das três etapas anuais. Ele prepara arquivos sintéticos vazios, aplica o remapeamento final e confere hashes, ausência de marcadores, tabela de origem, ano de proveniência e motivo de anomalia de referência. Também verifica a ausência de referências a 2020 no SQL de 2019. O teste passou, assim como os quatro testes leves de ingestão.

A compilação Python e a conferência dos links locais foram executadas. A equivalência comprovada cobre o SQL gerado. A validação anterior com dados reais continua registrada no [relatório final](../relatorio/STATUS_FINAL_PROJETO.md). Esta refatoração não executou cargas PostgreSQL, não reprocessou os 36 CSVs reais e não criou clusters ou backups.

## Auditoria da referência fora do ano em 2021

A anomalia `REFERENCIA_FORA_DE_2021` conserva o texto bruto em `valor_original` nos dois fluxos. No ELT, a auditoria consulta a RAW por arquivo e linha, par único na ingestão integrada. A condição de ano continua sobre a data convertida.

Antes da correção, `01/01/2020 00:00:00` aparecia como o texto bruto no Pandas e como `2020-01-01` na auditoria SQL. A comparação integral apontava duas linhas distintas para a mesma ocorrência. O teste integrado agora confere esse caso, o controle ISO `2020-01-01` e a entrada inválida `01/01/2020`. As duas referências válidas conservam a data na fato e a inválida permanece com `NULL`, sem excluir a ocorrência.

A mudança altera intencionalmente o SQL gerado para 2021 e seu hash de regressão. Os SQLs anuais de 2019 e 2020 permaneceram idênticos byte a byte. A comprovação após a correção usa fixtures sintéticas. Os registros da execução histórica com os dados reais permanecem como evidências daquela execução. [SQL de 2021](../sql/transformacoes/elt_2021.sql) · [Teste integrado](../tests/test_integracao_final.py)
