# Backend

API en Node.js + TypeScript (Fastify) con PostgreSQL, en la carpeta `backend/`. Guarda lo que tiene que sobrevivir a una desconexión: cuentas, personaje y dinero. También lleva la lista de servidores de juego vivos. Dónde encaja en el sistema: [ARQUITECTURA.md](ARQUITECTURA.md). Despliegue: [DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md).

Reglas que garantiza:
- **El cliente del juego nunca escribe.** Solo hace login y pide la lista de servidores. Todo lo demás lo pide el servidor de juego con su clave (`x-server-key`).
- **El dinero no se duplica.** Cada movimiento es una fila del ledger con una clave de idempotencia única. El saldo se actualiza en la misma transacción y la base no permite saldos negativos.
- **Todo movimiento queda auditado** en `audit_log`.
- **Las contraseñas nunca se guardan**: solo un hash scrypt (N = 2^17, recomendado por OWASP). Login y registro tienen límite de pedidos por IP, y la cuenta se bloquea 15 minutos tras 5 intentos fallidos. El error de login no revela si el usuario existe.

## Uso local

```bash
cd backend
npm install
cp .env.example .env     # completar JWT_SECRET y SERVER_API_KEY
npm run dev              # http://localhost:3000
npm test                 # 33 pruebas
```

Sin `DATABASE_URL` usa **PGlite** (PostgreSQL embebido) en `backend/data/`: no hace falta instalar Postgres para desarrollar. En producción, `DATABASE_URL` es obligatoria.

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | Conexión a PostgreSQL. Vacía = PGlite local |
| `JWT_SECRET` | Firma los tokens de sesión. Mínimo 32 caracteres |
| `SERVER_API_KEY` | Clave compartida con los servidores de juego. Mínimo 24 caracteres. Nunca va en el cliente |
| `AUTH_DEV_MODE` | `true` habilita entrar con un nombre, sin Steam. Prohibido en producción |
| `STEAM_WEB_API_KEY`, `STEAM_APP_ID` | Login con Steam (cuando exista la app en Steamworks) |
| `SESSION_TTL_SECONDS` | Duración del token del jugador. Por defecto 900 (15 min) |
| `SERVER_STALE_SECONDS` | Segundos sin heartbeat para dejar de listar un servidor. Por defecto 45 |
| `TRUST_PROXY` | `true` detrás de Caddy o Nginx, para tomar la IP real del jugador |
| `PASSWORD_SCRYPT_N` | Costo del hash. Por defecto 131072; en producción no se acepta menos de 65536 |
| `LOGIN_MAX_FAILED_ATTEMPTS`, `LOGIN_LOCK_MINUTES` | Bloqueo por intentos fallidos. Por defecto 5 intentos y 15 minutos |
| `AUTH_RATE_LIMIT_PER_MINUTE` | Pedidos de login o registro por minuto y por IP. Por defecto 10 |

En el VPS, la configuración la genera [infra/vps/setup-vps.sh](../infra/vps/setup-vps.sh) en `/etc/barrio/backend.env`.

## API

Errores: `{ "error": "<código>", "message": "<texto>" }` con el código HTTP correspondiente.

### Cliente del juego (sin clave)

| Método y ruta | Cuerpo | Respuesta |
| --- | --- | --- |
| `GET /health` | | `{ status: "ok" }` |
| `POST /v1/auth/register` | `{ username, password, email? }` | `{ token, expiresIn, accountId, characterId, name }` |
| `POST /v1/auth/login` | `{ username, password }` | igual que el registro |
| `POST /v1/auth/steam` | `{ ticket }` (hex del ticket de sesión de Steam) | igual que el registro |
| `POST /v1/auth/dev` | `{ name }` (solo con `AUTH_DEV_MODE`) | igual que Steam |
| `GET /v1/servers` | | `{ servers: [...], recommended }`: el más poblado con lugar |

### Servidor de juego (header `x-server-key`)

| Método y ruta | Cuerpo | Respuesta |
| --- | --- | --- |
| `POST /v1/servers/register` | `{ name, address, port, region, maxPlayers }` | servidor con su `id`. Al reiniciar con la misma dirección y puerto, reutiliza el `id` |
| `POST /v1/servers/:id/heartbeat` | `{ currentPlayers }` | servidor actualizado. Enviar cada 15 s |
| `POST /v1/sessions/verify` | `{ token }` del jugador que se conecta | perfil: `{ accountId, characterId, name, status, cash }` |
| `GET /v1/characters/:accountId` | | perfil |
| `POST /v1/economy/transactions` | `{ characterId, amount, reason, idempotencyKey, serverId? }` | `{ entryId, amount, balance, replayed }` |

`reason`: `sell_loot`, `arrest_reward`, `police_salary` (salario del turno policial), `shop_purchase`, `admin_adjustment`. `amount` positivo cobra, negativo paga.

Errores de economía: `insufficient_funds` (409), `idempotency_conflict` (409, misma clave con otros datos).

### Flujo de conexión

1. El cliente se registra o hace login (`/v1/auth/register` o `/v1/auth/login`) y recibe un `token` de 15 minutos.
2. Pide `/v1/servers` y se conecta al `recommended`, pasando el token en la URL de conexión.
3. El servidor de juego llama a `/v1/sessions/verify` antes de aceptarlo. Si falla, lo rechaza.
4. Cuando el jugador vende botín, el servidor llama a `/v1/economy/transactions` con una clave única (por ejemplo `venta-<servidor>-<jugador>-<contador>`). Si la red falla, reintenta con la misma clave sin riesgo de pagar dos veces.

## Estructura

```
src/
  app.ts          Rutas y validación (zod)
  auth.ts         Tokens de sesión, clave de servidor, verificación de Steam
  passwords.ts    Hash y verificación de contraseñas (scrypt)
  config.ts       Variables de entorno validadas
  db.ts           PostgreSQL / PGlite y migraciones
  services/       accounts, credentials, economy, servers
  server.ts       Arranque
migrations/       SQL versionado, se aplica solo al arrancar
test/             Pruebas con PGlite en memoria
```

