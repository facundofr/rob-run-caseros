import type { Db } from "../db.js";
import { isUniqueViolation } from "../db.js";
import { AppError, notFound } from "../errors.js";

export interface TransactionRequest {
  characterId: number;
  /** Positivo cobra, negativo paga. Nunca cero. */
  amount: number;
  reason: string;
  /** La genera el servidor de juego. Reintentar con la misma clave no repite el movimiento. */
  idempotencyKey: string;
  serverId?: string;
}

export interface TransactionResult {
  entryId: number;
  characterId: number;
  amount: number;
  balance: number;
  /** true si la clave ya se había usado y se devolvió el movimiento original. */
  replayed: boolean;
}

interface LedgerRow {
  id: number;
  character_id: number;
  amount: number;
  balance_after: number;
}

const findByKey = "SELECT id, character_id, amount, balance_after FROM ledger_entries WHERE idempotency_key = $1";

/**
 * Aplica un movimiento de dinero: actualiza el saldo y escribe el ledger en la misma transacción.
 * - Idempotente: la misma clave devuelve el movimiento ya hecho, sin repetirlo.
 * - La misma clave con otros datos es un conflicto (probable error del servidor de juego).
 * - Nunca deja el saldo negativo.
 */
export async function applyTransaction(db: Db, request: TransactionRequest): Promise<TransactionResult> {
  try {
    return await db.tx(async (q) => {
      const existing = (await q.query<LedgerRow>(findByKey, [request.idempotencyKey])).rows[0];
      if (existing) {
        return replay(existing, request);
      }

      // FOR UPDATE bloquea la billetera hasta terminar: dos movimientos simultáneos no se pisan.
      const wallet = (await q.query<{ cash: number }>(
        "SELECT cash FROM wallets WHERE character_id = $1 FOR UPDATE",
        [request.characterId],
      )).rows[0];
      if (!wallet) {
        throw notFound("El personaje");
      }

      const balance = wallet.cash + request.amount;
      if (balance < 0) {
        throw new AppError(409, "insufficient_funds", `Saldo insuficiente: tiene $${wallet.cash}.`);
      }

      await q.query("UPDATE wallets SET cash = $1, updated_at = now() WHERE character_id = $2", [balance, request.characterId]);
      const entry = (await q.query<{ id: number }>(
        `INSERT INTO ledger_entries (character_id, amount, reason, server_id, idempotency_key, balance_after)
         VALUES ($1, $2, $3, $4, $5, $6) RETURNING id`,
        [request.characterId, request.amount, request.reason, request.serverId ?? null, request.idempotencyKey, balance],
      )).rows[0]!;

      return { entryId: entry.id, characterId: request.characterId, amount: request.amount, balance, replayed: false };
    });
  } catch (error) {
    // Dos pedidos simultáneos con la misma clave: el segundo choca con UNIQUE y devuelve el primero.
    if (!isUniqueViolation(error)) {
      throw error;
    }
    const existing = (await db.query<LedgerRow>(findByKey, [request.idempotencyKey])).rows[0];
    if (!existing) {
      throw error;
    }
    return replay(existing, request);
  }
}

function replay(existing: LedgerRow, request: TransactionRequest): TransactionResult {
  if (existing.character_id !== request.characterId || existing.amount !== request.amount) {
    throw new AppError(409, "idempotency_conflict", "La clave de idempotencia ya se usó con otros datos.");
  }
  return {
    entryId: existing.id,
    characterId: existing.character_id,
    amount: existing.amount,
    balance: existing.balance_after,
    replayed: true,
  };
}
