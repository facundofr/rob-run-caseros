# Guía para asistentes de IA

Punto de entrada para cualquier IA que trabaje en este repositorio (Claude Code, Copilot, Cursor u otra). Leerlo completo antes de actuar. Responder al usuario en **español**.

**Barrio** es un juego multijugador en tercera persona ambientado en Caseros (Unreal Engine 5 + backend Node.js), hecho por una sola persona a tiempo parcial (programación y arte). El índice de la documentación está en [README.md](README.md). Cada tema tiene un único archivo: no repetir contenido entre archivos, enlazar.

## Con quién trabajás

- **Una sola persona, a tiempo parcial**, que viene del desarrollo web: apps React/Next.js y APIs Node.js con Docker, PM2 y Nginx, en el mismo VPS donde corre Barrio. Está aprendiendo Unreal y desarrollo de juegos.
- **Explicar como a alguien nuevo en desarrollo de juegos**, con equivalencias del desarrollo web ([docs/ARQUITECTURA.md](docs/ARQUITECTURA.md), "Para quien viene del desarrollo web"). Español rioplatense (vos).
- **Pide recomendaciones concretas:** decir qué conviene y por qué, en vez de listar opciones.
- **Recursos:** una PC con Windows (Ryzen 7 5700X, 32 GB, RTX 5050 de 8 GB) y un VPS Hostinger KVM 2 compartido con apps de clientes en producción. Nada de infraestructura paga hasta tener jugadores.

## Dónde estás trabajando

El proyecto se trabaja desde dos lugares ([docs/ENTORNOS.md](docs/ENTORNOS.md)). Antes de actuar, identificar en cuál estás:

| Si... | Estás en | Podés | No podés |
| --- | --- | --- | --- |
| El sistema es Windows | **PC de desarrollo** | Todo lo de Unreal (compilar, editor, empaquetar), backend, documentación | Tocar el VPS directamente (solo por SSH o `scp`, con confirmación del usuario) |
| El sistema es Linux y existe `/opt/barrio` | **VPS de producción** | Backend en `/var/www/rob-run-caseros/rob-run-caseros`, `npm test`, desplegar con `deploy-backend.sh`, ver logs y estado de servicios | Compilar Unreal o correr tareas pesadas; editar `/opt/barrio/repo` a mano; tocar las apps React, Nginx/Caddy de otros sitios o `api.facundofr.com` |

En el VPS, todo comando con `sudo`, reinicio de servicios o cambio de configuración se le muestra al usuario y espera su confirmación.

## Antes de actuar

1. **Estado real del proyecto:** [docs/PLAN.md](docs/PLAN.md). En resumen: el backend está probado; el código de Unreal compila con UE 5.8.4 y el mapa v5 está armado, pero **nunca se probó**: al jugar van a aparecer errores. El alcance del MVP está recortado para una persona. **Lo próximo está en la sección "Ahora" del plan.**
2. **Reglas del juego:** [docs/DISENO_JUEGO.md](docs/DISENO_JUEGO.md) es la fuente de verdad: el código se ajusta a ese documento.
3. **Arquitectura:** [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## Decisiones tomadas

Cada una está explicada, con su motivo, en el documento enlazado. No volver a discutirlas sin un dato nuevo (por ejemplo, una medición o el resultado de una prueba con jugadores).

| Decisión | Dónde está |
| --- | --- |
| MVP recortado para una persona: lo ya escrito más policías bot, gráficos en bajo y roles visibles. Moto, inventario, ganzúa y ventanas, email de recuperación y Steam, después de la alpha | [docs/PLAN.md](docs/PLAN.md), "Equipo, alcance y estimación" |
| Lanzamiento: prueba con amigos → alpha abierta chica (Discord, itch.io) → Steam cuando haya comunidad | [docs/PLAN.md](docs/PLAN.md), "Equipo, alcance y estimación" |
| Salas de 16 jugadores, no un MMO | [docs/DISENO_JUEGO.md](docs/DISENO_JUEGO.md), sección 11 |
| Servidor de juego por fases: el VPS actual → un VPS propio para el juego → un orquestador | [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md), sección 6 |
| Unreal se compila y se empaqueta solo en la PC; el VPS recibe el servidor ya empaquetado | [docs/ENTORNOS.md](docs/ENTORNOS.md), sección 1 |
| Backend en `127.0.0.1:3700`, instalación que no actualiza ni reinicia nada de las otras apps, servidor de juego con `MemoryMax=3G` | [docs/DESPLIEGUE_VPS.md](docs/DESPLIEGUE_VPS.md) |

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
- **La IA no puede usar `sudo`** (pide contraseña). Preparar el comando exacto y que lo corra el usuario, con `2>&1 | tee ~/<nombre>.log` si hay que revisar la salida. Después, verificar sin `sudo`: `systemctl is-active`, `curl`, `ss -tlnp`.
- **Los logs de systemd no se ven sin `sudo`**, salvo que el usuario esté en el grupo `systemd-journal` ([docs/ENTORNOS.md](docs/ENTORNOS.md), sección 3.2). Si no está, pedirle la salida de `sudo journalctl -u <servicio> -n 100 --no-pager`.
- **No correr `apt upgrade` ni `apt autoremove`, ni reiniciar servicios compartidos** (Nginx, PostgreSQL, Docker), sin que el usuario lo decida. Antes de dar por terminado un cambio en el VPS, comprobar que los otros sitios sigan respondiendo como antes.
- En la copia del VPS, los `.uasset` y `.umap` son **punteros de Git LFS** de unos 130 bytes: es lo esperado, porque el VPS no los usa. No instalar LFS ni "arreglarlos".
- Las pruebas del backend tardan unos 2 minutos en el VPS (por el costo de scrypt): no están colgadas.

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
