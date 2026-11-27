# Traza rayos verticales en puntos dados y anota contra qué choca cada uno (diagnóstico de colisión).
# Uso: py "<ruta>/probe_trace.py" x,y x,y ...
import os
import sys
import unreal

pts = [tuple(float(v) for v in a.split(',')) for a in sys.argv[1:]] or [(4500.0, 22880.0), (4900.0, 24000.0)]
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
out = []
for (x, y) in pts:
    z = 600.0
    hits = []
    for _ in range(6):
        r = unreal.SystemLibrary.line_trace_single(world, unreal.Vector(x, y, z), unreal.Vector(x, y, -900.0),
                                                   unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
                                                   unreal.DrawDebugTrace.NONE, True)
        if r is None:
            break
        hr = r.to_tuple() if hasattr(r, 'to_tuple') else None
        try:
            blocking = hr[0]
            loc = hr[4]
            actor = hr[9]
            comp = hr[10]
        except Exception as ex:  # noqa: BLE001
            hits.append('(%s)' % ex)
            break
        if not blocking:
            break
        name = actor.get_actor_label() if actor else '?'
        mesh = ''
        try:
            mesh = comp.get_editor_property('static_mesh').get_name()
        except Exception:  # noqa: BLE001
            pass
        hits.append('z=%.0f %s [%s]' % (loc.z, name, mesh))
        z = loc.z - 2.0
    out.append('(%.0f, %.0f): %s' % (x, y, ' | '.join(hits) if hits else 'sin choque'))
p = os.path.join(unreal.Paths.project_saved_dir(), 'probe_trace.txt')
with open(p, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
unreal.log('[PROBE] trazas en %s' % p)
