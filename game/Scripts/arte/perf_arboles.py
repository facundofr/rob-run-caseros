# -*- coding: utf-8 -*-
"""perf_arboles.py <modo> - Prueba de costo de los árboles de Fab en el mapa abierto.
modos: nowpo (sin viento), wpo2k (viento solo a < 20 m), wpo (viento siempre), nosombra, sombra, nort, rt"""
import sys
import unreal
modo = sys.argv[1] if len(sys.argv) > 1 else 'nowpo'
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
n = 0
for a in eas.get_all_level_actors():
    if not isinstance(a, unreal.StaticMeshActor):
        continue
    comp = a.static_mesh_component
    sm = comp.static_mesh
    if sm is None or 'Hornbeam' not in sm.get_path_name():
        continue
    if modo == 'nowpo':
        comp.set_editor_property('evaluate_world_position_offset', False)
    elif modo == 'wpo':
        comp.set_editor_property('evaluate_world_position_offset', True)
        comp.set_editor_property('world_position_offset_disable_distance', 0)
    elif modo == 'wpo2k':
        comp.set_editor_property('evaluate_world_position_offset', True)
        comp.set_editor_property('world_position_offset_disable_distance', 2000)
    elif modo == 'nosombra':
        comp.set_cast_shadow(False)
    elif modo == 'sombra':
        comp.set_cast_shadow(True)
    elif modo == 'nort':
        comp.set_editor_property('visible_in_ray_tracing', False)
    elif modo == 'rt':
        comp.set_editor_property('visible_in_ray_tracing', True)
    n += 1
unreal.log('[PERF] %s aplicado a %d árboles de Fab' % (modo, n))
