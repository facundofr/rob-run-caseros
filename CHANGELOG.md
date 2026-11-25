# Changelog

## [Sin publicar] Etapa 4: primera compilación

El editor (`BarrioEditor`, Win64, Development) compila sin errores ni advertencias con Unreal Engine 5.8.4 y Visual Studio 2022 (17.14).

### Corregido
- `ASafeZone` pasa a llamarse `ABarrioSafeZone`: chocaba con `USafeZone` de UMG. En el editor se busca como `BarrioSafeZone`.
- `ABarrioGameMode::ShouldSpawnAtStartSpot`: en 5.8 es una función virtual común, sin `_Implementation`.
- `ABarrioGameMode::GetPoliceQuota`: cuenta los jugadores humanos a mano, porque `GetNumPlayers()` del motor no es `const`.
- `Barrio.uproject` queda asociado a la versión 5.8 del motor.

## [Sin publicar] Entornos de trabajo

- `docs/ENTORNOS.md`: dos lugares de trabajo unidos por GitHub. En la PC de desarrollo va todo lo de Unreal; en el VPS, por VS Code Remote-SSH con Claude Code, van el backend, los despliegues y los logs. Incluye la preparación del VPS (usuario con clave SSH, herramientas, copia de trabajo, VS Code y Claude Code) y las precauciones por los servicios en producción.
- `AGENTS.md`: cómo detectar en qué entorno está la IA y qué puede hacer en cada uno.

## [Sin publicar] Documentación reorganizada

- Un archivo por tema, todos en `docs/`: `PLAN`, `DISENO_JUEGO`, `ARQUITECTURA`, `GUIA_DESARROLLO`, `PRUEBAS`, `DESPLIEGUE_VPS`, `BACKEND`, `ARTE`. El README quedó como portada e índice, y `AGENTS.md` como guía para asistentes de IA.
- `FASE0_INFORME.md` se dividió: la arquitectura pasó a `ARQUITECTURA.md` (actualizada a lo implementado, con el diagrama en Mermaid), la ambientación a `DISENO_JUEGO.md`, y el equipo, la estimación y los riesgos a `PLAN.md`.
- `DESPLIEGUE_VPS.md` suma la sección "Qué se instala en el VPS".

## [Sin publicar] Etapa 6b: reglas de roles v2

Código escrito, pendiente de compilar. Implementa `docs/DISENO_JUEGO.md`.

### Agregado
- Rol **ladrón**: el vecino se pone el pasamontañas (G, 2 s, fuera de zona segura) y deja de serlo solo al cruzar una salida del barrio (`AExitZone`).
- `ASafeZone`: sin daño y sin pasamontañas adentro.
- Regla central de daño (`UBarrioGameEvents::CanDamage`): vecinos sin armas, la policía solo daña ladrones, protección de 10 s al reaparecer como policía.
- Captura: rendirse (Q), orden de rendición del policía (Q, +20 % en el arresto), esposar (E, 2,5 s) a un ladrón rendido o reducido; el arresto confisca el botín.
- Salario policial acumulado en el turno: arresto $1.500 + 10 % del botín, abatir $300, matar a un rendido $0. Se cobra al terminar el turno o al desconectarse.
- Notoriedad: cada robo seguido vale +10 % (hasta +50 %).
- Nivel de búsqueda solo por violencia (+1 por vecino muerto, máximo 3); en nivel 3 toda la ciudad ve al ladrón.
- Barrio gris con 40 m de terreno "Afuera" para el reducidor.
- Backend: motivo `police_salary` (33 pruebas).
- `docs/ARTE.md`: encargo de arte (prioridades, especificaciones técnicas, quién hace qué).

### Cambiado
- La alarma ya no pone al ladrón como buscado: solo marca dónde ocurre el robo.
- Morir como ladrón: se pierde todo y se reaparece como vecino; ya no lleva a la cárcel.
- El reducidor solo le compra a vecinos (hay que salir del barrio primero).
- La comisaría: "entrar de servicio" o "terminar el turno y cobrar".

## [Sin publicar] Etapa 6: Unreal conectado al backend

Código escrito, pendiente de compilar.

### Agregado
- Módulo `BarrioOnline`: cliente HTTP con JSON, `UBarrioAuthSubsystem` (login, registro, servidor recomendado, conexión con token) y `UBarrioServerBackend` (registro de la instancia, heartbeat, verificación de sesión, movimientos de dinero con reintento idempotente).
- `SBarrioLoginScreen`: pantalla de login y registro en Slate, sin assets.
- GameMode: con backend activo nadie entra sin sesión válida; el personaje aparece recién cuando el backend confirma la sesión. Una cuenta, una conexión.
- Venta al reducidor y recompensa por captura guardadas en el backend; si la venta falla, el botín vuelve al jugador.
- Project Settings → Game → Barrio Online (URL del backend, servidor por defecto, login en el editor).

### Cambiado
- El reducidor ya no paga directamente: emite `OnSellLootRequested` y el GameMode resuelve la venta.
- Subdominios: `caseros-api.facundofr.com` (API) y `caseros.facundofr.com` (juego).
- `setup-vps.sh` convive con servicios existentes: Node propio, puerto 3100, Nginx o Caddy sin reemplazar otros sitios, sin activar el firewall.

