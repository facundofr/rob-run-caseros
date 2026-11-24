# Servidor dedicado en el VPS (Hostinger KVM 2)

Pasos para correr el servidor del MVP 0 en el VPS con Linux (Ubuntu). Se hace una vez; después, cada actualización repite solo los pasos 4 y 5.

## 1. Antes de empezar

- Desde el panel de Hostinger, anotar la **IP pública** y la **ubicación del datacenter**. Para jugar desde Buenos Aires conviene Brasil; si está en EE.UU. o Europa, el ping va a estar entre 150 y 250 ms.
- El servidor se compila en la PC de desarrollo, no en el VPS.

## 2. Compilar el motor desde el código fuente (PC de desarrollo, una sola vez)

El Unreal del Epic Games Launcher no puede generar servidores dedicados.

1. Vincular la cuenta de Epic con GitHub (en epicgames.com, Cuenta → Aplicaciones y cuentas → GitHub) y aceptar la invitación a la organización **EpicGames** en GitHub.
2. Clonar `https://github.com/EpicGames/UnrealEngine`, rama de la **misma versión** que se usa en el proyecto (por ejemplo `5.x` → la etiqueta `5.x.y-release`).
3. Ejecutar `Setup.bat` y luego `GenerateProjectFiles.bat`.
4. Abrir `UE5.sln` y compilar **UnrealEditor** en *Development Editor / Win64*. Con un Ryzen 7 5700X tarda entre 1 y 2 horas. Ocupa más de 200 GB.
5. Instalar el **toolchain de compilación cruzada para Linux** que indica la documentación de Epic para esa versión del motor ("Linux Development Requirements"). Reiniciar la PC después.
6. Clic derecho en `Barrio.uproject` → **Switch Unreal Engine version** → elegir el motor compilado.

## 3. Preparar el VPS (una sola vez)

Conectarse por SSH (`ssh root@IP`) y ejecutar:

```bash
apt update && apt upgrade -y
adduser --disabled-password --gecos "" barrio
mkdir -p /opt/barrio/server && chown -R barrio:barrio /opt/barrio
ufw allow OpenSSH
ufw allow 7777/udp
ufw enable
```

Además, en el panel de Hostinger, si hay un firewall propio, abrir **UDP 7777**.

## 4. Empaquetar el servidor (PC de desarrollo)

En el editor (con el motor compilado del paso 2):

1. **Platforms → Linux → Build Target: BarrioServer**, configuración **Development**.
2. **Platforms → Linux → Package Project**. Elegir una carpeta de salida, por ejemplo `Build/LinuxServer`.

## 5. Subir y arrancar

Desde la PC de desarrollo (PowerShell), con la carpeta empaquetada (el nombre exacto puede variar según la versión, por ejemplo `LinuxServer`):

```powershell
scp -r .\Build\LinuxServer\* root@IP:/opt/barrio/server/
scp .\infra\vps\barrio-server.service root@IP:/etc/systemd/system/
```

En el VPS:

```bash
chown -R barrio:barrio /opt/barrio
chmod +x /opt/barrio/server/BarrioServer.sh
systemctl daemon-reload
systemctl enable --now barrio-server
journalctl -u barrio-server -f     # ver el log; Ctrl+C para salir
```

En el log tiene que aparecer que el servidor escucha en el puerto 7777 y que cargó `L_Greybox`.

## 6. Conectarse

Desde un cliente empaquetado en **Development** (Windows):

```
Barrio.exe IP:7777
```

O desde el editor: **Play → Standalone Game**, abrir la consola con la tecla `º` (o `~`) y escribir `open IP:7777`.

## Problemas comunes

| Síntoma | Causa probable |
| --- | --- |
| El cliente se queda en el mapa local y no conecta | Puerto 7777 UDP cerrado en `ufw` o en el panel de Hostinger |
| "Version mismatch" o desconexión inmediata | Cliente y servidor empaquetados desde versiones distintas del código |
| El servidor se cierra al arrancar | Revisar `journalctl -u barrio-server`; suele ser el mapa faltante en el empaquetado |
| Mucho lag | Datacenter lejos; medir con `ping IP` desde la PC |

En el MVP 0 no hay login: cualquiera que tenga la IP puede entrar. Compartir la IP solo con los testers.
