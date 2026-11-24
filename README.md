# Barrio (nombre de trabajo)

Juego multijugador de mundo abierto ambientado en Caseros, Zona Oeste del conurbano bonaerense. Unreal Engine 5, servidor dedicado autoritativo, 16 jugadores por servidor.

- **Pasos para levantar todo (y guía para asistentes de IA): [AGENTS.md](AGENTS.md)**
- Plan de acción y estado: [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md)
- Arquitectura y decisiones: [docs/FASE0_INFORME.md](docs/FASE0_INFORME.md)
- Backend (cuentas, dinero, servidores): [backend/README.md](backend/README.md)
- Despliegue en el VPS (facundofr.com): [infra/vps/README.md](infra/vps/README.md)
- Cambios por versión: [CHANGELOG.md](CHANGELOG.md)

**Estado actual: MVP 0, código escrito y todavía sin compilar.** La primera compilación se hace en la PC de desarrollo; es normal que aparezcan errores a corregir.

## Qué es el MVP 0

Un barrio en gris de 4 manzanas donde se prueba el loop central con amigos:

Las reglas completas están en [docs/GAME_DESIGN_DOCUMENT.md](docs/GAME_DESIGN_DOCUMENT.md). En resumen:

1. Todos entran como **vecinos**: no usan armas, no roban y no pierden nada al morir.
2. Un vecino se pone el **pasamontañas** (G, 2 s) y pasa a ser **ladrón**: puede robar casas (puertas azules) y usar armas. Sigue siendo ladrón hasta **cruzar una salida del barrio**.
3. Si suena una alarma, los policías cercanos ven "ALARMA" en pantalla. Robar seguido sin salir sube la **notoriedad**: el botín vale más.
4. Un **policía** (mostrador de la comisaría, cupo de 1 cada 3 jugadores) solo puede dañar ladrones. Al ladrón **rendido** (Q) o **reducido** (poca vida) lo **esposa** (E, 2,5 s): cárcel y botín confiscado. Arrestar paga mucho más que abatir, y se cobra al terminar el turno.
5. El ladrón que escapa vuelve a ser vecino y vende el botín al **reducidor**, que está Afuera.
6. Morir siendo ladrón: se pierde todo lo que llevaba encima.

Sin vehículos ni bots policía todavía.

## Estructura

```
/game                 Proyecto de Unreal
  Barrio.uproject
  /Config             Configuración del proyecto
  /Content            Assets (diseñador): mapas, Blueprints, materiales
  /Source
    /Barrio           Módulo principal: GameMode con las reglas (roles, buscado, cárcel, reaparición)
    /BarrioCore       Tipos compartidos: PlayerState, PlayerController, eventos, interfaz de interacción
    /BarrioCombat     Vida y pistola (disparos validados por el servidor)
    /BarrioCharacters Personaje, movimiento (sprint predicho en red), cámara, controles, arresto
    /BarrioWorld      Barrio en gris, puntos de robo, reducidor, comisaría, celda
    /BarrioOnline     Conexión con el backend: login, sesiones, dinero, registro del servidor
    /BarrioUI         HUD y pantalla de login. Puede leer de los otros módulos; ninguno depende de él
/backend              API: cuentas, dinero (ledger), servidores de juego. Ver backend/README.md
/infra/vps            Despliegue del servidor dedicado en el VPS
/docs                 Documentación
```

## Requisitos de la PC de desarrollo

| Componente | Mínimo | PC actual del proyecto |
| --- | --- | --- |
| Disco libre | 150 GB en SSD (500 GB para compilar el motor) | a confirmar |
| RAM | 16 GB | 32 GB |
| Placa de video | GPU dedicada con 6 GB | RTX 5050 8 GB |
| Procesador | 6 núcleos | Ryzen 7 5700X |

**Software:**

1. **Epic Games Launcher** → Unreal Engine, última versión 5.x estable. (Para el servidor dedicado hace falta además el motor compilado desde el código fuente: ver [infra/vps/README.md](infra/vps/README.md).)
2. **Visual Studio 2022** (Community alcanza) con la carga de trabajo **"Desarrollo de juegos con C++"**, incluyendo el **SDK de Windows**.
3. **Git** y **Git LFS**.

## Primera vez: compilar y abrir

1. Clonar el repositorio y ejecutar `git lfs install` una vez en la PC.
2. Clic derecho en `game/Barrio.uproject` → **Switch Unreal Engine version** → elegir la versión instalada.
3. Clic derecho en `game/Barrio.uproject` → **Generate Visual Studio project files**.
4. Abrir `game/Barrio.sln` en Visual Studio. Configuración **Development Editor**, plataforma **Win64**, proyecto de inicio **Barrio**. Compilar con `Ctrl+Shift+B`.
5. Si la compilación falla, guardar la lista completa de errores (ventana *Output*, no solo *Error List*) para corregirlos.
6. Abrir `Barrio.uproject` con doble clic. Va a avisar que no encuentra `L_Greybox`: es normal hasta crear el mapa.

