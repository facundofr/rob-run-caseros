# -*- coding: utf-8 -*-
"""
build_barrio.py  -  Genera el primer mapa jugable de Barrio (MAPA.md) sobre /Game/Barrio/Maps/L_Greybox.

Correr en el editor (UE 5.8.4):   py "<ruta>/build_barrio.py"

Qué hace:
  1. Recarga los módulos auxiliares (barrio_kit, barrio_layout, barrio_props, barrio_geo, barrio_edificios).
  2. Chequea la API de Geometry Script y calibra (lo del kit).
  3. Borra lo generado antes (carpetas FacadeTest y Barrio/*, actor GreyboxNeighborhood). NO toca la carpeta
     Ambiente, el PostProcessVolume ni los actores de juego (se reubican).
  4. Construye con build_plan(SEED): calles, manzanas (variantes instanciadas, una malla por variante),
     comisaría, torre, plaza, baldío, pasillos, fondos, vías, Afuera, bordes, props, autos, cables,
     luminarias (TargetPoint LUM_<n>, tag LUMINARIA, mirando abajo) y juego (llegada, zonas seguras,
     salidas, comisaría, reducidor, celda, ~60 LootPoint, NavMeshBoundsVolume).
  5. Guarda mallas y nivel, imprime el resumen y "[BARRIO] MAPA LISTO".

Memoria: las DynamicMesh salen SIEMPRE del DynamicMeshPool del kit; al final se sueltan todas
(barrio_kit.shutdown -> free_all_meshes), se vacían los caches y se fuerza gc + collect_garbage.
No queda estado de Unreal en el namespace del módulo: todo vive en main() / Ctx.
Trace con flush en <Proyecto>/Saved/barrio_trace.txt (si el editor se cae, la última línea dice dónde).
"""

SEED = 5258
# None = todo. Para iterar rápido, una lista con algunas de:
#   'calles', 'manzana_0_0', 'manzana_0_1', 'manzana_1_0', 'manzana_1_1', 'manzana_2_0', 'manzana_2_1',
#   'vias', 'afuera', 'props', 'gameplay'
SOLO = ["manzana_0_0"]

import os
import sys
import gc
import time
import math
import random
import traceback
import importlib

PARTS = ['calles', 'manzana_0_0', 'manzana_0_1', 'manzana_1_0', 'manzana_1_1', 'manzana_2_0', 'manzana_2_1',
         'vias', 'afuera', 'props', 'gameplay']
MODULES = ['barrio_kit', 'barrio_layout', 'barrio_props', 'barrio_geo', 'barrio_edificios']
GP = 'Barrio/Gameplay'
PART_FOLDERS = {
    'calles': ['Barrio/Calles'],
    'manzana_0_0': ['Barrio/Manzanas/M00'], 'manzana_0_1': ['Barrio/Manzanas/M01'],
    'manzana_1_0': ['Barrio/Manzanas/M10'], 'manzana_1_1': ['Barrio/Manzanas/M11'],
    'manzana_2_0': ['Barrio/Manzanas/M20'], 'manzana_2_1': ['Barrio/Manzanas/M21'],
    'vias': ['Barrio/Vias'],
    'afuera': ['Barrio/Afuera'],
    'props': ['Barrio/Props', 'Barrio/Autos', 'Barrio/Cables', 'Barrio/Luminarias'],
    'gameplay': [GP],
}
# Actores de juego y de ambiente que se reubican o se respetan: nunca se borran.
PRESERVE = ['PlayerStart', 'BarrioSafeZone', 'ExitZone', 'PoliceStation', 'FenceStation', 'JailCell',
            'NavMeshBoundsVolume', 'PostProcessVolume']
FALLBACK_DIRS = ['C:/Users/facufr/Desktop/rob-run-caseros/rob-run-caseros/game/Scripts/arte',
                 '/home/claude/barrio_art/scripts']


# =====================================================================================
# ARRANQUE
# =====================================================================================
def _script_dir():
    cands = []
    try:
        cands.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    cands += FALLBACK_DIRS
    for c in cands:
        if c and os.path.exists(os.path.join(c, 'barrio_kit.py')):
            return c
    return cands[0] if cands else os.getcwd()


def _load_modules():
    out = {}
    for name in MODULES:
        if name in sys.modules:
            out[name] = importlib.reload(sys.modules[name])
        else:
            out[name] = importlib.import_module(name)
    return out


class Ctx(object):
    """Estado de UNA corrida (se vacía al final)."""
    pass


def _stable_hash(s):
    h = 2166136261
    for ch in str(s):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def _seed(name):
    return (SEED * 7919 + _stable_hash(name)) % 1000003


# =====================================================================================
# MALLAS E INSTANCIAS
# =====================================================================================
def mesh(c, asset, builder, *args, **kw):
    """Construye un MB con builder(*args) y lo convierte en StaticMesh(es) SM_M_<asset>."""
    nanite = kw.pop('nanite', True)
    collision = kw.pop('collision', True)
    k = c.k
    k.trace('MESH ' + asset)
    mb = k.piece('Malla %s' % asset, builder, *args)
    if mb is None:
        return []
    return k.finalize(mb, asset, nanite=nanite, collision=collision) or []


def mesh_merged(c, asset, items, **kw):
    """Varias piezas (builder, args, origen, yaw) combinadas en UNA malla (actor en el origen): menos assets,
    menos builds de Nanite y de colisión. Solo para piezas con colisión de cajas (yaw múltiplo de 90)."""
    k = c.k

    def build():
        dst = k.MB(asset)
        for (builder, args, loc, yaw) in items:
            mb = k.piece('%s: %s' % (asset, getattr(builder, '__name__', '?')), builder, *args)
            if mb is not None:
                k.merge_mb(dst, mb, loc, yaw)
        return dst
    return mesh(c, asset, build, **kw)


def put(c, sms, label, loc, yaw=0.0, folder='Barrio', collision=True, swaps=None, scale=None, rot=None, shadow=True):
    if not sms:
        return []
    k = c.k
    r = rot if rot is not None else k.R(yaw=yaw)
    return k.spawn(sms, label, (float(loc[0]), float(loc[1]), float(loc[2]) if len(loc) > 2 else 0.0), r, collision,
                   folder, scale, swaps, shadow)


def cached(c, key, builder, *args, **kw):
    """Malla compartida (props, árboles, postes): se construye la primera vez que se pide."""
    if key not in c.cache:
        c.cache[key] = mesh(c, key, builder, *args, **kw)
    return c.cache[key]


