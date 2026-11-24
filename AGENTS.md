# Guía para asistentes de IA: Barrio

Este archivo es el punto de entrada para cualquier IA que trabaje en este repositorio (Claude Code, Copilot, Cursor u otra). Leerlo completo antes de actuar. Las respuestas al usuario van en **español**.

## Qué es el proyecto

**Barrio** (nombre de trabajo) es un juego multijugador de mundo abierto en tercera persona, ambientado en Caseros (Zona Oeste del conurbano bonaerense). Los jugadores son vecinos, ladrones o policías en servidores de 16 jugadores. Lo hacen una persona que programa a tiempo parcial y un diseñador.

| Parte | Tecnología | Carpeta |
| --- | --- | --- |
| Juego (cliente y servidor dedicado) | Unreal Engine 5, C++ | `game/` |
| Backend (cuentas, dinero, lista de servidores) | Node.js 24 + TypeScript (Fastify), PostgreSQL | `backend/` |
| Despliegue | VPS Hostinger KVM 2 (Brasil), Ubuntu, dominio `facundofr.com` | `infra/vps/` |
| Documentación | Markdown | `docs/` |

## Estado real (leer antes de prometer nada)

| Parte | Estado |
| --- | --- |
| Backend | **Funciona y está probado**: 33 pruebas (`cd backend && npm test`) y una prueba manual por HTTP |
| Scripts del VPS | Escritos y revisados de sintaxis, **nunca ejecutados en el VPS real** |
| Código de Unreal (etapas 1, 6 y 6b del plan) | **Escrito pero NUNCA compilado.** Se escribió en una notebook sin Unreal. Es esperable que la primera compilación dé errores: corregirlos es la primera tarea en la PC de desarrollo |
| Arte | Solo mapa gris generado por código. El encargo de arte está en `docs/ARTE_BRIEF.md` |

## Documentos clave

