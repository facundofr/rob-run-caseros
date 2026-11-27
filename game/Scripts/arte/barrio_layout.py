# -*- coding: utf-8 -*-
"""
barrio_layout.py  -  Trazado del mapa de Barrio (MAPA.md) en Python puro (sin Unreal).

Todo lo que es "dónde va cada cosa" vive acá y se puede probar fuera del editor:
manzanas, lotes y variantes, veredas, calles, postes y luminarias, árboles, autos, cortes de visual,
puntos de robo, actores de juego. Coordenadas en cm: X este, Y norte, Z=0 calzada.

Convención de marcos de lado de manzana (frame): local +x = normal hacia la calle (afuera de la
manzana), local +y = a lo largo del frente, z arriba. La línea municipal (LM) es x=0.
  S: n=(0,-1) u=(1,0)  yaw -90  origen (x0,y0)      E: n=(1,0)  u=(0,1)  yaw 0    origen (x1,y0)
  N: n=(0,1)  u=(-1,0) yaw 90   origen (x1,y1)      W: n=(-1,0) u=(0,-1) yaw 180  origen (x0,y1)
Cada lado empieza en una esquina (slot 0 = esquina, con ochava) y tiene slots 1..8 de 8,66 m;
el slot 9 es la esquina del lado siguiente.
"""

import math
import random

# =====================================================================================
# MEDIDAS (MAPA.md §2-3)
# =====================================================================================
LOT = 866.0
MZ = 8660.0
CALLE = 1732.0
VER = 350.0            # vereda de calle
VER_AV = 450.0         # vereda de avenida
CALZ = 1032.0          # calzada entre cordones
OCHAVA = 283.0         # 4 m de ochava -> 2,83 m sobre cada línea municipal
Z_VER = 16.0

XCOL = [(1732.0, 10392.0), (12124.0, 20784.0), (22516.0, 31176.0)]
# v5: fila sur (-1) agregada. La calle 'Sur' (Y 0-1.732) pasa a ser la calle COMERCIAL (tipo 3 de Febrero: arcos,
# locales y edificios de departamentos) y aparece la calle 'Fondo' (Y -10.392 / -8.660) contra los galpones.
# YROW es un dict (fila -> (y0, y1)): ¡no indexar con [-1] creyendo que es la última fila!
ROWS = (-1, 0, 1)
YROW = {-1: (-8660.0, 0.0), 0: (1732.0, 10392.0), 1: (12124.0, 20784.0)}
FONDO_Y = (-10392.0, -8660.0)                  # calle Fondo, línea municipal a línea municipal
Y_SUR_MAPA = FONDO_Y[0]                        # frente de los galpones sur
COMERCIAL_SIDES = {('M0S', 'N'), ('M1S', 'N'), ('M2S', 'N'), ('M10', 'S'), ('M20', 'S')}
AV_X0, AV_X1 = 31176.0, 33776.0                # avenida LM a LM
AV_CALZ = (31626.0, 33326.0)                   # calzada 17 m
AV_CANTERO = (32401.0, 32551.0)                # cantero central con reja (1,5 m)
VIAS_Y0, VIAS_Y1 = 22516.0, 26016.0
FENCE_S, FENCE_N = 22616.0, 25916.0
TRACKS_Y = [24450.0, 24880.0]                  # ejes de las dos vías (trocha ancha 1676 mm)
GAUGE = 167.6
RAIL_TOP = 45.0                                # balasto 25 + durmiente 5 + riel 15
E1_X = (10392.0, 12124.0)
E3_Y = (10392.0, 12124.0)
# Pasarela E2: tablero a lo largo de Y sobre las vías; escaleras paralelas a las vías
E2 = dict(deck_x=(26680.0, 26920.0), deck_y=(22540.0, 26260.0), z=700.0, w=240.0,
          stairs=[dict(top=(26680.0, 22660.0), dir=(-1.0, 0.0)),      # sur: baja hacia el oeste
                  dict(top=(26680.0, 26140.0), dir=(-1.0, 0.0))],     # norte: baja hacia el oeste
          jog=(25280.0, 26960.0, 22880.0))                           # el alambrado sur rodea la escalera
# Pasarela provisoria de la obra del paso bajo nivel (une Afuera Este con Afuera Norte)
E2B = dict(deck_x=(34400.0, 34640.0), deck_y=(21900.0, 26300.0), z=700.0, w=240.0,
           stairs=[dict(top=(34640.0, 22020.0), dir=(1.0, 0.0)),
                   dict(top=(34640.0, 26180.0), dir=(1.0, 0.0))])
STAIR_RUN = 1270.0     # 2 tramos de 20 escalones (17,5 x 28) + descanso de 1,5 m
# Estación
PLATFORM = dict(x=(14000.0, 20500.0), y=(TRACKS_Y[1] + 165.0, FENCE_N), z=40.0)   # 40 cm: se sube sin rampa
STATION = dict(x=(15600.0, 18400.0), y=(25960.0, 27000.0))
EST_CALLE_Y = (27350.0, 28382.0)               # calzada de la calle de la estación
EST_VER_N = (28382.0, 28732.0)
EST_PLAZA_X = (13500.0, 20500.0)               # explanada peatonal de la estación (corta la calle)
AFN_X = (8500.0, 40000.0)                      # Afuera Norte jugable
AFN_Y1 = 33000.0
GALPON_RED = dict(x=(20900.0, 23500.0), front_y=29400.0, back_y=33200.0, porton=(21650.0, 22750.0))
PLAYON = dict(x=(24000.0, 31176.0), y=(28732.0, 33000.0))
OBRA_AV_S = (22316.0, 22516.0)                 # tapial de obra que corta la avenida antes de las vías
OBRA_AV_N = (26016.0, 26216.0)
AV_N_END = 33000.0
AV_S_END = FONDO_Y[0] - 150.0

# Paso bajo nivel peatonal (E4, v5): escaleras paralelas a las vías dentro del corredor, túnel norte-sur bajo las
# vías pintado a franjas de colores (como los túneles de Caseros). Piso a Z -330, cielorraso = losa del suelo (-60).
PBN = dict(x_top=4200.0, x_bot=4740.0, x_e=5040.0, ys=(22760.0, 23000.0), yn=(25520.0, 25760.0), z=-330.0,
           zc=-60.0, gap_s=(3920.0, 4180.0), gap_n=(3920.0, 4180.0), wall=20.0, steps=19)
E4_ZONE = dict(c=(4050.0, 26560.0), ext=(520.0, 420.0))
PATIO_E4 = dict(x=(1800.0, 7400.0), y=(26016.0, 28400.0))      # playa ferroviaria cerrada donde sale el túnel

# manzanas: id -> (columna, fila)
MANZANAS = {'M00': (0, 0), 'M01': (0, 1), 'M10': (1, 0), 'M11': (1, 1), 'M20': (2, 0), 'M21': (2, 1),
            'M0S': (0, -1), 'M1S': (1, -1), 'M2S': (2, -1)}


def mz_bounds(mid):
    c, r = MANZANAS[mid]
    return XCOL[c][0], XCOL[c][1], YROW[r][0], YROW[r][1]


FRAMES = {'S': ((0.0, -1.0), (1.0, 0.0), -90.0), 'E': ((1.0, 0.0), (0.0, 1.0), 0.0),
          'N': ((0.0, 1.0), (-1.0, 0.0), 90.0), 'W': ((-1.0, 0.0), (0.0, -1.0), 180.0)}
SIDE_ORDER = ['S', 'E', 'N', 'W']
PREV_SIDE = {'S': 'W', 'E': 'S', 'N': 'E', 'W': 'N'}


def make_frame(o, n, yaw=None):
    u = (-n[1], n[0])
    if yaw is None:
        yaw = math.degrees(math.atan2(n[1], n[0]))
    return {'o': (float(o[0]), float(o[1])), 'n': n, 'u': u, 'yaw': yaw}


def side_frame(mid, side):
    x0, x1, y0, y1 = mz_bounds(mid)
    n, u, yaw = FRAMES[side]
    o = {'S': (x0, y0), 'E': (x1, y0), 'N': (x1, y1), 'W': (x0, y1)}[side]
    f = make_frame(o, n, yaw)
    f['mid'] = mid
    f['side'] = side
    return f


def fw(f, lx, ly, z=0.0):
    """Local (x, y, z) de un marco -> mundo."""
    return (f['o'][0] + lx * f['n'][0] + ly * f['u'][0], f['o'][1] + lx * f['n'][1] + ly * f['u'][1], z)


def fdir(f, dx, dy):
    return (dx * f['n'][0] + dy * f['u'][0], dx * f['n'][1] + dy * f['u'][1])


def yaw_of(d):
    return math.degrees(math.atan2(d[1], d[0]))


def side_width(mid, side):
    """Ancho de la vereda que da a ese lado (avenida 4,5 m)."""
    if side == 'E' and MANZANAS[mid][0] == 2:
        return VER_AV
    return VER


def street_of(mid, side):
    """Nombre de la calle a la que da un lado de manzana."""
    c, r = MANZANAS[mid]
    if side == 'S':
        return {-1: 'Fondo', 0: 'Sur', 1: 'Media'}[r]
    if side == 'N':
        return {-1: 'Sur', 0: 'Media', 1: 'Paralela'}[r]
    if side == 'W':
        return ['Oeste', 'C01', 'C12'][c]
    return ['C01', 'C12', 'Avenida'][c]


# =====================================================================================
# VARIANTES DE CASA (lo que construye barrio_kit; coordenadas locales de lote, W=866)
# entry = (tipo, y0, y1, z0, zt, x) puerta/portón robable o con reja; garage = (y0, y1) para el rebaje
# =====================================================================================
REVOQUES = ['MI_Revoque_Blanco', 'MI_Revoque_Gris', 'MI_Revoque_Rosa', 'MI_Revoque_VerdeAgua', 'MI_Revoque_Amarillo']
CARTELES = ['MI_Cartel_Verde', 'MI_Cartel_Rojo', 'MI_Cartel_Azul', 'MI_Cartel_Blanco']
# comercios inventados del atlas v4 (MI_Comercio_<nombre>); el primero es el slot por defecto de la esquina EL
COMERCIOS = ['AlmacenDonTito', 'Kiosco24hs', 'VerduleriaLaEsquina', 'FerreteriaElTornillo', 'PizzeriaLoDeCacho',
             'FarmaciaDelBarrio', 'CarniceriaLosHermanos', 'PanaderiaLaEspiga', 'PeluqueriaEstilo', 'RotiseriaDonaRosa',
             'LibreriaElLapiz', 'GomeriaElRayo', 'PolirrubroLosChicos', 'DespensaMary', 'BazarElSol']
