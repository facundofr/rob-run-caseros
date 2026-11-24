import { timingSafeEqual } from "node:crypto";
import { SignJWT, jwtVerify } from "jose";
import { AppError } from "./errors.js";

export interface SessionClaims {
  accountId: number;
  characterId: number;
}

const issuer = "barrio-backend";
const audience = "barrio-game-server";

/** Token de sesión del jugador: lo presenta al servidor de juego al conectarse. Vida corta. */
export async function signSessionToken(secret: string, claims: SessionClaims, ttlSeconds: number): Promise<string> {
  return new SignJWT({ cid: claims.characterId })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(String(claims.accountId))
    .setIssuer(issuer)
    .setAudience(audience)
    .setIssuedAt()
    .setExpirationTime(`${ttlSeconds}s`)
    .sign(new TextEncoder().encode(secret));
}

export async function verifySessionToken(secret: string, token: string): Promise<SessionClaims> {
  try {
    const { payload } = await jwtVerify(token, new TextEncoder().encode(secret), { issuer, audience, algorithms: ["HS256"] });
    const accountId = Number(payload.sub);
    const characterId = Number(payload.cid);
    if (!Number.isInteger(accountId) || !Number.isInteger(characterId)) {
      throw new Error("claims inválidos");
    }
    return { accountId, characterId };
  } catch {
    throw new AppError(401, "invalid_token", "Token de sesión inválido o vencido.");
  }
}

/** Compara la clave de servidor sin filtrar información por tiempos de respuesta. */
export function isValidServerKey(expected: string, received: string | undefined): boolean {
  if (!received) {
    return false;
  }
  const a = Buffer.from(expected);
  const b = Buffer.from(received);
  return a.length === b.length && timingSafeEqual(a, b);
}

/** Verifica un ticket de sesión de Steam. Se inyecta para poder reemplazarlo en las pruebas. */
export interface SteamVerifier {
  verify(ticketHex: string): Promise<{ steamId: string }>;
}

/** Validación real con la Web API de Steam (requiere la Publisher Web API Key y el App ID). */
export function createSteamVerifier(webApiKey: string | undefined, appId: string | undefined): SteamVerifier {
  return {
    async verify(ticketHex) {
      if (!webApiKey || !appId) {
        throw new AppError(503, "steam_not_configured", "El login con Steam no está configurado en este servidor.");
      }

      const url = new URL("https://partner.steam-api.com/ISteamUserAuth/AuthenticateUserTicket/v1/");
      url.searchParams.set("key", webApiKey);
      url.searchParams.set("appid", appId);
      url.searchParams.set("ticket", ticketHex);

      const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
      if (!response.ok) {
        throw new AppError(502, "steam_unavailable", "Steam no respondió correctamente.");
      }

      const body = (await response.json()) as {
        response?: { params?: { result?: string; steamid?: string; publisherbanned?: boolean } };
      };
      const params = body.response?.params;
      if (params?.result !== "OK" || !params.steamid) {
        throw new AppError(401, "steam_ticket_invalid", "El ticket de Steam no es válido.");
      }
      if (params.publisherbanned) {
        throw new AppError(403, "account_banned", "La cuenta está suspendida.");
      }
      return { steamId: params.steamid };
    },
  };
}
