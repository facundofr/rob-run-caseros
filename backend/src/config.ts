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

  /** Costo de scrypt (potencia de 2). 131072 = 2^17, recomendado por OWASP. Solo las pruebas lo bajan. */
  PASSWORD_SCRYPT_N: z.coerce
    .number()
    .int()
    .refine((value) => value >= 1024 && (value & (value - 1)) === 0, "PASSWORD_SCRYPT_N debe ser potencia de 2 y al menos 1024")
    .default(131072),

  /** Intentos fallidos seguidos antes de bloquear la cuenta, y minutos de bloqueo. */
  LOGIN_MAX_FAILED_ATTEMPTS: z.coerce.number().int().min(3).default(5),
  LOGIN_LOCK_MINUTES: z.coerce.number().int().min(1).default(15),

  /** true cuando el backend está detrás de un proxy (Caddy): toma la IP real del header X-Forwarded-For. */
  TRUST_PROXY: booleanFromEnv,

  /** Pedidos de login/registro por minuto y por IP. */
  AUTH_RATE_LIMIT_PER_MINUTE: z.coerce.number().int().min(1).default(10),
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
    if (config.PASSWORD_SCRYPT_N < 65536) {
      throw new Error("PASSWORD_SCRYPT_N es demasiado bajo para producción (mínimo 65536).");
    }
  }
  return config;
}
