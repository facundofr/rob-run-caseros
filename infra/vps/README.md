# Despliegue en el VPS (facundofr.com)

VPS Hostinger KVM 2 en Brasil (latencia baja desde Buenos Aires). En el mismo VPS corren:

| Servicio | Dirección | Detalle |
| --- | --- | --- |
| Backend (API) | `https://api.facundofr.com` | Node.js detrás de Caddy, con HTTPS automático. Solo escucha en localhost |
| Base de datos | localhost:5432 | PostgreSQL. No se expone a internet |
| Servidor de juego | `juego.facundofr.com:7777` (UDP) | Unreal, servidor dedicado de 16 jugadores |

La página principal `facundofr.com` no se toca: todo va en subdominios.

## 1. DNS (panel donde está el dominio)

Crear dos registros **A** apuntando a la IP pública del VPS:

| Nombre | Tipo | Valor |
| --- | --- | --- |
| `api` | A | IP del VPS |
| `juego` | A | IP del VPS |

Comprobar desde la PC: `nslookup api.facundofr.com` tiene que devolver la IP del VPS. Puede tardar unos minutos.

## 2. Preparar el VPS y levantar el backend (una sola vez)

Conectarse por SSH como root y ejecutar:

```bash
git clone https://github.com/facundofr/rob-run-caseros.git /opt/barrio/repo
bash /opt/barrio/repo/infra/vps/setup-vps.sh
```

El script [setup-vps.sh](setup-vps.sh):
- Instala Node.js 24, PostgreSQL y Caddy.
- Crea el usuario `barrio` y la base `barrio` con una contraseña aleatoria.
- Genera los secretos (`JWT_SECRET`, `SERVER_API_KEY`) en `/etc/barrio/backend.env`, legible solo por root y el usuario `barrio`.
- Compila el backend y lo deja como servicio (`barrio-backend`), que se reinicia solo si se cae.
- Configura HTTPS para `api.facundofr.com`.
- Abre en el firewall solo SSH, 80, 443 y 7777/UDP.

Se puede volver a ejecutar sin perder datos ni secretos.

**Antes de ejecutarlo**, revisar que en el VPS no haya otro servidor web (Apache o Nginx) ocupando los puertos 80 y 443: `ss -tlnp | grep -E ':80|:443'`. Si lo hay, avisar antes de seguir.

**Comprobar desde la PC:**

```bash
curl https://api.facundofr.com/health          # {"status":"ok"}
curl https://api.facundofr.com/v1/servers      # {"servers":[],"recommended":null}
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
scp -r .\Build\LinuxServer\* root@juego.facundofr.com:/opt/barrio/server/
```

En el VPS:

```bash
chown -R barrio:barrio /opt/barrio/server
chmod +x /opt/barrio/server/BarrioServer.sh
systemctl enable --now barrio-server
journalctl -u barrio-server -f     # tiene que decir que escucha en 7777 y cargó L_Greybox
```

### 4.4 Conectarse

Con un cliente empaquetado en **Development**: `Barrio.exe juego.facundofr.com:7777`.
O desde el editor: **Play → Standalone Game**, consola (`º` o `~`) y `open juego.facundofr.com:7777`.

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