## Armar el contenido en el editor

Estos pasos crean assets (.uasset y .umap) que no se pueden escribir desde código.

**1. Maniquí y animaciones.** En el **Content Browser**: **Add** → **Add Feature or Content Pack** → **Blueprint** → **Third Person** → **Add to Project**.

**2. Blueprint del personaje.**
- Crear la carpeta `Content/Barrio/Characters`.
- Clic derecho → **Blueprint Class** → **All Classes** → `BarrioCharacter` → nombre `BP_BarrioCharacter`.
- Seleccionar el componente **Mesh** y asignar **Skeletal Mesh Asset** = `SKM_Manny_Simple` (o `SKM_Manny`) y **Anim Class** = el Animation Blueprint del pack (buscar "ABP"). Compilar y guardar.

**3. Blueprint del GameMode.**
- En `Content/Barrio`: **Blueprint Class** → `BarrioGameMode` → nombre `BP_BarrioGameMode`.
- **Default Pawn Class** = `BP_BarrioCharacter`. Guardar.
- **Project Settings → Maps & Modes → Default GameMode** = `BP_BarrioGameMode`.

**4. Mapa del MVP 0.**
- **File → New Level → Basic**. Guardarlo exactamente como `Content/Barrio/Maps/L_Greybox` (la configuración ya apunta a esa ruta).
- Borrar el piso del nivel (`Floor`).
- **Place Actors** → buscar y arrastrar:

| Actor | Posición sugerida | Para qué |
| --- | --- | --- |
| `GreyboxNeighborhood` | `0, 0, 0` | Las 4 manzanas más 40 m de terreno alrededor ("Afuera"). Al dar Play crea una puerta robable en cada casa (80 en total) |
| `Player Start` × 2 | `500, 500, 100` y `500, 11500, 100` | Aparición de vecinos (sobre la calle) |
| `SafeZone` | `500, 500, 100`, tamaño (Box Extent) `600, 600, 300` | Zona segura alrededor de la aparición: sin daño, sin pasamontañas |
| `Player Start` × 1, con **Player Start Tag** = `Police` | `11500, 500, 100` | Aparición de policías |
| `PoliceStation` | `11500, 800, 55` | Mostrador azul: entrar de servicio o terminar el turno y cobrar |
| `SafeZone` | `11500, 600, 100`, tamaño `500, 500, 300` | Zona segura de la comisaría |
| `ExitZone` × 2 | `-500, 11500, 100` y `23500, 11500, 100`, tamaño `500, 600, 300` | Salidas del barrio (cajas amarillas): cruzarlas deja de ser ladrón |
| `FenceStation` | `-2500, 11500, 55` | Mostrador verde: el reducidor, Afuera, pasando la salida oeste |
| `JailCell` | `-5000, -5000, 200` | La celda, lejos del barrio |
| `InteractableTestActor` | opcional | El interruptor de prueba de la Fase 1 |

El barrio va de `0` a `23000` en X y en Y (4 manzanas de 100 m y calles de 10 m); Afuera va de `-4000` a `27000`. Las calles quedan entre las manzanas, por ejemplo en `X = 11500` o `Y = 11500`. Las salidas están en los extremos de la calle del medio.

## Controles

| Acción | Tecla |
| --- | --- |
| Moverse | W A S D |
| Mirar | Mouse |
| Saltar | Espacio |
| Correr | Shift izquierdo (mantener) |
| Agacharse | C |
| Interactuar (robar, vender, esposar, comisaría) | E |
| Ponerse el pasamontañas (vecino → ladrón) | G |
| Rendirse (ladrón) / ordenar rendición (policía) | Q |
| Disparar (solo ladrones y policías) | Clic izquierdo |
| Recargar | R |

Los controles se crean desde código. Para editarlos, se crean Input Actions y un Input Mapping Context como assets y se asignan en `BP_BarrioCharacter` (categoría *Barrio | Input*).

## Pruebas

### Fase 1: un jugador (Play, modo Selected Viewport)

- [ ] W A S D mueven y el mouse gira la cámara.
- [ ] Shift corre (abajo a la izquierda dice *Corriendo*, unos 21 km/h; caminando, unos 12 km/h).
- [ ] Espacio salta y C agacha.
- [ ] El personaje choca con casas, medianeras y cordones.
- [ ] Mirando una puerta azul de cerca aparece `[E] Robar casa (botín ...)`. Desde más de 2,5 m no aparece.

### Fase 2: multijugador en el editor

Junto al botón Play, en **⋮**: **Number of Players: 3**, **Net Mode: Play As Client** (esto levanta un servidor dedicado oculto y tres clientes).

- [ ] Los tres se ven moviéndose, corriendo y agachándose sin tirones.
- [ ] Abajo a la izquierda cada ventana dice *Cliente*.
- [ ] Con latencia simulada se sigue pudiendo jugar: en la consola (`º` o `~`) escribir `NetEmulation.PktLag 150` en un cliente y repetir las pruebas.

