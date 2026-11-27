# Arma el contenido mínimo para jugar Barrio en el editor (docs/GUIA_DESARROLLO.md, sección 3):
# BP_BarrioCharacter, BP_BarrioGameMode y el mapa L_Greybox con todos sus actores.
# Uso, en el editor: consola Cmd -> py "<ruta>/game/Scripts/setup_greybox.py"
# Es idempotente: si un asset ya existe, lo reutiliza; si el mapa ya existe, no lo vuelve a crear.

import unreal

TAG = "[SETUP]"


def log(msg):
    unreal.log(f"{TAG} {msg}")


def err(msg):
    unreal.log_error(f"{TAG} {msg}")


eal = unreal.EditorAssetLibrary
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

CHAR_DIR = "/Game/Barrio/Characters"
CHAR_BP = f"{CHAR_DIR}/BP_BarrioCharacter"
GM_DIR = "/Game/Barrio"
GM_BP = f"{GM_DIR}/BP_BarrioGameMode"
MAP_PATH = "/Game/Barrio/Maps/L_Greybox"

MESH_PATH = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
ANIM_BP_PATH = "/Game/Characters/Mannequins/Anims/Unarmed/ABP_Unarmed"


def get_or_create_bp(path, parent_class):
    if eal.does_asset_exist(path):
        log(f"Ya existe {path}, se reutiliza")
        return eal.load_asset(path)
    folder, name = path.rsplit("/", 1)
    eal.make_directory(folder)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent_class)
    bp = asset_tools.create_asset(name, folder, unreal.Blueprint, factory)
    if bp is None:
        raise RuntimeError(f"No se pudo crear {path}")
    log(f"Creado {path}")
    return bp


# 1) Personaje
char_bp = get_or_create_bp(CHAR_BP, unreal.BarrioCharacter)
char_class = char_bp.generated_class()
char_cdo = unreal.get_default_object(char_class)
mesh_comp = char_cdo.get_editor_property("mesh")
skm = eal.load_asset(MESH_PATH)
abp = eal.load_asset(ANIM_BP_PATH)
if skm is None or abp is None:
    err("No se encontró el maniquí o su Animation Blueprint del paquete Third Person")
else:
    mesh_comp.set_editor_property("skeletal_mesh_asset", skm)
    mesh_comp.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_BLUEPRINT)
    mesh_comp.set_editor_property("anim_class", abp.generated_class())
    log("Mesh y Anim Class asignados")
unreal.BlueprintEditorLibrary.compile_blueprint(char_bp)
eal.save_asset(CHAR_BP, only_if_is_dirty=False)

# 2) GameMode
gm_bp = get_or_create_bp(GM_BP, unreal.BarrioGameMode)
gm_class = gm_bp.generated_class()
gm_cdo = unreal.get_default_object(gm_class)
gm_cdo.set_editor_property("default_pawn_class", char_class)
unreal.BlueprintEditorLibrary.compile_blueprint(gm_bp)
eal.save_asset(GM_BP, only_if_is_dirty=False)
log("GameMode con Default Pawn = BP_BarrioCharacter")

# Project Settings -> Maps & Modes -> Default GameMode (en memoria; el .ini se actualiza aparte)
try:
    maps_settings = unreal.get_default_object(unreal.GameMapsSettings)
    maps_settings.set_editor_property(
        "global_default_game_mode", unreal.SoftClassPath(f"{GM_BP}.BP_BarrioGameMode_C")
    )
    log("Default GameMode del proyecto actualizado en memoria")
except Exception as e:  # noqa: BLE001
    err(f"No se pudo cambiar el Default GameMode en memoria: {e}")

# 3) Mapa
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

if eal.does_asset_exist(MAP_PATH):
    log(f"El mapa {MAP_PATH} ya existe: no se toca")
else:
    eal.make_directory("/Game/Barrio/Maps")
    ok = les.new_level_from_template(MAP_PATH, "/Engine/Maps/Templates/Template_Default")
    if not ok:
        raise RuntimeError("No se pudo crear L_Greybox desde la plantilla Basic")
    log("Mapa creado desde la plantilla Basic")

    # Borrar el piso de la plantilla
    for a in eas.get_all_level_actors():
        if a.get_actor_label().startswith("Floor"):
            eas.destroy_actor(a)
            log("Floor borrado")

    def spawn(cls, loc, label, extent=None, tag=None):
        actor = eas.spawn_actor_from_class(cls, unreal.Vector(*loc), unreal.Rotator(0, 0, 0))
        if actor is None:
            err(f"No se pudo crear {label}")
            return None
        actor.set_actor_label(label)
        if extent is not None:
            box = actor.get_component_by_class(unreal.BoxComponent)
            box.set_box_extent(unreal.Vector(*extent))
        if tag is not None:
            actor.set_editor_property("player_start_tag", tag)
        log(f"{label} en {loc}")
        return actor

    spawn(unreal.GreyboxNeighborhood, (0, 0, 0), "GreyboxNeighborhood")
    spawn(unreal.PlayerStart, (500, 500, 100), "PlayerStart_Vecinos_1")
    spawn(unreal.PlayerStart, (500, 11500, 100), "PlayerStart_Vecinos_2")
    spawn(unreal.BarrioSafeZone, (500, 500, 100), "SafeZone_Aparicion", extent=(600, 600, 300))
    spawn(unreal.PlayerStart, (11500, 500, 100), "PlayerStart_Police", tag="Police")
    spawn(unreal.PoliceStation, (11500, 800, 55), "PoliceStation")
    spawn(unreal.BarrioSafeZone, (11500, 600, 100), "SafeZone_Comisaria", extent=(500, 500, 300))
    spawn(unreal.ExitZone, (-500, 11500, 100), "ExitZone_Oeste", extent=(500, 600, 300))
    spawn(unreal.ExitZone, (23500, 11500, 100), "ExitZone_Este", extent=(500, 600, 300))
    spawn(unreal.FenceStation, (-2500, 11500, 55), "FenceStation")
    spawn(unreal.JailCell, (-5000, -5000, 200), "JailCell")

    # El mapa usa el GameMode del proyecto, pero lo fijamos también acá para que PIE no dependa del .ini
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    world.get_world_settings().set_editor_property("default_game_mode", gm_class)

    les.save_current_level()
    log("Mapa guardado")

log("LISTO")
