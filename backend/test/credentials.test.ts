import { afterEach, describe, expect, it } from "vitest";
import { createTestApp, createTestAppOn, serverHeaders, type TestContext } from "./helpers.js";

let ctx: TestContext;

afterEach(async () => {
  await ctx.app.close();
  await ctx.db.close();
});

const register = (payload: Record<string, unknown>) => ctx.app.inject({ method: "POST", url: "/v1/auth/register", payload });
const login = (username: string, password: string, app = ctx.app) =>
  app.inject({ method: "POST", url: "/v1/auth/login", payload: { username, password } });

const goodPassword = "caseros-2026-oeste";

describe("registro con usuario y contraseña", () => {
  it("crea la cuenta y devuelve una sesión que el servidor de juego acepta", async () => {
    ctx = await createTestApp();
    const response = await register({ username: "Facu_10", password: goodPassword, email: "facu@example.com" });
    expect(response.statusCode).toBe(200);

    const session = response.json();
    const verify = await ctx.app.inject({
      method: "POST",
      url: "/v1/sessions/verify",
      headers: serverHeaders,
      payload: { token: session.token },
    });
    expect(verify.json()).toMatchObject({ accountId: session.accountId, name: "Facu_10", steamId: null, cash: 0 });
  });

  it("nunca guarda la contraseña: solo el hash scrypt con sus parámetros", async () => {
    ctx = await createTestApp();
    await register({ username: "Facu", password: goodPassword });
    const stored = (await ctx.db.query<{ password_hash: string }>("SELECT password_hash FROM credentials")).rows[0]!.password_hash;

    expect(stored.startsWith("scrypt$1024$8$1$")).toBe(true);
    expect(stored).not.toContain(goodPassword);
  });

  it("rechaza usuario o email repetidos, sin importar mayúsculas", async () => {
    ctx = await createTestApp();
    await register({ username: "Facu", password: goodPassword, email: "facu@example.com" });

    const sameUser = await register({ username: "FACU", password: goodPassword });
    const sameEmail = await register({ username: "Otro", password: goodPassword, email: "FACU@example.com" });
    expect(sameUser.statusCode).toBe(409);
    expect(sameUser.json().error).toBe("username_taken");
    expect(sameEmail.statusCode).toBe(409);
    expect(sameEmail.json().error).toBe("email_taken");
  });

  it("explica por qué rechaza datos inválidos", async () => {
    ctx = await createTestApp();
    const cases = [
      [{ username: "ab", password: goodPassword }, "El usuario debe tener entre 3 y 20 caracteres"],
      [{ username: "facu loco", password: goodPassword }, "El usuario solo puede tener letras, números, punto, guion y guion bajo"],
      [{ username: "Facu", password: "corta" }, "La contraseña debe tener al menos 10 caracteres"],
      [{ username: "Facu", password: "soyfacu12345" }, "La contraseña no puede contener el nombre de usuario"],
      [{ username: "Facu", password: goodPassword, email: "no-es-email" }, "Email inválido"],
    ] as const;

    for (const [payload, message] of cases) {
      const response = await register(payload);
      expect(response.statusCode).toBe(400);
      expect(response.json().message).toBe(message);
    }
  });
});

describe("login con usuario y contraseña", () => {
  it("entra con la contraseña correcta, sin importar mayúsculas en el usuario", async () => {
    ctx = await createTestApp();
    const created = (await register({ username: "Facu", password: goodPassword })).json();

    const response = await login("facu", goodPassword);
    expect(response.statusCode).toBe(200);
    expect(response.json().accountId).toBe(created.accountId);
  });

  it("da el mismo error para contraseña incorrecta y para usuario inexistente", async () => {
    ctx = await createTestApp();
    await register({ username: "Facu", password: goodPassword });

    const wrongPassword = await login("Facu", "otra-contraseña-123");
    const noUser = await login("NoExiste", goodPassword);
    expect(wrongPassword.statusCode).toBe(401);
    expect(noUser.statusCode).toBe(401);
    expect(wrongPassword.json()).toEqual(noUser.json());
  });

  it("bloquea la cuenta tras 5 intentos fallidos, incluso con la contraseña correcta", async () => {
    ctx = await createTestApp();
    await register({ username: "Facu", password: goodPassword });

    for (let attempt = 0; attempt < 5; attempt++) {
      expect((await login("Facu", "adivinando-123")).statusCode).toBe(401);
    }
    const locked = await login("Facu", goodPassword);
    expect(locked.statusCode).toBe(429);
    expect(locked.json().error).toBe("account_locked");

    // Pasado el bloqueo, la contraseña correcta funciona y el contador vuelve a cero.
    await ctx.db.query("UPDATE credentials SET locked_until = now() - interval '1 minute'");
    expect((await login("Facu", goodPassword)).statusCode).toBe(200);
    const attempts = (await ctx.db.query<{ failed_attempts: number }>("SELECT failed_attempts FROM credentials")).rows[0]!;
    expect(attempts.failed_attempts).toBe(0);
  });

  it("limita los pedidos por IP", async () => {
    ctx = await createTestApp({ AUTH_RATE_LIMIT_PER_MINUTE: "3" });
    for (let attempt = 0; attempt < 3; attempt++) {
      await login("Nadie", goodPassword);
    }
    const limited = await login("Nadie", goodPassword);
    expect(limited.statusCode).toBe(429);
    expect(limited.json().error).toBe("rate_limited");
  });

  it("no deja entrar a una cuenta suspendida", async () => {
    ctx = await createTestApp();
    const created = (await register({ username: "Tramposo", password: goodPassword })).json();
    await ctx.db.query("UPDATE accounts SET status = 'banned' WHERE id = $1", [created.accountId]);

    expect((await login("Tramposo", goodPassword)).statusCode).toBe(403);
  });

  it("actualiza el hash al subir el costo de scrypt, en el próximo login correcto", async () => {
    ctx = await createTestApp();
    await register({ username: "Facu", password: goodPassword });

    const stronger = await createTestAppOn(ctx.db, { PASSWORD_SCRYPT_N: "2048" });
    expect((await login("Facu", goodPassword, stronger)).statusCode).toBe(200);
    await stronger.close();

    const stored = (await ctx.db.query<{ password_hash: string }>("SELECT password_hash FROM credentials")).rows[0]!.password_hash;
    expect(stored.startsWith("scrypt$2048$8$1$")).toBe(true);
    expect((await login("Facu", goodPassword)).statusCode).toBe(200);
  });
});
