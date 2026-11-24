# Despliegue en el VPS

Guía única para poner Barrio en el VPS: Hostinger KVM 2 en Brasil, con Ubuntu y el dominio `facundofr.com`. Estado de cada paso: [PLAN.md](PLAN.md), etapas 3 y 5.

| Servicio | Dirección | Detalle |
| --- | --- | --- |
| Backend (API) | `https://caseros-api.facundofr.com` | Node.js detrás de Nginx o Caddy, con HTTPS. Escucha solo en `127.0.0.1:3100` |
| Base de datos | `127.0.0.1:5432` | PostgreSQL. No se expone a internet |
| Servidor de juego | `caseros.facundofr.com:7777` (UDP) | Unreal, servidor dedicado de 16 jugadores |

La página principal `facundofr.com` y los demás servicios del VPS (por ejemplo, lo que ya responde en `api.facundofr.com`) **no se tocan**: Barrio usa subdominios propios.

**Capacidad del KVM 2** (2 vCPU y 8 GB de RAM, a confirmar en el panel): alcanza para el backend, la base y 1 instancia de 16 jugadores durante el desarrollo y la alpha. El consumo real se mide en la etapa 5.

## 1. DNS

En el panel donde está el dominio, crear dos registros **A** con la IP pública del VPS:

| Nombre | Tipo | Valor |
| --- | --- | --- |
| `caseros-api` | A | IP del VPS |
| `caseros` | A | IP del VPS |

Si alguno de esos nombres también estuviera ocupado, se pueden usar otros: el script acepta `API_DOMAIN=... GAME_DOMAIN=...`.

Comprobar desde la PC: `nslookup caseros-api.facundofr.com` tiene que devolver la IP del VPS. Puede tardar unos minutos.

## 2. Qué se instala en el VPS

El VPS ya tiene Ubuntu con lo necesario para aplicaciones React. **No hay que instalar nada a mano**: el script de la sección 3 instala lo que falta y no modifica lo que ya está.

| Qué | Para qué | Cómo lo instala el script | ¿Afecta lo que ya corre? |
| --- | --- | --- | --- |
| **Node.js 24** | Correr el backend | Copia propia en `/opt/barrio/node`, descargada de nodejs.org y verificada | **No.** El Node del sistema y el de las apps React quedan igual |
| **PostgreSQL** | Base de datos del juego | `apt` (si ya está instalado, lo reutiliza) | No: crea una base y un usuario propios, `barrio` |
| **HTTPS** | Certificado para `caseros-api` | Si ya hay **Nginx**: agrega un sitio y usa `certbot`. Si ya hay **Caddy**: agrega un archivo importado. Si no hay ninguno: instala Caddy | No: nunca reemplaza la configuración de otros sitios. Con Apache se detiene y explica qué hacer |
| `git`, `curl`, `openssl`, `xz-utils` | Bajar el repo, generar secretos, descomprimir Node | `apt` | No |
| **Servidor de juego de Unreal** | El juego en sí | No se instala: se sube ya compilado desde la PC de desarrollo (sección 5). Es autocontenido y no necesita dependencias extra | No |

**Puertos que tienen que estar abiertos** (en `ufw` si está activo, y en el firewall del panel de Hostinger): **80/tcp** y **443/tcp**, para HTTPS (probablemente ya estén abiertos por las apps React), y **7777/udp**, para el juego.

**Antes de instalar**, conviene revisar qué corre en el VPS:

```bash
systemctl is-active nginx caddy apache2   # qué servidor web usa
ss -tlnp | grep -E ':80 |:443 |:3100 '    # puertos ocupados
```

## 3. Instalar y levantar el backend (una sola vez)

Por SSH, como root:

```bash
git clone https://github.com/facundofr/rob-run-caseros.git /opt/barrio/repo
bash /opt/barrio/repo/infra/vps/setup-vps.sh
```

Variables opcionales, antes del `bash`: `API_DOMAIN`, `GAME_DOMAIN`, `BACKEND_PORT` (por defecto 3100) y `CERTBOT_EMAIL`.

El script [setup-vps.sh](../infra/vps/setup-vps.sh):
- Instala lo de la tabla de la sección 2.
- Genera los secretos en `/etc/barrio/backend.env` y la configuración del servidor de juego en `/etc/barrio/gameserver.env`. Los dos archivos son legibles solo por root y el usuario `barrio`. **Nunca copiarlos al repositorio ni a un chat.**
- Deja el backend como servicio (`barrio-backend`), que se reinicia solo si se cae.
- Si `ufw` está activo, agrega los puertos. Si está apagado, no lo activa, para no cortar otros servicios.
- Se puede volver a ejecutar sin perder datos ni secretos.