def variant(c, key):
    """Una malla por variante de casa (A, A_m, ..., EL, EC); las instancias cambian colores con swaps."""
    if key in c.variants:
        return c.variants[key]
    k, L, E = c.k, c.L, c.E
    base = key[:-2] if key.endswith('_m') else key
    builders = {
        'A': lambda: k.build_casa_a(L.LOT, 860.0),
        'A2': lambda: k.build_casa_a(L.LOT, 860.0, True),
        'B': lambda: k.build_casa_b(L.LOT, 900.0),
        'C': lambda: k.build_casa_c(L.LOT, 860.0),
        'D': lambda: k.build_casa_d(L.LOT, 900.0),
        'E': lambda: k.build_local_e(L.LOT, 860.0),
        'PH': lambda: E.build_ph(L.LOT, 860.0),
        'EL': lambda: E.build_esquina('EL'),
        'EC': lambda: E.build_esquina('EC'),
    }
    sms = []
    if base in builders:
        k.RNG.seed(_seed('variante_' + key))
        mb = None
        if key.endswith('_m'):
            k.mirror_begin(L.LOT)
        try:
            mb = k.piece('Variante %s' % key, builders[base])
        finally:
            k.mirror_end()
        if mb is not None:
            sms = k.finalize(mb, 'Casa_' + key) or []
    else:
        k.err('Variante desconocida: %s' % key)
    c.variants[key] = sms
    c.count['variantes'] = c.count.get('variantes', 0) + 1
    return sms


def tree(c, kind, seed, pelado=False, big=False):
    key = 'Arbol_%s_%d%s%s' % (kind, seed, '_P' if pelado else '', '_G' if big else '')
    return cached(c, key, c.P.build_arbol2, kind, seed, pelado, big)


def spawn_trees(c, lst, folder, prefix):
    for i, t in enumerate(lst):
        sms = tree(c, t['kind'], t.get('seed', 0), t.get('pelado', False), t.get('big', False))
        put(c, sms, '%s_%d' % (prefix, i), t['pos'], t.get('yaw', 0.0), folder)
        c.count['arboles'] = c.count.get('arboles', 0) + 1


def place_lot(c, lot, folder):
    """Instancia la variante del lote con sus colores y, si la puerta no es robable, la reja con candado."""
    k, L = c.k, c.L
    v = lot.get('variant')
    if not v:
        return
    f = lot['frame']
    sms = variant(c, v)
    loc = L.fw(f, 0.0, lot['y0'], 0.0)
    put(c, sms, 'Lote_%s_%s' % (lot['id'], v), loc, f['yaw'], folder, swaps=lot.get('swaps') or None)
    c.count['lotes'] = c.count.get('lotes', 0) + 1
    e = lot.get('entry')
    if e is None or lot.get('robbable'):
        return
    kind, y0, y1, z0, zt, ex = e
    reja = cached(c, 'RejaPuerta', c.P.build_reja_puerta)
    if kind == 'door':
        w, h = y1 - y0, zt - z0
        p = L.fw(f, ex + 0.5, lot['y0'] + 0.5 * (y0 + y1), z0)
        put(c, reja, 'Reja_%s' % lot['id'], p, f['yaw'], folder, scale=(1.0, w / 100.0 + 0.08, h / 220.0 + 0.03))
    elif kind == 'chamfer':
        cc = L.OCHAVA
        lx, ly = -cc + 200.0 * 0.70711 + 0.35, 200.0 * 0.70711 - 0.35
        p = L.fw(f, lx, lot['y0'] + ly, z0)
        put(c, reja, 'Reja_%s' % lot['id'], p, f['yaw'] - 45.0, folder, scale=(1.0, 1.08, (zt - z0) / 220.0 + 0.03))
    else:
        return
    c.count['rejas'] = c.count.get('rejas', 0) + 1


def build_row(c, name, f, n, seed, choices, folder, no_garage=None):
    """Fila de lotes de Afuera con las mismas variantes del barrio (sin robos: puertas con reja)."""
    L = c.L
    rng = random.Random(seed)
    lots = []
    prev = None
    for i in range(n):
        opts = ['E', 'B'] if (no_garage and no_garage(i)) else choices
        v = rng.choice(opts)
        for _ in range(6):
            if v != prev:
                break
            v = rng.choice(opts)
        prev = v
        mir = rng.random() < 0.5
        key = v + ('_m' if mir else '')
        base, meta, _mir = L.variant_meta(key)
        swaps = {}
        col = rng.choice(meta['colors'])
        if col != meta['wall']:
            swaps[meta['wall']] = col
        if 'cartel' in meta:
            c2 = rng.choice(L.CARTELES)
            if c2 != meta['cartel']:
                swaps[meta['cartel']] = c2
        e = meta['entry']
        if mir:
            a, b = L.mirror_range((e[1], e[2]))
            e = (e[0], a, b, e[3], e[4], e[5])
        g = meta.get('garage')
        p = meta['power']
        lot = {'id': '%s_%d' % (name, i), 'frame': f, 'y0': i * L.LOT, 'variant': key, 'swaps': swaps, 'entry': e,
               'robbable': False, 'garage': L.mirror_range(g) if (g and mir) else g,
               'power': (p[0], L.LOT - p[1], p[2]) if mir else p,
               'tel': [(t[0], L.LOT - t[1], t[2]) if mir else t for t in meta.get('tel', [])], 'mid': None,
               'side': name}
        place_lot(c, lot, folder)
        lots.append(lot)
    return lots


# =====================================================================================
# LIMPIEZA
# =====================================================================================
def cleanup(c, parts, full):
    import unreal
    k = c.k
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    folders = []
    for p in parts:
        folders += PART_FOLDERS.get(p, [])
    pres = tuple(x for x in (getattr(unreal, n, None) for n in PRESERVE) if isinstance(x, type))
    loot_cls = getattr(unreal, 'LootPoint', None)
    kill = []
    nloot = 0
    for a in eas.get_all_level_actors():
        try:
            if pres and isinstance(a, pres):
                continue
            fp = str(a.get_folder_path())
            if fp == 'Ambiente' or fp.startswith('Ambiente/'):
                continue
            label = str(a.get_actor_label())
            hit = any(fp == f or fp.startswith(f + '/') for f in folders)
            if full:
                if fp in ('FacadeTest', 'Barrio') or fp.startswith('FacadeTest/') or fp.startswith('Barrio/'):
                    hit = True
                cname = ''
                try:
                    cname = str(a.get_class().get_name())
                except Exception:
                    pass
                if label == 'GreyboxNeighborhood' or 'GreyboxNeighborhood' in cname:
                    hit = True
                    k.log('Se borra el barrio gris: %s (%s)' % (label, cname))
                try:
                    tags = [str(t) for t in a.get_editor_property('tags')]
                except Exception:
                    tags = []
                if k.GEN_TAG in tags:
                    hit = True
            if 'gameplay' in parts and isinstance(loot_cls, type) and isinstance(a, loot_cls):
                hit = True
                nloot += 1
            if hit:
                kill.append(a)
        except Exception:
            continue
    n = 0
    for a in kill:
        try:
            eas.destroy_actor(a)
            n += 1
        except Exception as e:
            k.err_once('destroy', 'No se pudo borrar un actor previo: %s' % e)
    del kill[:]
    k.log('Limpieza: %d actores borrados (%d LootPoint viejos) de %s' % (n, nloot, ', '.join(folders) or '-'))


