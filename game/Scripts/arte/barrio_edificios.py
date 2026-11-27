# -*- coding: utf-8 -*-
"""
barrio_edificios.py  -  Lo que faltaba del mapa jugable (MAPA.md): variantes PH y de esquina, comisaría
con hall accesible y celda, torre de 12 pisos (hito NE), plaza, terreno baldío, pasillos de PH, relleno de
fondos de manzana, Afuera Norte (estación, andén, explanada con refugio de llegada, calle de la estación,
galpón del reducidor, playón, avenida norte), Afuera Este (obra de la pasarela provisoria), bordes
(tapial y club al oeste, galpones al sur), edificios bajos y torres de fondo (skyline).

Igual que barrio_geo / barrio_props: cada build_* devuelve un MB (barrio_kit) y no toca actores; el
docstring dice dónde va el actor. Los "*_layout()" / "*_lums()" son Python puro (posiciones fijas) que
usa build_barrio.py para instanciar props, luminarias (contrato LUM_<n>) y actores de juego.

Convención de marcos de lote (igual que el kit): +x hacia la calle, la línea municipal en x = 0, y a lo
largo del frente, z arriba.
"""

import math
import random

import barrio_kit as k
from barrio_kit import MB, box, cbox, prism, cyl, cone, blob, tube, rbox, M_HIERRO
import barrio_layout as L
import barrio_props as P
import barrio_geo as G

Z_VER = L.Z_VER
LOT = L.LOT
OCH = L.OCHAVA
SQ2 = math.sqrt(2.0)


# =====================================================================================
# HELPERS
# =====================================================================================
def facade_run(dst, p0, nyaw, Lr, z0, z1, wm, holes=(), open_holes=(), t=30.0, deco=None, coll=True):
    """Muro recto armado en un marco temporal (x = normal hacia afuera, cara en x = 0, espesor hacia -x,
    y de 0 a Lr) y sumado a dst con origen p0 y yaw de la normal. deco(mb) agrega puertas, ventanas, etc.
    en el marco temporal. coll: colisión del muro (los open_holes quedan pasables). wm=None: sin muro.
    No usar con el espejado del kit encendido (merge_mb no espeja)."""
    mb = MB('tmp_fachada')
    try:
        if wm is not None and z1 - z0 > 0.5:
            k.wall_holes(mb, wm, -t, 0.0, 0.0, Lr, z0, z1, list(holes))
            if coll:
                for (a0, a1, b0, b1) in k.rect_minus(0.0, Lr, z0, z1, list(open_holes)):
                    mb.col(-t, 0.0, a0, a1, b0, b1)
        if deco is not None:
            deco(mb)
    except Exception:
        mb.release()
        raise
    k.merge_mb(dst, mb, (p0[0], p0[1], p0[2] if len(p0) > 2 else 0.0), nyaw)


def face_patches(mb, rng, axis, coord, sign, a0, a1, z0, z1, mats, n=8):
    """Parches de revoque / ladrillo sobre una cara plana (medianeras). axis 'x': cara x = coord."""
    if a1 - a0 < 120.0 or z1 - z0 < 120.0:
        return
    for j in range(n):
        w = rng.uniform(60.0, min(260.0, a1 - a0 - 60.0))
        h = rng.uniform(40.0, min(180.0, z1 - z0 - 60.0))
        a = rng.uniform(a0 + 30.0, a1 - 30.0 - w)
        z = rng.uniform(z0 + 30.0, z1 - 30.0 - h)
        t0, t1 = coord - sign * 1.0, coord + sign * 1.2
        m = rng.choice(mats)
        if axis == 'x':
            box(mb, m, t0, t1, a, a + w, z, z + h)
        else:
            box(mb, m, a, a + w, t0, t1, z, z + h)


def stable_hash(s):
    h = 2166136261
    for ch in str(s):
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


# =====================================================================================
# VARIANTE PH (lote de 866 con pasillo de 2 m hacia el corazón de la manzana)
# =====================================================================================
def build_ph(W=LOT, depth=860.0):
    """Casa de PH de un lote: frente de 6,66 m y pasillo abierto de 2 m (y 666..866) con tapial de 2,5 m del
    lado del vecino y pórtico de entrada (dintel a 2,62 m). Se espeja con el kit para PH_m."""
    mb = MB('PH')
    p0, p1 = L.VARIANTS['PH']['pasillo']
    t = L.PH_WALL
    Wh = p0
    wm, sm_ = 'MI_Revoque_Blanco', 'MI_Revoque_Gris'
    zr, zp = 340.0, 420.0
    door = (220.0, 310.0, k.Z_PISO, 240.0)
    win = (390.0, 590.0, 100.0, 235.0)
    win2 = (45.0, 165.0, 110.0, 235.0)
    k.piece('PH cascaron', k.shell, mb, Wh, 0.0, depth, zr, zp, wm, sm_, [door, k.win_hole(*win), k.win_hole(*win2)])
    k.piece('PH puerta', k.k_door, mb, 0.0, door[0], door[1], door[2], door[3],
            dict(hoja=k.M_PUERTA, estilo='chapa', aplique=True, umbral_mat='MI_Hormigon'))
    k.piece('PH ventana', k.k_window, mb, wm, 0.0, win[0], win[1], win[2], win[3],
            dict(reja='barrotes', persiana='enrollar', cerrada=0.6, moldura=wm, persiana_mat='MI_Madera'))
    k.piece('PH ventana2', k.k_window, mb, wm, 0.0, win2[0], win2[1], win2[2], win2[3],
            dict(reja='cuadricula', persiana=None))
    k.piece('PH zocalo', k.k_zocalo, mb, sm_, 0.0, 0.0, Wh, 50.0, [(door[0] - 6.0, door[1] + 6.0)])
    k.piece('PH cornisa', k.k_cornisa, mb, wm, 0.0, 0.0, Wh, zr - 16.0, 1)
    k.piece('PH numero', k.k_numero, mb, 0.0, 345.0, 205.0)
    k.piece('PH tanque', k.tanque_simple, mb, -depth + 250.0, 300.0, zr + 2.0)
    # piso del pasillo (sigue la vereda) y tapial del lado del vecino
    box(mb, 'MI_Hormigon', -depth, 0.0, p0, p1, -1.0, Z_VER + 1.0)
    mb.col(-depth, 0.0, p0, p1, -1.0, Z_VER + 1.0)
    box(mb, M_HIERRO, -45.0, -15.0, p0 + 25.0, p1 - t - 25.0, Z_VER + 0.4, Z_VER + 1.3)          # rejilla
    box(mb, sm_, -depth, 0.0, p1 - t, p1, 0.0, 250.0)
    k.piece('PH cupertina', k.k_coping_x, mb, 'MI_Hormigon', p1 - t, p1, -depth, 0.0, 250.0, -1)
    mb.col(-depth, 0.0, p1 - t, p1, 0.0, 250.0)
    # pórtico de entrada: pilar y dintel (2,62 m libres)
    cbox(mb, sm_, -30.0, 4.0, p1 - t - 12.0, p1, 0.0, 300.0, 1.0, 'z')
    cbox(mb, sm_, -30.0, 2.0, p0, p1 - t - 12.0, 262.0, 300.0, 1.0, 'y')
    mb.col(-30.0, 4.0, p0, p1, 262.0, 300.0)
    # reja de entrada abierta, rebatida contra el tapial (sin colisión: es fina y está pegada al muro)
    k.piece('PH reja', k.k_reja_plano, mb, M_HIERRO, p1 - t - 5.0, -118.0, -16.0, Z_VER + 3.0, 232.0, 'x', 11.0, 1.6,
            2.5, (110.0,))
    # medidores en fila sobre el tapial (típico de PH), aplique y plantas
    for j in range(3):
        xa = -150.0 - j * 58.0
        cbox(mb, 'MI_Chapa_Gris', xa - 24.0, xa + 24.0, p1 - t - 7.0, p1 - t, 120.0, 182.0, 0.8, 'z')
        box(mb, 'MI_Vidrio', xa - 9.0, xa + 9.0, p1 - t - 7.4, p1 - t - 7.0, 160.0, 174.0)
    cbox(mb, M_HIERRO, -420.0, -404.0, p1 - t - 6.0, p1 - t, 226.0, 242.0, 0.5, 'z')
    box(mb, 'MI_Vidrio', -419.0, -405.0, p1 - t - 12.0, p1 - t - 6.0, 228.0, 240.0)
    k.piece('PH planta', k.k_planta, mb, -320.0, p1 - t - 20.0, Z_VER + 1.0, 0.9, True)
    k.piece('PH planta2', k.k_planta, mb, -620.0, p1 - t - 20.0, Z_VER + 1.0, 1.1, True)
    mb.anchors = {'power': (20.0, 600.0, 420.0), 'tel': [(2.0, 100.0, 380.0)], 'xf': 0.0}
    return mb


# =====================================================================================
# ESQUINAS (lote de 866 x 866 con ochava de 4 m)
#   este lado: línea municipal x = 0 (y de c a S); lado anterior: línea y = 0 (x de -S a -c);
#   ochava de (0, c) a (-c, 0).
# =====================================================================================
def _corner_walls(mb, S, c, zp, sm_):
    box(mb, sm_, -S, 0.0, S - 15.0, S, 0.0, zp)                 # medianera con el lote 1 de este lado
    box(mb, sm_, -S, -S + 15.0, 0.0, S - 15.0, 0.0, zp)         # medianera con el lote 8 del lado anterior
    mb.col(-S, 0.0, c, S, 0.0, zp)
    mb.col(-S, -c, 0.0, c, 0.0, zp)
    mb.ramps.append(([(0.0, c), (-c, 0.0), (-c, c)], 'z', 0.0, zp))


def _cartel(mb, mat, y0, y1, z0, z1, proud=9.0):
    cbox(mb, mat, 0.0, proud, y0, y1, z0, z1, 1.0, 'y')
    box(mb, 'MI_Cartel_Blanco', proud, proud + 0.5, y0 + 14.0, y1 - 14.0, z0 + 10.0, z1 - 10.0)


def _vidriera_interior(mb, rng, y0, y1, zs, zt):
    for kk in range(3):
        zz = zs + 20.0 + kk * 55.0
        if zz + 30.0 > zt:
            break
        box(mb, k.M_ALUMINIO, -75.0, -45.0, y0 + 6.0, y1 - 6.0, zz, zz + 2.0)
        y = y0 + 10.0
        while y < y1 - 25.0:
            w = rng.uniform(10.0, 24.0)
            box(mb, rng.choice(['MI_Cartel_Rojo', 'MI_Cartel_Azul', 'MI_Cartel_Blanco', 'MI_Cartel_Verde']),
                -72.0, -50.0, y, y + w, zz + 2.0, zz + 2.0 + rng.uniform(12.0, 30.0))
            y += w + rng.uniform(2.0, 8.0)
    box(mb, 'MI_Emisivo_Calido', -122.0, -120.0, y0, y1, zt - 20.0, zt)


COMERCIO_SLOT = 'MI_Comercio_AlmacenDonTito'     # slot de la marquesina de EL (se cambia por instancia)


# =====================================================================================
# v5: EDIFICIO DE DEPARTAMENTOS ENTRE MEDIANERAS CON LOCAL EN PB (variantes F4 / F6 del layout)
# =====================================================================================
F_ZPB = 420.0          # planta baja comercial (local + palier)
F_HF = 290.0           # piso a piso
F_PRE = 105.0          # pretil de la azotea


def edificio_f_altura(pisos):
    """Altura total (cm) hasta el coronamiento del pretil: F4 = 1.705, F6 = 2.285."""
    return F_ZPB + pisos * F_HF + F_PRE


def build_edificio_f(W, depth=860.0, pisos=4):
    """Edificio de departamentos de los 70-90 (como los de 3 de Febrero, Belgrano y Mariano Moreno), lote de W.
    PB: local con cortina metálica + puerta vidriada + vidriera, marquesina con cartel de comercio (slot
    COMERCIO_SLOT, se cambia por instancia igual que la esquina EL) y palier con puerta de hierro y vidrio,
    portero, medidores. Pisos: losas con canto, balcón corrido con baranda (de caño o de mampostería según el
    edificio), puerta-balcón con persiana de enrollar + ventana, splits, ropa tendida, macetas. Azotea con
    tanque, sala de máquinas y antenas. Medianeras de ladrillo con estructura de hormigón a la vista que asoman
    por encima de los vecinos. Marco del kit (+x a la calle, LM en x=0, y 0..W). Slot de fachada MI_Revoque_Gris.
    Altura total: edificio_f_altura(pisos)."""
    rng = k.RNG
    mb = MB('EdificioF%d' % pisos)
    wm, sm_ = 'MI_Revoque_Gris', 'MI_Ladrillo'
    xf, xb = 0.0, -depth
    zr = F_ZPB + pisos * F_HF
    zp = zr + F_PRE
    # --- PB: local (y 30..0.55W), puerta del local, palier (y W-150..W-40), vidriera entre medio
    cort = (30.0, 0.50 * W, Z_VER, 290.0)
    door = (480.3, 570.3, k.Z_PISO, 240.0)              # la del layout (robable)
    pal = (W - 160.0, W - 50.0, k.Z_PISO, 255.0)
    vid = (door[1] + 40.0, pal[0] - 40.0, 70.0, 255.0)
    holes = [cort, door, pal]
    if vid[1] - vid[0] > 60.0:
        holes.append(k.win_hole(*vid))
    # --- pisos: puerta-balcón (izq) + ventana (der)
    ftype = rng.choice(('caño', 'mamposteria', 'mixto'))
    pb_y = (70.0, 70.0 + 220.0)
    vn_y = (W - 330.0, W - 90.0)
    for i in range(pisos):
        zf = F_ZPB + i * F_HF
        holes.append((pb_y[0], pb_y[1], zf + 2.0, zf + 225.0))
        holes.append(k.win_hole(vn_y[0], vn_y[1], zf + 95.0, zf + 225.0))
    floors = [F_ZPB + i * F_HF for i in range(pisos)]
    k.piece('F cascaron', k.shell, mb, W, xf, depth, zr, zp, wm, sm_, holes, floors, True, 'MI_Revoque_Gris', True,
            'MI_Hormigon')
    # --- medianeras: estructura de hormigón a la vista (columnas cada ~4,3 m y vigas por piso) + parches
    for (yf, sg) in ((0.0, -1.0), (W, 1.0)):
        x = xf - 15.0
        while x > xb:
            box(mb, 'MI_Hormigon', x - 28.0, x, min(yf - sg * 0.5, yf + sg * 1.5), max(yf - sg * 0.5, yf + sg * 1.5),
                0.0, zp)
            x -= 430.0
        for zf in floors + [zr]:
            box(mb, 'MI_Hormigon', xb, xf - 15.0, min(yf, yf + sg * 1.5), max(yf, yf + sg * 1.5), zf - 20.0, zf + 2.0)
        face_patches(mb, rng, 'y', yf, sg, xb + 60.0, xf - 60.0, F_ZPB + 300.0, zp - 40.0,
                     ['MI_Revoque_Gris', 'MI_Hormigon', 'MI_Revoque_Blanco'], n=7)
    # --- PB
    k.piece('F faja PB', cbox, mb, 'MI_Hormigon', xf - 1.0, xf + 3.0, 0.0, W, F_ZPB - 30.0, F_ZPB - 16.0, 0.8, 'y')
    k.piece('F cortina', k.k_cortina_local, mb, xf, cort[0], cort[1], cort[2], cort[3])
    cbox(mb, 'MI_Hormigon', xf - 30.0, xf + 1.0, cort[0] - 15.0, cort[1] + 15.0, cort[3], cort[3] + 18.0, 0.6, 'y')
    k.k_umbral(mb, 'MI_Hormigon', xf, cort[0], cort[1], Z_VER, Z_VER + 1.0)
    k.piece('F puerta local', k.k_door, mb, xf, door[0], door[1], door[2], door[3],
            dict(hoja='MI_Chapa_Gris', estilo='vidriada', marco=M_HIERRO, umbral_mat='MI_Hormigon'))
    if vid[1] - vid[0] > 60.0:
        k.piece('F vidriera', k.k_window, mb, wm, xf, vid[0], vid[1], vid[2], vid[3],
                dict(reja=None, persiana=None, marco=k.M_ALUMINIO, alfeizar='MI_Hormigon', cortina=False))
        _vidriera_interior(mb, rng, vid[0], vid[1], vid[2], vid[3])
    # palier: puerta de hierro con vidrio, revestimiento de piedra alrededor, portero y número
    k.piece('F palier', k.k_door, mb, xf, pal[0], pal[1], pal[2], pal[3],
            dict(hoja=M_HIERRO, estilo='vidriada', marco=M_HIERRO, umbral_mat='MI_PiedraLaja', banderola=40.0))
    box(mb, 'MI_PiedraLaja', xf, xf + 2.5, pal[0] - 40.0, pal[0] - 6.0, 0.0, F_ZPB - 30.0)
    box(mb, 'MI_PiedraLaja', xf, xf + 2.5, pal[1] + 6.0, W, 0.0, F_ZPB - 30.0)
    box(mb, k.M_ALUMINIO, xf + 2.5, xf + 4.5, pal[1] + 14.0, pal[1] + 32.0, 120.0, 165.0)        # portero eléctrico
    k.k_numero(mb, xf + 2.5, pal[1] + 23.0, 190.0)
    k.k_medidor_luz(mb, wm, xf, pal[0] - 23.0, 40.0)
    # marquesina del local con el cartel del comercio (texto del atlas) y luz
    k.piece('F marquesina', cbox, mb, 'MI_Cartel_Blanco', xf, xf + 60.0, 15.0, vid[1] + 20.0, 300.0, 318.0, 1.0, 'y')
    P.placa_texto(mb, COMERCIO_SLOT, 10.0, 0.5 * (15.0 + vid[1] + 20.0), 322.0, min(380.0, vid[1] - 20.0))
    box(mb, 'MI_Emisivo_Calido', xf + 30.0, xf + 55.0, 30.0, vid[1], 298.0, 300.0)
    k.piece('F zocalo', k.k_zocalo, mb, 'MI_PiedraLaja', xf, 0.0, W, 45.0,
            [(cort[0] - 1.0, cort[1] + 1.0), (door[0] - 6.0, door[1] + 6.0), (pal[0] - 6.0, pal[1] + 6.0)])
    # --- pisos
    for i, zf in enumerate(floors):
        proj = 105.0
        k.piece('F losa %d' % i, k.k_losa_balcon, mb, 'MI_Hormigon', xf, 15.0, W - 15.0, zf, proj)
        box(mb, 'MI_Pintura_Blanca', xf + proj - 1.0, xf + proj + 0.6, 15.0, W - 15.0, zf - 17.0, zf - 2.0)
        maciza = ftype == 'mamposteria' or (ftype == 'mixto' and i % 2 == 1)
        if maciza:
            box(mb, wm, xf + proj - 14.0, xf + proj, 15.0, W - 15.0, zf, zf + 95.0)
            for yy in (15.0, W - 29.0):
                box(mb, wm, xf, xf + proj, yy, yy + 14.0, zf, zf + 95.0)
            cbox(mb, 'MI_Hormigon', xf - 1.0, xf + proj + 2.0, 13.0, W - 13.0, zf + 95.0, zf + 101.0, 0.8, 'y')
            mb.col(xf, xf + proj, 15.0, W - 15.0, zf, zf + 101.0)
        else:
            k.piece('F baranda %d' % i, k.k_baranda_hierro, mb, xf, 15.0, W - 15.0, zf, proj)
            mb.col(xf + proj - 8.0, xf + proj, 15.0, W - 15.0, zf, zf + 95.0)
        # puerta-balcón (k_window a ras del piso) y ventana con persiana de enrollar
        k.piece('F pbalcon %d' % i, k.k_window, mb, wm, xf, pb_y[0], pb_y[1], zf + 7.0, zf + 225.0,
                dict(persiana='enrollar', cerrada=rng.uniform(0.0, 0.9), marco=k.M_ALUMINIO, alfeizar='MI_Hormigon'))
        k.piece('F ventana %d' % i, k.k_window, mb, wm, xf, vn_y[0], vn_y[1], zf + 95.0, zf + 225.0,
                dict(persiana='enrollar', cerrada=rng.uniform(0.0, 0.9), marco=k.M_ALUMINIO, alfeizar='MI_Hormigon',
                     moldura='MI_Revoque_Blanco' if rng.random() < 0.4 else None))
        if rng.random() < 0.6:
            k.k_split(mb, xf, rng.choice((pb_y[1] + 75.0, vn_y[0] - 60.0)), zf + 12.0, 1)
        if rng.random() < 0.35:                     # ropa tendida
            yr = rng.uniform(40.0, W - 220.0)
            cyl(mb, M_HIERRO, (xf + 70.0, yr, zf + 185.0), (xf + 70.0, yr + 170.0, zf + 185.0), 0.4, 4)
            for q in range(3):
                box(mb, rng.choice(['MI_Cartel_Blanco', 'MI_Cartel_Azul', 'MI_Cartel_Rojo', 'MI_Pintura_Amarilla']),
                    xf + 69.0, xf + 71.0, yr + 12.0 + q * 52.0, yr + 52.0 + q * 52.0, zf + 120.0, zf + 183.0)
        if rng.random() < 0.45:                     # macetas
            for q in range(rng.randint(1, 3)):
                ym = rng.uniform(40.0, W - 40.0)
                cyl(mb, 'MI_Ladrillo', (xf + proj - 30.0, ym, zf), (xf + proj - 30.0, ym, zf + 28.0), 13.0, 10)
                blob(mb, 'MI_Follaje', (xf + proj - 30.0, ym, zf + 46.0), 20.0, 20.0, 24.0, steps=(5, 7))
        if rng.random() < 0.2:                      # cerramiento de vidrio de balcón
            box(mb, k.M_ALUMINIO, xf + proj - 18.0, xf + proj - 14.0, 15.0, W - 15.0, zf + 95.0, zf + 99.0)
            box(mb, 'MI_Vidrio', xf + proj - 17.0, xf + proj - 16.0, 15.0, W - 15.0, zf + 99.0, zf + 260.0)
            box(mb, k.M_ALUMINIO, xf + proj - 18.0, xf + proj - 14.0, 15.0, W - 15.0, zf + 258.0, zf + 262.0)
    # techo del último balcón
    k.k_losa_balcon(mb, 'MI_Hormigon', xf, 15.0, W - 15.0, zr, 105.0)
    # --- azotea: sala de máquinas, tanque, antenas, baranda
    tx, ty = xb + 260.0, 0.5 * W
    box(mb, wm, tx - 150.0, tx + 150.0, ty - 180.0, ty + 180.0, zr, zr + 260.0)
    cbox(mb, 'MI_Hormigon', tx - 158.0, tx + 158.0, ty - 188.0, ty + 188.0, zr + 260.0, zr + 275.0, 1.5, 'y')
    mb.col(tx - 150.0, tx + 150.0, ty - 180.0, ty + 180.0, zr, zr + 275.0)
    k.k_tanque_plastico(mb, tx, ty - 70.0, zr + 275.0)
    k.k_tanque_plastico(mb, tx, ty + 80.0, zr + 275.0, r=48.0, h=105.0)
    k.k_antena(mb, xb + 520.0, W * 0.3, zr)
    if rng.random() < 0.6:
        k.k_antena(mb, xb + 640.0, W * 0.75, zr)
    k.k_bajada(mb, xf, W - 20.0, 120.0, 500.0)
    mb.anchors = {'power': (xf + 20.0, W - 20.0, 495.0), 'tel': [(xf + 2.0, 120.0, 440.0)],
                  'run': [(290.0, 2.5), (282.0, 2.5)], 'xf': xf}
    return mb


