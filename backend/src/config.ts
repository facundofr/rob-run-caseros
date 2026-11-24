import { z } from "zod";

const booleanFromEnv = z
  .enum(["true", "false", "1", "0"])
  .default("false")
  .transform((value) => value === "true" || value === "1");

const configSchema = z.object({
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  HOST: z.string().default("0.0.0.0"),
  PORT: z.coerce.number().int().min(1).max(65535).default(3000),

  /** Sin DATABASE_URL se usa PGlite en ./data (solo para desarrollo). */
  DATABASE_URL: z.string().optional(),

  /** Firma los tokens de sesión de los jugadores. */
  JWT_SECRET: z.string().min(32, "JWT_SECRET debe tener al menos 32 caracteres"),

  /** Clave compartida con los servidores de juego. Nunca se entrega a los clientes. */
  SERVER_API_KEY: z.string().min(24, "SERVER_API_KEY debe tener al menos 24 caracteres"),

  /** Permite entrar con un nombre, sin Steam. Solo para desarrollo y pruebas internas. */
  AUTH_DEV_MODE: booleanFromEnv,

  STEAM_WEB_API_KEY: z.string().optional(),
  STEAM_APP_ID: z.string().optional(),

  /** Segundos sin heartbeat tras los cuales un servidor de juego deja de listarse. */
  SERVER_STALE_SECONDS: z.coerce.number().int().min(5).default(45),

  /** Duración del token de sesión del jugador, en segundos. */
  SESSION_TTL_SECONDS: z.coerce.number().int().min(60).default(900),
});

export type Config = z.infer<typeof configSchema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const config = configSchema.parse(env);

  if (config.NODE_ENV === "production") {
    if (config.AUTH_DEV_MODE) {
      throw new Error("AUTH_DEV_MODE no se puede activar en producción.");
    }
    if (!config.DATABASE_URL) {
      throw new Error("DATABASE_URL es obligatoria en producción.");
    }
  }
  return config;
}
