# Plan de acción hasta el MVP

Actualizado: 24 de noviembre de 2026.

Objetivo: un MVP jugable por internet con 16 jugadores en `caseros.facundofr.com`, con cuentas de usuario y contraseña, dinero que se conserva entre sesiones y el loop robo → alarma → persecución → escape o arresto.

## Estado

| # | Etapa | Estado | Dónde |
| --- | --- | --- | --- |
| 0 | Arquitectura y plan | Hecho | `docs/FASE0_INFORME.md` |
| 1 | MVP 0 en Unreal: personaje, barrio gris, robos, alarmas, policía, cárcel, pistola | **Código escrito, sin compilar** | `game/` |
| 2 | Backend: cuentas, economía con ledger, servidores | Hecho y probado (32 pruebas) | `backend/` |
| 2b | Login con usuario y contraseña | Hecho y probado | `backend/` |
| 3 | Backend en el VPS con HTTPS | Scripts listos, falta ejecutarlos | `infra/vps/` |
| 4 | Compilar y probar el MVP 0 en la PC de desarrollo | **Pendiente: bloquea las etapas de Unreal** | PC de desarrollo |
| 5 | Servidor de juego en el VPS | Guía lista, depende de 4 | `infra/vps/` |
| 6 | Unreal conectado al backend: pantalla de login, verificación de sesión, dinero persistente | Pendiente | `game/` |
| 7 | MVP completo: bots policía, inventario, moto, compensación de latencia | Pendiente | `game/` |
| 8 | Arte del barrio (kit modular de Caseros) | Pendiente, en paralelo | Diseñador |
| 9 | Alpha cerrada con 16 jugadores | Pendiente | VPS |

## Detalle de lo que falta

### 3. Backend en el VPS
1. Crear los registros DNS `api` y `juego` apuntando a la IP del VPS.
2. Revisar que no haya otro servidor web en los puertos 80 y 443.
3. Ejecutar `infra/vps/setup-vps.sh` (ver `infra/vps/README.md`).
4. Comprobar `https://caseros-api.facundofr.com/health`.

**Criterio de cierre:** desde cualquier PC se puede registrar una cuenta y hacer login contra `https://caseros-api.facundofr.com`.

### 4. Compilar y probar el MVP 0
1. Instalar Unreal 5.x y Visual Studio 2022 en la PC de desarrollo (Ryzen 7 5700X, 32 GB, RTX 5050).
2. Clonar el repo, compilar y corregir los errores de la primera compilación.
3. Armar el mapa según el README y pasar la lista de pruebas (un jugador, multijugador, loop completo).

**Criterio de cierre:** la lista de pruebas del README completa con 3 jugadores en el editor.

### 5. Servidor de juego en el VPS
1. Compilar el motor desde el código fuente.
2. Empaquetar `BarrioServer` para Linux y subirlo.
3. Repetir el loop completo con jugadores desde casas distintas, conectados a `caseros.facundofr.com:7777`.

**Criterio de cierre:** 1 hora de juego con varios jugadores sin caídas.

### 6. Unreal conectado al backend
Nuevo módulo `BarrioOnline`:
1. **Pantalla de login y registro** (usuario, contraseña, email opcional) con los mensajes de error que devuelve el backend.
2. El cliente guarda el token de sesión y se conecta pasándolo en la URL (`caseros.facundofr.com:7777?token=...`).
3. El servidor de juego verifica el token con `/v1/sessions/verify` antes de aceptar al jugador; si falla, lo rechaza.
4. El servidor de juego se registra al arrancar y envía heartbeat cada 15 s.
5. Vender al reducidor y cobrar recompensas pasa por `/v1/economy/transactions`: el dinero se conserva entre sesiones.
6. Selección de servidor: el cliente pide `/v1/servers` y entra al recomendado.

**Criterio de cierre:** un jugador vende botín, sale, vuelve a entrar y conserva el dinero.

### 7. MVP completo
- Bots policía que cubren los cupos vacíos.
- Inventario por ranuras, persistente.
- Un vehículo (moto, por la ambientación), probado primero en red de forma aislada.
- Compensación de latencia en los disparos.
- Recuperación de contraseña por email (requiere un servicio de envío de mails) y vinculación con Steam.

### 8. Arte
- Guía de arte de Caseros (paleta, referencias, escala, presupuesto de polígonos).
- Kit modular: fachadas, rejas, portones, persianas, veredas, cordones, postes. Se puede generar una base con scripts de Blender.
- Armas y personajes: diseñador, assets de Fab o Mixamo.

### 9. Alpha cerrada
- 16 jugadores reales, medir red, CPU del VPS y diversión (encuesta).
- Política de privacidad publicada (el juego guarda emails: Ley 25.326).

## Riesgos abiertos

| Riesgo | Mitigación |
| --- | --- |
| Muchos errores en la primera compilación de Unreal | Compilar cuanto antes; no seguir escribiendo código de Unreal sin compilar |
| El KVM 2 no alcanza para backend + juego con 16 jugadores | Medir en la etapa 5; si hace falta, separar el servidor de juego |
| Ataques de fuerza bruta al login | Ya mitigado: límite por IP, bloqueo de cuenta a los 5 intentos, hash scrypt |