def build_esquina(kind):
    """'EL' kiosco / almacén de esquina (puerta en la ochava, vidrieras y cortina, cartel corrido en
    MI_Cartel_Rojo que se recolorea por instancia) o 'EC' casa de esquina de dos plantas con balcón en la
    ochava. Actor en el marco del lado (slot 0)."""
    S, c = LOT, OCH
    rng = random.Random(stable_hash('esquina' + kind))
    mb = MB('Esquina' + kind)
    local = (kind == 'EL')
    wm = 'MI_Revoque_Gris' if local else 'MI_Revoque_Blanco'
    sm_ = 'MI_Revoque_Gris'
    zr, zp = (400.0, 470.0) if local else (630.0, 700.0)
    zpa = 330.0
    La = S - c
    Lc = c * SQ2
    foot = [(0.0, c), (0.0, S), (-S, S), (-S, 0.0), (-c, 0.0)]
    inner = [(-30.0, c + 12.4), (-30.0, S - 15.0), (-S + 15.0, S - 15.0), (-S + 15.0, 30.0), (-c - 12.4, 30.0)]
    prism(mb, 'MI_Hormigon', foot, 'z', -1.0, k.Z_PISO)
    prism(mb, 'MI_Hormigon', inner, 'z', zr - 18.0, zr + 2.0)
    if not local:
        prism(mb, 'MI_Hormigon', inner, 'z', zpa - 15.0, zpa)
    _corner_walls(mb, S, c, zp, sm_)
    # pilastras en las uniones con la ochava
    cbox(mb, wm, -32.0, 2.5, c - 4.0, c + 28.0, 0.0, zp + 4.0, 1.0, 'z')
    cbox(mb, wm, -c - 28.0, -c + 4.0, -2.5, 32.0, 0.0, zp + 4.0, 1.0, 'z')
    if local:
        hA = [k.win_hole(60.0, 300.0, 70.0, 250.0), (340.0, 550.0, Z_VER, 285.0)]
        hB = [k.win_hole(60.0, 200.0, 110.0, 230.0), k.win_hole(280.0, 520.0, 70.0, 250.0)]
        hC = [(150.0, 250.0, k.Z_PISO, 240.0)]

        def dA(m):
            k.k_window(m, wm, 0.0, 60.0, 300.0, 70.0, 250.0, dict(reja='cuadricula', persiana=None, cortina=False,
                                                                     alfeizar='MI_Hormigon'))
            _vidriera_interior(m, rng, 60.0, 300.0, 70.0, 250.0)
            k.k_cortina_local(m, 0.0, 340.0, 550.0, Z_VER, 285.0)
            cbox(m, 'MI_Hormigon', -30.0, 1.0, 325.0, 565.0, 285.0, 300.0, 0.6, 'y')
            _cartel(m, 'MI_Cartel_Rojo', 20.0, La - 20.0, 305.0, 377.0)
            P.placa_texto(m, COMERCIO_SLOT, 10.0, 0.5 * La, 311.0, 480.0)
            k.k_zocalo(m, 'MI_Hormigon', 0.0, 0.0, La, 40.0, [(339.0, 551.0)])
            box(m, M_HIERRO, 0.0, 3.0, 700.0 - c - 4.0, 700.0 - c + 4.0, 420.0, 440.0)      # caja de la acometida

        def dB(m):
            k.k_window(m, wm, 0.0, 60.0, 200.0, 110.0, 230.0, dict(reja='barrotes', persiana='enrollar', cerrada=0.7))
            k.k_window(m, wm, 0.0, 280.0, 520.0, 70.0, 250.0, dict(reja='cuadricula', persiana=None, cortina=False,
                                                                      alfeizar='MI_Hormigon'))
            _vidriera_interior(m, rng, 280.0, 520.0, 70.0, 250.0)
            _cartel(m, 'MI_Cartel_Rojo', 20.0, La - 20.0, 305.0, 377.0)
            P.placa_texto(m, COMERCIO_SLOT, 10.0, 0.5 * La, 311.0, 480.0)
            k.k_zocalo(m, 'MI_Hormigon', 0.0, 0.0, La, 40.0, [])

        def dC(m):
            k.k_door(m, 0.0, 150.0, 250.0, k.Z_PISO, 240.0, dict(hoja='MI_Chapa_Gris', estilo='vidriada', marco=M_HIERRO,
                                                                   umbral_mat='MI_Hormigon'))
            _cartel(m, 'MI_Cartel_Rojo', 25.0, Lc - 25.0, 305.0, 377.0)
            P.placa_texto(m, COMERCIO_SLOT, 10.0, 0.5 * Lc, 321.0, 320.0)
            # toldo sobre la puerta de la ochava
            prism(m, 'MI_Cartel_Rojo', [(0.0, 290.0), (4.0, 290.0), (95.0, 252.0), (95.0, 238.0), (91.0, 238.0),
                                        (91.0, 250.0)], 'y', 110.0, 290.0)
            k.k_zocalo(m, 'MI_Hormigon', 0.0, 0.0, Lc, 40.0, [(144.0, 256.0)])
    else:
        hA = [(277.0, 367.0, k.Z_PISO, 240.0), k.win_hole(40.0, 200.0, 100.0, 240.0), k.win_hole(420.0, 560.0, 100.0, 240.0),
              k.win_hole(60.0, 220.0, 430.0, 560.0), k.win_hole(300.0, 520.0, 430.0, 560.0)]
        hB = [k.win_hole(90.0, 250.0, 100.0, 240.0), k.win_hole(330.0, 490.0, 100.0, 240.0),
              k.win_hole(90.0, 250.0, 430.0, 560.0), k.win_hole(330.0, 520.0, 430.0, 560.0)]
        hC = [k.win_hole(130.0, 270.0, 100.0, 240.0), (110.0, 290.0, zpa + 15.0, 560.0)]
        wo = dict(reja='barrotes', persiana='enrollar', cerrada=0.5, moldura=wm, persiana_mat='MI_Madera')
        wo2 = dict(persiana='enrollar', cerrada=0.4, persiana_mat='MI_Cartel_Blanco')

        def dA(m):
            k.k_door(m, 0.0, 277.0, 367.0, k.Z_PISO, 240.0, dict(hoja=k.M_PUERTA, estilo='tablero', aplique=True))
            k.k_window(m, wm, 0.0, 40.0, 200.0, 100.0, 240.0, wo)
            k.k_window(m, wm, 0.0, 420.0, 560.0, 100.0, 240.0, wo)
            k.k_window(m, wm, 0.0, 60.0, 220.0, 430.0, 560.0, wo2)
            k.k_window(m, wm, 0.0, 300.0, 520.0, 430.0, 560.0, wo2)
            cbox(m, wm, -1.0, 2.5, 0.0, La, zpa - 8.0, zpa + 8.0, 0.8, 'y')
            k.k_cornisa(m, wm, 0.0, 0.0, La, zr - 17.0, 1)
            k.k_zocalo(m, 'MI_Revoque_Gris', 0.0, 0.0, La, 55.0, [(271.0, 373.0)])
            k.k_numero(m, 0.0, 395.0, 205.0)

        def dB(m):
            k.k_window(m, wm, 0.0, 90.0, 250.0, 100.0, 240.0, wo)
            k.k_window(m, wm, 0.0, 330.0, 490.0, 100.0, 240.0, wo)
            k.k_window(m, wm, 0.0, 90.0, 250.0, 430.0, 560.0, wo2)
            k.k_window(m, wm, 0.0, 330.0, 520.0, 430.0, 560.0, wo2)
            cbox(m, wm, -1.0, 2.5, 0.0, La, zpa - 8.0, zpa + 8.0, 0.8, 'y')
            k.k_cornisa(m, wm, 0.0, 0.0, La, zr - 17.0, 1)
            k.k_zocalo(m, 'MI_Revoque_Gris', 0.0, 0.0, La, 55.0, [])
            k.k_split(m, 0.0, 300.0, zpa + 60.0, 1)

        def dC(m):
            k.k_window(m, wm, 0.0, 130.0, 270.0, 100.0, 240.0, wo)
            k.k_window(m, wm, 0.0, 110.0, 290.0, zpa + 20.0, 560.0, dict(persiana='enrollar', cerrada=0.5,
                                                                         persiana_mat='MI_Madera', alfeizar='MI_Hormigon'))
            k.k_losa_balcon(m, 'MI_Hormigon', 0.0, 30.0, Lc - 30.0, zpa + 6.0, 95.0)
            k.k_baranda_hierro(m, 0.0, 30.0, Lc - 30.0, zpa + 6.0, 95.0)
            cbox(m, wm, -1.0, 2.5, 0.0, Lc, zpa - 8.0, zpa + 8.0, 0.8, 'y')
            k.k_cornisa(m, wm, 0.0, 0.0, Lc, zr - 17.0, 1)
            k.k_zocalo(m, 'MI_Revoque_Gris', 0.0, 0.0, Lc, 55.0, [])
    k.piece('Esquina fachada A', facade_run, mb, (0.0, c, 0.0), 0.0, La, 0.0, zp, wm, hA, (), 30.0, dA, False)
    k.piece('Esquina fachada B', facade_run, mb, (-S, 0.0, 0.0), -90.0, La, 0.0, zp, wm, hB, (), 30.0, dB, False)
    k.piece('Esquina ochava', facade_run, mb, (-c, 0.0, 0.0), -45.0, Lc, 0.0, zp, wm, hC, (), 30.0, dC, False)
    # coronamiento del parapeto en las tres fachadas
    k.piece('Esquina tanque', k.tanque_simple, mb, -S + 260.0, S - 260.0, zr + 2.0)
    if not local:
        k.piece('Esquina antena', k.k_antena, mb, -S + 420.0, S - 520.0, zr + 2.0)
    mb.anchors = {'xf': 0.0}
    return mb


# =====================================================================================
# COMISARÍA (lado N de la manzana 1,0, lotes 3..6) - marco del lado N de M10: x hacia la plaza
# =====================================================================================
COMISARIA = dict(y0=3 * LOT, y1=7 * LOT, D=1500.0, zf=46.0, zr=760.0, zp=840.0,
                 hall=(3930.0, 4730.0), hall_x=-600.0, door=(4200.0, 4460.0, 300.0),
                 rear=(-3650.0, -1500.0, 3850.0, 4810.0), cell=(-3392.0, -2992.0, 4130.0, 4530.0))


def comisaria_frame():
    return L.side_frame('M10', 'N')


def comisaria_world(lx, ly, z=0.0):
    return L.fw(comisaria_frame(), lx, ly, z)


def comisaria_rear_world():
    """Rectángulo en mundo (x0, x1, y0, y1) del bloque trasero con la celda (se excluye del relleno)."""
    C = COMISARIA
    a = comisaria_world(C['rear'][0], C['rear'][2])
    b = comisaria_world(C['rear'][1], C['rear'][3])
    return (min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]))


def comisaria_gameplay():
    """Posiciones (mundo) de la zona segura del hall, el mostrador, la aparición de policías y la celda."""
    C = COMISARIA
    f = comisaria_frame()
    yc = 0.5 * (C['hall'][0] + C['hall'][1])
    hx0 = C['hall_x']
    safe_c = L.fw(f, 0.5 * (hx0 - 30.0), yc, C['zf'] + 170.0)
    hw_y = 0.5 * (C['hall'][1] - C['hall'][0]) - 10.0
    hw_x = 0.5 * (-30.0 - hx0) - 5.0
    # el marco tiene yaw 90: x local = Y mundo, y local = -X mundo
    safe_ext = (hw_y, hw_x, 170.0)
    counter = L.fw(f, -405.0, yc, C['zf'])
    police = L.fw(f, -260.0, yc + 220.0, C['zf'] + 95.0)
    cx = 0.5 * (C['cell'][0] + C['cell'][1])
    cy = 0.5 * (C['cell'][2] + C['cell'][3])
    jail = L.fw(f, cx, cy, 230.0)
    return {'safe': (safe_c, safe_ext), 'counter': (counter, f['yaw']), 'police': (police, f['yaw']),
            'jail': (jail, f['yaw'] + 180.0)}


def build_comisaria():
    """Comisaría: fachada azul (MI_Comisaria_Azul) con guardas blancas, escalones, balizas azules, cartel
    en blanco, mástil; hall accesible de 8 x 5,7 m con puerta abierta (zona segura, mostrador, aparición de
    policías); bloque trasero cerrado con la celda (inaccesible). Actor en el marco del lado N de M10."""
    C = COMISARIA
    mb = MB('Comisaria')
    rng = random.Random(17)
    y0, y1, D = C['y0'], C['y1'], C['D']
    zf, zr, zp = C['zf'], C['zr'], C['zp']
    h0, h1 = C['hall']
    hx = C['hall_x']
    d0, d1, dz = C['door']
    yc = 0.5 * (y0 + y1)
    wm = 'MI_Comisaria_Azul'
    xb = -D
    win_pb = [(y0 + 120.0, y0 + 320.0), (y0 + 520.0, y0 + 720.0), (y0 + 920.0, y0 + 1120.0),
              (y1 - 1120.0, y1 - 920.0), (y1 - 720.0, y1 - 520.0), (y1 - 320.0, y1 - 120.0)]
    win_pa = []
    y = y0 + 150.0
    while y + 200.0 < y1 - 100.0:
        win_pa.append((y, y + 200.0))
        y += 400.0
    holes = [(d0, d1, zf, dz)] + [k.win_hole(a, b, 110.0, 250.0) for (a, b) in win_pb] + \
            [k.win_hole(a, b, 520.0, 680.0) for (a, b) in win_pa]
    # ---- cáscara
    k.piece('Comisaria fachada', k.wall_holes, mb, wm, -30.0, 0.0, y0, y1, 0.0, zp, holes)
    box(mb, 'MI_Revoque_Gris', xb, -30.0, y0, y0 + 30.0, 0.0, zp)
    box(mb, 'MI_Revoque_Gris', xb, -30.0, y1 - 30.0, y1, 0.0, zp)
    box(mb, 'MI_Revoque_Gris', xb, xb + 30.0, y0 + 30.0, y1 - 30.0, 0.0, zp)
    box(mb, 'MI_Hormigon', xb + 30.0, -30.0, y0 + 30.0, y1 - 30.0, zr - 20.0, zr)
    box(mb, 'MI_Hormigon', xb + 30.0, -30.0, y0 + 30.0, y1 - 30.0, -1.0, k.Z_PISO)
    k.piece('Comisaria cupertina', k.k_coping_y, mb, 'MI_Pintura_Blanca', -30.0, 0.0, y0, y1, zp)
    # guardas blancas, zócalo, pilastras
    cbox(mb, 'MI_Pintura_Blanca', -1.0, 3.0, y0, y1, 470.0, 495.0, 0.8, 'y')
    cbox(mb, 'MI_Pintura_Blanca', -1.0, 3.0, y0, y1, zr - 10.0, zr + 12.0, 0.8, 'y')
    k.piece('Comisaria zocalo', k.k_zocalo, mb, 'MI_PiedraLaja', 0.0, y0, y1, 80.0, [(d0 - 2.0, d1 + 2.0)], 0.0, 2.2)
    for (yp, ztp) in ((y0 + 20.0, zr - 10.0), (d0 - 60.0, 470.0), (d1 + 30.0, 470.0), (y1 - 50.0, zr - 10.0)):
        cbox(mb, 'MI_Pintura_Blanca', -1.0, 4.0, yp, yp + 30.0, 80.0, ztp, 0.8, 'z')
    # ---- ventanas (rejas de cuadrícula en PB)
    for (a, b) in win_pb:
        k.piece('Comisaria ventana PB', k.k_window, mb, wm, 0.0, a, b, 110.0, 250.0,
                dict(reja='cuadricula', persiana=None, marco=k.M_ALUMINIO, alfeizar='MI_PiedraLaja'))
    for (a, b) in win_pa:
        k.piece('Comisaria ventana PA', k.k_window, mb, wm, 0.0, a, b, 520.0, 680.0,
                dict(persiana='enrollar', cerrada=rng.uniform(0.3, 0.8), marco=k.M_ALUMINIO,
                     persiana_mat='MI_Pintura_Blanca'))
    # ---- puerta abierta: marco, hojas vidriadas rebatidas contra el muro interior
    box(mb, M_HIERRO, -30.0, 2.0, d0 - 8.0, d0, zf, dz + 8.0)
    box(mb, M_HIERRO, -30.0, 2.0, d1, d1 + 8.0, zf, dz + 8.0)
    box(mb, M_HIERRO, -30.0, 2.0, d0 - 8.0, d1 + 8.0, dz, dz + 8.0)
    for (ya, yb) in ((d0 - 128.0, d0 - 8.0), (d1 + 8.0, d1 + 128.0)):
        box(mb, M_HIERRO, -36.0, -31.0, ya, yb, zf + 2.0, dz - 2.0)
        box(mb, 'MI_Vidrio', -37.0, -36.0, ya + 8.0, yb - 8.0, zf + 90.0, dz - 10.0)
    # ---- escalones (15 cm) de la vereda al hall + umbral
    box(mb, 'MI_PiedraLaja', 30.0, 60.0, d0 - 70.0, d1 + 70.0, -1.0, 31.0)
    box(mb, 'MI_PiedraLaja', -30.0, 30.0, d0 - 70.0, d1 + 70.0, -1.0, zf)
    mb.col(30.0, 60.0, d0 - 70.0, d1 + 70.0, -1.0, 31.0)
    mb.col(-30.0, 30.0, d0 - 70.0, d1 + 70.0, -1.0, zf)
    for s in (-1.0, 1.0):        # barandas de los escalones
        ys = d0 - 66.0 if s < 0 else d1 + 66.0
        cyl(mb, M_HIERRO, (52.0, ys, 31.0), (52.0, ys, 121.0), 2.0, 8)
        cyl(mb, M_HIERRO, (4.0, ys, zf), (4.0, ys, zf + 90.0), 2.0, 8)
        cyl(mb, M_HIERRO, (52.0, ys, 121.0), (4.0, ys, zf + 90.0), 2.2, 8)
    # ---- cartel en blanco, balizas, mástil
    cbox(mb, M_HIERRO, -1.0, 10.0, d0 - 260.0, d1 + 260.0, 328.0, 448.0, 1.5, 'y')
    k.piece('Comisaria cartel', P.cartel_con_texto, mb, 'MI_Cartel_Comisaria', 11.2, 0.5 * (d0 + d1), 342.0,
            0.5 * (d1 - d0) * 2.0 + 480.0)
    for yb in (d0 - 330.0, d1 + 330.0):
        box(mb, M_HIERRO, 0.0, 24.0, yb - 4.0, yb + 4.0, 380.0, 386.0)
        cyl(mb, M_HIERRO, (24.0, yb, 386.0), (24.0, yb, 392.0), 11.0, 14)
        cyl(mb, 'MI_Emisivo_Baliza_Azul', (24.0, yb, 392.0), (24.0, yb, 410.0), 9.0, 14)
        cone(mb, 'MI_Emisivo_Baliza_Azul', (24.0, yb, 410.0), (24.0, yb, 416.0), 9.0, 4.0, 14)
    for yb in (y0 + 120.0, y1 - 120.0):
        cyl(mb, 'MI_Emisivo_Baliza_Azul', (-15.0, yb, zp + 6.0), (-15.0, yb, zp + 26.0), 10.0, 14)
        cyl(mb, M_HIERRO, (-15.0, yb, zp), (-15.0, yb, zp + 6.0), 13.0, 14)
    ym = y1 - 600.0
    cyl(mb, M_HIERRO, (0.0, ym, 500.0), (210.0, ym, 640.0), 3.5, 10)
    for j, m in enumerate(('MI_Cartel_Azul', 'MI_Pintura_Blanca', 'MI_Cartel_Azul')):
        prism(mb, m, [(205.0 - 8.0, 632.0 - j * 34.0), (205.0, 640.0 - j * 34.0), (75.0, 553.0 - j * 34.0),
                      (68.0, 545.0 - j * 34.0)], 'y', ym - 0.8, ym + 0.8)
    # ---- hall interior
    W_i = 'MI_Revoque_Blanco'
    box(mb, 'MI_Baldosa', hx, -30.0, h0, h1, -1.0, zf)
    box(mb, W_i, hx - 30.0, -30.0, h0 - 30.0, h0, zf, zf + 330.0)
    box(mb, W_i, hx - 30.0, -30.0, h1, h1 + 30.0, zf, zf + 330.0)
    box(mb, W_i, hx - 30.0, hx, h0, h1, zf, zf + 330.0)
    box(mb, 'MI_Hormigon', hx - 30.0, -30.0, h0 - 30.0, h1 + 30.0, zf + 330.0, zf + 350.0)
    for (ya, yb) in ((h0, h0 + 2.0), (h1 - 2.0, h1)):
        box(mb, wm, hx, -30.0, ya, yb, zf, zf + 90.0)       # zócalo azul interior
    box(mb, wm, hx, hx + 2.0, h0, h1, zf, zf + 90.0)
    # mostrador con frente azul y tapa de madera, con pasos libres en los extremos
    m0, m1 = h0 + 110.0, h1 - 110.0
    box(mb, wm, -480.0, -420.0, m0, m1, zf, zf + 105.0)
    box(mb, 'MI_Madera', -486.0, -414.0, m0 - 4.0, m1 + 4.0, zf + 105.0, zf + 110.0)
    box(mb, 'MI_Vidrio', -452.0, -450.0, m0 + 20.0, m1 - 20.0, zf + 110.0, zf + 170.0)
    mb.col(-486.0, -414.0, m0 - 4.0, m1 + 4.0, zf, zf + 110.0)
    # banco de espera, cartelera, luz de techo, puerta trasera cerrada
    box(mb, 'MI_Madera', -330.0, -110.0, h0 + 8.0, h0 + 50.0, zf + 42.0, zf + 47.0)
    box(mb, 'MI_Madera', -330.0, -110.0, h0 + 2.0, h0 + 8.0, zf + 50.0, zf + 95.0)
    for xl in (-320.0, -120.0):
        box(mb, M_HIERRO, xl - 3.0, xl + 3.0, h0 + 10.0, h0 + 48.0, zf, zf + 42.0)
    mb.col(-330.0, -110.0, h0, h0 + 50.0, zf, zf + 47.0)
    box(mb, 'MI_Cartel_Blanco', -300.0, -140.0, h1 - 3.0, h1, zf + 120.0, zf + 230.0)
    box(mb, 'MI_Corteza', -305.0, -135.0, h1 - 2.0, h1, zf + 115.0, zf + 235.0)
    box(mb, 'MI_Emisivo_Calido', -400.0, -200.0, yc - 25.0, yc + 25.0, zf + 326.0, zf + 330.0)
    box(mb, k.M_PUERTA, hx + 0.5, hx + 4.0, yc + 160.0, yc + 250.0, zf, zf + 210.0)
    box(mb, M_HIERRO, hx + 4.0, hx + 6.0, yc + 236.0, yc + 244.0, zf + 95.0, zf + 105.0)
    # colisión: todo el bloque menos el hall; el hall con piso, paredes, techo y fachada con la puerta libre
    for (a0, a1, b0, b1) in k.rect_minus(xb, 0.0, y0, y1, [(hx, 0.0, h0, h1)]):
        mb.col(a0, a1, b0, b1, -1.0, zp)
    mb.col(hx, 0.0, h0, h1, -1.0, zf)
    mb.col(hx, 0.0, h0, h1, zf + 330.0, zp)
    mb.col(-30.0, 0.0, h0, d0, zf, zf + 330.0)
    mb.col(-30.0, 0.0, d1, h1, zf, zf + 330.0)
    mb.col(-30.0, 0.0, d0, d1, dz, zf + 330.0)
    # ---- bloque trasero con la celda (cerrado: se ve como fondo, no se entra)
    rx0, rx1, ry0, ry1 = C['rear']
    hr = 420.0
    box(mb, 'MI_Revoque_Gris', rx0, rx1, ry0, ry0 + 30.0, -1.0, hr)
    box(mb, 'MI_Revoque_Gris', rx0, rx1, ry1 - 30.0, ry1, -1.0, hr)
    box(mb, 'MI_Revoque_Gris', rx0, rx0 + 30.0, ry0 + 30.0, ry1 - 30.0, -1.0, hr)
    box(mb, 'MI_Hormigon', rx0, rx1, ry0, ry1, hr, hr + 20.0)
    box(mb, 'MI_Hormigon', rx0 + 30.0, rx1, ry0 + 30.0, ry1 - 30.0, -1.0, 30.0)
    mb.col(rx0, rx1, ry0, ry0 + 30.0, -1.0, hr + 20.0)
    mb.col(rx0, rx1, ry1 - 30.0, ry1, -1.0, hr + 20.0)
    mb.col(rx0, rx0 + 30.0, ry0, ry1, -1.0, hr + 20.0)
    mb.col(rx0, rx1, ry0, ry1, hr, hr + 20.0)
    mb.col(rx0, rx1, ry0, ry1, -1.0, 30.0)
    cx0, cx1, cy0, cy1 = C['cell']
    zc = 300.0
    box(mb, 'MI_Revoque_Gris', cx0 - 25.0, cx0, cy0 - 25.0, cy1 + 25.0, 30.0, zc)
    box(mb, 'MI_Revoque_Gris', cx0, cx1, cy0 - 25.0, cy0, 30.0, zc)
    box(mb, 'MI_Revoque_Gris', cx0, cx1, cy1, cy1 + 25.0, 30.0, zc)
    box(mb, 'MI_Hormigon', cx0 - 25.0, cx1 + 6.0, cy0 - 25.0, cy1 + 25.0, zc, zc + 20.0)
    box(mb, 'MI_Hormigon', cx0, cx1, cy0, cy1, 29.0, 31.0)
    k.piece('Celda reja', k.k_reja_plano, mb, M_HIERRO, cx1, cy0, cy1, 30.0, zc, 'y', 12.0, 2.2, 4.0, (120.0, 220.0))
    box(mb, 'MI_Hormigon', cx0, cx0 + 70.0, cy0 + 10.0, cy1 - 10.0, 30.0, 75.0)          # cama de mampostería
    box(mb, 'MI_Emisivo_Calido', cx0 + 120.0, cx0 + 180.0, cy0 + 170.0, cy1 - 170.0, zc - 4.0, zc)
    k.piece('Celda ventanita', k.k_reja_plano, mb, M_HIERRO, cy0 - 2.0, cx0 + 120.0, cx0 + 220.0, 200.0, 260.0,
            'x', 10.0, 2.0, 3.0)
    box(mb, 'MI_Revoque_Blanco', cx1 + 150.0, cx1 + 152.0, cy0 - 25.0, cy1 + 25.0, 30.0, 250.0)   # pared del pasillo
    mb.col(cx0 - 25.0, cx0, cy0 - 25.0, cy1 + 25.0, 30.0, zc + 20.0)
    mb.col(cx0, cx1, cy0 - 25.0, cy0, 30.0, zc + 20.0)
    mb.col(cx0, cx1, cy1, cy1 + 25.0, 30.0, zc + 20.0)
    mb.col(cx1 - 2.0, cx1 + 6.0, cy0, cy1, 30.0, zc + 20.0)
    mb.col(cx0 - 25.0, cx1 + 6.0, cy0 - 25.0, cy1 + 25.0, zc, zc + 20.0)
    # tanques y equipos en la azotea
    k.piece('Comisaria tanque', k.tanque_simple, mb, xb + 300.0, y0 + 600.0, zr + 2.0, 60.0, 120.0)
    k.piece('Comisaria tanque2', k.tanque_simple, mb, xb + 300.0, y0 + 780.0, zr + 2.0, 60.0, 120.0)
    k.piece('Comisaria antena', k.k_antena, mb, xb + 500.0, y1 - 500.0, zr + 2.0)
    return mb


