# Plan de acción

Actualizado: 24 de noviembre de 2026. **Única fuente del estado del proyecto**: los demás documentos remiten acá.

**Objetivo del MVP:** jugable por internet en `caseros.facundofr.com`, con 16 jugadores, cuentas de usuario y contraseña, dinero que se conserva entre sesiones y el loop completo: vecino → pasamontañas → robo → escape por una salida del barrio → venta, contra policías jugadores. Las reglas están en [DISENO_JUEGO.md](DISENO_JUEGO.md).

## Equipo y estimación

- **Equipo:** 1 programador a tiempo parcial (experiencia web, aprendiendo Unreal) y 1 diseñador.
- **Estimación del MVP completo:** 16 a 24 meses a tiempo parcial (8 a 12 a tiempo completo). Es una estimación gruesa que se ajusta después de la primera compilación.
- **Por eso existe el MVP 0** (etapas 1 a 5): validar con amigos si el loop divierte antes de invertir en arte y en sistemas grandes.
- **Fuera del MVP:** clanes, territorios, construcción de bases, mercado entre jugadores, lavado de dinero, ciclos de reinicio del servidor. Se evalúan con jugadores reales.
- **Costos conocidos:** VPS propio (ya disponible) y Steam Direct (100 USD por juego, cuando se publique).

## Estado por etapa

| # | Etapa | Estado | Cómo se hace |
| --- | --- | --- | --- |
| 0 | Arquitectura y plan | Hecho | [ARQUITECTURA.md](ARQUITECTURA.md) |
| 1 | MVP 0 en Unreal: personaje, barrio gris, robos, alarmas, policía, cárcel, pistola | **Compila, sin probar** | — |
| 2 | Backend: cuentas (usuario y contraseña), economía con ledger, lista de servidores | **Hecho y probado** (33 pruebas) | [BACKEND.md](BACKEND.md) |
| 3 | Backend en el VPS con HTTPS | Scripts listos, **sin ejecutar** | [DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md), secciones 1 a 4 |
| 4 | Compilar y probar el juego en la PC de desarrollo | **Compila** con Unreal 5.8.4 (sin errores ni advertencias). Falta armar el mapa y probar con 3 jugadores. Bloquea todo lo de Unreal | [GUIA_DESARROLLO.md](GUIA_DESARROLLO.md) y [PRUEBAS.md](PRUEBAS.md) |
| 5 | Servidor de juego en el VPS | Guía lista, depende de 4 | [DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md), sección 5 |
| 6 | Unreal conectado al backend: pantalla de login, sesión verificada, dinero guardado | **Compila, sin probar** | — |
| 6b | Reglas de roles v2: pasamontañas, salidas, zonas seguras, la policía solo daña ladrones, rendición y esposas, salario de turno, notoriedad, búsqueda por violencia | **Compila, sin probar** | [DISENO_JUEGO.md](DISENO_JUEGO.md) |
| 7 | MVP completo: bots policía, ganzúa y ventanas, inventario, moto, compensación de latencia, recuperar contraseña por email | Pendiente, después de 4 | — |
| 8 | Arte: kit modular de Caseros, personajes, armas, moto | Pendiente, en paralelo | [ARTE.md](ARTE.md) |
| 9 | Alpha cerrada con 16 jugadores | Pendiente | — |

**Orden recomendado:** 3 y 4 en paralelo (no dependen entre sí) → 5 → pruebas de las etapas 6 y 6b → 7 → 9. La 8 avanza en paralelo todo el tiempo.

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
| El KVM 2 no alcanza para el backend y el juego con 16 jugadores | Medir en la etapa 5. Si no alcanza, separar el servidor de juego |
| El VPS ya tiene otros servicios en producción | El script de instalación convive con ellos y no los modifica ([DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md)) |
| Vehículos en red con tirones | Probarlos aislados antes de integrarlos (etapa 7) |
| Pocos jugadores conectados | Bots policía y servidores siempre abiertos (etapa 7) |
| El rol de policía aburre | Recompensas y progresión propias; se mide en la alpha |
| Parecerse demasiado a otro juego | Identidad propia: ver la sección 11 de [DISENO_JUEGO.md](DISENO_JUEGO.md) |