# =====================================================================================
# PARTES
# =====================================================================================
def part_calles(c):
    k, L, G = c.k, c.L, c.G
    F_ = 'Barrio/Calles'
    plan = c.plan
    put(c, mesh(c, 'Suelo', G.build_suelo), 'Suelo', (0.0, 0.0, 0.0), 0.0, F_)
    for v in plan['veredas']:
        pits = plan['furn']['pits'].get(v['name'], [])
        strips = plan['furn']['strips'].get(v['name'], [])
        sms = mesh(c, v['name'], G.build_vereda2, v, pits, strips, _seed(v['name']))
        f = v['frame']
        put(c, sms, v['name'], (f['o'][0], f['o'][1], 0.0), f['yaw'], F_)
    items = [(G.build_calzada, (seg, _seed('Calzada_' + seg[5])), (seg[1], seg[3], 0.0), 0.0) for seg in plan['segs']]
    items += [(G.build_cruce, (rect, _seed(rect[4])), (rect[0], rect[2], 0.0), 0.0) for rect in plan['inter']]
    put(c, mesh_merged(c, 'Calzadas', items), 'Calzadas', (0.0, 0.0, 0.0), 0.0, F_)
    put(c, mesh(c, 'Avenida', G.build_avenida, _seed('Avenida')), 'Avenida', (L.AV_X0, L.AV_S_END, 0.0), 0.0, F_)
    put(c, mesh(c, 'ParcheVereda_AvVias', G.build_parche_vereda, 'ParcheVereda_AvVias', L.AV_X0, L.AV_CALZ[0],
                L.OBRA_AV_S[0] + 40.0, L.VIAS_Y0), 'ParcheVereda_AvVias', (0.0, 0.0, 0.0), 0.0, F_)


def part_manzana(c, mid):
    k, L, E, P = c.k, c.L, c.E, c.P
    F_ = 'Barrio/Manzanas/' + mid
    for lot in c.plan['lots']:
        if lot['mid'] == mid:
            k.piece('Lote %s' % lot['id'], place_lot, c, lot, F_)
    if mid != 'M11':
        name = 'Fondos_' + mid
        put(c, mesh(c, name, E.build_core, name, E.core_rect(mid), E.core_exclusions(mid), _seed(name)), name,
            (0.0, 0.0, 0.0), 0.0, F_)
    if any(p[0] == mid for p in L.PASILLOS):
        name = 'Pasillo_' + mid
        put(c, mesh(c, name, E.build_pasillo, mid, _seed(name)), name, (0.0, 0.0, 0.0), 0.0, F_)
    if mid == 'M01':
        put(c, mesh(c, 'Baldio', E.build_baldio, _seed('Baldio')), 'Baldio', (0.0, 0.0, 0.0), 0.0, F_)
    elif mid == 'M10':
        f = E.comisaria_frame()
        put(c, mesh(c, 'Comisaria', E.build_comisaria), 'Comisaria', (f['o'][0], f['o'][1], 0.0), f['yaw'], F_)
    elif mid == 'M21':
        f = L.side_frame('M21', 'N')
        put(c, mesh(c, 'Torre', E.build_torre), 'Torre12Pisos', (f['o'][0], f['o'][1], 0.0), f['yaw'], F_)
    elif mid == 'M11':
        put(c, mesh(c, 'Plaza', E.build_plaza, _seed('Plaza')), 'Plaza', (0.0, 0.0, 0.0), 0.0, F_)
        lay = E.plaza_layout()
        trees = [dict(t, big=True) for t in lay['trees']]
        spawn_trees(c, trees, F_, 'Plaza_Arbol')
        banco = cached(c, 'Banco', E.build_banco)
        for i, b in enumerate(lay['benches']):
            put(c, banco, 'Plaza_Banco_%d' % i, b['pos'], b['yaw'], F_)
        farola = cached(c, 'Farola', P.build_farola)
        for i, p in enumerate(lay['farolas']):
            put(c, farola, 'Plaza_Farola_%d' % i, p, 0.0, F_)
        can = cached(c, 'Canasto_Bolsas', P.build_canasto2, True)
        for i, q in enumerate(lay['canastos']):
            put(c, can, 'Plaza_Canasto_%d' % i, q['pos'], q['yaw'], F_)
        put(c, mesh(c, 'PuestoVias', E.build_puesto_vias), 'PuestoVias', (0.0, 0.0, 0.0), 0.0, F_)


def part_vias(c):
    k, L, G, P = c.k, c.L, c.G, c.P
    F_ = 'Barrio/Vias'
    tramo = mesh(c, 'TramoVia', G.build_tramo_via)
    x = -4000.0
    i = 0
    while x <= 42000.0:
        put(c, tramo, 'Via_%d' % i, (x, 0.0, 0.0), 0.0, F_)
        x += G.TRAMO
        i += 1
    # catenaria: mástiles cada 45 m corridos fuera del paso a nivel y de las pasarelas
    avoid = [(L.E1_X[0] - 200.0, L.E1_X[1] + 200.0), (L.E2['deck_x'][0] - 250.0, L.E2['deck_x'][1] + 250.0),
             (L.E2B['deck_x'][0] - 250.0, L.E2B['deck_x'][1] + 250.0)]
    xs = []
    x = -3500.0
    while x <= 41500.0:
        xx = x
        for (a, b) in avoid:
            if a < xx < b:
                xx = a if (xx - a) < (b - xx) else b
        xs.append(xx)
        x += 4500.0
    mast = mesh(c, 'MastilCatenaria', G.build_mastil_catenaria)
    for i, xm in enumerate(xs):
        put(c, mast, 'Catenaria_Mastil_%d' % i, (xm, 0.0, 0.0), 0.0, F_)
    put(c, mesh(c, 'HilosCatenaria', G.build_hilos_catenaria, xs, collision=False), 'Catenaria_Hilos', (0.0, 0.0, 0.0),
        0.0, F_, collision=False)
    items = [(G.build_alambrado, (name, pts, 200.0, tapial, _seed(name)), (0.0, 0.0, 0.0), 0.0)
             for (name, pts, tapial) in G.fence_runs()]
    # cierre de la franja entre la obra norte de la avenida (Y 22.356) y el alambrado sur de las vías
    items.append((G.build_alambrado, ('Tapial_CorteAvVias', [(L.AV_CALZ[0], L.OBRA_AV_S[0] + 32.0), (L.AV_CALZ[0], L.FENCE_S)],
                                      200.0, True, 5), (0.0, 0.0, 0.0), 0.0))
    put(c, mesh_merged(c, 'Alambrados_Vias', items), 'Alambrados_Vias', (0.0, 0.0, 0.0), 0.0, F_)
    put(c, mesh(c, 'PasoNivel', G.build_paso_nivel, _seed('PasoNivel')), 'PasoNivel_E1', (L.E1_X[0], L.VIAS_Y0, 0.0),
        0.0, F_)
    put(c, mesh(c, 'PasarelaE2', G.build_pasarela, L.E2), 'Pasarela_E2', (0.0, 0.0, 0.0), 0.0, F_)
    put(c, mesh(c, 'PasarelaProvisoria', G.build_pasarela, L.E2B, True), 'Pasarela_Provisoria', (0.0, 0.0, 0.0), 0.0, F_)
    tren = mesh(c, 'Formacion', P.build_formacion)
    for i, (xt, yt) in enumerate(G.TRAIN_X):
        put(c, tren, 'Formacion_%d' % i, (xt, yt, 0.0), 0.0, F_)
    put(c, mesh(c, 'CorredorSuelo', G.build_corredor_suelo, _seed('CorredorSuelo'), collision=False), 'CorredorSuelo',
        (0.0, 0.0, 0.0), 0.0, F_, collision=False)
    alamos = [cached(c, 'Alamo_%d' % s, G.build_alamo, s) for s in range(3)]
    for i, (xa, ya) in enumerate(((8900.0, 26750.0), (9700.0, 26550.0), (13000.0, 26800.0), (21600.0, 26850.0),
                                  (23200.0, 26700.0), (29800.0, 26800.0), (30600.0, 26600.0))):
        put(c, alamos[i % 3], 'Alamo_%d' % i, (xa, ya, 3.0 - L.Z_VER), (i * 53.0) % 360.0, F_)


