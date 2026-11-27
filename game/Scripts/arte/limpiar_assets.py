# -*- coding: utf-8 -*-
"""limpiar_assets.py [borrar] - Busca assets de /Game que el juego no usa y, con 'borrar', los elimina.

Sin argumentos solo escribe el informe en Saved/limpieza.txt (no toca nada).

Qué se considera EN USO (raíces + todas sus dependencias, duras y blandas):
  - el mapa L_Greybox y los paquetes de sus actores externos (__ExternalActors__/__ExternalObjects__),
  - todo asset /Game/... nombrado en Config/*.ini (mapas por defecto, GameMode, etc.),
  - todo lo de /Game/Barrio que NO es una malla estática (materiales, texturas, Blueprints: los scripts
    los buscan por nombre aunque hoy nadie los referencie),
  - las mallas de Fab que usa barrio_fab (calle y plaza).
Qué se puede borrar:
  - /Game/EuropeanHornbeam y /Game/MSPresets: lo que no está en uso (variantes, impostores, plantines,
    PivotPainter, mapa de muestra...),
  - /Game/Barrio: mallas estáticas generadas que ya nada referencia (restos de builds viejos).
Las plantillas de Epic (Characters, Input, LevelPrototyping, ThirdPerson) solo se informan.
"""
import os
import re
import sys
import unreal

BORRAR = len(sys.argv) > 1 and sys.argv[1] == 'borrar'
AR = unreal.AssetRegistryHelpers.get_asset_registry()
EAL = unreal.EditorAssetLibrary
CONTENT = os.path.abspath(unreal.Paths.project_content_dir())
PROJ = os.path.abspath(unreal.Paths.project_dir())
OPTS = unreal.AssetRegistryDependencyOptions(include_soft_package_references=True,
                                             include_hard_package_references=True,
                                             include_searchable_names=False,
                                             include_soft_management_references=True,
                                             include_hard_management_references=True)
MAPA = '/Game/Barrio/Maps/L_Greybox'
FAB_DIRS = ('/Game/EuropeanHornbeam', '/Game/MSPresets')
PLANTILLAS = ('/Game/Characters', '/Game/Input', '/Game/LevelPrototyping', '/Game/ThirdPerson')


def pkg_files(pkg):
    rel = pkg[len('/Game/'):]
    base = os.path.join(CONTENT, *rel.split('/'))
    out = []
    for ext in ('.uasset', '.umap', '.uexp', '.ubulk', '.uptnl'):
        if os.path.exists(base + ext):
            out.append(base + ext)
    return out


def pkg_size(pkg):
    return sum(os.path.getsize(f) for f in pkg_files(pkg))


all_assets = [str(a) for a in EAL.list_assets('/Game', recursive=True, include_folder=False)]
pkgs = sorted(set(p.split('.')[0] for p in all_assets))
unreal.log('[LIMPIEZA] paquetes en /Game: %d' % len(pkgs))

# ---- raíces
roots = {MAPA}
for p in pkgs:
    if p.startswith('/Game/__ExternalActors__') or p.startswith('/Game/__ExternalObjects__'):
        roots.add(p)
ini_dir = os.path.join(PROJ, 'Config')
for fn in os.listdir(ini_dir):
    if fn.endswith('.ini'):
        txt = open(os.path.join(ini_dir, fn), encoding='utf-8', errors='ignore').read()
        for m in re.findall(r'/Game/[A-Za-z0-9_/]+', txt):
            roots.add(m.split('.')[0])
for p in pkgs:
    if p.startswith('/Game/Barrio/'):
        a = EAL.find_asset_data(p)
        cls = str(a.asset_class_path.asset_name) if a else ''
        if cls != 'StaticMesh':
            roots.add(p)
try:
    d = os.path.dirname(os.path.abspath(__file__))
    if d not in sys.path:
        sys.path.insert(0, d)
    import importlib
    import barrio_fab
    importlib.reload(barrio_fab)
    for lst in barrio_fab.trees().values():
        for t in lst:
            roots.add(t[4].split('.')[0])
    for t in barrio_fab.cars():
        roots.add(t[2].split('.')[0])
except Exception as e:  # noqa: BLE001
    unreal.log_warning('[LIMPIEZA] barrio_fab: %s' % e)

# ---- cierre de dependencias
used = set()
stack = [r for r in roots]
while stack:
    p = stack.pop()
    if p in used:
        continue
    used.add(p)
    try:
        deps = AR.get_dependencies(unreal.Name(p), OPTS) or []
    except Exception:  # noqa: BLE001
        deps = []
    for dd in deps:
        s = str(dd)
        if s.startswith('/Game/') and s not in used:
            stack.append(s)

# ---- candidatos
borrar = []
for p in pkgs:
    if p in used:
        continue
    if p.startswith(FAB_DIRS):
        borrar.append(p)
    elif p.startswith('/Game/Barrio/'):
        borrar.append(p)          # solo llegan acá las StaticMesh (lo demás es raíz)
info = []
for p in pkgs:
    if p not in used and p.startswith(PLANTILLAS):
        info.append(p)

def total(lst):
    return sum(pkg_size(p) for p in lst)

lines = ['MODO: %s' % ('BORRAR' if BORRAR else 'informe (no se borra nada)'),
         'paquetes en /Game: %d | en uso: %d' % (len(pkgs), len([p for p in pkgs if p in used])),
         'A BORRAR: %d paquetes, %.1f MB' % (len(borrar), total(borrar) / 1e6)]
for pre in FAB_DIRS + ('/Game/Barrio',):
    sub = [p for p in borrar if p.startswith(pre)]
    keep = [p for p in pkgs if p.startswith(pre) and p in used]
    lines.append('  %s: borrar %d (%.1f MB) | se queda %d (%.1f MB)' % (
        pre, len(sub), total(sub) / 1e6, len(keep), total(keep) / 1e6))
lines.append('PLANTILLAS sin uso (no se tocan): %d paquetes, %.1f MB' % (len(info), total(info) / 1e6))
lines.append('')
lines += ['BORRAR %s %.1f' % (p, pkg_size(p) / 1e6) for p in borrar]
lines += ['PLANTILLA_SIN_USO %s %.1f' % (p, pkg_size(p) / 1e6) for p in info]
lines += ['USO %s' % p for p in sorted(used) if p.startswith(FAB_DIRS)]

if BORRAR:
    ok = 0
    fallos = []
    for p in borrar:
        try:
            if EAL.does_asset_exist(p) and EAL.delete_asset(p):
                ok += 1
            else:
                fallos.append(p)
        except Exception as e:  # noqa: BLE001
            fallos.append('%s (%s)' % (p, e))
    lines.insert(1, 'borrados %d de %d; fallaron %d' % (ok, len(borrar), len(fallos)))
    lines += ['FALLO %s' % f for f in fallos]

fn = os.path.join(unreal.Paths.project_saved_dir(), 'limpieza.txt')
with open(fn, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
unreal.log('[LIMPIEZA] %s -> %s' % (lines[2] if not BORRAR else lines[1], fn))
