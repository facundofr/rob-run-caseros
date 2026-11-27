# -*- coding: utf-8 -*-
"""
barrio_geo.py  -  Geometría de calles del mapa: suelo base, veredas (por lado de manzana), calzadas
(con bombeo, cordón cuneta, bacheo, juntas de sellado, charcos y sendas), cruces, avenida con cantero
y reja (corte en E3), vías (tramo instanciable: balasto, durmientes, rieles), catenaria, alambrados,
paso a nivel E1, pasarelas (E2 y la provisoria de la obra) y cables por tramo de calle.

Todas las funciones build_* devuelven un MB (barrio_kit) en coordenadas locales; build_barrio.py
decide el origen y el yaw del actor (indicado en cada docstring).
"""

import math
import random

import barrio_kit as k
from barrio_kit import MB, box, cbox, prism, cyl, cone, blob, tube, rbox, torus, M_HIERRO
import barrio_layout as L
import barrio_props as P

Z_VER = L.Z_VER


def poly_z(mb, mat, pts, z0, z1):
    prism(mb, mat, pts, 'z', z0, z1)


# =====================================================================================
# SUELO BASE
# =====================================================================================
GROUND = (-26000.0, 66000.0, -36000.0, 62000.0)    # incluye el skyline lejano (v5: más al sur por la fila nueva)


def suelo_holes():
    """Huecos de la losa de suelo: las dos bocas (escalera + descanso) del paso bajo nivel E4."""
    p = L.PBN
    return [(p['x_top'], p['x_e'], p['ys'][0], p['ys'][1]), (p['x_top'], p['x_e'], p['yn'][0], p['yn'][1])]


def build_suelo():
    """Losa de tierra bajo todo el mapa (actor en el origen). Tapa el vacío bajo los fondos y Afuera.
    v5: con huecos en las bocas del paso bajo nivel (el túnel pasa por debajo de la losa: cielorraso a -60)."""
    mb = MB('Suelo')
    x0, x1, y0, y1 = GROUND
    for (a0, a1, b0, b1) in k.rect_minus(x0, x1, y0, y1, suelo_holes()):
        box(mb, 'MI_Tierra', a0, a1, b0, b1, -60.0, -1.0)
        mb.col(a0, a1, b0, b1, -60.0, -1.0)
    return mb


# =====================================================================================
# PASO BAJO NIVEL PEATONAL (E4, v5)
# =====================================================================================
TUNEL_FRANJAS = ['MI_Cartel_Rojo', 'MI_Pintura_Amarilla', 'MI_Cartel_Verde', 'MI_Cartel_Azul', 'MI_Pintura_Blanca']


def _franjas(mb, rng, axis, coord, sign, a0, a1, z0, z1, w=115.0, tags=0):
    """Franjas verticales de colores (como los túneles pintados de Caseros) sobre una cara de muro.
    axis 'x': la cara es el plano X=coord (franjas a lo largo de Y); 'y': plano Y=coord. sign: hacia dónde mira."""
    a = a0
    i = rng.randint(0, len(TUNEL_FRANJAS) - 1)
    while a < a1 - 1.0:
        b = min(a1, a + w)
        mat = TUNEL_FRANJAS[i % len(TUNEL_FRANJAS)]
        i += 1
        c0, c1 = (coord, coord + 1.0) if sign > 0 else (coord - 1.0, coord)
        if axis == 'x':
            box(mb, mat, c0, c1, a, b, z0, z1)
        else:
            box(mb, mat, a, b, c0, c1, z0, z1)
        a = b
    for t in range(tags):                        # tags en aerosol encima de las franjas
        u = rng.uniform(a0 + 100.0, a1 - 200.0)
        zz = rng.uniform(z0 + 40.0, max(z0 + 45.0, z1 - 160.0))
        if axis == 'x':
            P.pintada(mb, rng.randint(1, 4), coord + sign * 1.5, u, zz, rng.uniform(110.0, 170.0),
                      0.0 if sign > 0 else 180.0)
        else:
            P.pintada(mb, rng.randint(1, 4), u, coord + sign * 1.5, zz, rng.uniform(110.0, 170.0),
                      90.0 if sign > 0 else -90.0)


def _escalera(mb, p, yb, sentido):
    """Escalera recta paralela a las vías: arriba en x_top (Z -1), abajo en x_bot (Z = p['z']).
    yb = (y0, y1) de la banda. Peldaños macizos + nariz amarilla + rampa de colisión."""
    n = p['steps']
    xt, xb, z = p['x_top'], p['x_bot'], p['z']
    run = (xb - xt) / n
    rise = (-1.0 - z) / n
    y0, y1 = yb
    for i in range(n):
        xa, xc = xt + i * run, xt + (i + 1) * run
        zt = -1.0 - (i + 1) * rise
        box(mb, 'MI_Hormigon', xa, xc, y0, y1, z - 20.0, zt)
        box(mb, 'MI_Pintura_Amarilla', xa, xa + 5.0, y0 + 10.0, y1 - 10.0, zt, zt + 0.4)
    mb.ramp([(xt - 5.0, -1.0), (xb, z), (xb, z - 30.0), (xt - 5.0, z - 30.0)], 'y', y0, y1)
    # pasamanos de caño a los dos lados (a 90 cm sobre la nariz)
    for yy in (y0 + 6.0, y1 - 6.0):
        tube(mb, M_HIERRO, [(xt - 30.0, yy, 89.0), (xt, yy, 89.0), (xb, yy, z + 89.0), (xb + 30.0, yy, z + 89.0)], 2.4, 8)
        for xx in (xt + 40.0, 0.5 * (xt + xb), xb - 40.0):
            zz = -1.0 - (xx - xt) / run * rise
            cyl(mb, M_HIERRO, (xx, yy, zz), (xx, yy, zz + 89.0), 1.6, 6)


def build_paso_bajo_nivel(seed):
    """Paso bajo nivel peatonal bajo las vías (salida E4). Actor en el origen (mundo).
    Dos bocas con escalera paralela a las vías (dentro del corredor, entrando por un hueco del alambrado),
    túnel norte-sur de 3 m x 2,7 m con piso de hormigón, cielorraso de hormigón bajo la losa del suelo,
    tubos de luz, franjas verticales de colores y tags, pretiles de 90 cm alrededor de las bocas."""
    rng = random.Random(seed)
    mb = MB('PasoBajoNivel')
    p = L.PBN
    xt, xb, xe, z, zc, w = p['x_top'], p['x_bot'], p['x_e'], p['z'], p['zc'], p['wall']
    ys, yn = p['ys'], p['yn']
    PRE = 90.0                                         # pretil sobre el nivel del suelo
    # piso del túnel y de los descansos (con junta y rejilla de desagüe en el medio)
    box(mb, 'MI_Hormigon', xb, xe, ys[0], yn[1], z - 30.0, z)
    mb.col(xb, xe, ys[0], yn[1], z - 30.0, z)
    ym = 0.5 * (ys[1] + yn[0])
    box(mb, M_HIERRO, xb + 110.0, xe - 110.0, ym - 25.0, ym + 25.0, z, z + 0.5)
    y = ys[1] + 300.0
    while y < yn[0]:
        box(mb, 'MI_Hormigon_Bacheo', xb, xe, y, y + 2.0, z, z + 0.3)
        y += 400.0
    # escaleras
    _escalera(mb, p, ys, 1)
    _escalera(mb, p, yn, 1)
    # cielorraso de hormigón bajo la losa del suelo (el túnel)
    box(mb, 'MI_Hormigon', xb - w, xe + w, ys[1], yn[0], zc - 14.0, zc)
    # muros (revoque blanco de base, franjas encima). Cada boca: muro exterior, muro interior de la escalera,
    # muro este del descanso y pretiles; el túnel: muros oeste y este hasta el cielorraso.
    W = 'MI_Revoque_Blanco'
    for (b0, b1, out_y, in_y) in ((ys[0], ys[1], ys[0] - w, ys[1]), (yn[0], yn[1], yn[1], yn[0] - w)):
        # muro exterior (lado de afuera del corredor) a todo lo largo de la boca
        box(mb, W, xt, xe + w, out_y, out_y + w, z - 30.0, PRE)
        mb.col(xt, xe + w, out_y, out_y + w, z - 30.0, PRE)
        # muro interior de la escalera (contra la tierra del corredor)
        box(mb, W, xt, xb - w, in_y, in_y + w, z - 30.0, PRE)
        mb.col(xt, xb - w, in_y, in_y + w, z - 30.0, PRE)
        # dintel + pretil sobre la boca del túnel
        box(mb, W, xb - w, xe + w, in_y, in_y + w, zc - 14.0, PRE)
        mb.col(xb - w, xe + w, in_y, in_y + w, zc - 14.0, PRE)
        # muro este del descanso (de z a pretil)
        box(mb, W, xe, xe + w, b0 - w, b1 + w, z - 30.0, PRE)
        mb.col(xe, xe + w, b0 - w, b1 + w, z - 30.0, PRE)
        # coronamiento de los pretiles (hormigón) y baranda de caño encima
        for (a0, a1, c0, c1) in ((xt, xe + w, out_y, out_y + w), (xt, xb, in_y, in_y + w), (xb - w, xe + w, in_y, in_y + w)):
            box(mb, 'MI_Hormigon', a0 - 2.0, a1 + 2.0, c0 - 2.0, c1 + 2.0, PRE, PRE + 6.0)
        box(mb, 'MI_Hormigon', xe - 2.0, xe + w + 2.0, b0 - w, b1 + w, PRE, PRE + 6.0)
        yc = out_y + 0.5 * w
        tube(mb, M_HIERRO, [(xt, yc, PRE + 6.0 + 95.0), (xe + w, yc, PRE + 6.0 + 95.0)], 2.2, 8)
        xx = xt + 10.0
        while xx < xe + w:
            cyl(mb, M_HIERRO, (xx, yc, PRE + 6.0), (xx, yc, PRE + 101.0), 1.5, 6)
            xx += 150.0
        mb.col(xt, xe + w, out_y, out_y + w, PRE, PRE + 101.0)
        # franjas: cara interior del muro exterior y del muro interior, cara oeste del muro este
        sgn = 1.0 if out_y < b0 else -1.0
        _franjas(mb, rng, 'y', out_y + (w if sgn > 0 else 0.0), sgn, xt, xe, z, PRE - 2.0, tags=1)
        _franjas(mb, rng, 'y', in_y + (0.0 if sgn > 0 else w), -sgn, xt, xb - w, z, PRE - 2.0)
        _franjas(mb, rng, 'x', xe, -1.0, b0, b1, z, PRE - 2.0)
        # franja de prevención en el borde de arriba de la escalera
        box(mb, 'MI_Pintura_Amarilla', xt - 45.0, xt - 5.0, b0, b1, -1.0, 0.2)
    # muros del túnel
    box(mb, W, xb - w, xb, ys[1] + w, yn[0] - w, z - 30.0, zc - 14.0)
    mb.col(xb - w, xb, ys[1], yn[0], z - 30.0, zc)
    box(mb, W, xe, xe + w, ys[1] + w, yn[0] - w, z - 30.0, zc - 14.0)
    mb.col(xe, xe + w, ys[1], yn[0], z - 30.0, zc)
    _franjas(mb, rng, 'x', xb, 1.0, ys[1] + w, yn[0] - w, z, zc - 14.0, tags=3)
    _franjas(mb, rng, 'x', xe, -1.0, ys[1] + w, yn[0] - w, z, zc - 14.0, tags=3)
    # zócalo gris sucio abajo (las patadas y el agua)
    for (x0, x1) in ((xb, xb + 1.6), (xe - 1.6, xe)):
        box(mb, 'MI_Revoque_Gris', x0, x1, ys[0], yn[1], z, z + 35.0)
    # tubos de luz bajo el cielorraso (difusor + caja)
    for l in L.pbn_lums():
        x, yy, zz = l['pos']
        if zz < zc - 30.0:
            continue
        box(mb, M_HIERRO, x - 9.0, x + 9.0, yy - 65.0, yy + 65.0, zc - 22.0, zc - 14.0)
        box(mb, 'MI_Emisivo_Luminaria', x - 6.0, x + 6.0, yy - 60.0, yy + 60.0, zc - 25.0, zc - 22.0)
    # apliques en las escaleras (pared exterior)
    for (b0, b1, out_y) in ((ys[0], ys[1], ys[0]), (yn[0], yn[1], yn[1])):
        sg = 1.0 if out_y == b0 else -1.0
        for xx in (xt + 120.0, 0.5 * (xt + xb) + 60.0):
            box(mb, 'MI_Emisivo_Luminaria', xx - 25.0, xx + 25.0, out_y + sg * 1.0, out_y + sg * 9.0, -40.0, -30.0)
    # basura y hojas en los rincones de abajo
    for j in range(10):
        xx, yy = rng.uniform(xb + 15.0, xe - 15.0), rng.choice((rng.uniform(ys[0] + 10, ys[1]), rng.uniform(yn[0], yn[1] - 10)))
        blob(mb, rng.choice(['MI_Plastico_Negro', 'MI_Follaje', 'MI_Tierra']), (xx, yy, z + 3.0), rng.uniform(6, 14),
             rng.uniform(6, 14), rng.uniform(2, 6), yaw=rng.uniform(0, 180), steps=(4, 6))
    return mb