### MVP 0: el loop completo (3 jugadores, Play As Client)

Jugador A = ladrón, Jugador B = policía, Jugador C = vecino.

**Roles**
- [ ] Los tres aparecen como **VECINO**. Un vecino no puede disparar (el clic no hace nada) y frente a una puerta azul ve "Para robar, ponete el pasamontañas (G)".
- [ ] Dentro de la zona segura, G muestra "Acá no te podés poner el pasamontañas".
- [ ] B va a la comisaría y con E entra de servicio: reaparece en el Player Start `Police` y su panel dice **POLICÍA (de servicio)**.
- [ ] Un cuarto jugador no puede entrar de servicio si el cupo está lleno ("Cupo de policía completo").
- [ ] A, fuera de la zona segura, aprieta G: barra de 2 s y pasa a **LADRÓN**. Los demás ven "LADRÓN" sobre su cabeza.
- [ ] Un ladrón no puede entrar de servicio en la comisaría.

**Robo y alarma**
- [ ] A roba una casa: barra "Robando...". Si se aleja antes de terminar, se cancela.
- [ ] Al terminar, el panel muestra el botín y la notoriedad sube 1. El segundo robo seguido rinde más (+10 % por nivel).
- [ ] Si suena la alarma: la puerta se pone roja, A ve "¡Sonó la alarma!", B ve "ALARMA xx m", C no ve nada.

**Daño**
- [ ] B le dispara a C (vecino): no le hace daño. B le dispara a A (ladrón): sí.
- [ ] Nadie recibe daño dentro de una zona segura.
- [ ] A mata a C: el nivel de búsqueda de A sube 1. Con 3 muertes, B y C ven a A marcado como "MÁS BUSCADO" desde cualquier distancia.

**Captura**
- [ ] B aprieta Q cerca de A: A ve "¡POLICÍA! ¡Rendite! (Q)".
- [ ] A aprieta Q: queda **RENDIDO**, camina lento y no puede disparar.
- [ ] B mira a A y aprieta E: barra "Esposando..." de 2,5 s. A va a la celda con la cuenta regresiva, pierde el botín, y el panel de B suma la ganancia (+20 % si dio la orden de rendición antes).
- [ ] Si B se aleja durante el esposado, falla ("Se te escapó").
- [ ] Un ladrón con poca vida (25 % o menos) también se puede esposar sin rendirse.
- [ ] B abate a A sin que se rinda: +$300. Si A estaba rendido: "no se paga".
- [ ] Al terminar la condena, A reaparece como **vecino**.

**Escape y venta**
- [ ] A, con botín, cruza una salida (caja amarilla): "Saliste del barrio: ya no sos ladrón". Su panel dice VECINO con "Botín para vender".
- [ ] Con el pasamontañas puesto el reducidor no le compra. Ya como vecino, vende: el botín pasa a Banco.
- [ ] A muere siendo ladrón: pierde todo el botín y reaparece como vecino.

**Turno policial**
- [ ] B termina el turno en la comisaría: cobra las ganancias acumuladas y vuelve a ser vecino.
- [ ] B muere de servicio: reaparece como policía en la comisaría, con 10 s sin recibir daño.

### MVP 0 en el VPS

Seguir [infra/vps/README.md](infra/vps/README.md) y repetir la prueba del loop completo con jugadores conectados desde casas distintas.

### Cuentas y dinero guardado (etapa 6, con backend y servidor en el VPS)

Con un cliente empaquetado (Development) que abre el juego sin argumentos:

- [ ] Aparece la pantalla de login. Con usuario o contraseña incorrectos muestra "Usuario o contraseña incorrectos".
- [ ] "Crear cuenta" con una contraseña corta muestra el motivo ("al menos 10 caracteres").
- [ ] Al crear la cuenta, entra solo a `caseros.facundofr.com` y el panel muestra Dinero: $0.
- [ ] Robar, perder a la policía y vender: el dinero sube. Salir del juego, volver a entrar con la misma cuenta: el dinero sigue ahí.
- [ ] Abrir un segundo cliente con la misma cuenta: el segundo es expulsado con "Esa cuenta ya está conectada".
- [ ] Conectarse a mano sin login (`open caseros.facundofr.com:7777` desde la consola): el servidor lo rechaza.

Para ver la pantalla de login en el editor: **Project Settings → Game → Barrio Online → Show Login In Editor**, y Play en modo **Standalone Game**.

Si algo falla, anotar el paso de la lista, qué se ve y el error del **Output Log**.

## Flujo de trabajo con Git

- Los assets de Unreal van por Git LFS. Antes de editar un mapa o Blueprint compartido: `git lfs lock <archivo>`. Al terminar y subir: `git lfs unlock <archivo>`.
- Ramas cortas por tarea y commits chicos.
- No se suben `Binaries/`, `Intermediate/`, `Saved/` ni `DerivedDataCache/` (ya están en `.gitignore`).
