# Barrio (nombre de trabajo)

Juego multijugador de mundo abierto en tercera persona, ambientado en Caseros (Zona Oeste del conurbano bonaerense). Los jugadores son vecinos, ladrones o policías en servidores de 16 jugadores. Unreal Engine 5, servidor dedicado autoritativo y backend propio.

**Estado:** el backend funciona y está probado; el código de Unreal está escrito pero todavía no se compiló. Detalle en [docs/PLAN.md](docs/PLAN.md).

## Documentación

Cada tema tiene un solo archivo.

| Archivo | Qué tiene | Para quién |
| --- | --- | --- |
| [AGENTS.md](AGENTS.md) | Reglas del repo y orden de pasos para levantar todo | Asistentes de IA (y cualquiera que empiece) |
| [docs/PLAN.md](docs/PLAN.md) | **Estado del proyecto**, etapas, criterios de cierre, riesgos | Todo el equipo |
| [docs/ENTORNOS.md](docs/ENTORNOS.md) | Cómo trabajar: qué se hace en la PC y qué en el VPS, VS Code Remote-SSH, Claude Code en el VPS | Programación |
| [docs/DISENO_JUEGO.md](docs/DISENO_JUEGO.md) | Reglas del juego: roles, robo, captura, recompensas, ambientación | Todo el equipo |
| [docs/MAPA.md](docs/MAPA.md) | Diseño del mapa jugable: trazado, salidas, zonas, coberturas, hitos, navegación de bots | Todo el equipo |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Cómo está construido y por qué: componentes, stack, módulos, base de datos | Programación |
| [docs/GUIA_DESARROLLO.md](docs/GUIA_DESARROLLO.md) | PC de desarrollo: instalar, compilar, armar el mapa, controles | Programación |
| [docs/PRUEBAS.md](docs/PRUEBAS.md) | Listas de pruebas por etapa | Programación y testers |
| [docs/DESPLIEGUE_VPS.md](docs/DESPLIEGUE_VPS.md) | VPS: qué se instala, backend con HTTPS, servidor de juego | Programación |
| [docs/BACKEND.md](docs/BACKEND.md) | API del backend, variables de entorno, uso local | Programación |
| [docs/ARTE.md](docs/ARTE.md) | Encargo de arte: prioridades y especificaciones técnicas | Diseñador y artistas |
| [CHANGELOG.md](CHANGELOG.md) | Historial de cambios por etapa | Todo el equipo |

## Carpetas

```
/game        Proyecto de Unreal Engine 5 (C++)
/backend     API Node.js + TypeScript
/infra/vps   Scripts y servicios del VPS
/docs        Documentación
```

## Por dónde empezar

1. **Backend en el VPS:** [docs/DESPLIEGUE_VPS.md](docs/DESPLIEGUE_VPS.md), secciones 1 a 4.
2. **Juego en la PC de desarrollo:** [docs/GUIA_DESARROLLO.md](docs/GUIA_DESARROLLO.md) y después [docs/PRUEBAS.md](docs/PRUEBAS.md).
3. **Servidor de juego en el VPS:** [docs/DESPLIEGUE_VPS.md](docs/DESPLIEGUE_VPS.md), sección 5.