def part_afuera(c):
    k, L, G, P, E = c.k, c.L, c.G, c.P, c.E
    F_ = 'Barrio/Afuera'
    O = (0.0, 0.0, 0.0)
    # ---- Afuera Norte: estación, calles, filas de lotes
    put(c, mesh(c, 'Estacion', E.build_estacion, _seed('Estacion')), 'Estacion', O, 0.0, F_)
    put(c, mesh(c, 'CallesAfuera', E.build_calles_afuera, _seed('CallesAfuera')), 'CallesAfuera', O, 0.0, F_)
    ey0, ey1 = L.EST_CALLE_Y
    segs = [('EW', E.AFN_W, E.EXPLANADA['x'][0], ey0, ey1, 'Estacion_O'),
            ('EW', E.EXPLANADA['x'][1], L.AV_CALZ[0], ey0, ey1, 'Estacion_E'),
            ('NS', L.E1_X[0] + L.VER, L.E1_X[1] - L.VER, L.VIAS_Y1, ey0, 'C01_Norte')]
    items = [(G.build_calzada, (seg, _seed('Calzada_' + seg[5]), (seg[5] != 'C01_Norte', True)), (seg[1], seg[3], 0.0),
              0.0) for seg in segs]
    put(c, mesh_merged(c, 'CalzadasAfuera', items), 'CalzadasAfuera', O, 0.0, F_)
    fN = L.make_frame((E.ROW_N['x0'], E.ROW_N['y']), (0.0, -1.0))
    xexp = E.EXPLANADA['x'][0]
    lotsN = build_row(c, 'AfueraN', fN, E.ROW_N['n'], _seed('AfueraN'), ['A', 'A2', 'C', 'E', 'B', 'E'], F_,
                      lambda i: E.ROW_N['x0'] + (i + 1) * L.LOT > xexp)
    Lv = xexp - E.ROW_N['x0']
    segsv = []
    y = 0.0
    rng = random.Random(_seed('VeredaEstacionN'))
    while y < Lv - 1.0:
        y1 = min(Lv, y + L.LOT)
        segsv.append((y, y1, rng.choice(['MI_Baldosa', 'MI_Baldosa', 'MI_Hormigon']), rng.choice([0.0, 0.4, -0.3])))
        y = y1
    ramps = [(lot['y0'] + lot['garage'][0], lot['y0'] + lot['garage'][1]) for lot in lotsN
             if lot.get('garage') and lot['y0'] + lot['garage'][1] < Lv - 30.0]
    spec = {'name': 'Vereda_EstacionN', 'frame': fN, 'L': Lv, 'w': L.VER, 'wprev': L.VER, 'corner': False,
            'segs': segsv, 'ramps': ramps, 'mid': None, 'side': None, 'plaza': False}
    put(c, mesh(c, 'Vereda_EstacionN', G.build_vereda2, spec, [], [], _seed('Vereda_EstacionN')), 'Vereda_EstacionN',
        (fN['o'][0], fN['o'][1], 0.0), fN['yaw'], F_)
    c.afuera_lots = lotsN
    xN1 = E.ROW_N['x0'] + E.ROW_N['n'] * L.LOT
    cores = [('Fondos_AfueraN', (E.AFN_W, xN1, E.ROW_N['y'] + E.CORE_INSET, 34000.0)),
             ('Fondos_AfueraE', (L.AV_X1 + E.CORE_INSET, 37600.0, -500.0, E.ROW_E['y0'])),
             ('Fondos_AfueraEN', (L.AV_X1 + E.CORE_INSET, 37600.0, E.ROW_EN['y0'] - E.ROW_EN['n'] * L.LOT, 33800.0))]
    for (name, rect) in cores:
        put(c, mesh(c, name, E.build_core, name, rect, [], _seed(name)), name, O, 0.0, F_)
    # tapial del pasaje entre la fila norte y el galpón
    put(c, mesh(c, 'Tapial_PasajeGalpon', G.build_alambrado, 'Tapial_PasajeGalpon',
                [(xN1, E.ROW_N['y'] + 10.0), (E.GALPON['x'][0] + 15.0, E.ROW_N['y'] + 10.0),
                 (E.GALPON['x'][0] + 15.0, E.GALPON['front_y'])], 200.0, True, 3),
        'Tapial_PasajeGalpon', O, 0.0, F_)
    # ---- galpón del reducidor y playón
    put(c, mesh(c, 'GalponReducidor', E.build_galpon_reducidor, _seed('Galpon')), 'GalponReducidor', O, 0.0, F_)
    put(c, cached(c, 'Auto_sedan', P.build_auto, 'sedan'), 'Galpon_AutoDesarmadero', (22900.0, 31600.0, L.Z_VER), 90.0,
        F_, swaps={'MI_Auto_Blanco': 'MI_Auto_Rojo'})
    put(c, mesh(c, 'Playon', E.build_playon, _seed('Playon')), 'Playon', O, 0.0, F_)
    pl = E.playon_layout()
    cm = cached(c, 'ContenedorMaritimo', E.build_contenedor_maritimo)
    for i, (pos, yaw, colr) in enumerate(pl['containers']):
        put(c, cm, 'Playon_Contenedor_%d' % i, pos, yaw, F_,
            swaps=({'MI_Metal_Verde': colr} if colr != 'MI_Metal_Verde' else None))
    cam = cached(c, 'Camion', P.build_camion)
    for i, (pos, yaw) in enumerate(pl['trucks']):
        put(c, cam, 'Playon_Camion_%d' % i, pos, yaw, F_, swaps={'MI_Auto_Blanco': ('MI_Auto_Azul', 'MI_Auto_Gris')[i % 2]})
    items = [(G.build_alambrado, (name, pts, 200.0, tapial, _seed(name)), O, 0.0) for (name, pts, tapial) in E.playon_fences()]
    put(c, mesh_merged(c, 'Alambrados_Playon', items), 'Alambrados_Playon', O, 0.0, F_)
    # ---- avenida norte
    put(c, mesh(c, 'AvenidaNorte', E.build_avenida_norte, _seed('AvenidaNorte')), 'AvenidaNorte', O, 0.0, F_)
    col = cached(c, 'ColumnaAv', P.build_columna_av)
    xc = 0.5 * (L.AV_CANTERO[0] + L.AV_CANTERO[1])
    for i, yc in enumerate(E.avn_column_ys()):
        put(c, col, 'AvNorte_Columna_%d' % i, (xc, yc, 0.0), 0.0, F_)
    # ---- Afuera Este: locales de enfrente de la avenida y obras de la pasarela provisoria
    fE = L.make_frame((L.AV_X1, E.ROW_E['y0']), (-1.0, 0.0))
    c.afuera_lots += build_row(c, 'AfueraE', fE, E.ROW_E['n'], _seed('AfueraE'), ['E', 'E', 'E', 'A2', 'C', 'B'], F_)
    fEN = L.make_frame((L.AV_X1, E.ROW_EN['y0']), (-1.0, 0.0))
    c.afuera_lots += build_row(c, 'AfueraEN', fEN, E.ROW_EN['n'], _seed('AfueraEN'), ['E', 'A2', 'C', 'B'], F_)
    put(c, mesh(c, 'ObraE2B', E.build_obra_e2b, _seed('ObraE2B')), 'ObraE2B', O, 0.0, F_)
    # ---- bordes: tapial y club al oeste, galpones al sur
    put(c, mesh(c, 'Tapial_Club', G.build_alambrado, 'Tapial_Club', [(-12.0, -30.0), (-12.0, L.FENCE_S)], 220.0, True, 11),
        'Tapial_Club', O, 0.0, F_)
    put(c, mesh(c, 'Club', E.build_club, _seed('Club'), collision=False), 'Club', O, 0.0, F_, collision=False)
    put(c, mesh(c, 'GalponesSur', E.build_galpones_sur, _seed('GalponesSur')), 'GalponesSur', O, 0.0, F_)
    put(c, mesh(c, 'EdificiosBajos', E.build_edificios_bajos, _seed('EdificiosBajos'), collision=False), 'EdificiosBajos',
        O, 0.0, F_, collision=False)
    put(c, mesh(c, 'SkylineTorres', E.build_skyline, _seed('Skyline'), collision=False), 'SkylineTorres', O, 0.0, F_,
        collision=False)
    # ---- árboles y bancos de Afuera
    spawn_trees(c, E.afuera_trees(), F_, 'Afuera_Arbol')
    lay = E.estacion_layout()
    spawn_trees(c, lay['trees'], F_, 'Estacion_Arbol')
    spawn_trees(c, E.club_trees(), F_, 'Club_Arbol')
    banco = cached(c, 'Banco', E.build_banco)
    for i, b in enumerate(lay['benches']):
        put(c, banco, 'Estacion_Banco_%d' % i, b['pos'], b['yaw'], F_)