# =====================================================================================
# TORRE DE 12 PISOS (esquina NE de la manzana 2,1) - marco del lado N de M21
#   x hacia la calle de las vías (norte), y hacia el oeste; la línea de la avenida es y = 0.
# =====================================================================================
TORRE = dict(S=2 * LOT, c=OCH, zpb=450.0, hf=290.0, nf=12)


def torre_rect_world():
    f = L.side_frame('M21', 'N')
    S = TORRE['S']
    a = L.fw(f, 0.0, 0.0)
    b = L.fw(f, -S, S)
    return (min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]))


def _torre_pisos(mb, Lf, rng, balcon_all=True, lit=0.16):
    """Pisos 1..12 de una fachada de la torre en el marco temporal (x afuera, y de 0 a Lf): muro y pilastras de
    ladrillo visto, losas con canto blanco y balcones con baranda maciza blanca (torre de los 70). Las ventanas
    encendidas (lit) llevan MI_Emisivo_Calido EN el plano del vidrio (el vidrio es opaco: detrás no se vería)."""
    T_ = TORRE
    zpb, hf, nf = T_['zpb'], T_['hf'], T_['nf']
    ztop = zpb + nf * hf
    box(mb, 'MI_Ladrillo_Torre', -60.0, -32.0, 0.0, Lf, zpb, ztop)
    nb = max(1, int(round(Lf / 300.0)))
    bw = Lf / nb
    for i in range(nb + 1):
        yp = i * bw
        box(mb, 'MI_Ladrillo_Torre', -32.0, 0.0, max(0.0, yp - 22.0), min(Lf, yp + 22.0), zpb, ztop + 100.0)
    for f in range(nf):
        zf = zpb + f * hf
        proj = 125.0 if (balcon_all or f % 2 == 0) else 0.0
        box(mb, 'MI_Hormigon', -32.0, max(proj - 12.0, 0.0), 0.0, Lf, zf - 18.0, zf)
        box(mb, 'MI_Pintura_Blanca', max(proj - 12.0, 0.0), max(proj, 3.0), 0.0, Lf, zf - 20.0, zf + 1.0)
        if proj > 0.0:
            # baranda maciza blanca con coronamiento y separadores entre unidades
            box(mb, 'MI_Revoque_Blanco', proj - 12.0, proj, 0.0, Lf, zf, zf + 100.0)
            box(mb, 'MI_Pintura_Blanca', proj - 15.0, proj + 3.0, -1.0, Lf + 1.0, zf + 100.0, zf + 106.0)
            for yy in (2.0, Lf - 2.0):
                box(mb, 'MI_Revoque_Blanco', -2.0, proj - 12.0, yy - 6.0, yy + 6.0, zf, zf + 100.0)
            for i in range(1, nb):
                if i % 2 == 0:
                    box(mb, 'MI_Revoque_Blanco', -2.0, proj - 12.0, i * bw - 5.0, i * bw + 5.0, zf, zf + 245.0)
            if rng.random() < 0.35:                 # macetas, ropa tendida
                ym = rng.uniform(60.0, Lf - 60.0)
                cyl(mb, 'MI_Ladrillo', (proj - 35.0, ym, zf), (proj - 35.0, ym, zf + 30.0), 14.0, 10)
                blob(mb, 'MI_Follaje', (proj - 35.0, ym, zf + 48.0), 22.0, 22.0, 26.0, steps=(5, 7))
            if rng.random() < 0.2:
                yr = rng.uniform(40.0, Lf - 200.0)
                cyl(mb, M_HIERRO, (proj - 30.0, yr, zf + 180.0), (proj - 30.0, yr + 150.0, zf + 180.0), 0.4, 4)
                for q in range(3):
                    box(mb, rng.choice(['MI_Cartel_Blanco', 'MI_Cartel_Azul', 'MI_Cartel_Rojo']), proj - 31.0,
                        proj - 29.0, yr + 15.0 + q * 45.0, yr + 50.0 + q * 45.0, zf + 120.0, zf + 178.0)
        for i in range(nb):
            ya, yb = i * bw + 22.0, (i + 1) * bw - 22.0
            door = proj > 0.0 and i % 2 == 0
            zs = zf + (4.0 if door else 90.0)
            zt = zf + 245.0
            r = rng.random()
            box(mb, 'MI_Emisivo_Calido' if r < lit else 'MI_Vidrio', -31.0, -30.0, ya + 5.0, yb - 5.0, zs, zt)
            box(mb, 'MI_Chapa_Gris', -32.0, -27.0, ya, ya + 5.0, zs, zt)
            box(mb, 'MI_Chapa_Gris', -32.0, -27.0, yb - 5.0, yb, zs, zt)
            box(mb, 'MI_Chapa_Gris', -32.0, -27.0, ya + 5.0, yb - 5.0, zt - 5.0, zt)
            box(mb, 'MI_Chapa_Gris', -32.0, -27.0, ya + 5.0, yb - 5.0, zs, zs + 5.0)
            box(mb, 'MI_Chapa_Gris', -31.5, -28.0, 0.5 * (ya + yb) - 2.0, 0.5 * (ya + yb) + 2.0, zs + 5.0, zt - 5.0)
            if r >= lit and r < 0.5:
                zc = zt - (zt - zs) * rng.uniform(0.3, 0.9)
                box(mb, 'MI_Madera', -29.5, -28.5, ya + 5.0, yb - 5.0, zc, zt - 5.0)      # persiana de madera
            if not door and rng.random() < 0.25:
                k.k_split(mb, 0.0, ya + 70.0, zf + 20.0, 1)
    box(mb, 'MI_Revoque_Blanco', -32.0, 3.0, 0.0, Lf, ztop, ztop + 100.0)
    box(mb, 'MI_Pintura_Blanca', -34.0, 5.0, 0.0, Lf, ztop + 100.0, ztop + 106.0)


