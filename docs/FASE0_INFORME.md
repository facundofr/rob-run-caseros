# Fase 0 — Informe de arquitectura

24 de noviembre de 2026

## Resumen ejecutivo

Recomendación: construir en **Unreal Engine 5**, con servidor dedicado autoritativo de **16 jugadores** (4 policías + 12 civiles/ladrones) y backend propio en **TypeScript + PostgreSQL**. El MVP será un barrio chico donde cada casa se puede saquear y tiene alarma que avisa a la policía de la zona.

La visión completa del master prompt (clanes, territorios, bases, mercado, banco) es un trabajo de varios años para 1 programador y 1 diseñador. Este plan la mantiene como destino, pero la ordena para validar primero el loop **robar → alarma → persecución → escape o arresto**. Si ese loop no divierte, el resto no lo salva.

Cambios respecto del master prompt:

- **Orden de fases:** casas, alarmas y policía pasan antes que el backend. Son el núcleo del juego y hay que probarlos primero.
- **Login con Steam** en lugar de usuario y contraseña propios. Es más simple y más seguro.
- **Sin anti-cheat de kernel**, como pide el prompt: la defensa es la autoridad del servidor más detección del lado del servidor.
- **Clanes, territorios, construcción y mercado** quedan fuera del MVP. La arquitectura los contempla.

## Viabilidad

El proyecto es viable si el MVP se limita a un barrio de 16 jugadores y el resto se agrega por etapas. Estimación para llegar a un MVP jugable en internet: **16 a 24 meses** de 1 programador a tiempo parcial que está aprendiendo Unreal (equivale a 8–12 meses a tiempo completo). Es una estimación gruesa que se ajusta al cerrar la Fase 2. Para validar antes, se define un MVP 0 de 4 a 6 meses (ver al final).

| Factor | Situación | Impacto |
| --- | --- | --- |
| Programación | 1 persona, experiencia web, sin experiencia previa en Unreal (a confirmar) | Curva de 2 a 3 meses en C++ y replicación. Gran parte de la red ya viene resuelta por el motor |
| Arte | 1 diseñador; el equipo crea todo el arte | Un kit modular propio (fachadas, rejas, persianas, veredas) arma todo el barrio. Fab solo para lo genérico (vegetación, props comunes) |
| Backend | Experiencia web aprovechable | Es la parte de menor riesgo del proyecto |
| Red y servidores | Servidor autoritativo + dedicado | Unreal cubre el 70% del trabajo difícil (movimiento, replicación). Vehículos en red: riesgo alto |
| Jugadores | Juego nuevo sin audiencia | Riesgo de servidores vacíos. Se mitiga con bots policía y servidores siempre abiertos |
| Presupuesto | VPS Hostinger KVM 2 ya disponible | Steam Direct: 100 USD por juego. El VPS cubre desarrollo y alpha cerrada |

Qué queda fuera del MVP y entra después: clanes, territorios, construcción de bases, mercado entre jugadores, banco con transferencias, personalización avanzada, clima, motos y más de un vehículo.

## Evaluación de motores

Se elige **Unreal Engine 5**. Es el único de los tres que trae resuelto de fábrica lo más difícil de este juego: movimiento en tercera persona con predicción en red, servidor dedicado y mundo abierto por streaming.

| Criterio | Unreal Engine 5 | Unity 6 | Godot 4 |
| --- | --- | --- | --- |
| Networking | Replicación integrada y probada en shooters. Character Movement con predicción y corrección incluidas | Netcode for GameObjects o terceros (Mirror, FishNet). La predicción de movimiento se arma aparte | API multijugador básica. Predicción y compensación de lag hay que construirlas |
| Servidor dedicado | Nativo. Requiere compilar el motor desde el código fuente | Nativo (Dedicated Server build) | Posible (headless), poco usado en shooters |
| Mundo abierto | World Partition, streaming por celdas, HLOD | Posible, con más trabajo manual | Limitado para ciudades grandes |
| Física y vehículos | Chaos Vehicles. Vehículos en red con riesgo, como en todos | Asset Store con varias opciones. Red a cargo propio | Básico |
| Curva de aprendizaje | Alta en C++. Blueprints la suaviza | Media, en C# | Baja |
| Costos | 5% de regalías sobre ingresos brutos por encima de 1 M USD por producto | Sin regalías. Planes pagos según ingresos | Gratis, licencia MIT |
| Ecosistema | Fab, Lyra (shooter multijugador de referencia, gratis) | Asset Store muy amplio | Chico |
| Steam | Online Subsystem Steam integrado | Steamworks.NET o Facepunch.Steamworks | GodotSteam (comunidad) |
| Viabilidad para 1 dev | Alta, si se apoya en lo que el motor ya trae | Media: más código de red propio | Baja para este alcance |