def _tramo_key(L, mid, side, street):
    col, row = L.MANZANAS[mid]
    return '%s_%d' % (street, col if side in ('S', 'N') else row)


def collect_lums(c):
    """Todas las luminarias del mapa (contrato v2), en un orden estable."""
    k, L, E = c.k, c.L, c.E
    out = []
    for p in c.plan['furn']['poles'] + c.plan['border_poles']:
        if p['kind'] != 'lum':
            continue
        rot = k.R(roll=p['tilt'][0], pitch=p['tilt'][1], yaw=p['yaw'])
        out.append(k.world_pt(p['pos'], rot, (L.ARM_X + 8.0, 0.0, L.LUM_Z)))
    for l in c.plan['avenue']['lums'] + E.avn_lums() + E.plaza_lums() + E.estacion_lums() + E.galpon_lums() + \
            E.playon_lums():
        out.append(l['pos'])
    for (mid, ax, a0, a1) in L.PASILLOS:
        for l in E.pasillo_lums(mid):
            out.append(l['pos'])
    return out


def part_props(c):
    import unreal
    k, L, G, P, E = c.k, c.L, c.G, c.P, c.E
    FP, FA, FC, FL = 'Barrio/Props', 'Barrio/Autos', 'Barrio/Cables', 'Barrio/Luminarias'
    plan = c.plan
    furn = plan['furn']
    # ---- postes (calles y Afuera)
    pole_rt = []
    for i, p in enumerate(furn['poles'] + plan['border_poles']):
        sms = cached(c, 'Poste_%s_%s' % (p['kind'], p['mat']), P.build_poste2, p['kind'], p['mat'])
        rot = k.R(roll=p['tilt'][0], pitch=p['tilt'][1], yaw=p['yaw'])
        put(c, sms, 'Poste_%d' % i, p['pos'], rot=rot, folder=FP)
        pole_rt.append((p, rot))
        c.count['postes'] = c.count.get('postes', 0) + 1
    # ---- árboles, canastos, carteles, contenedores
    spawn_trees(c, furn['trees'], FP, 'Arbol')
    for i, q in enumerate(furn['canastos']):
        sms = cached(c, 'Canasto_Bolsas' if q['bolsas'] else 'Canasto', P.build_canasto2, q['bolsas'])
        put(c, sms, 'Canasto_%d' % i, q['pos'], q['yaw'], FP)
    cartel = cached(c, 'CartelCalle', P.build_cartel_calle)
    for i, s in enumerate(plan['signs']):
        put(c, cartel, 'CartelCalle_%d' % i, s['pos'], s['yaw'], FP)
    cont = cached(c, 'Contenedor', P.build_contenedor)
    for i, q in enumerate(plan['containers']):
        put(c, cont, 'Contenedor_%d' % i, (q['pos'][0], q['pos'][1], 2.5), q['yaw'], FP)
    # ---- avenida
    av = plan['avenue']
    col = cached(c, 'ColumnaAv', P.build_columna_av)
    for i, p in enumerate(av['cols']):
        put(c, col, 'Avenida_Columna_%d' % i, p, 0.0, FP)
    par = cached(c, 'Parada', P.build_parada)
    for i, q in enumerate(av['paradas']):
        put(c, par, 'Parada_%d' % i, q['pos'], q['yaw'], FP)
    sem = cached(c, 'Semaforo', P.build_semaforo)
    for i, q in enumerate(av['semaforos']):
        put(c, sem, 'Semaforo_%d' % i, q['pos'], q['yaw'], FP)
    # ---- cortes de visual (cada <= 120 m)
    for i, q in enumerate(plan['cuts']):
        kind = q['kind']
        if kind == 'camion':
            sms = cached(c, 'Camion', P.build_camion)
        elif kind == 'colectivo':
            sms = cached(c, 'Colectivo', P.build_colectivo)
        else:
            sms = cached(c, 'Corte_' + kind, P.build_corte, kind)
        put(c, sms, 'Corte_%s_%d' % (kind, i), (q['pos'][0], q['pos'][1], 2.0), q['yaw'], FP,
            swaps=({'MI_Auto_Blanco': 'MI_Auto_Gris'} if kind == 'camion' and i % 2 else None))
        c.count['cortes'] = c.count.get('cortes', 0) + 1
    # ---- autos estacionados (genéricos), color por instancia
    for i, q in enumerate(plan['cars']):
        sms = cached(c, 'Auto_' + q['type'], P.build_auto, q['type'])
        sw = {'MI_Auto_Blanco': q['color']} if q['color'] != 'MI_Auto_Blanco' else None
        put(c, sms, 'Auto_%s_%d' % (q['type'], i), (q['pos'][0], q['pos'][1], 3.0), q['yaw'], FA, swaps=sw)
        c.count['autos'] = c.count.get('autos', 0) + 1
    # ---- cables por tramo de calle (una malla Nanite sin colisión por tramo)
    groups = {}
    for (p, rot) in pole_rt:
        if p.get('mid'):
            key = _tramo_key(L, p['mid'], p['side'], p['street'])
            along = p['pos'][0] if p['side'] in ('S', 'N') else p['pos'][1]
            sid = (p['mid'], p['side'])
        else:
            key = 'Estacion'
            along = p['pos'][0]
            sid = ('borde', p['kind'])
        groups.setdefault(key, {'poles': [], 'houses': []})['poles'].append(
            {'loc': p['pos'], 'rot': rot, 'kind': p['kind'], 'side_id': sid, 'along': along})
    for lot in plan['lots'] + list(getattr(c, 'afuera_lots', [])):
        if not lot.get('variant') or lot.get('power') is None:
            continue
        f = lot['frame']
        if lot.get('mid'):
            key = _tramo_key(L, lot['mid'], lot['side'], L.street_of(lot['mid'], lot['side']))
        elif str(lot.get('side', '')).startswith('AfueraN'):
            key = 'Estacion'
        else:
            continue
        pw = lot['power']
        h = {'power': L.fw(f, pw[0], lot['y0'] + pw[1], pw[2]),
             'tel': [L.fw(f, t[0], lot['y0'] + t[1], t[2]) for t in lot.get('tel', [])]}
        if key in groups:
            groups[key]['houses'].append(h)
    for key in sorted(groups.keys()):
        g = groups[key]
        name = 'Cables_' + key
        sms = mesh(c, name, G.build_cables_group, name, g['poles'], g['houses'], _seed(name), collision=False)
        put(c, sms, name, (0.0, 0.0, 0.0), 0.0, FC, collision=False, shadow=True)
        if sms:
            c.count['cables'] = c.count.get('cables', 0) + 1
    # ---- luminarias (contrato con la iluminación)
    tp_cls = getattr(unreal, 'TargetPoint', None)
    for i, pos in enumerate(collect_lums(c)):
        try:
            a = k.spawn_class(tp_cls, 'LUM_%d' % i, pos, k.R(pitch=-90.0), FL)
            if a is not None:
                a.set_editor_property('tags', [unreal.Name(k.GEN_TAG), unreal.Name('LUMINARIA')])
                c.count['luminarias'] = c.count.get('luminarias', 0) + 1
        except Exception as e:
            k.err_once('lum', 'No se pudo crear LUM_%d: %s' % (i, e))


