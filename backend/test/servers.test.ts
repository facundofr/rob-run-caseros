import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createTestApp, serverHeaders, type TestContext } from "./helpers.js";

let ctx: TestContext;

beforeEach(async () => {
  ctx = await createTestApp();
});

afterEach(async () => {
  await ctx.app.close();
  await ctx.db.close();
});

async function register(name: string, port: number, maxPlayers = 16) {
  const response = await ctx.app.inject({
    method: "POST",
    url: "/v1/servers/register",
    headers: serverHeaders,
    payload: { name, address: "203.0.113.10", port, region: "sa-east", maxPlayers },
  });
  expect(response.statusCode).toBe(200);
  return response.json() as { id: string };
}

const beat = (id: string, currentPlayers: number) =>
  ctx.app.inject({ method: "POST", url: `/v1/servers/${id}/heartbeat`, headers: serverHeaders, payload: { currentPlayers } });

const list = async () => (await ctx.app.inject({ method: "GET", url: "/v1/servers" })).json() as {
  servers: { id: string; currentPlayers: number }[];
  recommended: { id: string } | null;
};

describe("servidores de juego", () => {
  it("recomienda el servidor más poblado que tenga lugar", async () => {
    const empty = await register("Caseros 1", 7777);
    const busy = await register("Caseros 2", 7778);
    const full = await register("Caseros 3", 7779, 4);

    await beat(empty.id, 1);
    await beat(busy.id, 9);
    await beat(full.id, 4);

    const result = await list();
    expect(result.servers.map((server) => server.id)).toEqual([busy.id, full.id, empty.id]);
    expect(result.recommended?.id).toBe(busy.id);
  });

  it("deja de listar servidores sin heartbeat reciente", async () => {
    const alive = await register("Vivo", 7777);
    const dead = await register("Caído", 7778);
    await ctx.db.query("UPDATE game_servers SET last_heartbeat = now() - interval '5 minutes' WHERE id = $1", [dead.id]);

    const result = await list();
    expect(result.servers.map((server) => server.id)).toEqual([alive.id]);
  });

  it("reutiliza el registro si el mismo servidor se reinicia", async () => {
    const first = await register("Caseros 1", 7777);
    await beat(first.id, 12);
    const again = await register("Caseros 1", 7777);

    expect(again.id).toBe(first.id);
    expect((await list()).servers).toEqual([expect.objectContaining({ id: first.id, currentPlayers: 0 })]);
  });

  it("no acepta más jugadores que el máximo", async () => {
    const server = await register("Chico", 7777, 4);
    const response = await beat(server.id, 50);
    expect(response.json().currentPlayers).toBe(4);
  });

  it("exige la clave de servidor para registrarse y devuelve 404 para un id desconocido", async () => {
    const noKey = await ctx.app.inject({
      method: "POST",
      url: "/v1/servers/register",
      payload: { name: "Pirata", address: "1.2.3.4", port: 7777, region: "sa-east", maxPlayers: 16 },
    });
    expect(noKey.statusCode).toBe(401);
    expect((await beat("00000000-0000-4000-8000-000000000000", 1)).statusCode).toBe(404);
  });
});
