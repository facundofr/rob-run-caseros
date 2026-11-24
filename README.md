# Barrio (nombre de trabajo)

Juego multijugador de mundo abierto ambientado en Caseros, Zona Oeste del conurbano bonaerense. Unreal Engine 5, servidor dedicado autoritativo, 16 jugadores por servidor.

- Plan de acción y estado: [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md)
- Arquitectura y decisiones: [docs/FASE0_INFORME.md](docs/FASE0_INFORME.md)
- Backend (cuentas, dinero, servidores): [backend/README.md](backend/README.md)
- Despliegue en el VPS (facundofr.com): [infra/vps/README.md](infra/vps/README.md)
- Cambios por versión: [CHANGELOG.md](CHANGELOG.md)

**Estado actual: MVP 0, código escrito y todavía sin compilar.** La primera compilación se hace en la PC de desarrollo; es normal que aparezcan errores a corregir.

## Qué es el MVP 0

Un barrio en gris de 4 manzanas donde se prueba el loop central con amigos:

1. Un civil fuerza la puerta de una casa (puertas azules) y la roba.
2. Puede sonar la alarma: la puerta se pone roja, el ladrón pasa a estar **buscado** y los policías cercanos ven "ALARMA" en pantalla.
3. La policía persigue y arresta (E de cerca) o abate al sospechoso. Va a la cárcel y pierde el botín.
4. Si el ladrón escapa, espera a que baje el nivel de buscado (1 nivel por minuto sin delitos) y vende el botín al reducidor.

Sin vehículos, sin backend (nada se guarda al salir) y sin bots policía.

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
    /BarrioUI         HUD. Puede leer de los otros módulos; ninguno depende de él
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
| `GreyboxNeighborhood` | `0, 0, 0` | Las 4 manzanas. Al dar Play crea una puerta robable en cada casa (80 en total) |
| `Player Start` × 2 | `500, 500, 100` y `500, 11500, 100` | Aparición de civiles (sobre la calle) |
| `Player Start` × 1, con **Player Start Tag** = `Police` | `11500, 500, 100` | Aparición de policías |
| `PoliceStation` | `11500, 800, 55` | Mostrador azul: unirse a la policía o dejarla |
| `FenceStation` | `22500, 22500, 55` | Mostrador verde: el reducidor que compra el botín |
| `JailCell` | `-5000, -5000, 200` | La celda, fuera del barrio |
| `InteractableTestActor` | opcional | El interruptor de prueba de la Fase 1 |

El barrio va de `0` a `23000` en X y en Y (4 manzanas de 100 m y calles de 10 m). Las calles quedan entre las manzanas, por ejemplo en `X = 11500` o `Y = 11500`.

## Controles

| Acción | Tecla |
| --- | --- |
| Moverse | W A S D |
| Mirar | Mouse |
| Saltar | Espacio |
| Correr | Shift izquierdo (mantener) |
| Agacharse | C |
| Interactuar (robar, vender, arrestar, comisaría) | E |
| Disparar | Clic izquierdo |
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

Jugador A = ladrón, Jugador B = policía, Jugador C = civil.

- [ ] B va a la comisaría (mostrador azul) y con E se une a la policía. Reaparece en el Player Start `Police` y su panel dice **POLICÍA**.
- [ ] Un cuarto jugador no puede sumarse a la policía si el cupo está lleno (mensaje "Cupo de policía completo").
- [ ] A roba una casa: aparece la barra "Robando...". Al alejarse antes de terminar, se cancela.
- [ ] Al terminar, el panel de A muestra el botín encima.
- [ ] Cuando suena una alarma: la puerta se pone roja, A ve "¡Sonó la alarma! Estás buscado", B ve "ALARMA xx m" y sobre A aparece "BUSCADO".
- [ ] C no ve la alarma ni recibe avisos.
- [ ] B se acerca a A y con E lo arresta: A aparece en la celda con la cuenta regresiva, pierde el botín, y B recibe la recompensa.
- [ ] Al terminar la condena, A reaparece libre en un Player Start de civil.
- [ ] A le dispara a C: A pasa a estar buscado. Si lo mata, sube 2 niveles más.
- [ ] B abate a A estando buscado: A reaparece en la cárcel.
- [ ] Un civil buscado no puede vender en el reducidor ("Estás buscado: el reducidor no te compra"). Al pasar los minutos sin delitos el nivel baja hasta 0 y ahí puede vender: el botín pasa a Dinero.
- [ ] Al morir, el jugador reaparece a los 5 s y pierde el botín encima.

### MVP 0 en el VPS

Seguir [infra/vps/README.md](infra/vps/README.md) y repetir la prueba del loop completo con jugadores conectados desde casas distintas.

Si algo falla, anotar el paso de la lista, qué se ve y el error del **Output Log**.

## Flujo de trabajo con Git

- Los assets de Unreal van por Git LFS. Antes de editar un mapa o Blueprint compartido: `git lfs lock <archivo>`. Al terminar y subir: `git lfs unlock <archivo>`.
- Ramas cortas por tarea y commits chicos.
- No se suben `Binaries/`, `Intermediate/`, `Saved/` ni `DerivedDataCache/` (ya están en `.gitignore`).
