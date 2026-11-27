# Plan de acción

Actualizado: 27 de noviembre de 2026. **Única fuente del estado del proyecto**: los demás documentos remiten acá.

**Objetivo del MVP:** jugable por internet en `caseros.facundofr.com`, con 16 jugadores, cuentas de usuario y contraseña, dinero que se conserva entre sesiones y el loop completo: vecino → pasamontañas → robo → escape por una salida del barrio → venta, contra policías jugadores. Las reglas están en [DISENO_JUEGO.md](DISENO_JUEGO.md).

## Equipo y estimación

- **Equipo:** 1 persona a tiempo parcial (experiencia web, aprendiendo Unreal), que hace la programación y el arte.
- **Alcance para una persona:** el MVP es lo que ya está escrito más policías bot, gráficos en bajo y roles que se distinguen a simple vista (etapa 7). Moto, inventario, ganzúa y ventanas, recuperar contraseña por email y login con Steam pasan a después de la alpha (etapa 10). Con dos personas, el MVP anterior se estimaba en 16 a 24 meses a tiempo parcial.
- **Estimación (gruesa, a tiempo parcial):** prueba online con amigos en 1 a 2 meses; alpha abierta chica en 3 a 6 meses en total. Se rehace después de la prueba con amigos.
- **Por eso existe el MVP 0** (etapas 1 a 5): validar con amigos si el loop divierte antes de invertir en arte y en sistemas grandes.
- **Fuera del MVP:** clanes, territorios, construcción de bases, mercado entre jugadores, lavado de dinero, ciclos de reinicio del servidor. Se evalúan con jugadores reales.
- **Costos conocidos:** VPS propio (ya disponible) y Steam Direct (100 USD por juego, cuando se publique).

## Estado por etapa

| # | Etapa | Estado | Cómo se hace |
| --- | --- | --- | --- |
| 0 | Arquitectura y plan | Hecho | [ARQUITECTURA.md](ARQUITECTURA.md) |
| 1 | MVP 0 en Unreal: personaje, barrio gris, robos, alarmas, policía, cárcel, pistola | **Compila, sin probar** | — |
| 2 | Backend: cuentas (usuario y contraseña), economía con ledger, lista de servidores | **Hecho y probado** (33 pruebas) | [BACKEND.md](BACKEND.md) |
| 3 | Backend en el VPS con HTTPS | DNS creado y scripts ajustados a este VPS (puerto 3700), **sin ejecutar** | [DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md), secciones 1 a 4 |
| 4 | Compilar y probar el juego en la PC de desarrollo | **Compila** con Unreal 5.8.4 (sin errores ni advertencias) y el mapa v5 está armado ([MAPA.md](MAPA.md)). Falta probar con 3 jugadores. Bloquea todo lo de Unreal | [GUIA_DESARROLLO.md](GUIA_DESARROLLO.md) y [PRUEBAS.md](PRUEBAS.md) |
| 5 | Servidor de juego en el VPS | Guía lista, depende de 4 | [DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md), sección 5 |
| 6 | Unreal conectado al backend: pantalla de login, sesión verificada, dinero guardado | **Compila, sin probar** | — |
| 6b | Reglas de roles v2: pasamontañas, salidas, zonas seguras, la policía solo daña ladrones, rendición y esposas, salario de turno, notoriedad, búsqueda por violencia | **Compila, sin probar** | [DISENO_JUEGO.md](DISENO_JUEGO.md) |
| 7 | MVP completo: policías bot, gráficos en bajo (sin ray tracing) con un menú de opciones mínimo, y vecino, ladrón y policía distinguibles a simple vista. Compensación de latencia, solo si la prueba con amigos lo pide | Pendiente, después de 5 | — |
| 8 | Arte: kit modular de Caseros, personajes, armas | En curso: el barrio se genera por script ([MAPA.md](MAPA.md)); faltan personajes y armas | [ARTE.md](ARTE.md) |
| 9 | Alpha abierta chica con 16 jugadores: Discord, descarga gratis (itch.io) y noches de juego en horario fijo. Steam, recién con comunidad | Pendiente | — |
| 10 | Después de la alpha: moto, inventario, ganzúa y ventanas, recuperar contraseña por email (mientras tanto, se resetea a mano), login con Steam | Postergado (alcance para una persona) | — |

**Orden recomendado:** 3 y 4 en paralelo (no dependen entre sí) → 5 (prueba con amigos: ¿divierte?) → pruebas de las etapas 6 y 6b → 7 → 9. La 8 avanza en paralelo todo el tiempo; la 10, después de la alpha.

## Criterios de cierre

| Etapa | Se da por terminada cuando |
| --- | --- |
| 3 | Desde cualquier PC se registra una cuenta y se hace login contra `https://caseros-api.facundofr.com` |
| 4 | Pasan las listas "Fase 1", "Fase 2" y "Loop completo" de [PRUEBAS.md](PRUEBAS.md) con 3 jugadores en el editor |
| 5 | 1 hora de juego con jugadores desde casas distintas, sin caídas |
| 6 | Un jugador vende botín, sale, vuelve a entrar y conserva el dinero ([PRUEBAS.md](PRUEBAS.md), "Cuentas y dinero") |
| 6b | Pasa la lista "Loop completo" de [PRUEBAS.md](PRUEBAS.md) con las reglas v2 |
| 9 | 16 jugadores reales, red y CPU del VPS medidos, encuesta de diversión, política de privacidad publicada (el juego guarda emails: Ley 25.326) |

## Riesgos abiertos

| Riesgo | Mitigación |
| --- | --- |
| Errores de comportamiento en el código de Unreal (compila, pero nunca se probó) | Probar con las listas de [PRUEBAS.md](PRUEBAS.md) antes de escribir más código |
| Alcance demasiado grande para una persona | MVP recortado (etapa 7); lo demás, después de la alpha (etapa 10) |
| El KVM 2 no alcanza para el backend y el juego con 16 jugadores | Medir en la etapa 5. El servidor de juego tiene `MemoryMax=3G` para no afectar a las otras apps. Si no alcanza, separar el servidor de juego |
| El VPS ya tiene otros servicios en producción | El script de instalación convive con ellos y no los modifica ([DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md)) |
| Vehículos en red con tirones | Probarlos aislados antes de integrarlos (etapa 7) |
| Pocos jugadores conectados | Bots policía (etapa 7), servidores siempre abiertos y noches de juego en horario fijo |
| Jugadores con PCs comunes (el juego usa ray tracing por hardware) | Gráficos en bajo (etapa 7) |
| El rol de policía aburre | Recompensas y progresión propias; se mide en la alpha |
| Parecerse demasiado a otro juego | Identidad propia: ver la sección 11 de [DISENO_JUEGO.md](DISENO_JUEGO.md) |
