# -*- coding: utf-8 -*-
"""barrio_fab.py - Assets de Fab (licencia estándar de Fab; NO se publican en el repo: ver .gitignore).

Si están en el proyecto, build_barrio los usa en lugar de los generados; si no están, todo sigue con lo
generado por script (no rompe nada).

- Árboles: Quixel Megascans "European Hornbeam" (carpe). Se usan los árboles de campo/bosque (no los
  plantines) para los árboles CON HOJA de vereda y de la plaza, escalados a la altura del barrio
  (vereda 9-12 m, plaza 13-16 m). Los plátanos podados de invierno siguen siendo los generados (son los de
  las fotos de julio y no hay uno así en Fab).
- Autos: Switchboard Studios "Vehicle Variety Pack" (sedán deportivo, hatchback, pickup, SUV, camión de caja).

Todo se descubre por nombre en el Content Browser (las rutas exactas cambian entre versiones del paquete).
"""
import unreal

EAL = unreal.EditorAssetLibrary
_CACHE = {}

TREE_KEYS = ('Hornbeam',)
TREE_SKIP = ('Sapling', 'Seedling', 'Billboard', 'Impostor', 'Branch', 'Twig', 'Leaf', 'Leaves', 'Trunk', 'Bark',
             'Debris', 'Root', 'Stump', 'Log')
CAR_KEYS = ('VehicleVarietyPack', 'Vehicle_Variety', 'VehicleVariety')
CAR_SKIP = ('Wheel', 'Tire', 'Tyre', 'Door', 'Interior', 'Glass', 'Window', 'Steering', 'Seat', 'Light', 'Brake',
            'Physics', 'Phys', 'Box_', 'Collision', 'Hood', 'Trunk', 'Mirror', 'Wiper', 'Caliper', 'Disc')


def _all_assets():
    if 'all' not in _CACHE:
        try:
            _CACHE['all'] = list(EAL.list_assets('/Game', recursive=True, include_folder=False))
        except Exception as e:  # noqa: BLE001
            unreal.log_warning('[FAB] no pude listar /Game: %s' % e)
            _CACHE['all'] = []
    return _CACHE['all']


def _height(obj):
    try:
        bb = obj.get_bounding_box()
        return float(bb.max.z - bb.min.z), float(bb.min.z)
    except Exception:  # noqa: BLE001
        try:
            b = obj.get_bounds()
            return float(b.box_extent.z * 2.0), float(b.origin.z - b.box_extent.z)
        except Exception:  # noqa: BLE001
            return 0.0, 0.0


def trees():
    """{'calle': [...], 'plaza': [...]} con (StaticMesh, alto_cm, z_min, ancho_cm, ruta) del carpe (vacío si no
    está). Se usan las versiones SimpleWind (más baratas que PivotPainter). Calle: copas angostas (Forest);
    plaza: copas anchas (Field y los Forest grandes)."""
    if 'trees' in _CACHE:
        return _CACHE['trees']
    out = {'calle': [], 'plaza': []}
    for p in _all_assets():
        name = p.split('/')[-1].split('.')[0]
        if not any(k_ in p for k_ in TREE_KEYS) or '/SimpleWind/' not in p or any(s in name for s in TREE_SKIP):
            continue
        if '/Geometry/' not in p:
            continue
        obj = EAL.load_asset(p)
        if not isinstance(obj, unreal.StaticMesh):
            continue
        h, z0 = _height(obj)
        if h < 1000.0:              # arbustos, plantines y el Forest_09 (6 m)
            continue
        try:
            bb = obj.get_bounding_box()
            w = float(max(bb.max.x - bb.min.x, bb.max.y - bb.min.y))
        except Exception:  # noqa: BLE001
            w = h * 0.6
        t = (obj, h, z0, w, p)
        if 'Field' in name or w > 1200.0:
            out['plaza'].append(t)
        else:
            out['calle'].append(t)
        if 'Forest' in name and w <= 1200.0 and h >= 1450.0:
            out['plaza'].append(t)
    for v in out.values():
        v.sort(key=lambda t: t[4])
    _CACHE['trees'] = out
    unreal.log('[FAB] árboles de Fab: calle %d (%s) / plaza %d (%s)' % (
        len(out['calle']), ', '.join(t[4].split('.')[-1] for t in out['calle']),
        len(out['plaza']), ', '.join(t[4].split('.')[-1] for t in out['plaza'])))
    return out


def cars():
    """[(malla, largo_cm, ruta, es_esqueletica)] de vehículos del paquete (vacío si no está)."""
    if 'cars' in _CACHE:
        return _CACHE['cars']
    out = []
    for p in _all_assets():
        name = p.split('/')[-1].split('.')[0]
        if not any(k_ in p for k_ in CAR_KEYS) or any(s.lower() in name.lower() for s in CAR_SKIP):
            continue
        obj = EAL.load_asset(p)
        sk = isinstance(obj, unreal.SkeletalMesh)
        if not (sk or isinstance(obj, unreal.StaticMesh)):
            continue
        try:
            bb = obj.get_bounding_box()
            L = max(bb.max.x - bb.min.x, bb.max.y - bb.min.y)
        except Exception:  # noqa: BLE001
            L = 0.0
        if L < 300.0:
            continue
        out.append((obj, float(L), p, sk))
    out.sort(key=lambda t: t[2])
    _CACHE['cars'] = out
    unreal.log('[FAB] vehículos de Fab: %d (%s)' % (len(out), ', '.join(t[2].split('/')[-1].split('.')[0]
                                                                     for t in out)))
    return out


def reset():
    _CACHE.clear()