# =====================================================================================
# JUEGO
# =====================================================================================
def _cls(name):
    import unreal
    c = getattr(unreal, name, None)
    return c if isinstance(c, type) else None


def _move(c, a, loc, yaw, label=None):
    k = c.k
    a.set_actor_location(k.V(loc), False, True)
    a.set_actor_rotation(k.R(yaw=yaw), True)
    if label:
        a.set_actor_label(label)
    a.set_folder_path(GP)


def _box_extent(c, a, ext):
    import unreal
    k = c.k
    try:
        a.set_actor_scale3d(k.V(1.0, 1.0, 1.0))
        comp = a.get_component_by_class(unreal.BoxComponent)
        if comp is None:
            k.warn('%s no tiene BoxComponent: no se ajustó el tamaño' % a.get_actor_label())
            return
        comp.set_box_extent(k.V(ext), True)
    except Exception as e:
        k.warn('No se pudo ajustar la caja de %s: %s' % (a.get_actor_label(), e))


def _tags(a):
    try:
        return [str(t) for t in a.get_editor_property('tags')]
    except Exception:
        return []


def _is_police_start(a):
    try:
        if str(a.get_editor_property('player_start_tag')) == 'Police':
            return True
    except Exception:
        pass
    return 'Police' in _tags(a)


def _set_tier(c, a, tier):
    """tier: 'High' / 'Low' / None (aleatorio). Solo si el LootPoint tiene esas propiedades."""
    import unreal
    k = c.k

    def try_set(name, val):
        try:
            a.set_editor_property(name, val)
            return True
        except Exception:
            return False
    rnd_names = ('b_randomize_tier', 'randomize_tier')
    if tier is None:
        for n in rnd_names:
            if try_set(n, True):
                return True
        return False
    for prop in ('tier', 'loot_tier'):
        try:
            cur = a.get_editor_property(prop)
        except Exception:
            continue
        cands = [type(cur)] + [getattr(unreal, n, None) for n in ('LootTier', 'ELootTier', 'BarrioLootTier')]
        for enum_cls in cands:
            if enum_cls is None:
                continue
            for nm in (tier.upper(), tier, tier.capitalize(), 'TIER_' + tier.upper()):
                val = getattr(enum_cls, nm, None)
                if val is not None and try_set(prop, val):
                    for n in rnd_names:
                        if try_set(n, False):
                            break
                    return True
        k.warn_once('tier_enum', 'LootPoint.%s existe pero no encontré el valor "%s" en %s' % (prop, tier, type(cur)))
        return False
    k.warn_once('tier_prop', 'LootPoint no tiene propiedad tier/loot_tier: el botín queda como lo decida el actor')
    return False


