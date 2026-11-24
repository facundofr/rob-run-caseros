import { randomUUID } from "node:crypto";
import type { Db } from "../db.js";
import { notFound } from "../errors.js";

export interface GameServer {
  id: string;
  name: string;
  address: string;
  port: number;
  region: string;
  maxPlayers: number;
  currentPlayers: number;
}

export interface RegisterServerRequest {
  name: string;
  address: string;
  port: number;
  region: string;
  maxPlayers: number;
}

const serverColumns = `id, name, address, port, region, max_players AS "maxPlayers", current_players AS "currentPlayers"`;

/** Registra una instancia al arrancar. Si ya existía con la misma dirección y puerto, la reutiliza. */
export async function registerServer(db: Db, request: RegisterServerRequest): Promise<GameServer> {
  const rows = (await db.query<GameServer>(
    `INSERT INTO game_servers (id, name, address, port, region, max_players, current_players, last_heartbeat)
     VALUES ($1, $2, $3, $4, $5, $6, 0, now())
     ON CONFLICT (address, port) DO UPDATE
       SET name = EXCLUDED.name, region = EXCLUDED.region, max_players = EXCLUDED.max_players,
           current_players = 0, last_heartbeat = now()
     RETURNING ${serverColumns}`,
    [randomUUID(), request.name, request.address, request.port, request.region, request.maxPlayers],
  )).rows;
  return rows[0]!;
}

export async function heartbeat(db: Db, serverId: string, currentPlayers: number): Promise<GameServer> {
  const server = (await db.query<GameServer>(
    `UPDATE game_servers SET current_players = LEAST($2::int, max_players), last_heartbeat = now()
     WHERE id = $1 RETURNING ${serverColumns}`,
    [serverId, currentPlayers],
  )).rows[0];
  if (!server) {
    throw notFound("El servidor");
  }
  return server;
}

/**
 * Servidores vivos (con heartbeat reciente), los más poblados primero.
 * Se recomienda el más poblado que tenga lugar, para concentrar a los jugadores.
 */
export async function listServers(db: Db, staleSeconds: number): Promise<{ servers: GameServer[]; recommended: GameServer | null }> {
  const servers = (await db.query<GameServer>(
    `SELECT ${serverColumns} FROM game_servers
     WHERE last_heartbeat > now() - ($1::int * interval '1 second')
     ORDER BY current_players DESC, name ASC`,
    [staleSeconds],
  )).rows;

  const recommended = servers.find((server) => server.currentPlayers < server.maxPlayers) ?? null;
  return { servers, recommended };
}
