# Assets de Fab

El barrio se genera por script (`game/Scripts/arte/build_barrio.py`) y funciona sin nada externo.
Si en el proyecto están los paquetes de Fab de abajo, el build los usa en lugar de lo generado.

Los paquetes están bajo la **Licencia estándar de Fab**: se pueden usar en el juego, pero **no se
redistribuyen** en este repositorio (están en `.gitignore`). Cada persona que clone el repo los agrega
gratis desde su cuenta de Epic.

| Paquete | Autor | Carpeta en `Content/` | Para qué se usa |
|---|---|---|---|
| European Hornbeam (Megascans) | Quixel | `EuropeanHornbeam/` y `MSPresets/` | Árboles con hoja de vereda (copas angostas, 9,5–11,5 m) y de plaza (13–16 m). Los plátanos podados de invierno siguen siendo los generados. |
| Vehicle Variety Pack | Switchboard Studios | `VehicleVarietyPack/` | ~60 % de los autos estacionados (el patrullero sigue siendo el generado). |

## Cómo agregarlos

1. Abrir `game/Barrio.uproject` con UE 5.8 e iniciar sesión en Epic.
2. **Ventana → Fab**, buscar cada paquete, **Añadir a Mi biblioteca** y después **Añadir al proyecto**.
   - Si el botón del panel no responde (pasó con Vehicle Variety Pack), usar el Epic Games Launcher:
     **Unreal Engine → Biblioteca → Biblioteca de Fab → Añadir al proyecto**. El launcher solo lista
     proyectos que están en `Documentos/Unreal Projects`; si Barrio está en otra carpeta, se puede añadir
     a un proyecto vacío de 5.8 de esa carpeta y copiar la carpeta del paquete a `game/Content/`
     (las referencias internas usan `/Game/<Carpeta>`, así que se mantienen).
3. Volver a correr `build_barrio.py`. En el log aparecen `[FAB] árboles de Fab: ...` y
   `[FAB] vehículos de Fab: ...`; si un paquete falta, se usa lo generado y no hay errores.

## Detalles técnicos

- `barrio_fab.py` descubre los assets por nombre (las rutas exactas cambian entre versiones).
- Árboles: versiones **SimpleWind** (más baratas que PivotPainter), Nanite. La malla de follaje va sin
  colisión; cada árbol lleva un cilindro invisible como colisión del tronco (`*_Tronco`).
- Los actores del mapa que usan estos paquetes quedan con referencias rotas en un clon sin los paquetes;
  volver a correr el build los reemplaza por los generados.