def place_navmesh(c):
    import unreal
    k, L = c.k, c.L
    cls = _cls('NavMeshBoundsVolume')
    if cls is None:
        k.err('No existe unreal.NavMeshBoundsVolume')
        return
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    vols = [a for a in eas.get_all_level_actors() if isinstance(a, cls)]
    center, size = L.GAMEPLAY['nav']
    if vols:
        v = vols[0]
        if len(vols) > 1:
            k.warn('Hay %d NavMeshBoundsVolume; se usa "%s" y los otros quedan como estaban' %
                   (len(vols), v.get_actor_label()))
    else:
        v = k.spawn_class(cls, 'NavMeshBounds_Barrio', center, None, GP)
        k.warn('Se creó un NavMeshBoundsVolume nuevo: verificar que tenga brush (si no, crear uno a mano)')
    if v is None:
        return
    _move(c, v, center, 0.0)
    try:
        v.set_actor_scale3d(k.V(1.0, 1.0, 1.0))
        res = v.get_actor_bounds(False)
        ext = res[1] if isinstance(res, (list, tuple)) else res
        half = [max(1.0, abs(ext.x)), max(1.0, abs(ext.y)), max(1.0, abs(ext.z))]
        if min(half) < 2.0:
            half = [100.0, 100.0, 100.0]
        v.set_actor_scale3d(k.V(size[0] * 0.5 / half[0], size[1] * 0.5 / half[1], size[2] * 0.5 / half[2]))
        k.log('NavMeshBoundsVolume "%s": %.0f x %.0f x %.0f m centrado en %s' %
              (v.get_actor_label(), size[0] / 100.0, size[1] / 100.0, size[2] / 100.0, center))
    except Exception as e:
        k.err('No se pudo escalar el NavMeshBoundsVolume: %s' % e)
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(world, 'RebuildNavigation')
        k.log('Navegación: se pidió RebuildNavigation. Si no aparece (tecla P en el viewport), Build > Build Paths.')
    except Exception as e:
        k.warn('Navegación: reconstruir a mano con Build > Build Paths (%s)' % e)


def part_gameplay(c):
    import unreal
    k, L, E = c.k, c.L, c.E
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(eas.get_all_level_actors())
    G_ = L.GAMEPLAY

    def of(name):
        cls = _cls(name)
        if cls is None:
            k.warn('No existe la clase unreal.%s (¿módulo del juego compilado?)' % name)
            return cls, []
        return cls, sorted([a for a in actors if isinstance(a, cls)], key=lambda a: str(a.get_actor_label()))

    def need(cls, have, label, loc, yaw=0.0):
        if have is not None:
            return have
        if cls is None:
            return None
        a = k.spawn_class(cls, label, loc, k.R(yaw=yaw), GP)
        if a is not None:
            k.log('Creado %s (no existía)' % label)
        return a
    cg = E.comisaria_gameplay()
    # ---- PlayerStart: 2 de llegada + 1 de policía
    cls_ps, starts = of('PlayerStart')
    police = [a for a in starts if _is_police_start(a)]
    arrive = [a for a in starts if not _is_police_start(a)]
    for i, (loc, yaw) in enumerate(G_['player_starts']):
        a = need(cls_ps, arrive[i] if i < len(arrive) else None, 'PlayerStart_Llegada_%d' % (i + 1), loc, yaw)
        if a is not None:
            _move(c, a, loc, yaw, 'PlayerStart_Llegada_%d' % (i + 1))
    for j, a in enumerate(arrive[len(G_['player_starts']):]):
        loc = (16000.0 + 400.0 * j, 28100.0, L.Z_VER + 100.0)
        _move(c, a, loc, -90.0)
        k.warn('PlayerStart extra "%s" movido a la llegada' % a.get_actor_label())
    pa = need(cls_ps, police[0] if police else None, 'PlayerStart_Policia', cg['police'][0], cg['police'][1])
    if pa is not None:
        _move(c, pa, cg['police'][0], cg['police'][1], 'PlayerStart_Policia')
        try:
            pa.set_editor_property('player_start_tag', unreal.Name('Police'))
        except Exception:
            pass
        tg = _tags(pa)
        if 'Police' not in tg:
            try:
                pa.set_editor_property('tags', [unreal.Name(t) for t in tg] + [unreal.Name('Police')])
            except Exception:
                pass
    for a in police[1:]:
        _move(c, a, cg['police'][0], cg['police'][1])
    # ---- zonas seguras
    cls_sz, zones = of('BarrioSafeZone')
    comi = [a for a in zones if any(s in str(a.get_actor_label()).lower() for s in ('comis', 'polic', 'police'))]
    rest = [a for a in zones if a not in comi]
    zl = rest[0] if rest else None
    zc = comi[0] if comi else (rest[1] if len(rest) > 1 else None)
    (sl_c, sl_e) = G_['safe_llegada']
    zl = need(cls_sz, zl, 'SafeZone_Llegada', sl_c)
    if zl is not None:
        _move(c, zl, sl_c, 0.0, 'SafeZone_Llegada')
        _box_extent(c, zl, sl_e)
    zc = need(cls_sz, zc, 'SafeZone_Comisaria', cg['safe'][0])
    if zc is not None:
        _move(c, zc, cg['safe'][0], 0.0, 'SafeZone_Comisaria')
        _box_extent(c, zc, cg['safe'][1])
    # ---- salidas (la 3ª se crea si falta)
    cls_ez, exits = of('ExitZone')
    keys = [('e1', 'paso'), ('e2', 'pasarela'), ('e3', 'avenida')]
    assigned = [None, None, None]
    for a in exits:
        lab = str(a.get_actor_label()).lower()
        for i, ks in enumerate(keys):
            if assigned[i] is None and any(s in lab for s in ks):
                assigned[i] = a
                break
    free = [a for a in exits if a not in assigned]
    for i in range(3):
        if assigned[i] is None and free:
            assigned[i] = free.pop(0)
    for i, (label, cen, ext) in enumerate(G_['exit']):
        a = need(cls_ez, assigned[i], label, cen)
        if a is not None:
            _move(c, a, cen, 0.0, label)
            _box_extent(c, a, ext)
    # ---- comisaría (mostrador), reducidor, celda
    for (name, loc, yaw, label) in (('PoliceStation', cg['counter'][0], cg['counter'][1], 'PoliceStation_Comisaria'),
                                    ('FenceStation', G_['fence'][0], G_['fence'][1], 'FenceStation_Reducidor'),
                                    ('JailCell', cg['jail'][0], cg['jail'][1], 'JailCell_Celda')):
        cls, have = of(name)
        a = need(cls, have[0] if have else None, label, loc, yaw)
        if a is not None:
            _move(c, a, loc, yaw, label)
        for extra in have[1:]:
            k.warn('%s extra "%s" quedó donde estaba' % (name, extra.get_actor_label()))
    # ---- puntos de robo (~60, frente a la puerta, mirando a la calle)
    cls_lp = _cls('LootPoint')
    if cls_lp is None:
        k.err('No existe unreal.LootPoint: no se colocan robos')
    else:
        ntier = 0
        for i, q in enumerate(c.plan['loot']):
            try:
                a = k.spawn_class(cls_lp, 'Loot_%02d_%s' % (i, q['id']), q['pos'], k.R(yaw=q['yaw']), GP)
                if a is None:
                    continue
                if _set_tier(c, a, q.get('tier')):
                    ntier += 1
                c.count['loot'] = c.count.get('loot', 0) + 1
            except Exception as e:
                k.err_once('loot', 'No se pudo crear el LootPoint %s: %s' % (q['id'], e))
        k.log('LootPoints: %d (%d con tier/aleatorio fijado); High %d, Low %d, aleatorio %d; sin cubrir a 40 m: %d' %
              (c.count.get('loot', 0), ntier, sum(1 for q in c.plan['loot'] if q.get('tier') == 'High'),
               sum(1 for q in c.plan['loot'] if q.get('tier') == 'Low'),
               sum(1 for q in c.plan['loot'] if q.get('tier') is None), len(c.plan['uncovered'])))
    # ---- puntos de patrulla sugeridos (TargetPoint con tag PATRULLA)
    tp = _cls('TargetPoint')
    for i, (x, y) in enumerate(G_['patrol']):
        try:
            a = k.spawn_class(tp, 'PATRULLA_%d' % i, (x, y, L.Z_VER + 60.0), k.R(), GP)
            if a is not None:
                a.set_editor_property('tags', [unreal.Name(k.GEN_TAG), unreal.Name('PATRULLA')])
        except Exception as e:
            k.err_once('patrol', 'Punto de patrulla %d: %s' % (i, e))
    k.piece('NavMesh', place_navmesh, c)