def _antena_reticulada(mb, cx, cy, z0, H=1250.0):
    """Antena reticulada triangular con dos balizas rojas (mitad y punta): remate nocturno de la torre."""
    r0, r1 = 70.0, 18.0
    legs = []
    for j in range(3):
        a = math.radians(90.0 + j * 120.0)
        legs.append((math.cos(a), math.sin(a)))
    for (lx, ly) in legs:
        cyl(mb, 'MI_Pintura_Blanca', (cx + lx * r0, cy + ly * r0, z0), (cx + lx * r1, cy + ly * r1, z0 + H), 3.5, 6)
    n = 10
    for i in range(n):
        za, zb = z0 + H * i / n, z0 + H * (i + 1) / n
        ra, rb = r0 + (r1 - r0) * i / n, r0 + (r1 - r0) * (i + 1) / n
        for j in range(3):
            (ax, ay), (bx, by) = legs[j], legs[(j + 1) % 3]
            m = 'MI_Cartel_Rojo' if (i // 2) % 2 == 0 else 'MI_Pintura_Blanca'
            cyl(mb, m, (cx + ax * ra, cy + ay * ra, za), (cx + bx * rb, cy + by * rb, zb), 1.4, 4)
            cyl(mb, m, (cx + ax * rb, cy + ay * rb, zb), (cx + bx * rb, cy + by * rb, zb), 1.4, 4)
    for (zz, rr) in ((z0 + H * 0.5, 13.0), (z0 + H + 12.0, 15.0)):
        cyl(mb, M_HIERRO, (cx, cy, zz - 16.0), (cx, cy, zz - 8.0), 10.0, 10)
        blob(mb, 'MI_Emisivo_Baliza_Roja', (cx, cy, zz), rr, rr, rr, steps=(6, 8))
    # parábolas y antenas de TV en la base
    for (dx, dy) in ((140.0, 60.0), (-120.0, 160.0)):
        cyl(mb, M_HIERRO, (cx + dx, cy + dy, z0), (cx + dx, cy + dy, z0 + 160.0), 2.0, 6)
        cone(mb, 'MI_Pintura_Blanca', (cx + dx + 6.0, cy + dy, z0 + 160.0), (cx + dx + 30.0, cy + dy, z0 + 175.0), 38.0, 4.0, 14)


def build_torre():
    """Torre de 12 pisos (≈40 m + sala de máquinas y antena reticulada roja y blanca de 12,5 m con dos balizas
    rojas): ladrillo visto con balcones de baranda maciza blanca sobre las dos calles, ~16 % de ventanas
    encendidas (emisivo cálido), PB con hall y locales, medianeras de ladrillo con parches. Es la ÚNICA altura
    del cuadrante NE (ver SKYLINE). Actor en el marco del lado N de M21."""
    T_ = TORRE
    S, c = T_['S'], T_['c']
    zpb, hf, nf = T_['zpb'], T_['hf'], T_['nf']
    ztop = zpb + nf * hf
    rng = random.Random(1212)
    mb = MB('Torre')
    Lf = S - c
    Lc = c * SQ2
    foot = [(0.0, c), (0.0, S), (-S, S), (-S, 0.0), (-c, 0.0)]
    inner = [(-60.0, c + 25.0), (-60.0, S - 30.0), (-S + 30.0, S - 30.0), (-S + 30.0, 60.0), (-c - 25.0, 60.0)]
    prism(mb, 'MI_Hormigon', foot, 'z', -1.0, k.Z_PISO)
    prism(mb, 'MI_Hormigon', inner, 'z', ztop - 20.0, ztop + 2.0)
    prism(mb, 'MI_Hormigon', inner, 'z', zpb - 30.0, zpb)
    # medianeras ciegas hacia la manzana (se ven por encima de las casas)
    box(mb, 'MI_Ladrillo_Torre', -S, -S + 30.0, 0.0, S, 0.0, ztop + 100.0)
    box(mb, 'MI_Ladrillo_Torre', -S + 30.0, 0.0 - 60.0, S - 30.0, S, 0.0, ztop + 100.0)
    face_patches(mb, rng, 'x', -S, -1.0, 40.0, S - 40.0, 700.0, ztop, ['MI_Revoque_Gris', 'MI_Hormigon', 'MI_Revoque_Blanco'], 16)
    face_patches(mb, rng, 'y', S, 1.0, -S + 40.0, -100.0, 700.0, ztop, ['MI_Revoque_Gris', 'MI_Hormigon', 'MI_Revoque_Blanco'], 16)
    z = zpb
    while z < ztop:
        box(mb, 'MI_Hormigon', -S - 2.0, -S + 1.0, 0.0, S, z - 15.0, z + 15.0)
        box(mb, 'MI_Hormigon', -S, -60.0, S - 1.0, S + 2.0, z - 15.0, z + 15.0)
        z += 3 * hf
    # pisos (fachadas a la calle y la ochava)
    k.piece('Torre pisos N', facade_run, mb, (0.0, c, 0.0), 0.0, Lf, 0.0, 0.0, None, (), (), 30.0,
            lambda m: _torre_pisos(m, Lf, rng, True), False)
    k.piece('Torre pisos E', facade_run, mb, (-S, 0.0, 0.0), -90.0, Lf, 0.0, 0.0, None, (), (), 30.0,
            lambda m: _torre_pisos(m, Lf, rng, False), False)
    k.piece('Torre pisos ochava', facade_run, mb, (-c, 0.0, 0.0), -45.0, Lc, 0.0, 0.0, None, (), (), 30.0,
            lambda m: _torre_pisos(m, Lc, rng, True), False)
    # planta baja: hall de entrada al norte, locales sobre la avenida, vidriera en la ochava
    hN = [(560.0, 760.0, k.Z_PISO, 300.0), k.win_hole(820.0, 1300.0, 80.0, 330.0), (60.0, 480.0, Z_VER, 330.0)]
    hE = [(80.0, 600.0, Z_VER, 330.0), k.win_hole(660.0, 900.0, 90.0, 330.0), (960.0, 1400.0, Z_VER, 330.0)]
    hC = [k.win_hole(60.0, 340.0, 80.0, 330.0)]

    def dN(m):
        k.k_door(m, 0.0, 560.0, 760.0, k.Z_PISO, 300.0, dict(hoja=k.M_ALUMINIO, estilo='vidriada', marco=k.M_ALUMINIO,
                                                               umbral_mat='MI_PiedraLaja', aplique=True))
        k.k_window(m, 'MI_PiedraLaja', 0.0, 820.0, 1300.0, 80.0, 330.0, dict(persiana=None, cortina=False,
                                                                           marco=k.M_ALUMINIO, alfeizar='MI_PiedraLaja'))
        box(m, 'MI_Emisivo_Calido', -200.0, -198.0, 830.0, 1290.0, 280.0, 320.0)
        k.k_cortina_local(m, 0.0, 60.0, 480.0, Z_VER, 330.0)
        _cartel(m, 'MI_Cartel_Azul', 40.0, 500.0, 345.0, 420.0)
        P.placa_texto(m, 'MI_Comercio_FarmaciaDelBarrio', 10.0, 270.0, 356.0, 420.0)
        cbox(m, 'MI_PiedraLaja', -1.0, 3.0, 0.0, Lf, 0.0, 80.0, 1.0, 'y')

    def dE(m):
        k.k_cortina_local(m, 0.0, 80.0, 600.0, Z_VER, 330.0)
        k.k_window(m, 'MI_PiedraLaja', 0.0, 660.0, 900.0, 90.0, 330.0, dict(reja='cuadricula', persiana=None,
                                                                          cortina=False, alfeizar='MI_Hormigon'))
        _vidriera_interior(m, rng, 660.0, 900.0, 90.0, 330.0)
        k.k_cortina_local(m, 0.0, 960.0, 1400.0, Z_VER, 330.0)
        _cartel(m, 'MI_Cartel_Verde', 60.0, 640.0, 345.0, 420.0)
        _cartel(m, 'MI_Cartel_Rojo', 940.0, 1420.0, 345.0, 420.0)
        P.placa_texto(m, 'MI_Comercio_PizzeriaLoDeCacho', 10.0, 350.0, 350.0, 520.0)
        P.placa_texto(m, 'MI_Comercio_LavaderoBurbujas', 10.0, 1180.0, 355.0, 440.0)

    def dC(m):
        k.k_window(m, 'MI_PiedraLaja', 0.0, 60.0, 340.0, 80.0, 330.0, dict(persiana=None, cortina=False,
                                                                         marco=k.M_ALUMINIO))
        _vidriera_interior(m, rng, 60.0, 340.0, 80.0, 330.0)
    k.piece('Torre PB N', facade_run, mb, (0.0, c, 0.0), 0.0, Lf, 0.0, zpb, 'MI_PiedraLaja', hN, (), 30.0, dN, False)
    k.piece('Torre PB E', facade_run, mb, (-S, 0.0, 0.0), -90.0, Lf, 0.0, zpb, 'MI_PiedraLaja', hE, (), 30.0, dE, False)
    k.piece('Torre PB ochava', facade_run, mb, (-c, 0.0, 0.0), -45.0, Lc, 0.0, zpb, 'MI_PiedraLaja', hC, (), 30.0, dC,
            False)
    # coronamiento: sala de máquinas, tanques, mástil con baliza roja (hito nocturno)
    mx0, mx1, my0, my1 = -1150.0, -650.0, 600.0, 1150.0
    box(mb, 'MI_Revoque_Blanco', mx0, mx1, my0, my1, ztop, ztop + 320.0)
    box(mb, 'MI_Pintura_Blanca', mx0 - 10.0, mx1 + 10.0, my0 - 10.0, my1 + 10.0, ztop + 320.0, ztop + 335.0)
    box(mb, 'MI_Emisivo_Calido', mx1, mx1 + 1.0, my0 + 200.0, my0 + 320.0, ztop + 120.0, ztop + 240.0)
    for (tx, ty) in ((-1350.0, 400.0), (-1350.0, 1300.0)):
        k.piece('Torre tanque', k.tanque_simple, mb, tx, ty, ztop + 2.0, 90.0, 160.0)
    k.piece('Torre antena', _antena_reticulada, mb, -900.0, 875.0, ztop + 335.0, 1250.0)
    # colisión (toda la torre cerrada)
    mb.col(-S, 0.0, c, S, -1.0, ztop + 106.0)
    mb.col(-S, -c, 0.0, c, -1.0, ztop + 106.0)
    mb.ramps.append(([(0.0, c), (-c, 0.0), (-c, c)], 'z', -1.0, ztop + 106.0))
    return mb


# =====================================================================================
# RELLENO DE FONDOS DE MANZANA
# =====================================================================================
CORE_INSET = 855.0


def core_rect(mid):
    x0, x1, y0, y1 = L.mz_bounds(mid)
    d = CORE_INSET
    return (x0 + d, x1 - d, y0 + d, y1 - d)


def core_exclusions(mid):
    x0, x1, y0, y1 = L.mz_bounds(mid)
    ex = []
    for (m, ax, a0, a1) in L.PASILLOS:
        if m != mid:
            continue
        c0, c1 = L.pasillo_clear(mid)
        t = L.PH_WALL
        if ax == 'NS':
            ex.append((c0 - t, c1 + t, y0, y1))
        else:
            ex.append((x0, x1, c0 - t, c1 + t))
    if mid == 'M01':
        ex.append((x0, x1, L.BALDIO_Y[0], L.BALDIO_Y[1]))
    if mid == 'M10':
        ex.append(comisaria_rear_world())
    if mid == 'M21':
        ex.append(torre_rect_world())
    return ex


def build_core(name, rect, excl, seed, hmin=320.0, hmax=680.0, cell=LOT):
    """Fondos de manzana: celdas de ~8,66 m de techos, medianeras y tanques a alturas variadas, cerradas y
    con colisión (no se entra; desde la calle no se ve vacío). Actor en el origen (mundo)."""
    rng = random.Random(seed)
    mb = MB(name)
    x0, x1, y0, y1 = rect
    nx = max(1, int(round((x1 - x0) / cell)))
    ny = max(1, int(round((y1 - y0) / cell)))
    dx, dy = (x1 - x0) / nx, (y1 - y0) / ny
    walls = ['MI_Ladrillo', 'MI_Revoque_Gris', 'MI_Revoque_Gris', 'MI_Revoque_Blanco', 'MI_Hormigon']
    for i in range(nx):
        for j in range(ny):
            cx0, cx1 = x0 + i * dx, x0 + (i + 1) * dx
            cy0, cy1 = y0 + j * dy, y0 + (j + 1) * dy
            h = rng.uniform(hmin, hmax)
            wall = rng.choice(walls)
            for (a0, a1, b0, b1) in k.rect_minus(cx0, cx1, cy0, cy1, excl):
                if a1 - a0 < 40.0 or b1 - b0 < 40.0:
                    continue
                box(mb, wall, a0, a1, b0, b1, -1.0, h - 14.0)
                box(mb, 'MI_Hormigon', a0, a1, b0, b1, h - 14.0, h)
                mb.col(a0, a1, b0, b1, -1.0, h)
                r = rng.random()
                big = (a1 - a0) > 300.0 and (b1 - b0) > 300.0
                if r < 0.22 and big:
                    k.tanque_simple(mb, rng.uniform(a0 + 120.0, a1 - 120.0), rng.uniform(b0 + 120.0, b1 - 120.0), h,
                                    rng.uniform(40.0, 55.0), rng.uniform(90.0, 120.0))
                elif r < 0.42 and big:
                    prism(mb, rng.choice(['MI_Chapa_Gris', 'MI_Chapa_Verde', 'MI_Tejas']),
                          [(a0, h), (a1, h), (a1, h + 8.0), (a0, h + rng.uniform(35.0, 90.0))], 'y', b0, b1)
                elif r < 0.6 and big:
                    hh = h + rng.uniform(140.0, 380.0)
                    if rng.random() < 0.5:
                        box(mb, rng.choice(walls), a0, a0 + 30.0, b0, b1, h, hh)
                    else:
                        box(mb, rng.choice(walls), a0, a1, b0, b0 + 30.0, h, hh)
                elif r < 0.7 and big:
                    for q in range(rng.randint(2, 4)):     # ropa tendida / parrilla: cajas chicas
                        rbox(mb, rng.choice(['MI_Cartel_Blanco', 'MI_Cartel_Azul', 'MI_Cartel_Rojo']),
                             rng.uniform(a0 + 60.0, a1 - 60.0), rng.uniform(b0 + 60.0, b1 - 60.0), h + 90.0,
                             rng.uniform(40.0, 70.0), 1.0, rng.uniform(40.0, 60.0), rng.uniform(0, 180))
    return mb


# =====================================================================================
# PASILLOS DE PH (tramo interior entre los dos lotes PH)
# =====================================================================================
PH_DEPTH = 860.0


def _pasillo_geom(mid):
    entry = [p for p in L.PASILLOS if p[0] == mid][0]
    _, ax, a0, a1 = entry
    c0, c1 = L.pasillo_clear(mid)
    x0, x1, y0, y1 = L.mz_bounds(mid)
    if ax == 'NS':
        s0, s1 = y0 + PH_DEPTH, y1 - PH_DEPTH
    else:
        s0, s1 = x0 + PH_DEPTH, x1 - PH_DEPTH
    return ax, c0, c1, s0, s1


def pasillo_lums(mid):
    """Un aplique por puerta (contrato de luminarias) a 2,45 m, del lado del pasillo."""
    ax, c0, c1, s0, s1 = _pasillo_geom(mid)
    out = []
    for d in L.pasillo_doors():
        if d['mid'] != mid:
            continue
        off = d['wall'] - d['side'] * 30.0
        if ax == 'NS':
            out.append({'pos': (off, d['along'], 245.0), 'street': 'pasillo'})
        else:
            out.append({'pos': (d['along'], off, 245.0), 'street': 'pasillo'})
    return out


def build_pasillo(mid, seed):
    """Tramo interior de un pasillo de PH (1,85 m libres entre tapiales de 2,5 m) con 2-3 puertas de PH
    (robables), apliques y plantas sin colisión. Actor en el origen (mundo)."""
    rng = random.Random(seed)
    ax, c0, c1, s0, s1 = _pasillo_geom(mid)
    t = L.PH_WALL
    H = 250.0
    mb = MB('Pasillo_' + mid)
    doors = [d for d in L.pasillo_doors() if d['mid'] == mid]
    Lw = s1 - s0
    if ax == 'NS':
        box(mb, 'MI_Hormigon', c0 - t, c1 + t, s0, s1, -1.0, Z_VER + 1.0)
        mb.col(c0 - t, c1 + t, s0, s1, -1.0, Z_VER + 1.0)
        walls = [((c0, s0, 0.0), 0.0, -1, lambda a: a - s0), ((c1, s1, 0.0), 180.0, 1, lambda a: s1 - a)]
    else:
        box(mb, 'MI_Hormigon', s0, s1, c0 - t, c1 + t, -1.0, Z_VER + 1.0)
        mb.col(s0, s1, c0 - t, c1 + t, -1.0, Z_VER + 1.0)
        walls = [((s1, c0, 0.0), 90.0, -1, lambda a: s1 - a), ((s0, c1, 0.0), -90.0, 1, lambda a: a - s0)]
    for (p0, yaw, side, along) in walls:
        ds = [along(d['along']) for d in doors if d['side'] == side]
        holes = [(a - 45.0, a + 45.0, k.Z_PISO, 240.0) for a in ds]
        mat = rng.choice(['MI_Revoque_Gris', 'MI_Revoque_Blanco', 'MI_Ladrillo'])
        styles = ['chapa', 'tablero', 'vidriada']

        def deco(m, ds=ds, mat=mat):
            k.k_coping_y(m, 'MI_Hormigon', -t, 0.0, 0.0, Lw, H)
            for a in ds:
                k.k_door(m, 0.0, a - 45.0, a + 45.0, k.Z_PISO, 240.0,
                         dict(hoja=rng.choice([k.M_PUERTA, 'MI_Chapa_Verde', 'MI_Chapa_Gris']), estilo=rng.choice(styles),
                              marco=M_HIERRO, aplique=True, base_z=Z_VER + 1.0, umbral_mat='MI_Hormigon'))
                k.k_numero(m, 0.0, a - 70.0, 205.0)
            y = 300.0
            while y < Lw - 300.0:
                if all(abs(y - a) > 160.0 for a in ds) and rng.random() < 0.35:
                    k.k_planta(m, 18.0, y, Z_VER + 1.0, rng.uniform(0.8, 1.2), True)
                y += rng.uniform(250.0, 500.0)
            # manchas de humedad / revoque caído en el tapial
            for j in range(rng.randint(3, 6)):
                ya = rng.uniform(50.0, Lw - 200.0)
                box(m, rng.choice(['MI_Revoque_Gris', 'MI_Ladrillo', 'MI_Hormigon']), -1.0, 1.0, ya,
                    ya + rng.uniform(40.0, 160.0), rng.uniform(20.0, 60.0), rng.uniform(90.0, 200.0))
        k.piece('Pasillo muro %s %d' % (mid, side), facade_run, mb, p0, yaw, Lw, 0.0, H, mat, holes, (), t, deco, True)
    return mb


# =====================================================================================
# TERRENO BALDÍO (manzana 0,1, cruzable este-oeste)
# =====================================================================================
CASILLA = dict(x=(5450.0, 5750.0), y=(16546.0, 16846.0))


BALDIO_COVERS = [('auto', (3900.0, 16180.0), 12.0), ('bloques', (6450.0, 16960.0), 0.0),
                 ('chapa', (8050.0, 16120.0), -8.0), ('tambores', (2350.0, 16900.0), 0.0)]


def build_baldio(seed):
    """Baldío de 17 m que cruza la manzana: tierra, pasto, yuyos (sin colisión), montones de escombro legibles
    (losas con hierros, ladrillos, bloques), 4 coberturas altas escalonadas norte/sur (auto abandonado, pila de
    bloques de 1,4 m, chapas caídas apoyadas, tambores) que cortan la visual este-oeste, alambrado caído en los
    frentes, medianeras de 3 m con parches y la huella de la casa demolida, y casilla precaria (robo chico).
    Actor en el origen (mundo). El auto usa el slot MI_Auto_Blanco (build_barrio lo recolorea)."""
    rng = random.Random(seed)
    mb = MB('Baldio')
    x0, x1 = L.XCOL[0]
    y0, y1 = L.BALDIO_Y
    zg = Z_VER - 1.0
    box(mb, 'MI_Tierra', x0, x1, y0, y1, -1.0, zg)
    mb.col(x0, x1, y0, y1, -1.0, zg)
    for j in range(16):
        pts = k.jitter_poly(rng, rng.uniform(x0 + 300.0, x1 - 300.0), rng.uniform(y0 + 200.0, y1 - 200.0),
                            rng.uniform(150.0, 420.0), rng.uniform(80.0, 260.0), rng.randint(8, 11), 30.0)
        prism(mb, 'MI_Pasto', pts, 'z', zg - 1.0, zg + rng.uniform(0.4, 1.2))
    for j in range(70):
        blob(mb, 'MI_Follaje', (rng.uniform(x0 + 40.0, x1 - 40.0), rng.uniform(y0 + 40.0, y1 - 40.0), zg),
             rng.uniform(12.0, 35.0), rng.uniform(12.0, 35.0), rng.uniform(15.0, 45.0), yaw=rng.uniform(0, 180),
             steps=(4, 6))
    # escombros (cobertura PvP): montones con colisión de caja, separados > 2 m
    piles = [(3200.0, 16050.0), (4600.0, 16980.0), (6900.0, 16150.0), (8200.0, 16900.0), (2500.0, 16950.0),
             (9300.0, 15980.0), (7600.0, 17000.0)]
    for (px, py) in piles:
        w, d = rng.uniform(160.0, 260.0), rng.uniform(110.0, 170.0)
        hgt = rng.uniform(85.0, 125.0)
        for q in range(rng.randint(9, 14)):
            mat = rng.choice(['MI_Ladrillo', 'MI_Ladrillo', 'MI_Hormigon', 'MI_Revoque_Gris', 'MI_Madera'])
            rbox(mb, mat, px + rng.uniform(-w * 0.4, w * 0.4), py + rng.uniform(-d * 0.4, d * 0.4), zg,
                 rng.uniform(30.0, 90.0), rng.uniform(25.0, 70.0), rng.uniform(15.0, hgt * 0.7),
                 rng.uniform(0, 180), rng.uniform(-15, 15), rng.uniform(-15, 15))
        blob(mb, 'MI_Tierra', (px, py, zg), w * 0.55, d * 0.55, hgt * 0.55, steps=(5, 8))
        mb.col(px - w * 0.45, px + w * 0.45, py - d * 0.45, py + d * 0.45, zg, zg + hgt * 0.8)
        # pedazo de losa con hierros a la vista y ladrillos enteros: se lee "escombro de demolición"
        sa = rng.uniform(0, 180)
        rbox(mb, 'MI_Hormigon', px + rng.uniform(-30, 30), py + rng.uniform(-20, 20), zg + hgt * 0.35, 110.0, 70.0, 12.0,
             sa, rng.uniform(-20, 20), rng.uniform(-12, 12))
        for q in range(rng.randint(3, 5)):
            a = math.radians(sa + rng.uniform(-30, 30))
            p0 = (px + rng.uniform(-40, 40), py + rng.uniform(-25, 25), zg + hgt * 0.4)
            cyl(mb, M_HIERRO, p0, (p0[0] + math.cos(a) * rng.uniform(40, 90), p0[1] + math.sin(a) * rng.uniform(40, 90),
                                   p0[2] + rng.uniform(20, 70)), 0.6, 4)
        for q in range(rng.randint(4, 7)):
            rbox(mb, 'MI_Ladrillo', px + rng.uniform(-w * 0.5, w * 0.5), py + rng.uniform(-d * 0.6, d * 0.6), zg,
                 24.0, 12.0, 6.0, rng.uniform(0, 180), 0.0, rng.uniform(-20, 20))
    # basura suelta: neumáticos, un tambor, una heladera vieja
    for (px, py) in ((3900.0, 15800.0), (5100.0, 17100.0), (8800.0, 16400.0)):
        k.torus(mb, 'MI_Neumatico', (px, py, zg + 10.0), 26.0, 9.0, (0.1, 0.05, 1.0), 14, 6)
    cyl(mb, 'MI_Metal_Verde', (6300.0, 15800.0, zg), (6300.0, 15800.0, zg + 88.0), 29.0, 14)
    mb.col(6271.0, 6329.0, 15771.0, 15829.0, zg, zg + 88.0)
    rbox(mb, 'MI_Pintura_Blanca', 3600.0, 17120.0, zg, 70.0, 65.0, 165.0, 22.0, 0.0, -9.0)
    mb.col(3560.0, 3640.0, 17085.0, 17155.0, zg, zg + 160.0)
    # coberturas altas escalonadas (alternan sur / norte: no queda una visual recta este-oeste)
    for (kind, (px, py), yaw) in BALDIO_COVERS:
        k.piece('Baldio cobertura ' + kind, _baldio_cobertura, mb, rng, kind, px, py, yaw, zg)
    # medianeras (3 m) con parches de revoque, ladrillo y hormigón, y la huella de la casa demolida
    for (ya, yb, sign) in ((y0, y0 + 15.0, 1.0), (y1 - 15.0, y1, -1.0)):
        box(mb, 'MI_Ladrillo', x0, x1, ya, yb, -1.0, 300.0)
        k.k_coping_x(mb, 'MI_Hormigon', ya, yb, x0, x1, 300.0, 1 if sign < 0 else -1)
        mb.col(x0, x1, ya, yb, -1.0, 300.0)
        face = yb if sign > 0 else ya
        face_patches(mb, rng, 'y', face, sign, x0 + 100.0, x1 - 100.0, 0.0, 290.0,
                     ['MI_Revoque_Gris', 'MI_Revoque_Blanco', 'MI_Hormigon', 'MI_Revoque_Rosa'], 18)
        # huella de la casa demolida: revoque de los cuartos (dos colores), zócalo y perfil del techo a dos aguas
        hx0 = rng.uniform(x0 + 1500.0, x1 - 4500.0)
        for (a, b, m) in ((hx0, hx0 + 1100.0, 'MI_Revoque_VerdeAgua'), (hx0 + 1130.0, hx0 + 2300.0, 'MI_Revoque_Amarillo')):
            box(mb, m, a, b, face - sign * 1.0, face + sign * 1.6, 0.0, 250.0)
            box(mb, 'MI_Revoque_Gris', a, b, face + sign * 1.6, face + sign * 2.0, 0.0, 22.0)
        for (a, b, z0_, z1_) in ((hx0, hx0 + 1150.0, 250.0, 292.0), (hx0 + 1150.0, hx0 + 2300.0, 292.0, 250.0)):
            Lr = math.hypot(b - a, z1_ - z0_)
            ang = math.degrees(math.atan2(z1_ - z0_, b - a))
            rbox(mb, 'MI_Hormigon', 0.5 * (a + b), face + sign * 1.8, 0.5 * (z0_ + z1_) - 5.0, Lr, 1.6, 10.0, 0.0,
                 0.0, 0.0) if abs(ang) < 0.01 else _huella_techo(mb, a, b, z0_, z1_, face + sign * 1.8)
        for q in range(2):
            P.pintada(mb, rng.randint(1, 4), rng.uniform(x0 + 600.0, x1 - 600.0), face, rng.uniform(40.0, 110.0),
                      rng.uniform(120.0, 170.0), 90.0 * sign)
        # caño de desagüe y cables viejos
        xp = rng.uniform(x0 + 800.0, x1 - 800.0)
        cyl(mb, 'MI_Plastico_Negro', (xp, face + sign * 6.0, 0.0), (xp, face + sign * 6.0, 300.0), 4.0, 8)
    # alambrado caído en los dos frentes (los extremos quedan parados, el medio se cruza)
    for (xf, s) in ((x0, 1.0), (x1, -1.0)):
        y = y0 + 40.0
        while y < y1 - 30.0:
            standing = (y < y0 + 330.0) or (y > y1 - 330.0) or rng.random() < 0.25
            if standing:
                box(mb, 'MI_Hormigon', xf + s * 8.0 - 6.0, xf + s * 8.0 + 6.0, y - 6.0, y + 6.0, -1.0, 205.0)
            else:
                rbox(mb, 'MI_Hormigon', xf + s * 60.0, y, zg, 12.0, 12.0, 160.0, rng.uniform(-20, 20),
                     s * rng.uniform(50.0, 80.0), rng.uniform(-10, 10))
            y += 250.0
        for (ya, yb) in ((y0 + 15.0, y0 + 330.0), (y1 - 330.0, y1 - 15.0)):
            box(mb, 'MI_Alambrado', xf + s * 8.0 - 0.3, xf + s * 8.0 + 0.3, ya, yb, 10.0, 200.0)
            mb.col(xf + s * 8.0 - 6.0, xf + s * 8.0 + 6.0, ya, yb, -1.0, 205.0)
        for j in range(3):
            yc = rng.uniform(y0 + 600.0, y1 - 600.0)
            rbox(mb, 'MI_Alambrado', xf + s * 110.0, yc, zg + 1.0, 200.0, rng.uniform(300.0, 500.0), 0.6,
                 rng.uniform(-8, 8), 0.0, rng.uniform(-3, 3))
    # casilla precaria (puerta al sur: punto de robo chico)
    cx0, cx1 = CASILLA['x']
    cy0, cy1 = CASILLA['y']
    W_ = cx1 - cx0

    def dhut(m):
        k.k_door(m, 0.0, 110.0, 190.0, 20.0, 205.0, dict(hoja='MI_Madera', estilo='chapa', marco='MI_Madera',
                                                          umbral=False))
        prism(m, 'MI_Chapa_Gris', k.ribs_profile_xy(-2.0, 0.8, 0.0, 100.0, 7.6, 1.6), 'z', 0.0, 230.0)
        prism(m, 'MI_Chapa_Gris', k.ribs_profile_xy(-2.0, 0.8, 200.0, W_, 7.6, 1.6), 'z', 0.0, 230.0)
    facade_run(mb, (cx0, cy0, 0.0), -90.0, W_, 0.0, 230.0, 'MI_Madera', [(110.0, 190.0, 20.0, 205.0)], (), 6.0, dhut,
               False)
    box(mb, 'MI_Chapa_Verde', cx0, cx0 + 6.0, cy0 + 6.0, cy1, 0.0, 225.0)
    box(mb, 'MI_Chapa_Gris', cx1 - 6.0, cx1, cy0 + 6.0, cy1, 0.0, 220.0)
    box(mb, 'MI_Madera', cx0, cx1, cy1 - 6.0, cy1, 0.0, 215.0)
    prism(mb, 'MI_Chapa_Gris', [(cy0 - 40.0, 236.0), (cy1 + 30.0, 214.0), (cy1 + 30.0, 218.0), (cy0 - 40.0, 240.0)], 'x',
          cx0 - 30.0, cx1 + 30.0)
    for (tx, ty) in ((cx0 + 60.0, cy0 + 80.0), (cx1 - 70.0, cy1 - 60.0)):
        k.torus(mb, 'MI_Neumatico', (tx, ty, 240.0), 25.0, 8.0, (0, 0, 1), 12, 5)
    box(mb, 'MI_Madera', cx0, cx1, cy0, cy1, zg, 20.0)
    mb.col(cx0, cx1, cy0, cy1, -1.0, 236.0)
    return mb


def _huella_techo(mb, a, b, z0, z1, yface):
    """Franja inclinada (marca del techo de la casa demolida) en la medianera (plano y = yface)."""
    n = 8
    for i in range(n):
        t0, t1 = i / float(n), (i + 1) / float(n)
        xa, xb = a + (b - a) * t0, a + (b - a) * t1
        za, zb = z0 + (z1 - z0) * t0, z0 + (z1 - z0) * t1
        box(mb, 'MI_Hormigon', xa, xb, yface - 0.8, yface + 0.8, min(za, zb) - 8.0, max(za, zb) + 2.0)


def _baldio_cobertura(mb, rng, kind, px, py, yaw, zg):
    """Coberturas altas del baldío."""
    if kind == 'auto':
        car = P.build_auto('hatch')
        k.merge_mb(mb, car, (px, py, zg - 6.0), yaw)                 # sin ruedas a la vista: hundido en la tierra
        for (dx, dy) in ((-140.0, -70.0), (140.0, 70.0), (-140.0, 70.0), (140.0, -70.0)):
            c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            box(mb, 'MI_Hormigon', px + dx * c - dy * s_ - 15.0, px + dx * c - dy * s_ + 15.0,
                py + dx * s_ + dy * c - 15.0, py + dx * s_ + dy * c + 15.0, zg, zg + 22.0)
        for q in range(6):
            blob(mb, 'MI_Follaje', (px + rng.uniform(-220, 220), py + rng.uniform(-110, 110), zg), rng.uniform(15, 35),
                 rng.uniform(15, 30), rng.uniform(30, 70), yaw=rng.uniform(0, 180), steps=(4, 6))
    elif kind == 'bloques':
        # pila de bloques de hormigón de 1,4 m sobre dos pallets
        for (ox, n) in ((-65.0, 7), (65.0, 6)):
            box(mb, 'MI_Madera', px + ox - 60.0, px + ox + 60.0, py - 55.0, py + 55.0, zg, zg + 14.0)
            for j in range(n):
                z = zg + 14.0 + j * 18.0
                for q in range(3):
                    box(mb, 'MI_Hormigon', px + ox - 58.0 + q * 39.0, px + ox - 21.0 + q * 39.0, py - 52.0, py + 52.0,
                        z, z + 17.5)
        box(mb, 'MI_Hormigon', px - 20.0, px + 30.0, py + 60.0, py + 110.0, zg, zg + 19.0)
        mb.col(px - 125.0, px + 125.0, py - 55.0, py + 55.0, zg, zg + 140.0)
    elif kind == 'chapa':
        # chapas acanaladas caídas y apoyadas en un tirante: pantalla de 1,8 m
        for j in range(4):
            rbox(mb, rng.choice(['MI_Chapa_Gris', 'MI_Chapa_Verde']), px + (j - 1.5) * 75.0, py + j * 3.0, zg, 92.0, 2.0,
                 190.0 - j * 6.0, yaw, 0.0, 14.0 + rng.uniform(-3, 3))
        rbox(mb, 'MI_Madera', px, py + 30.0, zg, 330.0, 10.0, 10.0, yaw)
        for q in range(3):
            rbox(mb, 'MI_Chapa_Gris', px + rng.uniform(-150, 150), py - rng.uniform(40, 120), zg, 200.0, 85.0, 1.5,
                 yaw + rng.uniform(-20, 20), rng.uniform(-4, 4), rng.uniform(-4, 4))
        c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        pts = [(px + x * c - y * s_, py + x * s_ + y * c) for (x, y) in ((-170.0, -10.0), (170.0, -10.0), (170.0, 50.0),
                                                                          (-170.0, 50.0))]
        mb.ramps.append((pts, 'z', zg, zg + 175.0))
    else:
        # tambores apilados y un portón viejo apoyado
        for (ox, oy, z) in ((-35.0, 0.0, 0.0), (35.0, 0.0, 0.0), (0.0, -55.0, 0.0), (0.0, -20.0, 88.0)):
            cyl(mb, rng.choice(['MI_Metal_Verde', 'MI_Cartel_Azul', 'MI_Chapa_Gris']), (px + ox, py + oy, zg + z),
                (px + ox, py + oy, zg + z + 88.0), 29.0, 14)
        rbox(mb, 'MI_Metal_Negro', px + 40.0, py + 45.0, zg, 260.0, 4.0, 170.0, 0.0, 0.0, 10.0)
        mb.col(px - 70.0, px + 70.0, py - 85.0, py + 50.0, zg, zg + 170.0)


# =====================================================================================
# PLAZA (manzana 1,1 entera)
# =====================================================================================
PLAZA_C = (0.5 * (L.XCOL[1][0] + L.XCOL[1][1]), 0.5 * (L.YROW[1][0] + L.YROW[1][1]))
Z_PASTO = Z_VER + 1.5
Z_SENDA = Z_VER + 2.5
PLAYGROUND = (2500.0, 3800.0, -1900.0, -700.0)       # desplazamiento desde el centro (cuadrante SE)


PLAZA_HALF = 0.5 * (L.XCOL[1][1] - L.XCOL[1][0])
PLAZA_PW = 250.0                       # senda perimetral
MONUMENTO = (0.0, 0.0)                 # monumento en el centro de la plazoleta (desplazamiento)
MASTIL = (520.0, 520.0)                # el mástil pasa a un costado de la plazoleta


def plaza_clear(dx, dy, m=0.0):
    """True si el punto (desplazamiento desde el centro) no pisa sendas, plazoleta, juegos ni kioscos."""
    h = PLAZA_HALF
    if abs(dx) < 175.0 + m or abs(dy) < 175.0 + m:                 # sendas en cruz
        return False
    if abs(abs(dx) - abs(dy)) / SQ2 < 150.0 + m:                    # diagonales
        return False
    if abs(dx) > h - PLAZA_PW - m or abs(dy) > h - PLAZA_PW - m:    # senda perimetral
        return False
    if math.hypot(dx, dy) < 912.0 + m:                              # plazoleta
        return False
    if PLAYGROUND[0] - m - 80.0 < dx < PLAYGROUND[1] + m + 80.0 and PLAYGROUND[2] - m - 80.0 < dy < PLAYGROUND[3] + m + 80.0:
        return False
    cx, cy = PLAZA_C
    for (kx, ky, r) in ((L.KIOSCO_DIARIOS[0], L.KIOSCO_DIARIOS[1], 300.0), (L.KIOSCO_PLAZA[0], L.KIOSCO_PLAZA[1], 360.0)):
        if math.hypot(cx + dx - kx, cy + dy - ky) < r + m:
            return False
    return True


def plaza_layout():
    """Posiciones fijas (mundo) de árboles (dos anillos desfasados), bancos, farolas, canastos y coberturas
    (canteros de ladrillo de 80 cm y setos de 1,1 m cada 6-8 m en el pasto, nunca sobre las sendas)."""
    cx, cy = PLAZA_C
    trees, benches, farolas, canastos, covers = [], [], [], [], []
    offs = [(1300.0, 2700.0), (2700.0, 1300.0), (1300.0, 3700.0), (3700.0, 1300.0), (2500.0, 3700.0), (3700.0, 2500.0),
            (2000.0, 1000.0), (1000.0, 2000.0)]
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for j, (ox, oy) in enumerate(offs):
                px, py = cx + sx * ox, cy + sy * oy
                if sx > 0 and sy < 0:
                    dx, dy = ox, -oy
                    if PLAYGROUND[0] - 300.0 < dx < PLAYGROUND[1] + 300.0 and PLAYGROUND[2] - 300.0 < dy < PLAYGROUND[3] + 300.0:
                        continue
                if abs(px - L.KIOSCO_DIARIOS[0]) < 450.0 and abs(py - L.KIOSCO_DIARIOS[1]) < 450.0:
                    continue
                if abs(px - L.KIOSCO_PLAZA[0]) < 500.0 and abs(py - L.KIOSCO_PLAZA[1]) < 500.0:
                    continue
                if j >= 6 and (sx * sy) > 0:
                    continue
                trees.append({'pos': (px, py, Z_PASTO - Z_VER), 'kind': ('fresno', 'platano')[(j + int(sx > 0)) % 2],
                              'seed': j % 3, 'yaw': (j * 47.0 + sx * 30.0 + sy * 70.0) % 360.0})
    # segundo anillo, desfasado respecto del primero (rompe las visuales en diagonal de cuadrante a cuadrante)
    offs2 = [(1950.0, 3250.0), (3250.0, 1950.0), (650.0, 3450.0), (3450.0, 650.0), (1650.0, 2250.0), (2250.0, 1650.0),
             (3000.0, 3300.0), (3300.0, 3000.0)]
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for j, (ox, oy) in enumerate(offs2):
                dx, dy = sx * ox, sy * oy
                if not plaza_clear(dx, dy, 120.0):
                    continue
                if any(math.hypot(cx + dx - t['pos'][0], cy + dy - t['pos'][1]) < 550.0 for t in trees):
                    continue
                trees.append({'pos': (cx + dx, cy + dy, Z_PASTO - Z_VER), 'kind': ('platano', 'fresno')[j % 2],
                              'seed': (j + 1) % 3, 'yaw': (j * 71.0 + sx * 50.0 + sy * 20.0) % 360.0, 'ring': 2})
    # bancos a los costados de los dos ejes, mirando al sendero
    for d in (1500.0, 3100.0):
        for s in (-1.0, 1.0):
            benches.append({'pos': (cx + 300.0, cy + s * d, Z_SENDA), 'yaw': 180.0})
            benches.append({'pos': (cx - 300.0, cy + s * d + 400.0 * s, Z_SENDA), 'yaw': 0.0})
            benches.append({'pos': (cx + s * d, cy + 300.0, Z_SENDA), 'yaw': -90.0})
            benches.append({'pos': (cx + s * d + 400.0 * s, cy - 300.0, Z_SENDA), 'yaw': 90.0})
    for a in (45.0, 135.0, 225.0, 315.0):
        r = 1050.0
        benches.append({'pos': (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)), Z_SENDA),
                        'yaw': a + 180.0})
    for d in (2500.0, 3950.0):
        farolas.append((cx - 260.0, cy + d, Z_SENDA))
        farolas.append((cx + 260.0, cy - d, Z_SENDA))
        farolas.append((cx + d, cy + 260.0, Z_SENDA))
        farolas.append((cx - d, cy - 260.0, Z_SENDA))
    for a in (0.0, 90.0, 180.0, 270.0):
        r = 980.0
        farolas.append((cx + r * math.cos(math.radians(a + 22.0)), cy + r * math.sin(math.radians(a + 22.0)), Z_SENDA))
    for a in (60.0, 150.0, 240.0, 330.0):
        r = 1150.0
        canastos.append({'pos': (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)), Z_SENDA - Z_VER),
                         'yaw': a})
    # coberturas en grilla de ~7 m con jitter determinista, alineadas con la senda más cercana
    rng = random.Random(1111)
    busy = [(t['pos'][0], t['pos'][1], 170.0) for t in trees] + [(b['pos'][0], b['pos'][1], 230.0) for b in benches] + \
           [(f[0], f[1], 150.0) for f in farolas] + \
           [(cx + 1350.0 * math.cos(math.radians(a)), cy + 1350.0 * math.sin(math.radians(a)), 300.0)
            for a in (20.0, 110.0, 200.0, 290.0)] + [(q['pos'][0], q['pos'][1], 200.0) for q in canastos]
    step = 620.0
    n = int(PLAZA_HALF // step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            dx = i * step + (step * 0.5 if j % 2 else 0.0) + rng.uniform(-110.0, 110.0)
            dy = j * step + rng.uniform(-110.0, 110.0)
            if not plaza_clear(dx, dy, 165.0):
                continue
            x, y = cx + dx, cy + dy
            if any(math.hypot(x - bx, y - by) < r for (bx, by, r) in busy):
                continue
            # dirección de la senda más cercana: cruz (0 / 90) o diagonal (45 / -45)
            dcross = min(abs(dx), abs(dy))
            ddiag = abs(abs(dx) - abs(dy)) / SQ2
            if dcross < ddiag:
                yaw = 90.0 if abs(dx) < abs(dy) else 0.0
            else:
                yaw = 45.0 if dx * dy > 0 else -45.0
            kind = 'cantero' if rng.random() < 0.55 else 'seto'
            covers.append({'kind': kind, 'pos': (x, y), 'yaw': yaw,
                           'size': (260.0, 100.0) if kind == 'cantero' else (300.0, 80.0),
                           'h': rng.uniform(70.0, 90.0) if kind == 'cantero' else 110.0})
            busy.append((x, y, 300.0))
    return {'trees': trees, 'benches': benches, 'farolas': farolas, 'canastos': canastos, 'covers': covers}


def plaza_lums():
    return [{'pos': (x, y, z + P.FAROLA_LUM_Z - 8.0), 'street': 'plaza'} for (x, y, z) in plaza_layout()['farolas']]


def _juegos(mb, ox, oy, z0):
    """Juegos de plaza simples: arenero, hamacas, tobogán, sube y baja (cuadrante SE)."""
    x0, x1 = ox + PLAYGROUND[0], ox + PLAYGROUND[1]
    y0, y1 = oy + PLAYGROUND[2], oy + PLAYGROUND[3]
    box(mb, 'MI_Tierra', x0 + 15.0, x1 - 15.0, y0 + 15.0, y1 - 15.0, z0 - 2.0, z0 + 1.0)
    for (a0, a1, b0, b1) in ((x0, x1, y0, y0 + 15.0), (x0, x1, y1 - 15.0, y1), (x0, x0 + 15.0, y0, y1),
                             (x1 - 15.0, x1, y0, y1)):
        box(mb, 'MI_Hormigon', a0, a1, b0, b1, z0 - 2.0, z0 + 18.0)
    # hamacas
    hx, hy = x0 + 350.0, 0.5 * (y0 + y1)
    for yy in (hy - 160.0, hy + 160.0):
        for s in (-1.0, 1.0):
            cyl(mb, 'MI_Metal_Verde', (hx + s * 90.0, yy, z0), (hx, yy, z0 + 245.0), 4.0, 10)
        for s in (-1.0, 1.0):
            mb.col(hx + s * 90.0 - 6.0, hx + s * 90.0 + 6.0, yy - 6.0, yy + 6.0, z0, z0 + 120.0)
        mb.col(hx - 50.0, hx + 50.0, yy - 6.0, yy + 6.0, z0 + 120.0, z0 + 248.0)
    cyl(mb, 'MI_Metal_Verde', (hx, hy - 165.0, z0 + 245.0), (hx, hy + 165.0, z0 + 245.0), 4.5, 10)
    # trepador (cubo de caños) con colisión: cobertura en los juegos
    qx, qy = x0 + 680.0, 0.5 * (y0 + y1)
    for (ax_, ay_) in ((-100.0, -100.0), (100.0, -100.0), (100.0, 100.0), (-100.0, 100.0)):
        cyl(mb, 'MI_Cartel_Azul', (qx + ax_, qy + ay_, z0), (qx + ax_, qy + ay_, z0 + 180.0), 3.5, 8)
    for zz in (60.0, 120.0, 180.0):
        for (a, b) in (((-100.0, -100.0), (100.0, -100.0)), ((100.0, -100.0), (100.0, 100.0)),
                       ((100.0, 100.0), (-100.0, 100.0)), ((-100.0, 100.0), (-100.0, -100.0))):
            cyl(mb, 'MI_Pintura_Amarilla', (qx + a[0], qy + a[1], z0 + zz), (qx + b[0], qy + b[1], z0 + zz), 2.5, 6)
    box(mb, 'MI_Madera', qx - 100.0, qx + 100.0, qy - 100.0, qy + 100.0, z0 + 118.0, z0 + 124.0)
    mb.col(qx - 103.0, qx + 103.0, qy - 103.0, qy + 103.0, z0, z0 + 124.0)
    # pirca de ladrillo de 75 cm en dos lados del sector de juegos (con paso al medio)
    for (a0, a1) in ((x0 + 40.0, x0 + 520.0), (x0 + 800.0, x1 - 40.0)):
        box(mb, 'MI_Ladrillo', a0, a1, y0 - 30.0, y0 - 16.0, z0 - 2.0, z0 + 75.0)
        mb.col(a0, a1, y0 - 30.0, y0 - 16.0, z0 - 2.0, z0 + 75.0)
    for (b0, b1) in ((y0 + 40.0, 0.5 * (y0 + y1) - 160.0), (0.5 * (y0 + y1) + 160.0, y1 - 40.0)):
        box(mb, 'MI_Ladrillo', x0 - 30.0, x0 - 16.0, b0, b1, z0 - 2.0, z0 + 75.0)
        mb.col(x0 - 30.0, x0 - 16.0, b0, b1, z0 - 2.0, z0 + 75.0)
    for ys in (hy - 70.0, hy + 70.0):
        for dx in (-18.0, 18.0):
            cyl(mb, M_HIERRO, (hx + dx * 0.3, ys, z0 + 243.0), (hx + dx, ys, z0 + 50.0), 0.6, 4)
        box(mb, 'MI_Neumatico', hx - 22.0, hx + 22.0, ys - 12.0, ys + 12.0, z0 + 45.0, z0 + 50.0)
    # tobogán (escalera + rampa)
    tx, ty = x0 + 900.0, y0 + 250.0
    for s in (-1.0, 1.0):
        cyl(mb, 'MI_Cartel_Rojo', (tx - 60.0, ty + s * 30.0, z0), (tx - 40.0, ty + s * 30.0, z0 + 160.0), 2.5, 8)
    for j in range(5):
        zz = z0 + 25.0 + j * 30.0
        cyl(mb, 'MI_Cartel_Rojo', (tx - 57.0 + j * 4.0, ty - 30.0, zz), (tx - 57.0 + j * 4.0, ty + 30.0, zz), 1.6, 6)
    box(mb, 'MI_Pintura_Amarilla', tx - 40.0, tx + 10.0, ty - 32.0, ty + 32.0, z0 + 150.0, z0 + 156.0)
    for (px, py) in ((tx - 40.0, ty - 30.0), (tx - 40.0, ty + 30.0), (tx + 8.0, ty - 30.0), (tx + 8.0, ty + 30.0)):
        cyl(mb, 'MI_Metal_Verde', (px, py, z0), (px, py, z0 + 156.0), 2.5, 8)
    slide = [(tx + 10.0, z0 + 150.0), (tx + 230.0, z0 + 20.0), (tx + 260.0, z0 + 20.0), (tx + 260.0, z0 + 26.0),
             (tx + 230.0, z0 + 26.0), (tx + 10.0, z0 + 156.0)]
    prism(mb, 'MI_Pintura_Amarilla', slide, 'y', ty - 28.0, ty + 28.0)
    for s in (-1.0, 1.0):
        prism(mb, 'MI_Cartel_Rojo', [(tx + 10.0, z0 + 156.0), (tx + 230.0, z0 + 26.0), (tx + 230.0, z0 + 40.0),
                                     (tx + 10.0, z0 + 170.0)], 'y', ty + s * 28.0 - 2.0, ty + s * 28.0 + 2.0)
    mb.col(tx - 62.0, tx + 10.0, ty - 34.0, ty + 34.0, z0, z0 + 156.0)
    # sube y baja
    sx, sy = x0 + 900.0, y1 - 250.0
    cbox(mb, 'MI_Metal_Verde', sx - 12.0, sx + 12.0, sy - 20.0, sy + 20.0, z0, z0 + 45.0, 2.0, 'z')
    rbox(mb, 'MI_Madera', sx, sy, z0 + 40.0, 340.0, 24.0, 5.0, 0.0, 9.0, 0.0)
    mb.col(sx - 14.0, sx + 14.0, sy - 22.0, sy + 22.0, z0, z0 + 45.0)


def _kiosco_diarios(mb, cx, cy, z0):
    x0, x1, y0, y1 = cx - 110.0, cx + 110.0, cy - 80.0, cy + 80.0
    box(mb, 'MI_Metal_Verde', x0, x1, y0 + 4.0, y1, z0, z0 + 230.0)
    cbox(mb, 'MI_Metal_Verde', x0 - 30.0, x1 + 30.0, y0 - 30.0, y1 + 30.0, z0 + 230.0, z0 + 244.0, 2.0, 'y')
    sp = k.slats_profile(y0 - 2.0, 1.0, z0 + 10.0, z0 + 215.0, 8.0, 1.0)
    if sp:
        prism(mb, 'MI_Chapa_Gris', [(q, p) for (p, q) in sp], 'x', x0 + 10.0, x1 - 10.0)
    for (xa, sgn) in ((x0, -1.0), (x1, 1.0)):
        for j in range(6):
            zz = z0 + 40.0 + j * 28.0
            box(mb, ['MI_Cartel_Rojo', 'MI_Cartel_Azul', 'MI_Cartel_Blanco', 'MI_Pintura_Amarilla'][j % 4],
                xa + sgn * 0.5, xa + sgn * 2.0, y0 + 20.0, y1 - 20.0, zz, zz + 24.0)
    box(mb, 'MI_Cartel_Rojo', x0, x1, y0 - 1.0, y0 + 4.0, z0 + 215.0, z0 + 229.0)
    mb.col(x0, x1, y0, y1, z0, z0 + 244.0)


def _kiosco_bebidas(mb, cx, cy, z0):
    x0, x1, y0, y1 = cx - 150.0, cx + 150.0, cy - 124.0, cy + 124.0
    box(mb, 'MI_Revoque_Blanco', x0, x1, y0 + 6.0, y1, z0, z0 + 250.0)
    cbox(mb, 'MI_Hormigon', x0 - 20.0, x1 + 20.0, y0 - 25.0, y1 + 20.0, z0 + 250.0, z0 + 262.0, 2.0, 'y')
    sp = k.slats_profile(y0 - 2.0, 1.0, z0 + 8.0, z0 + 225.0, 8.0, 1.0)
    if sp:
        prism(mb, 'MI_Chapa_Gris', [(q, p) for (p, q) in sp], 'x', x0 + 20.0, x1 - 20.0)
    box(mb, 'MI_Cartel_Rojo', x0 + 10.0, x1 - 10.0, y0 - 2.0, y0 + 6.0, z0 + 228.0, z0 + 248.0)
    box(mb, 'MI_Pintura_Blanca', x1 + 10.0, x1 + 75.0, y0 + 20.0, y0 + 90.0, z0, z0 + 150.0)      # heladera
    box(mb, 'MI_Vidrio', x1 + 74.0, x1 + 75.5, y0 + 26.0, y0 + 84.0, z0 + 40.0, z0 + 140.0)
    mb.col(x0, x1 + 75.0, y0, y1, z0, z0 + 262.0)


def _seto(mb, cx, cy, lx, ly, h, yaw, rng):
    """Seto recortado (ligustro): caja de follaje con bultos y colisión (cobertura de 0,9-1,1 m)."""
    rbox(mb, 'MI_Follaje', cx, cy, Z_PASTO - 2.0, lx, ly, h - 12.0, yaw)
    c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    nb = max(2, int(lx / 55.0))
    for j in range(nb):
        u = -lx * 0.5 + (j + 0.5) * lx / nb
        blob(mb, 'MI_Follaje', (cx + u * c, cy + u * s_, Z_PASTO + h - 18.0), lx / nb * 0.65, ly * 0.55,
             rng.uniform(14.0, 22.0), yaw=yaw + rng.uniform(-10, 10), steps=(5, 6))
    pts = [(cx + x * c - y * s_, cy + x * s_ + y * c) for (x, y) in
           ((-lx * 0.5, -ly * 0.5), (lx * 0.5, -ly * 0.5), (lx * 0.5, ly * 0.5), (-lx * 0.5, ly * 0.5))]
    if abs(round(yaw / 90.0) * 90.0 - yaw) < 1e-3:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        mb.col(min(xs), max(xs), min(ys), max(ys), Z_PASTO - 2.0, Z_PASTO + h - 6.0)
    else:
        mb.ramps.append((pts, 'z', Z_PASTO - 2.0, Z_PASTO + h - 6.0))


def _monumento(mb, x, y, zb):
    """Monumento central: basamento escalonado de piedra, pedestal de 1,9 m (cobertura alta en el centro de la
    plaza) y figura alegórica de bronce (MI_Metal_Verde, abstracta, sin retrato). Bancos de piedra alrededor."""
    cbox(mb, 'MI_PiedraLaja', x - 260.0, x + 260.0, y - 260.0, y + 260.0, zb - 1.0, zb + 18.0, 2.0, 'z')
    cbox(mb, 'MI_PiedraLaja', x - 215.0, x + 215.0, y - 215.0, y + 215.0, zb + 18.0, zb + 36.0, 2.0, 'z')
    cbox(mb, 'MI_Hormigon', x - 125.0, x + 125.0, y - 125.0, y + 125.0, zb + 36.0, zb + 190.0, 3.0, 'z')
    cbox(mb, 'MI_PiedraLaja', x - 140.0, x + 140.0, y - 140.0, y + 140.0, zb + 190.0, zb + 214.0, 3.0, 'z')
    for (dx, dy) in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        box(mb, 'MI_Metal_Verde', x + dx * 126.0 - (1 if dx else 60), x + dx * 126.0 + (1 if dx else 60),
            y + dy * 126.0 - (1 if dy else 60), y + dy * 126.0 + (1 if dy else 60), zb + 90.0, zb + 140.0)   # placas
    cone(mb, 'MI_Metal_Verde', (x, y, zb + 214.0), (x, y, zb + 330.0), 48.0, 28.0, 12)
    blob(mb, 'MI_Metal_Verde', (x, y, zb + 360.0), 34.0, 26.0, 42.0, steps=(7, 9))
    blob(mb, 'MI_Metal_Verde', (x, y + 4.0, zb + 418.0), 17.0, 17.0, 20.0, steps=(6, 8))
    cyl(mb, 'MI_Metal_Verde', (x + 20.0, y, zb + 380.0), (x + 70.0, y + 10.0, zb + 470.0), 7.0, 8)
    blob(mb, 'MI_Metal_Verde', (x + 74.0, y + 10.0, zb + 480.0), 14.0, 9.0, 16.0, steps=(5, 7))
    mb.col(x - 260.0, x + 260.0, y - 260.0, y + 260.0, zb - 1.0, zb + 36.0)
    mb.col(x - 140.0, x + 140.0, y - 140.0, y + 140.0, zb + 36.0, zb + 214.0)
    mb.col(x - 50.0, x + 50.0, y - 50.0, y + 50.0, zb + 214.0, zb + 440.0)
    for a in (135.0, 225.0, 315.0):            # el NE queda para el mástil
        bx, by = x + 520.0 * math.cos(math.radians(a)), y + 520.0 * math.sin(math.radians(a))
        rbox(mb, 'MI_PiedraLaja', bx, by, zb - 1.0, 200.0, 50.0, 46.0, a + 90.0)


def build_plaza(seed):
    """Plaza (manzana 1,1): pasto, sendas de baldosa en cruz y diagonales, plazoleta central con monumento
    (cobertura alta) y mástil a un costado, coberturas cada 6-8 m en el pasto (canteros de ladrillo de 70-90 cm
    y setos de 1,1 m, alineados con las sendas y sin cerrarlas), setos bajos de borde con huecos, juegos con
    colisión (hamacas, tobogán, trepador, pirca), kiosco de diarios y kiosco de bebidas (robos chicos).
    Árboles (dos anillos), bancos, farolas y canastos se instancian aparte (plaza_layout). Actor en el origen."""
    rng = random.Random(seed)
    mb = MB('Plaza')
    x0, x1 = L.XCOL[1]
    y0, y1 = L.YROW[1]
    cx, cy = PLAZA_C
    box(mb, 'MI_Pasto', x0, x1, y0, y1, -1.0, Z_PASTO)
    mb.col(x0, x1, y0, y1, -1.0, Z_PASTO)
    pw = 250.0
    zs = Z_SENDA
    for (a0, a1, b0, b1) in ((x0, x1, y0, y0 + pw), (x0, x1, y1 - pw, y1), (x0, x0 + pw, y0 + pw, y1 - pw),
                             (x1 - pw, x1, y0 + pw, y1 - pw)):
        box(mb, 'MI_Baldosa', a0, a1, b0, b1, Z_PASTO - 1.0, zs)
    # cordoncito entre la senda perimetral y el pasto
    for (a0, a1, b0, b1) in ((x0 + pw, x1 - pw, y0 + pw, y0 + pw + 8.0), (x0 + pw, x1 - pw, y1 - pw - 8.0, y1 - pw),
                             (x0 + pw, x0 + pw + 8.0, y0 + pw, y1 - pw), (x1 - pw - 8.0, x1 - pw, y0 + pw, y1 - pw)):
        box(mb, 'MI_Hormigon', a0, a1, b0, b1, Z_PASTO - 1.0, zs + 4.0)
    box(mb, 'MI_Baldosa', cx - 175.0, cx + 175.0, y0 + pw, y1 - pw, Z_PASTO - 1.0, zs)
    box(mb, 'MI_Baldosa', x0 + pw, x1 - pw, cy - 175.0, cy + 175.0, Z_PASTO - 1.0, zs)
    half = cx - x0 - pw
    Ld = half * SQ2
    for (sx, sy) in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        yaw = math.degrees(math.atan2(sy, sx))
        rbox(mb, 'MI_Baldosa', cx + sx * half * 0.5, cy + sy * half * 0.5, Z_PASTO - 1.0, Ld, 300.0, zs - Z_PASTO + 1.0, yaw)
    cyl(mb, 'MI_PiedraLaja', (cx, cy, Z_PASTO - 1.0), (cx, cy, zs + 0.5), 900.0, 40)
    cyl(mb, 'MI_Hormigon', (cx, cy, Z_PASTO - 1.0), (cx, cy, zs + 0.2), 912.0, 40)     # cordón de la plazoleta
    zb = zs + 0.5
    k.piece('Plaza monumento', _monumento, mb, cx + MONUMENTO[0], cy + MONUMENTO[1], zb)
    # mástil con bandera (celeste y blanca, sin escudos), a un costado de la plazoleta
    cx, cy = cx + MASTIL[0], cy + MASTIL[1]
    cbox(mb, 'MI_PiedraLaja', cx - 90.0, cx + 90.0, cy - 90.0, cy + 90.0, zb - 1.0, zb + 40.0, 3.0, 'z')
    cbox(mb, 'MI_PiedraLaja', cx - 60.0, cx + 60.0, cy - 60.0, cy + 60.0, zb + 40.0, zb + 75.0, 2.0, 'z')
    mb.col(cx - 90.0, cx + 90.0, cy - 90.0, cy + 90.0, zb - 1.0, zb + 75.0)
    cone(mb, 'MI_Pintura_Blanca', (cx, cy, zb + 75.0), (cx, cy, zb + 1400.0), 9.0, 5.0, 12)
    blob(mb, 'MI_Pintura_Amarilla', (cx, cy, zb + 1410.0), 10.0, 10.0, 10.0, steps=(6, 8))
    k.piece('Plaza bandera', P.bandera_celeste, mb, cx + 7.0, cy, zb + 1385.0, 280.0, 0.0)
    cyl(mb, M_HIERRO, (cx + 9.0, cy + 2.0, zb + 80.0), (cx + 9.0, cy + 2.0, zb + 1385.0), 0.4, 4)
    cx, cy = PLAZA_C
    # coberturas: canteros de ladrillo de 70-90 cm y setos de 1,1 m en el pasto (plaza_layout), sendas libres
    lay = plaza_layout()
    for q in lay['covers']:
        (lx, ly), yaw = q['size'], q['yaw']
        if q['kind'] == 'cantero':
            G.k_cantero_alto(mb, q['pos'][0], q['pos'][1], lx, ly, Z_PASTO - 1.0, Z_PASTO + q['h'], yaw, rng)
        else:
            k.piece('Plaza seto', _seto, mb, q['pos'][0], q['pos'][1], lx, ly, q['h'], yaw, rng)
    # setos bajos (90 cm) del lado interior de la senda perimetral, con huecos en las sendas y cada ~12 m
    hh = PLAZA_HALF - pw - 8.0 - 45.0
    for (ax, sgn) in (('x', -1.0), ('x', 1.0), ('y', -1.0), ('y', 1.0)):
        t = -hh + 60.0
        while t < hh - 60.0:
            t1 = min(hh - 60.0, t + 900.0)
            gaps = [(-330.0, 330.0), (-hh, -hh + 480.0), (hh - 480.0, hh)]
            for (a, b) in k.interval_minus(t, t1, gaps):
                if b - a < 120.0:
                    continue
                m = 0.5 * (a + b)
                px, py = (cx + m, cy + sgn * hh) if ax == 'x' else (cx + sgn * hh, cy + m)
                k.piece('Plaza seto borde', _seto, mb, px, py, b - a, 55.0, 90.0, 0.0 if ax == 'x' else 90.0, rng)
            t = t1 + 220.0
    # juegos, kioscos
    k.piece('Plaza juegos', _juegos, mb, cx, cy, Z_PASTO)
    k.piece('Plaza kiosco diarios', _kiosco_diarios, mb, L.KIOSCO_DIARIOS[0], L.KIOSCO_DIARIOS[1], Z_PASTO - 1.0)
    k.piece('Plaza kiosco bebidas', _kiosco_bebidas, mb, L.KIOSCO_PLAZA[0], L.KIOSCO_PLAZA[1], Z_PASTO - 1.0)
    box(mb, 'MI_Baldosa', L.KIOSCO_DIARIOS[0] - 160.0, L.KIOSCO_DIARIOS[0] + 160.0, L.KIOSCO_DIARIOS[1] - 200.0,
        L.KIOSCO_DIARIOS[1] + 120.0, Z_PASTO - 1.0, zs)
    box(mb, 'MI_Baldosa', L.KIOSCO_PLAZA[0] - 200.0, L.KIOSCO_PLAZA[0] + 260.0, L.KIOSCO_PLAZA[1] - 250.0,
        L.KIOSCO_PLAZA[1] + 160.0, Z_PASTO - 1.0, zs)
    # canteros de flores y arbustos (sin colisión) junto a la plazoleta
    for a in (20.0, 110.0, 200.0, 290.0):
        r = 1350.0
        px, py = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
        for q in range(4):
            blob(mb, 'MI_Follaje', (px + rng.uniform(-80, 80), py + rng.uniform(-80, 80), Z_PASTO),
                 rng.uniform(30.0, 55.0), rng.uniform(30.0, 55.0), rng.uniform(25.0, 45.0), yaw=rng.uniform(0, 180),
                 steps=(5, 7))
    return mb


def build_puesto_vias():
    """Puesto de diarios y golosinas contra el alambrado de las vías (robo chico). Actor en el origen."""
    mb = MB('PuestoVias')
    cx, cy = L.PUESTO_VIAS
    x0, x1, y0, y1 = cx - 120.0, cx + 120.0, cy - 94.0, cy + 36.0
    z0 = Z_VER
    box(mb, 'MI_Chapa_Verde', x0, x1, y0 + 4.0, y1, z0, z0 + 215.0)
    cbox(mb, 'MI_Chapa_Gris', x0 - 25.0, x1 + 25.0, y0 - 45.0, y1, z0 + 215.0, z0 + 226.0, 2.0, 'y')
    sp = k.slats_profile(y0 - 2.0, 1.0, z0 + 8.0, z0 + 200.0, 8.0, 1.0)
    if sp:
        prism(mb, 'MI_Chapa_Gris', [(q, p) for (p, q) in sp], 'x', x0 + 12.0, x1 - 12.0)
    box(mb, 'MI_Cartel_Azul', x0, x1, y0 - 1.0, y0 + 4.0, z0 + 200.0, z0 + 214.0)
    box(mb, 'MI_Pintura_Blanca', x1 + 6.0, x1 + 70.0, y0 + 10.0, y1 - 4.0, z0, z0 + 140.0)
    mb.col(x0, x1 + 70.0, y0, y1, z0 - 1.0, z0 + 226.0)
    return mb


# =====================================================================================
# AFUERA NORTE
# =====================================================================================
EXPLANADA = dict(x=L.EST_PLAZA_X, y=(L.FENCE_N, L.EST_VER_N[1]))
REFUGIO = dict(x=(15800.0, 18200.0), y=(27850.0, 28650.0), z=330.0)
CANOPY = dict(x=(14600.0, 19900.0), y=(25250.0, L.STATION['y'][0]), col_y=25620.0)
ROW_N = dict(x0=8566.0, n=14, y=L.EST_VER_N[1])
AFN_W = 8500.0
GALPON = L.GALPON_RED


def estacion_layout():
    """Bancos del andén y del refugio de llegada, árboles de la explanada (mundo)."""
    benches = []
    x = CANOPY['x'][0] + 500.0
    while x < CANOPY['x'][1] - 300.0:
        benches.append({'pos': (x, 25780.0, L.PLATFORM['z']), 'yaw': -90.0})
        x += 1500.0
    for xb in (15950.0, 16850.0, 17150.0, 18050.0):
        benches.append({'pos': (xb, 28450.0, Z_VER), 'yaw': -90.0})
    trees = []
    for (x, y) in ((13900.0, 27300.0), (13900.0, 28300.0), (20100.0, 27300.0), (20100.0, 28300.0),
                   (14800.0, 27550.0), (19200.0, 27550.0)):
        trees.append({'pos': (x, y, 0.0), 'kind': 'fresno', 'seed': int(x) % 3, 'yaw': (x * 0.37) % 360.0})
    return {'benches': benches, 'trees': trees}


def estacion_lums():
    out = []
    x = CANOPY['x'][0] + 300.0
    while x < CANOPY['x'][1]:
        out.append({'pos': (x, CANOPY['col_y'] - 160.0, 372.0), 'street': 'anden'})
        x += 1200.0
    for xx in (16300.0, 17700.0):
        out.append({'pos': (xx, 28250.0, REFUGIO['z'] - 12.0), 'street': 'refugio'})
    return out


def build_estacion(seed):
    """Andén (40 cm) con borde amarillo y baldosa podotáctil, refugio con columnas de fundición verdes, edificio
    de la estación (ladrillo, techo de tejas, reloj, cartel "CASEROS" con textura), explanada peatonal y refugio
    de llegada. La formación detenida junto al andén la pone build_barrio (G.TRAIN_ANDEN). Actor en el origen."""
    rng = random.Random(seed)
    mb = MB('Estacion')
    px0, px1 = L.PLATFORM['x']
    py0, py1 = L.PLATFORM['y']
    zp = L.PLATFORM['z']
    # andén
    box(mb, 'MI_Hormigon', px0, px1, py0, py1, -1.0, zp)
    # borde del andén: cordón de hormigón con nariz, franja amarilla de 45 cm y baldosa podotáctil (barras)
    box(mb, 'MI_Hormigon', px0, px1, py0 - 6.0, py0 + 30.0, zp - 6.0, zp + 0.5)
    box(mb, 'MI_Pintura_Amarilla', px0, px1, py0 + 2.0, py0 + 45.0, zp - 1.0, zp + 0.8)
    box(mb, 'MI_Pintura_Amarilla', px0, px1, py0 + 55.0, py0 + 100.0, zp - 1.0, zp + 0.5)
    for j in range(5):
        yb = py0 + 59.0 + j * 9.0
        box(mb, 'MI_Pintura_Amarilla', px0 + 10.0, px1 - 10.0, yb, yb + 3.5, zp + 0.5, zp + 1.0)
    box(mb, 'MI_Hormigon_Bacheo', px0, px1, py0 - 6.0, py0 - 5.0, 2.0, zp - 6.0)    # cara del andén hacia la vía
    mb.col(px0, px1, py0, py1, -1.0, zp)
    # refugio del andén: columnas y techo de chapa con pendiente hacia la vía
    x = CANOPY['x'][0]
    while x <= CANOPY['x'][1] + 1.0:
        cyl(mb, 'MI_Metal_Verde', (x, CANOPY['col_y'], zp), (x, CANOPY['col_y'], 400.0), 9.0, 12)    # columna de fundición
        cbox(mb, 'MI_Metal_Verde', x - 14.0, x + 14.0, CANOPY['col_y'] - 14.0, CANOPY['col_y'] + 14.0, zp, zp + 45.0, 2.0, 'z')
        cyl(mb, 'MI_Metal_Verde', (x, CANOPY['col_y'], 330.0), (x, CANOPY['col_y'] - 150.0, 396.0), 3.0, 8)   # ménsulas
        cyl(mb, 'MI_Metal_Verde', (x, CANOPY['col_y'], 330.0), (x, CANOPY['col_y'] + 150.0, 396.0), 3.0, 8)
        mb.col(x - 10.0, x + 10.0, CANOPY['col_y'] - 10.0, CANOPY['col_y'] + 10.0, zp, 400.0)
        box(mb, 'MI_Metal_Verde', x - 5.0, x + 5.0, CANOPY['y'][0], CANOPY['y'][1], 392.0, 404.0)
        x += 600.0
    prism(mb, 'MI_Chapa_Gris', [(CANOPY['y'][0], 398.0), (CANOPY['y'][1], 428.0), (CANOPY['y'][1], 434.0),
                                (CANOPY['y'][0], 404.0)], 'x', CANOPY['x'][0] - 60.0, CANOPY['x'][1] + 60.0)
    x = CANOPY['x'][0] + 300.0
    while x < CANOPY['x'][1]:
        box(mb, 'MI_Emisivo_Calido', x - 50.0, x + 50.0, CANOPY['col_y'] - 172.0, CANOPY['col_y'] - 148.0, 378.0, 384.0)
        box(mb, M_HIERRO, x - 54.0, x + 54.0, CANOPY['col_y'] - 176.0, CANOPY['col_y'] - 144.0, 384.0, 392.0)
        x += 1200.0
    # explanada peatonal (corta la calle) con canteros
    ex0, ex1 = EXPLANADA['x']
    ey0, ey1 = EXPLANADA['y']
    box(mb, 'MI_Baldosa', ex0, ex1, ey0, ey1, -1.0, Z_VER)
    mb.col(ex0, ex1, ey0, ey1, -1.0, Z_VER)
    for (cx_, cy_) in ((14400.0, 27100.0), (19600.0, 27100.0), (15200.0, 28300.0), (18800.0, 27350.0)):
        k.k_cantero(mb, cx_ - 220.0, cx_ + 220.0, cy_ - 90.0, cy_ + 90.0, Z_VER, 40.0)
        box(mb, 'MI_Pasto', cx_ - 214.0, cx_ + 214.0, cy_ - 84.0, cy_ + 84.0, Z_VER, Z_VER + 38.0)
        for q in range(3):
            blob(mb, 'MI_Follaje', (cx_ + rng.uniform(-150, 150), cy_ + rng.uniform(-40, 40), Z_VER + 38.0),
                 rng.uniform(30, 50), rng.uniform(25, 40), rng.uniform(25, 45), steps=(5, 7))
        mb.col(cx_ - 220.0, cx_ + 220.0, cy_ - 90.0, cy_ + 90.0, Z_VER, Z_VER + 40.0)
    # edificio de la estación (marco temporal: x hacia la explanada, y hacia el oeste)
    sx0, sx1 = L.STATION['x']
    sy0, sy1 = L.STATION['y']
    Wst, Dst = sx1 - sx0, sy1 - sy0
    st = MB('EdificioEstacion')
    z_e, ang = 520.0, 25.0
    ftop = z_e + 50.0 * math.tan(math.radians(ang))
    wins = [(300.0, 460.0), (600.0, 760.0), (900.0, 1060.0), (Wst - 1060.0, Wst - 900.0), (Wst - 760.0, Wst - 600.0),
            (Wst - 460.0, Wst - 300.0)]
    doors = [(Wst * 0.5 - 200.0, Wst * 0.5 - 60.0), (Wst * 0.5 + 60.0, Wst * 0.5 + 200.0)]
    holes = [k.win_hole(a, b, 120.0, 360.0) for (a, b) in wins] + [(a, b, k.Z_PISO, 330.0) for (a, b) in doors]
    k.piece('Estacion cascaron', k.shell, st, Wst, 0.0, Dst, z_e, z_e, 'MI_Ladrillo', 'MI_Ladrillo', holes, (), False,
            None, False, None, ftop)
    for (a, b) in wins:
        k.piece('Estacion ventana', k.k_window, st, 'MI_Ladrillo', 0.0, a, b, 120.0, 360.0,
                dict(persiana='postigos_cerrados', marco='MI_Madera', moldura='MI_Revoque_Blanco',
                     alfeizar='MI_PiedraLaja'))
    for (a, b) in doors:
        k.piece('Estacion puerta', k.k_door, st, 0.0, a, b, k.Z_PISO, 330.0,
                dict(hoja='MI_Madera', estilo='tablero', banderola=70.0, marco='MI_Madera', base_z=Z_VER))
    k.piece('Estacion techo', k.k_techo_tejas, st, Wst, 0.0, -Dst, z_e, ang, 50.0, 12.0, 'MI_Ladrillo')
    k.piece('Estacion cornisa', k.k_cornisa, st, 'MI_Revoque_Blanco', 0.0, 0.0, Wst, z_e - 30.0, 2)
    k.piece('Estacion zocalo', k.k_zocalo, st, 'MI_PiedraLaja', 0.0, 0.0, Wst, 70.0,
            [(a - 6.0, b + 6.0) for (a, b) in doors])
    cyl(st, 'MI_Pintura_Blanca', (1.0, Wst * 0.5, 430.0), (6.0, Wst * 0.5, 430.0), 42.0, 24)
    k.torus(st, M_HIERRO, (6.0, Wst * 0.5, 430.0), 42.0, 2.5, (1, 0, 0), 24, 4)
    box(st, M_HIERRO, 6.0, 7.0, Wst * 0.5 - 1.5, Wst * 0.5 + 1.5, 430.0, 462.0)
    box(st, M_HIERRO, 6.0, 7.0, Wst * 0.5 - 1.5, Wst * 0.5 + 24.0, 428.5, 431.5)
    cbox(st, 'MI_Cartel_Azul', 0.0, 6.0, Wst * 0.5 - 212.0, Wst * 0.5 + 212.0, 331.0, 387.0, 1.0, 'y')
    k.piece('Estacion cartel', P.placa_texto, st, 'MI_Cartel_Estacion', 7.0, Wst * 0.5, 334.0, 400.0)
    for yp in (0.0, Wst - 40.0):
        cbox(st, 'MI_Revoque_Blanco', -1.0, 4.0, yp, yp + 40.0, 0.0, z_e - 30.0, 1.0, 'z')
    k.merge_mb(mb, st, (sx1, sy1, 0.0), 90.0)
    # refugio de llegada (sobre la explanada)
    rx0, rx1 = REFUGIO['x']
    ry0, ry1 = REFUGIO['y']
    zr = REFUGIO['z']
    for xc in (rx0 + 100.0, 0.5 * (rx0 + rx1), rx1 - 100.0):
        for yc in (ry0 + 50.0, ry1 - 50.0):
            cyl(mb, 'MI_Metal_Verde', (xc, yc, Z_VER), (xc, yc, zr), 8.0, 12)
            mb.col(xc - 9.0, xc + 9.0, yc - 9.0, yc + 9.0, Z_VER, zr)
    prism(mb, 'MI_Chapa_Gris', [(ry0 - 40.0, zr + 8.0), (ry1 + 40.0, zr + 26.0), (ry1 + 40.0, zr + 32.0),
                                (ry0 - 40.0, zr + 14.0)], 'x', rx0 - 40.0, rx1 + 40.0)
    box(mb, M_HIERRO, rx0 - 40.0, rx1 + 40.0, ry0 - 40.0, ry0 - 34.0, zr - 4.0, zr + 14.0)
    box(mb, 'MI_Cartel_Blanco', 0.5 * (rx0 + rx1) - 120.0, 0.5 * (rx0 + rx1) + 120.0, ry0 + 40.0, ry0 + 44.0,
        150.0, 260.0)
    box(mb, 'MI_Cartel_Azul', 0.5 * (rx0 + rx1) - 126.0, 0.5 * (rx0 + rx1) + 126.0, ry0 + 44.0, ry0 + 46.0,
        144.0, 266.0)
    for xx in (16300.0, 17700.0):
        box(mb, 'MI_Emisivo_Calido', xx - 60.0, xx + 60.0, 28230.0, 28270.0, zr - 4.0, zr + 4.0)
    return mb


def build_calles_afuera(seed):
    """Veredas sueltas de Afuera Norte: calle de la estación (lado sur y tramo este del norte), C01 norte
    (llegada del paso a nivel) y márgenes de pasto entre el alambrado y la vereda. Actor en el origen."""
    rng = random.Random(seed)
    mb = MB('CallesAfuera')
    ys0, ys1 = L.STATION['y'][1], L.EST_CALLE_Y[0]         # vereda sur 27000..27350
    yn0, yn1 = L.EST_VER_N
    e1a, e1b = L.E1_X[0] + L.VER, L.E1_X[1] - L.VER
    ex0, ex1 = EXPLANADA['x']
    for (a, b) in ((AFN_W, e1a), (e1b, ex0), (ex1, L.AV_X0)):
        box(mb, rng.choice(['MI_Baldosa', 'MI_Hormigon']), a, b, ys0, ys1 - 15.0, -1.0, Z_VER)
        prism(mb, 'MI_Hormigon', [(ys1 - 15.0, -1.0), (ys1, -1.0), (ys1, Z_VER - 2.5), (ys1 - 2.5, Z_VER),
                                  (ys1 - 15.0, Z_VER)], 'x', a, b)
        mb.col(a, b, ys0, ys1, -1.0, Z_VER)
    # vereda norte del tramo este (frente al galpón y al playón)
    box(mb, 'MI_Hormigon', ex1, L.AV_X0, yn0 + 15.0, yn1, -1.0, Z_VER)
    prism(mb, 'MI_Hormigon', [(yn0, -1.0), (yn0 + 15.0, -1.0), (yn0 + 15.0, Z_VER), (yn0 + 2.5, Z_VER),
                              (yn0, Z_VER - 2.5)], 'x', ex1, L.AV_X0)
    mb.col(ex1, L.AV_X0, yn0, yn1, -1.0, Z_VER)
    # C01 norte: veredas a los lados de la calzada del paso a nivel
    for (a, b) in ((L.E1_X[0], e1a), (e1b, L.E1_X[1])):
        box(mb, 'MI_Hormigon', a, b, L.VIAS_Y1, ys0, -1.0, Z_VER)
        mb.col(a, b, L.VIAS_Y1, ys0, -1.0, Z_VER)
    # márgenes de pasto (entre el alambrado norte de las vías y la vereda sur)
    for (a, b) in ((AFN_W, L.E1_X[0]), (L.E1_X[1], ex0), (ex1, L.AV_X0)):
        box(mb, 'MI_Pasto', a, b, L.FENCE_N + 10.0, ys0, -1.0, 3.0)
        for j in range(int((b - a) / 500.0)):
            blob(mb, 'MI_Follaje', (rng.uniform(a + 50.0, b - 50.0), rng.uniform(L.FENCE_N + 60.0, ys0 - 60.0), 2.0),
                 rng.uniform(15, 40), rng.uniform(15, 40), rng.uniform(12, 35), yaw=rng.uniform(0, 180), steps=(4, 6))
    # tapial que cierra Afuera Norte al oeste (corta la calle de la estación)
    G.tapial_obra(mb, AFN_W, L.FENCE_N, AFN_W, ROW_N['y'] + 900.0, 240.0, True)
    return mb


def afuera_trees():
    """Árboles de los márgenes de Afuera Norte (mundo)."""
    out = []
    rng = random.Random(404)
    for (a, b) in ((AFN_W + 300.0, L.E1_X[0] - 200.0), (L.E1_X[1] + 200.0, EXPLANADA['x'][0] - 200.0),
                   (EXPLANADA['x'][1] + 300.0, 24800.0), (26200.0, L.AV_X0 - 300.0)):
        x = a
        while x < b:
            out.append({'pos': (x, rng.uniform(26300.0, 26700.0), 3.0 - Z_VER), 'kind': rng.choice(['fresno', 'platano', 'paraiso']),
                        'seed': rng.randint(0, 2), 'yaw': rng.uniform(0, 360)})
            x += rng.uniform(900.0, 1500.0)
    return out


def galpon_lums():
    return [{'pos': (21600.0, 30700.0, 690.0), 'street': 'galpon'}, {'pos': (22800.0, 30700.0, 690.0), 'street': 'galpon'},
            {'pos': (22200.0, 32300.0, 690.0), 'street': 'galpon'}, {'pos': (22200.0, 29385.0, 540.0), 'street': 'galpon'}]


def build_galpon_reducidor(seed):
    """Galpón del reducidor: ladrillo y chapa, techo a dos aguas, portón de 11 m abierto (corredizo
    rebatido), adentro estanterías, mesa, palets, neumáticos, columnas; patio delantero. El auto sobre tacos
    se instancia aparte. Actor en el origen (mundo)."""
    rng = random.Random(seed)
    mb = MB('GalponReducidor')
    gx0, gx1 = GALPON['x']
    gy0, gy1 = GALPON['front_y'], GALPON['back_y']
    p0, p1 = GALPON['porton']
    H = 750.0
    W_ = gx1 - gx0
    t = 30.0
    box(mb, 'MI_Hormigon', gx0, gx1, L.EST_VER_N[1], gy1, -1.0, Z_VER)
    mb.col(gx0, gx1, L.EST_VER_N[1], gy1, -1.0, Z_VER)
    for j in range(6):
        pts = k.jitter_poly(rng, rng.uniform(gx0 + 200, gx1 - 200), rng.uniform(gy0 - 500, gy1 - 300),
                            rng.uniform(60, 160), rng.uniform(40, 120), 9, 12.0)
        prism(mb, 'MI_Hormigon_Bacheo', pts, 'z', Z_VER - 0.5, Z_VER + 0.3)
    ph0, ph1 = p0 - gx0, p1 - gx0
    holes = [(ph0, ph1, Z_VER, 520.0)]

    def dfront(m):
        for (a, b, zc) in ((0.0, ph0 - 2.0, 450.0), (ph1 + 2.0, W_, 450.0), (ph0 - 2.0, ph1 + 2.0, 528.0)):
            if b - a > 20.0:
                prism(m, 'MI_Chapa_Gris', k.ribs_profile_xy(0.0, 0.8, a, b, 7.6, 1.6), 'z', zc, H)
        box(m, M_HIERRO, -30.0, 2.0, ph0 - 10.0, ph1 + 10.0, 520.0, 528.0)
        box(m, M_HIERRO, 2.0, 8.0, ph0 - 700.0 if ph0 > 700.0 else 0.0, ph1 + 700.0 if ph1 + 700.0 < W_ else W_,
            530.0, 538.0)                                                    # riel del portón
        for (a, b) in ((ph0 - 560.0, ph0 - 10.0), (ph1 + 10.0, ph1 + 560.0)):
            a, b = max(5.0, a), min(W_ - 5.0, b)
            prism(m, 'MI_Chapa_Gris', k.ribs_profile_xy(8.0, 1.0, a, b, 7.6, 1.6), 'z', Z_VER + 2.0, 528.0)
            m.col(8.0, 12.0, a, b, Z_VER, 528.0)
        box(m, 'MI_Emisivo_Calido', 0.0, 3.0, ph0 + 520.0, ph0 + 580.0, 545.0, 560.0)
        box(m, M_HIERRO, 0.0, 14.0, ph0 + 515.0, ph0 + 585.0, 560.0, 566.0)
    k.piece('Galpon frente', facade_run, mb, (gx0, gy0, 0.0), -90.0, W_, 0.0, H, 'MI_Ladrillo', holes,
            [(ph0, ph1, Z_VER, 520.0)], t, dfront, True)
    box(mb, 'MI_Ladrillo', gx0, gx0 + t, gy0, gy1, -1.0, H)
    box(mb, 'MI_Ladrillo', gx1 - t, gx1, gy0, gy1, -1.0, H)
    box(mb, 'MI_Ladrillo', gx0, gx1, gy1 - t, gy1, -1.0, H)
    mb.col(gx0, gx0 + t, gy0, gy1, -1.0, H)
    mb.col(gx1 - t, gx1, gy0, gy1, -1.0, H)
    mb.col(gx0, gx1, gy1 - t, gy1, -1.0, H)
    xm = 0.5 * (gx0 + gx1)
    zc = H + 230.0
    prism(mb, 'MI_Chapa_Gris', [(gx0 - 50.0, H - 4.0), (xm, zc), (gx1 + 50.0, H - 4.0), (gx1 + 50.0, H + 8.0), (xm, zc + 12.0),
                                (gx0 - 50.0, H + 8.0)], 'y', gy0 - 50.0, gy1 + 50.0)
    for (ya, yb) in ((gy0, gy0 + t), (gy1 - t, gy1)):
        prism(mb, 'MI_Chapa_Gris', [(gx0, H - 1.0), (xm, zc - 2.0), (gx1, H - 1.0)], 'y', ya, yb)
    mb.col(gx0, gx1, gy0, gy1, H - 4.0, H + 20.0)
    # columnas y cabriadas
    for xc in (gx0 + 900.0, gx1 - 900.0):
        y = gy0 + 900.0
        while y < gy1 - 400.0:
            box(mb, M_HIERRO, xc - 12.0, xc + 12.0, y - 12.0, y + 12.0, Z_VER, H)
            mb.col(xc - 13.0, xc + 13.0, y - 13.0, y + 13.0, Z_VER, H)
            y += 900.0
    y = gy0 + 900.0
    while y < gy1 - 400.0:
        cyl(mb, M_HIERRO, (gx0 + t, y, H - 10.0), (xm, y, zc - 25.0), 4.0, 6)
        cyl(mb, M_HIERRO, (gx1 - t, y, H - 10.0), (xm, y, zc - 25.0), 4.0, 6)
        cyl(mb, M_HIERRO, (gx0 + t, y, H - 20.0), (gx1 - t, y, H - 20.0), 3.0, 6)
        y += 900.0
    # estanterías contra los muros laterales
    for (xa, xb) in ((gx0 + t, gx0 + t + 70.0), (gx1 - t - 70.0, gx1 - t)):
        y = gy0 + 500.0
        while y < gy1 - 900.0:
            for (px, py) in ((xa + 3.0, y), (xb - 3.0, y), (xa + 3.0, y + 240.0), (xb - 3.0, y + 240.0)):
                box(mb, M_HIERRO, px - 3.0, px + 3.0, py - 3.0, py + 3.0, Z_VER, Z_VER + 260.0)
            for zz in (Z_VER + 20.0, Z_VER + 100.0, Z_VER + 180.0, Z_VER + 255.0):
                box(mb, 'MI_Chapa_Gris', xa, xb, y - 3.0, y + 243.0, zz, zz + 3.0)
                q = y + 5.0
                while q < y + 230.0:
                    w = rng.uniform(25.0, 60.0)
                    if rng.random() < 0.8:
                        box(mb, rng.choice(['MI_Cartel_Blanco', 'MI_Madera', 'MI_Cartel_Azul', 'MI_Chapa_Gris',
                                            'MI_Plastico_Negro']), xa + 6.0, xb - 6.0, q, q + w, zz + 3.0,
                            zz + 3.0 + rng.uniform(20.0, 70.0))
                    q += w + rng.uniform(4.0, 15.0)
            mb.col(xa, xb, y - 6.0, y + 246.0, Z_VER, Z_VER + 260.0)
            y += 420.0
    # mesa del reducidor (detrás del punto de venta), silla, palets, neumáticos, motor
    fx, fy = L.GAMEPLAY['fence'][0][0], L.GAMEPLAY['fence'][0][1]
    box(mb, 'MI_Madera', fx - 110.0, fx + 110.0, fy + 120.0, fy + 190.0, Z_VER + 72.0, Z_VER + 77.0)
    for (px, py) in ((fx - 100.0, fy + 125.0), (fx + 100.0, fy + 125.0), (fx - 100.0, fy + 185.0), (fx + 100.0, fy + 185.0)):
        box(mb, M_HIERRO, px - 3.0, px + 3.0, py - 3.0, py + 3.0, Z_VER, Z_VER + 72.0)
    mb.col(fx - 110.0, fx + 110.0, fy + 120.0, fy + 190.0, Z_VER, Z_VER + 77.0)
    box(mb, 'MI_Emisivo_Calido', fx - 20.0, fx + 20.0, fy + 140.0, fy + 170.0, 300.0, 306.0)
    cyl(mb, M_HIERRO, (fx, fy + 155.0, 306.0), (fx, fy + 155.0, H - 20.0), 0.6, 4)
    for (px, py, n) in ((gx0 + 500.0, gy1 - 600.0, 5), (gx0 + 700.0, gy1 - 600.0, 3), (gx1 - 600.0, gy0 + 700.0, 4)):
        for j in range(n):
            box(mb, 'MI_Madera', px - 60.0, px + 60.0, py - 50.0, py + 50.0, Z_VER + j * 14.0, Z_VER + j * 14.0 + 12.0)
        mb.col(px - 60.0, px + 60.0, py - 50.0, py + 50.0, Z_VER, Z_VER + n * 14.0)
    for (px, py) in ((gx1 - 400.0, gy1 - 500.0), (gx1 - 470.0, gy1 - 420.0), (gx0 + 400.0, gy0 + 500.0)):
        for j in range(4):
            cyl(mb, 'MI_Neumatico', (px, py, Z_VER + j * 22.0), (px, py, Z_VER + j * 22.0 + 20.0), 32.0, 14)
        mb.col(px - 32.0, px + 32.0, py - 32.0, py + 32.0, Z_VER, Z_VER + 88.0)
    cbox(mb, 'MI_Metal_Negro', xm + 300.0, xm + 420.0, gy1 - 1100.0, gy1 - 1020.0, Z_VER, Z_VER + 70.0, 3.0, 'z')
    for (lx, ly, lz) in [(l['pos'][0], l['pos'][1], l['pos'][2]) for l in galpon_lums()[:3]]:
        box(mb, 'MI_Emisivo_Calido', lx - 40.0, lx + 40.0, ly - 12.0, ly + 12.0, lz + 4.0, lz + 8.0)
        box(mb, M_HIERRO, lx - 44.0, lx + 44.0, ly - 15.0, ly + 15.0, lz + 8.0, lz + 14.0)
        cyl(mb, M_HIERRO, (lx, ly, lz + 14.0), (lx, ly, H - 20.0), 0.6, 4)
    # patio delantero: tambores
    for (px, py) in ((gx0 + 300.0, gy0 - 250.0), (gx0 + 380.0, gy0 - 200.0), (gx1 - 350.0, gy0 - 300.0)):
        cyl(mb, rng.choice(['MI_Metal_Verde', 'MI_Cartel_Azul', 'MI_Cartel_Rojo']), (px, py, Z_VER),
            (px, py, Z_VER + 88.0), 29.0, 14)
        mb.col(px - 29.0, px + 29.0, py - 29.0, py + 29.0, Z_VER, Z_VER + 88.0)
    return mb


PLAYON = dict(x=(GALPON['x'][1], L.PLAYON['x'][1]), y=(L.EST_VER_N[1], L.PLAYON['y'][1]))


def playon_layout():
    """Contenedores marítimos (cobertura), camiones y torres de luz del playón (mundo)."""
    conts = [((24900.0, 30200.0, Z_VER), 0.0, 'MI_Metal_Verde'), ((24900.0, 30200.0, Z_VER + 259.0), 2.0, 'MI_Cartel_Rojo'),
             ((26300.0, 31500.0, Z_VER), 90.0, 'MI_Cartel_Azul'), ((27900.0, 30000.0, Z_VER), 0.0, 'MI_Chapa_Gris'),
             ((29500.0, 31600.0, Z_VER), 90.0, 'MI_Metal_Verde'), ((29500.0, 31600.0, Z_VER + 259.0), 88.0, 'MI_Chapa_Gris'),
             ((30300.0, 29800.0, Z_VER), 0.0, 'MI_Cartel_Rojo'), ((25200.0, 32300.0, Z_VER), 0.0, 'MI_Cartel_Azul')]
    trucks = [((27200.0, 32300.0, Z_VER), 180.0), ((28600.0, 29600.0, Z_VER), 0.0)]
    towers = [(24300.0, 29100.0), (30800.0, 32600.0)]
    return {'containers': conts, 'trucks': trucks, 'towers': towers}


def playon_lums():
    out = []
    for (x, y) in playon_layout()['towers']:
        for dx in (-60.0, 60.0):
            out.append({'pos': (x + dx, y, 1180.0), 'street': 'playon'})
    return out


def build_contenedor_maritimo():
    """Contenedor de 20 pies (606 x 244 x 259) de chapa acanalada. Slot de color MI_Metal_Verde.
    Marco: +X a lo largo, origen en el piso al centro."""
    mb = MB('ContenedorMaritimo')
    hx, hy, h = 303.0, 122.0, 259.0
    c = 'MI_Metal_Verde'
    for s in (-1.0, 1.0):
        pr = k.ribs_profile_xy(0.0, 2.0, -hx + 12.0, hx - 12.0, 28.0, 3.0)
        prism(mb, c, [(q, s * (hy - 5.0 + p)) for (p, q) in pr], 'z', 8.0, h - 8.0)
    box(mb, c, -hx + 12.0, hx - 12.0, -hy + 5.0, hy - 5.0, h - 10.0, h)
    box(mb, c, -hx + 12.0, hx - 12.0, -hy + 5.0, hy - 5.0, 0.0, 12.0)
    for (xa, xb) in ((-hx, -hx + 12.0), (hx - 12.0, hx)):
        for ys in (-1.0, 1.0):
            box(mb, M_HIERRO, xa, xb, ys * hy - (12.0 if ys > 0 else 0.0), ys * hy + (0.0 if ys > 0 else 12.0), 0.0, h)
    box(mb, c, -hx, -hx + 6.0, -hy + 12.0, hy - 12.0, 0.0, h)
    box(mb, c, hx - 6.0, hx, -hy + 12.0, hy - 12.0, 0.0, h)
    for ys in (-60.0, 60.0):
        for yy in (ys - 20.0, ys + 20.0):
            box(mb, M_HIERRO, hx, hx + 3.0, yy - 2.0, yy + 2.0, 10.0, h - 10.0)
    mb.col(-hx, hx, -hy, hy, 0.0, h)
    return mb


def build_playon(seed):
    """Playón de cargas (hormigón con bacheo), garita en el portón, palets, torres de luz. Contenedores,
    camiones y alambrados se instancian / construyen aparte. Actor en el origen (mundo)."""
    rng = random.Random(seed)
    mb = MB('Playon')
    x0, x1 = PLAYON['x']
    y0, y1 = PLAYON['y']
    box(mb, 'MI_Hormigon', x0, x1, y0, y1, -1.0, Z_VER)
    mb.col(x0, x1, y0, y1, -1.0, Z_VER)
    for j in range(14):
        pts = k.jitter_poly(rng, rng.uniform(x0 + 300, x1 - 300), rng.uniform(y0 + 300, y1 - 300), rng.uniform(80, 260),
                            rng.uniform(60, 200), rng.randint(8, 11), 18.0)
        prism(mb, rng.choice(['MI_Hormigon_Bacheo', 'MI_Asfalto']), pts, 'z', Z_VER - 0.5, Z_VER + 0.4)
    for j in range(3):
        y = rng.uniform(y0 + 400, y1 - 400)
        box(mb, 'MI_Pintura_Amarilla', x0 + 300.0, x1 - 300.0, y - 6.0, y + 6.0, Z_VER - 0.2, Z_VER + 0.5)
    # garita junto al portón
    gx, gy = 28400.0, 29050.0
    box(mb, 'MI_Revoque_Blanco', gx - 100.0, gx + 100.0, gy - 90.0, gy + 90.0, Z_VER, 250.0)
    box(mb, 'MI_Vidrio', gx - 101.0, gx + 101.0, gy - 70.0, gy + 70.0, 120.0, 210.0)
    cbox(mb, 'MI_Chapa_Gris', gx - 120.0, gx + 120.0, gy - 110.0, gy + 110.0, 250.0, 262.0, 2.0, 'y')
    mb.col(gx - 100.0, gx + 100.0, gy - 90.0, gy + 90.0, Z_VER, 262.0)
    # pilas de palets
    for (px, py) in ((26600.0, 29400.0), (26750.0, 29400.0), (28800.0, 32500.0), (30700.0, 30800.0), (24300.0, 31300.0)):
        n = rng.randint(3, 7)
        for j in range(n):
            rbox(mb, 'MI_Madera', px, py, Z_VER + j * 14.0, 120.0, 100.0, 12.0, rng.uniform(-4, 4))
        mb.col(px - 62.0, px + 62.0, py - 52.0, py + 52.0, Z_VER, Z_VER + n * 14.0)
    # torres de luz
    for (tx, ty) in playon_layout()['towers']:
        cbox(mb, 'MI_Hormigon', tx - 40.0, tx + 40.0, ty - 40.0, ty + 40.0, Z_VER, Z_VER + 50.0, 2.0, 'z')
        cone(mb, 'MI_Chapa_Gris', (tx, ty, Z_VER + 50.0), (tx, ty, 1200.0), 16.0, 9.0, 12)
        box(mb, M_HIERRO, tx - 90.0, tx + 90.0, ty - 8.0, ty + 8.0, 1195.0, 1205.0)
        for dx in (-60.0, 60.0):
            cbox(mb, M_HIERRO, tx + dx - 24.0, tx + dx + 24.0, ty - 18.0, ty + 18.0, 1185.0, 1200.0, 1.0, 'z')
            box(mb, 'MI_Emisivo_Calido', tx + dx - 20.0, tx + dx + 20.0, ty - 14.0, ty + 14.0, 1183.0, 1186.0)
        mb.col(tx - 40.0, tx + 40.0, ty - 40.0, ty + 40.0, Z_VER, 1200.0)
    return mb


def playon_fences():
    """(nombre, pts, tapial) del cerco del playón (alambrado al frente con portones, tapial al fondo)."""
    x0, x1 = PLAYON['x']
    y0, y1 = PLAYON['y']
    return [('Alambrado_Playon_S1', [(x0 + 300.0, y0 + 20.0), (26900.0, y0 + 20.0)], False),
            ('Alambrado_Playon_S2', [(28100.0, y0 + 20.0), (29900.0, y0 + 20.0)], False),
            ('Alambrado_Playon_S3', [(30500.0, y0 + 20.0), (x1 - 10.0, y0 + 20.0)], False),
            ('Alambrado_Playon_E', [(x1 - 10.0, y0 + 20.0), (x1 - 10.0, y1)], False),
            ('Tapial_Playon_N', [(x0, y1), (x1, y1)], True)]


def avn_lums():
    out = []
    xc = 0.5 * (L.AV_CANTERO[0] + L.AV_CANTERO[1])
    for y in avn_column_ys():
        out.append({'pos': (xc - L.AV_ARM_X, y, L.AV_LUM_Z), 'street': 'Avenida'})
        out.append({'pos': (xc + L.AV_ARM_X, y, L.AV_LUM_Z), 'street': 'Avenida'})
    return out


def avn_column_ys():
    ys = []
    y = L.OBRA_AV_N[1] + 900.0
    while y < L.AV_N_END - 500.0:
        if not (L.EST_CALLE_Y[0] - 300.0 < y < L.EST_CALLE_Y[1] + 300.0):
            ys.append(y)
        y += 2500.0
    return ys


def build_avenida_norte(seed):
    """Tramo de la avenida en Afuera Norte (Y 26.216 - 33.000): calzadas, cantero bajo (sin reja), veredas a
    ambos lados (la oeste cortada por la calle de la estación), obras en los extremos. Actor en el origen."""
    rng = random.Random(seed)
    mb = MB('AvenidaNorte')
    ya, yb = L.OBRA_AV_N[1], L.AV_N_END
    xw0, xw1 = L.AV_CALZ[0], L.AV_CANTERO[0]
    xe0, xe1 = L.AV_CANTERO[1], L.AV_CALZ[1]
    for (a, b) in ((xw0, xw1), (xe0, xe1)):
        box(mb, 'MI_Asfalto', a, b, ya, yb, -10.0, 4.2)
        mb.col(a, b, ya, yb, -10.0, 4.2)
        y = ya + 200.0
        while y < yb - 300.0:
            box(mb, 'MI_Pintura_Blanca', 0.5 * (a + b) - 6.0, 0.5 * (a + b) + 6.0, y, y + 300.0, 2.0, 4.4)
            y += 800.0
    box(mb, 'MI_Hormigon', xw1, xe0, ya, yb, -10.0, 18.0)
    box(mb, 'MI_Pasto', xw1 + 12.0, xe0 - 12.0, ya + 12.0, yb - 12.0, 0.0, 18.6)
    mb.col(xw1, xe0, ya, yb, -10.0, 18.0)
    # veredas
    ey0, ey1 = L.EST_CALLE_Y
    for (a, b) in ((ya, ey0), (ey1, yb)):
        box(mb, rng.choice(['MI_Baldosa', 'MI_Hormigon']), L.AV_X0, xw0 - 15.0, a, b, -1.0, Z_VER)
        prism(mb, 'MI_Hormigon', [(xw0 - 15.0, -1.0), (xw0, -1.0), (xw0, Z_VER - 2.5), (xw0 - 2.5, Z_VER),
                                  (xw0 - 15.0, Z_VER)], 'y', a, b)
        mb.col(L.AV_X0, xw0, a, b, -1.0, Z_VER)
    box(mb, 'MI_Asfalto', L.AV_X0, xw0, ey0, ey1, -10.0, 4.2)          # boca de la calle de la estación
    mb.col(L.AV_X0, xw0, ey0, ey1, -10.0, 4.2)
    box(mb, 'MI_Baldosa', xe1 + 15.0, L.AV_X1, ya, yb, -1.0, Z_VER)
    prism(mb, 'MI_Hormigon', [(xe1, -1.0), (xe1 + 15.0, -1.0), (xe1 + 15.0, Z_VER), (xe1 + 2.5, Z_VER), (xe1, Z_VER - 2.5)],
          'y', ya, yb)
    mb.col(xe1, L.AV_X1, ya, yb, -1.0, Z_VER)
    # obras que cierran el tramo (sur: antes de las vías; norte: fin del mapa)
    G.tapial_obra(mb, L.AV_X0, L.OBRA_AV_N[0] + 100.0, L.AV_X1, L.OBRA_AV_N[0] + 100.0, 240.0, True)
    G.tapial_obra(mb, L.AV_X0, yb, L.AV_X1, yb, 240.0, True)
    for x in (xw0 + 200.0, xe0 + 300.0):
        P.k_valla(mb, x, ya + 150.0, x + 360.0, ya + 150.0)
        P.k_cono(mb, x + 450.0, ya + 250.0, 3.0)
    return mb


# Afuera Este: obra del paso bajo nivel (acceso a la pasarela provisoria E2B)
OBRA_E2B_S = dict(x=(L.AV_X1, 37000.0), y=(21000.0, L.OBRA_AV_S[0] + 40.0))
OBRA_E2B_N = dict(x=(L.AV_X1, 37000.0), y=(L.FENCE_N + 10.0, 27804.0))
ROW_E = dict(y0=21000.0, n=36)          # v5: hasta la calle Fondo
ROW_EN = dict(y0=L.AV_N_END, n=6)


def build_obra_e2b(seed):
    """Dos predios de obra (al sur y al norte de las vías) que llevan a las escaleras de la pasarela
    provisoria: tierra, tapiales de chapa, volquete, vallas, conos, obrador. Actor en el origen."""
    rng = random.Random(seed)
    mb = MB('ObraE2B')
    for (name, o) in (('S', OBRA_E2B_S), ('N', OBRA_E2B_N)):
        x0, x1 = o['x']
        y0, y1 = o['y']
        box(mb, 'MI_Tierra', x0, x1, y0, y1, -1.0, Z_VER - 2.0)
        mb.col(x0, x1, y0, y1, -1.0, Z_VER - 2.0)
        for j in range(8):
            pts = k.jitter_poly(rng, rng.uniform(x0 + 200, x1 - 200), rng.uniform(y0 + 150, y1 - 150), rng.uniform(80, 220),
                                rng.uniform(60, 160), 9, 25.0)
            prism(mb, rng.choice(['MI_Pasto', 'MI_Hormigon_Bacheo']), pts, 'z', Z_VER - 3.0, Z_VER - 1.0)
        G.tapial_obra(mb, x1, y0, x1, y1, 240.0, True)
        if name == 'S':
            G.tapial_obra(mb, x0, y1, x1, y1, 240.0, False)
        vq = P.build_volquete()
        vx, vy = x0 + 700.0, (y0 + 350.0 if name == 'S' else y1 - 350.0)
        k.merge_mb(mb, vq, (vx, vy, Z_VER - 2.0), 90.0)
        for q in range(5):
            P.k_cono(mb, rng.uniform(x0 + 200, x1 - 400), rng.uniform(y0 + 150, y1 - 150), Z_VER - 2.0)
        P.k_valla(mb, x0 + 1200.0, y0 + 250.0, x0 + 1200.0, y0 + 700.0)
        mb.col(x0 + 1195.0, x0 + 1205.0, y0 + 250.0, y0 + 700.0, 0.0, 105.0)
    # obrador (caseta) en el predio sur
    ox, oy = 36200.0, 21500.0
    box(mb, 'MI_Chapa_Gris', ox - 300.0, ox + 300.0, oy - 120.0, oy + 120.0, Z_VER - 2.0, 260.0)
    box(mb, 'MI_Vidrio', ox - 200.0, ox - 60.0, oy - 121.0, oy - 120.0, 120.0, 200.0)
    box(mb, 'MI_Madera', ox + 60.0, ox + 150.0, oy - 122.0, oy - 120.0, Z_VER, 220.0)
    mb.col(ox - 300.0, ox + 300.0, oy - 120.0, oy + 120.0, Z_VER - 2.0, 260.0)
    # tapial sur que cierra la obra contra los fondos
    G.tapial_obra(mb, L.AV_X1 + 860.0, OBRA_E2B_S['y'][0] + 10.0, OBRA_E2B_S['x'][1], OBRA_E2B_S['y'][0] + 10.0, 240.0,
                  False)
    G.tapial_obra(mb, L.AV_X1 + 860.0, OBRA_E2B_N['y'][1] - 10.0, OBRA_E2B_N['x'][1], OBRA_E2B_N['y'][1] - 10.0, 240.0,
                  False)
    # cierre sur de Afuera Este (continúa la obra de la avenida)
    G.tapial_obra(mb, L.AV_X1, L.AV_S_END + 8.0, L.AV_X1 + 900.0, L.AV_S_END + 8.0, 240.0, True)
    return mb


# =====================================================================================
# BORDES: tapial y club al oeste, galpones al sur
# =====================================================================================
def club_trees():
    out = []
    rng = random.Random(77)
    y = 600.0
    while y < L.VIAS_Y0 - 400.0:
        out.append({'pos': (rng.uniform(-650.0, -420.0), y, -1.0 - Z_VER), 'kind': rng.choice(['fresno', 'platano']),
                    'seed': rng.randint(0, 2), 'yaw': rng.uniform(0, 360), 'big': True})
        y += rng.uniform(1100.0, 1700.0)
    return out


def build_club(seed):
    """Club de barrio detrás del tapial oeste: gimnasio de ladrillo con techo parabólico, cancha con arcos,
    tribuna y torres de luz. Inaccesible (sin colisión salvo el gimnasio). Actor en el origen (mundo)."""
    rng = random.Random(seed)
    mb = MB('Club')
    # gimnasio
    gx0, gx1, gy0, gy1 = -5200.0, -1600.0, 2500.0, 8500.0
    H = 800.0
    box(mb, 'MI_Ladrillo', gx0, gx1, gy0, gy1, -1.0, H)
    rise = 450.0
    n = 14
    outer, inner = [], []
    for i in range(n + 1):
        t = i / float(n)
        x = gx0 - 40.0 + (gx1 - gx0 + 80.0) * t
        z = H + rise * 4.0 * t * (1.0 - t)
        outer.append((x, z + 14.0))
        inner.append((x, z))
    prism(mb, 'MI_Chapa_Gris', outer + list(reversed(inner)), 'y', gy0 - 40.0, gy1 + 40.0)
    for yy in (gy0, gy1 - 30.0):
        prism(mb, 'MI_Ladrillo', [(gx0, H - 1.0)] + inner[1:-1] + [(gx1, H - 1.0)], 'y', yy, yy + 30.0)
    for j in range(5):
        x = gx1 - 1.0
        y = gy0 + 600.0 + j * 1100.0
        box(mb, 'MI_Vidrio', x, x + 1.0, y, y + 500.0, 520.0, 700.0)
        box(mb, 'MI_Hormigon', x, x + 4.0, y - 10.0, y + 510.0, 510.0, 520.0)
    box(mb, 'MI_Cartel_Verde', gx1, gx1 + 4.0, gy0 + 1500.0, gy1 - 1500.0, 720.0, 790.0)
    box(mb, 'MI_Cartel_Blanco', gx1 + 4.0, gx1 + 5.0, gy0 + 1550.0, gy1 - 1550.0, 732.0, 778.0)
    mb.col(gx0, gx1, gy0, gy1, -1.0, H)
    # cancha
    fx0, fx1, fy0, fy1 = -6800.0, -1200.0, 10200.0, 21400.0
    box(mb, 'MI_Pasto', fx0, fx1, fy0, fy1, -1.0, 2.0)
    for (a0, a1, b0, b1) in ((fx0 + 200, fx1 - 200, fy0 + 200, fy0 + 212), (fx0 + 200, fx1 - 200, fy1 - 212, fy1 - 200),
                             (fx0 + 200, fx0 + 212, fy0 + 200, fy1 - 200), (fx1 - 212, fx1 - 200, fy0 + 200, fy1 - 200),
                             (fx0 + 200, fx1 - 200, 0.5 * (fy0 + fy1) - 6, 0.5 * (fy0 + fy1) + 6)):
        box(mb, 'MI_Pintura_Blanca', a0, a1, b0, b1, 2.0, 2.6)
    xc = 0.5 * (fx0 + fx1)
    for yg, s in ((fy0 + 200.0, 1.0), (fy1 - 200.0, -1.0)):
        for xs in (xc - 366.0, xc + 366.0):
            cyl(mb, 'MI_Pintura_Blanca', (xs, yg, 0.0), (xs, yg, 244.0), 6.0, 10)
        cyl(mb, 'MI_Pintura_Blanca', (xc - 366.0, yg, 244.0), (xc + 366.0, yg, 244.0), 6.0, 10)
        box(mb, 'MI_Alambrado', xc - 366.0, xc + 366.0, yg - s * 150.0 - 0.3, yg - s * 150.0 + 0.3, 0.0, 240.0)
    # tribuna de hormigón contra el tapial
    for j in range(6):
        box(mb, 'MI_Hormigon', -980.0 + j * 110.0, -320.0, 13500.0, 18500.0, -1.0, 80.0 + j * 40.0)
    for (tx, ty) in ((fx0 + 100.0, fy0 + 100.0), (fx1 - 100.0, fy0 + 100.0), (fx0 + 100.0, fy1 - 100.0),
                     (fx1 - 100.0, fy1 - 100.0)):
        cone(mb, 'MI_Chapa_Gris', (tx, ty, 0.0), (tx, ty, 1800.0), 22.0, 12.0, 10)
        box(mb, M_HIERRO, tx - 150.0, tx + 150.0, ty - 20.0, ty + 20.0, 1760.0, 1860.0)
    return mb


def build_galpones_sur(seed):
    """Frente de galpones al sur (Y < 0): tramos de 35-55 m con muros de ladrillo y chapa de 5,5-9 m,
    portones cerrados, ventanas altas con reja y techos de dientes de sierra. Colisión solo en el frente.
    Actor en el origen (mundo)."""
    rng = random.Random(seed)
    mb = MB('GalponesSur')
    # muro lateral del primer galpón: cierra el hueco entre el frente y la obra sur de la avenida (Y -142)
    box(mb, 'MI_Ladrillo', L.AV_X0 - 30.0, L.AV_X0 + 2.0, -4600.0, -30.0, -1.0, 700.0)
    mb.col(L.AV_X0 - 30.0, L.AV_X0 + 2.0, -4600.0, 0.0, -1.0, 700.0)
    x = L.AV_X0
    i = 0
    while x > -40.0:
        w = min(x + 40.0, rng.uniform(3500.0, 5500.0))
        if x - w < 600.0:
            w = x + 40.0
        h = rng.uniform(550.0, 900.0)
        top_mat = rng.choice(['MI_Chapa_Gris', 'MI_Chapa_Verde', 'MI_Ladrillo', 'MI_Revoque_Gris'])
        nd = max(1, int(w / 1800.0))
        doors = []
        for j in range(nd):
            yc = w * (j + 0.5) / nd + rng.uniform(-200.0, 200.0)
            doors.append((yc - 220.0, yc + 220.0))
        holes = [(a, b, 0.0, 420.0) for (a, b) in doors]
        wins = []
        y = 300.0
        while y < w - 400.0:
            if all(y + 240.0 < a - 60.0 or y > b + 60.0 for (a, b) in doors):
                wins.append((y, y + 240.0))
            y += rng.uniform(500.0, 800.0)
        holes += [k.win_hole(a, b, h - 230.0, h - 120.0) for (a, b) in wins]

        def deco(m, w=w, h=h, doors=doors, wins=wins, top_mat=top_mat):
            for (a, b) in doors:
                k.k_garage_chapa(m, 0.0, a, b, 0.0, 420.0, dict(mat=rng.choice(['MI_Chapa_Gris', 'MI_Chapa_Verde',
                                                                              'MI_Metal_Negro']), orient='v'))
                box(m, 'MI_Hormigon', 0.0, 30.0, a - 20.0, b + 20.0, -1.0, Z_VER + 2.0)
            for (a, b) in wins:
                k.k_window(m, 'MI_Ladrillo', 0.0, a, b, h - 230.0, h - 120.0, dict(reja='barrotes', persiana=None,
                                                                                    cortina=False))
            if top_mat != 'MI_Ladrillo':
                box(m, top_mat, 0.0, 1.5, 0.0, w, 430.0, h)
            cbox(m, 'MI_Hormigon', -2.0, 4.0, 0.0, w, h, h + 10.0, 1.0, 'y')
            if rng.random() < 0.6:
                _cartel(m, rng.choice(['MI_Cartel_Azul', 'MI_Cartel_Rojo', 'MI_Cartel_Verde']), w * 0.5 - 500.0,
                        w * 0.5 + 500.0, h - 110.0, h - 20.0, 6.0)
            for q in range(rng.randint(1, 3)):        # tags en aerosol (MI_Pintada_1..4)
                P.pintada(m, rng.randint(1, 4), 0.0, rng.uniform(200.0, w - 300.0), rng.uniform(60.0, 140.0),
                          rng.uniform(110.0, 180.0), 0.0)
            for q in range(rng.randint(2, 4)):        # manchas de pintura vieja
                ya = rng.uniform(100.0, w - 400.0)
                box(m, rng.choice(['MI_Cartel_Rojo', 'MI_Cartel_Azul', 'MI_Pintura_Blanca', 'MI_Pintura_Amarilla']),
                    0.0, 0.6, ya, ya + rng.uniform(100.0, 300.0), rng.uniform(40.0, 120.0), rng.uniform(150.0, 260.0))
        k.piece('Galpon sur %d' % i, facade_run, mb, (x, 0.0, 0.0), 90.0, w, 0.0, h, 'MI_Ladrillo', holes, (), 30.0, deco,
                True)
        # techo de dientes de sierra (no se alcanza)
        D = rng.uniform(2500.0, 4200.0)
        y = -30.0
        while y > -D:
            ya, yb = y, max(-D, y - 600.0)
            prism(mb, 'MI_Chapa_Gris', [(ya, h - 30.0), (yb, h - 30.0), (yb, h + 160.0), (yb + 8.0, h + 160.0),
                                        (ya, h - 20.0)], 'x', x - w, x)
            box(mb, 'MI_Vidrio', x - w, x, yb + 1.0, yb + 3.0, h - 30.0, h + 155.0)
            y = yb
        box(mb, 'MI_Ladrillo', x - w - 1.0, x - w + 30.0, -D, -30.0, -1.0, h)
        i += 1
        x -= w
    return mb


# =====================================================================================
# EDIFICIOS BAJOS Y TORRES DE FONDO (skyline, sin colisión)
# =====================================================================================
def build_edificios_bajos(seed):
    """Anillo de edificios bajos lejanos (2-4 pisos) más allá de los bordes. Actor en el origen."""
    rng = random.Random(seed)
    mb = MB('EdificiosBajos')
    # v5: la fila sur corre el anillo sur detrás de los galpones (Y < -15.000) y alarga los anillos oeste/este
    zones = [(-12000.0, -7000.0, -16000.0, 30000.0), (-6000.0, 40000.0, -20500.0, -16000.0),
             (6000.0, 42000.0, 34600.0, 39000.0), (38200.0, 44000.0, -16000.0, 34000.0),
             (-6500.0, -1800.0, -10000.0, -1000.0)]
    for (x0, x1, y0, y1) in zones:
        n = int(((x1 - x0) * (y1 - y0)) / 9.0e6)
        for j in range(n):
            w, d = rng.uniform(900.0, 2200.0), rng.uniform(900.0, 2200.0)
            cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1)
            h = rng.choice([650.0, 700.0, 950.0, 1250.0])
            if cx > PLAZA_C[0] and cy > PLAZA_C[1]:
                h = min(h, 950.0)            # en el NE la torre del mapa es la única altura
            mat = rng.choice(['MI_Revoque_Gris', 'MI_Revoque_Blanco', 'MI_Ladrillo', 'MI_Revoque_Amarillo',
                              'MI_Revoque_Rosa'])
            box(mb, mat, cx - w * 0.5, cx + w * 0.5, cy - d * 0.5, cy + d * 0.5, -1.0, h)
            box(mb, 'MI_Hormigon', cx - w * 0.5 - 5.0, cx + w * 0.5 + 5.0, cy - d * 0.5 - 5.0, cy + d * 0.5 + 5.0, h, h + 12.0)
            z = 160.0
            while z < h - 120.0:
                for (a0, a1, b0, b1) in ((cx - w * 0.5 - 1.0, cx - w * 0.5, cy - d * 0.4, cy + d * 0.4),
                                         (cx + w * 0.5, cx + w * 0.5 + 1.0, cy - d * 0.4, cy + d * 0.4),
                                         (cx - w * 0.4, cx + w * 0.4, cy - d * 0.5 - 1.0, cy - d * 0.5),
                                         (cx - w * 0.4, cx + w * 0.4, cy + d * 0.5, cy + d * 0.5 + 1.0)):
                    box(mb, 'MI_Emisivo_Calido' if rng.random() < 0.06 else 'MI_Vidrio', a0, a1, b0, b1, z, z + 110.0)
                z += 300.0
            if rng.random() < 0.5:
                k.tanque_simple(mb, cx + rng.uniform(-w * 0.3, w * 0.3), cy + rng.uniform(-d * 0.3, d * 0.3), h + 12.0)
    return mb


