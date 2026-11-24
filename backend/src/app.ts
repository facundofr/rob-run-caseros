import Fastify, { type FastifyInstance, type FastifyRequest } from "fastify";
import { z, ZodError } from "zod";
import { isValidServerKey, signSessionToken, verifySessionToken, type SteamVerifier } from "./auth.js";
import type { Config } from "./config.js";
import type { Db } from "./db.js";
import { AppError, notFound } from "./errors.js";
import { findOrCreatePlayer, getProfileByAccountId, type PlayerProfile } from "./services/accounts.js";
import { applyTransaction } from "./services/economy.js";
import { heartbeat, listServers, registerServer } from "./services/servers.js";

export interface AppDependencies {
  db: Db;
  config: Config;
  steam: SteamVerifier;
}

// --- Esquemas de entrada ------------------------------------------------------------------

const steamLoginBody = z.object({ ticket: z.string().regex(/^[0-9a-fA-F]+$/).min(16).max(4096) });
const devLoginBody = z.object({ name: z.string().trim().min(2).max(24).regex(/^[\p{L}\p{N}_\- ]+$/u) });
const verifySessionBody = z.object({ token: z.string().min(10).max(2048) });
const registerServerBody = z.object({
  name: z.string().trim().min(1).max(64),
  address: z.string().trim().min(1).max(255),
  port: z.number().int().min(1).max(65535),
  region: z.string().trim().min(2).max(32),
  maxPlayers: z.number().int().min(1).max(128),
});
const heartbeatBody = z.object({ currentPlayers: z.number().int().min(0).max(1000) });
const serverIdParams = z.object({ id: z.string().uuid() });
const transactionBody = z.object({
  characterId: z.number().int().positive(),
  amount: z.number().int().refine((value) => value !== 0, "El monto no puede ser cero").refine((value) => Math.abs(value) <= 1_000_000, "Monto fuera de rango"),
  reason: z.enum(["sell_loot", "arrest_reward", "shop_purchase", "admin_adjustment"]),
  idempotencyKey: z.string().min(8).max(128),
  serverId: z.string().uuid().optional(),
});
const characterParams = z.object({ accountId: z.coerce.number().int().positive() });

// --- Aplicación ---------------------------------------------------------------------------

export function buildApp({ db, config, steam }: AppDependencies): FastifyInstance {
  const app = Fastify({
    logger: config.NODE_ENV === "test" ? false : { level: "info", redact: ["req.headers.authorization", 'req.headers["x-server-key"]'] },
    bodyLimit: 64 * 1024,
  });

  app.setErrorHandler((error, request, reply) => {
    if (error instanceof ZodError) {
      return reply.status(400).send({ error: "invalid_request", message: "Datos inválidos.", issues: error.issues });
    }
    if (error instanceof AppError) {
      return reply.status(error.statusCode).send({ error: error.code, message: error.message });
    }
    const status = (error as { statusCode?: number }).statusCode;
    if (status && status >= 400 && status < 500) {
      return reply.status(status).send({ error: "bad_request", message: (error as Error).message });
    }
    request.log.error(error);
    return reply.status(500).send({ error: "internal_error", message: "Error interno." });
  });

  /** Las rutas de servidor de juego exigen la clave compartida en el header x-server-key. */
  const requireServerKey = async (request: FastifyRequest) => {
    const received = request.headers["x-server-key"];
    if (!isValidServerKey(config.SERVER_API_KEY, typeof received === "string" ? received : undefined)) {
      throw new AppError(401, "invalid_server_key", "Clave de servidor inválida.");
    }
  };

  const issueSession = async (profile: PlayerProfile) => ({
    token: await signSessionToken(config.JWT_SECRET, profile, config.SESSION_TTL_SECONDS),
    expiresIn: config.SESSION_TTL_SECONDS,
    accountId: profile.accountId,
    characterId: profile.characterId,
    name: profile.name,
  });

  const audit = (actor: string, action: string, details: Record<string, unknown>) =>
    db.query("INSERT INTO audit_log (actor, action, details) VALUES ($1, $2, $3)", [actor, action, JSON.stringify(details)]);

  app.get("/health", async () => {
    await db.query("SELECT 1");
    return { status: "ok" };
  });

  // --- Jugadores (cliente del juego) -------------------------------------------------------

  app.post("/v1/auth/steam", async (request) => {
    const { ticket } = steamLoginBody.parse(request.body);
    const { steamId } = await steam.verify(ticket);
    const profile = await findOrCreatePlayer(db, steamId, `Jugador ${steamId.slice(-4)}`);
    return issueSession(profile);
  });

  if (config.AUTH_DEV_MODE) {
    app.post("/v1/auth/dev", async (request) => {
      const { name } = devLoginBody.parse(request.body);
      const profile = await findOrCreatePlayer(db, `dev:${name.toLowerCase()}`, name);
      return issueSession(profile);
    });
  }

  app.get("/v1/servers", async () => listServers(db, config.SERVER_STALE_SECONDS));

  // --- Servidores de juego -----------------------------------------------------------------

  app.register(async (serverRoutes) => {
    serverRoutes.addHook("onRequest", requireServerKey);

    serverRoutes.post("/v1/servers/register", async (request) => {
      const server = await registerServer(db, registerServerBody.parse(request.body));
      await audit(`server:${server.id}`, "server_registered", { address: server.address, port: server.port });
      return server;
    });

    serverRoutes.post("/v1/servers/:id/heartbeat", async (request) => {
      const { id } = serverIdParams.parse(request.params);
      const { currentPlayers } = heartbeatBody.parse(request.body);
      return heartbeat(db, id, currentPlayers);
    });

    /** El servidor de juego valida el token que presenta el jugador al conectarse. */
    serverRoutes.post("/v1/sessions/verify", async (request) => {
      const { token } = verifySessionBody.parse(request.body);
      const claims = await verifySessionToken(config.JWT_SECRET, token);
      const profile = await getProfileByAccountId(db, claims.accountId);
      if (!profile || profile.characterId !== claims.characterId) {
        throw notFound("La cuenta");
      }
      if (profile.status !== "active") {
        throw new AppError(403, "account_banned", "La cuenta está suspendida.");
      }
      return profile;
    });

    serverRoutes.get("/v1/characters/:accountId", async (request) => {
      const { accountId } = characterParams.parse(request.params);
      const profile = await getProfileByAccountId(db, accountId);
      if (!profile) {
        throw notFound("La cuenta");
      }
      return profile;
    });

    serverRoutes.post("/v1/economy/transactions", async (request) => {
      const body = transactionBody.parse(request.body);
      const result = await applyTransaction(db, body);
      if (!result.replayed) {
        await audit(`server:${body.serverId ?? "unknown"}`, "economy_transaction", { ...body, balance: result.balance });
      }
      return result;
    });
  });

  return app;
}
