# Diagnóstico de navegación: volúmenes, su tamaño real y si existe el RecastNavMesh.
import unreal

out = []
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for a in eas.get_all_level_actors():
    cls = a.get_class().get_name()
    if cls in ("NavMeshBoundsVolume", "RecastNavMesh", "NavigationData"):
        origin, extent = a.get_actor_bounds(False)
        out.append("%s %s loc=%s scale=%s bounds_extent=%s" % (
            cls, a.get_actor_label(), a.get_actor_location(), a.get_actor_scale3d(), extent))
path = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()) + "nav_check.txt"
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(out) if out else "nada")
unreal.log("[NAV] " + " | ".join(out))