| Archivo | Para qué |
| --- | --- |
| [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | Plan de acción: etapas, estado, criterios de cierre |
| [docs/GAME_DESIGN_DOCUMENT.md](docs/GAME_DESIGN_DOCUMENT.md) | **Reglas del juego** (roles, captura, recompensas). Es la fuente de verdad: el código se ajusta a este documento |
| [docs/FASE0_INFORME.md](docs/FASE0_INFORME.md) | Arquitectura y decisiones técnicas |
| [README.md](README.md) | Compilar el juego, armar el mapa en el editor, lista de pruebas |
| [infra/vps/README.md](infra/vps/README.md) | Despliegue en el VPS, paso a paso |
| [backend/README.md](backend/README.md) | API del backend y variables de entorno |
| [docs/ARTE_BRIEF.md](docs/ARTE_BRIEF.md) | Encargo de arte para el diseñador o artistas |
| [CHANGELOG.md](CHANGELOG.md) | Cambios por etapa |

## Cómo levantar todo: orden de pasos

Seguir este orden. Cada paso remite al documento con el detalle; no inventar pasos que no estén ahí. Si algo falla, diagnosticar con el log antes de cambiar código.

### Paso 1: Backend en el VPS (no depende de Unreal)

Detalle: [infra/vps/README.md](infra/vps/README.md), secciones 1 a 3.

1. **DNS:** en el panel del dominio `facundofr.com`, crear dos registros **A** con la IP pública del VPS: `caseros-api` y `caseros`. El subdominio `api` **ya está en uso** por otro servicio del VPS: no tocarlo.
2. **Revisar qué corre en el VPS** antes de instalar nada: `systemctl is-active nginx caddy apache2` y `ss -tlnp`. El VPS tiene otros servicios en producción. El script convive con Nginx o Caddy sin pisar otros sitios, se detiene con Apache, y no activa el firewall si está apagado.
3. **Instalar** (por SSH, como root):
   ```bash
   git clone https://github.com/facundofr/rob-run-caseros.git /opt/barrio/repo
   bash /opt/barrio/repo/infra/vps/setup-vps.sh
   ```
   Variables opcionales: `API_DOMAIN`, `GAME_DOMAIN`, `BACKEND_PORT` (por defecto 3100), `CERTBOT_EMAIL`.
4. **Comprobar** desde otra PC: `curl https://caseros-api.facundofr.com/health` tiene que devolver `{"status":"ok"}`.
5. **Probar el login** registrando una cuenta: `POST /v1/auth/register` (ver `backend/README.md`).
6. **Actualizar más adelante:** `bash /opt/barrio/repo/infra/vps/deploy-backend.sh`.

Los secretos quedan en el VPS, en `/etc/barrio/backend.env` y `/etc/barrio/gameserver.env`. **Nunca copiarlos al repositorio ni a un chat.**

### Paso 2: Compilar el juego en la PC de desarrollo

Detalle: [README.md](README.md), secciones "Requisitos", "Primera vez: compilar y abrir" y "Armar el contenido en el editor".

PC de desarrollo: Ryzen 7 5700X, 32 GB de RAM, RTX 5050 de 8 GB. Necesita al menos 150 GB libres, y 500 GB para el paso 3.

1. Instalar Unreal Engine 5.x (Epic Launcher), Visual Studio 2022 con "Desarrollo de juegos con C++", Git y Git LFS.
2. Clonar el repo, generar los archivos de Visual Studio desde `game/Barrio.uproject` y compilar **Development Editor / Win64**.
3. **Corregir los errores de compilación**: el código nunca se compiló. Trabajar módulo por módulo, en este orden de dependencias: `BarrioCore` → `BarrioCombat` → `BarrioCharacters` → `BarrioWorld` → `BarrioOnline` → `BarrioUI` → `Barrio`.
4. Armar en el editor el Blueprint del personaje, el del GameMode y el mapa `L_Greybox`, con los actores y las coordenadas de la tabla del README.
5. Pasar la lista de pruebas del README con 3 jugadores en el editor (**Play As Client**).

### Paso 3: Servidor de juego en el VPS

Detalle: [infra/vps/README.md](infra/vps/README.md), sección 4.

1. Compilar Unreal **desde el código fuente** (el del Launcher no genera servidores dedicados), de la misma versión que el proyecto. Instalar además el toolchain de compilación cruzada para Linux.
2. Empaquetar el target `BarrioServer` para Linux.
3. Subir el resultado a `/opt/barrio/server/` y arrancarlo con `systemctl enable --now barrio-server`. Lee `/etc/barrio/gameserver.env`: con esa configuración se registra en el backend y exige login.
4. Conectarse con un cliente empaquetado en Development: aparece la pantalla de login y después entra solo a `caseros.facundofr.com:7777`.
5. Hacer la prueba "Cuentas y dinero guardado" del README.

### Paso 4 en adelante

Seguir [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md): bots policía, inventario, moto, arte y alpha cerrada.

## Reglas de trabajo en este repo

- **Subir cada cambio a GitHub:** commit con mensaje en español y push a `main` del repo `facundofr/rob-run-caseros`. El repositorio es **público**: nunca subir secretos (`.env`, claves, IPs privadas, contraseñas).
- **No escribir más código de Unreal sin compilar** mientras no se haya compilado lo existente. Ya hay cuatro etapas sin compilar.
- **Dependencias entre módulos de Unreal:** todos dependen de `BarrioCore`, que no depende de ningún otro. Nadie depende de `BarrioUI`. Solo el módulo principal `Barrio` (GameMode) depende de todos. Los sistemas se comunican por eventos de `UBarrioGameEvents` y las reglas viven en el GameMode.
- **Servidor autoritativo:** el cliente pide y el servidor valida y decide (dinero, daño, botín, roles, arrestos). La plata solo se mueve con el backend, mediante transacciones idempotentes.
- **Identidad propia:** Barrio toma mecánicas del género, pero no copia nombres, personajes, objetos, valores de balance ni estética de otros juegos (en particular de ROB RUN). Los análisis de mercado están en `docs/referencias/`, que está en `.gitignore` y no se publica.
- **Nada de marcas reales** en el arte, y una policía ficticia.
- **Documentación al día:** al cambiar una regla del juego, actualizar `docs/GAME_DESIGN_DOCUMENT.md`. Al terminar una etapa, actualizar `docs/DEVELOPMENT_ROADMAP.md` y `CHANGELOG.md`.

## Comandos útiles

| Para | Comando |
| --- | --- |
| Pruebas del backend | `cd backend && npm install && npm test` |
| Backend local (PGlite, sin Postgres) | `cd backend && cp .env.example .env && npm run dev` |
| Estado de los servicios en el VPS | `systemctl status barrio-backend barrio-server` |
| Logs en el VPS | `journalctl -u barrio-backend -f` / `journalctl -u barrio-server -f` |
| Clave para el servidor de juego (en el VPS) | `grep SERVER_API_KEY /etc/barrio/backend.env` |