**Por qué no Unity:** su C# se aprende más rápido, pero el programador terminaría escribiendo predicción de movimiento y compensación de lag que Unreal ya trae. Para 1 persona, ese código de red es justo lo que no conviene construir.

**Versión:** la última 5.x estable al iniciar la Fase 1, congelada durante el MVP. Solo se actualiza entre fases.

Condiciones de licencia y regalías de memoria (aproximadas): hay que verificarlas en los sitios de Epic y Unity antes de aprobar.

## Stack seleccionado

Un solo motor y un solo lenguaje de backend. Cada pieza se eligió porque viene integrada o porque el programador ya la conoce.

| Capa | Tecnología | Por qué |
| --- | --- | --- |
| Cliente y servidor de juego | Unreal Engine 5, C++ para sistemas + Blueprints para contenido | El mismo código compila cliente y servidor dedicado |
| Movimiento | Character Movement Component | Predicción y corrección en red incluidas |
| Combate y atributos | Gameplay Ability System (GAS), solo salud, armadura, daño y efectos | Replicación y validación de atributos ya resueltas. Lyra sirve de ejemplo |
| Mundo | World Partition + PCG para variar interiores | Streaming por celdas y variaciones sin modelar cada casa |
| Vehículos | Chaos Vehicles | Integrado. Se prueba en red en la Fase 2 |
| Steam | Online Subsystem Steam | Login, amigos y overlay |
| Backend | Node.js + TypeScript (Fastify) | Experiencia web del programador |
| Base de datos | PostgreSQL | Transacciones ACID para dinero e inventario |
| Caché | Ninguna al inicio. Redis solo si una métrica lo justifica | Evitar piezas sin necesidad |
| Hosting del servidor de juego | VPS Hostinger KVM 2 (Linux + Docker), ya disponible | Alcanza para 1 instancia de 16 jugadores + backend + base en la alpha |
| Logs y monitoreo | Logs JSON + Grafana y Loki (o servicio gestionado equivalente) | Un solo lugar para servidor de juego y backend |
| Control de versiones | Git + Git LFS con bloqueo de archivos | Los .uasset son binarios: el bloqueo evita conflictos entre las 2 personas |
| CI | GitHub Actions para el backend. Builds de Unreal a mano al inicio | Los builds de Unreal en CI son pesados; se automatizan en la Fase 7 |

## Arquitectura

El servidor de juego es la autoridad sobre todo lo que pasa en la partida. El backend es la autoridad sobre todo lo que persiste. El cliente solo muestra y pide.

![Arquitectura: 6 componentes](arquitectura.png)

El cliente nunca habla con la base de datos y nunca escribe en el backend: solo hace login y pide la lista de servidores.

**Ejemplo: robar una casa y vender el botín.**

1. El cliente pide interactuar con la ventana (RPC al servidor).
2. El servidor valida distancia, estado de la casa y nivel de alarma. Si algo no cierra, rechaza y registra.
3. El servidor dispara la alarma y avisa solo a los policías del distrito.
4. El servidor genera el loot desde la tabla y envía el contenido solo a ese cliente.
5. En la tienda, el servidor valida que el objeto esté en el inventario y llama al backend con una idempotency_key.
6. El backend escribe el movimiento en el ledger y el saldo en una sola transacción, y confirma.

**Qué valida siempre el servidor:** dinero, inventario, daño (raycast del lado del servidor con compensación de latencia), velocidad de movimiento, alcance de interacción, recompensas, transacciones, propiedad de objetos y permisos. También aplica límites de frecuencia a cada RPC.

## Persistencia

El estado vivo de la partida está en la memoria del servidor de juego. Lo que sobrevive a la desconexión está en PostgreSQL. Solo el backend escribe en la base, y solo acepta escrituras del servidor de juego.