# =====================================================================================
# VEREDAS
# =====================================================================================
def build_vereda2(spec, pits, strips, seed):
    """Vereda de un lado de manzana (o de borde). Actor en spec['frame']['o'] con yaw del frame.
    Local: x = 0 en la línea municipal, x = w en la cara del cordón; y a lo largo; esquina en y<0."""
    rng = random.Random(seed)
    mb = MB(spec['name'])
    w = spec['w']
    Ls = spec['L']
    wp = spec['wprev']
    cx = w - 15.0
    corner = spec['corner']
    plaza = spec.get('plaza', False)

    def seg_top(y):
        for (a, b, m, dz) in spec['segs']:
            if a <= y < b:
                return Z_VER + dz
        return Z_VER
    pit_h = [(w - 120.0, w - 50.0, y - 35.0, y + 35.0) for y in pits]
    strip_h = [(w - 55.0, cx, a, b) for (a, b, m) in strips]
    ramp_h = [(w - 95.0, w, r0 - 25.0, r1 + 25.0) for (r0, r1) in spec['ramps']]
    for (y0, y1, mat, dz) in spec['segs']:
        top = Z_VER + dz
        hs = [h for h in pit_h + strip_h + ramp_h if h[3] > y0 and h[2] < y1]
        for (a0, a1, b0, b1) in k.rect_minus(0.0, cx, y0, y1, hs):
            box(mb, mat, a0, a1, b0, b1, -1.0, top)
        for (a0, a1, b0, b1) in k.rect_minus(0.0, w, y0, y1, [h for h in ramp_h if h[3] > y0 and h[2] < y1]):
            mb.col(a0, a1, b0, b1, -1.0, top)
        if y0 > 0.5:
            box(mb, 'MI_Hormigon', 0.0, cx, y0 - 1.0, y0 + 1.0, -1.0, top + 0.25)
        # detalles por tramo: tapas, baldosas flojas
        if rng.random() < 0.4:
            x = rng.uniform(40.0, 110.0)
            y = rng.uniform(y0 + 60.0, y1 - 60.0)
            s = rng.choice((22.0, 30.0, 40.0))
            cbox(mb, M_HIERRO, x - s * 0.5, x + s * 0.5, y - s * 0.5, y + s * 0.5, top - 1.0, top + 0.4, 0.4, 'z')
        if mat == 'MI_Baldosa' and rng.random() < 0.6:
            for j in range(rng.randint(1, 3)):
                x = rng.uniform(40.0, w - 150.0)
                y = rng.uniform(y0 + 40.0, y1 - 40.0)
                raise_ = rng.uniform(2.0, 4.0)
                rbox(mb, mat, x, y, top - 1.2 + raise_, 39.5, 39.5, 1.8, rng.uniform(-4.0, 4.0),
                     rng.choice((-1, 1)) * rng.uniform(3.0, 6.0), rng.choice((-1, 1)) * rng.uniform(3.0, 6.0))
    # cazuelas (tierra, borde de ladrillo; algunas con anillo de baldosas levantadas por las raíces)
    for y in pits:
        top = seg_top(y)
        box(mb, 'MI_Tierra', w - 118.0, w - 52.0, y - 33.0, y + 33.0, -1.0, top - 4.0)
        for (a0, a1, b0, b1) in ((w - 120.0, w - 50.0, y - 35.0, y - 30.0), (w - 120.0, w - 50.0, y + 30.0, y + 35.0),
                                 (w - 120.0, w - 115.0, y - 30.0, y + 30.0), (w - 55.0, w - 50.0, y - 30.0, y + 30.0)):
            box(mb, 'MI_Ladrillo', a0, a1, b0, b1, -1.0, top + 1.5)
        if rng.random() < 0.35:
            for (dx, dy, pit_, rol_) in ((-60.0, 0.0, 0.0, 4.0), (60.0, 0.0, 0.0, -4.0), (0.0, -60.0, -4.0, 0.0),
                                         (0.0, 60.0, 4.0, 0.0)):
                px = w - 85.0 + dx
                if px > cx - 25.0:
                    continue
                rbox(mb, 'MI_Baldosa', px, y + dy, top - 1.0 + rng.uniform(2.0, 3.5), 39.5, 39.5, 1.8,
                     rng.uniform(-6, 6), pit_ * rng.uniform(0.8, 1.4), rol_ * rng.uniform(0.8, 1.4))
        elif rng.random() < 0.4:
            box(mb, 'MI_Pasto', w - 116.0, w - 54.0, y - 31.0, y + 31.0, -1.0, top - 2.5)
    # franjas de tierra / pasto junto al cordón
    for (a, b, m) in strips:
        top = seg_top(a)
        box(mb, m, w - 55.0, cx, a, b, -1.0, top - 2.5)
        if m == 'MI_Pasto':
            for j in range(rng.randint(2, 4)):
                blob(mb, 'MI_Follaje', (rng.uniform(w - 50.0, cx - 5.0), rng.uniform(a + 10.0, b - 10.0), top - 1.0),
                     rng.uniform(5.0, 9.0), rng.uniform(5.0, 9.0), rng.uniform(4.0, 8.0), steps=(4, 6))
    # rebajes de garaje (rampa) con cordón pintado de amarillo a los costados
    yellow = []
    for (r0, r1) in spec['ramps']:
        top = seg_top(r0)
        prof = [(w - 95.0, -1.0), (w, -1.0), (w, 6.0), (w - 95.0, top)]
        prism(mb, 'MI_Hormigon', prof, 'y', r0, r1)
        mb.ramp(prof, 'y', r0, r1)
        prof2 = [(w - 95.0, -1.0), (w, -1.0), (w, 11.0), (w - 95.0, top)]
        for (a, b) in ((r0 - 25.0, r0), (r1, r1 + 25.0)):
            prism(mb, 'MI_Hormigon', prof2, 'y', a, b)
            mb.ramp(prof2, 'y', a, b)
        yellow += [(r0 - 160.0, r0 - 25.0), (r1 + 25.0, r1 + 160.0)]
    # cordón
    y_start = -wp + 60.0 if corner else 0.0
    gaps = [(r0 - 25.0, r1 + 25.0) for (r0, r1) in spec['ramps']]
    if corner:
        gaps.append((-220.0, -60.0))         # rebaje de esquina (cruce de esta calle)
    for (a, b) in k.interval_minus(y_start, Ls, gaps):
        cuts = sorted(set([a, b] + [v for yy in yellow for v in yy if a < v < b]))
        for i in range(len(cuts) - 1):
            ya, yb = cuts[i], cuts[i + 1]
            mid = 0.5 * (ya + yb)
            mat = 'MI_Pintura_Amarilla' if any(p <= mid <= q for (p, q) in yellow) else 'MI_Hormigon'
            y = ya
            while y < yb - 0.5:
                yn = min(yb, y + rng.uniform(140.0, 220.0))
                h = Z_VER + rng.uniform(-0.4, 0.4)
                prism(mb, mat, [(cx, -1.0), (w, -1.0), (w, h - 2.5), (w - 2.5, h), (cx, h)], 'y', y + 0.25, yn - 0.25)
                y = yn
        mb.col(cx, w, a, b, -1.0, Z_VER)
    if corner:
        _vereda_corner(mb, rng, spec, w, wp, cx, plaza)
    # en la vereda de la plaza: borde bajo de la plaza (cordón interior) sin ochava
    return mb


def _vereda_corner(mb, rng, spec, w, wp, cx, plaza):
    c = 60.0
    mat = spec['segs'][0][2]
    ramp_a = (70.0, 220.0, -wp, -wp + 100.0)                 # cruce de la calle anterior (en -y)
    ramp_b = (w - 100.0, w, -220.0, -60.0)                   # cruce de esta calle (en +x)
    holes = [ramp_a, ramp_b, (cx - c, cx, -wp + 15.0, -wp + 15.0 + c)]
    for (a0, a1, b0, b1) in k.rect_minus(0.0, cx, -wp + 15.0, 0.0, holes):
        box(mb, mat, a0, a1, b0, b1, -1.0, Z_VER)
    poly_z(mb, mat, [(cx - c, -wp + 15.0), (cx, -wp + 15.0 + c), (cx - c, -wp + 15.0 + c)], -1.0, Z_VER)
    for (a0, a1, b0, b1) in k.rect_minus(0.0, w, -wp, 0.0, [ramp_a, ramp_b]):
        mb.col(a0, a1, b0, b1, -1.0, Z_VER)
    # rampas de esquina
    pa = [(-wp, -1.0), (-wp + 100.0, -1.0), (-wp + 100.0, Z_VER), (-wp, 5.0)]
    prism(mb, 'MI_Hormigon', pa, 'x', ramp_a[0], ramp_a[1])
    mb.ramp(pa, 'x', ramp_a[0], ramp_a[1])
    pb = [(w - 100.0, -1.0), (w, -1.0), (w, 5.0), (w - 100.0, Z_VER)]
    prism(mb, 'MI_Hormigon', pb, 'y', ramp_b[2], ramp_b[3])
    mb.ramp(pb, 'y', ramp_b[2], ramp_b[3])
    # textura táctil de alerta en los rebajes
    box(mb, 'MI_Pintura_Amarilla', ramp_a[0] + 10.0, ramp_a[1] - 10.0, -wp + 70.0, -wp + 95.0, -1.0, Z_VER + 0.3)
    box(mb, 'MI_Pintura_Amarilla', w - 95.0, w - 70.0, ramp_b[2] + 10.0, ramp_b[3] - 10.0, -1.0, Z_VER + 0.3)
    # cordón de la esquina: borde de la calle anterior (a lo largo de x), ochava del cordón y borde x=w
    for (a, b) in k.interval_minus(0.0, w - c, [(ramp_a[0], ramp_a[1])]):
        prism(mb, 'MI_Hormigon', [(-wp, -1.0), (-wp + 15.0, -1.0), (-wp + 15.0, Z_VER), (-wp + 2.5, Z_VER),
                                  (-wp, Z_VER - 2.5)], 'x', a + 0.25, b - 0.25)
        mb.col(a, b, -wp, -wp + 15.0, -1.0, Z_VER)
    rbox(mb, 'MI_Hormigon', w - c * 0.5 - 5.3, -wp + c * 0.5 + 5.3, -1.0, c * 1.414 + 8.0, 15.0, Z_VER + 1.0, 45.0)
    for (a, b) in k.interval_minus(-wp + c, 0.0, [(ramp_b[2], ramp_b[3])]):
        prism(mb, 'MI_Hormigon', [(cx, -1.0), (w, -1.0), (w, Z_VER - 2.5), (w - 2.5, Z_VER), (cx, Z_VER)], 'y',
              a + 0.25, b - 0.25)
    # ochava (dentro de la línea municipal): vereda hasta la pared de la esquina
    if not plaza:
        tri = [(0.0, 0.0), (0.0, L.OCHAVA), (-L.OCHAVA, 0.0)]
        poly_z(mb, mat, tri, -1.0, Z_VER)
        mb.ramp(tri, 'z', -1.0, Z_VER)


# =====================================================================================
# CALZADAS
# =====================================================================================
def _crown(c, Wc):
    e = min(c, Wc - c)
    if e < 45.0:
        return 1.6 + e / 45.0
    if e < 250.0:
        return 2.6 + (e - 45.0) / 205.0 * 2.0
    return 4.6


