import type { Db } from "../db.js";
import { isUniqueViolation } from "../db.js";
import { AppError } from "../errors.js";
import { getDummyHash, hashPassword, verifyPassword, type ScryptParams } from "../passwords.js";
import { assertActive, createPlayer, getProfileByAccountId, type PlayerProfile } from "./accounts.js";

export interface LockoutPolicy {
  /** Intentos fallidos seguidos antes de bloquear la cuenta. */
  maxFailedAttempts: number;
  /** Minutos de bloqueo. */
  lockMinutes: number;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
}

/** Mismo mensaje para usuario inexistente y contraseña incorrecta: no revela qué usuarios existen. */
const invalidCredentials = () => new AppError(401, "invalid_credentials", "Usuario o contraseña incorrectos.");

export async function registerWithPassword(db: Db, request: RegisterRequest, params: ScryptParams): Promise<PlayerProfile> {
  const passwordHash = await hashPassword(request.password, params);
  const usernameLower = request.username.toLowerCase();
  const emailLower = request.email?.toLowerCase() ?? null;

  try {
    return await db.tx(async (q) => {
      const accountId = await createPlayer(q, null, request.username, `user:${usernameLower}`);
      await q.query(
        `INSERT INTO credentials (account_id, username, username_lower, email, email_lower, password_hash)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [accountId, request.username, usernameLower, request.email ?? null, emailLower, passwordHash],
      );
      return (await getProfileByAccountId(q, accountId))!;
    });
  } catch (error) {
    if (isUniqueViolation(error)) {
      const detail = String((error as { detail?: string; message?: string }).detail ?? (error as Error).message);
      if (detail.includes("email")) {
        throw new AppError(409, "email_taken", "Ese email ya está registrado.");
      }
      throw new AppError(409, "username_taken", "Ese nombre de usuario ya existe.");
    }
    throw error;
  }
}

interface CredentialRow {
  account_id: number;
  password_hash: string;
  failed_attempts: number;
  locked_minutes_left: number | null;
}

export async function loginWithPassword(
  db: Db,
  username: string,
  password: string,
  params: ScryptParams,
  lockout: LockoutPolicy,
): Promise<PlayerProfile> {
  const row = (await db.query<CredentialRow>(
    `SELECT account_id, password_hash, failed_attempts,
            CASE WHEN locked_until > now()
                 THEN CEIL(EXTRACT(EPOCH FROM (locked_until - now())) / 60)::int END AS locked_minutes_left
     FROM credentials WHERE username_lower = $1`,
    [username.toLowerCase()],
  )).rows[0];

  if (!row) {
    await verifyPassword(password, await getDummyHash(params), params); // mismo tiempo de respuesta
    throw invalidCredentials();
  }

  if (row.locked_minutes_left !== null) {
    throw new AppError(429, "account_locked", `Demasiados intentos fallidos. Probá de nuevo en ${row.locked_minutes_left} min.`);
  }

  const { valid, needsRehash } = await verifyPassword(password, row.password_hash, params);

  if (!valid) {
    await db.query(
      `UPDATE credentials
       SET failed_attempts = failed_attempts + 1,
           locked_until = CASE WHEN failed_attempts + 1 >= $2 THEN now() + ($3::int * interval '1 minute') ELSE locked_until END
       WHERE account_id = $1`,
      [row.account_id, lockout.maxFailedAttempts, lockout.lockMinutes],
    );
    await db.query("INSERT INTO audit_log (actor, action, details) VALUES ($1, 'login_failed', $2)", [
      `account:${row.account_id}`,
      JSON.stringify({ attempt: row.failed_attempts + 1 }),
    ]);
    throw invalidCredentials();
  }

  const newHash = needsRehash ? await hashPassword(password, params) : null;
  await db.query(
    `UPDATE credentials
     SET failed_attempts = 0, locked_until = NULL,
         password_hash = COALESCE($2, password_hash)
     WHERE account_id = $1`,
    [row.account_id, newHash],
  );

  const profile = await getProfileByAccountId(db, row.account_id);
  if (!profile) {
    throw invalidCredentials();
  }
  return assertActive(profile);
}