**Qué se guarda y cuándo:**

- **Al entrar:** el servidor pide al backend el personaje, el inventario y el dinero.
- **En eventos importantes:** compra, venta, robo cobrado, arresto. Se envía en el momento, como transacción.
- **Periódicamente:** posición y salud cada 60 segundos.
- **Al salir o si se cae el servidor:** lo pendiente se guarda; lo último que se pierde son los 60 segundos de posición.
- **No se guarda:** el estado de casas, alarmas y loot del mundo. Se regenera al reiniciar el servidor.

**Tablas del MVP:**

| Tabla | Contenido |
| --- | --- |
| accounts | steam_id, fecha de alta, estado (activo, sancionado) |
| characters | account_id, nombre, apariencia, nivel, experiencia, salud, última posición |
| item_definitions | catálogo de objetos: tipo, rareza, apilable, máximo por pila. Generado desde las DataTables de Unreal |
| inventory_items | character_id, item_def_id, cantidad, ranura, instance_id único |
| wallets | character_id, efectivo, saldo bancario |
| ledger_entries | movimiento de dinero: monto, motivo, origen, destino, idempotency_key, fecha |
| sanctions | account_id, tipo, motivo, vencimiento, admin_id |
| audit_log | acciones sensibles de jugadores y admins |

**Reglas contra duplicación:**

- Todo movimiento de dinero es una fila en `ledger_entries`. El saldo se actualiza en la misma transacción.
- Cada operación lleva una `idempotency_key`: si el servidor reintenta, no se cobra ni se paga dos veces.
- Cada objeto único (armas) tiene `instance_id`. Una restricción en la base impide que exista dos veces.
- Migraciones versionadas en el repo del backend. Backup diario de PostgreSQL con restauración probada una vez por fase.

Clanes, territorios y bases agregan sus tablas después, sin tocar estas.

## Servidores dedicados

Cada servidor es una instancia independiente del mismo barrio, siempre abierta, con 16 cupos. Los jugadores entran y salen cuando quieren. El personaje no pertenece a un servidor: vive en el backend, así que se puede jugar en cualquiera.

**Cómo funciona una instancia:**

1. El VPS ejecuta el build Linux del servidor dentro de Docker. Un VPS chico aloja de 1 a 3 instancias; el número real se mide en la Fase 7.
2. Al arrancar, la instancia se registra en el backend con su IP, puerto, región y cupos libres. Después envía un heartbeat cada 15 segundos.
3. Si deja de enviar heartbeats, el backend la saca de la lista.
4. Se reinicia automáticamente una vez por día, de madrugada, para regenerar el mundo y liberar memoria.

**Matchmaking del MVP:**

- El cliente pide al backend la lista de servidores. El backend devuelve el que tiene más gente sin estar lleno, para concentrar jugadores.
- También hay un explorador de servidores manual, útil para jugar con amigos.
- Los roles se asignan dentro del servidor: el GameMode controla el cupo de 4 policías y crea bots policía en los lugares vacíos.

**Entrada al servidor:**

1. El cliente obtiene un ticket de sesión de Steam y se lo da al backend.
2. El backend lo valida con la API de Steam y devuelve un token de juego firmado, de vida corta.
3. El cliente se conecta al servidor con ese token. El servidor lo verifica con el backend antes de aceptarlo.

**Reconexión:** si un jugador se desconecta, su personaje queda en el mundo 60 segundos. Si vuelve en ese tiempo, lo recupera tal como estaba; si no, se guarda y se retira. Así nadie puede desconectarse para escapar de un arresto sin consecuencias.

**Escala futura:** con más jugadores, las instancias pasan a un orquestador (Agones o un servicio gestionado como Edgegap) sin cambiar el código del juego: solo cambia quién arranca las instancias. Subir a 32 o 64 jugadores se decide midiendo CPU y ancho de banda en la alpha.

## Estructura del proyecto

Un monorepo con dos partes: el proyecto de Unreal y el backend. Dentro de Unreal, cada sistema es un módulo de C++ propio. Así el compilador impide dependencias circulares y cada sistema se prueba por separado.

