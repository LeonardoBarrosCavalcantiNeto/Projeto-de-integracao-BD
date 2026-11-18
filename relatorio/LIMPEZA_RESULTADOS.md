# Limpeza dos resultados da entrega

Revisão na branch portabilidade-academica. Dos 101 arquivos rastreados em resultados, 54 já estavam excluídos pelo responsável, 31 exportações reproduzíveis foram removidas nesta limpeza e 16 evidências compactas foram preservadas. As exclusões preexistentes ficam fora do commit desta tarefa.

A classificação A identifica entradas e evidências preservadas da execução já validada. B identifica saídas reproduzíveis removidas. C identifica artefatos históricos já excluídos pelo responsável. Nenhuma dependência D ficou sem resolução. Os arquivos ignorados preexistentes continuam no disco.

O manifesto dos 36 CSVs está em [dados/manifesto_vra.json](../dados/manifesto_vra.json). O teste do downloader também lê [fontes_inalteradas.json](../resultados/validacoes/integracao_final/fontes_inalteradas.json). Os três resumos individuais e o JSON da carga PostgreSQL de 2020 preservam a evidência daquela entrega. Backup, recuperação, armazenamento, testes e identidade RAW registram condições da execução histórica que uma nova execução não reproduz literalmente. O contrato e a rastreabilidade continuam implementados nas tabelas de auditoria e nos geradores preservados.

As leituras de inventário ELT e resumo ELT em salvar_evidencias do ETL 2020 são opcionais e condicionadas à existência dos dois arquivos. A ausência do inventário, já excluído pelo responsável, omite apenas a comparação preliminar histórica. A comparação final por ocorrência continua disponível.

## Regeneração

Após preparar os dados e carregar os DWs conforme o [guia multiplataforma](../documentacao/REPRODUCAO_MULTIPLATAFORMA.md), os comandos abaixo regeneram exportações e auditorias sobre o cluster isolado. Exigem os artefatos locais da preparação e o cluster desligado, conforme o [guia da integração](../documentacao/INTEGRACAO_FINAL.md).

```bash
python scripts/evidencias_final.py
python scripts/auditar_contrato_final.py
python scripts/integracao_final.py compare
```

As consultas e CSVs analíticos são gerados em .local/final/evidencias. A comparação registra a conferência dimensional em .local/final/validacao_dimensoes.log e a igualdade por ano em .local/final/validacao_ANO.log. O gerador de evidências reexporta RAW temporariamente e verifica espaço em disco. Estes comandos não foram executados durante a limpeza.

As exportações individuais são produzidas pelas células de exportação de [ELT 2020](../notebooks/elt/elt_2020.ipynb) e [ELT 2021](../notebooks/elt/elt_2021.ipynb). O [ETL 2020](../notebooks/etl/etl_2020.ipynb) também gera evidências opcionais pelo script original. Os resultados e limitações medidos permanecem nos relatórios individuais e no [relatório final](STATUS_FINAL_PROJETO.md).

A ordem de carga, validação e auditoria dos três anos está na [documentação da integração final](../documentacao/INTEGRACAO_FINAL.md). O validador `scripts/validar_guia.py` verifica os guias atuais e o bundle final preparado.

## Inventário por arquivo

Os caminhos abaixo são relativos à raiz do repositório e registram o estado observado antes da limpeza.

