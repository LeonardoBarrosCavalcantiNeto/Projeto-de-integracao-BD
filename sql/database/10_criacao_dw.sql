CREATE TABLE IF NOT EXISTS dw.dim_tempo (
    id_tempo INTEGER PRIMARY KEY,
    data DATE NOT NULL UNIQUE,
    ano INTEGER NOT NULL,
    trimestre INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    dia INTEGER NOT NULL,
    dia_semana INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_companhia_aerea (
    id_companhia BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    companhia_icao TEXT NOT NULL UNIQUE,
    companhia_nome TEXT
);

CREATE TABLE IF NOT EXISTS dw.dim_aeroporto (
    id_aeroporto BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    aeroporto_icao TEXT NOT NULL UNIQUE,
    descricao_aeroporto TEXT
);

CREATE TABLE IF NOT EXISTS dw.dim_situacao_voo (
    id_situacao INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    situacao_voo TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dw.dim_justificativa (
    id_justificativa BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    justificativa TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dw.dim_tipo_linha (
    id_tipo_linha INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_linha TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dw.dim_equipamento (
    id_equipamento BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    modelo_equipamento TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dw.fato_voo (
    id_voo BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_raw BIGINT NOT NULL UNIQUE,

    id_companhia BIGINT NOT NULL,
    id_aeroporto_origem BIGINT NOT NULL,
    id_aeroporto_destino BIGINT NOT NULL,
    id_tempo_partida INTEGER NOT NULL,
    id_tempo_chegada INTEGER NOT NULL,
    id_situacao INTEGER,
    id_justificativa BIGINT NOT NULL,
    id_tipo_linha INTEGER,
    id_equipamento BIGINT NOT NULL,

    numero_voo TEXT,
    codigo_di TEXT,
    referencia DATE,
    situacao_partida TEXT,
    situacao_chegada TEXT,

    partida_prevista TIMESTAMP,
    partida_real TIMESTAMP,
    chegada_prevista TIMESTAMP,
    chegada_real TIMESTAMP,

    numero_assentos INTEGER,
    quantidade_voos SMALLINT NOT NULL DEFAULT 1,

    diferenca_partida_min NUMERIC(12,2),
    diferenca_chegada_min NUMERIC(12,2),
    atraso_partida_min NUMERIC(12,2),
    atraso_chegada_min NUMERIC(12,2),

    partida_atipica_flag BOOLEAN NOT NULL,
    chegada_atipica_flag BOOLEAN NOT NULL,

    ano_origem INTEGER NOT NULL,
    arquivo_origem TEXT,
    linha_origem BIGINT,
    pipeline TEXT NOT NULL DEFAULT 'ELT',

    CONSTRAINT fk_fato_companhia
        FOREIGN KEY (id_companhia)
        REFERENCES dw.dim_companhia_aerea(id_companhia),
    CONSTRAINT fk_fato_aeroporto_origem
        FOREIGN KEY (id_aeroporto_origem)
        REFERENCES dw.dim_aeroporto(id_aeroporto),
    CONSTRAINT fk_fato_aeroporto_destino
        FOREIGN KEY (id_aeroporto_destino)
        REFERENCES dw.dim_aeroporto(id_aeroporto),
    CONSTRAINT fk_fato_tempo_partida
        FOREIGN KEY (id_tempo_partida)
        REFERENCES dw.dim_tempo(id_tempo),
    CONSTRAINT fk_fato_tempo_chegada
        FOREIGN KEY (id_tempo_chegada)
        REFERENCES dw.dim_tempo(id_tempo),
    CONSTRAINT fk_fato_situacao
        FOREIGN KEY (id_situacao)
        REFERENCES dw.dim_situacao_voo(id_situacao),
    CONSTRAINT fk_fato_justificativa
        FOREIGN KEY (id_justificativa)
        REFERENCES dw.dim_justificativa(id_justificativa),
    CONSTRAINT fk_fato_tipo_linha
        FOREIGN KEY (id_tipo_linha)
        REFERENCES dw.dim_tipo_linha(id_tipo_linha),
    CONSTRAINT fk_fato_equipamento
        FOREIGN KEY (id_equipamento)
        REFERENCES dw.dim_equipamento(id_equipamento)
);