COMERCIOS2 = ['ZapateriaPasoFirme', 'TiendaMarelu', 'ConexionCelulares', 'OpticaVisionClara', 'MerceriaElHilo',
              'DeportesLaCancha', 'PintureriaArcoiris', 'JugueteriaElTrompo', 'CotillonFiestita', 'HeladeriaLaNieve',
              'RegaleriaElMono', 'ForrajeriaLaHuella']

VARIANTS = {
    'A': dict(kind='casa', depth=860.0, entry=('door', 365.0, 455.0, 30.0, 240.0, 0.0), garage=(40.0, 310.0),
              wall='MI_Revoque_Blanco', colors=REVOQUES, h=428.0, power=(25.0, 840.0, 455.0),
              tel=[(2.0, 150.0, 395.0), (2.0, 700.0, 386.0)]),
    'A2': dict(kind='casa', depth=860.0, entry=('door', 365.0, 455.0, 30.0, 240.0, 0.0), garage=(40.0, 310.0),
               wall='MI_Revoque_Blanco', colors=REVOQUES, h=643.0, power=(25.0, 840.0, 455.0),
               tel=[(2.0, 150.0, 395.0)]),
    'B': dict(kind='casa', depth=1200.0, entry=('gate', 365.0, 475.0, 16.0, 118.0, 0.0), garage=None,
              wall='MI_Revoque_VerdeAgua', colors=REVOQUES, h=470.0, power=(5.0, 722.0, 368.0),
              tel=[(-298.0, 62.0, 338.0)]),
    'C': dict(kind='casa', depth=860.0, entry=('door', 385.0, 475.0, 30.0, 240.0, 0.0), garage=(35.0, 335.0),
              wall='MI_Revoque_Amarillo', colors=REVOQUES, h=720.0, power=(3.0, 822.0, 700.0),
              tel=[(2.0, 740.0, 680.0), (2.0, 380.0, 596.0)]),
    'D': dict(kind='chalet', depth=1350.0, entry=('gate', 45.0, 140.0, 16.0, 200.0, 0.0), garage=(340.0, 836.0),
              wall='MI_Revoque_Rosa', colors=['MI_Revoque_Rosa', 'MI_Revoque_Blanco', 'MI_Revoque_Amarillo',
                                              'MI_Revoque_Gris'], h=820.0, power=(3.0, 24.5, 388.0),
              tel=[(-448.0, 780.0, 572.0)]),
    'E': dict(kind='local', depth=860.0, entry=('door', 480.3, 570.3, 30.0, 240.0, 0.0), garage=None,
              wall='MI_Ladrillo', colors=['MI_Ladrillo', 'MI_Revoque_Gris', 'MI_Revoque_Blanco', 'MI_Revoque_Amarillo'],
              cartel='MI_Cartel_Verde', h=470.0, power=(27.0, 846.0, 488.0), tel=[(2.0, 120.0, 440.0)]),
    # v5: edificio de departamentos entre medianeras con local en PB (barrio_kit.build_edificio_f). La puerta
    # robable es la del local, igual que 'E'. h = altura total (cables, sombras).
    'F4': dict(kind='local', depth=860.0, entry=('door', 480.3, 570.3, 30.0, 240.0, 0.0), garage=None,
               wall='MI_Revoque_Gris', colors=['MI_Revoque_Gris', 'MI_Revoque_Blanco', 'MI_Ladrillo', 'MI_Revoque_Amarillo'],
               h=1720.0, power=(27.0, 846.0, 488.0), tel=[(2.0, 120.0, 440.0)], pisos=4),
    'F6': dict(kind='local', depth=860.0, entry=('door', 480.3, 570.3, 30.0, 240.0, 0.0), garage=None,
               wall='MI_Revoque_Gris', colors=['MI_Revoque_Gris', 'MI_Revoque_Blanco', 'MI_Ladrillo', 'MI_Revoque_Rosa'],
               h=2300.0, power=(27.0, 846.0, 488.0), tel=[(2.0, 120.0, 440.0)], pisos=6),
    'PH': dict(kind='ph', depth=860.0, entry=('door', 220.0, 310.0, 30.0, 240.0, 0.0), garage=None,
               wall='MI_Revoque_Blanco', colors=REVOQUES, h=420.0, power=(20.0, 600.0, 420.0),
               tel=[(2.0, 100.0, 380.0)], pasillo=(666.0, 866.0)),
}
SHALLOW = set(['A', 'A2', 'C', 'E', 'PH', 'F4', 'F6'])     # cabe en los slots 1 y 8 (no pisa al lote del lado vecino)
MIRRORABLE = ['A', 'A2', 'B', 'C', 'D', 'E', 'PH', 'F4', 'F6']
# Esquinas (cuadrado de 866 con ochava). La puerta de la esquina-local está en la ochava.
CORNERS = {
    'EL': dict(kind='kiosco', entry=('chamfer', 0.0, 0.0, 30.0, 240.0, 0.0), wall='MI_Revoque_Gris',
               colors=['MI_Revoque_Gris', 'MI_Revoque_Blanco', 'MI_Revoque_Amarillo', 'MI_Ladrillo'],
               cartel='MI_Cartel_Rojo', h=470.0, power=(10.0, 700.0, 430.0)),
    'EC': dict(kind='casa', entry=('door', 560.0, 650.0, 30.0, 240.0, 0.0), wall='MI_Revoque_Blanco',
               colors=REVOQUES, h=700.0, power=(10.0, 800.0, 640.0)),
}


def variant_meta(key):
    base = key[:-2] if key.endswith('_m') else key
    if base in VARIANTS:
        return base, VARIANTS[base], key.endswith('_m')
    return base, CORNERS[base], False


def mirror_range(r, W=LOT):
    return (W - r[1], W - r[0])


# =====================================================================================
# PLAN DE LOTES
# =====================================================================================
CHAR_WEIGHTS = {
    'M00': {'D': 5, 'B': 2, 'C': 2, 'A2': 1},
    'M01': {'A': 3, 'A2': 2, 'B': 2, 'C': 2, 'E': 0.6},
    'M10': {'A': 3, 'C': 2, 'B': 1, 'A2': 1.5, 'E': 0.4},
    'M20': {'A': 3, 'C': 2, 'A2': 2, 'B': 1, 'E': 0.8},
    'M21': {'A': 3, 'C': 2, 'A2': 2, 'B': 1, 'E': 0.8},
    # v5, fila sur: casas bajas con edificios de departamentos mezclados (como alrededor de la estación)
    'M0S': {'A': 3, 'A2': 2, 'C': 2, 'B': 1.5, 'F4': 0.8, 'E': 0.5},
    'M1S': {'A': 3, 'A2': 2, 'C': 2, 'B': 1, 'F4': 1.0, 'F6': 0.5, 'E': 0.6},
    'M2S': {'A': 3, 'A2': 2, 'C': 2, 'B': 1, 'F4': 0.8, 'E': 0.6},
}
# lados sobre la calle comercial: locales y edificios con PB comercial
COMERCIAL_WEIGHTS = {'E': 5, 'F4': 3, 'F6': 2, 'A2': 0.6}

# lotes especiales: (manzana, lado, slot) -> tipo
SPECIAL = {
    ('M00', 'S', 5): 'PH', ('M00', 'N', 4): 'PH_m',          # pasillo norte-sur de la 0,0
    ('M20', 'W', 4): 'PH', ('M20', 'E', 5): 'PH_m',          # pasillo este-oeste de la 2,0
    ('M21', 'S', 5): 'PH', ('M21', 'N', 4): 'PH_m',          # pasillo norte-sur de la 2,1
}
COMISARIA_SLOTS = ('M10', 'N', (3, 4, 5, 6))
TOWER = ('M21', 'N', (0, 1), 'E', (8,))
BALDIO = {('M01', 'W', 4), ('M01', 'W', 5), ('M01', 'E', 4), ('M01', 'E', 5)}
BALDIO_Y = (15588.0, 17320.0)
# pasillos de PH que cruzan la manzana: (manzana, eje, a0, a1) en mundo
PASILLOS = [('M00', 'NS', 6728.0, 6928.0), ('M20', 'EW', 6062.0, 6262.0), ('M21', 'NS', 27512.0, 27712.0)]
AVENUE_LOCAL_SIDES = {('M20', 'E'), ('M21', 'E')}


def _pick(rng, weights):
    tot = sum(weights.values())
    r = rng.uniform(0, tot)
    for k, w in sorted(weights.items()):
        r -= w
        if r <= 0:
            return k
    return sorted(weights.keys())[-1]


def lot_world_entry(lot):
    """Punto de la entrada (puerta) en mundo: (x, y, z), yaw hacia la calle, ancho, alto."""
    f = lot['frame']
    e = lot['entry']
    kind, y0, y1, z0, zt, ex = e
    if kind == 'chamfer':
        c = fw(f, -OCHAVA * 0.5 + 6.0, lot['y0'] + OCHAVA * 0.5 - 6.0, z0)
        d = fdir(f, 0.7071, -0.7071)
        return (c[0] + d[0] * 6.0, c[1] + d[1] * 6.0, z0), yaw_of(d), 100.0, zt - z0
    yc = lot['y0'] + 0.5 * (y0 + y1)
    p = fw(f, ex + (20.0 if kind == 'gate' else 6.0), yc, z0)     # el cerco bajo de B sobresale 6 cm
    return p, f['yaw'], (y1 - y0), zt - z0