| Caminho | Classe | Decisão e justificativa |
|---|---|---|
| `resultados/logs/inventario_arquivos_elt_2020.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/logs/inventario_arquivos_elt_2021.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/logs/inventario_arquivos_etl_2020.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/logs/metadados_execucao_elt_2020.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/logs/metadados_execucao_elt_2021.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/rejeicoes/motivos_rejeicao_elt_2020.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/rejeicoes/motivos_rejeicao_elt_2021.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/rejeicoes/vra_duplicatas_excluidas_elt_2020.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/rejeicoes/vra_duplicatas_excluidas_elt_2021.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/rejeicoes/vra_rejeicoes_elt_2020.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/atipicos_amostra_elt_2020.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/atipicos_amostra_elt_2021.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/guia_execucao/assercoes_resultados.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_01.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_02.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_03.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_04.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_05.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_06.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_07.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_08.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_09.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consulta_10.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/consultas_executadas.sql` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/equivalencia_bundle.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/execucao_manual.log` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/manual_09_validar_contrato.log` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/postgres_reexecucao.log` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/referencias_documentos.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/guia_execucao/testes.log` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/analise_01.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/analise_02.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/analise_03.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/analise_04.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/analise_05.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/analise_06.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/anomalias.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/backup_isolado.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/comparacao_etl_elt.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/dimensoes.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/etl_2019_resumo.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/etl_2020_resumo.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/fato_por_ano.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/grupos_duplicados.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/identidade_csv_raw.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/manifesto_carga_inicial.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/manifesto_fontes.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/manifesto_reproducao.json` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/motivos_rejeicao.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/origem_por_arquivo.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/qualidade.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/qualidade_adicional.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/resolucoes_aplicadas.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/restricoes.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/servidor_teste.csv` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_2019_2020/testes.log` | C | Exclusão preexistente, fora do commit. Artefato histórico já excluído pelo responsável. |
| `resultados/validacoes/integracao_final/aeroportos_destino_elt.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/aeroportos_destino_etl.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/aeroportos_origem_elt.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/aeroportos_origem_etl.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/armazenamento.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/backup_isolado.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/companhias_elt.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/companhias_etl.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/comparacao_analitica.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/comparacao_integral.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/diagnosticos_contrato.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/diagnosticos_contrato_sql.csv` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/dimensoes.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/dimensoes_elt.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/dimensoes_etl.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/fato_elt.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/fato_etl.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/fontes_inalteradas.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/identidade_raw.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/indicadores_elt.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/indicadores_etl.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/layout_2021.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/mensal_elt.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/mensal_etl.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/motivos_rejeicao.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/nulos_elt.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/nulos_etl.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/origem_arquivo.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/qualidade.csv` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/recuperacao_cluster.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/restricoes.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/integracao_final/testes.json` | A | Preservar. Registro compacto da validação real, recuperação ou proveniência. |
| `resultados/validacoes/integracao_final/variantes_dimensoes.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/layout_por_arquivo_elt_2021.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/mensal_elt_2020.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/mensal_elt_2021.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/resumo_qualidade_elt_2020.csv` | A | Preservar. Resumo da entrega individual ou prova da carga experimental. |
| `resultados/validacoes/resumo_qualidade_elt_2021.csv` | A | Preservar. Resumo da entrega individual ou prova da carga experimental. |
| `resultados/validacoes/resumo_qualidade_etl_2020.csv` | A | Preservar. Resumo da entrega individual ou prova da carga experimental. |
| `resultados/validacoes/situacao_voo_elt_2020.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/situacao_voo_elt_2021.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/validacao_postgresql_etl_2020.json` | A | Preservar. Resumo da entrega individual ou prova da carga experimental. |
| `resultados/validacoes/vra_anomalias_elt_2020.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/vra_anomalias_elt_2021.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |
| `resultados/validacoes/vra_conflitos_codigo_elt_2021.csv` | B | Remover nesta limpeza. Exportação regenerável pelas consultas ou notebooks preservados. |

## Saídas locais ignoradas

Os arquivos abaixo são classe B, saídas geradas do ETL 2020. Continuam no disco e fora do Git.

- `resultados/validacoes/analise_2_mensal_2020.csv`
- `resultados/validacoes/atipicos_etl_2020.csv`
- `resultados/validacoes/comparacao_preliminar_etl_elt_2020.json`
- `resultados/validacoes/dim_aeroporto_experimental_2020.csv`
- `resultados/validacoes/mensal_etl_2020.csv`
- `resultados/validacoes/partidas_ano_divergente_etl_2020.csv.gz`
- `resultados/validacoes/resolucoes_aeroportos_aplicadas_etl_2020.csv.gz`
- `resultados/validacoes/situacao_voo_etl_2020.csv`
- `resultados/validacoes/vra_anomalias_etl_2020.csv.gz`

## Verificações da limpeza

Oito testes leves passaram, cobrindo downloader e manifesto, ingestão e reserva de espaço. A sintaxe dos 21 arquivos Python foi analisada com ast.parse. O validador do guia aprovou 35 blocos Bash, 14 hashes do bundle local existente e suas referências. A conferência dos links Markdown locais passou.

Os scripts Python, SQL, testes, entradas de referência e notebooks permaneceram com o conteúdo observado no início desta tarefa. A análise sintática PostgreSQL ficou pendente pela ausência de parser instalado. Nenhuma consulta ou carga foi executada no banco nesta revisão. As suítes que criam clusters foram dispensadas.