# Torres de fondo: topadas en 25 m y NINGUNA en el cuadrante NE (rumbo 0-90 grados desde la plaza): ahí la única
# altura es la torre del mapa (hito de la avenida y de E2/E3).
SKYLINE_MAX_H = 2500.0
SKYLINE = [(-9000.0, 30500.0, 2400.0), (-13000.0, 9000.0, 2100.0), (-16000.0, 20000.0, 2500.0),
           (6000.0, -24000.0, 2300.0), (23000.0, -27000.0, 2500.0), (47000.0, 4000.0, 2000.0),
           (12000.0, 45000.0, 1900.0), (-12000.0, -15000.0, 2200.0)]


def skyline_ok(x, y, h):
    """True si una torre de fondo respeta el tope de altura y no cae en el cuadrante NE del barrio."""
    cx, cy = PLAZA_C
    return h <= SKYLINE_MAX_H and not (x > cx and y > cy)


def build_skyline(seed):
    """Torres de fondo de 25-45 m a 60-200 m del barrio: bloque, bandas de ventanas (algunas encendidas),
    sala de máquinas y baliza roja. Actor en el origen (mundo), sin colisión."""
    rng = random.Random(seed)
    mb = MB('SkylineTorres')
    for (cx, cy, H) in SKYLINE:
        if not skyline_ok(cx, cy, H):
            k.warn('Skyline: torre en (%.0f, %.0f) de %.0f m descartada (NE o más de 25 m)' % (cx, cy, H / 100.0))
            continue
        w, d = rng.uniform(1600.0, 2400.0), rng.uniform(1400.0, 2200.0)
        mat = rng.choice(['MI_Revoque_Blanco', 'MI_Revoque_Gris', 'MI_Hormigon', 'MI_Revoque_Amarillo'])
        box(mb, mat, cx - w * 0.5, cx + w * 0.5, cy - d * 0.5, cy + d * 0.5, -1.0, H)
        z = 400.0
        lit = rng.random() < 0.6
        while z < H - 150.0:
            for (a0, a1, b0, b1) in ((cx - w * 0.5 - 2.0, cx - w * 0.5, cy - d * 0.45, cy + d * 0.45),
                                     (cx + w * 0.5, cx + w * 0.5 + 2.0, cy - d * 0.45, cy + d * 0.45),
                                     (cx - w * 0.45, cx + w * 0.45, cy - d * 0.5 - 2.0, cy - d * 0.5),
                                     (cx - w * 0.45, cx + w * 0.45, cy + d * 0.5, cy + d * 0.5 + 2.0)):
                m = 'MI_Emisivo_Calido' if (lit and rng.random() < 0.12) else 'MI_Vidrio'
                box(mb, m, a0, a1, b0, b1, z, z + 150.0)
            box(mb, 'MI_Hormigon', cx - w * 0.5 - 40.0, cx + w * 0.5 + 40.0, cy - d * 0.5 - 40.0, cy - d * 0.5, z - 20.0, z)
            z += 290.0
        box(mb, 'MI_Revoque_Gris', cx - 300.0, cx + 300.0, cy - 250.0, cy + 250.0, H, H + 320.0)
        cyl(mb, M_HIERRO, (cx, cy, H + 320.0), (cx, cy, H + 800.0), 8.0, 8)
        blob(mb, 'MI_Emisivo_Baliza_Roja', (cx, cy, H + 812.0), 14.0, 14.0, 14.0, steps=(6, 8))
    return mb