```
/game                      Proyecto Unreal (Git LFS)
  /Source
    /Barrio                Módulo principal: GameMode, GameState, junta los sistemas
    /BarrioCore            Tipos comunes (interfaces, log). No depende de nada del juego
    /BarrioCharacters      Personaje, movimiento, interacción, animación
    /BarrioCombat          Armas, daño, GAS (atributos y efectos)
    /BarrioInventory       Inventario, objetos, loot
    /BarrioWorld           Casas, zonas, alarmas, reposición
    /BarrioPolice          Roles, nivel de buscado, arrestos, cárcel, bots
    /BarrioVehicles        Vehículos
    /BarrioOnline          Cliente HTTP del backend, sesiones, Steam
    /BarrioUI              Widgets de HUD y menús (UMG)
    /BarrioAdmin           Comandos de administración en el servidor
  /Content                 Assets (diseñador), Blueprints y DataTables
  /Tests                   Pruebas automáticas (Automation / Functional Tests)
/backend                   Node.js + TypeScript
  /src/modules             auth, characters, inventory, economy, servers, admin
  /migrations
  /tests
/infra                     Docker, scripts de despliegue, monitoreo
/docs                      Documentos del master prompt
```

**Reglas de dependencia:** todos los módulos dependen de BarrioCore, que no depende de ninguno; ninguno depende de BarrioUI; solo el módulo principal Barrio depende de todos. "Barrio" es el nombre de trabajo interno y no cambia aunque cambie el nombre comercial del juego. Los sistemas se comunican por eventos (delegados) en lugar de llamarse entre sí. Ejemplo: World anuncia que sonó una alarma y Police decide qué hacer.

**División de trabajo:** el programador es dueño de /Source, /backend e /infra. El diseñador es dueño de /Content (mapas, materiales, UI visual) y de las DataTables de loot y balance. Ambos usan bloqueo de archivos en Git LFS para los .uasset.

**Convenciones:** prefijos estándar de Unreal en assets (BP_, SM_, M_, DT_, WBP_), nombres en inglés en el código, documentación en español, configuración por entorno (local, staging, producción) en archivos .ini y variables de entorno del backend.

**Documentos:** los 9 del master prompt viven en /docs desde la Fase 1. Este informe es la base de TECHNICAL_ARCHITECTURE.md y DEVELOPMENT_ROADMAP.md.

## MVP

El MVP responde una sola pregunta: ¿es divertido robar una casa, que suene la alarma y escapar de la policía, con 16 personas en un servidor?

**Incluye:**

- Un barrio de 6 a 10 manzanas, con zona segura (spawn y tienda) y comisaría.
- 16 jugadores en un servidor dedicado: hasta 4 policías, el resto civiles. Bots policía en los cupos vacíos.
- Casas con 3 a 5 interiores base y puntos de saqueo rápido. Loot por tablas con 3 rarezas y reposición por tiempo.
- Alarma con retardo, aviso a la policía del distrito y posibilidad de desactivarla en silencio.
- Nivel de buscado: sube con los delitos, baja con el tiempo, habilita a la policía a actuar.
- Arresto, cárcel por tiempo y pérdida del botín.
- Combate: 1 arma de fuego y 1 cuerpo a cuerpo, salud, armadura, muerte y respawn.
- Inventario por ranuras con apilado, soltar y recoger.
- 1 auto.
- Tienda para vender el botín y comprar equipo.
- Login con Steam, y dinero e inventario que se conservan entre sesiones.
- HUD: salud, armadura, dinero, munición, nivel de buscado, minimapa con alarmas (solo policía).
- Comandos de admin: listar jugadores, expulsar, sancionar.

**Criterios de éxito, medidos en la alpha cerrada:**

- 16 jugadores durante 1 hora sin caídas del servidor.
- Movimiento y disparos jugables con 150 ms de latencia.
- 60 FPS en la configuración mínima elegida.
- En una encuesta, la mayoría de los testers quiere volver a jugar.
- Cero duplicaciones de dinero u objetos en los logs de auditoría.

## Plan de tareas

Las fases son secuenciales: no se avanza sin cumplir el criterio de cierre de la anterior. Complejidad: S (días), M (1 a 2 semanas), L (3 a 5 semanas), XL (más de 5 semanas). Las semanas son para 1 programador; el diseñador trabaja en paralelo en arte y mapa.