def build_calzada(seg, seed, zebra=(True, True)):
    """Tramo de calzada de 10,32 m (cordón cuneta + asfalto con bombeo). Actor en (x0, y0), yaw 0."""
    axis, x0, x1, y0, y1, name = seg
    rng = random.Random(seed)
    mb = MB('Calzada_' + name)
    if axis == 'EW':
        La, Wc = x1 - x0, y1 - y0
    else:
        La, Wc = y1 - y0, x1 - x0
    pax = 'x' if axis == 'EW' else 'y'

    def PT(a, c):
        return (a, c) if axis == 'EW' else (c, a)

    def BX(mat, a0, a1, c0, c1, z0, z1):
        p, q = PT(a0, c0), PT(a1, c1)
        box(mb, mat, p[0], q[0], p[1], q[1], z0, z1)

    def RB(mat, a, c, z0, la, lc, h, heading):
        p = PT(a, c)
        if axis == 'EW':
            rbox(mb, mat, p[0], p[1], z0, la, lc, h, math.degrees(heading))
        else:
            rbox(mb, mat, p[0], p[1], z0, la, lc, h, 90.0 - math.degrees(heading))
    prism(mb, 'MI_Asfalto', [(45.0, -10.0), (Wc - 45.0, -10.0), (Wc - 45.0, 2.6), (Wc - 250.0, 4.6), (250.0, 4.6),
                             (45.0, 2.6)], pax, 0.0, La)
    prism(mb, 'MI_Hormigon', [(0.0, -10.0), (45.0, -10.0), (45.0, 2.6), (0.0, 1.6)], pax, 0.0, La)
    prism(mb, 'MI_Hormigon', [(Wc - 45.0, -10.0), (Wc, -10.0), (Wc, 1.6), (Wc - 45.0, 2.6)], pax, 0.0, La)
    a = 300.0
    while a < La - 50.0:
        prism(mb, 'MI_Plastico_Negro', [(0.0, 0.5), (45.0, 0.5), (45.0, 2.7), (0.0, 1.7)], pax, a - 0.7, a + 0.7)
        prism(mb, 'MI_Plastico_Negro', [(Wc - 45.0, 0.5), (Wc, 0.5), (Wc, 1.7), (Wc - 45.0, 2.7)], pax, a - 0.7, a + 0.7)
        a += 300.0
    # bacheo: polígonos irregulares de hormigón con junta de sellado negra
    for j in range(rng.randint(2, 4) if La > 3000.0 else rng.randint(0, 2)):
        rc = rng.uniform(45.0, 110.0)
        ra = rng.uniform(60.0, 170.0)
        cc = rng.uniform(250.0 + rc + 15.0, Wc - 250.0 - rc - 15.0) if Wc > 2 * (265.0 + rc) else Wc * 0.5
        ca = rng.uniform(400.0, La - 400.0) if La > 900.0 else La * 0.5
        pts = k.jitter_poly(rng, ca, cc, ra, rc, rng.randint(8, 12), 15.0, rng.uniform(-0.3, 0.3))
        mat = 'MI_Hormigon_Bacheo' if rng.random() < 0.7 else 'MI_Asfalto'
        poly_z(mb, 'MI_Plastico_Negro', [PT(p, q) for (p, q) in k.scale_poly(pts, 1.0, 3.0)], 3.6, 4.72)
        poly_z(mb, mat, [PT(p, q) for (p, q) in pts], 3.7, 4.8)
    # juntas de sellado (grietas selladas con brea)
    for j in range(rng.randint(1, 3)):
        a = rng.uniform(300.0, max(320.0, La - 300.0))
        c = rng.uniform(300.0, Wc - 300.0)
        hd = rng.uniform(0.0, 2.0 * math.pi)
        for s in range(rng.randint(10, 16)):
            ln = rng.uniform(25.0, 55.0)
            na = a + math.cos(hd) * ln
            nc = c + math.sin(hd) * ln
            if not (260.0 < nc < Wc - 260.0 and 20.0 < na < La - 20.0):
                break
            RB('MI_Plastico_Negro', 0.5 * (a + na), 0.5 * (c + nc), 4.45, ln + 1.0, rng.uniform(1.5, 2.6), 0.27, hd)
            a, c = na, nc
            hd += rng.uniform(-0.45, 0.45)
    # charcos en la cuneta
    for j in range(rng.randint(0, 2)):
        side = rng.choice((0, 1))
        ca = rng.uniform(300.0, La - 300.0) if La > 700.0 else La * 0.5
        cc = 20.0 if side == 0 else Wc - 20.0
        pts = k.jitter_poly(rng, ca, cc, rng.uniform(60.0, 140.0), rng.uniform(26.0, 42.0), 10, 8.0)
        poly_z(mb, 'MI_Agua', [PT(p, q) for (p, q) in pts], 0.5, 2.8)
    # sendas peatonales gastadas en los extremos (frente a las esquinas de vereda)
    for (end, on) in ((0, zebra[0]), (1, zebra[1])):
        if not on or La < 1200.0:
            continue
        a0, a1 = (30.0, 320.0) if end == 0 else (La - 320.0, La - 30.0)
        c = 80.0
        while c < Wc - 100.0:
            zt = max(_crown(c, Wc), _crown(c + 40.0, Wc)) + 0.15
            if rng.random() < 0.18:
                cut = rng.uniform(a0 + 60.0, a1 - 60.0)
                BX('MI_Pintura_Blanca', a0, cut - rng.uniform(20.0, 60.0), c, c + 40.0, zt - 1.0, zt)
                BX('MI_Pintura_Blanca', cut + rng.uniform(10.0, 40.0), a1, c, c + 40.0, zt - 1.0, zt)
            else:
                BX('MI_Pintura_Blanca', a0, a1, c, c + 40.0, zt - 1.0, zt)
            c += 80.0
    p, q = PT(0.0, 0.0), PT(La, Wc)
    mb.col(p[0], q[0], p[1], q[1], -10.0, 4.6)
    return mb


def build_cruce(rect, seed):
    """Cruce de calles (cuadrado de calzada). Actor en (x0, y0), yaw 0."""
    x0, x1, y0, y1, name = rect
    rng = random.Random(seed)
    mb = MB(name)
    W, H = x1 - x0, y1 - y0
    box(mb, 'MI_Asfalto', 0.0, W, 0.0, H, -10.0, 4.0)
    if rng.random() < 0.6:
        pts = k.jitter_poly(rng, rng.uniform(300, W - 300), rng.uniform(300, H - 300), rng.uniform(70, 150),
                            rng.uniform(60, 120), rng.randint(8, 12), 15.0)
        poly_z(mb, 'MI_Plastico_Negro', k.scale_poly(pts, 1.0, 3.0), 3.0, 4.12)
        poly_z(mb, 'MI_Hormigon_Bacheo', pts, 3.1, 4.2)
    if rng.random() < 0.5:
        cxn, cyn = rng.choice(((40.0, 40.0), (W - 40.0, 40.0), (40.0, H - 40.0), (W - 40.0, H - 40.0)))
        poly_z(mb, 'MI_Agua', k.jitter_poly(rng, cxn, cyn, rng.uniform(50, 100), rng.uniform(40, 80), 10, 10.0), 0.5, 4.2)
    mb.col(0.0, W, 0.0, H, -10.0, 4.0)
    return mb


def build_parche_vereda(name, x0, x1, y0, y1, mat='MI_Hormigon'):
    """Pedazo suelto de vereda (bocas de calle contra la avenida, etc.). Actor en el origen."""
    mb = MB(name)
    box(mb, mat, x0, x1, y0, y1, -1.0, Z_VER)
    mb.col(x0, x1, y0, y1, -1.0, Z_VER)
    return mb


# =====================================================================================
# AVENIDA (lado barrio, entre la obra sur y la obra antes de las vías)
# =====================================================================================
def _reja_panel_template(h=92.0, Lp=250.0):
    """Reja baja común del cantero central (no penitenciaria): 92 cm, barrotes cada 16 cm sin puntas ni púas,
    travesaño bajo y pasamanos redondo."""
    m = k.new_mesh()
    one = k._One(m)
    k.k_reja_plano(one, M_HIERRO, -1.0, 0.0, Lp, 0.0, h - 4.0, axis='y', spacing=16.0, bar=1.6, frame=2.5,
                   rails=(18.0,), lanzas=0.0)
    cyl(one, M_HIERRO, (0.25, 0.0, h - 2.0), (0.25, Lp, h - 2.0), 2.4, 8)
    return m


def k_cantero_alto(mb, cx, cy, lx, ly, z0, ztop, yaw=0.0, rng=None, col=True):
    """Cantero de ladrillo (cobertura baja de 70-90 cm): muro de 12 cm con coronamiento de hormigón, tierra y
    plantas. Rectángulo lx x ly centrado en (cx, cy), girado yaw. Colisión de caja (o prisma si está girado)."""
    rng = rng or random.Random(int(cx * 7 + cy * 13) & 0xFFFF)
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    t = 12.0
    h = ztop - z0
    for (ox, oy, ex, ey) in ((0.0, (ly - t) * 0.5, lx, t), (0.0, -(ly - t) * 0.5, lx, t),
                             ((lx - t) * 0.5, 0.0, t, ly - 2 * t), (-(lx - t) * 0.5, 0.0, t, ly - 2 * t)):
        px, py = cx + ox * c - oy * s_, cy + ox * s_ + oy * c
        rbox(mb, 'MI_Ladrillo', px, py, z0, ex, ey, h - 5.0, yaw)
        rbox(mb, 'MI_Hormigon', px, py, ztop - 5.0, ex + 3.0, ey + 3.0, 5.0, yaw)
    rbox(mb, 'MI_Tierra', cx, cy, z0, lx - 2 * t, ly - 2 * t, h - 14.0, yaw)
    n = max(1, int(lx * ly / 30000.0))
    for j in range(n):
        u, v = rng.uniform(-0.35, 0.35) * lx, rng.uniform(-0.3, 0.3) * ly
        blob(mb, 'MI_Follaje', (cx + u * c - v * s_, cy + u * s_ + v * c, ztop - 8.0), rng.uniform(22.0, 38.0),
             rng.uniform(20.0, 32.0), rng.uniform(20.0, 40.0), yaw=rng.uniform(0, 180), steps=(5, 7))
    if col:
        pts = [(cx + x * c - y * s_, cy + x * s_ + y * c) for (x, y) in
               ((-lx * 0.5, -ly * 0.5), (lx * 0.5, -ly * 0.5), (lx * 0.5, ly * 0.5), (-lx * 0.5, ly * 0.5))]
        if abs(round(yaw / 90.0) * 90.0 - yaw) < 1e-3:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            mb.col(min(xs), max(xs), min(ys), max(ys), z0, ztop)
        else:
            mb.ramps.append((pts, 'z', z0, ztop))


