import type { Db, Queryable } from "../db.js";
import { isUniqueViolation } from "../db.js";
import { AppError } from "../errors.js";

export interface PlayerProfile {
  accountId: number;
  characterId: number;
  steamId: string;
  name: string;
  status: "active" | "banned";
  cash: number;
}

const profileQuery = `
  SELECT a.id AS "accountId", c.id AS "characterId", a.steam_id AS "steamId",
         c.name AS "name", a.status AS "status", w.cash AS "cash"
  FROM accounts a
  JOIN characters c ON c.account_id = a.id
  JOIN wallets w ON w.character_id = c.id`;

export async function getProfileByAccountId(q: Queryable, accountId: number): Promise<PlayerProfile | undefined> {
  return (await q.query<PlayerProfile>(`${profileQuery} WHERE a.id = $1`, [accountId])).rows[0];
}

async function getProfileBySteamId(q: Queryable, steamId: string): Promise<PlayerProfile | undefined> {
  return (await q.query<PlayerProfile>(`${profileQuery} WHERE a.steam_id = $1`, [steamId])).rows[0];
}

/**
 * Devuelve el perfil del jugador; si es la primera vez que entra, crea cuenta, personaje y billetera
 * en una sola transacción. Una cuenta suspendida no puede entrar.
 */
export async function findOrCreatePlayer(db: Db, steamId: string, displayName: string): Promise<PlayerProfile> {
  let profile = await getProfileBySteamId(db, steamId);

  if (!profile) {
    try {
      profile = await db.tx(async (q) => {
        const account = (await q.query<{ id: number }>(
          "INSERT INTO accounts (steam_id, display_name) VALUES ($1, $2) RETURNING id",
          [steamId, displayName],
        )).rows[0]!;
        const character = (await q.query<{ id: number }>(
          "INSERT INTO characters (account_id, name) VALUES ($1, $2) RETURNING id",
          [account.id, displayName],
        )).rows[0]!;
        await q.query("INSERT INTO wallets (character_id) VALUES ($1)", [character.id]);
        await q.query("INSERT INTO audit_log (actor, action, details) VALUES ($1, 'account_created', $2)", [
          `steam:${steamId}`,
          JSON.stringify({ accountId: account.id }),
        ]);
        return (await getProfileByAccountId(q, account.id))!;
      });
    } catch (error) {
      // Dos logins simultáneos de un jugador nuevo: el segundo encuentra la cuenta ya creada.
      if (!isUniqueViolation(error)) {
        throw error;
      }
      profile = await getProfileBySteamId(db, steamId);
    }
  }

  if (!profile) {
    throw new AppError(500, "account_unavailable", "No se pudo crear la cuenta.");
  }
  if (profile.status !== "active") {
    throw new AppError(403, "account_banned", "La cuenta está suspendida.");
  }
  return profile;
}