# =====================================================================================
# BANCO (instanciable)
# =====================================================================================
def build_banco():
    """Banco de plaza: patas de hormigón y listones de madera. Mira a +X (respaldo en -X)."""
    mb = MB('Banco')
    for y in (-78.0, 78.0):
        cbox(mb, 'MI_Hormigon', -24.0, 22.0, y - 7.0, y + 7.0, 0.0, 42.0, 1.0, 'z')
        cbox(mb, 'MI_Hormigon', -32.0, -22.0, y - 7.0, y + 7.0, 0.0, 92.0, 1.0, 'z')
    for j in range(4):
        x = -22.0 + j * 11.5
        cbox(mb, 'MI_Madera', x, x + 10.0, -96.0, 96.0, 42.0, 46.0, 0.6, 'y')
    for j in range(3):
        z = 54.0 + j * 12.5
        cbox(mb, 'MI_Madera', -31.0, -27.0, -96.0, 96.0, z, z + 9.0, 0.6, 'y')
    mb.col(-32.0, 22.0, -96.0, 96.0, 0.0, 46.0)
    return mb


# =====================================================================================
# MARCA DE PUERTA ROBABLE (se lee a 10 m, además del LootPoint)
#   Marco: +X hacia la calle (afuera de la pared), Y a lo largo del frente, origen en el centro de la entrada
#   sobre la cara de la pared (o del cerco, en los portones), z = 0 calzada (alturas absolutas).
# =====================================================================================
def build_marca_robo(kind, w, z0):
    """Lo que distingue una casa "habitada y abierta" (robable) de las cerradas con reja y candado:
    farol de pared negro con vidrio cálido encendido (MI_Emisivo_Calido, se ve de noche), número grande en
    placa blanca, timbre, felpudo y maceta con planta. Para 'gate' (cercos) el farol va en un poste corto.
    Sin colisión (detalles finos)."""
    mb = MB('MarcaRobo_%s_%d' % (kind, int(w)))
    side = w * 0.5 + 30.0
    if kind == 'gate':
        cyl(mb, M_HIERRO, (8.0, side, Z_VER), (8.0, side, 175.0), 3.0, 8)
        lx, lz = 8.0, 175.0
        cbox(mb, M_HIERRO, lx - 11.0, lx + 11.0, side - 11.0, side + 11.0, lz, lz + 6.0, 1.0, 'z')
        box(mb, 'MI_Emisivo_Calido', lx - 8.0, lx + 8.0, side - 8.0, side + 8.0, lz + 6.0, lz + 30.0)
        for (dx, dy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            box(mb, M_HIERRO, lx + dx * 9.0 - 1.2, lx + dx * 9.0 + 1.2, side + dy * 9.0 - 1.2, side + dy * 9.0 + 1.2,
                lz + 6.0, lz + 30.0)
        cone(mb, M_HIERRO, (lx, side, lz + 30.0), (lx, side, lz + 44.0), 14.0, 2.0, 4)
        cbox(mb, 'MI_Cartel_Blanco', 2.0, 3.5, side - 18.0, side + 18.0, 120.0, 140.0, 0.5, 'z')
        for j in range(3):
            box(mb, M_HIERRO, 3.5, 4.0, side - 12.0 + j * 9.0, side - 6.0 + j * 9.0, 124.0, 136.0)
    else:
        # farol de pared con ménsula
        zl = z0 + 228.0
        box(mb, M_HIERRO, 0.0, 3.0, side - 7.0, side + 7.0, zl - 14.0, zl + 14.0)
        cyl(mb, M_HIERRO, (2.0, side, zl + 6.0), (24.0, side, zl + 6.0), 1.6, 6)
        cbox(mb, M_HIERRO, 14.0, 34.0, side - 10.0, side + 10.0, zl - 26.0, zl - 22.0, 0.8, 'z')
        box(mb, 'MI_Emisivo_Calido', 16.5, 31.5, side - 7.5, side + 7.5, zl - 22.0, zl + 2.0)
        for (dx, dy) in ((14.5, -9.0), (33.5, -9.0), (33.5, 9.0), (14.5, 9.0)):
            box(mb, M_HIERRO, dx - 1.0, dx + 1.0, side + dy - 1.0, side + dy + 1.0, zl - 22.0, zl + 2.0)
        cone(mb, M_HIERRO, (24.0, side, zl + 2.0), (24.0, side, zl + 14.0), 15.0, 2.0, 4)
        # número grande (placa blanca con cifras oscuras) y timbre
        cbox(mb, 'MI_Cartel_Blanco', 0.0, 1.6, side - 20.0, side + 20.0, z0 + 165.0, z0 + 188.0, 0.5, 'z')
        for j in range(4):
            box(mb, M_HIERRO, 1.6, 2.0, side - 14.0 + j * 7.5, side - 9.5 + j * 7.5, z0 + 169.0, z0 + 184.0)
        cbox(mb, 'MI_Chapa_Gris', 0.0, 2.0, side - 4.0, side + 4.0, z0 + 125.0, z0 + 137.0, 0.4, 'z')
        # felpudo y maceta con planta del otro lado de la puerta
        box(mb, 'MI_Neumatico', 4.0, 50.0, -w * 0.4, w * 0.4, Z_VER - 0.5, Z_VER + 1.2)
        ms = -(w * 0.5 + 32.0)
        cone(mb, 'MI_Ladrillo', (22.0, ms, Z_VER), (22.0, ms, Z_VER + 42.0), 15.0, 19.0, 10)
        blob(mb, 'MI_Follaje', (22.0, ms, Z_VER + 70.0), 24.0, 24.0, 34.0, steps=(6, 8))
    return mb
