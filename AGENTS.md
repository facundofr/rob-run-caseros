# Guía para asistentes de IA

Punto de entrada para cualquier IA que trabaje en este repositorio (Claude Code, Copilot, Cursor u otra). Leerlo completo antes de actuar. Responder al usuario en **español**.

**Barrio** es un juego multijugador en tercera persona ambientado en Caseros (Unreal Engine 5 + backend Node.js), hecho por un programador a tiempo parcial y un diseñador. El índice de la documentación está en [README.md](README.md). Cada tema tiene un único archivo: no repetir contenido entre archivos, enlazar.

## Antes de actuar

1. **Estado real del proyecto:** [docs/PLAN.md](docs/PLAN.md). En resumen: el backend está probado; los scripts del VPS nunca se ejecutaron; **el código de Unreal nunca se compiló** y la primera compilación va a dar errores.
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
- **No escribir más código de Unreal hasta compilar el existente.** Ya hay cuatro etapas sin compilar.
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