def tapial_obra(mb, x0, y0, x1, y1, h=240.0, cartel=True):
    """Tapial de chapa de obra (línea recta) con parantes; corta la calle. Coordenadas del MB."""
    L_ = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L_, (y1 - y0) / L_
    yaw = math.degrees(math.atan2(uy, ux))
    n = int(L_ // 100.0)
    for i in range(n + 1):
        a = i * 100.0
        b = min(L_, a + 99.0)
        if b - a < 5.0:
            continue
        cxm, cym = x0 + ux * (a + b) * 0.5, y0 + uy * (a + b) * 0.5
        rbox(mb, 'MI_Chapa_Gris', cxm, cym, 0.0, b - a, 1.4, h, yaw + (0.6 if i % 3 == 0 else 0.0))
    i = 0
    a = 0.0
    while a <= L_:
        px, py = x0 + ux * a, y0 + uy * a
        rbox(mb, 'MI_Madera', px - uy * 6.0, py + ux * 6.0, 0.0, 8.0, 8.0, h + 10.0, yaw)
        a += 250.0
    if cartel and L_ > 600.0:
        m = 0.5 * L_
        px, py = x0 + ux * m - uy * 2.0, y0 + uy * m + ux * 2.0
        rbox(mb, 'MI_Cartel_Azul', px, py, 90.0, 460.0, 2.0, 130.0, yaw)
        rbox(mb, 'MI_Cartel_Blanco', px - uy * 1.2, py + ux * 1.2, 100.0, 420.0, 1.0, 100.0, yaw)
    xs = [x0, x1]
    ys = [y0, y1]
    if abs(ux) > 0.99:
        mb.col(min(xs), max(xs), y0 - 8.0, y0 + 8.0, 0.0, h)
    elif abs(uy) > 0.99:
        mb.col(x0 - 8.0, x0 + 8.0, min(ys), max(ys), 0.0, h)
    else:
        nx, ny = -uy * 8.0, ux * 8.0
        mb.ramps.append(([(x0 - nx, y0 - ny), (x1 - nx, y1 - ny), (x1 + nx, y1 + ny), (x0 + nx, y0 + ny)], 'z', 0.0, h))


def build_avenida(seed):
    """Avenida lado barrio: calzadas de 7,75 m, cantero central con reja (salvo E3), sendas y obras en
    los extremos. Actor en (AV_X0, AV_S_END), yaw 0. Local x = X - 31176, y = Y + 150."""
    rng = random.Random(seed)
    mb = MB('Avenida')
    Y0 = L.AV_S_END
    Ly = L.OBRA_AV_S[0] - Y0
    gA = L.E3_Y[0] - Y0
    gB = L.E3_Y[1] - Y0
    xw0, xw1 = L.AV_CALZ[0] - L.AV_X0, L.AV_CANTERO[0] - L.AV_X0      # 450 .. 1225
    xe0, xe1 = L.AV_CANTERO[1] - L.AV_X0, L.AV_CALZ[1] - L.AV_X0      # 1375 .. 2150
    prism(mb, 'MI_Asfalto', [(xw0 + 45.0, -10.0), (xw1, -10.0), (xw1, 4.2), (xw0 + 45.0, 2.6)], 'y', 0.0, Ly)
    prism(mb, 'MI_Hormigon', [(xw0, -10.0), (xw0 + 45.0, -10.0), (xw0 + 45.0, 2.6), (xw0, 1.6)], 'y', 0.0, Ly)
    prism(mb, 'MI_Asfalto', [(xe0, -10.0), (xe1 - 45.0, -10.0), (xe1 - 45.0, 2.6), (xe0, 4.2)], 'y', 0.0, Ly)
    prism(mb, 'MI_Hormigon', [(xe1 - 45.0, -10.0), (xe1, -10.0), (xe1, 1.6), (xe1 - 45.0, 2.6)], 'y', 0.0, Ly)
    mb.col(xw0, xe1, 0.0, Ly, -10.0, 4.2)
    # cantero central con pasto, reja baja común y canteros de ladrillo de 80 cm cada ~25 m; corte en E3
    tpl = _reja_panel_template()
    xc = 0.5 * (xw1 + xe0)
    planters = [yw - Y0 for yw in L.avenue_planters()]
    for (a, b) in ((0.0, gA), (gB, Ly)):
        box(mb, 'MI_Hormigon', xw1, xe0, a, b, -10.0, 18.0)
        box(mb, 'MI_Pasto', xw1 + 12.0, xe0 - 12.0, a + 12.0, b - 12.0, 0.0, 18.6)
        mb.col(xw1, xe0, a, b, -10.0, 120.0)
        gaps = [(yp - 125.0, yp + 125.0) for yp in planters if a < yp < b]
        for (ra, rb) in k.interval_minus(a + 40.0, b - 30.0, gaps):
            y = ra
            while y + 250.0 <= rb:
                k.place(mb, M_HIERRO, tpl, (xc, y, 18.0), 0.0)
                y += 252.0
        for yp in planters:
            if a + 200.0 < yp < b - 200.0:
                k_cantero_alto(mb, xc, yp, 120.0, 230.0, 18.0, 95.0, 0.0, rng, False)
        y = a + 300.0
        while y < b - 300.0:
            if rng.random() < 0.5 and all(abs(y - yp) > 300.0 for yp in planters):
                blob(mb, 'MI_Follaje', (xc + rng.uniform(-25, 25), y, 40.0), rng.uniform(25, 40), rng.uniform(25, 40),
                     rng.uniform(20, 35), yaw=rng.uniform(0, 180), steps=(5, 7))
            y += rng.uniform(300.0, 700.0)
    k.free_mesh(tpl)
    box(mb, 'MI_Asfalto', xw1, xe0, gA, gB, -10.0, 4.2)
    # líneas de carril y sendas de E3
    for xl in (0.5 * (xw0 + xw1), 0.5 * (xe0 + xe1)):
        y = 200.0
        while y < Ly - 300.0:
            if not (gA - 400.0 < y < gB + 100.0):
                box(mb, 'MI_Pintura_Blanca', xl - 6.0, xl + 6.0, y, y + 300.0, 2.0, 4.0)
            y += 800.0
    for (ya, yb) in ((gA + 50.0, gA + 350.0), (gB - 350.0, gB - 50.0)):
        for (xa, xb) in ((xw0 + 50.0, xw1 - 20.0), (xe0 + 20.0, xe1 - 50.0)):
            x = xa
            while x < xb - 30.0:
                box(mb, 'MI_Pintura_Blanca', x, x + 40.0, ya, yb, 2.0, 4.5)
                x += 80.0
        box(mb, 'MI_Pintura_Blanca', xw0 + 50.0, xw1, ya - 70.0 if ya < gB - 400 else yb + 40.0,
            (ya - 40.0) if ya < gB - 400 else yb + 70.0, 2.0, 4.5)
    # obras que cierran la avenida (sur y antes de las vías)
    W_av = L.AV_X1 - L.AV_X0
    tapial_obra(mb, 0.0, 8.0, W_av, 8.0)
    tapial_obra(mb, 0.0, Ly + 40.0, W_av, Ly + 40.0)
    for (yv, sgn) in ((8.0, 1.0), (Ly + 40.0, -1.0)):
        for x in (500.0, 900.0, 1700.0, 2100.0):
            P.k_valla(mb, x - 180.0, yv + sgn * 160.0, x + 180.0, yv + sgn * 160.0)
        for x in (300.0, 1300.0, 2300.0):
            P.k_cono(mb, x, yv + sgn * 260.0, 3.0)
    # pedacitos de vereda que faltan contra la avenida
    ys0 = L.FONDO_Y[0] - Y0                       # v5: la avenida termina contra la calle Fondo
    box(mb, 'MI_Hormigon', 0.0, xw0, ys0, ys0 + L.VER, -1.0, Z_VER)
    mb.col(0.0, xw0, ys0, ys0 + L.VER, -1.0, Z_VER)
    yv0 = L.VIAS_Y0 - L.VER - Y0
    box(mb, 'MI_Hormigon', 0.0, xw0, yv0, Ly + 40.0, -1.0, Z_VER)
    mb.col(0.0, xw0, yv0, Ly + 40.0, -1.0, Z_VER)
    return mb


# =====================================================================================
# VÍAS
# =====================================================================================
TRAMO = 2000.0
BAL_Y = (L.TRACKS_Y[0] - 320.0, L.TRACKS_Y[1] + 320.0)


def build_tramo_via():
    """2000 cm de doble vía. Actor en (X, 0, 0): local y = Y de mundo."""
    mb = MB('TramoVia')
    rng = random.Random(3)
    b0, b1 = BAL_Y
    prism(mb, 'MI_Balasto', [(b0 - 70.0, -1.0), (b1 + 70.0, -1.0), (b1, 26.0), (b0, 26.0)], 'x', 0.0, TRAMO)
    mb.col(0.0, TRAMO, b0, b1, -1.0, 28.0)
    g = L.GAUGE * 0.5
    for yc in L.TRACKS_Y:
        x = 15.0
        while x < TRAMO:
            j = rng.uniform(-2.0, 2.0)
            rbox(mb, 'MI_Durmiente', x + j, yc, 14.0, 24.0, 275.0, 16.0, rng.uniform(-1.0, 1.0))
            for s in (-1.0, 1.0):
                for o in (-9.0, 9.0):
                    box(mb, M_HIERRO, x + j - 3.0, x + j + 3.0, yc + s * g + o - 2.0, yc + s * g + o + 2.0, 30.0, 33.0)
            x += 60.0
        for s in (-1.0, 1.0):
            yr = yc + s * g
            prism(mb, 'MI_Riel', [(yr - 7.5, 29.5), (yr + 7.5, 29.5), (yr + 7.5, 31.5), (yr + 1.0, 32.5), (yr + 1.0, 40.5),
                                  (yr + 3.5, 41.5), (yr + 3.5, 45.0), (yr - 3.5, 45.0), (yr - 3.5, 41.5), (yr - 1.0, 40.5),
                                  (yr - 1.0, 32.5), (yr - 7.5, 31.5)], 'x', 0.0, TRAMO)
            box(mb, M_HIERRO, TRAMO - 30.0, TRAMO - 2.0, yr - 4.5 * s - 0.6, yr - 4.5 * s + 0.6, 33.0, 43.0)
    # piedras sueltas fuera del balasto
    for j in range(10):
        blob(mb, 'MI_Balasto', (rng.uniform(0, TRAMO), rng.choice((b0 - 90.0, b1 + 90.0)) + rng.uniform(-30, 30), 0.0),
             rng.uniform(20, 50), rng.uniform(15, 35), rng.uniform(4, 9), yaw=rng.uniform(0, 180), steps=(4, 6))
    return mb


CATENARY_Z = (560.0, 650.0)     # hilo de contacto, sustentador
MAST_Y = BAL_Y[0] - 140.0


def build_mastil_catenaria():
    """Poste de catenaria simple con ménsula sobre las dos vías. Actor en (X, 0, 0)."""
    mb = MB('MastilCatenaria')
    y0 = MAST_Y
    box(mb, 'MI_Hormigon', -30.0, 30.0, y0 - 30.0, y0 + 30.0, -1.0, 30.0)
    for s in (-1.0, 1.0):
        box(mb, 'MI_Chapa_Gris', s * 9.0 - 2.0, s * 9.0 + 2.0, y0 - 12.0, y0 + 12.0, 30.0, 760.0)
    box(mb, 'MI_Chapa_Gris', -9.0, 9.0, y0 - 1.0, y0 + 1.0, 30.0, 760.0)
    ytip = L.TRACKS_Y[1] + 120.0
    cyl(mb, 'MI_Chapa_Gris', (0.0, y0, CATENARY_Z[1] + 40.0), (0.0, ytip, CATENARY_Z[1] + 40.0), 4.5, 10)
    cyl(mb, 'MI_Chapa_Gris', (0.0, y0, 560.0), (0.0, ytip - 60.0, CATENARY_Z[1] + 38.0), 3.0, 8)
    for yc in L.TRACKS_Y:
        cyl(mb, M_HIERRO, (0.0, yc, CATENARY_Z[1] + 40.0), (0.0, yc, CATENARY_Z[1]), 1.5, 6)
        cyl(mb, M_HIERRO, (0.0, yc - 80.0, CATENARY_Z[0] + 30.0), (0.0, yc, CATENARY_Z[0] + 2.0), 1.6, 6)
        cyl(mb, M_HIERRO, (0.0, y0, CATENARY_Z[0] + 30.0), (0.0, yc - 80.0, CATENARY_Z[0] + 30.0), 2.2, 6)
        for j in range(3):
            cyl(mb, k.M_PORCELANA, (0.0, yc, CATENARY_Z[1] + 20.0 + j * 4.0), (0.0, yc, CATENARY_Z[1] + 22.0 + j * 4.0), 5.0, 10)
    box(mb, M_HIERRO, -6.0, 6.0, y0 + 12.0, y0 + 22.0, 300.0, 340.0)
    mb.col(-14.0, 14.0, y0 - 14.0, y0 + 14.0, 0.0, 760.0)
    return mb


def build_hilos_catenaria(xs):
    """Hilos de contacto y sustentadores entre mástiles (actor en el origen)."""
    mb = MB('HilosCatenaria')
    for i in range(len(xs) - 1):
        xa, xb = xs[i], xs[i + 1]
        for yc in L.TRACKS_Y:
            z1, z0 = CATENARY_Z[1], CATENARY_Z[0]
            # zigzag del hilo de contacto
            za = yc + (15.0 if i % 2 == 0 else -15.0)
            zb = yc + (-15.0 if i % 2 == 0 else 15.0)
            tube(mb, 'MI_Cable', k.catenary((xa, za, z0), (xb, zb, z0), 4.0, 10), 0.5, 5)
            tube(mb, 'MI_Cable', k.catenary((xa, yc, z1), (xb, yc, z1), 55.0, 14), 0.55, 5)
            n = 6
            for j in range(1, n):
                t = j / float(n)
                x = xa + (xb - xa) * t
                ztop = z1 - 55.0 * 4.0 * t * (1.0 - t)
                cyl(mb, 'MI_Cable', (x, yc, ztop), (x, za + (zb - za) * t, z0 + 1.0), 0.3, 4)
    return mb


def _malla_romboidal(mb, x0, y0, ux, uy, a, b, z0, z1, step=20.0, r=0.32):
    """Malla romboidal modelada (alambres a +-45 grados) en el plano vertical del tramo, de a a b."""
    Lw = b - a
    H = z1 - z0
    for sgn in (1.0, -1.0):
        t = -H
        while t < Lw:
            # recta u = t + sgn*(z - z0) (sgn>0) o u = t + (H - (z - z0)) (sgn<0), recortada al paño
            u0, v0 = t, 0.0
            u1, v1 = t + H, H
            if u0 < 0.0:
                v0, u0 = -u0, 0.0
            if u1 > Lw:
                v1, u1 = H - (u1 - Lw), Lw
            if u1 - u0 > 2.0:
                if sgn < 0:
                    v0, v1 = H - v0, H - v1
                p0 = (x0 + ux * (a + u0), y0 + uy * (a + u0), z0 + v0)
                p1 = (x0 + ux * (a + u1), y0 + uy * (a + u1), z0 + v1)
                cyl(mb, M_HIERRO, p0, p1, r, 3)
            t += step


def build_alambrado(name, pts, h=200.0, tapial=False, seed=0, wire=False):
    """Alambrado olímpico (postes de hormigón con brazo para 3 hilos de púas) o tapial premoldeado,
    a lo largo de una polilínea de tramos rectos. wire=True: malla romboidal modelada (se lee de cerca
    aunque MI_Alambrado sea opaco) y yuyos al pie. Actor en el origen (mundo)."""
    rng = random.Random(seed)
    mb = MB(name)
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        Lr = math.hypot(x1 - x0, y1 - y0)
        if Lr < 1.0:
            continue
        ux, uy = (x1 - x0) / Lr, (y1 - y0) / Lr
        nx, ny = -uy, ux
        n = max(1, int(round(Lr / 300.0)))
        if tapial:
            for j in range(n):
                a = Lr * j / n
                b = Lr * (j + 1) / n
                cxm, cym = x0 + ux * (a + b) * 0.5, y0 + uy * (a + b) * 0.5
                yaw = math.degrees(math.atan2(uy, ux))
                rbox(mb, 'MI_Hormigon', cxm, cym, 0.0, b - a - 2.0, 8.0, 220.0, yaw)
                if rng.random() < 0.45:        # pintadas sin texto (manchas de color)
                    mat = rng.choice(['MI_Cartel_Rojo', 'MI_Cartel_Azul', 'MI_Cartel_Verde', 'MI_Pintura_Blanca',
                                      'MI_Pintura_Amarilla'])
                    for side in (-1.0, 1.0):
                        rbox(mb, mat, cxm + nx * side * 4.3, cym + ny * side * 4.3, rng.uniform(30, 80),
                             rng.uniform(80, b - a - 30.0), 0.5, rng.uniform(40, 120), yaw)
            for j in range(n + 1):
                a = Lr * j / n
                px, py = x0 + ux * a, y0 + uy * a
                box(mb, 'MI_Hormigon', px - 10.0, px + 10.0, py - 10.0, py + 10.0, 0.0, 232.0)
        else:
            posts = []
            for j in range(n + 1):
                a = Lr * j / n
                px, py = x0 + ux * a, y0 + uy * a
                box(mb, 'MI_Hormigon', px - 6.0, px + 6.0, py - 6.0, py + 6.0, -1.0, h + 25.0)
                cyl(mb, 'MI_Hormigon', (px, py, h + 25.0), (px + nx * 32.0, py + ny * 32.0, h + 50.0), 4.0, 6)
                posts.append((px, py))
            yaw = math.degrees(math.atan2(uy, ux))
            # malla romboidal como paño fino (MI_Alambrado), algunos paños vencidos
            for j in range(n):
                a = Lr * j / n
                b = Lr * (j + 1) / n
                cxm, cym = x0 + ux * (a + b) * 0.5, y0 + uy * (a + b) * 0.5
                if wire:
                    _malla_romboidal(mb, x0, y0, ux, uy, a + 7.0, b - 7.0, 8.0, h - 2.0)
                    for q in range(rng.randint(2, 4)):          # yuyos al pie del alambrado
                        tq = rng.uniform(a + 20.0, b - 20.0)
                        sd = rng.choice((-1.0, 1.0)) * rng.uniform(8.0, 40.0)
                        blob(mb, 'MI_Follaje', (x0 + ux * tq + nx * sd, y0 + uy * tq + ny * sd, 2.0),
                             rng.uniform(15.0, 35.0), rng.uniform(12.0, 25.0), rng.uniform(25.0, 60.0),
                             yaw=rng.uniform(0, 180), steps=(4, 6))
                    continue
                tilt = rng.uniform(-4.0, 4.0) if rng.random() < 0.15 else 0.0
                rbox(mb, 'MI_Alambrado', cxm, cym, 6.0, b - a - 8.0, 0.6, h - 6.0, yaw, 0.0, tilt)
            for z in (10.0, h * 0.5, h):
                tube(mb, M_HIERRO, [(x0, y0, z), (x1, y1, z)], 0.35, 4)
            for k_ in range(3):
                off = 12.0 + k_ * 10.0
                zz = h + 25.0 + off * 0.78
                ptsw = []
                for (px, py) in posts:
                    ptsw.append((px + nx * off, py + ny * off, zz))
                path = []
                for q in range(len(ptsw) - 1):
                    seg = k.catenary(ptsw[q], ptsw[q + 1], 2.5, 4)
                    path.extend(seg if not path else seg[1:])
                if len(path) > 1:
                    tube(mb, M_HIERRO, path, 0.3, 4)
        hh = 232.0 if tapial else h + 50.0
        if abs(ux) > 0.99:
            mb.col(min(x0, x1), max(x0, x1), y0 - 8.0, y0 + 8.0, -1.0, hh)
        elif abs(uy) > 0.99:
            mb.col(x0 - 8.0, x0 + 8.0, min(y0, y1), max(y0, y1), -1.0, hh)
        else:
            mb.ramps.append(([(x0 - nx * 8, y0 - ny * 8), (x1 - nx * 8, y1 - ny * 8), (x1 + nx * 8, y1 + ny * 8),
                              (x0 + nx * 8, y0 + ny * 8)], 'z', -1.0, hh))
    return mb


WIRE_NEAR_E1 = 3500.0     # metros de alambrado con malla modelada a cada lado de E1


def fence_runs():
    """Polilíneas de alambrado del corredor ferroviario (mundo). (nombre, pts, tapial, malla modelada).
    Sin tapiales de premoldeado: alambrado romboidal como en Cavassa; con malla modelada junto a E1."""
    S, N = L.FENCE_S, L.FENCE_N
    j0, j1, jy = L.E2['jog']
    wa, wb = L.E1_X[0] - WIRE_NEAR_E1, L.E1_X[1] + WIRE_NEAR_E1
    gs, gn = L.PBN['gap_s'], L.PBN['gap_n']
    runs = [
        ('Alambrado_Vias_S_0', [(-4000.0, S), (gs[0], S)], False, False),
        ('Alambrado_Vias_S_0b', [(gs[1], S), (wa, S)], False, False),
        ('Alambrado_Vias_S_1', [(wa, S), (L.E1_X[0], S)], False, True),
        ('Alambrado_Vias_S_2a', [(L.E1_X[1], S), (wb, S)], False, True),
        ('Alambrado_Vias_S_2', [(wb, S), (j0, S), (j0, jy), (j1, jy), (j1, S), (L.AV_X0, S)], False, False),
        ('Alambrado_Vias_S_3', [(L.AV_X0, S), (42000.0, S)], False, False),
        ('Alambrado_Vias_N_0', [(-4000.0, N), (gn[0], N)], False, False),
        ('Alambrado_Vias_N_0b', [(gn[1], N), (wa, N)], False, False),
        ('Alambrado_Vias_N_1', [(wa, N), (L.E1_X[0], N)], False, True),
        ('Alambrado_Vias_N_2', [(L.E1_X[1], N), (L.PLATFORM['x'][0], N)], False, True),
        ('Alambrado_Vias_N_3', [(L.PLATFORM['x'][1], N), (42000.0, N)], False, False),
        # cierres del corredor contra las formaciones detenidas en los extremos
        ('Alambrado_Cierre_O1', [(-30.0, S), (-30.0, L.TRACKS_Y[0] - 160.0)], False, False),
        ('Alambrado_Cierre_O2', [(-30.0, L.TRACKS_Y[0] + 160.0), (-30.0, L.TRACKS_Y[1] - 160.0)], False, False),
        ('Alambrado_Cierre_O3', [(-30.0, L.TRACKS_Y[1] + 160.0), (-30.0, N)], False, False),
        ('Alambrado_Cierre_E1', [(38030.0, S), (38030.0, L.TRACKS_Y[0] - 160.0)], False, False),
        ('Alambrado_Cierre_E2', [(38030.0, L.TRACKS_Y[0] + 160.0), (38030.0, L.TRACKS_Y[1] - 160.0)], False, False),
        ('Alambrado_Cierre_E3', [(38030.0, L.TRACKS_Y[1] + 160.0), (38030.0, N)], False, False),
    ]
    return runs


# formaciones detenidas: las 4 que cierran la vía en los extremos + la que trajo a los jugadores (vía norte,
# junto al andén, al oeste de la llegada para no tapar la vista hacia la plaza y la torre)
TRAIN_ANDEN = (15800.0, L.TRACKS_Y[1])
TRAIN_X = [(-2000.0, L.TRACKS_Y[0]), (-2000.0, L.TRACKS_Y[1]), (40030.0, L.TRACKS_Y[0]), (40030.0, L.TRACKS_Y[1]),
           TRAIN_ANDEN]


def build_corredor_suelo(seed):
    """Pasto y yuyos en los márgenes del corredor ferroviario (actor en el origen)."""
    rng = random.Random(seed)
    mb = MB('CorredorSuelo')
    for j in range(70):
        x = rng.uniform(-3500.0, 41500.0)
        y = rng.choice((rng.uniform(L.FENCE_S + 80.0, BAL_Y[0] - 120.0), rng.uniform(BAL_Y[1] + 120.0, L.FENCE_N - 80.0)))
        if L.E1_X[0] - 100 < x < L.E1_X[1] + 100 or L.PLATFORM['x'][0] < x < L.PLATFORM['x'][1] and y > BAL_Y[1]:
            continue
        if L.PBN['gap_s'][0] - 900.0 < x < L.PBN['x_e'] + 700.0:      # bocas del paso bajo nivel
            continue
        pts = k.jitter_poly(rng, x, y, rng.uniform(150, 600), rng.uniform(80, 250), rng.randint(8, 11), 30.0)
        poly_z(mb, 'MI_Pasto', pts, -1.0, rng.uniform(0.3, 1.5))
        for q in range(rng.randint(2, 5)):
            blob(mb, 'MI_Follaje', (x + rng.uniform(-120, 120), y + rng.uniform(-60, 60), 5.0), rng.uniform(15, 40),
                 rng.uniform(15, 40), rng.uniform(15, 35), yaw=rng.uniform(0, 180), steps=(4, 6))
    return mb


def build_alamo(seed):
    """Álamo (columnar) para el borde del corredor: hito vertical a lo lejos."""
    rng = random.Random(seed)
    mb = MB('Alamo')
    h = rng.uniform(1300.0, 1600.0)
    cone(mb, 'MI_Corteza', (0.0, 0.0, -20.0), (rng.uniform(-10, 10), rng.uniform(-10, 10), h * 0.9), 22.0, 4.0, 10)
    z = 250.0
    while z < h:
        r = 95.0 * math.sin(math.pi * min(1.0, (z - 150.0) / (h - 100.0))) + 25.0
        for j in range(3):
            a = rng.uniform(0, 2 * math.pi)
            blob(mb, 'MI_Follaje', (math.cos(a) * r * 0.35, math.sin(a) * r * 0.35, z + rng.uniform(-30, 30)),
                 r * rng.uniform(0.6, 0.85), r * rng.uniform(0.6, 0.85), rng.uniform(80, 130), yaw=rng.uniform(0, 180),
                 pitch=rng.uniform(-8, 8), steps=(6, 8))
        z += rng.uniform(110.0, 160.0)
    mb.col(-22.0, 22.0, -22.0, 22.0, 0.0, 400.0)
    return mb


# =====================================================================================
# PASO A NIVEL E1
# =====================================================================================
def _barrera(mb, px, py, arm_dir, open_deg=82.0):
    """Barrera de paso a nivel levantada (abierta): pie, motor, brazo rojo y blanco."""
    cbox(mb, 'MI_Pintura_Amarilla', px - 22.0, px + 22.0, py - 22.0, py + 22.0, 0.0, 115.0, 2.0, 'z')
    cbox(mb, M_HIERRO, px - 25.0, px + 25.0, py - 25.0, py + 25.0, 115.0, 125.0, 1.5, 'y')
    piv = (px, py, 105.0)
    a = math.radians(open_deg)
    d = (arm_dir[0] * math.cos(a), arm_dir[1] * math.cos(a), math.sin(a))
    cyl(mb, M_HIERRO, (px - arm_dir[1] * 26.0, py + arm_dir[0] * 26.0, 105.0),
        (px + arm_dir[1] * 26.0, py - arm_dir[0] * 26.0, 105.0), 6.0, 10)
    seg = 60.0
    for i in range(9):
        p0 = k.v_add(piv, k.v_mul(d, i * seg))
        p1 = k.v_add(piv, k.v_mul(d, (i + 1) * seg - 1.0))
        cyl(mb, 'MI_Cartel_Rojo' if i % 2 == 0 else 'MI_Pintura_Blanca', p0, p1, 5.0 - i * 0.25, 8)
    cw = k.v_add(piv, k.v_mul(d, -70.0))
    cbox(mb, M_HIERRO, cw[0] - 18.0, cw[0] + 18.0, cw[1] - 14.0, cw[1] + 14.0, cw[2] - 25.0, cw[2] + 25.0, 2.0, 'z')
    mb.col(px - 22.0, px + 22.0, py - 22.0, py + 22.0, 0.0, 125.0)


def _cruz_san_andres(mb, px, py, face_yaw):
    """Cruz de San Andrés grande (brazos de 2,3 m blancos con borde rojo, a 4 m: se lee a 60 m), poste rayado,
    semáforo ferroviario de dos luces rojas con visera hacia los dos lados y campana (sin texto)."""
    zc = 400.0
    cyl(mb, M_HIERRO, (px, py, -10.0), (px, py, 470.0), 6.5, 12)
    for j in range(4):                                       # franjas rojas y blancas en el poste
        z = 40.0 + j * 60.0
        cyl(mb, 'MI_Cartel_Rojo' if j % 2 == 0 else 'MI_Pintura_Blanca', (px, py, z), (px, py, z + 60.0), 7.2, 12)
    cbox(mb, 'MI_Hormigon', px - 30.0, px + 30.0, py - 30.0, py + 30.0, -5.0, 25.0, 2.0, 'z')
    for d in (40.0, -40.0):
        rbox(mb, 'MI_Cartel_Rojo', px, py, zc - 18.0, 7.0, 236.0, 36.0, face_yaw + 90.0, 0.0, d)
        rbox(mb, 'MI_Pintura_Blanca', px, py, zc - 14.0, 8.0, 228.0, 28.0, face_yaw + 90.0, 0.0, d)
    c, s = math.cos(math.radians(face_yaw)), math.sin(math.radians(face_yaw))
    for face in (1.0, -1.0):
        cc, ss = c * face, s * face
        box(mb, M_HIERRO, px - 42.0 if abs(c) < 0.5 else px - 4.0, px + 42.0 if abs(c) < 0.5 else px + 4.0,
            py - 4.0 if abs(c) < 0.5 else py - 42.0, py + 4.0 if abs(c) < 0.5 else py + 42.0, 286.0, 296.0)
        for o in (-36.0, 36.0):
            q = (px + cc * 10.0 - ss * o, py + ss * 10.0 + cc * o, 270.0)
            cyl(mb, M_HIERRO, (q[0] - cc * 8.0, q[1] - ss * 8.0, q[2]), (q[0] + cc * 2.0, q[1] + ss * 2.0, q[2]), 17.0, 14)
            cyl(mb, 'MI_Emisivo_Baliza_Roja', (q[0] + cc * 2.0, q[1] + ss * 2.0, q[2]),
                (q[0] + cc * 3.5, q[1] + ss * 3.5, q[2]), 12.5, 14)
            # visera
            cyl(mb, M_HIERRO, (q[0] + cc * 2.0, q[1] + ss * 2.0, q[2] + 9.0), (q[0] + cc * 22.0, q[1] + ss * 22.0, q[2] + 9.0),
                3.0, 6)
    cone(mb, M_HIERRO, (px, py, 470.0), (px, py, 452.0), 14.0, 4.0, 12)
    mb.col(px - 8.0, px + 8.0, py - 8.0, py + 8.0, 0.0, 470.0)


def build_paso_nivel(seed):
    """Paso a nivel E1 sobre las dos vías. Actor en (E1_X[0], VIAS_Y0). Local x 0..1732, y 0..3500."""
    rng = random.Random(seed)
    mb = MB('PasoNivel')
    W = L.E1_X[1] - L.E1_X[0]
    Ly = L.VIAS_Y1 - L.VIAS_Y0
    ya = L.TRACKS_Y[0] - L.VIAS_Y0 - 430.0
    yb = L.TRACKS_Y[1] - L.VIAS_Y0 + 330.0
    top = L.RAIL_TOP - 0.5
    prof = [(0.0, -6.0), (Ly, -6.0), (Ly, 4.0), (yb, top), (ya, top), (0.0, 4.0)]
    prism(mb, 'MI_Hormigon', prof, 'x', 0.0, L.VER)
    prism(mb, 'MI_Asfalto', prof, 'x', L.VER, W - L.VER)
    prism(mb, 'MI_Hormigon', prof, 'x', W - L.VER, W)
    mb.ramp(prof, 'x', 0.0, W)
    # paneles de goma entre rieles y líneas de detención
    g = L.GAUGE * 0.5
    for yc in L.TRACKS_Y:
        y = yc - L.VIAS_Y0
        box(mb, 'MI_Neumatico', L.VER, W - L.VER, y - g + 8.0, y + g - 8.0, top - 3.0, top + 0.25)
        for s in (-1.0, 1.0):
            box(mb, 'MI_Plastico_Negro', 0.0, W, y + s * g - 3.0 * s - 2.5, y + s * g - 3.0 * s + 2.5, top - 3.0, top + 0.2)
            box(mb, 'MI_Neumatico', L.VER, W - L.VER, y + s * (g + 10.0) - 25.0 * (1 if s < 0 else 0),
                y + s * (g + 10.0) + 25.0 * (1 if s > 0 else 0), top - 3.0, top + 0.25)
    box(mb, 'MI_Pintura_Blanca', L.VER + 20.0, W - L.VER - 20.0, 380.0, 420.0, 3.0, 4.0 + 0.1 + (top - 4.0) * 380.0 / ya)
    box(mb, 'MI_Pintura_Blanca', L.VER + 20.0, W - L.VER - 20.0, Ly - 420.0, Ly - 380.0, 3.0,
        4.0 + 0.1 + (top - 4.0) * 400.0 / (Ly - yb))
    # barreras levantadas: una por mano (se circula por la derecha)
    _barrera(mb, W - 120.0, ya - 380.0, (-1.0, 0.0))
    _barrera(mb, 120.0, yb + 380.0, (1.0, 0.0))
    _barrera(mb, 60.0, ya - 380.0, (1.0, 0.0), 85.0)          # peatonales
    _barrera(mb, W - 60.0, yb + 380.0, (-1.0, 0.0), 85.0)
    _cruz_san_andres(mb, W + 80.0, ya - 520.0, -90.0)
    _cruz_san_andres(mb, -80.0, yb + 520.0, 90.0)
    # laberintos peatonales (pasos de 1,2 m)
    for (x0, yy, sgn) in ((0.0, 240.0, 1.0), (W - L.VER, 240.0, 1.0), (0.0, Ly - 240.0, -1.0),
                          (W - L.VER, Ly - 240.0, -1.0)):
        for (a, b, dy) in ((x0, x0 + 230.0, 0.0), (x0 + 120.0, x0 + L.VER, sgn * 130.0)):
            zb = 4.0
            y = yy + dy
            for xx in (a, b):
                cyl(mb, 'MI_Cartel_Rojo', (xx, y, zb), (xx, y, zb + 100.0), 2.5, 8)
            cyl(mb, 'MI_Pintura_Blanca', (a, y, zb + 100.0), (b, y, zb + 100.0), 2.5, 8)
            cyl(mb, 'MI_Cartel_Rojo', (a, y, zb + 55.0), (b, y, zb + 55.0), 2.0, 8)
            mb.col(a, b, y - 4.0, y + 4.0, 0.0, 105.0)
    # casilla del guardabarrera (en el margen del corredor, al este)
    hx0, hx1, hy0, hy1 = W + 220.0, W + 520.0, 450.0, 700.0
    box(mb, 'MI_Hormigon', hx0 - 30.0, hx1 + 30.0, hy0 - 30.0, hy1 + 60.0, -1.0, 12.0)
    hut = MB('Casilla')
    k.wall_holes(hut, 'MI_Ladrillo', -25.0, 0.0, 0.0, hy1 - hy0, 12.0, 270.0, [(60.0, 140.0, 12.0, 215.0),
                                                                             (170.0, 230.0, 110.0, 190.0)])
    k.k_door(hut, 0.0, 60.0, 140.0, 12.0, 215.0, dict(hoja='MI_Chapa_Verde', estilo='chapa', umbral=False))
    k.k_window(hut, 'MI_Ladrillo', 0.0, 170.0, 230.0, 115.0, 190.0, dict(reja='barrotes', persiana=None, cortina=False))
    k.merge_mb(mb, hut, (hx0, hy0, 0.0), 0.0)
    for (a0, a1, b0, b1) in ((hx0 - 300.0, hx0 - 275.0, hy0, hy1), (hx0 - 300.0, hx0, hy0, hy0 + 25.0),
                             (hx0 - 300.0, hx0, hy1 - 25.0, hy1)):
        box(mb, 'MI_Ladrillo', a0, a1, b0, b1, 12.0, 270.0)
    prism(mb, 'MI_Chapa_Gris', [(hy0 - 40.0, 268.0), (hy1 + 40.0, 268.0), (hy1 + 40.0, 290.0), (hy0 - 40.0, 300.0)], 'x',
          hx0 - 320.0, hx0 + 40.0)
    cyl(mb, M_HIERRO, (hx0 - 60.0, hy1 - 40.0, 280.0), (hx0 - 60.0, hy1 - 40.0, 360.0), 5.0, 8)
    cbox(mb, 'MI_Madera', hx0 + 40.0, hx0 + 80.0, hy0 + 20.0, hy1 - 20.0, 40.0, 46.0, 1.0, 'y')
    mb.col(hx0 - 300.0, hx0, hy0, hy1, 0.0, 300.0)
    # casilla del guardabarrera: banda verde, luz encendida detrás de la ventana y farol sobre la puerta
    box(mb, 'MI_Metal_Verde', hx0 - 2.0, hx0, hy0, hy1, 245.0, 268.0)
    box(mb, 'MI_Emisivo_Calido', hx0 + 8.0, hx0 + 10.0, hy0 + 172.0, hy0 + 228.0, 112.0, 188.0)
    cbox(mb, M_HIERRO, hx0 - 22.0, hx0, hy0 + 92.0, hy0 + 108.0, 222.0, 246.0, 1.0, 'z')
    box(mb, 'MI_Emisivo_Calido', hx0 - 20.0, hx0 - 17.0, hy0 + 94.0, hy0 + 106.0, 226.0, 240.0)
    # balasto desparramado y yuyos en los márgenes del cruce (sin colisión)
    for (xa, xb) in ((-1600.0, -60.0), (W + 60.0, W + 1600.0)):
        for (ya_, yb_) in ((120.0, ya - 200.0), (yb + 200.0, Ly - 120.0)):
            for j in range(9):
                pts = k.jitter_poly(rng, rng.uniform(xa + 100.0, xb - 100.0), rng.uniform(ya_ + 40.0, yb_ - 40.0),
                                    rng.uniform(60.0, 200.0), rng.uniform(40.0, 120.0), rng.randint(7, 10), 20.0)
                prism(mb, rng.choice(['MI_Balasto', 'MI_Pasto', 'MI_Tierra']), pts, 'z', -1.0, rng.uniform(0.6, 3.0))
            for j in range(14):
                blob(mb, 'MI_Follaje', (rng.uniform(xa + 40.0, xb - 40.0), rng.uniform(ya_, yb_), 0.0),
                     rng.uniform(14.0, 34.0), rng.uniform(12.0, 30.0), rng.uniform(25.0, 70.0), yaw=rng.uniform(0, 180),
                     steps=(4, 6))
    # cruces de San Andrés también del lado del barrio (se leen desde la calle paralela a 60 m)
    _cruz_san_andres(mb, W + 70.0, -260.0, -90.0)
    _cruz_san_andres(mb, -70.0, -260.0, -90.0)
    return mb


# =====================================================================================
# PASARELAS (E2 y provisoria)
# =====================================================================================
def build_pasarela(cfg, provisoria=False):
    """Pasarela peatonal sobre las vías con escaleras en dos tramos (append_linear_stairs) y jaula de
    alambrado alta. Actor en el origen (mundo)."""
    mb = MB('Pasarela' + ('Provisoria' if provisoria else ''))
    dk = 'MI_Madera' if provisoria else 'MI_Hormigon'
    st = 'MI_Chapa_Gris' if provisoria else 'MI_Hormigon'
    beam = M_HIERRO
    cage = 'MI_Alambrado'
    x0, x1 = cfg['deck_x']
    y0, y1 = cfg['deck_y']
    Z = cfg['z']
    w = cfg['w']
    box(mb, dk, x0, x1, y0, y1, Z - 25.0, Z)
    mb.col(x0, x1, y0, y1, Z - 25.0, Z)
    for xb in (x0 + 10.0, x1 - 10.0):
        box(mb, beam, xb - 10.0, xb + 10.0, y0, y1, Z - 95.0, Z - 25.0)
    yy = y0 + 300.0
    while yy < y1 - 100.0:
        box(mb, beam, x0, x1, yy - 6.0, yy + 6.0, Z - 90.0, Z - 25.0)
        yy += 600.0
    # columnas (fuera del balasto)
    for yc in (y0 + 120.0, BAL_Y[0] - 260.0, BAL_Y[1] + 260.0, y1 - 120.0):
        for xc in (x0 + 15.0, x1 - 15.0):
            if provisoria:
                cyl(mb, beam, (xc, yc, -1.0), (xc, yc, Z - 95.0), 6.0, 10)
                cyl(mb, beam, (xc, yc - 100.0, 0.0), (xc, yc + 100.0, Z - 100.0), 2.5, 6)
            else:
                box(mb, beam, xc - 15.0, xc + 15.0, yc - 15.0, yc + 15.0, -1.0, Z - 95.0)
                box(mb, 'MI_Hormigon', xc - 35.0, xc + 35.0, yc - 35.0, yc + 35.0, -1.0, 30.0)
            mb.col(xc - 15.0, xc + 15.0, yc - 15.0, yc + 15.0, 0.0, Z - 95.0)
    # jaula: paños de alambrado de 1,9 m, postes cada 250, pasamanos; aberturas donde llegan las escaleras
    openings = []
    for s in cfg['stairs']:
        tx, ty = s['top']
        openings.append((tx, ty - w * 0.5, ty + w * 0.5))
    for (xe, side) in ((x0, -1.0), (x1, 1.0)):
        gaps = [(a, b) for (tx, a, b) in openings if abs(tx - xe) < 1.0]
        for (a, b) in k.interval_minus(y0, y1, gaps):
            box(mb, cage, xe - 1.0, xe + 1.0, a, b, Z, Z + 190.0)
            box(mb, beam, xe - 3.0, xe + 3.0, a, b, Z + 186.0, Z + 192.0)
            box(mb, beam, xe - 2.5, xe + 2.5, a, b, Z + 95.0, Z + 99.0)
            yy = a
            while yy <= b:
                box(mb, beam, xe - 3.0, xe + 3.0, yy - 3.0, yy + 3.0, Z, Z + 192.0)
                yy += 250.0
            mb.col(xe - 5.0, xe + 5.0, a, b, Z, Z + 195.0)
    for ye in (y0, y1):
        box(mb, cage, x0, x1, ye - 1.0, ye + 1.0, Z, Z + 190.0)
        box(mb, beam, x0, x1, ye - 3.0, ye + 3.0, Z + 186.0, Z + 192.0)
        mb.col(x0, x1, ye - 5.0, ye + 5.0, Z, Z + 195.0)
    if provisoria:
        for ye in (y0 + 400.0, 0.5 * (y0 + y1), y1 - 400.0):
            box(mb, 'MI_Cartel_Rojo', x0 - 2.0, x0 - 1.4, ye - 300.0, ye + 300.0, Z + 20.0, Z + 120.0)
    # escaleras: tramo inferior + descanso + tramo superior
    for s in cfg['stairs']:
        tx, ty = s['top']
        dx = s['dir'][0]
        h_, d_, n_ = 17.5, 28.0, 20
        run = n_ * d_
        xbot = tx + dx * L.STAIR_RUN
        xland0 = tx + dx * run
        xland1 = tx + dx * (L.STAIR_RUN - run)
        k.stairs_flight(mb, st, (xbot, ty, 0.0), (-dx, 0.0), w, n_, h_, d_)
        box(mb, st, min(xland0, xland1), max(xland0, xland1), ty - w * 0.5, ty + w * 0.5, Z * 0.5 - 20.0, Z * 0.5)
        mb.col(min(xland0, xland1), max(xland0, xland1), ty - w * 0.5, ty + w * 0.5, Z * 0.5 - 20.0, Z * 0.5)
        k.stairs_flight(mb, st, (xland0, ty, Z * 0.5), (-dx, 0.0), w, n_, h_, d_)
        for xc in (xland0, xland1):
            for yc in (ty - w * 0.5 + 12.0, ty + w * 0.5 - 12.0):
                box(mb, beam, xc - 8.0, xc + 8.0, yc - 8.0, yc + 8.0, -1.0, Z * 0.5 - 20.0)
        # zancas y jaula inclinada a ambos lados
        flights = [((xbot, 0.0), (xland1, Z * 0.5)), ((xland0, Z * 0.5), (tx, Z))]
        for (pa, pb) in flights:
            for yside in (ty - w * 0.5 - 4.0, ty + w * 0.5 + 4.0):
                prism(mb, beam, [(pa[0], pa[1] - 30.0), (pb[0], pb[1] - 30.0), (pb[0], pb[1] + 8.0), (pa[0], pa[1] + 8.0)],
                      'y', yside - 3.0, yside + 3.0)
                panel = [(pa[0], pa[1]), (pb[0], pb[1]), (pb[0], pb[1] + 185.0), (pa[0], pa[1] + 185.0)]
                prism(mb, cage, panel, 'y', yside - 0.8, yside + 0.8)
                mb.ramp(panel, 'y', yside - 4.0, yside + 4.0)
                tube(mb, beam, [(pa[0], yside, pa[1] + 95.0), (pb[0], yside, pb[1] + 95.0)], 2.2, 6)
                tube(mb, beam, [(pa[0], yside, pa[1] + 188.0), (pb[0], yside, pb[1] + 188.0)], 2.5, 6)
                n = int(abs(pb[0] - pa[0]) // 140.0) + 1
                for j in range(n + 1):
                    t = j / float(n)
                    xx = pa[0] + (pb[0] - pa[0]) * t
                    zz = pa[1] + (pb[1] - pa[1]) * t
                    box(mb, beam, xx - 2.5, xx + 2.5, yside - 2.5, yside + 2.5, zz, zz + 190.0)
        for yside in (ty - w * 0.5 - 4.0, ty + w * 0.5 + 4.0):
            box(mb, cage, min(xland0, xland1), max(xland0, xland1), yside - 0.8, yside + 0.8, Z * 0.5, Z * 0.5 + 185.0)
            mb.col(min(xland0, xland1), max(xland0, xland1), yside - 4.0, yside + 4.0, Z * 0.5, Z * 0.5 + 190.0)
        # pie de escalera: losa de llegada
        xb2 = xbot + dx * 160.0
        box(mb, 'MI_Hormigon', min(xbot, xb2), max(xbot, xb2), ty - w * 0.5 - 40.0, ty + w * 0.5 + 40.0, -1.0, Z_VER)
        mb.col(min(xbot, xb2), max(xbot, xb2), ty - w * 0.5 - 40.0, ty + w * 0.5 + 40.0, -1.0, Z_VER)
    return mb


# =====================================================================================
# CABLES POR TRAMO DE CALLE
# =====================================================================================
def pole_anchor(pole_actor_info, local):
    """Punto local de un poste colocado (loc, rot) -> mundo con la matemática del motor."""
    return k.world_pt(pole_actor_info['loc'], pole_actor_info['rot'], local)


def build_cables_group(name, poles, houses, seed):
    """poles: lista de dict(loc, rot, kind, side_id, along) colocados; houses: lista de dict(power, tel, side_id,
    along) en mundo. Cables de baja tensión, 2-3 haces de 6+ cables de telecomunicaciones con rulos,
    cruces diagonales, acometidas y bajadas. Actor en el origen."""
    rng = random.Random(seed)
    mb = MB(name)
    if len(poles) < 2:
        return None
    sides = {}
    for p in poles:
        sides.setdefault(p['side_id'], []).append(p)
    for sid in sides:
        sides[sid].sort(key=lambda p: p['along'])

    def ins(p, i):
        d = P.POLE2[p['kind']]
        xi = d['ins'][i % len(d['ins'])]
        return pole_anchor(p, (xi, 0.0, d['za'] + 13.0))

    def telpt(p, idx, toward):
        d = P.POLE2[p['kind']]
        z = d['tel'][idx % len(d['tel'])]
        c = pole_anchor(p, (0.0, 0.0, z))
        dx, dy = toward[0] - c[0], toward[1] - c[1]
        l = math.hypot(dx, dy) or 1.0
        r = P.pole_r(p['kind'], z) + 2.0
        return (c[0] + dx / l * r, c[1] + dy / l * r, c[2] + rng.uniform(-3.0, 3.0))

    def add(p0, p1, sag, r=0.45, sides_=5):
        tube(mb, 'MI_Cable', k.catenary(p0, p1, sag), r, sides_)
    lum_poles = []
    for sid, lst in sides.items():
        # línea de baja tensión entre postes con cruceta
        lp = [p for p in lst if p['kind'] == 'lum']
        lum_poles += lp
        for i in range(len(lp) - 1):
            a, b = lp[i], lp[i + 1]
            for q in range(4):
                add(ins(a, q), ins(b, q), rng.uniform(40.0, 95.0), 0.55, 6)
        # haces de telecomunicaciones: 1-2 haces de 3-5 cables finos (0,6-1 cm), flechas de 20 a 180 cm
        for i in range(len(lst) - 1):
            a, b = lst[i], lst[i + 1]
            nh = rng.randint(1, 2)
            for h in range(nh):
                base_sag = rng.uniform(20.0, 160.0)
                nc = rng.randint(3, 5)
                pa0 = telpt(a, h * 2, b['loc'])
                pb0 = telpt(b, h * 2 + rng.randint(0, 1), a['loc'])
                for c in range(nc):
                    off = (rng.uniform(-4, 4), rng.uniform(-4, 4), rng.uniform(-5, 5))
                    sag = min(180.0, max(20.0, base_sag + rng.uniform(-15.0, 25.0)))
                    add(k.v_add(pa0, off), k.v_add(pb0, (off[0], off[1], off[2] + rng.uniform(-3, 3))), sag,
                        rng.choice((0.3, 0.35, 0.4, 0.45, 0.5)), 4)
                # rulo de reserva colgando a mitad del vano (a veces)
                if rng.random() < 0.2:
                    t = rng.uniform(0.3, 0.7)
                    mid = k.v_lerp(pa0, pb0, t)
                    mid = (mid[0], mid[1], mid[2] - base_sag * 4.0 * t * (1 - t) - 25.0)
                    dx, dy = pb0[0] - pa0[0], pb0[1] - pa0[1]
                    l = math.hypot(dx, dy) or 1.0
                    torus(mb, 'MI_Cable', mid, rng.uniform(18.0, 28.0), 0.4, (dx / l, dy / l, 0.0), 16, 4)
            # haz grueso preensamblado
            if rng.random() < 0.6:
                add(telpt(a, 1, b['loc']), telpt(b, 1, a['loc']), rng.uniform(35.0, 60.0), 0.6, 6)
    # cruces diagonales sobre la calle (de un lado al otro, corridos a lo largo)
    sids = list(sides.keys())
    if len(sids) >= 2:
        A, B = sides[sids[0]], sides[sids[1]]
        for j in range(rng.randint(1, 2)):
            a = rng.choice(A)
            cand = [b for b in B if 700.0 < abs(b['along'] - a['along']) < 3200.0]
            if not cand:
                continue
            b = rng.choice(cand)
            for c in range(rng.randint(1, 2)):
                add(telpt(a, rng.randint(0, 4), b['loc']), telpt(b, rng.randint(0, 4), a['loc']),
                    rng.uniform(60.0, 180.0), rng.choice((0.3, 0.4, 0.5)), 4)
    # acometidas de energía y bajadas de telecomunicaciones
    for h in houses:
        if h.get('power') is not None and lum_poles:
            src_p = min(lum_poles, key=lambda p: (p['loc'][0] - h['power'][0]) ** 2 + (p['loc'][1] - h['power'][1]) ** 2)
            src = ins(src_p, 0 if rng.random() < 0.5 else 3)
            Lc = k.v_len(k.v_sub(h['power'], src))
            if Lc < 5000.0:
                add(src, h['power'], max(10.0, Lc * rng.uniform(0.03, 0.05)), 0.45, 5)
                if rng.random() < 0.25:
                    add(ins(src_p, 1), k.v_add(h['power'], (0.0, 0.0, -5.0)), max(12.0, Lc * 0.06), 0.35, 4)
        for t in h.get('tel', []):
            near = min(poles, key=lambda p: (p['loc'][0] - t[0]) ** 2 + (p['loc'][1] - t[1]) ** 2)
            src = telpt(near, rng.randint(2, 5), t)
            Lc = k.v_len(k.v_sub(t, src))
            if Lc < 4500.0:
                add(src, t, Lc * rng.uniform(0.03, 0.08), rng.choice((0.3, 0.35)), 4)
                box(mb, M_HIERRO, t[0] - 1.5, t[0] + 1.5, t[1] - 1.5, t[1] + 1.5, t[2] - 2.0, t[2] + 2.0)
    # lazos sueltos colgando de algunos postes
    for p in rng.sample(poles, min(len(poles), 2)):
        d = P.POLE2[p['kind']]
        c = pole_anchor(p, (0.0, 0.0, d['tel'][-1]))
        a = rng.uniform(0, 2 * math.pi)
        p0 = (c[0] + 13.0 * math.cos(a), c[1] + 13.0 * math.sin(a), c[2])
        p1 = (c[0] + 60.0 * math.cos(a), c[1] + 60.0 * math.sin(a), c[2] - rng.uniform(200.0, 380.0))
        p2 = (c[0] + 20.0 * math.cos(a) + 8.0, c[1] + 20.0 * math.sin(a), c[2] - 70.0)
        tube(mb, 'MI_Cable', k.bezier(p0, p1, p2, 14), 0.35, 4)
    return mb


# =====================================================================================
# SEMICORTES DE CALZADA (cortes de visual que cruzan el eje de la calle)
#   Marco: +X a lo largo de la calle, +Y hacia la vereda, origen en la cara del cordón, z = 0 calzada.
#   Ocupan la calzada hacia -Y (huellas en barrio_layout.CUT_FOOT) y dejan >= 3,8 m libres del otro lado.
# =====================================================================================
def _baliza_obra(mb, x, y, z):
    cyl(mb, M_HIERRO, (x, y, z), (x, y, z + 8.0), 4.0, 8)
    blob(mb, 'MI_Emisivo_Baliza_Roja', (x, y, z + 14.0), 7.0, 7.0, 7.0, steps=(5, 7))


def _zanja(mb, rng, hx, b):
    """Zanja de cloaca / agua con tapial de chapa en tres lados y vallas del lado del cordón."""
    y0, y1 = -640.0, -140.0
    tapial_obra(mb, -hx, y1 - 6.0, -hx, y0, 220.0, False)
    tapial_obra(mb, hx, y0, hx, y1 - 6.0, 220.0, False)
    tapial_obra(mb, -hx, y0, hx, y0, 220.0, True)
    for x in (-hx + 15.0, 0.0):
        P.k_valla(mb, x + 10.0, y1, x + hx - 20.0, y1)
    mb.col(-hx, hx, y1 - 4.0, y1 + 4.0, 0.0, 105.0)
    # la zanja (fondo oscuro), tierra sacada, caños, tablones
    box(mb, 'MI_Tierra', -hx + 20.0, hx - 20.0, y0 + 10.0, y1 - 10.0, 0.0, 5.5)
    box(mb, 'MI_Plastico_Negro', -hx + 90.0, hx * 0.3, y0 + 140.0, y0 + 260.0, 5.0, 5.8)
    for (a0, a1, c0, c1) in ((-hx + 80.0, hx * 0.3 + 10.0, y0 + 130.0, y0 + 140.0),
                             (-hx + 80.0, hx * 0.3 + 10.0, y0 + 260.0, y0 + 270.0)):
        box(mb, 'MI_Madera', a0, a1, c0, c1, 4.0, 12.0)
    cone(mb, 'MI_Tierra', (hx * 0.55, y0 + 230.0, 0.0), (hx * 0.55 + 10.0, y0 + 235.0, 115.0), 125.0, 18.0, 14)
    mb.col(hx * 0.55 - 90.0, hx * 0.55 + 90.0, y0 + 150.0, y0 + 310.0, 0.0, 100.0)
    if b:
        # generador y pila de ladrillos
        cbox(mb, 'MI_Pintura_Amarilla', -hx + 60.0, -hx + 170.0, y1 - 150.0, y1 - 70.0, 0.0, 90.0, 3.0, 'z')
        for j in range(5):
            box(mb, 'MI_Ladrillo', -40.0, 80.0, y1 - 170.0 + (j % 2) * 3.0, y1 - 70.0, j * 24.0, j * 24.0 + 22.0)
        mb.col(-hx + 60.0, 80.0, y1 - 170.0, y1 - 70.0, 0.0, 120.0)
    else:
        for j in range(3):
            z = 15.0 + j * 31.0
            cyl(mb, 'MI_Cartel_Rojo', (-hx + 60.0, y1 - 90.0 - (j % 2) * 16.0, z), (hx * 0.4, y1 - 90.0 - (j % 2) * 16.0, z),
                15.0, 12)
        mb.col(-hx + 60.0, hx * 0.4, y1 - 110.0, y1 - 70.0, 0.0, 95.0)
        cyl(mb, 'MI_Metal_Verde', (hx - 80.0, y1 - 80.0, 0.0), (hx - 80.0, y1 - 80.0, 88.0), 29.0, 14)
    for (x, y) in ((-hx, y0), (hx, y0), (-hx, y1), (hx, y1)):
        _baliza_obra(mb, x, y, 220.0 if y == y0 else 105.0)
    for (x, y) in ((-hx - 80.0, y1 + 20.0), (hx + 80.0, y1 + 20.0), (-hx - 60.0, y0 + 80.0), (hx + 60.0, y0 + 80.0)):
        P.k_cono(mb, x, y, 2.0)


def _camion_con_carga(mb, rng, kind):
    """Camión estacionado en doble fila (cruza el eje) con la carga en la calzada del lado del cordón."""
    P_cam = P.build_camion()
    k.merge_mb(mb, P_cam, (0.0, -415.0, 0.0), 0.0)
    if kind == 'mudanza':
        # ropero, heladera, colchón apoyado, cajas apiladas, sillas
        box(mb, 'MI_Madera', -330.0, -230.0, -275.0, -215.0, 0.0, 190.0)
        box(mb, M_HIERRO, -232.0, -230.0, -270.0, -265.0, 90.0, 120.0)
        cbox(mb, 'MI_Pintura_Blanca', -200.0, -135.0, -270.0, -205.0, 0.0, 172.0, 3.0, 'z')
        rbox(mb, 'MI_Cartel_Blanco', -60.0, -235.0, 0.0, 190.0, 22.0, 150.0, 0.0, 0.0, -12.0)
        for (x, n) in ((70.0, 6), (140.0, 5), (210.0, 6)):
            for j in range(n):
                rbox(mb, 'MI_Madera', x + rng.uniform(-4, 4), -235.0 + rng.uniform(-4, 4), j * 30.0, 62.0, 52.0, 29.0,
                     rng.uniform(-6, 6))
        for x in (300.0, 345.0):
            box(mb, 'MI_Madera', x - 20.0, x + 20.0, -200.0, -160.0, 0.0, 45.0)
            box(mb, 'MI_Madera', x - 20.0, x + 20.0, -162.0, -158.0, 45.0, 95.0)
        mb.col(-330.0, 245.0, -280.0, -200.0, 0.0, 180.0)
    else:
        # pallets con cajones de bebida, zorra y conos
        for (x, n) in ((-260.0, 6), (-130.0, 5), (0.0, 6), (130.0, 4)):
            box(mb, 'MI_Madera', x - 55.0, x + 55.0, -285.0, -185.0, 0.0, 12.0)
            for j in range(n):
                m = 'MI_Cartel_Rojo' if (j + int(x)) % 2 == 0 else 'MI_Cartel_Azul'
                cbox(mb, m, x - 52.0, x + 52.0, -282.0, -188.0, 12.0 + j * 27.0, 12.0 + j * 27.0 + 26.0, 1.5, 'z')
        cyl(mb, M_HIERRO, (260.0, -230.0, 0.0), (250.0, -230.0, 130.0), 2.0, 6)
        box(mb, M_HIERRO, 235.0, 285.0, -250.0, -210.0, 0.0, 4.0)
        mb.col(-315.0, 185.0, -285.0, -185.0, 0.0, 175.0)
    for (x, y) in ((-470.0, -300.0), (450.0, -300.0)):
        P.k_cono(mb, x, y, 2.0)


def _arbol_caido(mb, rng):
    """Fresno caído en la tormenta: raíz en la cuneta, tronco cruzando media calzada, copa rota y cinta."""
    blob(mb, 'MI_Tierra', (0.0, 30.0, 30.0), 70.0, 22.0, 60.0, steps=(6, 8))
    for j in range(6):
        a = rng.uniform(0, 2 * math.pi)
        cyl(mb, 'MI_Corteza', (0.0, 25.0, 30.0), (math.cos(a) * 70.0, 35.0, 30.0 + math.sin(a) * 55.0), 3.0, 5)
    tip = (rng.uniform(-40.0, 40.0), -470.0, 45.0)
    cone(mb, 'MI_Corteza', (0.0, 10.0, 30.0), tip, 22.0, 13.0, 12)
    mb.col(-25.0, 25.0, -470.0, 40.0, 0.0, 60.0)
    # ramas principales y copa aplastada contra el asfalto
    for j in range(6):
        a = rng.uniform(-1.2, 1.2)
        L_ = rng.uniform(180.0, 300.0)
        p1 = (tip[0] + math.sin(a) * L_, tip[1] - math.cos(a) * L_ * 0.6, rng.uniform(60.0, 200.0))
        cyl(mb, 'MI_Corteza', (tip[0] + rng.uniform(-30, 30), tip[1] + rng.uniform(0, 120), 45.0), p1, 6.0, 6)
        for q in range(3):
            c_ = (p1[0] + rng.uniform(-60, 60), p1[1] + rng.uniform(-60, 60), max(60.0, p1[2] + rng.uniform(-40, 40)))
            blob(mb, 'MI_Follaje', c_, rng.uniform(55.0, 90.0), rng.uniform(50.0, 85.0), rng.uniform(45.0, 75.0),
                 yaw=rng.uniform(0, 180), steps=(6, 8))
    for q in range(5):
        blob(mb, 'MI_Follaje', (rng.uniform(-250, 250), rng.uniform(-690, -380), rng.uniform(40.0, 110.0)),
             rng.uniform(60.0, 100.0), rng.uniform(50.0, 90.0), rng.uniform(50.0, 90.0), yaw=rng.uniform(0, 180),
             steps=(6, 8))
    mb.col(-300.0, 300.0, -700.0, -330.0, 0.0, 200.0)
    # hojas sueltas y vallas con cinta a los costados
    for q in range(10):
        blob(mb, 'MI_Follaje', (rng.uniform(-320, 320), rng.uniform(-720, -60), 3.0), rng.uniform(20.0, 45.0),
             rng.uniform(15.0, 35.0), rng.uniform(4.0, 9.0), yaw=rng.uniform(0, 180), steps=(4, 6))
    P.k_valla(mb, -330.0, -60.0, -330.0, -420.0)
    P.k_valla(mb, 330.0, -420.0, 330.0, -60.0)
    for x in (-330.0, 330.0):
        mb.col(x - 4.0, x + 4.0, -420.0, -60.0, 0.0, 105.0)
    tube(mb, 'MI_Cartel_Rojo', [(-330.0, -420.0, 95.0), (0.0, -740.0, 90.0), (330.0, -420.0, 95.0)], 0.8, 4)


def build_semicorte(kind):
    """Semicorte de calzada: 'zanja' / 'zanja_b' (las dos mitades de una obra en chicana), 'mudanza', 'reparto'
    (camión en doble fila con la carga) o 'arbol_caido'. Marco del comentario de la sección."""
    rng = random.Random(sum(ord(ch) * (i + 1) for i, ch in enumerate(kind)))
    mb = MB('Semicorte_' + kind)
    if kind == 'zanja':
        _zanja(mb, rng, 360.0, False)
    elif kind == 'zanja_b':
        _zanja(mb, rng, 300.0, True)
    elif kind in ('mudanza', 'reparto'):
        _camion_con_carga(mb, rng, kind)
    else:
        _arbol_caido(mb, rng)
    return mb


# =====================================================================================
# SALIDAS: marca diegética única (tótem verde con luz verde y flecha), franjas y coberturas de aproximación
# =====================================================================================
TOTEM_LUZ_Z = (338.0, 362.0)


def build_marcas_salida():
    """Los tótems de las tres salidas (L.salida_totems) y las franjas verdes del piso (L.salida_lines), en una
    sola malla en mundo. La luz va aparte (build_luces_salida) para poder cambiarle el material."""
    mb = MB('MarcasSalida')
    for (x, y, ayaw) in L.salida_totems():
        cbox(mb, 'MI_Hormigon', x - 32.0, x + 32.0, y - 32.0, y + 32.0, -4.0, 22.0, 2.0, 'z')
        cbox(mb, 'MI_Cartel_Verde', x - 17.0, x + 17.0, y - 17.0, y + 17.0, 22.0, TOTEM_LUZ_Z[0] - 6.0, 1.5, 'z')
        for z in (120.0, 250.0):
            box(mb, 'MI_Pintura_Blanca', x - 17.6, x + 17.6, y - 17.6, y + 17.6, z, z + 14.0)
        # flecha blanca hacia Afuera en las dos caras laterales (chevron, sin texto)
        c, s_ = math.cos(math.radians(ayaw)), math.sin(math.radians(ayaw))
        for side in (1.0, -1.0):
            nx, ny = -s_ * side, c * side
            for (u0, w0) in ((-9.0, 1.0), (-9.0, -1.0)):
                px = x + nx * 17.8 + c * (u0 + 6.0)
                py = y + ny * 17.8 + s_ * (u0 + 6.0)
                rbox(mb, 'MI_Pintura_Blanca', px, py, 175.0 + w0 * 14.0, 24.0, 0.8, 6.0, ayaw, 0.0, w0 * -40.0 * side)
        box(mb, M_HIERRO, x - 21.0, x + 21.0, y - 21.0, y + 21.0, TOTEM_LUZ_Z[0] - 6.0, TOTEM_LUZ_Z[0])
        box(mb, M_HIERRO, x - 19.0, x + 19.0, y - 19.0, y + 19.0, TOTEM_LUZ_Z[1], TOTEM_LUZ_Z[1] + 6.0)
        for (dx, dy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            box(mb, M_HIERRO, x + dx * 16.0 - 2.0, x + dx * 16.0 + 2.0, y + dy * 16.0 - 2.0, y + dy * 16.0 + 2.0,
                TOTEM_LUZ_Z[0], TOTEM_LUZ_Z[1])
        mb.col(x - 20.0, x + 20.0, y - 20.0, y + 20.0, 0.0, TOTEM_LUZ_Z[1] + 6.0)
    for (x0, x1, y0, y1, z0, z1) in L.salida_lines():
        box(mb, 'MI_Cartel_Verde', x0, x1, y0, y1, z0, z1)
    return mb


def build_luces_salida():
    """Faroles de los tótems de salida. Slot MI_Emisivo_Calido: build_barrio lo cambia por MI_Emisivo_Verde si
    existe (la luz verde de la marca); si no, quedan encendidos en cálido."""
    mb = MB('LucesSalida')
    for (x, y, ayaw) in L.salida_totems():
        cyl(mb, 'MI_Emisivo_Calido', (x, y, TOTEM_LUZ_Z[0] + 1.0), (x, y, TOTEM_LUZ_Z[1] - 1.0), 14.0, 12)
    return mb


def _kiosco_cobertura(mb, x, y, yaw, rng):
    """Kiosco de chapa verde (frente con persiana y heladera), 2,2 x 1,5 m: cobertura alta."""
    x0, x1, y0, y1, top = L.COVER_FOOT['kiosco']
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    rbox(mb, 'MI_Chapa_Verde', x, y, 0.0, x1 - x0, y1 - y0, 232.0, yaw)
    rbox(mb, 'MI_Chapa_Gris', x, y, 232.0, x1 - x0 + 40.0, y1 - y0 + 50.0, 12.0, yaw)
    fx, fy = x + c * (x1 + 1.0), y + s_ * (x1 + 1.0)
    rbox(mb, 'MI_Cartel_Rojo', fx, fy, 205.0, 2.0, y1 - y0 - 10.0, 24.0, yaw)
    rbox(mb, 'MI_Chapa_Gris', fx, fy, 20.0, 2.0, y1 - y0 - 20.0, 175.0, yaw)
    for j in range(5):
        rbox(mb, ['MI_Cartel_Azul', 'MI_Cartel_Blanco', 'MI_Pintura_Amarilla'][j % 3], x - s_ * (y1 + 1.0) + c * (j * 30.0 - 60.0),
             y + c * (y1 + 1.0) + s_ * (j * 30.0 - 60.0), 60.0 + (j % 2) * 40.0, 24.0, 1.0, 30.0, yaw)
    pts = [(x + px * c - py * s_, y + px * s_ + py * c) for (px, py) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    mb.ramps.append((pts, 'z', 0.0, top))


def _garita_cobertura(mb, x, y, yaw):
    """Garita de vigilancia de mampostería con ventana corrida y techito de chapa, 1,6 x 1,6 m."""
    x0, x1, y0, y1, top = L.COVER_FOOT['garita']
    box(mb, 'MI_Revoque_Blanco', x + x0, x + x1, y + y0, y + y1, 0.0, 115.0)
    box(mb, 'MI_Vidrio', x + x0 + 2.0, x + x1 - 2.0, y + y0 + 2.0, y + y1 - 2.0, 115.0, 215.0)
    for (dx, dy) in ((x0, y0), (x1 - 8.0, y0), (x1 - 8.0, y1 - 8.0), (x0, y1 - 8.0)):
        box(mb, 'MI_Revoque_Blanco', x + dx, x + dx + 8.0, y + dy, y + dy + 8.0, 115.0, 240.0)
    box(mb, 'MI_Revoque_Blanco', x + x0, x + x1, y + y0, y + y1, 215.0, 240.0)
    cbox(mb, 'MI_Chapa_Gris', x + x0 - 20.0, x + x1 + 20.0, y + y0 - 20.0, y + y1 + 20.0, 240.0, top, 2.0, 'y')
    box(mb, 'MI_Emisivo_Calido', x - 20.0, x + 20.0, y - 20.0, y + 20.0, 236.0, 239.0)
    mb.col(x + x0, x + x1, y + y0, y + y1, 0.0, top)


def build_coberturas_salida(seed):
    """Coberturas en la aproximación a las tres salidas (kiosco, garita) y el cartel de la parada de remís junto
    a E1. Actor en el origen (mundo)."""
    rng = random.Random(seed)
    mb = MB('CoberturasSalida')
    for (kind, (x, y), yaw) in L.SALIDA_COVERS:
        if kind == 'kiosco':
            _kiosco_cobertura(mb, x, y, yaw, rng)
        else:
            _garita_cobertura(mb, x, y, yaw)
    px, py = L.REMIS['pole']
    cyl(mb, M_HIERRO, (px, py, 0.0), (px, py, 280.0), 3.0, 8)
    cbox(mb, 'MI_Cartel_Azul', px - 3.0, px + 3.0, py - 35.0, py + 35.0, 210.0, 275.0, 1.0, 'z')
    box(mb, 'MI_Cartel_Blanco', px - 3.4, px + 3.4, py - 28.0, py + 28.0, 220.0, 265.0)
    # banco de la remisería y silla de plástico
    box(mb, 'MI_Madera', px - 160.0, px + 40.0, py - 40.0, py - 4.0, 42.0, 46.0)
    for xx in (px - 150.0, px + 30.0):
        box(mb, M_HIERRO, xx - 3.0, xx + 3.0, py - 38.0, py - 6.0, Z_VER, 42.0)
    return mb
