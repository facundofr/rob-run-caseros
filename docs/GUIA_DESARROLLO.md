# Guía de desarrollo

Cómo preparar la PC de desarrollo, compilar el juego y armar el mapa en el editor. Después de esto: [PRUEBAS.md](PRUEBAS.md). Para el servidor en el VPS: [DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md).

> **El código de Unreal nunca se compiló.** Es esperable que la primera compilación dé errores. Corregirlos es la primera tarea (etapa 4 de [PLAN.md](PLAN.md)).

## 1. Requisitos

| Componente | Mínimo | PC de desarrollo del proyecto |
| --- | --- | --- |
| Disco libre | 150 GB en SSD (500 GB para compilar el motor para el servidor) | a confirmar |
| RAM | 16 GB | 32 GB |
| Placa de video | GPU dedicada con 6 GB | RTX 5050 8 GB |
| Procesador | 6 núcleos | Ryzen 7 5700X |

**Software:**
1. **Epic Games Launcher** → Unreal Engine, última versión 5.x estable.
2. **Visual Studio 2022** (Community alcanza) con la carga de trabajo **"Desarrollo de juegos con C++"**, incluyendo el **SDK de Windows**.
3. **Git** y **Git LFS**.
4. **Node.js 24**, solo si se va a tocar el backend.

## 2. Compilar y abrir (primera vez)

1. `git clone https://github.com/facundofr/rob-run-caseros.git` y, una vez en la PC, `git lfs install`.
2. Clic derecho en `game/Barrio.uproject` → **Switch Unreal Engine version** → la versión instalada.
3. Clic derecho en `game/Barrio.uproject` → **Generate Visual Studio project files**.
4. Abrir `game/Barrio.sln`. Configuración **Development Editor**, plataforma **Win64**, proyecto de inicio **Barrio**. Compilar con `Ctrl+Shift+B`.
5. Si falla, guardar la lista completa de errores (ventana *Output*, no solo *Error List*) y corregir módulo por módulo, en orden de dependencias: `BarrioCore` → `BarrioCombat` → `BarrioCharacters` → `BarrioWorld` → `BarrioOnline` → `BarrioUI` → `Barrio`.
6. Abrir `Barrio.uproject` con doble clic. Va a avisar que no encuentra `L_Greybox`: es normal hasta crear el mapa.

## 3. Armar el contenido en el editor

Estos pasos crean assets (`.uasset` y `.umap`) que no se pueden escribir desde código.

**3.1 Maniquí y animaciones.** En el **Content Browser**: **Add** → **Add Feature or Content Pack** → **Blueprint** → **Third Person** → **Add to Project**.

**3.2 Blueprint del personaje.**
- Crear la carpeta `Content/Barrio/Characters`.
- Clic derecho → **Blueprint Class** → **All Classes** → `BarrioCharacter` → nombre `BP_BarrioCharacter`.
- En el componente **Mesh**: **Skeletal Mesh Asset** = `SKM_Manny_Simple` (o `SKM_Manny`) y **Anim Class** = el Animation Blueprint del pack (buscar "ABP"). Compilar y guardar.

**3.3 Blueprint del GameMode.**
- En `Content/Barrio`: **Blueprint Class** → `BarrioGameMode` → nombre `BP_BarrioGameMode`.
- **Default Pawn Class** = `BP_BarrioCharacter`. Guardar.
- **Project Settings → Maps & Modes → Default GameMode** = `BP_BarrioGameMode`.

**3.4 Mapa.**
- **File → New Level → Basic**. Guardarlo exactamente como `Content/Barrio/Maps/L_Greybox` (la configuración ya apunta a esa ruta).
- Borrar el piso del nivel (`Floor`).
- **Place Actors** → buscar y arrastrar:

| Actor | Posición | Tamaño (Box Extent) | Para qué |
| --- | --- | --- | --- |
| `GreyboxNeighborhood` | `0, 0, 0` | — | Las 4 manzanas más 40 m de "Afuera" alrededor. Al dar Play crea una puerta robable en cada casa (80 en total) |
| `Player Start` × 2 | `500, 500, 100` y `500, 11500, 100` | — | Aparición de vecinos |
| `BarrioSafeZone` | `500, 500, 100` | `600, 600, 300` | Zona segura de la aparición: sin daño, sin pasamontañas |
| `Player Start`, con **Player Start Tag** = `Police` | `11500, 500, 100` | — | Aparición de policías |
| `PoliceStation` | `11500, 800, 55` | — | Mostrador azul: entrar de servicio, o terminar el turno y cobrar |
| `BarrioSafeZone` | `11500, 600, 100` | `500, 500, 300` | Zona segura de la comisaría |
| `ExitZone` × 2 | `-500, 11500, 100` y `23500, 11500, 100` | `500, 600, 300` | Salidas del barrio (cajas amarillas) |
| `FenceStation` | `-2500, 11500, 55` | — | Mostrador verde: el reducidor, Afuera, pasando la salida oeste |
| `JailCell` | `-5000, -5000, 200` | — | La celda, lejos del barrio |
| `InteractableTestActor` | opcional | — | Interruptor de prueba |

El barrio va de `0` a `23000` en X y en Y (4 manzanas de 100 m y calles de 10 m); Afuera va de `-4000` a `27000`. Las salidas están en los extremos de la calle del medio (`Y = 11500`).

## 4. Controles

| Acción | Tecla |
| --- | --- |
| Moverse / mirar | W A S D / mouse |
| Saltar / agacharse / correr | Espacio / C / Shift izquierdo (mantener) |
| Interactuar (robar, vender, esposar, comisaría) | E |
| Ponerse el pasamontañas (vecino → ladrón) | G |
| Rendirse (ladrón) / ordenar rendición (policía) | Q |
| Disparar (solo ladrones y policías) / recargar | Clic izquierdo / R |

Los controles se crean desde código. Para editarlos, se crean Input Actions y un Input Mapping Context como assets y se asignan en `BP_BarrioCharacter` (categoría *Barrio | Input*).

## 5. Configuración del juego

**Project Settings → Game → Barrio Online** (se guarda en `game/Config/DefaultGame.ini`):

| Opción | Valor | Para qué |
| --- | --- | --- |
| Backend Url | `https://caseros-api.facundofr.com` | Login del cliente |
| Default Game Server | `caseros.facundofr.com:7777` | Si el backend no recomienda ninguno |
| Require Login | Activado | Pantalla de login al abrir el juego empaquetado |
| Show Login In Editor | Desactivado | Activarlo para ver el login al probar en el editor |

En el editor, sin la variable `BARRIO_SERVER_KEY`, el juego funciona sin cuentas: nada se guarda. Es lo esperado para probar rápido.

## 6. Flujo de trabajo con Git

- Los assets de Unreal van por Git LFS. Antes de editar un mapa o Blueprint compartido: `git lfs lock <archivo>`. Al terminar y subir: `git lfs unlock <archivo>`.
- Commits chicos con mensaje en español. Cada cambio se sube a `main`.
- No se suben `Binaries/`, `Intermediate/`, `Saved/` ni `DerivedDataCache/` (ya están en `.gitignore`), ni archivos con secretos.
