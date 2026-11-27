# -*- coding: utf-8 -*-
"""probe_fab.py - Lista lo que barrio_fab encuentra (árboles y autos de Fab) en Saved/probe_fab.txt."""
import importlib, os, sys
import unreal
d = os.path.dirname(os.path.abspath(__file__))
if d not in sys.path:
    sys.path.insert(0, d)
import barrio_fab
importlib.reload(barrio_fab)
F = barrio_fab
F.reset()
out = []
for p in F._all_assets():
    if 'EuropeanHornbeam' in p or 'Vehicle' in p:
        out.append('ASSET ' + p)
for sm, h, z0, p in F.trees():
    bb = sm.get_bounding_box()
    out.append('TREE %s h=%.0f z0=%.0f xy=%.0f nanite=%s lods=%d' % (
        p, h, z0, max(bb.max.x - bb.min.x, bb.max.y - bb.min.y),
        sm.get_editor_property('nanite_settings').enabled, sm.get_num_lods()))
for o, L, p, sk in F.cars():
    out.append('CAR %s L=%.0f skel=%s' % (p, L, sk))
fn = os.path.join(unreal.Paths.project_saved_dir(), 'probe_fab.txt')
with open(fn, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out) + '\n')
unreal.log('[FAB] probe -> %s (%d lineas)' % (fn, len(out)))