## [Sin publicar] Login con usuario y contraseña, y despliegue en el VPS

### Agregado
- `POST /v1/auth/register` y `POST /v1/auth/login`: cuentas con usuario, contraseña y email opcional.
- Contraseñas con hash scrypt (N = 2^17); rehash automático si se sube el costo.
- Protección contra fuerza bruta: límite de pedidos por IP y bloqueo de 15 minutos tras 5 intentos fallidos. El error no revela si el usuario existe.
- Mensajes de validación en español, listos para mostrar en la pantalla de login.
- `TRUST_PROXY` para tomar la IP real del jugador detrás de Caddy.
- `infra/vps/setup-vps.sh` y `deploy-backend.sh`: instalación y actualización en el VPS (`caseros-api.facundofr.com` con HTTPS, PostgreSQL, firewall, servicios).
- `docs/PLAN.md`: plan de acción hasta el MVP.
- 10 pruebas nuevas (32 en total).

### Cambiado
- El MVP usa login con usuario y contraseña; Steam queda como vinculación posterior.

## [Sin publicar] Fase 4: backend

Probado en esta máquina: 22 pruebas automáticas y prueba manual del flujo completo por HTTP.

### Agregado
- `backend/`: API en Node.js + TypeScript (Fastify) con PostgreSQL, o PGlite embebido para desarrollo y pruebas.
- Cuentas con login por Steam (validación del ticket con la Web API) y login de desarrollo con nombre.
- Tokens de sesión firmados de 15 minutos, verificados por el servidor de juego.
- Economía con ledger: idempotente, sin saldos negativos, sin duplicación con pedidos simultáneos, auditada.
- Registro de servidores de juego con heartbeat y recomendación del más poblado con lugar.
- Migraciones SQL versionadas.

## [Sin publicar] MVP 0: robo, alarma y policía

Código escrito, pendiente de primera compilación y de las pruebas del README.

### Agregado
- Módulo `BarrioCombat`: vida replicada y pistola hitscan con validación en el servidor (cadencia, munición, punto de vista y dirección). Disparo con clic izquierdo y recarga con R.
- `ABarrioPlayerState`: rol, nivel de buscado (0 a 5), dinero, botín encima, cárcel y progreso de robo.
- `ABarrioPlayerController`: avisos de alarma solo para policías y mensajes en pantalla.
- `UBarrioGameEvents`: canal de eventos del servidor (alarma, daño, muerte, arresto, cambio de rol).
- `ABarrioGameMode` con las reglas: cupo de policías, nivel de buscado y su descenso, arresto, cárcel, recompensas, reaparición por rol.
- `ALootPoint`: puerta robable con 3 niveles de botín, robo con duración, modo sigilo agachado, alarma con demora, reposición a los 5 minutos. El barrio gris crea una en cada casa.
- `AFenceStation` (reducidor), `APoliceStation` (comisaría) y `AJailCell` (celda).
- El personaje se puede arrestar: un policía que mira de cerca a un sospechoso buscado ve "Arrestar".
- Muerte con ragdoll y reaparición a los 5 segundos.
- HUD: panel de rol, buscado, botín, dinero, vida y balas; barra de robo; cuenta de la cárcel; marcas de POLICÍA y BUSCADO sobre otros jugadores; alarmas para la policía.
- Target `BarrioServer` para servidor dedicado, mapas por defecto, `MaxPlayers=16` y guía de despliegue en el VPS (`infra/vps`).

### Cambiado
- `IInteractable::GetInteractionText` recibe a quien mira, porque el texto depende de su rol.
- La detección de interacción busca por tipo de objeto para incluir a otros personajes.

### Diferido respecto del informe
- Gameplay Ability System: el MVP 0 usa el daño simple del motor. GAS entra con armaduras y más armas.
- Bots policía, inventario por ranuras, vehículos y backend quedan para el MVP completo.
- Compensación de latencia en los disparos.

## [Sin publicar] Fase 1: prototipo

Código escrito, pendiente de primera compilación y de las pruebas del README.

### Agregado
- Proyecto de Unreal `Barrio` con 5 módulos de C++: `Barrio`, `BarrioCore`, `BarrioCharacters`, `BarrioWorld`, `BarrioUI`.
- Personaje en tercera persona: caminar, correr, saltar, agacharse. Cámara con brazo.
- Sprint predicho en red dentro del movimiento del personaje, validado por el servidor.
- Controles por defecto creados desde código (Enhanced Input), reemplazables por assets.
- Interfaz `IInteractable` e interacción autoritativa: el cliente pide, el servidor valida distancia y frecuencia, y ejecuta.
- `InteractableTestActor`: interruptor de prueba con estado replicado.
- `GreyboxNeighborhood`: generador de barrio en gris configurable (por defecto, 4 manzanas de 100 m con casas, veredas y medianeras).
- HUD mínimo: mira, aviso de interacción y línea de estado (rol de red, velocidad, estado).
- Git LFS con bloqueo para assets de Unreal.

### Cambiado respecto del informe de la Fase 0
- El GameMode pasa del módulo base a un módulo principal (`Barrio`) para que el módulo base no dependa de ningún otro sistema.
- Los módulos de sistemas futuros se crean al iniciar su fase, no vacíos de antemano.
