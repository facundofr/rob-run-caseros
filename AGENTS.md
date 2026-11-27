# Guía para asistentes de IA

Punto de entrada para cualquier IA que trabaje en este repositorio (Claude Code, Copilot, Cursor u otra). Leerlo completo antes de actuar. Responder al usuario en **español**.

**Barrio** es un juego multijugador en tercera persona ambientado en Caseros (Unreal Engine 5 + backend Node.js), hecho por una sola persona a tiempo parcial (programación y arte). El índice de la documentación está en [README.md](README.md). Cada tema tiene un único archivo: no repetir contenido entre archivos, enlazar.

## Dónde estás trabajando

El proyecto se trabaja desde dos lugares ([docs/ENTORNOS.md](docs/ENTORNOS.md)). Antes de actuar, identificar en cuál estás:

| Si... | Estás en | Podés | No podés |
| --- | --- | --- | --- |
| El sistema es Windows | **PC de desarrollo** | Todo lo de Unreal (compilar, editor, empaquetar), backend, documentación | Tocar el VPS directamente (solo por SSH o `scp`, con confirmación del usuario) |
| El sistema es Linux y existe `/opt/barrio` | **VPS de producción** | Backend en `/var/www/rob-run-caseros/rob-run-caseros`, `npm test`, desplegar con `deploy-backend.sh`, ver logs y estado de servicios | Compilar Unreal o correr tareas pesadas; editar `/opt/barrio/repo` a mano; tocar las apps React, Nginx/Caddy de otros sitios o `api.facundofr.com` |

En el VPS, todo comando con `sudo`, reinicio de servicios o cambio de configuración se le muestra al usuario y espera su confirmación.

## Antes de actuar

1. **Estado real del proyecto:** [docs/PLAN.md](docs/PLAN.md). En resumen: el backend está probado; el código de Unreal compila con UE 5.8.4 y el mapa v5 está armado, pero **nunca se probó**: al jugar van a aparecer errores. El alcance del MVP está recortado para una persona (ver el plan).
2. **Reglas del juego:** [docs/DISENO_JUEGO.md](docs/DISENO_JUEGO.md) es la fuente de verdad: el código se ajusta a ese documento.
3. **Arquitectura:** [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Cómo levantar todo (orden)

Seguir los documentos enlazados; no inventar pasos que no estén ahí. Si algo falla, diagnosticar con el log antes de cambiar código.

| Orden | Qué | Guía |
| --- | --- | --- |
| 1 | Backend en el VPS (DNS, instalación, HTTPS) | [docs/DESPLIEGUE_VPS.md](docs/DESPLIEGUE_VPS.md), secciones 1 a 4 |
| 2 | Compilar el juego en la PC de desarrollo, corregir errores, armar el mapa | [docs/GUIA_DESARROLLO.md](docs/GUIA_DESARROLLO.md) |
| 3 | Probar en el editor con 3 jugadores | [docs/PRUEBAS.md](docs/PRUEBAS.md) |
| 4 | Servidor de juego en el VPS | [docs/DESPLIEGUE_VPS.md](docs/DESPLIEGUE_VPS.md), sección 5 |
| 5 | Lo que sigue | [docs/PLAN.md](docs/PLAN.md) |

Los pasos 1 y 2 no dependen entre sí.

## Cuidados con el VPS

- **El VPS tiene otros servicios en producción** (apps React; el subdominio `api.facundofr.com` ya está en uso). No tocar su configuración. Barrio usa `caseros-api.facundofr.com` y `caseros.facundofr.com`.
- Revisar qué corre (`systemctl is-active nginx caddy apache2`, `ss -tlnp`) antes de instalar nada.
- Los secretos viven solo en el VPS (`/etc/barrio/*.env`). **Nunca copiarlos al repositorio ni a un chat.**

## Reglas de trabajo

- **Subir cada cambio a GitHub:** commit con mensaje en español y push a `main` de `facundofr/rob-run-caseros`. El repositorio es **público**: nada de secretos, IPs privadas ni contraseñas.
- **No escribir más código de Unreal hasta probar el existente** con [docs/PRUEBAS.md](docs/PRUEBAS.md). Hay cuatro etapas que compilan pero nunca se probaron.
- **Dependencias entre módulos de Unreal** según [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md), sección 7: `BarrioCore` no depende de nadie, nadie depende de `BarrioUI`, las reglas viven en el GameMode y los sistemas se comunican por eventos.
- **Servidor autoritativo:** el cliente pide y el servidor valida (dinero, daño, botín, roles). El dinero solo se mueve por el backend, con transacciones idempotentes.
- **Identidad propia:** se toman mecánicas del género, pero no nombres, personajes, objetos, valores ni estética de otros juegos (en particular de ROB RUN). Los análisis de mercado están en `docs/referencias/`, que está en `.gitignore` y no se publica.
- **Sin marcas reales** en el arte; la policía es ficticia.
- **Documentación al día:** si cambia una regla, actualizar [docs/DISENO_JUEGO.md](docs/DISENO_JUEGO.md). Al terminar algo, actualizar [docs/PLAN.md](docs/PLAN.md) y [CHANGELOG.md](CHANGELOG.md). Cada dato se guarda en un solo archivo.

## Comandos útiles

| Para | Comando |
| --- | --- |
| Pruebas del backend | `cd backend && npm install && npm test` |
| Backend local (sin instalar Postgres) | `cd backend && cp .env.example .env && npm run dev` |
| Servicios y logs en el VPS | [docs/DESPLIEGUE_VPS.md](docs/DESPLIEGUE_VPS.md), "Comandos útiles" |