# =====================================================================================
# MAIN
# =====================================================================================
def run(c, parts):
    import unreal
    k = c.k
    k.log('==== build_barrio.py: mapa jugable de Caseros (semilla %d, partes: %s) ====' %
          (SEED, 'TODAS' if SOLO is None else ', '.join(parts)))
    k.probe_api()
    if not k.F.get('box') or not k.F.get('append_mesh') or not (k.F.get('create_sm') or k.F.get('copy_sm')):
        k.err('Faltan funciones básicas de Geometry Script; ¿está habilitado el plugin GeometryScripting?')
        return False
    k.piece('Calibracion', k.calibrate)
    k.piece('Calibracion escaleras', k.stairs_probe)
    k.ensure_map()
    k.piece('Limpieza', cleanup, c, parts, SOLO is None)
    k.load_materials()
    try:
        unreal.EditorAssetLibrary.make_directory(k.ASSET_DIR)
    except Exception:
        pass
    c.plan = c.L.build_plan(SEED)
    k.log('Plan: %d lotes, %d robos, %d autos, %d cortes, %d árboles de vereda' %
          (len(c.plan['lots']), len(c.plan['loot']), len(c.plan['cars']), len(c.plan['cuts']),
           len(c.plan['furn']['trees'])))
    funcs = {'calles': part_calles, 'vias': part_vias, 'afuera': part_afuera, 'props': part_props,
             'gameplay': part_gameplay}
    for mid, (cc, rr) in c.L.MANZANAS.items():
        funcs['manzana_%d_%d' % (cc, rr)] = (lambda m: (lambda cx: part_manzana(cx, m)))(mid)
    with unreal.ScopedSlowTask(len(parts) + 1, 'Construyendo el barrio...') as task:
        task.make_dialog(True)
        for p in parts:
            if task.should_cancel():
                k.warn('Cancelado por el usuario antes de "%s"' % p)
                break
            task.enter_progress_frame(1, 'Barrio: %s' % p)
            tp = time.time()
            k.piece('Parte %s' % p, funcs[p], c)
            k.log('Parte %s: %.1f s (mallas %d, actores %d)' % (p, time.time() - tp, k.STATS.get('meshes', 0),
                                                                 k.STATS.get('actors', 0)))
        task.enter_progress_frame(1, 'Guardando')
        k.save_all()
    return True


def main():
    t0 = time.time()
    d = _script_dir()
    if d not in sys.path:
        sys.path.insert(0, d)
    import unreal
    mods = _load_modules()
    c = Ctx()
    c.k, c.L, c.P, c.G, c.E = (mods['barrio_kit'], mods['barrio_layout'], mods['barrio_props'], mods['barrio_geo'],
                               mods['barrio_edificios'])
    mods.clear()
    k = c.k
    c.cache, c.variants, c.count, c.afuera_lots, c.plan = {}, {}, {}, [], None
    parts = list(PARTS) if SOLO is None else [p for p in PARTS if p in SOLO]
    unknown = [] if SOLO is None else [p for p in SOLO if p not in PARTS]
    k.reset_state(SEED)
    trace_path = None
    try:
        trace_path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                  'barrio_trace.txt')
    except Exception:
        trace_path = os.path.join(d, 'barrio_trace.txt')
    k.trace_open(trace_path)
    k.pool_open()
    if unknown:
        k.warn('SOLO tiene partes desconocidas (se ignoran): %s' % ', '.join(unknown))
    ok = False
    try:
        ok = run(c, parts)
    except Exception as e:
        k.err('Corrida abortada: %s\n%s' % (e, traceback.format_exc()))
    try:
        cnt = c.count
        st = k.STATS
        k.log('==== RESUMEN ====')
        k.log('Lotes instanciados %d (variantes %d) | rejas de puerta %d | LootPoints %d | luminarias %d' %
              (cnt.get('lotes', 0), cnt.get('variantes', 0), cnt.get('rejas', 0), cnt.get('loot', 0),
               cnt.get('luminarias', 0)))
        k.log('Autos %d | cortes de visual %d | árboles %d | postes %d | tramos de cables %d' %
              (cnt.get('autos', 0), cnt.get('cortes', 0), cnt.get('arboles', 0), cnt.get('postes', 0),
               cnt.get('cables', 0)))
        k.log('Mallas %d (con error %d) | actores %d | piezas OK %d | piezas con error %d | DynamicMesh pedidas %d '
              'devueltas %d | %.1f s' % (st.get('meshes', 0), st.get('mesh_fail', 0), st.get('actors', 0), st['ok'],
                                         st['fail'], k.POOL.get('requested', 0), k.POOL.get('returned', 0),
                                         time.time() - t0))
        if st['fail']:
            k.warn('Piezas con error: %s' % ', '.join(sorted(set(st.get('fail_names', [])))[:30]))
        if 'props' in parts or 'gameplay' in parts:
            k.log('Recordatorio: correr setup_lighting.py (preset noche) para poner luces en los LUM_<n> nuevos; '
                  'y reconstruir la navegación si no se hizo sola (Build > Build Paths).')
    except Exception as e:
        k.err('Resumen: %s' % e)
    # ---- soltar TODO lo de Unreal antes de volver al editor
    nfail = k.STATS.get('fail', 0)
    c.__dict__.clear()
    c = None
    k.trace('SHUTDOWN')
    k.shutdown()
    gc.collect()
    try:
        unreal.SystemLibrary.collect_garbage()
    except Exception:
        pass
    gc.collect()
    msg = '[BARRIO] MAPA LISTO (%s, %d piezas con error, %.1f s)' % ('ok' if ok else 'con errores', nfail,
                                                                     time.time() - t0)
    unreal.log(msg)
    try:
        if trace_path:
            with open(trace_path, 'a', encoding='utf-8') as fh:
                fh.write(msg + '\n')
    except Exception:
        pass


main()