| Fase | Tareas | Complejidad | Depende de | Criterio de cierre |
| --- | --- | --- | --- | --- |
| 1. Prototipo | Proyecto, Git LFS, módulos vacíos. Personaje en tercera persona: caminar, correr, saltar, agacharse. Cámara, interacción, HUD mínimo. Mapa gris de 4 manzanas | M | Este informe aprobado | Personaje controlable con interacción en el mapa gris |
| 2. Multijugador | Build del motor desde código fuente. Servidor dedicado local. 2 a 4 clientes con movimiento y animaciones. Conexión y errores. **Prueba de un auto en red** | L | Fase 1 | 4 clientes con 150 ms simulados, sin tirones; decisión tomada sobre vehículos |
| 3. Núcleo del juego | Casas y loot por tablas. Alarmas y distritos. Roles y nivel de buscado. Arresto y cárcel. Combate con GAS. Inventario. Bots policía básicos | XL | Fase 2 | Primera prueba con 6 a 8 amigos: el loop robo-alarma-persecución funciona y divierte |
| 4. Backend | API de auth con Steam, personajes, inventario y economía. Ledger e idempotencia. Registro de servidores y heartbeat. Tienda | L | Fase 3 (en paralelo desde su mitad) | El progreso se conserva al salir y volver, sin duplicaciones en pruebas de estrés |
| 5. Mundo | Barrio completo de 6 a 10 manzanas con arte final. Interiores variados con PCG. NPCs civiles básicos. Ciclo día y noche. Auto final | XL | Fase 3; arte en paralelo desde la Fase 1 | Vertical slice presentable |
| 7. Infraestructura | VPS con Docker, despliegue scriptado, logs y monitoreo, backups, comandos de admin | M | Fase 4 | Servidor online estable 72 horas |
| 8. Alpha cerrada | Pruebas con 16 jugadores reales, estrés, seguridad, optimización | L | Fases 5 y 7 | Criterios de éxito del MVP cumplidos |

La **Fase 6** del master prompt (clanes, chat, grupos, territorios, construcción) pasa después del MVP. Solo entra antes un chat global simple, porque se necesita en la alpha. La infraestructura (Fase 7) puede empezar apenas termina la Fase 4, porque la alpha necesita servidores online.

## Riesgos

El riesgo principal es el alcance: con 2 personas, cada sistema que se suma antes de tiempo atrasa la prueba del loop. El resto se ordena por impacto.

| Riesgo | Probabilidad | Impacto | Mitigación |
| --- | --- | --- | --- |
| El alcance crece antes de validar el loop | Alta | Alto | Lista cerrada del MVP. Cualquier sistema nuevo va al backlog posterior |
| Vehículos en red con tirones o desincronizados | Alta | Alto | Prueba aislada en la Fase 2. Plan B: conducción más simple, sin física completa, con predicción propia |
| Curva de Unreal y C++ | Alta | Medio | Blueprints para prototipar, Lyra como referencia, C++ solo donde haga falta |
| Servidores vacíos al lanzar | Media | Alto | Bots policía, servidores persistentes, concentrar jugadores en pocos servidores, comunidad en Discord desde la alpha |
| Producción de arte para un mundo abierto | Alta | Alto | Kits de Fab, interiores modulares, PCG, mapa chico |
| Trampas en PvP sin anti-cheat de kernel | Media | Alto | Servidor autoritativo, validación de velocidad y alcance de disparos, logs y sanciones. Revaluar anti-cheat antes de Early Access |
| Duplicación de dinero u objetos | Media | Alto | Ledger, idempotencia, instance_id único, auditoría |
| El rol de policía aburre y nadie lo elige | Media | Medio | Recompensas y progresión propias. Bots cubren los cupos |
| Costos de servidores | Baja | Medio | VPS chico hasta la alpha. Orquestador solo con demanda real |
| Parecerse demasiado a ROB RUN | Baja | Alto | Nombre, ciudad, arte e identidad propios. Inspiración en mecánicas, nunca en contenido |

## Decisiones a aprobar

Con estas decisiones aprobadas arranca la Fase 1.

