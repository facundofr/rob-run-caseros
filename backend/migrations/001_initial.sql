-- Esquema inicial del MVP: cuentas, personaje, billetera, ledger, servidores de juego y auditoría.
-- Los montos son INTEGER (pesos del juego, sin decimales).

CREATE TABLE accounts (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    steam_id     TEXT        NOT NULL UNIQUE,
    display_name TEXT        NOT NULL,
    status       TEXT        NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'banned')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Un personaje por cuenta en el MVP.
CREATE TABLE characters (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id INTEGER     NOT NULL UNIQUE REFERENCES accounts (id),
    name       TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- El saldo nunca puede quedar negativo: lo garantiza la base, no solo el código.
CREATE TABLE wallets (
    character_id INTEGER     PRIMARY KEY REFERENCES characters (id),
    cash         INTEGER     NOT NULL DEFAULT 0 CHECK (cash >= 0),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Cada movimiento de dinero es una fila. La clave de idempotencia impide cobrar o pagar dos veces.
CREATE TABLE ledger_entries (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    character_id    INTEGER     NOT NULL REFERENCES characters (id),
    amount          INTEGER     NOT NULL CHECK (amount <> 0),
    reason          TEXT        NOT NULL,
    server_id       TEXT,
    idempotency_key TEXT        NOT NULL UNIQUE,
    balance_after   INTEGER     NOT NULL CHECK (balance_after >= 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ledger_entries_character_idx ON ledger_entries (character_id, created_at);

CREATE TABLE game_servers (
    id              TEXT        PRIMARY KEY,
    name            TEXT        NOT NULL,
    address         TEXT        NOT NULL,
    port            INTEGER     NOT NULL CHECK (port BETWEEN 1 AND 65535),
    region          TEXT        NOT NULL,
    max_players     INTEGER     NOT NULL CHECK (max_players > 0),
    current_players INTEGER     NOT NULL DEFAULT 0 CHECK (current_players >= 0),
    last_heartbeat  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (address, port)
);

CREATE TABLE audit_log (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor      TEXT        NOT NULL,
    action     TEXT        NOT NULL,
    details    JSONB       NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
