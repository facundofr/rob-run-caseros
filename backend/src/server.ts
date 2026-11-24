import { mkdir } from "node:fs/promises";
import { buildApp } from "./app.js";
import { createSteamVerifier } from "./auth.js";
import { loadConfig } from "./config.js";
import { createPgDb, createPgliteDb, migrate, type Db } from "./db.js";

// Carga backend/.env si existe (las variables del sistema tienen prioridad).
try {
  process.loadEnvFile(".env");
} catch {
  // sin .env: se usan solo las variables del sistema
}

const config = loadConfig();

async function openDatabase(): Promise<Db> {
  if (config.DATABASE_URL) {
    return createPgDb(config.DATABASE_URL);
  }
  await mkdir("data", { recursive: true });
  return createPgliteDb("data/pglite");
}

const db = await openDatabase();

const applied = await migrate(db);
const app = buildApp({ db, config, steam: createSteamVerifier(config.STEAM_WEB_API_KEY, config.STEAM_APP_ID) });

if (applied.length > 0) {
  app.log.info({ applied }, "Migraciones aplicadas");
}
if (!config.DATABASE_URL) {
  app.log.warn("Sin DATABASE_URL: usando PGlite en ./data (solo para desarrollo).");
}
if (config.AUTH_DEV_MODE) {
  app.log.warn("AUTH_DEV_MODE activo: se puede entrar sin Steam.");
}

const shutdown = async () => {
  await app.close();
  await db.close();
  process.exit(0);
};
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

await app.listen({ host: config.HOST, port: config.PORT });