- [ ] Motor: Unreal Engine 5, última 5.x estable, congelada durante el MVP
- [ ] Backend: Node.js + TypeScript + PostgreSQL
- [ ] Login solo con Steam, sin usuario y contraseña propios
- [ ] Servidores persistentes de 16 jugadores (hasta 4 policías), con bots policía de relleno
- [ ] Orden de fases: núcleo del juego (casas, alarmas, policía) antes del backend
- [ ] Alcance del MVP tal como figura arriba; clanes, territorios, bases y mercado después
- [ ] Sin anti-cheat de kernel en el MVP, revaluar antes de Early Access
- [ ] Git + Git LFS con bloqueo de archivos

**Preguntas respondidas:**

| Pregunta | Respuesta | Qué cambia |
| --- | --- | --- |
| Dedicación del programador | Tiempo parcial | La estimación del MVP pasa de 8–12 a **16–24 meses**. Se agrega un hito intermedio (MVP 0) para validar el loop mucho antes |
| Arte | El equipo crea todo | El arte se hace a medida, con un kit modular propio. Encaja con la ambientación, que no existe en las tiendas de assets |
| Servidores | VPS propio en Hostinger, plan KVM 2 | Sirve para desarrollo y alpha cerrada. Ver la sección "VPS disponible" |
| Ambientación | Buenos Aires, Zona Oeste, Caseros, época actual | Ver la sección "Ambientación" |

**Pendiente:** nombre de trabajo del juego.

## MVP 0 (hito intermedio por dedicación parcial)

Con dedicación parcial, esperar 16 a 24 meses para saber si el juego divierte es demasiado riesgo. Antes del MVP completo se arma un **MVP 0** de unos 4 a 6 meses:

- 4 manzanas en gris, sin arte final.
- Servidor dedicado con 4 a 8 jugadores, corriendo en el VPS.
- Casas con loot, alarma y aviso a la policía.
- Roles civil, ladrón y policía, con nivel de buscado y arresto.
- 1 arma, sin vehículos, sin backend: el progreso no se guarda.

Se prueba con amigos. Si el loop divierte, se sigue con el MVP completo. Si no, se ajusta el diseño antes de invertir en arte y backend.

## VPS disponible

Hostinger KVM 2. Especificaciones de memoria, a verificar en el panel: 2 vCPU, 8 GB de RAM, 100 GB NVMe.

**Alcanza para:** 1 instancia del servidor de juego de 16 jugadores + backend + PostgreSQL, durante desarrollo y alpha cerrada.

**Hay que verificar:**

- **Ubicación del datacenter.** Para jugadores en Buenos Aires conviene São Paulo (unos 30–40 ms de latencia). Uno en Estados Unidos o Europa da 150–250 ms, que en un shooter se nota.
- **Puertos UDP abiertos.** El servidor de Unreal usa UDP (por defecto el 7777). Se habilitan en el firewall del panel de Hostinger.
- **Consumo real.** El uso de CPU y RAM de una instancia se mide en la Fase 2. Si no alcanza, se separan el backend y la base a otro servidor.

**No alcanza para:** varias instancias con muchos jugadores a la vez. Para Early Access se evalúa un segundo VPS u hosting por uso.

## Ambientación

Caseros, partido de Tres de Febrero, Zona Oeste del conurbano bonaerense, época actual. Es una identidad muy propia: ningún juego del género está ambientado así.

**Rasgos del barrio que se vuelven mecánicas:**

- **Casas bajas con rejas, portones y persianas.** Cada acceso es una decisión: forzar la reja (ruido) o buscar otra entrada.
- **Alarma vecinal.** Además de la alarma de la casa, un botón comunitario avisa a toda la cuadra. Los vecinos NPC miran por la ventana y pueden dar la descripción del ladrón.
- **Comercios de barrio** (kiosco, almacén, autoservicio, verdulería): objetivos de robo rápidos con poco botín.
- **Moto como vehículo icónico.** En este contexto la moto es más representativa que el auto. Se puede evaluar como primer vehículo en la Fase 2.
- **Vías del tren, avenidas y pasajes** como rutas de escape y puntos de control.

**Cuidados legales:** el nombre del barrio se puede usar, pero no marcas reales de comercios ni el escudo o nombre de la policía real. La fuerza policial del juego es ficticia, con nombre y emblema propios.
