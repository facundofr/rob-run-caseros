import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.js";
import type { SteamVerifier } from "../src/auth.js";
import { AppError } from "../src/errors.js";
import { loadConfig, type Config } from "../src/config.js";
import { createPgliteDb, migrate, type Db } from "../src/db.js";

export const SERVER_KEY = "test-server-key-0123456789abcdef";

/** Steam falso: el ticket "aaaa...<steamId en hex>" es válido; "deadbeef..." es inválido. */
export const fakeSteam: SteamVerifier = {
  async verify(ticketHex) {
    if (ticketHex.startsWith("deadbeef")) {
      throw new AppError(401, "steam_ticket_invalid", "El ticket de Steam no es válido.");
    }
    return { steamId: `7656119${ticketHex.slice(-10)}` };
  },
};

export interface TestContext {
  app: FastifyInstance;
  db: Db;
  config: Config;
}

export async function createTestApp(overrides: Partial<Record<string, string>> = {}): Promise<TestContext> {
  const config = loadConfig({
    NODE_ENV: "test",
    JWT_SECRET: "test-jwt-secret-0123456789abcdefghijklmnop",
    SERVER_API_KEY: SERVER_KEY,
    AUTH_DEV_MODE: "true",
    ...overrides,
  });
  const db = await createPgliteDb();
  await migrate(db);
  const app = buildApp({ db, config, steam: fakeSteam });
  await app.ready();
  return { app, db, config };
}

export async function devLogin(app: FastifyInstance, name: string) {
  const response = await app.inject({ method: "POST", url: "/v1/auth/dev", payload: { name } });
  if (response.statusCode !== 200) {
    throw new Error(`login falló: ${response.statusCode} ${response.body}`);
  }
  return response.json() as { token: string; accountId: number; characterId: number; name: string };
}

export const serverHeaders = { "x-server-key": SERVER_KEY };