def plan_lots(rng):
    lots = []
    for mid in sorted(MANZANAS.keys()):
        if mid == 'M11':
            continue
        weights = CHAR_WEIGHTS[mid]
        for side in SIDE_ORDER:
            f = side_frame(mid, side)
            prev_key = None
            for slot in range(0, 9):
                key3 = (mid, side, slot)
                lot = {'id': '%s_%s_%d' % (mid, side, slot), 'mid': mid, 'side': side, 'slot': slot, 'frame': f,
                       'y0': slot * LOT, 'W': LOT, 'swaps': {}, 'robbable': False, 'tier': None}
                # torre (esquina NE de la 2,1)
                if mid == TOWER[0] and ((side == TOWER[1] and slot in TOWER[2]) or (side == TOWER[3] and slot in TOWER[4])):
                    lot['kind'] = 'torre'
                    lots.append(lot)
                    continue
                if mid == COMISARIA_SLOTS[0] and side == COMISARIA_SLOTS[1] and slot in COMISARIA_SLOTS[2]:
                    lot['kind'] = 'comisaria'
                    lots.append(lot)
                    continue
                if key3 in BALDIO:
                    lot['kind'] = 'baldio'
                    lots.append(lot)
                    continue
                if slot == 0:
                    # esquina: kiosco/almacén en la mitad (las de la avenida, siempre)
                    on_av = (mid, side) in AVENUE_LOCAL_SIDES or (mid, PREV_SIDE[side]) in AVENUE_LOCAL_SIDES
                    on_com = (mid, side) in COMERCIAL_SIDES or (mid, PREV_SIDE[side]) in COMERCIAL_SIDES
                    is_local = on_av or rng.random() < (0.85 if on_com else 0.45)
                    v = 'EL' if is_local else 'EC'
                    lot['variant'] = v
                    lot['kind'] = 'esquina'
                    meta = CORNERS[v]
                    col = rng.choice(meta['colors'])
                    if col != meta['wall']:
                        lot['swaps'][meta['wall']] = col
                    if 'cartel' in meta:
                        c2 = rng.choice(CARTELES)
                        if c2 != meta['cartel']:
                            lot['swaps'][meta['cartel']] = c2
                    if v == 'EL':          # marquesina con nombre inventado (slot de barrio_edificios.COMERCIO_SLOT)
                        nm = COMERCIOS[(len([l for l in lots if l.get('variant') == 'EL']) * 7 + 3) % len(COMERCIOS)]
                        if nm != COMERCIOS[0]:
                            lot['swaps']['MI_Comercio_' + COMERCIOS[0]] = 'MI_Comercio_' + nm
                    lot['entry'] = meta['entry']
                    lot['garage'] = None
                    lot['h'] = meta['h']
                    lot['power'] = meta['power']
                    lot['tel'] = []
                    lot['depth'] = LOT
                    lots.append(lot)
                    prev_key = None
                    continue
                wts = COMERCIAL_WEIGHTS if (mid, side) in COMERCIAL_SIDES else weights
                if key3 in SPECIAL:
                    v = SPECIAL[key3]
                elif (mid, side) in AVENUE_LOCAL_SIDES:
                    v = 'E'
                else:
                    for _ in range(12):
                        v = _pick(rng, wts)
                        if slot in (1, 8) and v not in SHALLOW:
                            continue
                        if prev_key is not None and v == prev_key[0] and rng.random() < 0.7:
                            continue
                        break
                    if slot in (1, 8) and v not in SHALLOW:
                        v = 'A'
                base = v.replace('_m', '')
                if not v.endswith('_m') and key3 not in SPECIAL and base not in ('F4', 'F6') and rng.random() < 0.5:
                    v = base + '_m'
                _, meta, mir = variant_meta(v)
                lot['variant'] = v
                lot['kind'] = meta['kind']
                col = rng.choice(meta['colors'])
                if prev_key is not None and col == prev_key[1]:
                    col = rng.choice(meta['colors'])
                if col != meta['wall']:
                    lot['swaps'][meta['wall']] = col
                if 'cartel' in meta:
                    c2 = rng.choice(CARTELES)
                    if c2 != meta['cartel']:
                        lot['swaps'][meta['cartel']] = c2
                if 'pisos' in meta:        # edificio F: el local de PB lleva marquesina con nombre (slot de EL)
                    pool = COMERCIOS2 + COMERCIOS[1:]          # v5: la calle comercial usa sobre todo los nuevos
                    nm = pool[(len([l for l in lots if l.get('variant', '')[:1] in ('F', 'E')]) * 5 + 1) % len(pool)]
                    if nm != COMERCIOS[0]:
                        lot['swaps']['MI_Comercio_' + COMERCIOS[0]] = 'MI_Comercio_' + nm
                e = meta['entry']
                if mir:
                    a, b = mirror_range((e[1], e[2]))
                    e = (e[0], a, b, e[3], e[4], e[5])
                lot['entry'] = e
                g = meta.get('garage')
                lot['garage'] = mirror_range(g) if (g and mir) else g
                p = meta['power']
                lot['power'] = (p[0], LOT - p[1], p[2]) if mir else p
                lot['tel'] = [(t[0], LOT - t[1], t[2]) if mir else t for t in meta.get('tel', [])]
                lot['h'] = meta['h']
                lot['depth'] = meta['depth']
                if 'pasillo' in meta:
                    lot['pasillo'] = mirror_range(meta['pasillo']) if mir else meta['pasillo']
                lots.append(lot)
                prev_key = (base, col)
    return lots


# =====================================================================================
# PUNTOS DE ROBO (cobertura < 40 m en todo el barrio jugable)
# =====================================================================================
PH_WALL = 15.0         # espesor de los tapiales del pasillo de PH


def pasillo_clear(mid):
    """Intervalo libre (mundo) del pasillo de PH de la manzana, medido sobre el eje perpendicular al pasillo.
    Sale de la geometría del lote PH sin espejar: casa en y<666, pasillo 666..866 con tapial de 15 cm del
    lado del vecino (y 851..866). El PH_m del otro lado de la manzana cae exactamente en el mismo intervalo."""
    p0, p1 = VARIANTS['PH']['pasillo']
    for key, v in sorted(SPECIAL.items()):
        if key[0] == mid and v == 'PH':
            _, side, slot = key
            f = side_frame(mid, side)
            a = fw(f, 0.0, slot * LOT + p0)
            b = fw(f, 0.0, slot * LOT + p1 - PH_WALL)
            ax = 0 if abs(f['u'][0]) > 0.5 else 1
            return (min(a[ax], b[ax]), max(a[ax], b[ax]))
    return None


def pasillo_doors():
    """Puertas de PH a lo largo de los pasillos (2-3 por pasillo, robables siempre).
    El punto de robo queda 6 cm delante de la puerta, del lado del pasillo, mirando hacia el pasillo
    (side -1: muro en c0, la puerta mira a +eje; side +1: muro en c1, mira a -eje)."""
    out = []
    for (mid, ax, a0, a1) in PASILLOS:
        x0, x1, y0, y1 = mz_bounds(mid)
        c0, c1 = pasillo_clear(mid) or (a0, a1)
        if ax == 'NS':
            for k, (t, s) in enumerate(((0.33, -1), (0.52, 1), (0.71, -1))):
                y = y0 + (y1 - y0) * t
                wall = c0 if s < 0 else c1
                out.append({'pos': (wall - s * 6.0, y, 30.0), 'yaw': 0.0 if s < 0 else 180.0, 'w': 90.0, 'h': 210.0,
                            'id': 'PH_%s_%d' % (mid, k), 'mid': mid, 'kind': 'ph_int', 'wall': wall, 'side': s,
                            'along': y, 'axis': ax})
        else:
            for k, (t, s) in enumerate(((0.35, -1), (0.62, 1))):
                x = x0 + (x1 - x0) * t
                wall = c0 if s < 0 else c1
                out.append({'pos': (x, wall - s * 6.0, 30.0), 'yaw': 90.0 if s < 0 else -90.0, 'w': 90.0, 'h': 210.0,
                            'id': 'PH_%s_%d' % (mid, k), 'mid': mid, 'kind': 'ph_int', 'wall': wall, 'side': s,
                            'along': x, 'axis': ax})
    return out


KIOSCO_DIARIOS = (15200.0, 14300.0)      # cuadrante SO de la plaza (frente a la comisaría)
KIOSCO_PLAZA = (15800.0, 19500.0)        # kiosco de bebidas, lado norte de la plaza (cubre la calle de las vías)
CASILLA_BALDIO = (5600.0, 16700.0)       # casilla precaria en el baldío (robo chico)
PUESTO_VIAS = (17200.0, 22470.0)         # puesto de diarios/golosinas contra el alambrado de las vías


def walk_samples(step=400.0):
    """Puntos caminables del barrio (calles, veredas, plaza, baldío, pasillos)."""
    pts = []
    x = 0.0
    while x <= AV_CANTERO[0]:
        y = FONDO_Y[0]
        while y <= VIAS_Y0:
            inside = None
            for mid in MANZANAS:
                x0, x1, y0, y1 = mz_bounds(mid)
                if x0 < x < x1 and y0 < y < y1:
                    inside = mid
            ok = inside is None or inside == 'M11'
            if inside == 'M01' and BALDIO_Y[0] < y < BALDIO_Y[1]:
                ok = True
            pts.append((x, y)) if ok else None
            y += step
        x += step
    return pts


# =====================================================================================
# LÍNEAS DE VISIÓN: validador en Python puro (rayos 2D por el eje de cada calle)
# =====================================================================================
SIGHT_MAX = 7000.0        # ningún tramo de calle con más de 70 m libres
SIGHT_Z = 160.0           # altura del rayo: solo cuentan las huellas con techo >= 1,6 m

# huellas de los vehículos: (medio largo, medio ancho, alto) en el marco del auto (+X adelante)
CAR_DIMS = {'sedan': (228.0, 88.0, 140.0), 'hatch': (198.0, 88.0, 140.0), 'utilitario': (213.0, 88.0, 184.0),
            'pickup': (263.0, 88.0, 156.0), 'patrullero': (228.0, 88.0, 159.0)}
# huellas de los cortes en el marco del actor (+X a lo largo de la calle, +Y hacia la vereda): x0, x1, y0, y1, alto.
# Los viejos (build_corte, camión, colectivo) tienen el origen en el carril de estacionamiento; los semicortes
# (barrio_geo.build_semicorte) tienen el origen en la cara del cordón y ocupan la calzada hacia -Y.
CUT_FOOT = {'obra': (-455.0, 455.0, -186.0, 125.0, 230.0), 'camion': (-432.0, 412.0, -125.0, 125.0, 360.0),
            'volquete': (-230.0, 230.0, -133.0, 97.0, 126.0), 'puesto': (-112.0, 192.0, -62.0, 62.0, 125.0),
            'colectivo': (-606.0, 606.0, -128.0, 128.0, 308.0),
            # semicortes (cruzan el eje y dejan >= 3,8 m libres del otro lado)
            'zanja': (-360.0, 360.0, -640.0, -140.0, 230.0), 'zanja_b': (-300.0, 300.0, -640.0, -140.0, 225.0),
            'mudanza': (-440.0, 420.0, -540.0, -140.0, 360.0), 'reparto': (-440.0, 420.0, -540.0, -140.0, 360.0),
            'arbol_caido': (-330.0, 330.0, -720.0, 40.0, 240.0)}
