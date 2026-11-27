# Coloca la cámara del viewport en vistas fijas del mapa (para capturas de revisión).
# Uso:
#   py "<ruta>/cam.py" <nombre>            -> solo mueve la cámara
#   py "<ruta>/cam.py" <nombre> shot       -> mueve la cámara y saca HighResShot 1920x1080
#   py "<ruta>/cam.py" todas [n1 n2 ...]   -> recorre las vistas (o las nombradas) en modo juego (G),
#                                             esperando a que Lumen asiente, y saca una captura de cada una.
# Las capturas quedan en Saved/Screenshots/WindowsEditor; el orden se escribe en Saved/cam_shots.txt.
import os
import sys
import unreal

VIEWS = {
    # nombre: (x, y, z, pitch, yaw)
    "llegada":   (19600, 25350, 215, -3, -68),     # PlayerStart del andén, mirando a la plaza y la torre
    "calle":     (2600, 11258, 175, -2, 0),        # calle entre filas, mirando al este
    "plaza":     (12900, 12900, 180, -3, 45),      # esquina SO de la plaza, mirando al centro
    "comisaria": (16700, 12300, 200, -4, -90),     # desde la plaza hacia la comisaría
    "avenida":   (32476, 4000, 180, -2, 90),       # avenida, mirando al norte
    "e3":        (31200, 11258, 175, -2, 0),       # cruce de la avenida hacia la salida E3
    "pasonivel": (11258, 20200, 180, 0, 90),       # llegando al paso a nivel E1
    "e2":        (24840, 21400, 175, 2, 90),       # calle de las vías mirando a la pasarela E2
    "torre":     (21650, 13000, 175, 6, 55),       # esquina mirando a la torre NE
    "baldio":    (4200, 16454, 175, -2, 0),        # baldío de la manzana 0,1
    "estacion":  (17000, 27200, 180, -2, 0),       # explanada de la estación
    "aerea":     (-5000, -6000, 9000, -32, 40),    # vista aérea general
    "aerea2":    (38000, 30000, 7000, -30, -140),  # vista aérea desde el NE
    # v5: fila sur, calle comercial y paso bajo nivel
    "comercial": (1300, 700, 175, -1, 0),          # calle comercial (arcos), mirando al este
    "comercial2": (16500, 560, 175, 4, 160),       # calle comercial a mitad de cuadra, mirando al oeste
    "fondo":     (1300, -9526, 175, -2, 0),        # calle Fondo contra los galpones
    "sur_ns":    (11258, -9000, 175, -2, 90),      # C01 en la fila sur, mirando al norte
    "tunel_boca": (3650, 22330, 175, -12, 40),     # boca sur del paso bajo nivel desde la vereda
    "tunel":     (4890, 23250, -160, 0, 90),       # adentro del túnel, mirando al norte
    "aerea_sur": (16000, -24000, 7500, -30, 90),   # aérea desde el sur (fila nueva)
}
ORDEN = ["comercial", "comercial2", "fondo", "sur_ns", "tunel_boca", "tunel", "aerea_sur", "plaza", "calle",
         "llegada", "aerea"]
TICKS_ASENTAR = 150     # cuadros antes de capturar (Lumen + streaming)
TICKS_CAPTURA = 40      # cuadros para que termine la captura


def poner(n):
    x, y, z, pitch, yaw = VIEWS[n]
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    ues.set_level_viewport_camera_info(unreal.Vector(x, y, z), unreal.Rotator(roll=0, pitch=pitch, yaw=yaw))
    unreal.log(f"[CAM] vista {n}")


def modo_juego(on):
    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_set_game_view(on)
    except Exception as e:  # noqa: BLE001
        unreal.log_warning(f"[CAM] no pude cambiar el modo juego: {e}")


def disparo():
    unreal.SystemLibrary.execute_console_command(None, "HighResShot 1920x1080")


args = sys.argv[1:] or ["calle"]
if args[0] == "todas":
    lista = [n for n in (args[1:] or ORDEN) if n in VIEWS]
    traza = os.path.join(unreal.Paths.project_saved_dir(), "cam_shots.txt")
    with open(traza, "w", encoding="utf-8") as f:
        f.write("")
    estado = {"i": 0, "t": 0, "fase": "poner"}
    modo_juego(True)

    def tick(_dt):
        if estado["i"] >= len(lista):
            unreal.unregister_slate_post_tick_callback(estado["h"])
            modo_juego(False)
            unreal.log(f"[CAM] CAPTURAS LISTAS ({len(lista)})")
            return
        n = lista[estado["i"]]
        if estado["fase"] == "poner":
            poner(n)
            estado.update(fase="asentar", t=0)
        elif estado["fase"] == "asentar":
            estado["t"] += 1
            if estado["t"] >= TICKS_ASENTAR:
                disparo()
                with open(traza, "a", encoding="utf-8") as f:
                    f.write(n + "\n")
                estado.update(fase="capturar", t=0)
        else:
            estado["t"] += 1
            if estado["t"] >= TICKS_CAPTURA:
                estado.update(fase="poner", i=estado["i"] + 1)

    estado["h"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log(f"[CAM] recorriendo {len(lista)} vistas: {' '.join(lista)}")
else:
    poner(args[0])
    if len(args) > 1 and args[1] == "shot":
        disparo()