**Comprobar desde la PC:**

```bash
curl https://caseros-api.facundofr.com/health       # {"status":"ok"}
curl https://caseros-api.facundofr.com/v1/servers   # {"servers":[],"recommended":null}
```

Para probar el registro de una cuenta, ver `POST /v1/auth/register` en [BACKEND.md](BACKEND.md).

## 4. Actualizar el backend

Cada vez que hay cambios en GitHub:

```bash
bash /opt/barrio/repo/infra/vps/deploy-backend.sh
```

Baja lo último, compila, reinicia y comprueba que responda. Las migraciones de la base se aplican solas.

## 5. Servidor de juego

Requiere que el juego ya compile y funcione en la PC de desarrollo ([GUIA_DESARROLLO.md](GUIA_DESARROLLO.md)).

### 5.1 Compilar el motor desde el código fuente (PC de desarrollo, una sola vez)

El Unreal del Epic Games Launcher no puede generar servidores dedicados.

1. Vincular la cuenta de Epic con GitHub (en epicgames.com: Cuenta → Aplicaciones y cuentas → GitHub) y aceptar la invitación a la organización **EpicGames**.
2. Clonar `https://github.com/EpicGames/UnrealEngine` en la etiqueta de la **misma versión** que usa el proyecto (`5.x.y-release`).
3. Ejecutar `Setup.bat` y `GenerateProjectFiles.bat`.
4. Abrir `UE5.sln` y compilar **UnrealEditor** en *Development Editor / Win64*. Con un Ryzen 7 5700X tarda entre 1 y 2 horas y ocupa más de 200 GB.
5. Instalar el **toolchain de compilación cruzada para Linux** que indica la documentación de Epic para esa versión ("Linux Development Requirements"). Reiniciar.
6. Clic derecho en `Barrio.uproject` → **Switch Unreal Engine version** → el motor compilado.

### 5.2 Empaquetar

En el editor: **Platforms → Linux → Build Target: BarrioServer**, configuración **Development** → **Package Project** en `Build/LinuxServer`.

### 5.3 Subir y arrancar

Desde la PC (PowerShell):

```powershell
scp -r .\Build\LinuxServer\* root@caseros.facundofr.com:/opt/barrio/server/
```

En el VPS:

```bash
chown -R barrio:barrio /opt/barrio/server
chmod +x /opt/barrio/server/BarrioServer.sh
systemctl enable --now barrio-server
journalctl -u barrio-server -f   # tiene que decir que escucha en 7777, cargó L_Greybox y se registró en el backend
```

El servicio lee `/etc/barrio/gameserver.env`. Con ese archivo, el servidor se registra en el backend y **exige login**. Sin él, cualquiera con la dirección puede entrar y nada se guarda.

### 5.4 Conectarse

Con un cliente empaquetado en **Development**: al abrir `Barrio.exe` aparece la pantalla de login. Después de iniciar sesión entra solo a `caseros.facundofr.com:7777`. Pruebas: [PRUEBAS.md](PRUEBAS.md), "Cuentas y dinero".

## Comandos útiles

| Para | Comando |
| --- | --- |
| Estado de los servicios | `systemctl status barrio-backend barrio-server postgresql` |
| Log del backend | `journalctl -u barrio-backend -f` |
| Log del servidor de juego | `journalctl -u barrio-server -f` |
| Clave del servidor de juego | `grep SERVER_API_KEY /etc/barrio/backend.env` |
| Backup de la base | `sudo -u postgres pg_dump barrio > /root/barrio-$(date +%F).sql` |

## Problemas comunes

| Síntoma | Causa probable |
| --- | --- |
| `curl https://caseros-api...` falla por certificado | El DNS todavía no apunta al VPS, o el puerto 80 está cerrado (Let's Encrypt lo necesita) |
| El script se detiene con "puerto en uso" | Otro servicio usa el 3100: volver a ejecutar con `BACKEND_PORT=<otro puerto libre>` |
| Caddy no arranca | Otro servidor web ocupa el 80 o el 443 y no fue detectado: revisar con `ss -tlnp` |
| El cliente no conecta al juego | Puerto 7777/UDP cerrado en `ufw` o en el firewall del panel de Hostinger |
| Expulsado al entrar con "La sesión venció" | El token dura 15 minutos: volver a iniciar sesión |
| Desconexión inmediata o "version mismatch" | Cliente y servidor empaquetados desde versiones distintas del código |
| El servidor de juego se cierra al arrancar | Ver `journalctl -u barrio-server`; suele ser el mapa faltante en el empaquetado |