SEMICORTES = ('zanja', 'zanja_b', 'mudanza', 'reparto', 'arbol_caido')


def foot_poly(pos, yaw, x0, x1, y0, y1):
    """Rectángulo local (x0..x1, y0..y1) de un actor en pos/yaw -> polígono en mundo."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return [(pos[0] + x * c - y * s, pos[1] + x * s + y * c) for (x, y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]


def sight_obstacles(plan, z=SIGHT_Z):
    """Huellas 2D (polígonos y círculos) de todo lo que corta un rayo a la altura z."""
    obs = []

    def rect(name, pos, yaw, x0, x1, y0, y1, top):
        if top >= z:
            obs.append({'name': name, 'poly': foot_poly(pos, yaw, x0, x1, y0, y1)})

    def circ(name, p, r, top):
        if top >= z:
            obs.append({'name': name, 'circ': (p[0], p[1], r)})
    for q in plan['cars']:
        hl, hw, top = CAR_DIMS.get(q['type'], CAR_DIMS['sedan'])
        rect('auto_' + q['type'], q['pos'], q['yaw'], -hl, hl, -hw, hw, top)
    for q in plan['cuts']:
        x0, x1, y0, y1, top = CUT_FOOT.get(q['kind'], CUT_FOOT['obra'])
        rect('corte_' + q['kind'], q['pos'], q['yaw'], x0, x1, y0, y1, top)
    for t in plan['furn']['trees']:
        circ('arbol', t['pos'], 18.0, 400.0)
    for p in plan['furn']['poles'] + plan['border_poles']:
        circ('poste', p['pos'], 14.0, 800.0)
    av = plan['avenue']
    for p in av['cols']:
        circ('columna_av', p, 14.0, 960.0)
    for q in av['paradas']:
        rect('parada', q['pos'], q['yaw'], -70.0, 46.0, -170.0, 170.0, 263.0)     # vidrio opaco
    for q in av['semaforos']:
        circ('semaforo', q['pos'], 8.0, 400.0)
    for (kind, pos, yaw) in SALIDA_COVERS:
        x0, x1, y0, y1, top = COVER_FOOT[kind]
        rect('cobertura_' + kind, pos, yaw, x0, x1, y0, y1, top)
    for (x, y, ayaw) in salida_totems():
        circ('totem_salida', (x, y), 20.0, 360.0)
    return obs


def _line_interval(o, axis, c):
    """Intervalo (a lo largo del rayo) donde la recta transversal = c atraviesa la huella o."""
    if 'circ' in o:
        cx, cy, r = o['circ']
        ca, cc = (cx, cy) if axis == 'EW' else (cy, cx)
        d = abs(cc - c)
        if d >= r:
            return None
        h = math.sqrt(r * r - d * d)
        return (ca - h, ca + h)
    pts = []
    poly = o['poly']
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        if axis == 'EW':
            pa, pc, qa, qc = p[0], p[1], q[0], q[1]
        else:
            pa, pc, qa, qc = p[1], p[0], q[1], q[0]
        if (pc - c) * (qc - c) <= 0.0:
            if abs(qc - pc) < 1e-6:
                pts += [pa, qa]
            else:
                pts.append(pa + (qa - pa) * (c - pc) / (qc - pc))
    if not pts:
        return None
    return (min(pts), max(pts))


def sight_rays():
    """Rayos a validar: (calle, nombre del rayo, eje, coordenada transversal, a0, a1, obligatorio).
    Por cada calle: el eje (obligatorio) y los centros de los dos carriles (informativos)."""
    out = []
    for (name, axis, (c0, c1), (a0, a1), _x) in STREETS:
        cm = 0.5 * (c0 + c1)
        q = 0.25 * (c1 - c0)
        out.append((name, 'eje', axis, cm, a0, a1, True))
        out.append((name, 'carril-', axis, cm - q, a0, a1, False))
        out.append((name, 'carril+', axis, cm + q, a0, a1, False))
    return out


def validate_sightlines(plan, max_free=SIGHT_MAX, z=SIGHT_Z):
    """Tira un rayo 2D a la altura z por el eje (y los carriles) de cada calle contra las huellas de autos,
    cortes, árboles, postes, paradas y coberturas. Devuelve (resultados, errores): cada resultado tiene el
    tramo libre más largo y dónde está; error si un rayo obligatorio tiene más de max_free libres."""
    obs = sight_obstacles(plan, z)
    res, errs = [], []
    for (street, ray, axis, c, a0, a1, req) in sight_rays():
        iv = []
        for o in obs:
            r = _line_interval(o, axis, c)
            if r is not None and r[1] > a0 and r[0] < a1:
                iv.append((max(a0, r[0]), min(a1, r[1])))
        iv.sort()
        best, at, cur = 0.0, (a0, a0), a0
        for (s, e) in iv:
            if s > cur and s - cur > best:
                best, at = s - cur, (cur, s)
            cur = max(cur, e)
        if a1 - cur > best:
            best, at = a1 - cur, (cur, a1)
        ok = best <= max_free
        item = {'street': street, 'ray': ray, 'axis': axis, 'c': c, 'max': best, 'at': at, 'ok': ok,
                'required': req, 'hits': len(iv)}
        res.append(item)
        if req and not ok:
            p0 = (at[0], c) if axis == 'EW' else (c, at[0])
            p1 = (at[1], c) if axis == 'EW' else (c, at[1])
            errs.append('Calle %s (%s): %.1f m libres entre (%.0f, %.0f) y (%.0f, %.0f) (máximo %.0f m)' %
                        (street, ray, best / 100.0, p0[0], p0[1], p1[0], p1[1], max_free / 100.0))
    return res, errs


def choose_loot(rng, lots, target=86, radius=4000.0):
    cands = []
    for lot in lots:
        if lot.get('entry') is None:
            continue
        p, yaw, w, h = lot_world_entry(lot)
        cands.append({'pos': p, 'yaw': yaw, 'w': w, 'h': h, 'lot': lot, 'id': lot['id'], 'mid': lot['mid'],
                      'kind': lot['kind']})
    fixed = pasillo_doors()
    fixed.append({'pos': (KIOSCO_DIARIOS[0], KIOSCO_DIARIOS[1] - 85.0, Z_VER), 'yaw': -90.0, 'w': 80.0, 'h': 190.0,
                  'id': 'KioscoDiarios', 'mid': 'M11', 'kind': 'kiosco_diarios'})
    fixed.append({'pos': (KIOSCO_PLAZA[0], KIOSCO_PLAZA[1] - 130.0, Z_VER), 'yaw': -90.0, 'w': 90.0, 'h': 200.0,
                  'id': 'KioscoPlaza', 'mid': 'M11', 'kind': 'kiosco_diarios'})
    fixed.append({'pos': (CASILLA_BALDIO[0], CASILLA_BALDIO[1] - 160.0, 20.0), 'yaw': -90.0, 'w': 80.0, 'h': 190.0,
                  'id': 'CasillaBaldio', 'mid': 'M01', 'kind': 'kiosco_diarios'})
    fixed.append({'pos': (PUESTO_VIAS[0], PUESTO_VIAS[1] - 100.0, Z_VER), 'yaw': -90.0, 'w': 90.0, 'h': 200.0,
                  'id': 'PuestoVias', 'mid': 'M11', 'kind': 'kiosco_diarios'})
    chosen = list(fixed)
    pts = walk_samples()

    def d2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
    r2 = radius * radius
    cap = {'M10': 5}
    count = {}
    for c in chosen:
        count[c['mid']] = count.get(c['mid'], 0) + 1

    def covered_set(sel):
        cov = set()
        for i, p in enumerate(pts):
            for c in sel:
                if d2(p, c['pos']) <= r2:
                    cov.add(i)
                    break
        return cov
    cov = covered_set(chosen)
    pool = [c for c in cands]
    rng.shuffle(pool)
    # 1) cobertura voraz
    while len(cov) < len(pts) and len(chosen) < target:
        best, best_gain = None, 0
        for c in pool:
            if c in chosen or count.get(c['mid'], 0) >= cap.get(c['mid'], 99):
                continue
            g = 0
            for i, p in enumerate(pts):
                if i not in cov and d2(p, c['pos']) <= r2:
                    g += 1
            w = 1.25 if c['kind'] in ('local', 'kiosco', 'chalet') else 1.0
            if g * w > best_gain:
                best, best_gain = c, g * w
        if best is None:
            break
        chosen.append(best)
        count[best['mid']] = count.get(best['mid'], 0) + 1
        for i, p in enumerate(pts):
            if d2(p, best['pos']) <= r2:
                cov.add(i)
    # 2) completar hasta target maximizando la distancia al robo más cercano (reparto parejo)
    while len(chosen) < target:
        best, best_d = None, -1.0
        for c in pool:
            if c in chosen or count.get(c['mid'], 0) >= cap.get(c['mid'], 99):
                continue
            dmin = min(d2(c['pos'], s['pos']) for s in chosen)
            if c['kind'] in ('local', 'kiosco'):
                dmin *= 1.3
            if dmin > best_d:
                best, best_d = c, dmin
        if best is None:
            break
        chosen.append(best)
        count[best['mid']] = count.get(best['mid'], 0) + 1
    uncovered = [pts[i] for i in range(len(pts)) if i not in covered_set(chosen)]
    for c in chosen:
        if 'lot' in c:
            c['lot']['robbable'] = True
        k = c['kind']
        if c['mid'] == 'M00' and k in ('chalet', 'casa', 'esquina', 'ph'):
            c['tier'] = 'High'
        elif k in ('local', 'kiosco', 'kiosco_diarios') or (k == 'esquina' and c['lot']['variant'] == 'EL'):
            c['tier'] = 'Low'
        else:
            c['tier'] = None       # aleatorio
    return chosen, uncovered


# =====================================================================================
# VEREDAS: tramos por lado de manzana y bordes
# =====================================================================================
def vereda_specs(rng, lots):
    """Una vereda por lado de manzana (incluye su esquina de inicio y la ochava) + bordes del barrio."""
    by_side = {}
    for lot in lots:
        by_side.setdefault((lot['mid'], lot['side']), []).append(lot)
    out = []
    for mid in sorted(MANZANAS.keys()):
        for side in SIDE_ORDER:
            f = side_frame(mid, side)
            w = side_width(mid, side)
            wprev = side_width(mid, PREV_SIDE[side])
            segs = []
            ramps = []
            for slot in range(0, 10):
                y0 = slot * LOT
                y1 = y0 + LOT
                mat = rng.choice(['MI_Baldosa'] * 6 + ['MI_Hormigon'] * 2 + ['MI_PiedraLaja'])
                if mid == 'M11':
                    mat = 'MI_Baldosa'
                segs.append((y0, y1, mat, rng.choice([0.0, 0.0, 0.4, -0.4, 0.8, 1.1])))
            for lot in by_side.get((mid, side), []):
                g = lot.get('garage')
                if g:
                    ramps.append((lot['y0'] + g[0], lot['y0'] + g[1]))
            out.append({'name': 'Vereda_%s_%s' % (mid, side), 'frame': f, 'L': MZ, 'w': w, 'wprev': wprev,
                        'corner': True, 'segs': segs, 'ramps': ramps, 'mid': mid, 'side': side,
                        'plaza': mid == 'M11'})
    # bordes (sin esquinas; el frente es un tapial / galpón / alambrado)
    def border(name, o, n, L, w=VER, cut=None):
        f = make_frame(o, n)
        segs = []
        y = 0.0
        while y < L - 1.0:
            y1 = min(L, y + rng.uniform(600.0, 1400.0))
            segs.append((y, y1, rng.choice(['MI_Hormigon', 'MI_Hormigon', 'MI_Baldosa']), rng.choice([0.0, 0.5, -0.3])))
            y = y1
        return {'name': name, 'frame': f, 'L': L, 'w': w, 'wprev': w, 'corner': False, 'segs': segs, 'ramps': [],
                'mid': None, 'side': None, 'plaza': False, 'cut': cut or []}
    out.append(border('Vereda_Club', (0.0, FONDO_Y[0] + 350.0), (1.0, 0.0), VIAS_Y0 - FONDO_Y[0] - 350.0))
    out.append(border('Vereda_Galpones', (AV_X0, FONDO_Y[0]), (0.0, 1.0), AV_X0))
    # vereda norte de la calle paralela: cortada por E1 (calzada del paso a nivel)
    out.append(border('Vereda_Vias_O', (0.0, VIAS_Y0), (0.0, -1.0), E1_X[0] + VER))
    out.append(border('Vereda_Vias_E', (E1_X[1] - VER, VIAS_Y0), (0.0, -1.0), AV_X0 - (E1_X[1] - VER)))
    out.append(border('Vereda_AvEste', (AV_X1, OBRA_AV_S[0]), (-1.0, 0.0), OBRA_AV_S[0] - AV_S_END - 8.0, VER_AV))
    return out


# =====================================================================================
# CALZADAS
# =====================================================================================
def street_segments():
    """Tramos de calzada (rectángulos en mundo) con su eje: ('EW'|'NS', x0, x1, y0, y1, nombre)."""
    segs = []
    ew = [('Fondo', FONDO_Y), ('Sur', (0.0, CALLE)), ('Media', (YROW[0][1], YROW[1][0])),
          ('Paralela', (YROW[1][1], VIAS_Y0))]
    ns = [('Oeste', (0.0, CALLE)), ('C01', (XCOL[0][1], XCOL[1][0])), ('C12', (XCOL[1][1], XCOL[2][0]))]
    for (name, (ya, yb)) in ew:
        cy0, cy1 = ya + VER, yb - VER
        for ci, (x0, x1) in enumerate(XCOL):
            xe = x1 + (VER_AV if ci == 2 else VER)
            segs.append(('EW', x0 - VER, xe, cy0, cy1, '%s_%d' % (name, ci)))
    for (name, (xa, xb)) in ns:
        cx0, cx1 = xa + VER, xb - VER
        for ri in ROWS:
            y0, y1 = YROW[ri]
            segs.append(('NS', cx0, cx1, y0 - VER, y1 + VER, '%s_%s' % (name, 'S' if ri < 0 else ri)))
    inter = []
    for (name, (xa, xb)) in ns:
        for (ename, (ya, yb)) in ew:
            inter.append((xa + VER, xb - VER, ya + VER, yb - VER, 'Cruce_%s_%s' % (name, ename)))
    # E1: la calle C01 sigue al norte hasta la calle de la estación (el paso a nivel va encima)
    e1 = ('NS', E1_X[0] + VER, E1_X[1] - VER, VIAS_Y0 - VER, VIAS_Y0, 'C01_Vias')
    segs.append(e1)
    return segs, inter


# =====================================================================================
# POSTES, LUMINARIAS, ÁRBOLES, CANASTOS, AUTOS, CORTES
# =====================================================================================
# Postes: local +x hacia la calle. Cabeza de la luminaria a ARM_X en x y LUM_Z de alto.
ARM_X = 190.0
LUM_Z = 805.0
AV_ARM_X = 230.0
AV_LUM_Z = 960.0
FAROLA_Z = 400.0


def lum_point(loc, yaw, arm=ARM_X, z=LUM_Z):
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    return (loc[0] + arm * c, loc[1] + arm * s, z)


def _free(y, used, gap):
    return all(abs(y - u) >= gap for u in used)


def plan_street_furniture(rng, lots, verdes):
    """Postes, árboles, canastos por lado de manzana; luminarias en los postes con brazo.
    Devuelve dict con listas en mundo."""
    out = {'poles': [], 'trees': [], 'canastos': [], 'lums': [], 'pits': {}, 'strips': {}}
    by_side = {}
    for lot in lots:
        by_side.setdefault((lot['mid'], lot['side']), []).append(lot)
    # lado con la línea de energía (P) por calle: el otro lado tiene postes simples de telefonía
    p_side = {'Fondo': 'S', 'Sur': 'S', 'Media': 'N', 'Paralela': 'N', 'Oeste': 'W', 'C01': 'E', 'C12': 'W',
              'Avenida': 'E'}
    for v in verdes:
        mid, side = v['mid'], v['side']
        if mid is None:
            continue
        f = v['frame']
        street = street_of(mid, side)
        # el lado P mira a la calle desde la manzana cuyo lado coincide con p_side
        is_p = (side == p_side[street]) or street in ('Sur', 'Paralela', 'Oeste', 'Fondo') or street == 'Avenida'
        avoid = []
        for lot in by_side.get((mid, side), []):
            g = lot.get('garage')
            if g:
                avoid.append((lot['y0'] + g[0] - 40.0, lot['y0'] + g[1] + 40.0))
            e = lot.get('entry')
            if e and e[0] != 'chamfer':
                avoid.append((lot['y0'] + e[1] - 30.0, lot['y0'] + e[2] + 30.0))

        def blocked(y):
            return any(a <= y <= b for (a, b) in avoid) or y < 450.0 or y > MZ - 450.0
        pole_ys = []
        spacing = 2900.0 if street != 'Avenida' else 2500.0
        y = (500.0 if is_p else 500.0 + spacing * 0.5)
        while y < MZ - 300.0:
            yy = y
            for k in range(12):
                cand = y + (k // 2 + 1) * 60.0 * (1 if k % 2 == 0 else -1) if k else y
                if not blocked(cand):
                    yy = cand
                    break
            pole_ys.append(yy)
            y += spacing
        wood = rng.random() < 0.25
        for yy in pole_ys:
            kind = 'lum' if (is_p or mid == 'M11') else 'simple'
            mat = 'madera' if (rng.random() < 0.25) else 'hormigon'
            p = fw(f, v['w'] - 30.0, yy)
            tilt = (rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2))
            pole = {'pos': p, 'yaw': f['yaw'], 'kind': kind, 'mat': mat, 'tilt': tilt, 'street': street,
                    'mid': mid, 'side': side, 'ly': yy}
            out['poles'].append(pole)
            if kind == 'lum':
                out['lums'].append({'pos': lum_point(p, f['yaw']), 'street': street})
        # árboles: uno por lote en su cazuela, lejos de puertas, garajes y postes
        pits = []
        strips = []
        for slot in range(1, 9):
            if mid == 'M11':
                continue
            y0 = slot * LOT
            if rng.random() < 0.1:
                continue
            for cand in (0.5, 0.3, 0.72, 0.15, 0.88):
                yy = y0 + LOT * cand + rng.uniform(-40.0, 40.0)
                if not blocked(yy) and _free(yy, pole_ys, 160.0):
                    pits.append(yy)
                    break
        if mid == 'M11':
            yy = 900.0
            while yy < MZ - 800.0:
                if _free(yy, pole_ys, 200.0):
                    pits.append(yy)
                yy += 1100.0
        for yy in pits:
            # v5 (fotos de julio alrededor de la estación): plátanos podados y pelados en la mayoría de las veredas,
            # mezclados con fresnos y paraísos que todavía tienen hoja (y la plaza siempre verde).
            r = rng.random()
            kind = 'platano' if r < 0.7 else ('fresno' if r < 0.88 else 'paraiso')
            rp = rng.random()                       # siempre se consume (el resto del plan no depende de la mezcla)
            pelado = kind == 'platano' and rp < 0.9
            if mid == 'M11':
                kind, pelado = rng.choice(['fresno', 'platano']), False
            out['trees'].append({'pos': fw(f, v['w'] - 85.0, yy), 'yaw': f['yaw'] + rng.uniform(-25, 25),
                                 'kind': kind, 'pelado': pelado, 'seed': rng.randint(0, 2)})
        # franjas de tierra/pasto junto al cordón
        y = 300.0
        while y < MZ - 300.0:
            L = rng.uniform(80.0, 120.0)
            if rng.random() < 0.18 and not blocked(y) and _free(y, pits, 120.0) and _free(y, pole_ys, 80.0):
                strips.append((y, y + L, rng.choice(['MI_Tierra', 'MI_Pasto'])))
            y += L + rng.uniform(150.0, 600.0)
        out['pits'][v['name']] = pits
        out['strips'][v['name']] = strips
        # canastos (con bolsas a veces), cerca del cordón, frente a ~35% de los lotes
        for slot in range(1, 9):
            if mid == 'M11' or rng.random() > 0.35:
                continue
            for cand in (0.2, 0.8, 0.5):
                yy = slot * LOT + LOT * cand
                if not blocked(yy) and _free(yy, pits, 120.0) and _free(yy, pole_ys, 100.0):
                    out['canastos'].append({'pos': fw(f, v['w'] - 70.0, yy), 'yaw': f['yaw'] + rng.uniform(-6, 6),
                                            'bolsas': rng.random() < 0.65})
                    break
    return out


ARCO_Y = (310.0, 1422.0)          # columnas de los arcos de la calle comercial: al borde de cada vereda (cordón)


def plan_arcos(furn):
    """Arcos decorativos con guirnaldas que cruzan la calle comercial ('Sur') cada ~28 m, fuera de los cruces
    y sin pisar postes ni árboles de vereda. Devuelve [(x, y_centro, ancho)]."""
    busy = [p['pos'][0] for p in furn['poles'] if p.get('street') == 'Sur'] + \
        [t['pos'][0] for t in furn['trees'] if -100.0 < t['pos'][1] < 1832.0]
    out = []
    for (x0, x1) in XCOL:
        x = x0 + 1300.0
        while x < x1 - 1100.0:
            xx = x
            for k in range(12):
                cand = x + (k // 2 + 1) * 70.0 * (1 if k % 2 == 0 else -1) if k else x
                if all(abs(cand - b) > 110.0 for b in busy):
                    xx = cand
                    break
            out.append((xx, 0.5 * (ARCO_Y[0] + ARCO_Y[1]), ARCO_Y[1] - ARCO_Y[0]))
            x += 2850.0
    return out


def plan_border_poles(rng):
    """Postes en los bordes y Afuera (luminarias incluidas)."""
    poles, lums = [], []

    def line(p0, p1, yaw, step, kind='lum', mat=None, arm=ARM_X):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        n = max(1, int(L // step))
        for k in range(n + 1):
            t = k / float(n)
            p = (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, 0.0)
            m = mat or ('madera' if rng.random() < 0.25 else 'hormigon')
            poles.append({'pos': p, 'yaw': yaw, 'kind': kind, 'mat': m,
                          'tilt': (rng.uniform(-1, 1), rng.uniform(-1, 1)), 'street': 'borde'})
            if kind == 'lum':
                lums.append({'pos': lum_point(p, yaw, arm), 'street': 'borde'})
    # calle de la estación (Afuera Norte): vereda sur (franja) y norte
    line((AFN_X[0] + 600.0, EST_CALLE_Y[0] - 40.0), (EST_PLAZA_X[0] - 300.0, EST_CALLE_Y[0] - 40.0), 90.0, 2800.0)
    line((EST_PLAZA_X[1] + 300.0, EST_CALLE_Y[0] - 40.0), (AV_X0 - 400.0, EST_CALLE_Y[0] - 40.0), 90.0, 2800.0)
    line((AFN_X[0] + 2000.0, EST_VER_N[0] + 40.0), (EST_PLAZA_X[0] - 500.0, EST_VER_N[0] + 40.0), -90.0, 2800.0, 'simple')
    line((EST_PLAZA_X[1] + 1200.0, EST_VER_N[0] + 40.0), (AV_X0 - 600.0, EST_VER_N[0] + 40.0), -90.0, 2800.0, 'simple')
    return poles, lums


# =====================================================================================
# CALLES, SALIDAS Y COBERTURAS (lo usan los cortes, el estacionamiento y el validador)
# =====================================================================================
def _mk_streets():
    """(nombre, eje, (c0, c1) calzada en la coordenada transversal, (a0, a1) tramo a validar, cruces a lo largo)."""
    out = []
    ew_cross = [(0.0, CALLE), (XCOL[0][1], XCOL[1][0]), (XCOL[1][1], XCOL[2][0]), (AV_X0, AV_X1)]
    ns_cross = [FONDO_Y, (0.0, CALLE), (YROW[0][1], YROW[1][0]), (YROW[1][1], VIAS_Y0)]
    for (name, (ya, yb)) in (('Fondo', FONDO_Y), ('Sur', (0.0, CALLE)), ('Media', (YROW[0][1], YROW[1][0])),
                             ('Paralela', (YROW[1][1], VIAS_Y0))):
        out.append((name, 'EW', (ya + VER, yb - VER), (0.0, AV_X1), ew_cross))
    for (name, (xa, xb), a1) in (('Oeste', (0.0, CALLE), FENCE_S), ('C01', (XCOL[0][1], XCOL[1][0]), VIAS_Y0),
                                 ('C12', (XCOL[1][1], XCOL[2][0]), FENCE_S)):
        out.append((name, 'NS', (xa + VER, xb - VER), (FONDO_Y[0], a1), ns_cross))
    a_av = (AV_S_END + 8.0, OBRA_AV_S[0])
    out.append(('Av_O', 'NS', (AV_CALZ[0], AV_CANTERO[0]), a_av, ns_cross))
    out.append(('Av_E', 'NS', (AV_CANTERO[1], AV_CALZ[1]), a_av, ns_cross))
    return out


STREETS = _mk_streets()
# yaw del marco de un corte apoyado en el cordón (lado -1: sur/oeste; +1: norte/este): +X a lo largo, +Y a la vereda
YAW_CURB = {('EW', -1): 180.0, ('EW', 1): 0.0, ('NS', -1): 90.0, ('NS', 1): -90.0}


def street_def(name):
    for s in STREETS:
        if s[0] == name:
            return s
    return None


def street_pt(axis, along, c):
    return (along, c, 0.0) if axis == 'EW' else (c, along, 0.0)


def curb_c(name, side):
    s = street_def(name)
    return s[2][0] if side < 0 else s[2][1]


def _in_any(v, ivs, half=0.0):
    return any(v + half > a and v - half < b for (a, b) in ivs)


# Coberturas en la aproximación a las salidas (kiosco, garita) y el remís junto a E1: (tipo, (x, y), yaw del frente)
COVER_FOOT = {'kiosco': (-75.0, 75.0, -110.0, 110.0, 250.0),     # +X = frente (150 de fondo, 220 de ancho)
              'garita': (-80.0, 80.0, -80.0, 80.0, 262.0)}
SALIDA_COVERS = [('kiosco', (9600.0, 22340.0), -90.0),       # E1, vereda de las vías (oeste)
                 ('garita', (12820.0, 22345.0), -90.0),      # E1, vereda de las vías (este)
                 ('kiosco', (24250.0, 22340.0), -90.0),      # E2, junto al bolsillo de la escalera sur
                 ('garita', (31400.0, 12820.0), 0.0)]        # E3, vereda del barrio de la avenida
REMIS = dict(pole=(8450.0, 21070.0), cars=[(7620.0, 0.0), (8240.0, 0.0)])     # parada de remís (Paralela)
# cartel SALIDA (barrio_props.build_cartel_salida, el mismo en las tres): del lado barrio, mirando al barrio
SALIDA_CARTELES = [(10470.0, 22250.0, -90.0), (26100.0, 22300.0, -90.0), (31250.0, 10560.0, 180.0),
                   (PBN['gap_s'][1] + 260.0, 22250.0, -90.0)]


def salida_totems():
    """Marca diegética ÚNICA de las tres salidas: tótem verde con luz verde y flecha hacia Afuera.
    Dos por boca (lado barrio y lado Afuera). (x, y, yaw de la flecha)."""
    return [(10560.0, 22420.0, 90.0), (11956.0, 22420.0, 90.0),            # E1 lado barrio
            (10567.0, 26120.0, 90.0), (11949.0, 26120.0, 90.0),            # E1 lado Afuera
            (25200.0, 22420.0, 90.0), (27040.0, 22420.0, 90.0),            # E2 escalera sur
            (25170.0, 25985.0, 180.0), (25170.0, 26335.0, 180.0),          # E2 pie de la escalera norte
            (31470.0, 10290.0, 0.0), (31470.0, 12226.0, 0.0),              # E3 lado barrio
            (33570.0, 10440.0, 0.0), (33570.0, 12076.0, 0.0),              # E3 vereda de enfrente
            (PBN['gap_s'][0] - 60.0, 22420.0, 90.0), (PBN['gap_s'][1] + 60.0, 22420.0, 90.0),    # E4 lado barrio
            (PBN['gap_n'][0] - 60.0, 26110.0, 90.0), (PBN['gap_n'][1] + 60.0, 26110.0, 90.0)]    # E4 patio


def salida_lines():
    """Franja verde en el piso donde empieza cada ExitZone: (x0, x1, y0, y1, z0, z1)."""
    e1a, e1b = E1_X[0] + VER, E1_X[1] - VER
    return [(E1_X[0], e1a, 26185.0, 26215.0, Z_VER - 1.0, Z_VER + 0.6),
            (e1a, e1b, 26185.0, 26215.0, 1.0, 5.2),
            (e1b, E1_X[1], 26185.0, 26215.0, Z_VER - 1.0, Z_VER + 0.6),
            (25262.0, 25292.0, 25990.0, 26310.0, 1.0, 3.8),
            (AV_CALZ[1] + 18.0, AV_CALZ[1] + 48.0, 10578.0, 11938.0, Z_VER - 1.0, Z_VER + 0.6),
            (E4_ZONE['c'][0] - E4_ZONE['ext'][0], E4_ZONE['c'][0] + E4_ZONE['ext'][0],
             E4_ZONE['c'][1] - E4_ZONE['ext'][1] - 15.0, E4_ZONE['c'][1] - E4_ZONE['ext'][1] + 15.0, -1.0, 1.2)]


def pbn_lums():
    """Tubos del paso bajo nivel (contrato de luminarias): escaleras y túnel, pegados al cielorraso."""
    xc = 0.5 * (PBN['x_bot'] + PBN['x_e'])
    out = [{'pos': (0.5 * (PBN['x_top'] + PBN['x_bot']), 0.5 * (PBN['ys'][0] + PBN['ys'][1]), PBN['zc'] - 40.0),
            'street': 'Tunel'},
           {'pos': (0.5 * (PBN['x_top'] + PBN['x_bot']), 0.5 * (PBN['yn'][0] + PBN['yn'][1]), PBN['zc'] - 40.0),
            'street': 'Tunel'}]
    y = PBN['ys'][1] + 300.0
    while y < PBN['yn'][0]:
        out.append({'pos': (xc, y, PBN['zc'] - 12.0), 'street': 'Tunel'})
        y += 600.0
    return out


def plan_avenue(rng):
    """Columnas dobles en el cantero, paradas, semáforos de E3."""
    av = {'cols': [], 'lums': [], 'paradas': [], 'semaforos': []}
    xc = 0.5 * (AV_CANTERO[0] + AV_CANTERO[1])
    for y in avenue_column_ys():
        av['cols'].append((xc, y, 0.0))
        av['lums'].append({'pos': (xc - AV_ARM_X, y, AV_LUM_Z), 'street': 'Avenida'})
        av['lums'].append({'pos': (xc + AV_ARM_X, y, AV_LUM_Z), 'street': 'Avenida'})
    # paradas de colectivo (refugio) en ambas veredas: una por cuadra y por mano (ahí para un colectivo)
    av['paradas'] = [{'pos': (x, y, Z_VER), 'yaw': yaw} for (x, y, yaw) in AV_PARADAS]
    av['semaforos'] = [{'pos': (AV_X0 + 380.0, E3_Y[0] + 300.0, 0.0), 'yaw': 0.0},
                       {'pos': (AV_X1 - 380.0, E3_Y[1] - 300.0, 0.0), 'yaw': 180.0},
                       {'pos': (xc, E3_Y[0] + 60.0, 0.0), 'yaw': 90.0},
                       {'pos': (xc, E3_Y[1] - 60.0, 0.0), 'yaw': -90.0}]
    return av


AV_PARADAS = [(AV_X0 + 300.0, 4800.0, 0.0), (AV_X0 + 300.0, 14600.0, 0.0),
              (AV_X1 - 300.0, 8400.0, 180.0), (AV_X1 - 300.0, 18200.0, 180.0),
              (AV_X0 + 300.0, -5200.0, 0.0), (AV_X1 - 300.0, -2600.0, 180.0)]


def avenue_column_ys():
    ys = []
    y = AV_S_END + 1050.0
    while y < OBRA_AV_S[0] - 400.0:
        if not (E3_Y[0] - 500.0 < y < E3_Y[1] + 500.0):
            ys.append(y)
        y += 2500.0
    return ys


def avenue_planters():
    """Canteros de ladrillo de 80 cm en el cantero central, entre columnas (cada 25 m), fuera de E3."""
    out = []
    for y in avenue_column_ys():
        yc = y + 1250.0
        if E3_Y[0] - 400.0 < yc < E3_Y[1] + 400.0 or yc > OBRA_AV_S[0] - 500.0:
            continue
        out.append(yc)
    return out


CAR_TYPES = [('sedan', 0.36), ('hatch', 0.34), ('utilitario', 0.2), ('pickup', 0.1)]
CAR_COLORS = ['MI_Auto_Blanco', 'MI_Auto_Blanco', 'MI_Auto_Gris', 'MI_Auto_Gris', 'MI_Auto_Negro', 'MI_Auto_Rojo',
              'MI_Auto_Azul']
CUT_SPACING = 6000.0          # un corte que cruza el eje cada <= 60 m (validador: 70 m libres)
CHICANA = (1700.0, -1700.0, 1500.0, -1500.0, 2000.0, -2000.0)
# cortes viejos que se conservan junto al cordón (no cruzan el eje: decoran y cubren la vereda)
CURB_CUTS = [('M10', 'S', 3600.0, 'camion'), ('M20', 'N', 5600.0, 'puesto'), ('M21', 'N', 5800.0, 'volquete'),
             ('M00', 'W', 4300.0, 'volquete'), ('M01', 'W', 2600.0, 'camion'), ('M21', 'W', 4600.0, 'camion'),
             ('M20', 'E', 3900.0, 'camion')]
# zonas sin cortes que cruzan el eje (a lo largo de cada calle)
CUT_FORBID = {'Media': [(14600.0, 18300.0)],                     # frente de la comisaría
              'Paralela': [(24700.0, 27400.0)]}                  # boca de la escalera sur de E2
# estacionamiento: (calle, lado, tramos a lo largo). Las E-O tienen autos en los DOS lados.
def _park_ranges():
    out = []
    for (name, axis, cc, aa, cross) in STREETS:
        if axis == 'EW':
            for side in (-1, 1):
                out.append((name, side, [(x0 + 900.0, x1 - 900.0) for (x0, x1) in XCOL]))
    r0, r1 = (YROW[0][0] + 900.0, YROW[0][1] - 900.0), (YROW[1][0] + 900.0, YROW[1][1] - 900.0)
    rs = (YROW[-1][0] + 900.0, YROW[-1][1] - 900.0)
    out += [('Oeste', 1, [rs, r0, r1]), ('C01', -1, [r0]), ('C01', 1, [rs, r1]), ('C12', 1, [r0]),
            ('C12', -1, [rs, r1]), ('Av_O', -1, [rs, r0, r1])]
    return out


def _lot_curb(lot):
    st = street_of(lot['mid'], lot['side'])
    if st == 'Avenida':
        st = 'Av_O'
    return st, {'S': 1, 'N': -1, 'W': 1, 'E': -1}[lot['side']]


def _along(axis, p):
    return p[0] if axis == 'EW' else p[1]


def plan_cars_and_cuts(rng, lots, verdes):
    """Cortes que cruzan el eje de cada calle (semicortes de calzada: zanjas con chicana, mudanzas, repartos,
    árbol caído; colectivos detenidos en doble fila en la avenida), cortes viejos junto al cordón, autos
    estacionados (en los dos lados de las E-O) con huecos para cruzar y nunca frente a garajes, puertas
    robables, la comisaría ni las salidas. Llamar DESPUÉS de choose_loot (usa lot['robbable'])."""
    cars, cuts, conts = [], [], []
    by_street = {}           # (calle) -> lista de (along, half, lado o None)

    def add_cut(kind, street, along, side, d=0.0, colectivo=False):
        name, axis, (c0, c1), aa, cross = street_def(street)
        cc = c0 if side < 0 else c1
        if colectivo:
            c = cc - side * 300.0
            yaw = YAW_CURB[(axis, side)] + 180.0
        else:
            c = cc + side * d
            yaw = YAW_CURB[(axis, side)]
        x0, x1, y0, y1, top = CUT_FOOT[kind]
        q = {'kind': kind, 'pos': street_pt(axis, along, c), 'yaw': yaw, 'street': street, 'along': along,
             'side': side, 'axis_cut': True, 'L': x1 - x0}
        cuts.append(q)
        by_street.setdefault(street, []).append((along, 0.5 * (x1 - x0), side))
        return q
    # ---- avenida: un colectivo detenido (en doble fila, cruza el eje de su mano) por cuadra y por mano
    fixed = {'Av_O': [], 'Av_E': []}
    for (x, y, yaw) in AV_PARADAS:
        st, side = ('Av_O', -1) if x < AV_CANTERO[0] else ('Av_E', 1)
        add_cut('colectivo', st, y + (-250.0 if side < 0 else 250.0), side, colectivo=True)
        fixed[st].append(y)
    # ---- cortes que cruzan el eje, repartidos cada <= CUT_SPACING
    n_kinds = ['zanja', 'mudanza', 'arbol_caido', 'reparto']
    for (name, axis, (c0, c1), (a0, a1), cross) in STREETS:
        av = name.startswith('Av_')
        forbid = [(a - 700.0, b + 700.0) for (a, b) in cross] + CUT_FORBID.get(name, [])
        fx = sorted(fixed.get(name, []))
        forbid += [(f - 1500.0, f + 1500.0) for f in fx]
        pts = [a0] + fx + [a1]
        kinds = list(n_kinds) if not av else ['reparto', 'mudanza']
        rng.shuffle(kinds)
        side = 1 if rng.random() < 0.5 else -1
        if av:
            side = 1 if name == 'Av_O' else -1          # empieza del lado del cantero; después alterna
        k = 0
        targets = []
        for i in range(len(pts) - 1):
            p, q = pts[i], pts[i + 1]
            cur = p
            while q - cur > CUT_SPACING:
                lim = min(cur + CUT_SPACING, q - 1500.0)
                pos = None
                v = lim
                while v > cur + 1500.0:                       # el más lejano permitido sin pasarse
                    if not _in_any(v, forbid, 450.0):
                        pos = v
                        break
                    v -= 100.0
                if pos is None:                               # si no hay, el primero permitido después
                    v = lim
                    while v < q - 1000.0:
                        if not _in_any(v, forbid, 450.0):
                            pos = v
                            break
                        v += 100.0
                if pos is None:
                    break
                targets.append(pos)
                cur = pos
        for pos in targets:
            kind = kinds[k % len(kinds)]
            k += 1
            if av:
                add_cut(kind, name, pos, side, d=130.0)       # la mano de la avenida tiene 7,75 m
                side = -side
                continue
            add_cut(kind, name, pos, side)
            if kind == 'zanja':
                # chicana: el otro medio corte, del lado opuesto, a 15-20 m
                for off in CHICANA:
                    if not _in_any(pos + off, forbid, 350.0):
                        add_cut('zanja_b', name, pos + off, -side)
                        break
            side = -side
    # ---- cortes viejos junto al cordón (si no chocan con un semicorte de la misma calle)
    for (mid, sd, yy, kind) in CURB_CUTS:
        f = side_frame(mid, sd)
        w = side_width(mid, sd)
        st, side = _lot_curb({'mid': mid, 'side': sd})
        axis = street_def(st)[1]
        p = fw(f, w + 135.0, yy)
        al = _along(axis, p)
        if any(abs(al - a) < h + 900.0 for (a, h, s_) in by_street.get(st, [])):
            continue
        x0, x1, y0, y1, top = CUT_FOOT[kind]
        cuts.append({'kind': kind, 'frame': f, 'ly': yy, 'w': w, 'L': x1 - x0, 'pos': p, 'yaw': f['yaw'] + 90.0,
                     'mid': mid, 'side': side, 'street': st, 'along': al, 'axis_cut': False})
        by_street.setdefault(st, []).append((al, 0.5 * (x1 - x0), side))
    # ---- zonas prohibidas para autos, por (calle, lado)
    avoid = {}

    def av_add(st, side, a, b):
        avoid.setdefault((st, side), []).append((a, b))
    for lot in lots:
        if not lot.get('mid') or lot.get('mid') == 'M11' or not lot.get('variant'):
            continue
        st, side = _lot_curb(lot)
        axis = street_def(st)[1]
        f = lot['frame']
        g = lot.get('garage')
        if g:
            a, b = _along(axis, fw(f, 0.0, lot['y0'] + g[0])), _along(axis, fw(f, 0.0, lot['y0'] + g[1]))
            av_add(st, side, min(a, b) - 30.0, max(a, b) + 30.0)
        e = lot.get('entry')
        if lot.get('robbable') and e:
            p, yaw, ew, eh = lot_world_entry(lot)
            a = _along(axis, p)
            av_add(st, side, a - ew * 0.5 - 150.0, a + ew * 0.5 + 150.0)
    for st, lst in by_street.items():
        for (a, h, s_) in lst:
            for side in (-1, 1):
                av_add(st, side, a - h - 200.0, a + h + 200.0)
    av_add('Media', -1, 14400.0, 18500.0)                                   # comisaría (patrulleros aparte)
    av_add('Paralela', 1, E1_X[0] - 1200.0, E1_X[1] + 1200.0)               # boca de E1
    av_add('Paralela', 1, 24600.0, 27400.0)                                 # boca de E2
    av_add('Av_O', -1, E3_Y[0] - 1500.0, E3_Y[1] + 1500.0)                  # E3
    av_add('Paralela', -1, REMIS['cars'][0][0] - 500.0, REMIS['cars'][-1][0] + 500.0)
    # ---- autos estacionados
    for (st, side, ranges) in _park_ranges():
        name, axis, (c0, c1), aa, cross = street_def(st)
        cc = c0 if side < 0 else c1
        ivs = avoid.get((st, side), [])
        for (r0, r1) in ranges:
            y = r0 + rng.uniform(0.0, 300.0)
            while y < r1:
                r = rng.random()
                acc = 0.0
                t = 'sedan'
                for (nm, pw) in CAR_TYPES:
                    acc += pw
                    if r <= acc:
                        t = nm
                        break
                half = CAR_DIMS[t][0] + 15.0
                if _in_any(y, ivs, half) or y + half > r1 + 300.0:
                    y += rng.uniform(250.0, 500.0)
                    continue
                if rng.random() < 0.15:              # hueco para cruzar
                    y += LOT * rng.uniform(0.8, 1.1)
                    continue
                d = 0.0 if rng.random() < 0.8 else 180.0
                cars.append({'type': t, 'color': rng.choice(CAR_COLORS),
                             'pos': street_pt(axis, y, cc - side * (118.0 + rng.uniform(-8.0, 8.0))),
                             'yaw': YAW_CURB[(axis, side)] + 180.0 + d + rng.uniform(-2.5, 2.5),
                             'street': st, 'side': side})
                y += rng.uniform(LOT * 0.7, LOT * 1.2)
    # ---- contenedores de residuos en algunas esquinas de inicio (calzada, junto al cordón)
    for v in verdes:
        mid, sd = v['mid'], v['side']
        if mid is None or mid == 'M11':
            continue
        if rng.random() < 0.5:
            f = v['frame']
            conts.append({'pos': fw(f, v['w'] + 100.0, 520.0), 'yaw': f['yaw'] + 90.0})
    # ---- patrulleros frente a la comisaría y remises junto a E1
    f = side_frame('M10', 'N')
    for k, yy in enumerate((2900.0, 5800.0)):
        cars.append({'type': 'patrullero', 'color': 'MI_Auto_Blanco', 'pos': fw(f, VER + 118.0, yy),
                     'yaw': f['yaw'] + 90.0, 'street': 'Media', 'side': -1})
    cpar = curb_c('Paralela', -1)
    for (x, yaw) in REMIS['cars']:
        cars.append({'type': 'sedan', 'color': 'MI_Auto_Negro', 'pos': (x, cpar + 118.0, 0.0), 'yaw': yaw,
                     'street': 'Paralela', 'side': -1, 'remis': True})
    return cars, cuts, conts



def plan_motos(seed, lots):
    """Motos estacionadas en la vereda contra el frente de algunas casas y locales (no en puertas robables,
    garajes ni esquinas), paralelas a la línea municipal."""
    rng = random.Random(seed * 3 + 17)
    out = []
    for lot in lots:
        if not lot.get('mid') or not lot.get('variant') or lot.get('robbable') or lot.get('slot', 0) == 0:
            continue
        if rng.random() > 0.2:
            continue
        busy = []
        e = lot.get('entry')
        if e:
            busy.append((e[1] - 70.0, e[2] + 70.0))
        g = lot.get('garage')
        if g:
            busy.append((g[0] - 40.0, g[1] + 40.0))
        for yy in (150.0, 700.0, 430.0):
            if not _in_any(yy, busy, 110.0):
                f = lot['frame']
                out.append({'pos': fw(f, 55.0, lot['y0'] + yy, Z_VER), 'yaw': f['yaw'] + (90.0 if rng.random() < 0.5 else -90.0),
                            'color': rng.choice(['MI_Auto_Rojo', 'MI_Auto_Negro', 'MI_Auto_Azul', 'MI_Auto_Blanco'])})
                break
    return out


def plan_street_signs():
    """Un cartel de calle por cruce, en la esquina de vereda de alguna manzana."""
    signs = []
    for mid in sorted(MANZANAS.keys()):
        for side in SIDE_ORDER:
            # cada manzana pone cartel en su esquina SO (lado S, slot 0) y NE (lado N, slot 0)
            if side not in ('S', 'N'):
                continue
            f = side_frame(mid, side)
            w = side_width(mid, side)
            wp = side_width(mid, PREV_SIDE[side])
            signs.append({'pos': fw(f, w - 45.0, -wp + 45.0), 'yaw': f['yaw']})
    return signs


# =====================================================================================
# ACTORES DE JUEGO
# =====================================================================================
def _look(p, targets=((16454.0, 16454.0), (30300.0, 19900.0))):
    """Yaw que deja en cuadro la plaza y la torre (promedio de los dos rumbos) desde p."""
    a = [math.degrees(math.atan2(t[1] - p[1], t[0] - p[0])) for t in targets]
    return 0.5 * (a[0] + a[1])


# Llegada: andén de la estación (la formación que los trajo queda detenida al oeste del andén, en la vía norte).
ARRIVAL = [(19250.0, 25350.0), (19950.0, 25350.0)]
GAMEPLAY = {
    'player_starts': [((x, y, PLATFORM['z'] + 100.0), _look((x, y))) for (x, y) in ARRIVAL],
    'extra_start': ((18550.0, 25350.0, PLATFORM['z'] + 100.0), 700.0),       # base y paso para PlayerStart extra
    # zona segura: andén, estación, explanada y refugio de llegada
    'safe_llegada': ((17250.0, 26750.0, Z_VER + 150.0), (3300.0, 1750.0, 400.0)),
    # comisaría: hall de 8 x 6 m detrás de la puerta (frente norte, Y LM 10392), piso a Z 46
    'comisaria_hall': dict(x=(16054.0, 16854.0), y=(9792.0, 10392.0), z=46.0),
    # las tres ExitZone del lado de Afuera: E1 pasando las vías (Y > 26.016), E2 al pie de la escalera norte
    # (sin tocar la escalera), E3 en la vereda de enfrente de la avenida (X 33.345 - 33.775, no en la calzada)
    'exit': [('ExitZone_E1_PasoNivel', (11258.0, 26800.0, 150.0), (900.0, 600.0, 300.0)),
             ('ExitZone_E2_Pasarela', (24840.0, 26250.0, 150.0), (430.0, 320.0, 300.0)),
             ('ExitZone_E3_Avenida', (33560.0, 11258.0, 150.0), (215.0, 680.0, 300.0)),
             # E4: patio ferroviario al salir del paso bajo nivel (lado norte de las vías)
             ('ExitZone_E4_Tunel', (E4_ZONE['c'][0], E4_ZONE['c'][1], 150.0), (E4_ZONE['ext'][0], E4_ZONE['ext'][1], 300.0))],
    'fence': ((22200.0, 30000.0, Z_VER + 55.0), -90.0),
    'jail': ((16454.0, 7200.0, 230.0), 0.0),
    'nav': ((19500.0, 11700.0, 300.0), (43000.0, 46400.0, 2000.0)),     # v5: incluye la fila sur y el túnel
    'patrol': [(12250.0, 12250.0), (20650.0, 12250.0), (12250.0, 20650.0), (20650.0, 20650.0),
               (11258.0, 22000.0), (26300.0, 22300.0), (31900.0, 11258.0), (31900.0, 4000.0), (31900.0, 18000.0),
               (16454.0, 11000.0)],
}


def comisaria_layout():
    """Marco del frente de la comisaría (lado N de la 1,0, slots 3..6)."""
    f = side_frame('M10', 'N')
    return f, 3 * LOT, 7 * LOT


# =====================================================================================
# TODO JUNTO
# =====================================================================================
def build_plan(seed):
    rng = random.Random(seed)
    lots = plan_lots(rng)
    verdes = vereda_specs(rng, lots)
    furn = plan_street_furniture(rng, lots, verdes)
    bpoles, blums = plan_border_poles(rng)
    av = plan_avenue(rng)
    loot, uncovered = choose_loot(rng, lots)               # antes que los autos: no estacionar frente a robos
    cars, cuts, conts = plan_cars_and_cuts(rng, lots, verdes)
    segs, inter = street_segments()
    plan = {'seed': seed, 'lots': lots, 'veredas': verdes, 'furn': furn, 'border_poles': bpoles,
            'border_lums': blums, 'avenue': av, 'cars': cars, 'cuts': cuts, 'containers': conts, 'loot': loot,
            'uncovered': uncovered, 'segs': segs, 'inter': inter, 'signs': plan_street_signs(),
            'rng': rng}
    plan['motos'] = plan_motos(seed, lots)
    plan['arcos'] = plan_arcos(furn)
    plan['sight'] = validate_sightlines(plan)
    return plan


if __name__ == '__main__':
    p = build_plan(5258)
    kinds = {}
    for l in p['lots']:
        kinds[l['kind']] = kinds.get(l['kind'], 0) + 1
    print('lotes', len(p['lots']), kinds)
    print('robos', len(p['loot']), 'sin cubrir', len(p['uncovered']))
    print('postes', len(p['furn']['poles']) + len(p['border_poles']), 'lums',
          len(p['furn']['lums']) + len(p['border_lums']) + len(p['avenue']['lums']))
    print('arboles', len(p['furn']['trees']), 'autos', len(p['cars']), 'cortes', len(p['cuts']))
    kc = {}
    for q in p['cuts']:
        kc[q['kind']] = kc.get(q['kind'], 0) + 1
    print('cortes por tipo', kc)
    res, errs = p['sight']
    for r in res:
        print('%-9s %-8s libre max %6.1f m %s' % (r['street'], r['ray'], r['max'] / 100.0,
                                                 'OK' if r['ok'] else ('ERROR' if r['required'] else 'aviso')))
    print('errores de visual:', len(errs))
    for e in errs:
        print('  ' + e)
