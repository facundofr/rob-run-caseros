# Diagnóstico de colisión simple de mallas generadas. Uso: py "<ruta>/probe_coll.py" PasoBajoNivel Suelo
import os
import sys
import unreal

out = []
names = sys.argv[1:] or ['PasoBajoNivel', 'Suelo']
assets = unreal.EditorAssetLibrary.list_assets('/Game/Barrio/Art/Mapa', recursive=True, include_folder=False)
for n in names:
    hits = [a for a in assets if a.split('/')[-1].split('.')[0] in (n, 'SM_' + n, 'SM_M_' + n)]
    out.append('%s -> %s' % (n, hits))
    for h in hits:
        sm = unreal.EditorAssetLibrary.load_asset(h)
        if not isinstance(sm, unreal.StaticMesh):
            continue
        bs = sm.get_editor_property('body_setup')
        if bs is None:
            out.append('  sin body_setup')
            continue
        out.append('  collision_trace_flag=%s' % bs.get_editor_property('collision_trace_flag'))
        agg = bs.get_editor_property('agg_geom')
        for f in ('box_elems', 'convex_elems', 'sphere_elems', 'sphyl_elems'):
            try:
                els = agg.get_editor_property(f)
                out.append('  %s: %d' % (f, len(els)))
                for e in list(els)[:40]:
                    try:
                        if f == 'box_elems':
                            c = e.get_editor_property('center')
                            out.append('    box c=(%.0f,%.0f,%.0f) x=%.0f y=%.0f z=%.0f' % (
                                c.x, c.y, c.z, e.get_editor_property('x'), e.get_editor_property('y'),
                                e.get_editor_property('z')))
                        else:
                            bb = e.get_editor_property('elem_box')
                            out.append('    convex min=(%.0f,%.0f,%.0f) max=(%.0f,%.0f,%.0f)' % (
                                bb.min.x, bb.min.y, bb.min.z, bb.max.x, bb.max.y, bb.max.z))
                    except Exception as ex:  # noqa: BLE001
                        out.append('    (%s)' % ex)
            except Exception as ex:  # noqa: BLE001
                out.append('  %s: no accesible (%s)' % (f, ex))
p = os.path.join(unreal.Paths.project_saved_dir(), 'probe_coll.txt')
with open(p, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out))
unreal.log('[PROBE] colisión escrita en %s' % p)
