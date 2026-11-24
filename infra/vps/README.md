# Despliegue en el VPS (facundofr.com)

VPS Hostinger KVM 2 en Brasil (latencia baja desde Buenos Aires). En el mismo VPS corren:

| Servicio | Dirección | Detalle |
| --- | --- | --- |
| Backend (API) | `https://caseros-api.facundofr.com` | Node.js detrás de Nginx o Caddy, con HTTPS automático. Solo escucha en `127.0.0.1:3100` |
| Base de datos | localhost:5432 | PostgreSQL. No se expone a internet |
| Servidor de juego | `caseros.facundofr.com:7777` (UDP) | Unreal, servidor dedicado de 16 jugadores |

La página principal `facundofr.com` y los demás servicios del VPS (por ejemplo, lo que ya responde en `api.facundofr.com`) no se tocan: todo va en subdominios propios.

## 1. DNS (panel donde está el dominio)

Crear dos registros **A** apuntando a la IP pública del VPS:

| Nombre | Tipo | Valor |
| --- | --- | --- |
| `caseros-api` | A | IP del VPS |
| `caseros` | A | IP del VPS |

Si alguno de estos nombres también estuviera ocupado, se pueden usar otros: el script acepta `API_DOMAIN=... GAME_DOMAIN=...`.

Comprobar desde la PC: `nslookup caseros-api.facundofr.com` tiene que devolver la IP del VPS. Puede tardar unos minutos.

## 2. Preparar el VPS y levantar el backend (una sola vez)

Conectarse por SSH como root y ejecutar:

```bash
git clone https://github.com/facundofr/rob-run-caseros.git /opt/barrio/repo
bash /opt/barrio/repo/infra/vps/setup-vps.sh
```

El script [setup-vps.sh](setup-vps.sh) está pensado para **convivir con lo que ya corre en el VPS**:
- Instala su propio Node.js 24 en `/opt/barrio/node`. No cambia el Node del sistema ni el de otras aplicaciones.
- Usa PostgreSQL (lo instala si falta) con una base y un usuario propios, `barrio`, con contraseña aleatoria.
- El backend escucha en `127.0.0.1:3100`. Si ese puerto está ocupado, se detiene y avisa (`BACKEND_PORT=otro` para cambiarlo).
- HTTPS: si el VPS ya usa **Nginx**, agrega un sitio nuevo y saca el certificado con certbot. Si usa **Caddy**, agrega un archivo importado y guarda copia del Caddyfile. Si no hay ninguno, instala Caddy. **Nunca reemplaza la configuración de otros sitios.** Con Apache se detiene y explica qué agregar a mano.
- Firewall: si `ufw` está activo, agrega 80, 443 y 7777/UDP. Si está apagado, no lo activa, para no cortar otros servicios.
- Genera los secretos en `/etc/barrio/backend.env` y la configuración del servidor de juego en `/etc/barrio/gameserver.env`, legibles solo por root y el usuario `barrio`.
- Deja el backend como servicio (`barrio-backend`), que se reinicia solo si se cae.

Se puede volver a ejecutar sin perder datos ni secretos.

**Antes de ejecutarlo**, conviene ver qué servidor web usa el VPS: `systemctl is-active nginx caddy apache2`.

**Comprobar desde la PC:**

```bash
curl https://caseros-api.facundofr.com/health          # {"status":"ok"}
curl https://caseros-api.facundofr.com/v1/servers      # {"servers":[],"recommended":null}
```

## 3. Actualizar el backend

Cada vez que hay cambios en GitHub:

```bash
bash /opt/barrio/repo/infra/vps/deploy-backend.sh
```

Baja lo último, compila, reinicia y comprueba que responda. Las migraciones de la base se aplican solas.

## 4. Servidor de juego

### 4.1 Compilar el motor desde el código fuente (PC de desarrollo, una sola vez)

El Unreal del Epic Games Launcher no puede generar servidores dedicados.

1. Vincular la cuenta de Epic con GitHub (en epicgames.com: Cuenta → Aplicaciones y cuentas → GitHub) y aceptar la invitación a la organización **EpicGames**.
2. Clonar `https://github.com/EpicGames/UnrealEngine` en la etiqueta de la **misma versión** que usa el proyecto (`5.x.y-release`).
3. Ejecutar `Setup.bat` y `GenerateProjectFiles.bat`.
4. Abrir `UE5.sln` y compilar **UnrealEditor** en *Development Editor / Win64*. Con un Ryzen 7 5700X tarda entre 1 y 2 horas y ocupa más de 200 GB.
5. Instalar el **toolchain de compilación cruzada para Linux** que indica la documentación de Epic para esa versión ("Linux Development Requirements"). Reiniciar.
6. Clic derecho en `Barrio.uproject` → **Switch Unreal Engine version** → el motor compilado.

### 4.2 Empaquetar

En el editor: **Platforms → Linux → Build Target: BarrioServer**, configuración **Development** → **Package Project** en `Build/LinuxServer`.

### 4.3 Subir y arrancar

Desde la PC (PowerShell):

```powershell
scp -r .\Build\LinuxServer\* root@caseros.facundofr.com:/opt/barrio/server/
```

En el VPS:

```bash
chown -R barrio:barrio /opt/barrio/server
chmod +x /opt/barrio/server/BarrioServer.sh
systemctl enable --now barrio-server
journalctl -u barrio-server -f     # tiene que decir que escucha en 7777 y cargó L_Greybox
```

### 4.4 Conectarse

Con un cliente empaquetado en **Development**: `Barrio.exe caseros.facundofr.com:7777`.
O desde el editor: **Play → Standalone Game**, consola (`º` o `~`) y `open caseros.facundofr.com:7777`.

Hasta que esté la integración con el backend (etapa 4 del plan), el servidor de juego no pide login: cualquiera con la dirección puede entrar. Compartirla solo con los testers.

## Comandos útiles

| Para | Comando |
| --- | --- |
| Estado de los servicios | `systemctl status barrio-backend barrio-server caddy postgresql` |
| Log del backend | `journalctl -u barrio-backend -f` |
| Log del servidor de juego | `journalctl -u barrio-server -f` |
| Ver la clave para el servidor de juego | `grep SERVER_API_KEY /etc/barrio/backend.env` |
| Backup de la base | `sudo -u postgres pg_dump barrio > /root/barrio-$(date +%F).sql` |

## Problemas comunes

| Síntoma | Causa probable |
| --- | --- |
| `curl https://api...` falla por certificado | El DNS todavía no apunta al VPS, o el puerto 80 está bloqueado (Let's Encrypt lo necesita) |
| Caddy no arranca | Otro servidor web ocupa el 80 o el 443 |
| El cliente no conecta al juego | Puerto 7777 UDP cerrado en `ufw` o en el firewall del panel de Hostinger |
| Desconexión inmediata o "version mismatch" | Cliente y servidor empaquetados desde versiones distintas del código |
| El servidor de juego se cierra al arrancar | Ver `journalctl -u barrio-server`; suele ser el mapa faltante en el empaquetado |
