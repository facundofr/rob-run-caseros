-- Login con usuario y contraseña. Una cuenta puede tener credenciales, Steam, o ambas (vinculación futura).

ALTER TABLE accounts ALTER COLUMN steam_id DROP NOT NULL;

CREATE TABLE credentials (
    account_id          INTEGER     PRIMARY KEY REFERENCES accounts (id),
    username            TEXT        NOT NULL,
    username_lower      TEXT        NOT NULL UNIQUE,
    email               TEXT,
    email_lower         TEXT        UNIQUE,
    -- Formato: scrypt$N$r$p$sal$hash. Nunca se guarda la contraseña.
    password_hash       TEXT        NOT NULL,
    failed_attempts     INTEGER     NOT NULL DEFAULT 0,
    locked_until        TIMESTAMPTZ,
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
