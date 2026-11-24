import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { applyTransaction } from "../src/services/economy.js";
import { createTestApp, devLogin, serverHeaders, type TestContext } from "./helpers.js";

let ctx: TestContext;
let characterId: number;

beforeEach(async () => {
  ctx = await createTestApp();
  characterId = (await devLogin(ctx.app, "Ladron")).characterId;
});

afterEach(async () => {
  await ctx.app.close();
  await ctx.db.close();
});

const post = (payload: Record<string, unknown>) =>
  ctx.app.inject({ method: "POST", url: "/v1/economy/transactions", headers: serverHeaders, payload });

async function walletAndLedger() {
  const cash = (await ctx.db.query<{ cash: number }>("SELECT cash FROM wallets WHERE character_id = $1", [characterId])).rows[0]!.cash;
  const ledger = (await ctx.db.query<{ total: number; count: number }>(
    "SELECT COALESCE(SUM(amount), 0)::int AS total, COUNT(*)::int AS count FROM ledger_entries WHERE character_id = $1",
    [characterId],
  )).rows[0]!;
  return { cash, ledgerTotal: ledger.total, entries: ledger.count };
}

describe("economía", () => {
  it("cobra y paga, y el saldo siempre coincide con la suma del ledger", async () => {
    expect((await post({ characterId, amount: 500, reason: "sell_loot", idempotencyKey: "venta-0001" })).json().balance).toBe(500);
    expect((await post({ characterId, amount: -200, reason: "shop_purchase", idempotencyKey: "compra-0001" })).json().balance).toBe(300);

    const state = await walletAndLedger();
    expect(state).toEqual({ cash: 300, ledgerTotal: 300, entries: 2 });
  });

  it("no repite un movimiento reintentado con la misma clave", async () => {
    const first = await post({ characterId, amount: 500, reason: "sell_loot", idempotencyKey: "venta-retry-1" });
    const retry = await post({ characterId, amount: 500, reason: "sell_loot", idempotencyKey: "venta-retry-1" });

    expect(first.json()).toMatchObject({ balance: 500, replayed: false });
    expect(retry.json()).toMatchObject({ balance: 500, replayed: true, entryId: first.json().entryId });
    expect(await walletAndLedger()).toEqual({ cash: 500, ledgerTotal: 500, entries: 1 });
  });

  it("no duplica dinero con pedidos simultáneos con la misma clave", async () => {
    const results = await Promise.all(
      Array.from({ length: 5 }, () =>
        applyTransaction(ctx.db, { characterId, amount: 250, reason: "sell_loot", idempotencyKey: "simultaneo-1" }),
      ),
    );

    expect(new Set(results.map((result) => result.entryId)).size).toBe(1);
    expect(await walletAndLedger()).toEqual({ cash: 250, ledgerTotal: 250, entries: 1 });
  });

  it("rechaza reutilizar una clave con otro monto", async () => {
    await post({ characterId, amount: 500, reason: "sell_loot", idempotencyKey: "clave-unica-1" });
    const conflict = await post({ characterId, amount: 900, reason: "sell_loot", idempotencyKey: "clave-unica-1" });

    expect(conflict.statusCode).toBe(409);
    expect(conflict.json().error).toBe("idempotency_conflict");
    expect((await walletAndLedger()).cash).toBe(500);
  });

  it("no deja el saldo negativo", async () => {
    await post({ characterId, amount: 100, reason: "sell_loot", idempotencyKey: "venta-0002" });
    const response = await post({ characterId, amount: -101, reason: "shop_purchase", idempotencyKey: "compra-0002" });

    expect(response.statusCode).toBe(409);
    expect(response.json().error).toBe("insufficient_funds");
    expect(await walletAndLedger()).toEqual({ cash: 100, ledgerTotal: 100, entries: 1 });
  });

  it("acepta el salario del turno policial", async () => {
    const response = await post({ characterId, amount: 4500, reason: "police_salary", idempotencyKey: "turno-0001" });
    expect(response.statusCode).toBe(200);
    expect(response.json().balance).toBe(4500);
  });

  it("rechaza monto cero, motivo desconocido y personaje inexistente", async () => {
    expect((await post({ characterId, amount: 0, reason: "sell_loot", idempotencyKey: "cero-0001" })).statusCode).toBe(400);
    expect((await post({ characterId, amount: 10, reason: "regalo", idempotencyKey: "motivo-001" })).statusCode).toBe(400);
    expect((await post({ characterId: 99999, amount: 10, reason: "sell_loot", idempotencyKey: "nadie-0001" })).statusCode).toBe(404);
  });

  it("exige la clave de servidor: un cliente no puede darse dinero", async () => {
    const response = await ctx.app.inject({
      method: "POST",
      url: "/v1/economy/transactions",
      payload: { characterId, amount: 1_000_000, reason: "sell_loot", idempotencyKey: "trampa-0001" },
    });
    expect(response.statusCode).toBe(401);
    expect((await walletAndLedger()).cash).toBe(0);
  });

  it("registra en auditoría cada movimiento nuevo, no los reintentos", async () => {
    await post({ characterId, amount: 500, reason: "sell_loot", idempotencyKey: "audit-0001" });
    await post({ characterId, amount: 500, reason: "sell_loot", idempotencyKey: "audit-0001" });

    const audits = await ctx.db.query<{ count: number }>("SELECT COUNT(*)::int AS count FROM audit_log WHERE action = 'economy_transaction'");
    expect(audits.rows[0]!.count).toBe(1);
  });
});
