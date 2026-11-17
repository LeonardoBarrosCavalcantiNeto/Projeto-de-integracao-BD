-- Executar depois da criação das funções; teste não modifica os dados ANAC.
DO $$ BEGIN
 IF staging.datahora_segura('31/02/2020 12:00') IS NOT NULL
 OR staging.datahora_segura('01/01/2020 24:00') IS NOT NULL
 OR staging.datahora_segura('01/01/2020 12:60') IS NOT NULL
 OR staging.datahora_segura('2020-01-01 12:00') IS NOT NULL
 OR staging.datahora_segura(NULL) IS NOT NULL
 OR staging.data_segura('2019-02-29') IS NOT NULL
 OR staging.data_segura('2020-02-29') IS DISTINCT FROM date '2020-02-29'
 OR staging.inteiro_seguro('-1') IS NOT NULL
 OR staging.inteiro_seguro('2147483648') IS NOT NULL
 OR staging.inteiro_seguro('1.5') IS NOT NULL
 OR staging.inteiro_seguro('0') IS DISTINCT FROM 0
 OR staging.limpar_texto(E' \t\n ') IS NOT NULL
 OR staging.limpar_texto('NULL') IS DISTINCT FROM 'NULL' THEN
 RAISE EXCEPTION 'Falha nas conversões seguras'; END IF;
END $$;
