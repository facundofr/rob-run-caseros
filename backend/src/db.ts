import { readdir, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import pg from "pg";
import { PGlite } from "@electric-sql/pglite";

/** Lo mínimo que el resto del código necesita de una conexión: ejecutar SQL con parámetros. */
export interface Queryable {
  query<T = Record<string, unknown>>(sql: string, params?: unknown[]): Promise<{ rows: T[] }>;
}

export interface Db extends Queryable {
  /** Ejecuta fn dentro de una transacción: si lanza un error, no se guarda nada. */
  tx<T>(fn: (q: Queryable) => Promise<T>): Promise<T>;
  close(): Promise<void>;
}

/** PostgreSQL real (producción y VPS). */
export function createPgDb(connectionString: string): Db {
  const pool = new pg.Pool({ connectionString, max: 10 });

  return {
    async query<T>(sql: string, params: unknown[] = []) {
      const result = await pool.query(sql, params);
      return { rows: result.rows as T[] };
    },
    async tx<T>(fn: (q: Queryable) => Promise<T>) {
      const client = await pool.connect();
      try {
        await client.query("BEGIN");
        const result = await fn({
          query: async <R>(sql: string, params: unknown[] = []) => ({ rows: (await client.query(sql, params)).rows as R[] }),
        });
        await client.query("COMMIT");
        return result;
      } catch (error) {
        await client.query("ROLLBACK");
        throw error;
      } finally {
        client.release();
      }
    },
    close: () => pool.end(),
  };
}

/**
 * PostgreSQL embebido (PGlite): para pruebas y para desarrollo sin instalar Postgres.
 * Sin dataDir guarda todo en memoria.
 */
export async function createPgliteDb(dataDir?: string): Promise<Db> {
  const db = dataDir ? new PGlite(dataDir) : new PGlite();
  await db.waitReady;

  return {
    async query<T>(sql: string, params: unknown[] = []) {
      const result = await db.query<T>(sql, params);
      return { rows: result.rows };
    },
    async tx<T>(fn: (q: Queryable) => Promise<T>) {
      return db.transaction(async (transaction) =>
        fn({
          query: async <R>(sql: string, params: unknown[] = []) => ({ rows: (await transaction.query<R>(sql, params)).rows }),
        }),
      );
    },
    close: () => db.close(),
  };
}

const migrationsDir = join(dirname(fileURLToPath(import.meta.url)), "..", "migrations");

/** Aplica, en orden, las migraciones de /migrations que todavía no se aplicaron. */
export async function migrate(db: Db): Promise<string[]> {
  await db.query(`CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
  )`);

  const applied = new Set((await db.query<{ name: string }>("SELECT name FROM schema_migrations")).rows.map((row) => row.name));
  const files = (await readdir(migrationsDir)).filter((file) => file.endsWith(".sql")).sort();
  const newlyApplied: string[] = [];

  for (const file of files) {
    if (applied.has(file)) {
      continue;
    }
    const sql = await readFile(join(migrationsDir, file), "utf8");
    await db.tx(async (q) => {
      for (const statement of splitStatements(sql)) {
        await q.query(statement);
      }
      await q.query("INSERT INTO schema_migrations (name) VALUES ($1)", [file]);
    });
    newlyApplied.push(file);
  }
  return newlyApplied;
}

/** Separa un archivo SQL en sentencias (las migraciones no usan ';' dentro de strings ni funciones). */
function splitStatements(sql: string): string[] {
  return sql
    .split("\n")
    .filter((line) => !line.trim().startsWith("--"))
    .join("\n")
    .split(";")
    .map((statement) => statement.trim())
    .filter((statement) => statement.length > 0);
}

/** Código de error de Postgres para violación de restricción UNIQUE. */
export function isUniqueViolation(error: unknown): boolean {
  return typeof error === "object" && error !== null && (error as { code?: string }).code === "23505";
}
