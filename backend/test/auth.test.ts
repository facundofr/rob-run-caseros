import { afterEach, describe, expect, it } from "vitest";
import { createTestApp, devLogin, serverHeaders, type TestContext } from "./helpers.js";

let ctx: TestContext;

afterEach(async () => {
  await ctx.app.close();
  await ctx.db.close();
});

describe("login", () => {
  it("crea cuenta, personaje y billetera en el primer login, y reutiliza la cuenta después", async () => {
    ctx = await createTestApp();
    const first = await devLogin(ctx.app, "Facu");
    const second = await devLogin(ctx.app, "facu");

    expect(second.accountId).toBe(first.accountId);
    expect(second.characterId).toBe(first.characterId);

    const wallets = await ctx.db.query<{ cash: number }>("SELECT cash FROM wallets WHERE character_id = $1", [first.characterId]);
    expect(wallets.rows).toEqual([{ cash: 0 }]);
  });

  it("no expone el login de desarrollo si AUTH_DEV_MODE está apagado", async () => {
    ctx = await createTestApp({ AUTH_DEV_MODE: "false" });
    const response = await ctx.app.inject({ method: "POST", url: "/v1/auth/dev", payload: { name: "Facu" } });
    expect(response.statusCode).toBe(404);
  });

  it("rechaza nombres inválidos", async () => {
    ctx = await createTestApp();
    const response = await ctx.app.inject({ method: "POST", url: "/v1/auth/dev", payload: { name: "<script>" } });
    expect(response.statusCode).toBe(400);
  });

  it("acepta un ticket de Steam válido y rechaza uno inválido", async () => {
    ctx = await createTestApp();
    const ok = await ctx.app.inject({ method: "POST", url: "/v1/auth/steam", payload: { ticket: "aaaaaaaaaaaaaaaa0123456789" } });
    expect(ok.statusCode).toBe(200);
    expect(ok.json().token).toBeTypeOf("string");

    const bad = await ctx.app.inject({ method: "POST", url: "/v1/auth/steam", payload: { ticket: "deadbeefdeadbeef00" } });
    expect(bad.statusCode).toBe(401);
  });

  it("no deja entrar a una cuenta suspendida", async () => {
    ctx = await createTestApp();
    const player = await devLogin(ctx.app, "Tramposo");
    await ctx.db.query("UPDATE accounts SET status = 'banned' WHERE id = $1", [player.accountId]);

    const response = await ctx.app.inject({ method: "POST", url: "/v1/auth/dev", payload: { name: "Tramposo" } });
    expect(response.statusCode).toBe(403);
  });
});

describe("verificación de sesión por el servidor de juego", () => {
  it("devuelve el perfil para un token válido", async () => {
    ctx = await createTestApp();
    const player = await devLogin(ctx.app, "Facu");

    const response = await ctx.app.inject({
      method: "POST",
      url: "/v1/sessions/verify",
      headers: serverHeaders,
      payload: { token: player.token },
    });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toMatchObject({ accountId: player.accountId, characterId: player.characterId, cash: 0, status: "active" });
  });

  it("rechaza un token alterado", async () => {
    ctx = await createTestApp();
    const player = await devLogin(ctx.app, "Facu");
    const tampered = player.token.slice(0, -4) + (player.token.endsWith("AAAA") ? "BBBB" : "AAAA");

    const response = await ctx.app.inject({
      method: "POST",
      url: "/v1/sessions/verify",
      headers: serverHeaders,
      payload: { token: tampered },
    });
    expect(response.statusCode).toBe(401);
  });

  it("exige la clave de servidor", async () => {
    ctx = await createTestApp();
    const player = await devLogin(ctx.app, "Facu");

    const noKey = await ctx.app.inject({ method: "POST", url: "/v1/sessions/verify", payload: { token: player.token } });
    const wrongKey = await ctx.app.inject({
      method: "POST",
      url: "/v1/sessions/verify",
      headers: { "x-server-key": "otra-clave-cualquiera-0123456789" },
      payload: { token: player.token },
    });
    expect(noKey.statusCode).toBe(401);
    expect(wrongKey.statusCode).toBe(401);
  });

  it("rechaza tokens firmados con otro secreto", async () => {
    ctx = await createTestApp();
    const other = await createTestApp({ JWT_SECRET: "otro-secreto-distinto-0123456789abcdefghij" });
    const foreign = await devLogin(other.app, "Facu");
    await other.app.close();
    await other.db.close();

    const response = await ctx.app.inject({
      method: "POST",
      url: "/v1/sessions/verify",
      headers: serverHeaders,
      payload: { token: foreign.token },
    });
    expect(response.statusCode).toBe(401);
  });
});
