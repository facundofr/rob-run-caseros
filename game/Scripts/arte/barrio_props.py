# -*- coding: utf-8 -*-
"""
barrio_props.py  -  Props del mapa (cada uno se construye UNA vez y se instancia muchas veces).

Árboles (fresno, plátano podado, paraíso; con hojas de noviembre o pelados), postes de hormigón y de
madera con y sin luminaria, columna doble de avenida, farola de plaza, semáforo, cartel de calle,
canasto (con bolsas), contenedor, volquete, obra, puesto, autos genéricos (sedán, hatchback,
utilitario, pickup, patrullero), camión, colectivo, formación de tren, reja de puerta con candado,
refugio de colectivo, cono, moto.

v4: carteles con TEXTO por UV0 (placa_texto, build_cartel_calle con nombre por instancia, build_cartel_salida),
registro de las MI nuevas en el kit (registrar_materiales), autos a tres vistas, moto (build_moto), árboles
x1,5 / x2,2 con copa orgánica y colisión solo del tronco. Contrato en CONVENCIONES.md, sección v4.

Convenciones: origen en el piso del prop. Vehículos: +X adelante, +Y izquierda. Postes y carteles:
+X hacia la calle. Árboles: -X hacia las casas (ahí la poda acorta las ramas).
"""

import math
import random

import barrio_kit as k
from barrio_kit import MB, box, cbox, prism, cyl, cone, blob, tube, rbox, torus, M_HIERRO, M_PORCELANA
import barrio_layout as L

Z_VER = L.Z_VER


# =====================================================================================
# v4: MATERIALES NUEVOS (registro en el kit) Y PLACAS CON TEXTO (UV0 explícita)
# =====================================================================================
# barrio_kit.MATS es la lista de MI que el kit carga y numera; las MI de v4 se agregan acá al importar este
# módulo (build_barrio recarga barrio_kit ANTES que barrio_props, y llama load_materials() después), así
# barrio_geo y barrio_edificios también pueden usarlas por nombre sin tocar el kit.
CALLES_V4 = [  # (slug de MI_CartelCalle_<slug>, texto)  — mismo orden que gen_textures.CALLES
    ('ValentinGomez', 'Valentín Gómez'), ('Urquiza', 'Justo José de Urquiza'), ('AvSanMartin', 'Av. San Martín'),
    ('Ferreyra', 'Andrés Ferreyra'), ('Alberdi', 'Juan Bautista Alberdi'), ('Nicaragua', 'Nicaragua'),
    ('Sabattini', 'Sabattini'), ('Fischetti', 'Fischetti'), ('MarianoMoreno', 'Mariano Moreno'),
    ('EstebanMerlo', 'Esteban Merlo'), ('Bonifacini', 'Bonifacini'), ('Puan', 'Puan'), ('Rauch', 'Rauch'),
    ('MarcoPolo', 'Marco Polo'), ('Espana', 'España'), ('Constitucion', 'Constitución'),
]
COMERCIOS_V4 = ['AlmacenDonTito', 'Kiosco24hs', 'VerduleriaLaEsquina', 'FerreteriaElTornillo', 'PizzeriaLoDeCacho',
                'FarmaciaDelBarrio', 'CarniceriaLosHermanos', 'PanaderiaLaEspiga', 'PeluqueriaEstilo',
                'RotiseriaDonaRosa', 'LibreriaElLapiz', 'GomeriaElRayo', 'LavaderoBurbujas', 'PolirrubroLosChicos',
                'DespensaMary', 'BazarElSol']
# MI de texto -> aspecto ancho/alto de la placa (la textura NO se estira si se respeta)
CARTELES_V4 = {}
for _s, _t in CALLES_V4:
    CARTELES_V4['MI_CartelCalle_' + _s] = 4.0
CARTELES_V4['MI_CartelCalle_X'] = 4.0          # slots de la malla CartelCalle (se cambian por instancia)
CARTELES_V4['MI_CartelCalle_Y'] = 4.0
for _s in COMERCIOS_V4:
    CARTELES_V4['MI_Comercio_' + _s] = 8.0
CARTELES_V4.update({
    'MI_Cartel_Comisaria': 8.0, 'MI_Cartel_Estacion': 8.0, 'MI_Cartel_Salida': 4.0, 'MI_Cartel_Salida_Der': 4.0,
    'MI_Cartel_Salida_Izq': 4.0, 'MI_Cartel_NoEstacionar': 4.0, 'MI_Bandera_Celeste': 2.0,
    'MI_Afiche_SeVende': 1.0, 'MI_Afiche_Alquilo': 1.0,
    'MI_Pintada_1': 1.0, 'MI_Pintada_2': 1.0, 'MI_Pintada_3': 1.0, 'MI_Pintada_4': 1.0,   # enmascaradas (alfa)
})
MATS_V4 = sorted(CARTELES_V4.keys()) + ['MI_Ladrillo_Torre', 'MI_Hormigon_Pilar']


def registrar_materiales(nombres=MATS_V4):
    """Agrega MI al kit (MATS / MAT_INDEX). Idempotente. Si load_materials() ya corrió, carga las que falten."""
    nuevos = []
    for m in nombres:
        if m not in k.MAT_INDEX:
            k.MATS.append(m)
            k.MAT_INDEX[m] = len(k.MATS) - 1
            nuevos.append(m)
    if k.MI:
        try:
            import unreal
            for m in nombres:
                if k.MI.get(m) is None:
                    p = k.MAT_DIR + '/' + m
                    if unreal.EditorAssetLibrary.does_asset_exist(p):
                        k.MI[m] = unreal.EditorAssetLibrary.load_asset(p)
        except Exception as e:
            k.warn('registrar_materiales: %s' % e)
    return nuevos


registrar_materiales()


def _norm_txt(s):
    import unicodedata
    s = unicodedata.normalize('NFKD', str(s))
    return ''.join(ch for ch in s if ch.isalnum()).lower()


_ALIAS_CALLE = {'sanmartin': 'AvSanMartin', 'avsanmartin': 'AvSanMartin', 'urquiza': 'Urquiza',
                'justojosedeurquiza': 'Urquiza', 'alberdi': 'Alberdi', 'ferreyra': 'Ferreyra', 'moreno': 'MarianoMoreno',
                'merlo': 'EstebanMerlo', 'gomez': 'ValentinGomez'}


def mi_calle(nombre):
    """'Nicaragua' / 'nicaragua' / 'Av. San Martín' / 'AvSanMartin' / 'MI_CartelCalle_Puan' -> nombre de MI."""
    if str(nombre).startswith('MI_CartelCalle_'):
        return str(nombre)
    n = _norm_txt(nombre)
    for slug, txt in CALLES_V4:
        if n in (slug.lower(), _norm_txt(txt)):
            return 'MI_CartelCalle_' + slug
    if n in _ALIAS_CALLE:
        return 'MI_CartelCalle_' + _ALIAS_CALLE[n]
    k.warn_once('calle_' + n, 'mi_calle: no hay placa para "%s"; uso Nicaragua' % nombre)
    return 'MI_CartelCalle_Nicaragua'


# Nombres sugeridos por eje de calle (MAPA.md). Ejes: X de las calles N-S, Y de las calles E-O.
CALLES_NS = [(866.0, 'Fischetti'), (11258.0, 'Valentín Gómez'), (21650.0, 'Mariano Moreno'),
             (32476.0, 'Av. San Martín')]
CALLES_EO = [(-9526.0, 'Bonifacini'), (866.0, 'Esteban Merlo'), (11258.0, 'Justo José de Urquiza'), (21650.0, 'Andrés Ferreyra'),
             (27866.0, 'Sabattini')]


def nombres_esquina(x, y):
    """(calle N-S más cercana a x, calle E-O más cercana a y)."""
    ns = min(CALLES_NS, key=lambda c: abs(c[0] - x))[1]
    eo = min(CALLES_EO, key=lambda c: abs(c[0] - y))[1]
    return ns, eo


def swaps_cartel_calle(nombre_x, nombre_y):
    """swaps para spawn/put de la malla CartelCalle: placa del eje local X y placa del eje local Y."""
    return {'MI_CartelCalle_X': mi_calle(nombre_x), 'MI_CartelCalle_Y': mi_calle(nombre_y)}


def swaps_cartel_calle_en(pos, yaw):
    """Swaps listos para un cartel de esquina en pos (mundo) con yaw (grados): cada placa queda paralela a la
    calle que nombra (la placa del eje local X nombra la calle que corre en esa dirección del mundo)."""
    ns, eo = nombres_esquina(pos[0], pos[1])
    a = math.radians(yaw)
    x_en_mundo_x = abs(math.cos(a)) >= abs(math.sin(a))
    return swaps_cartel_calle(eo, ns) if x_en_mundo_x else swaps_cartel_calle(ns, eo)


# ------------------------------------------------------------------ UV explícita (Geometry Script)
_UVA = {}


def _uv_api():
    if 'ok' in _UVA:
        return _UVA
    import unreal

    def pick(libname, names):
        lib = getattr(unreal, libname, None)
        if lib is None:
            return None
        for n in names:
            if hasattr(lib, n):
                return getattr(lib, n)
        return None
    _UVA['set_tri'] = pick('GeometryScript_UVs', ['set_mesh_triangle_u_vs', 'set_mesh_triangle_uvs'])
    _UVA['tri_pos'] = pick('GeometryScript_MeshQueries', ['get_triangle_positions'])
    _UVA['num_tri'] = pick('GeometryScript_MeshQueries', ['get_num_triangle_i_ds', 'get_num_triangle_ids',
                                                          'get_triangle_count'])
    _UVA['planar'] = pick('GeometryScript_UVs', ['set_mesh_u_vs_from_planar_projection',
                                                 'set_mesh_uvs_from_planar_projection'])
    _UVA['uvtri'] = getattr(unreal, 'GeometryScriptUVTriangle', None)
    _UVA['ok'] = bool(_UVA['set_tri'] and _UVA['tri_pos'] and _UVA['num_tri'] and _UVA['uvtri'])
    k.log('UV de carteles: %s' % ('por triángulo (exacta)' if _UVA['ok'] else
                                   ('proyección plana (respaldo)' if _UVA['planar'] else 'NO DISPONIBLE')))
    return _UVA


def _vecs(res):
    out = []
    items = res if isinstance(res, (list, tuple)) else [res]
    for x in items:
        if hasattr(x, 'x') and hasattr(x, 'y') and hasattr(x, 'z'):
            out.append((float(x.x), float(x.y), float(x.z)))
    return out


def _int_of(res):
    items = res if isinstance(res, (list, tuple)) else [res]
    for x in items:
        if isinstance(x, int) and not isinstance(x, bool):
            return x
    return -1


def _uv_placa(mesh, ancho, alto, esp, dos_caras, uv_borde=(0.5, 0.03)):
    """UV0 de una placa canónica (caja: x en ±esp/2, y en ±ancho/2, z 0..alto). Cara +X: texto legible para quien
    la mira desde +X (en UE, mirando hacia -X la derecha de pantalla es -Y => u crece hacia -Y); cara -X: igual
    desde atrás (u crece hacia +Y) o borde si no es doble faz; cantos: un texel del margen del cartel."""
    api = _uv_api()
    if api['ok']:
        n = _int_of(api['num_tri'](mesh))
        if n <= 0:
            raise RuntimeError('placa sin triángulos')
        for tid in range(n):
            p = _vecs(api['tri_pos'](mesh, tid))
            if len(p) < 3:
                continue
            cx = (p[0][0] + p[1][0] + p[2][0]) / 3.0
            uvs = []
            for (x, y, z) in p[:3]:
                if cx > esp * 0.25:
                    u, v = (ancho * 0.5 - y) / ancho, (alto - z) / alto
                elif cx < -esp * 0.25 and dos_caras:
                    u, v = (y + ancho * 0.5) / ancho, (alto - z) / alto
                else:
                    u, v = uv_borde
                uvs.append((min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)))
            import unreal
            t = api['uvtri']()
            for name, (u, v) in zip(('uv0', 'uv1', 'uv2'), uvs):
                k._sp(t, name, unreal.Vector2D(u, v))
            try:
                api['set_tri'](mesh, 0, tid, t)
            except TypeError:
                api['set_tri'](target_mesh=mesh, uv_set_index=0, triangle_id=tid, uvs=t)
        return 'tri'
    if api['planar']:
        # Respaldo: proyección plana sobre la cara +X (el dorso queda espejado, los cantos estirados).
        import unreal
        rot = unreal.MathLibrary.make_rot_from_xy(k.V(0.0, -1.0, 0.0), k.V(0.0, 0.0, -1.0))
        t = k.T((esp * 0.5, ancho * 0.5, alto), rot, (ancho, alto, 1.0))
        sel = unreal.GeometryScriptMeshSelection()
        try:
            api['planar'](mesh, 0, t, sel)
        except TypeError:
            api['planar'](target_mesh=mesh, uv_set_index=0, plane_transform=t, selection=sel)
        return 'planar'
    return None


def placa_texto(mb, mat, cx, cy, z0, ancho, alto=None, espesor=1.5, yaw=0.0, dos_caras=False):
    """Placa con la textura de un cartel (MI de CARTELES_V4) mapeada por UV0 a la cara de texto.
    Marco (antes de yaw): caja centrada en (cx, cy), espesor en X (cara de texto mirando a +X, la convención de
    fachadas del kit: +X hacia la calle), ancho en Y, de z0 a z0+alto. yaw gira alrededor de (cx, cy).
    alto=None -> ancho / aspecto del cartel. dos_caras=True: el dorso también muestra el texto (legible).
    Respeta el espejado del kit (variantes _m): la placa se ubica espejada pero el texto NO se invierte."""
    if mat in CARTELES_V4 and alto is None:
        alto = ancho / CARTELES_V4[mat]
    alto = float(alto or ancho * 0.25)
    registrar_materiales([mat])
    tmp = None
    try:
        tmp = k.new_mesh()
        k._box_raw(tmp, k.popts(mat), k.T((0.0, 0.0, 0.0)), espesor, ancho, alto, k.ORIGIN['base'])
        modo = _uv_placa(tmp, ancho, alto, espesor, dos_caras)
        if modo is None:
            k.err_once('uv_placa', 'Sin API de UV en Geometry Script: los carteles con texto quedan sin mapear')
        loc, yw = (cx, cy, z0), yaw
        if k.MIRROR['on']:
            loc, yw = k._mp(loc), -yaw
        k.append_into(mb.m(mat), tmp, k.T(loc, k.R(yaw=yw)))
    finally:
        k.free_mesh(tmp)


def cartel_con_texto(mb, mat, cx, cy, z0, ancho, yaw=0.0, espesor=2.0, marco=None, dos_caras=False):
    """Cartel de chapa listo: placa de texto (aspecto del atlas) + marco/canto opcional de otro material
    (p. ej. M_HIERRO) 1 cm más grande, por detrás. Devuelve el alto."""
    alto = ancho / CARTELES_V4.get(mat, 4.0)
    if marco:
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        bx, by = cx - c * (espesor * 0.5 + 0.6), cy - s * (espesor * 0.5 + 0.6)
        rbox(mb, marco, bx, by, z0 - 1.0, 1.2, ancho + 2.0, alto + 2.0, yaw)
    placa_texto(mb, mat, cx, cy, z0, ancho, alto, espesor, yaw, dos_caras)
    return alto


def bandera_celeste(mb, mx, my, z_top, ancho=150.0, yaw=0.0, espesor=1.0):
    """Bandera (MI_Bandera_Celeste, 2:1) colgada de un mástil en (mx, my): se extiende hacia +X local (girada por
    yaw alrededor del mástil) con el borde superior en z_top; las dos caras muestran la bandera."""
    alto = ancho / CARTELES_V4['MI_Bandera_Celeste']
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cx, cy = mx + c * (ancho * 0.5 + 2.0), my + s * (ancho * 0.5 + 2.0)
    placa_texto(mb, 'MI_Bandera_Celeste', cx, cy, z_top - alto, ancho, alto, espesor, yaw + 90.0, dos_caras=True)


def pintada(mb, n, cx, cy, z0, ancho=120.0, yaw=0.0):
    """Tag en aerosol (MI_Pintada_1..4, enmascarado por alfa) pegado a una pared que mira a +X local.
    cx = cara de la pared (la lámina de 0,2 cm queda apenas por delante)."""
    mat = 'MI_Pintada_%d' % (1 + (int(n) - 1) % 4)
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    placa_texto(mb, mat, cx + c * 0.3, cy + s * 0.3, z0, ancho, ancho, 0.2, yaw, dos_caras=False)


# =====================================================================================
# ÁRBOLES
# =====================================================================================
def _dir(el_deg, az):
    el = math.radians(el_deg)
    return (math.sin(el) * math.cos(az), math.sin(el) * math.sin(az), math.cos(el))


def _poda(d, f=0.45):
    if d[0] < 0:
        d = (d[0] * f, d[1], d[2])
    return k.v_norm(d)


TREE_KIND_ID = {'fresno': 1, 'platano': 2, 'paraiso': 3}


# ------------------------------------------------------------------ tarjetas de hojas (v5)
HOJAS_MI = {'fresno': 'MI_Hojas_Fresno', 'paraiso': 'MI_Hojas_Paraiso', 'platano': 'MI_Hojas_Platano'}


def _card_template(mat, quad, esp=0.3):
    """Tarjeta canónica 1x1 (escala por transform) centrada en el origen, cara en el plano YZ mirando a +X,
    con UV0 en el cuadrante `quad` (0-3) del atlas T_Hojas (2x2). Dorso con la misma imagen; cantos a un texel
    transparente. Devuelve una DynamicMesh del pool (la libera el llamador)."""
    import unreal
    api = _uv_api()
    tmp = k.new_mesh()
    k._box_raw(tmp, k.popts(mat), k.T((0.0, 0.0, 0.0)), esp, 1.0, 1.0, k.ORIGIN['center'])
    qx, qy = (quad % 2) * 0.5, (quad // 2) * 0.5
    if api['ok']:
        n = _int_of(api['num_tri'](tmp))
        for tid in range(n):
            p = _vecs(api['tri_pos'](tmp, tid))
            if len(p) < 3:
                continue
            cx = (p[0][0] + p[1][0] + p[2][0]) / 3.0
            uvs = []
            for (x, y, z) in p[:3]:
                if cx > esp * 0.25:
                    u, v = 0.5 - y, 0.5 - z
                elif cx < -esp * 0.25:
                    u, v = y + 0.5, 0.5 - z
                else:
                    u, v = 0.01, 0.01
                u, v = min(max(u, 0.004), 0.996), min(max(v, 0.004), 0.996)
                uvs.append((qx + 0.5 * u, qy + 0.5 * v))
            t = api['uvtri']()
            for name, (u, v) in zip(('uv0', 'uv1', 'uv2'), uvs):
                k._sp(t, name, unreal.Vector2D(u, v))
            try:
                api['set_tri'](tmp, 0, tid, t)
            except TypeError:
                api['set_tri'](target_mesh=tmp, uv_set_index=0, triangle_id=tid, uvs=t)
    else:
        k.err_once('uv_hojas', 'Sin API de UV: las copas con tarjetas de hojas quedan sin mapear')
    return tmp


def _copa_tarjetas(mb, rng, mat, tpl, c, R, flat, n, size, up_bias=0.45, street_bias=True):
    """Racimo de tarjetas de hojas sobre un elipsoide (R, R, R*flat) alrededor de c. Cada tarjeta apunta su
    ramita hacia el centro (el 'arriba' de la imagen va hacia afuera) con giro aleatorio sobre ese eje."""
    import unreal
    for i in range(n):
        # dirección sobre la esfera, sesgada hacia arriba y (en vereda) hacia la calle (+X)
        z = rng.uniform(-0.55, 1.0)
        a = rng.uniform(0.0, 2.0 * math.pi)
        r = math.sqrt(max(0.0, 1.0 - z * z))
        o = (r * math.cos(a), r * math.sin(a), z)
        if street_bias and o[0] < 0:
            o = (o[0] * 0.75, o[1], o[2])
        o = k.v_norm((o[0], o[1], o[2] + up_bias))
        dist = rng.uniform(0.55, 0.95)
        pos = (c[0] + o[0] * R * dist, c[1] + o[1] * R * dist, c[2] + o[2] * R * flat * dist)
        # eje Z de la tarjeta = afuera; X (normal) perpendicular aleatoria
        tmpv = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.3))
        xn = k.v_norm(k.v_cross(o, tmpv)) if hasattr(k, 'v_cross') else k.v_norm((o[1] * tmpv[2] - o[2] * tmpv[1],
                                                                              o[2] * tmpv[0] - o[0] * tmpv[2],
                                                                              o[0] * tmpv[1] - o[1] * tmpv[0]))
        rot = unreal.MathLibrary.make_rot_from_zx(k.V(o), k.V(xn))
        sz = size * rng.uniform(0.75, 1.25)
        # la tarjeta se corre medio tamaño hacia afuera: la ramita queda adentro de la copa
        pc = (pos[0] + o[0] * sz * 0.35, pos[1] + o[1] * sz * 0.35, pos[2] + o[2] * sz * 0.35)
        k.append_into(mb.m(mat), tpl[rng.randrange(len(tpl))], k.T(pc, rot, (1.0, sz, sz)))


def build_arbol2(kind, seed, pelado=False, big=False):
    """Árbol de vereda/plaza (v4). Escala x1,5 en vereda (9-12 m, la copa techa la calzada como en las refs de
    Valentín Gómez / Esteban Merlo) y x2,2 en plaza (big). Copa = muchos grupos chicos y aplanados de hojas
    (elipsoides de 8x12 lados: con el corte de normales del kit a 40° quedan lisos, no "rocas"), con huecos y
    sin bloques sueltos fuera de la silueta. Ramas finas en dos tramos con curva; las que van a la calle (+X)
    son más largas y bajas (la poda municipal acorta las del lado de las casas, -X). Colisión: solo el tronco."""
    rng = random.Random(1000 + seed * 31 + TREE_KIND_ID[kind] * 7 + (500 if pelado else 0) + (900 if big else 0))
    mb = MB('Arbol')
    S = 2.2 if big else 1.5
    Sr = 1.0 + (S - 1.0) * 0.6        # los grosores crecen menos que el porte (tronco de vereda ~40 cm, plaza ~65 cm)
    if kind == 'platano':
        th, r0, r1 = rng.uniform(260.0, 300.0) * S, 20.0 * Sr, 14.0 * Sr
        nmain, el_rng, l1_rng = rng.randint(4, 5), (22.0, 38.0), (95.0, 135.0)
    elif kind == 'paraiso':
        th, r0, r1 = rng.uniform(200.0, 240.0) * S, 15.0 * Sr, 11.0 * Sr
        nmain, el_rng, l1_rng = rng.randint(5, 6), (55.0, 70.0), (130.0, 170.0)
    else:
        th, r0, r1 = rng.uniform(220.0, 260.0) * S, 16.0 * Sr, 11.5 * Sr
        nmain, el_rng, l1_rng = rng.randint(4, 6), (28.0, 48.0), (120.0, 175.0)
    lean = 0.0 if big else 14.0 * S                        # vereda: el tronco se va hacia la luz de la calle
    mid = (rng.uniform(-6.0, 6.0) + lean * 0.35, rng.uniform(-6.0, 6.0), th * 0.5)
    top = (mid[0] + rng.uniform(-6.0, 6.0) + lean * 0.65, mid[1] + rng.uniform(-9.0, 9.0), th)
    rm = 0.5 * (r0 + r1)
    cone(mb, 'MI_Corteza', (0.0, 0.0, -20.0), mid, r0, rm, 14)
    cone(mb, 'MI_Corteza', mid, top, rm, r1, 14)
    blob(mb, 'MI_Corteza', top, r1 * 1.2, r1 * 1.2, r1 * 1.05, steps=(8, 12))
    for i in range(3):                                     # raíces que levantan la vereda
        a = rng.uniform(0.0, 2.0 * math.pi)
        cone(mb, 'MI_Corteza', (0.0, 0.0, 4.0), (r0 * 2.0 * math.cos(a), r0 * 2.0 * math.sin(a), Z_VER - 2.0),
             r0 * 0.45, r0 * 0.12, 6)
    if kind != 'paraiso' and not big and rng.random() < 0.6:
        t = min(1.0, 120.0 / (mid[2] + 20.0))
        pe = k.v_lerp((0.0, 0.0, -20.0), mid, t)
        cone(mb, 'MI_Pintura_Blanca', (0.0, 0.0, -20.0), pe, r0 + 0.8, r0 + (rm - r0) * t + 0.8, 14)
    tips = []
    for i in range(nmain):
        az = 2.0 * math.pi * i / nmain + rng.uniform(-0.35, 0.35)
        el = rng.uniform(*el_rng)
        L1 = rng.uniform(*l1_rng) * S
        d1 = _poda(_dir(el, az))
        if d1[0] > 0.3 and not big:                       # hacia la calle: más larga y más tendida
            L1 *= 1.45
            el = max(15.0, el - 8.0)
            d1 = _poda(_dir(el, az))
        p1 = k.v_add(top, k.v_mul(d1, L1))
        if kind == 'paraiso':
            el2 = el + rng.uniform(4.0, 12.0)
        else:
            el2 = max(5.0, el - rng.uniform(12.0, 25.0))
        d2 = _poda(_dir(el2, az + rng.uniform(-0.3, 0.3)))
        L2 = L1 * rng.uniform(0.6, 0.85)
        p2 = k.v_add(p1, k.v_mul(d2, L2))
        rb = (11.0 if kind == 'platano' else 8.5) * Sr
        cone(mb, 'MI_Corteza', top, p1, rb, rb * 0.68, 10)
        blob(mb, 'MI_Corteza', p1, rb * 0.72, rb * 0.72, rb * 0.75, steps=(6, 10))
        cone(mb, 'MI_Corteza', p1, p2, rb * 0.68, rb * 0.36, 9)
        if kind == 'platano':
            blob(mb, 'MI_Corteza', p2, 10.0 * Sr, 10.0 * Sr, 12.0 * Sr, steps=(6, 10))  # cabeza de poda
        tips.append((p2, d2, rb * 0.36))
        for j in range(rng.randint(1, 2)):
            q0 = k.v_lerp(top, p1, rng.uniform(0.55, 0.95))
            d3 = _poda(_dir(el + rng.uniform(-10.0, 15.0), az + rng.choice((-1, 1)) * rng.uniform(0.5, 1.0)))
            q1 = k.v_add(q0, k.v_mul(d3, rng.uniform(55.0, 100.0) * S))
            d4 = _poda(_dir(max(5.0, el - rng.uniform(5.0, 20.0)), az + rng.uniform(-0.6, 0.6)))
            q2 = k.v_add(q1, k.v_mul(d4, rng.uniform(45.0, 85.0) * S))
            cone(mb, 'MI_Corteza', q0, q1, 3.6 * Sr, 2.3 * Sr, 7)
            cone(mb, 'MI_Corteza', q1, q2, 2.3 * Sr, 1.2 * Sr, 6)
            tips.append((q2, d4, 1.2 * Sr))
    # brotes finos en dos tramos (no púas: curvan y varían); más en los pelados (es lo que se ve)
    nb = rng.randint(14, 22) + (10 if pelado else 0)
    for b in range(nb):
        p, d, r = tips[b % len(tips)]
        up = 0.5 if kind != 'platano' else 1.2
        dd = k.v_norm((d[0] + rng.uniform(-0.6, 0.6), d[1] + rng.uniform(-0.6, 0.6), d[2] + up))
        Lb = rng.uniform(40.0, 110.0) * (1.6 if kind == 'platano' else 1.0) * S
        rr = rng.uniform(0.6, 1.1) * Sr
        a = k.v_add(p, (rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-2, 3)))
        m = k.v_add(a, k.v_mul(dd, Lb * 0.55))
        dd2 = k.v_norm((dd[0] + rng.uniform(-0.35, 0.35), dd[1] + rng.uniform(-0.35, 0.35), dd[2] + 0.25))
        e = k.v_add(m, k.v_mul(dd2, Lb * 0.45))
        cone(mb, 'MI_Corteza', a, m, rr, rr * 0.62, 5)
        cone(mb, 'MI_Corteza', m, e, rr * 0.62, 0.18, 5)
    # copa de noviembre: por punta de rama un "racimo" de 9-14 grupos chicos y planos + 2 núcleos que tapan
    # las transparencias. Las rotaciones son chicas (±12°): capas horizontales de follaje, no piedras volteadas.
    if not pelado:
        if kind == 'paraiso':
            Rr, flat = (95.0, 135.0), 0.42
        elif kind == 'platano':
            Rr, flat = (80.0, 110.0), 0.55
        else:
            Rr, flat = (85.0, 122.0), 0.6
        # v5: núcleos de follaje opaco (dan volumen y sombra) + tarjetas de hojas enmascaradas que arman la
        # silueta (antes eran 9-14 elipsoides por racimo: de cerca se leían como "brócoli").
        hm = HOJAS_MI.get(kind, 'MI_Hojas_Fresno')
        registrar_materiales([hm])
        tpl = []
        try:
            tpl = [_card_template(hm, q) for q in range(4)]
            for (p, d, r) in tips:
                if rng.random() < 0.10:
                    continue                                    # hueco en la copa
                R_ = rng.uniform(*Rr) * S
                c = k.v_add(p, (d[0] * 26.0 * S, d[1] * 26.0 * S, 20.0 * S + d[2] * 10.0))
                for b in range(2):                              # núcleos (más chicos que antes, quedan adentro)
                    off = (rng.uniform(-0.2, 0.2) * R_, rng.uniform(-0.2, 0.2) * R_, rng.uniform(-0.1, 0.12) * R_)
                    rx = R_ * rng.uniform(0.26, 0.32)               # chicos: quedan tapados por las tarjetas
                    blob(mb, 'MI_Follaje', k.v_add(c, off), rx, rx * rng.uniform(0.85, 1.1), rx * flat * 0.9,
                         yaw=rng.uniform(0, 180), pitch=rng.uniform(-8, 8), roll=rng.uniform(-8, 8), steps=(7, 10))
                _copa_tarjetas(mb, rng, hm, tpl, c, R_, max(flat, 0.55), rng.randint(24, 32),
                               rng.uniform(105.0, 135.0) * S * 0.55, street_bias=not big)
            # relleno interior (sin cerrar la copa) + tarjetas que lo rodean
            hc = th + (120.0 if kind != 'paraiso' else 90.0) * S
            for b in range(rng.randint(2, 3)):
                q = (top[0] + rng.uniform(-40, 50) * S, top[1] + rng.uniform(-50, 50) * S, hc + rng.uniform(-20, 40) * S)
                rs = rng.uniform(26.0, 36.0) * S
                blob(mb, 'MI_Follaje', q, rs, rs, rs * 0.6, yaw=rng.uniform(0, 180), steps=(7, 10))
                _copa_tarjetas(mb, rng, hm, tpl, q, rs * 1.9, 0.7, 12, 62.0 * S, street_bias=not big)
        finally:
            for t_ in tpl:
                k.free_mesh(t_)
    # colisión: SOLO el tronco (una caja un poco más chica que el tronco, hasta la cruz)
    rc = r0 * 0.85
    mb.col(-rc, rc, -rc, rc, 0.0, min(th, 400.0))
    return mb


# =====================================================================================
# POSTES
# =====================================================================================
POLE2 = {
    'lum': {'top': 900.0, 'za': 840.0, 'ins': [-75.0, -28.0, 28.0, 75.0], 'tel': [700.0, 676.0, 652.0, 628.0, 604.0]},
    'simple': {'top': 820.0, 'za': None, 'ins': [], 'tel': [740.0, 714.0, 688.0, 662.0, 636.0, 610.0]},
}


def pole_r(kind, z):
    top = POLE2[kind]['top']
    return 15.0 - 5.5 * (z + 40.0) / (top + 40.0)


def build_poste2(kind, matname):
    """Poste de hormigón (gris, mayoría en Caseros) o de madera gris plata. 'lum' = con cruceta de
    baja tensión y luminaria de brazo; 'simple' = de telefonía/fibra."""
    d = POLE2[kind]
    mb = MB('Poste')
    M = 'MI_PosteHormigon' if matname == 'hormigon' else 'MI_PosteMadera'
    top = d['top']
    sides = 12 if matname == 'hormigon' else 14
    cone(mb, M, (0.0, 0.0, -40.0), (0.0, 0.0, top), 15.0, 9.5, sides)
    cone(mb, M, (0.0, 0.0, top), (0.0, 0.0, top + 4.0), 9.5, 6.0, sides)
    cyl(mb, 'MI_Hormigon', (0.0, 0.0, Z_VER - 1.0), (0.0, 0.0, Z_VER + 4.0), 23.0, 14)
    if matname == 'hormigon':
        # agujeros de escalamiento / bulones (detalle de poste de hormigón)
        for z in (300.0, 420.0, 540.0):
            r = pole_r(kind, z)
            box(mb, M_HIERRO, -1.5, 1.5, -r - 1.5, r + 1.5, z, z + 3.0)
    za = d['za']
    if za is not None:
        cm = 'MI_Hormigon' if matname == 'hormigon' else 'MI_PosteMadera'
        cbox(mb, cm, -95.0, 95.0, -6.0, 6.0, za - 10.0, za, 1.0, 'x')
        rr = pole_r(kind, za)
        box(mb, M_HIERRO, -rr - 1.0, rr + 1.0, -7.0, 7.0, za - 8.0, za - 2.0)
        for s in (-1.0, 1.0):
            cyl(mb, M_HIERRO, (s * 52.0, 7.0, za - 10.0), (s * (pole_r(kind, za - 60.0) + 0.5), 7.0, za - 60.0), 1.0, 6)
        for xi in d['ins']:
            cyl(mb, M_PORCELANA, (xi, 0.0, za), (xi, 0.0, za + 13.0), 3.0, 10)
            for j in range(3):
                cyl(mb, M_PORCELANA, (xi, 0.0, za + 2.5 + j * 3.6), (xi, 0.0, za + 3.7 + j * 3.6), 5.5, 12)
    for z in d['tel']:
        r = pole_r(kind, z)
        torus(mb, M_HIERRO, (0.0, 0.0, z), r + 1.2, 1.0, (0, 0, 1), 14, 4)
        box(mb, M_HIERRO, -3.0, 3.0, r - 1.0, r + 4.0, z - 3.0, z + 3.0)
    # rulos de reserva de fibra
    zc = 520.0 if kind == 'lum' else 480.0
    rz = pole_r(kind, zc)
    # v4: 2 vueltas finas (antes 4 de 0,9 cm: de lejos se leían como un aro grueso)
    for (R_, dz, tilt) in ((27.0, 0.0, 0.0), (25.5, 2.5, 0.12)):
        torus(mb, 'MI_Cable', (0.0, rz + 2.0, zc + dz), R_, 0.6, (tilt, 1.0, 0.0), 20, 5)
    box(mb, M_HIERRO, -2.0, 2.0, rz - 1.0, rz + 4.0, zc + 20.0, zc + 30.0)
    zb = 565.0 if kind == 'lum' else 545.0
    rb = pole_r(kind, zb)
    cbox(mb, 'MI_Chapa_Gris', -9.0, 9.0, -rb - 15.0, -rb - 1.0, zb, zb + 38.0, 1.2, 'z')
    for j in range(3):
        tube(mb, 'MI_Cable', [(-4.0 + j * 4.0, -rb - 8.0, zb), (-4.0 + j * 4.0, -rb - 9.0, zb - 25.0 - j * 10.0),
                              (-3.0 + j * 4.0, -rb - 3.0, zb - 60.0 - j * 12.0)], 0.45, 5)
    cyl(mb, 'MI_Chapa_Gris', (-17.5, 0.0, 0.0), (-16.0, 0.0, 260.0), 2.6, 10)
    r2 = pole_r(kind, 250.0)
    box(mb, 'MI_Chapa_Gris', r2 - 0.6, r2 + 0.2, -6.0, 6.0, 240.0, 258.0)
    if kind == 'lum':
        r7 = pole_r(kind, 772.0)
        torus(mb, M_HIERRO, (0.0, 0.0, 772.0), r7 + 1.5, 1.6, (0, 0, 1), 14, 4)
        ax = L.ARM_X
        pts = [(r7, 0.0, 772.0), (60.0, 0.0, 793.0), (130.0, 0.0, 810.0), (ax - 20.0, 0.0, L.LUM_Z + 14.0)]
        tube(mb, M_HIERRO, pts, 2.8, 8)
        cyl(mb, M_HIERRO, (r7, 0.0, 740.0), (70.0, 0.0, 794.0), 1.6, 8)
        blob(mb, 'MI_Chapa_Gris', (ax + 4.0, 0.0, L.LUM_Z + 14.0), 34.0, 15.0, 8.0, steps=(6, 10))
        blob(mb, 'MI_Emisivo_Calido', (ax + 8.0, 0.0, L.LUM_Z + 8.0), 24.0, 10.5, 3.0, steps=(5, 8))
        tube(mb, 'MI_Cable', [(r7 + 1.0, 2.0, 768.0), (r7 + 2.0, 4.0, 700.0), (r7 + 1.0, 3.0, 640.0)], 0.5, 5)
    mb.col(-15.0, 15.0, -15.0, 15.0, 0.0, top)
    return mb


def build_columna_av():
    """Columna de acero doble de avenida (cantero central): brazos hacia ambas calzadas (±X)."""
    mb = MB('ColumnaAv')
    cone(mb, 'MI_Chapa_Gris', (0.0, 0.0, -30.0), (0.0, 0.0, L.AV_LUM_Z - 10.0), 12.0, 7.0, 14)
    cbox(mb, 'MI_Hormigon', -25.0, 25.0, -25.0, 25.0, 0.0, 40.0, 2.0, 'z')
    box(mb, 'MI_Chapa_Gris', -14.0, 14.0, -14.0, 14.0, 40.0, 140.0)
    box(mb, 'MI_Chapa_Gris', -14.5, 14.5, 3.0, 14.5, 80.0, 115.0)
    for s in (-1.0, 1.0):
        ax = s * L.AV_ARM_X
        pts = [(0.0, 0.0, L.AV_LUM_Z - 40.0), (s * 50.0, 0.0, L.AV_LUM_Z - 5.0), (s * 140.0, 0.0, L.AV_LUM_Z + 14.0),
               (ax - s * 25.0, 0.0, L.AV_LUM_Z + 16.0)]
        tube(mb, 'MI_Chapa_Gris', pts, 3.5, 8)
        blob(mb, 'MI_Chapa_Gris', (ax, 0.0, L.AV_LUM_Z + 15.0), 38.0, 17.0, 9.0, steps=(6, 10))
        blob(mb, 'MI_Emisivo_Calido', (ax + s * 3.0, 0.0, L.AV_LUM_Z + 8.0), 27.0, 12.0, 3.0, steps=(5, 8))
    mb.col(-25.0, 25.0, -25.0, 25.0, 0.0, L.AV_LUM_Z)
    return mb


FAROLA_LUM_Z = 372.0


def build_farola():
    """Farola de plaza (poste verde con farol de 4 vidrios)."""
    mb = MB('Farola')
    cyl(mb, 'MI_Hormigon', (0.0, 0.0, -10.0), (0.0, 0.0, 24.0), 16.0, 12)
    cone(mb, 'MI_Metal_Verde', (0.0, 0.0, 24.0), (0.0, 0.0, 70.0), 11.0, 6.0, 12)
    cone(mb, 'MI_Metal_Verde', (0.0, 0.0, 70.0), (0.0, 0.0, 360.0), 6.0, 4.0, 12)
    torus(mb, 'MI_Metal_Verde', (0.0, 0.0, 120.0), 6.2, 1.2, (0, 0, 1), 12, 4)
    cyl(mb, 'MI_Metal_Verde', (0.0, 0.0, 358.0), (0.0, 0.0, 368.0), 12.0, 10)
    box(mb, 'MI_Emisivo_Calido', -12.0, 12.0, -12.0, 12.0, 368.0, 412.0)
    for (sx, sy) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        box(mb, 'MI_Metal_Verde', sx * 13.0 - 1.2, sx * 13.0 + 1.2, sy * 13.0 - 1.2, sy * 13.0 + 1.2, 366.0, 414.0)
    cone(mb, 'MI_Metal_Verde', (0.0, 0.0, 414.0), (0.0, 0.0, 432.0), 19.0, 3.0, 4)
    blob(mb, 'MI_Metal_Verde', (0.0, 0.0, 436.0), 3.5, 3.5, 4.5, steps=(5, 6))
    mb.col(-14.0, 14.0, -14.0, 14.0, 0.0, 360.0)
    return mb


def build_semaforo():
    """Semáforo vehicular + peatonal (cara hacia +X)."""
    mb = MB('Semaforo')
    cyl(mb, M_HIERRO, (0.0, 0.0, -20.0), (0.0, 0.0, 330.0), 5.5, 12)
    for z in (40.0, 120.0, 200.0):
        box(mb, 'MI_Pintura_Amarilla', -6.0, 6.0, -6.0, 6.0, z, z + 18.0)
    cbox(mb, M_HIERRO, 8.0, 30.0, -17.0, 17.0, 240.0, 335.0, 2.0, 'z')
    for j, (mat, zc) in enumerate((('MI_Emisivo_Baliza_Roja', 315.0), ('MI_Pintura_Amarilla', 288.0),
                                    ('MI_Cartel_Verde', 261.0))):
        cyl(mb, mat, (30.0, 0.0, zc), (31.5, 0.0, zc), 9.0, 14)
        prism(mb, M_HIERRO, [(30.0, zc + 10.0), (44.0, zc + 9.0), (44.0, zc + 7.5), (30.0, zc + 8.0)], 'y', -10.0, 10.0)
    cbox(mb, M_HIERRO, 8.0, 26.0, -13.0, 13.0, 170.0, 222.0, 1.5, 'z')
    box(mb, 'MI_Emisivo_Baliza_Roja', 26.0, 27.0, -8.0, 8.0, 200.0, 216.0)
    box(mb, 'MI_Cartel_Blanco', 26.0, 26.8, -8.0, 8.0, 176.0, 192.0)
    box(mb, M_HIERRO, -3.0, 10.0, -3.0, 3.0, 300.0, 306.0)
    box(mb, M_HIERRO, -3.0, 10.0, -3.0, 3.0, 195.0, 200.0)
    mb.col(-7.0, 7.0, -7.0, 7.0, 0.0, 330.0)
    return mb


CARTEL_PLACA = (84.0, 21.0, 1.2)      # placa de calle: 84 x 21 cm (4:1, el atlas), chapa de 1,2 cm


def build_cartel_calle(nombre_x=None, nombre_y=None):
    """Poste con dos placas de calle cruzadas, con el NOMBRE real (textura de texto por UV0, doble faz).
    Placa a lo largo del eje local X (más alta, z 262) y a lo largo del eje local Y (z 236).
    Elegir el nombre por instancia (recomendado, UNA malla para todo el mapa): la malla sin argumentos usa los
    slots 'MI_CartelCalle_X' / 'MI_CartelCalle_Y' y cada instancia los reemplaza con
        put(..., swaps=P.swaps_cartel_calle_en(pos, yaw))          # nombres por posición (CALLES_NS / CALLES_EO)
        put(..., swaps=P.swaps_cartel_calle('Nicaragua', 'Puan'))  # nombres a mano (placa X, placa Y)
    Alternativa: build_cartel_calle('Nicaragua', 'Puan') hornea los nombres (una malla por combinación)."""
    mb = MB('CartelCalle')
    mx = mi_calle(nombre_x) if nombre_x else 'MI_CartelCalle_X'
    my = mi_calle(nombre_y) if nombre_y else 'MI_CartelCalle_Y'
    W, H, E = CARTEL_PLACA
    cyl(mb, M_HIERRO, (0.0, 0.0, -20.0), (0.0, 0.0, 300.0), 3.5, 12)
    cone(mb, M_HIERRO, (0.0, 0.0, 300.0), (0.0, 0.0, 306.0), 3.5, 1.0, 12)
    for (along, z0, mat) in (('x', 262.0, mx), ('y', 236.0, my)):
        c0 = 6.0 + W * 0.5                        # centro de la placa, a 6 cm del poste
        if along == 'x':
            # canónica: ancho en Y, cara a +X  ->  yaw 90: ancho en X, caras a ±Y
            placa_texto(mb, mat, c0, 0.0, z0, W, H, E, yaw=90.0, dos_caras=True)
            box(mb, M_HIERRO, -3.0, 8.0, -1.2, 1.2, z0 + 3.0, z0 + 6.0)          # abrazaderas
            box(mb, M_HIERRO, -3.0, 8.0, -1.2, 1.2, z0 + H - 6.0, z0 + H - 3.0)
            box(mb, M_HIERRO, 4.0, 7.0, -1.4, 1.4, z0 + 2.0, z0 + H - 2.0)       # planchuela
        else:
            placa_texto(mb, mat, 0.0, c0, z0, W, H, E, yaw=0.0, dos_caras=True)
            box(mb, M_HIERRO, -1.2, 1.2, -3.0, 8.0, z0 + 3.0, z0 + 6.0)
            box(mb, M_HIERRO, -1.2, 1.2, -3.0, 8.0, z0 + H - 6.0, z0 + H - 3.0)
            box(mb, M_HIERRO, -1.4, 1.4, 4.0, 7.0, z0 + 2.0, z0 + H - 2.0)
    mb.col(-5.0, 5.0, -5.0, 5.0, 0.0, 300.0)
    return mb


def build_cartel_salida(variante='', alto_poste=230.0, ancho=120.0):
    """Cartel diegético de salida (común a E1/E2/E3): poste doble de caño con placa verde 'SALIDA'.
    variante: '' (flecha arriba), 'Der', 'Izq'. Cara de texto hacia +X (doble faz)."""
    mat = 'MI_Cartel_Salida' + ('_' + variante if variante else '')
    mb = MB('CartelSalida' + variante)
    alto = ancho / CARTELES_V4[mat]
    for s in (-1.0, 1.0):
        cyl(mb, M_HIERRO, (0.0, s * ancho * 0.38, -20.0), (0.0, s * ancho * 0.38, alto_poste + alto), 2.4, 10)
    placa_texto(mb, mat, 3.4, 0.0, alto_poste, ancho, alto, 1.5, 0.0, dos_caras=True)
    mb.col(-4.0, 4.0, -ancho * 0.4, ancho * 0.4, 0.0, alto_poste)
    return mb


def build_canasto2(bolsas):
    mb = k.build_canasto()
    if bolsas:
        rng = random.Random(31)
        for (x, y, r) in ((-6.0, -14.0, 20.0), (8.0, 12.0, 22.0), (-4.0, 6.0, 17.0)):
            blob(mb, 'MI_Plastico_Negro', (x, y, 112.0 + r * 0.6), r, r * 0.9, r * 1.05, yaw=rng.uniform(0, 180),
                 pitch=rng.uniform(-15, 15), steps=(7, 10))
            cone(mb, 'MI_Plastico_Negro', (x, y, 112.0 + r * 1.5), (x + 2.0, y, 112.0 + r * 1.5 + 9.0), 4.0, 1.5, 6)
        blob(mb, 'MI_Plastico_Negro', (30.0, 46.0, 16.0 + Z_VER), 19.0, 16.0, 16.0, yaw=30.0, steps=(7, 10))
    return mb


def build_contenedor():
    """Contenedor municipal de residuos (verde) con tapa negra, sobre la calzada junto al cordón."""
    mb = MB('Contenedor')
    side = [(-88.0, 12.0), (88.0, 12.0), (96.0, 122.0), (-96.0, 122.0)]
    prism(mb, 'MI_Metal_Verde', side, 'y', -55.0, 55.0)
    cbox(mb, 'MI_Metal_Verde', -100.0, 100.0, -58.0, 58.0, 112.0, 124.0, 2.0, 'y')
    prism(mb, 'MI_Plastico_Negro', [(-100.0, 124.0), (100.0, 124.0), (100.0, 131.0), (-100.0, 127.0)], 'y', -57.0, 57.0)
    for x in (-70.0, 70.0):
        for y in (-42.0, 42.0):
            cyl(mb, 'MI_Neumatico', (x, y - 4.0, 8.0), (x, y + 4.0, 8.0), 8.0, 12)
    for y in (-56.0, 56.0):
        box(mb, M_HIERRO, -60.0, 60.0, y - 1.0, y + 1.0, 60.0, 70.0)
    box(mb, 'MI_Pintura_Blanca', 92.0, 93.0, -30.0, 30.0, 70.0, 100.0)
    mb.col(-96.0, 96.0, -56.0, 56.0, 0.0, 128.0)
    return mb


def build_volquete():
    """Volquete de obra (amarillo) con escombros."""
    mb = MB('Volquete')
    rng = random.Random(5)
    out = [(-190.0, 125.0), (-150.0, 8.0), (150.0, 8.0), (190.0, 125.0)]
    prism(mb, 'MI_Pintura_Amarilla', out, 'y', -95.0, -85.0)
    prism(mb, 'MI_Pintura_Amarilla', out, 'y', 85.0, 95.0)
    prism(mb, 'MI_Pintura_Amarilla', [(-150.0, 8.0), (150.0, 8.0), (150.0, 18.0), (-150.0, 18.0)], 'y', -85.0, 85.0)
    prism(mb, 'MI_Pintura_Amarilla', [(-190.0, 125.0), (-150.0, 8.0), (-140.0, 8.0), (-180.0, 125.0)], 'y', -85.0, 85.0)
    prism(mb, 'MI_Pintura_Amarilla', [(180.0, 125.0), (140.0, 8.0), (150.0, 8.0), (190.0, 125.0)], 'y', -85.0, 85.0)
    for y in (-97.0, 97.0):
        for x in (-100.0, 0.0, 100.0):
            box(mb, M_HIERRO, x - 4.0, x + 4.0, y - 2.0, y + 2.0, 10.0, 122.0)
        box(mb, M_HIERRO, -170.0, 170.0, y - 2.0, y + 2.0, 118.0, 126.0)
    for x in (-120.0, 120.0):
        box(mb, M_HIERRO, x - 8.0, x + 8.0, -90.0, 90.0, 0.0, 9.0)
    for j in range(16):
        mat = rng.choice(['MI_Hormigon', 'MI_Ladrillo', 'MI_Ladrillo', 'MI_Madera', 'MI_Revoque_Gris'])
        rbox(mb, mat, rng.uniform(-130, 130), rng.uniform(-60, 60), rng.uniform(60, 105), rng.uniform(25, 70),
             rng.uniform(20, 50), rng.uniform(10, 30), rng.uniform(0, 180), rng.uniform(-20, 20), rng.uniform(-20, 20))
    blob(mb, 'MI_Tierra', (0.0, 0.0, 100.0), 150.0, 75.0, 25.0, steps=(6, 10))
    mb.col(-190.0, 190.0, -97.0, 97.0, 0.0, 126.0)
    return mb


def k_cono(mb, x, y, z=0.0):
    cbox(mb, 'MI_Plastico_Negro', x - 17.0, x + 17.0, y - 17.0, y + 17.0, z, z + 3.0, 2.0, 'z')
    cone(mb, 'MI_Cartel_Rojo', (x, y, z + 3.0), (x, y, z + 70.0), 13.0, 3.0, 12)
    cone(mb, 'MI_Pintura_Blanca', (x, y, z + 32.0), (x, y, z + 45.0), 8.6, 6.6, 12)


def k_valla(mb, x0, y0, x1, y1, h=105.0):
    """Valla de obra metálica con franjas rojas y blancas, sobre dos pies."""
    L_ = math.hypot(x1 - x0, y1 - y0)
    if L_ < 10.0:
        return
    ux, uy = (x1 - x0) / L_, (y1 - y0) / L_
    yaw = math.degrees(math.atan2(uy, ux))
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    rbox(mb, M_HIERRO, cx, cy, 0.0, L_, 4.0, 4.0, yaw)
    rbox(mb, M_HIERRO, cx, cy, h - 4.0, L_, 4.0, 4.0, yaw)
    n = max(2, int(L_ / 40.0))
    for j in range(n):
        t0 = (j + 0.08) / n
        t1 = (j + 0.92) / n
        mat = 'MI_Cartel_Rojo' if j % 2 == 0 else 'MI_Pintura_Blanca'
        px = x0 + (x1 - x0) * 0.5 * (t0 + t1)
        py = y0 + (y1 - y0) * 0.5 * (t0 + t1)
        rbox(mb, mat, px, py, h - 34.0, L_ * (t1 - t0), 2.0, 26.0, yaw)
    for t in (0.06, 0.94):
        px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
        cyl(mb, M_HIERRO, (px, py, 0.0), (px, py, h), 2.0, 8)
        rbox(mb, M_HIERRO, px, py, 0.0, 6.0, 55.0, 4.0, yaw)


def build_corte(kind):
    """Cortes de visual en la calle. Marco: +X a lo largo de la calle, +Y hacia la vereda,
    origen en el carril de estacionamiento (el cordón queda en y≈+135)."""
    mb = MB('Corte_' + kind)
    rng = random.Random(len(kind) * 13)
    if kind == 'obra':
        # volquete + vallado + tapial de chapa de 2,2 m del lado de la calle (corta la visual)
        vq = build_volquete()
        k.merge_mb(mb, vq, (-150.0, 20.0, 0.0), 0.0)
        y_out = -185.0
        for x in range(-450, 450, 100):
            rib = k.ribs_profile_xy(y_out, 0.8, float(x) + 0.5, float(x) + 99.5, 7.6, 1.6)
            prism(mb, 'MI_Chapa_Gris', [(q, p_) for (p_, q) in rib], 'z', 2.0, 220.0)
        for x in range(-450, 451, 150):
            box(mb, 'MI_Madera', x - 4.0, x + 4.0, y_out + 1.2, y_out + 9.0, 0.0, 230.0)
        box(mb, 'MI_Madera', -452.0, 452.0, y_out + 1.2, y_out + 7.0, 100.0, 108.0)
        # carteles pintados en blanco sobre el tapial (sin texto)
        box(mb, 'MI_Pintura_Blanca', -300.0, -80.0, y_out - 0.4, y_out, 120.0, 190.0)
        box(mb, 'MI_Pintura_Blanca', 160.0, 380.0, y_out - 0.4, y_out, 60.0, 150.0)
        k_valla(mb, -450.0, y_out + 10.0, -450.0, 125.0)
        k_valla(mb, 450.0, y_out + 10.0, 450.0, 125.0)
        # montaña de arena, bolsas de cemento, carretilla
        cone(mb, 'MI_Tierra', (230.0, -60.0, 0.0), (240.0, -55.0, 70.0), 95.0, 12.0, 14)
        for j in range(6):
            rbox(mb, 'MI_Pintura_Blanca', 330.0 + (j % 3) * 33.0, 40.0 + (j // 3) * 3.0, (j // 3) * 12.0, 30.0, 48.0, 12.0,
                 rng.uniform(-8, 8))
        for (x, y) in ((-460.0, 140.0), (460.0, 140.0), (-470.0, -120.0)):
            k_cono(mb, x, y)
        mb.col(-452.0, 452.0, y_out - 1.0, y_out + 9.0, 0.0, 230.0)
        mb.col(-455.0, -445.0, y_out, 125.0, 0.0, 105.0)
        mb.col(445.0, 455.0, y_out, 125.0, 0.0, 105.0)
        mb.col(140.0, 320.0, -150.0, 30.0, 0.0, 60.0)
    elif kind == 'volquete':
        vq = build_volquete()
        k.merge_mb(mb, vq, (0.0, 15.0, 0.0), rng.uniform(-3, 3))
        for (x, y) in ((-260.0, -110.0), (-240.0, 60.0), (260.0, -100.0), (250.0, 70.0)):
            k_cono(mb, x, y)
        k_valla(mb, -230.0, -130.0, 230.0, -130.0)
        mb.col(-230.0, 230.0, -133.0, -127.0, 0.0, 105.0)
    elif kind == 'puesto':
        # puesto ambulante (carrito con sombrilla y heladera), cubre parte del carril
        cbox(mb, 'MI_Chapa_Gris', -110.0, 110.0, -60.0, 60.0, 30.0, 120.0, 2.0, 'z')
        box(mb, 'MI_Cartel_Rojo', -112.0, 112.0, -61.0, -60.0, 60.0, 100.0)
        for x in (-80.0, 80.0):
            cyl(mb, 'MI_Neumatico', (x, -64.0, 28.0), (x, -54.0, 28.0), 28.0, 14)
            cyl(mb, 'MI_Neumatico', (x, 54.0, 28.0), (x, 64.0, 28.0), 28.0, 14)
        cyl(mb, M_HIERRO, (0.0, 0.0, 120.0), (0.0, 0.0, 250.0), 2.5, 8)
        cone(mb, 'MI_Cartel_Rojo', (0.0, 0.0, 225.0), (0.0, 0.0, 262.0), 150.0, 4.0, 12)
        cbox(mb, 'MI_Pintura_Blanca', 130.0, 190.0, -40.0, 40.0, 0.0, 85.0, 3.0, 'z')
        cbox(mb, 'MI_Cartel_Azul', -190.0, -140.0, -30.0, 30.0, 0.0, 45.0, 2.0, 'z')
        mb.col(-112.0, 192.0, -62.0, 62.0, 0.0, 125.0)
    return mb


# =====================================================================================
# VEHÍCULOS (genéricos, sin marcas)
# =====================================================================================
BODY = 'MI_Auto_Blanco'          # slot de color: se recolorea por instancia con set_material
_V4 = {'plan_ok': True}


def _plan_redondeado(x0, x1, hw_tr, hw_del, r_tr, r_del, n=5):
    """Planta de carrocería (x, y) con esquinas redondeadas y trompa algo más angosta (orden antihorario)."""
    pts = []

    def arco(cx, cy, r, a0, a1):
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    arco(x1 - r_del, -hw_del + r_del, r_del, -math.pi * 0.5, 0.0)
    arco(x1 - r_del, hw_del - r_del, r_del, 0.0, math.pi * 0.5)
    arco(x0 + r_tr, hw_tr - r_tr, r_tr, math.pi * 0.5, math.pi)
    arco(x0 + r_tr, -hw_tr + r_tr, r_tr, math.pi, math.pi * 1.5)
    return pts


def _carroceria(mb, mat, side, hw, front, x0, x1, plan, cuts):
    """Volumen a TRES vistas: lateral ∩ frontal ∩ planta (esquinas redondeadas = biseles en planta), menos los
    pasaruedas. Si la tercera intersección falla, cae a barrio_kit.body_two_views (dos vistas)."""
    if plan and _V4['plan_ok'] and k.F.get('boolean') and k.CAPS.get('boolean_ok', True) and \
            k.CAPS.get('intersect_ok', True):
        a = b = None
        try:
            a = k.new_mesh()
            k.prism(k._One(a), mat, side, 'y', -hw, hw)
            b = k.new_mesh()
            k.prism(k._One(b), mat, front, 'x', x0, x1)
            k.boolean_op(a, b, 'INTERSECTION')
            k.free_mesh(b)
            b = k.new_mesh()
            k.prism(k._One(b), mat, plan, 'z', -50.0, 600.0)
            k.boolean_op(a, b, 'INTERSECTION')
            for (p0, p1, r) in cuts:
                k.free_mesh(b)
                b = k.new_mesh()
                cyl(k._One(b), mat, p0, p1, r, 20)
                k.boolean_op(a, b, 'SUBTRACT')
            if k.tri_count(a) == 0:
                raise RuntimeError('intersección vacía')
            k.append_into(mb.m(mat), a)
            return
        except Exception as e:
            k.err_once('carroceria3', 'Carrocería a tres vistas falló (%s): uso dos vistas' % e)
            _V4['plan_ok'] = False
        finally:
            k.free_mesh(a)
            k.free_mesh(b)
    k.body_two_views(mb, mat, side, -hw, hw, front, x0, x1, cuts)


def _frente(hw, z0, zt, tuck=6.0, hombro=8.0):
    """Perfil frontal (y, z): zócalo metido, costado con caída (tumblehome) y hombro redondeado."""
    zm = z0 + (zt - z0) * 0.55
    return [(-hw + tuck, z0), (hw - tuck, z0), (hw - 1.5, z0 + 10.0), (hw, zm), (hw - 2.0, zt - hombro),
            (hw - hombro, zt), (-hw + hombro, zt), (-hw + 2.0, zt - hombro), (-hw, zm), (-hw + 1.5, z0 + 10.0)]


def _rueda(mb, x, s, y_in, y_out, r):
    """Neumático con flancos achaflanados, llanta hundida de chapa, tapa y 4 bulones."""
    ch = min(3.0, (y_out - y_in) * 0.2)
    cyl(mb, 'MI_Neumatico', (x, s * (y_in + ch), r), (x, s * (y_out - ch), r), r, 22)
    cone(mb, 'MI_Neumatico', (x, s * (y_out - ch), r), (x, s * y_out, r), r, r * 0.88, 22)
    cone(mb, 'MI_Neumatico', (x, s * (y_in + ch), r), (x, s * y_in, r), r, r * 0.88, 22)
    cyl(mb, 'MI_Chapa_Gris', (x, s * (y_out - 0.5), r), (x, s * (y_out + 0.3), r), r * 0.6, 18)
    cyl(mb, M_HIERRO, (x, s * (y_out + 0.3), r), (x, s * (y_out + 0.5), r), r * 0.5, 18)     # sombra del rayo
    cone(mb, 'MI_Chapa_Gris', (x, s * (y_out + 0.5), r), (x, s * (y_out + 1.8), r), r * 0.3, r * 0.2, 14)
    for j in range(4):
        a = j * math.pi * 0.5 + 0.4
        cyl(mb, M_HIERRO, (x + math.cos(a) * r * 0.25, s * (y_out + 1.6), r + math.sin(a) * r * 0.25),
            (x + math.cos(a) * r * 0.25, s * (y_out + 2.4), r + math.sin(a) * r * 0.25), 1.1, 6)


def _wheels(mb, xs, y_in, y_out, r, rim=0.62):
    for x in xs:
        for s in (-1.0, 1.0):
            _rueda(mb, x, s, y_in, y_out, r)


def _pasaruedas(mb, xs, hw, r, mat=BODY):
    """Fondo oscuro del pasaruedas (tapa el túnel del booleano) + labio del guardabarros."""
    for x in xs:
        cyl(mb, 'MI_Plastico_Negro', (x, -(hw - 24.0), r), (x, hw - 24.0, r), r + 4.2, 20)
        for s in (-1.0, 1.0):
            pts = []
            for i in range(9):
                a = math.radians(10.0 + 160.0 * i / 8.0)
                pts.append((x + math.cos(a) * (r + 5.6), s * (hw - 0.8), r + math.sin(a) * (r + 5.6)))
            tube(mb, mat, pts, 1.7, 6)


def _opticas(mb, xf, xr, hw, zl, zt):
    """Faros (carcasa cromada + lente MI_Vidrio + giro ámbar), traseros con luz de retroceso, patentes lisas."""
    for s in (-1.0, 1.0):
        cbox(mb, 'MI_Chapa_Gris', xf - 9.0, xf - 1.0, s * (hw - 34.0), s * (hw - 9.0), zl, zl + 12.0, 1.5, 'y')
        cbox(mb, 'MI_Vidrio', xf - 1.0, xf + 0.8, s * (hw - 33.0), s * (hw - 10.0), zl + 0.8, zl + 11.2, 1.5, 'y')
        box(mb, 'MI_Pintura_Amarilla', xf - 6.0, xf + 0.5, s * (hw - 9.0), s * (hw - 4.0), zl + 2.0, zl + 9.0)
        cbox(mb, 'MI_Cartel_Rojo', xr - 1.0, xr + 6.0, s * (hw - 31.0), s * (hw - 5.0), zt, zt + 13.0, 1.5, 'y')
        box(mb, 'MI_Pintura_Blanca', xr - 1.5, xr + 1.0, s * (hw - 30.0), s * (hw - 23.0), zt + 1.5, zt + 6.0)
        box(mb, 'MI_Pintura_Amarilla', xr - 1.5, xr + 1.0, s * (hw - 13.0), s * (hw - 7.0), zt + 7.0, zt + 11.5)
    # patentes genéricas (blancas con franja azul, sin caracteres)
    for (xa, xb, z) in ((xf + 2.6, xf + 3.2, zl - 26.0), (xr - 3.2, xr - 2.6, zt - 22.0)):
        box(mb, 'MI_Pintura_Blanca', xa, xb, -20.0, 20.0, z, z + 13.0)
        box(mb, 'MI_Cartel_Azul', xa - 0.1, xb + 0.1, -20.0, 20.0, z + 10.0, z + 13.0)


def _paragolpes(mb, x_ext, sgn, hw, z0, z1):
    """Paragolpes envolvente: frente + retornos laterales de 30 cm (plástico negro texturado)."""
    xi = x_ext - sgn * 12.0
    cbox(mb, 'MI_Plastico_Negro', min(x_ext, xi), max(x_ext, xi), -hw + 6.0, hw - 6.0, z0, z1, 3.5, 'y')
    for s in (-1.0, 1.0):
        xa = x_ext - sgn * 36.0
        cbox(mb, 'MI_Plastico_Negro', min(xa, x_ext - sgn * 4.0), max(xa, x_ext - sgn * 4.0),
             s * (hw - 9.0), s * (hw + 0.8), z0, z1, 2.5, 'x')
    box(mb, 'MI_Plastico_Negro', min(x_ext, xi), max(x_ext, xi), -hw * 0.4, hw * 0.4, z0 - 6.0, z0)   # spoiler


def _lights(mb, xf, xr, half_w, zl, zt):
    for s in (-1.0, 1.0):
        cbox(mb, 'MI_Pintura_Blanca', xf - 6.0, xf + 1.0, s * (half_w - 32.0), s * (half_w - 8.0), zl, zl + 11.0, 1.2, 'y')
        cbox(mb, 'MI_Cartel_Rojo', xr - 1.0, xr + 5.0, s * (half_w - 30.0), s * (half_w - 6.0), zt, zt + 13.0, 1.2, 'y')
    box(mb, 'MI_Pintura_Blanca', xf + 0.5, xf + 2.0, -20.0, 20.0, zl - 22.0, zl - 10.0)
    box(mb, 'MI_Pintura_Blanca', xr - 2.0, xr - 0.5, -20.0, 20.0, zt - 18.0, zt - 6.0)


def build_auto(t):
    """Auto genérico (sin marcas), v4: carrocería a TRES vistas (lateral ∩ frontal con caída ∩ planta con esquinas
    redondeadas), pasaruedas con fondo oscuro y labio, habitáculo MI_Vidrio con burletes negros, techo y parantes
    del color de la carrocería, paragolpes envolventes, faros con carcasa y lente, traseros con retroceso,
    patentes lisas, espejos, manijas, ruedas con flanco y llanta. Colisión: UNA caja."""
    mb = MB('Auto_' + t)
    hw = 88.0
    if t in ('sedan', 'patrullero'):
        Lh, wx, r = 228.0, 132.0, 31.0
        side = [(-225.0, 30.0), (-222.0, 22.0), (222.0, 22.0), (226.0, 30.0), (228.0, 55.0), (220.0, 72.0), (150.0, 84.0),
                (75.0, 92.0), (-140.0, 95.0), (-210.0, 92.0), (-226.0, 78.0), (-228.0, 55.0)]
        gh = [(76.0, 91.0), (20.0, 137.0), (-95.0, 140.0), (-150.0, 100.0), (-157.0, 93.0)]
        roof = [(28.0, 132.0), (18.0, 143.0), (-100.0, 146.0), (-112.0, 135.0)]
        a_p, c_p, b_x = ((74.0, 92.0), (19.0, 138.0)), ((-152.0, 96.0), (-100.0, 139.0)), -40.0
        top = 140.0
    elif t == 'hatch':
        Lh, wx, r = 196.0, 120.0, 30.0
        side = [(-195.0, 30.0), (-192.0, 22.0), (192.0, 22.0), (196.0, 30.0), (198.0, 55.0), (190.0, 70.0), (130.0, 82.0),
                (60.0, 90.0), (-175.0, 96.0), (-195.0, 90.0), (-197.0, 55.0)]
        gh = [(62.0, 89.0), (10.0, 136.0), (-148.0, 139.0), (-186.0, 99.0), (-188.0, 94.0)]
        roof = [(18.0, 131.0), (8.0, 142.0), (-150.0, 145.0), (-160.0, 134.0)]
        a_p, c_p, b_x = ((60.0, 90.0), (9.0, 137.0)), ((-184.0, 98.0), (-150.0, 139.0)), -55.0
        top = 140.0
    elif t == 'utilitario':
        Lh, wx, r = 212.0, 135.0, 30.0
        side = [(-210.0, 28.0), (-207.0, 20.0), (207.0, 20.0), (211.0, 28.0), (213.0, 55.0), (205.0, 75.0), (150.0, 92.0),
                (96.0, 101.0), (-208.0, 104.0), (-211.0, 80.0)]
        gh = [(96.0, 100.0), (44.0, 163.0), (24.0, 165.0), (24.0, 100.0)]
        roof = None
        a_p, c_p, b_x = ((95.0, 101.0), (43.0, 164.0)), None, None
        top = 184.0
    else:   # pickup
        Lh, wx, r = 262.0, 160.0, 33.0
        side = [(-260.0, 30.0), (-257.0, 24.0), (257.0, 24.0), (261.0, 30.0), (263.0, 60.0), (255.0, 80.0), (180.0, 95.0),
                (-258.0, 98.0), (-261.0, 60.0)]
        gh = [(112.0, 95.0), (62.0, 148.0), (-62.0, 151.0), (-72.0, 96.0)]
        roof = [(70.0, 143.0), (62.0, 154.0), (-66.0, 156.0), (-74.0, 145.0)]
        a_p, c_p, b_x = ((110.0, 96.0), (60.0, 149.0)), ((-70.0, 97.0), (-64.0, 150.0)), None
        top = 156.0
    zt_body = max(p[1] for p in side) + 1.0
    front = _frente(hw, 18.0, zt_body)
    plan = _plan_redondeado(-Lh - 4.0, Lh + 4.0, hw, hw - 5.0, 26.0, 38.0)
    cuts = [((x, -120.0, r), (x, 120.0, r), r + 4.5) for x in (-wx, wx)]
    _carroceria(mb, BODY, side, hw, front, -Lh - 5.0, Lh + 5.0, plan, cuts)
    _pasaruedas(mb, (-wx, wx), hw, r)
    # habitáculo (vidrio oscuro opaco, convención v2) con planta redondeada y caída hacia el techo
    gx0 = min(p[0] for p in gh) - 2.0
    gx1 = max(p[0] for p in gh) + 2.0
    zg0 = min(p[1] for p in gh)
    zg1 = max(p[1] for p in gh)
    gfront = [(-hw + 4.0, zg0 - 2.0), (hw - 4.0, zg0 - 2.0), (hw - 18.0, zg1 + 1.0), (-hw + 18.0, zg1 + 1.0)]
    gplan = _plan_redondeado(gx0 - 2.0, gx1 + 2.0, hw - 3.0, hw - 6.0, 18.0, 24.0)
    _carroceria(mb, 'MI_Vidrio', gh, hw, gfront, gx0, gx1, gplan, [])
    # burletes: línea de cintura negra a lo largo de la base de los vidrios
    for s in (-1.0, 1.0):
        box(mb, 'MI_Plastico_Negro', gx0 + 8.0, gx1 - 6.0, s * (hw - 4.6), s * (hw - 3.4), zg0 - 1.0, zg0 + 1.8)
    if t == 'utilitario':
        # caja de carga cerrada (chapa del color de la carrocería) detrás de la cabina
        up_side = [(-209.0, 100.0), (26.0, 100.0), (26.0, 182.0), (-200.0, 184.0), (-209.0, 176.0)]
        up_front = [(-hw + 1.0, 100.0), (hw - 1.0, 100.0), (hw - 6.0, 184.0), (-hw + 6.0, 184.0)]
        uplan = _plan_redondeado(-212.0, 30.0, hw - 1.0, hw - 1.0, 10.0, 4.0)
        _carroceria(mb, BODY, up_side, hw, up_front, -212.0, 30.0, uplan, [])
        cbox(mb, BODY, 20.0, 50.0, -hw + 8.0, hw - 8.0, 160.0, 168.0, 2.0, 'y')
        for s in (-1.0, 1.0):
            box(mb, 'MI_Vidrio', 30.0, 88.0, s * (hw - 6.0) - 0.4, s * (hw - 6.0) + 0.4, 108.0, 150.0)
            box(mb, 'MI_Plastico_Negro', -90.0, -88.5, s * hw - 0.3, s * hw + 0.3, 30.0, 175.0)
            for xr_ in (-150.0, -30.0):                     # nervaduras de la caja
                box(mb, BODY, xr_ - 2.0, xr_ + 2.0, s * (hw - 0.5), s * (hw + 0.6), 104.0, 176.0)
    if roof:
        rfront = [(-hw + 12.0, roof[0][1]), (hw - 12.0, roof[0][1]), (hw - 19.0, top + 6.0), (-hw + 19.0, top + 6.0)]
        rx0, rx1 = min(p[0] for p in roof) - 1.0, max(p[0] for p in roof) + 1.0
        rplan = _plan_redondeado(rx0 - 1.0, rx1 + 1.0, hw - 12.0, hw - 14.0, 14.0, 14.0)
        _carroceria(mb, BODY, roof, hw, rfront, rx0, rx1, rplan, [])
    for s in (-1.0, 1.0):
        if a_p:
            (p0, p1) = a_p
            cyl(mb, BODY, (p0[0], s * (hw - 5.0), p0[1]), (p1[0], s * (hw - 18.0), p1[1]), 3.2, 10)
        if c_p:
            (p0, p1) = c_p
            cyl(mb, BODY, (p0[0], s * (hw - 5.0), p0[1]), (p1[0], s * (hw - 18.0), p1[1]), 5.0, 10)
        if b_x is not None:
            box(mb, 'MI_Plastico_Negro', b_x - 4.0, b_x + 4.0, s * (hw - 14.0) - 2.0, s * (hw - 6.0) + 2.0, zg0, zg1 - 3.0)
        # espejo (pie negro + carcasa color), manijas, líneas de puertas
        ax = a_p[0][0]
        box(mb, 'MI_Plastico_Negro', ax - 14.0, ax - 8.0, s * (hw - 2.0), s * (hw + 4.0), a_p[0][1] - 1.0, a_p[0][1] + 4.0)
        cbox(mb, BODY, ax - 18.0, ax - 6.0, s * (hw + 3.0), s * (hw + 14.0), a_p[0][1] + 1.0, a_p[0][1] + 12.0, 2.0, 'y')
        box(mb, 'MI_Vidrio', ax - 6.4, ax - 5.8, s * (hw + 4.0), s * (hw + 13.0), a_p[0][1] + 2.0, a_p[0][1] + 11.0)
        for xd in (10.0, -90.0):
            cbox(mb, 'MI_Plastico_Negro', xd - 8.0, xd + 8.0, s * hw - 0.8, s * hw + 0.9, 77.0, 81.5, 1.0, 'x')
        for xd in (45.0, -45.0, -140.0):
            if -Lh + 30.0 < xd < Lh - 60.0:
                box(mb, 'MI_Plastico_Negro', xd - 0.4, xd + 0.4, s * hw - 0.2, s * hw + 0.3, 32.0, zg0 - 1.0)
        # zócalo lateral oscuro y moldura
        box(mb, 'MI_Plastico_Negro', -Lh + 48.0, Lh - 48.0, s * (hw - 7.0), s * (hw - 5.0), 20.0, 29.0)
        box(mb, 'MI_Plastico_Negro', -wx + r + 8.0, wx - r - 8.0, s * hw - 0.4, s * hw + 0.6, 46.0, 50.0)
    # paragolpes, parrilla, ópticas
    _paragolpes(mb, Lh + 5.0, 1.0, hw, 24.0, 46.0)
    _paragolpes(mb, -Lh - 5.0, -1.0, hw, 24.0, 46.0)
    cbox(mb, 'MI_Plastico_Negro', Lh - 2.0, Lh + 2.5, -38.0, 38.0, 48.0, 64.0, 1.5, 'y')
    for z in (52.0, 57.0, 62.0):
        box(mb, 'MI_Chapa_Gris', Lh + 2.5, Lh + 3.0, -36.0, 36.0, z - 0.6, z + 0.6)
    _opticas(mb, Lh + 1.0, -Lh - 1.0, hw, 56.0, 64.0)
    box(mb, 'MI_Plastico_Negro', -Lh + 30.0, Lh - 30.0, -hw + 10.0, hw - 10.0, 14.0, 23.0)
    _wheels(mb, (-wx, wx), hw - 22.0, hw - 2.0, r)
    if t == 'pickup':
        # caja abierta
        for s in (-1.0, 1.0):
            cbox(mb, BODY, -258.0, -80.0, s * hw - (4.0 if s > 0 else -4.0), s * hw, 98.0, 140.0, 1.0, 'x')
        cbox(mb, BODY, -261.0, -255.0, -hw, hw, 60.0, 140.0, 1.0, 'y')
        cbox(mb, BODY, -84.0, -78.0, -hw, hw, 98.0, 142.0, 1.0, 'y')
        box(mb, 'MI_Plastico_Negro', -255.0, -84.0, -hw + 4.0, hw - 4.0, 96.0, 99.0)
    if t == 'patrullero':
        cbox(mb, 'MI_Plastico_Negro', -45.0, 5.0, -62.0, 62.0, top + 4.0, top + 12.0, 1.5, 'y')
        for (s, m) in ((-1.0, 'MI_Emisivo_Baliza_Roja'), (1.0, 'MI_Emisivo_Baliza_Azul')):
            cbox(mb, m, -40.0, 0.0, s * 8.0, s * 58.0, top + 11.0, top + 19.0, 2.0, 'y')
        for s in (-1.0, 1.0):
            box(mb, 'MI_Comisaria_Azul', -Lh + 20.0, Lh - 20.0, s * hw - 0.4, s * hw + 0.4, 60.0, 74.0)
            box(mb, 'MI_Pintura_Blanca', -60.0, 20.0, s * hw - 0.5, s * hw + 0.5, 63.0, 71.0)
        box(mb, 'MI_Comisaria_Azul', -110.0, 10.0, -hw + 20.0, hw - 20.0, top + 0.5, top + 1.5)
    mb.col(-Lh, Lh, -hw, hw, 0.0, top)
    return mb


def build_moto():
    """Moto de baja cilindrada genérica (110 cc "cub"/underbone, sin marcas), +X adelante, apoyada en el
    pie lateral (izquierdo, -Y). Al instanciar: rot = R(roll=-6, yaw=...) para que quede inclinada sobre el pie.
    Carenado en BODY (slot recoloreable con swaps como los autos). Colisión: una caja."""
    mb = MB('Moto')
    R_, wb = 29.0, 61.0
    for x in (wb, -wb):
        cyl(mb, 'MI_Neumatico', (x, -3.2, R_), (x, 3.2, R_), R_, 24)
        for s in (-1.0, 1.0):
            cone(mb, 'MI_Neumatico', (x, s * 3.2, R_), (x, s * 4.4, R_), R_ - 0.6, R_ - 4.5, 24)
        cyl(mb, 'MI_Chapa_Gris', (x, -4.6, R_), (x, 4.6, R_), R_ - 7.0, 20)        # llanta
        cyl(mb, M_HIERRO, (x, -4.8, R_), (x, 4.8, R_), R_ - 9.0, 20)               # fondo de llanta
        cyl(mb, 'MI_Chapa_Gris', (x, -6.5, R_), (x, 6.5, R_), 5.5, 12)             # maza
        for j in range(5):                                                          # rayos de aleación
            a = j * 2.0 * math.pi / 5.0
            p = (x + math.cos(a) * (R_ - 8.5), 0.0, R_ + math.sin(a) * (R_ - 8.5))
            cyl(mb, 'MI_Chapa_Gris', (x, 0.0, R_), p, 1.6, 6)
    cyl(mb, 'MI_Chapa_Gris', (wb, 0.0, R_), (wb + 1.0, 6.0, R_ + 1.0), 6.5, 12)      # disco/campana
    # horquilla y manubrio
    for s in (-1.0, 1.0):
        cyl(mb, 'MI_Chapa_Gris', (wb, s * 7.0, R_), (wb - 20.0, s * 7.0, 86.0), 1.9, 10)
        cyl(mb, M_HIERRO, (wb - 8.0, s * 7.0, 52.0), (wb - 20.0, s * 7.0, 86.0), 2.4, 10)
    tube(mb, M_HIERRO, [(wb - 22.0, -34.0, 101.0), (wb - 19.0, -14.0, 97.0), (wb - 19.0, 14.0, 97.0),
                        (wb - 22.0, 34.0, 101.0)], 1.3, 8)
    for s in (-1.0, 1.0):
        cyl(mb, 'MI_Plastico_Negro', (wb - 22.0, s * 26.0, 100.0), (wb - 22.5, s * 36.0, 101.5), 1.9, 8)   # puños
        cyl(mb, M_HIERRO, (wb - 20.0, s * 18.0, 99.0), (wb - 23.0, s * 21.0, 118.0), 0.6, 5)             # espejos
        blob(mb, 'MI_Plastico_Negro', (wb - 23.5, s * 21.5, 120.0), 2.0, 6.0, 4.0, steps=(6, 10))
    # óptica delantera + tablero (carenado de manubrio)
    blob(mb, BODY, (wb - 16.0, 0.0, 95.0), 12.0, 17.0, 9.0, steps=(8, 12))
    cbox(mb, 'MI_Chapa_Gris', wb - 7.0, wb - 3.0, -7.0, 7.0, 86.0, 96.0, 1.5, 'x')
    cbox(mb, 'MI_Vidrio', wb - 3.0, wb - 2.2, -6.0, 6.0, 87.0, 95.0, 1.2, 'x')
    for s in (-1.0, 1.0):
        box(mb, 'MI_Pintura_Amarilla', wb - 10.0, wb - 5.0, s * 13.0 - 2.0, s * 13.0 + 2.0, 90.0, 93.0)
    # guardabarros delantero
    tube(mb, BODY, [(wb + math.cos(math.radians(a)) * (R_ + 4.0), 0.0, R_ + math.sin(math.radians(a)) * (R_ + 4.0))
                    for a in range(10, 131, 20)], 4.5, 8)
    # escudo (legshield), túnel, piso y tapas laterales: el chasis "underbone" tapado
    prism(mb, BODY, [(28.0, 34.0), (40.0, 34.0), (wb - 14.0, 84.0), (wb - 22.0, 90.0), (32.0, 60.0)], 'y', -18.0, 18.0)
    box(mb, 'MI_Plastico_Negro', -6.0, 30.0, -15.0, 15.0, 30.0, 35.0)
    prism(mb, BODY, [(-8.0, 34.0), (6.0, 40.0), (6.0, 52.0), (-28.0, 70.0), (-82.0, 72.0), (-92.0, 64.0),
                     (-70.0, 50.0), (-30.0, 40.0)], 'y', -15.0, 15.0)
    cbox(mb, 'MI_Plastico_Negro', -84.0, -18.0, -13.5, 13.5, 71.0, 81.0, 4.0, 'x')                       # asiento
    cbox(mb, M_HIERRO, -100.0, -70.0, -11.0, 11.0, 72.0, 74.5, 1.0, 'x')                                  # parrilla
    cbox(mb, 'MI_Cartel_Rojo', -95.0, -90.0, -6.0, 6.0, 64.0, 70.0, 1.0, 'y')                             # trasero
    box(mb, 'MI_Pintura_Blanca', -97.0, -96.4, -9.0, 9.0, 47.0, 58.0)                                     # patente lisa
    box(mb, 'MI_Cartel_Azul', -97.1, -96.3, -9.0, 9.0, 55.5, 58.0)
    tube(mb, BODY, [(-wb + math.cos(math.radians(a)) * (R_ + 4.0), 0.0, R_ + math.sin(math.radians(a)) * (R_ + 4.0))
                    for a in range(60, 171, 20)], 4.0, 8)
    # motor, cilindro horizontal, escape, basculante, amortiguadores, pie
    cbox(mb, M_HIERRO, -12.0, 20.0, -12.0, 12.0, 14.0, 38.0, 3.0, 'y')
    cyl(mb, 'MI_Chapa_Gris', (18.0, 0.0, 30.0), (34.0, 0.0, 26.0), 7.0, 12)
    tube(mb, 'MI_Chapa_Gris', [(30.0, 3.0, 22.0), (20.0, 9.0, 13.0), (-20.0, 12.0, 14.0), (-45.0, 13.0, 24.0)], 2.2, 8)
    cyl(mb, 'MI_Chapa_Gris', (-42.0, 13.5, 23.0), (-84.0, 13.5, 36.0), 4.6, 12)
    for s in (-1.0, 1.0):
        cyl(mb, M_HIERRO, (-6.0, s * 8.0, 30.0), (-wb, s * 8.0, R_), 2.2, 8)
        cyl(mb, 'MI_Chapa_Gris', (-wb + 6.0, s * 10.5, R_ + 6.0), (-74.0, s * 10.5, 66.0), 2.2, 8)
    cyl(mb, M_HIERRO, (-10.0, -12.0, 18.0), (-14.0, -30.0, 1.0), 1.2, 6)
    cyl(mb, M_HIERRO, (16.0, -16.0, 22.0), (8.0, -26.0, 22.0), 0.9, 6)                                    # pedalín
    cyl(mb, M_HIERRO, (16.0, 16.0, 22.0), (8.0, 26.0, 22.0), 0.9, 6)
    mb.col(-98.0, wb + R_, -18.0, 18.0, 0.0, 100.0)
    return mb


def build_camion():
    """Camión de reparto de caja cerrada (estacionado: corta la visual de la calle)."""
    mb = MB('Camion')
    hw = 122.0
    side = [(230.0, 45.0), (405.0, 45.0), (410.0, 120.0), (400.0, 215.0), (360.0, 290.0), (230.0, 295.0)]
    front = [(-hw, 45.0), (hw, 45.0), (hw, 260.0), (hw - 8.0, 295.0), (-hw + 8.0, 295.0), (-hw, 260.0)]
    k.body_two_views(mb, BODY, side, -hw, hw, front, 225.0, 412.0, [((330.0, -150.0, 48.0), (330.0, 150.0, 48.0), 54.0)])
    k.body_two_views(mb, 'MI_Vidrio', [(398.0, 205.0), (402.0, 210.0), (365.0, 282.0), (300.0, 284.0), (300.0, 205.0)],
                     -hw + 4.0, hw - 4.0, [(-hw + 3.0, 200.0), (hw - 3.0, 200.0), (hw - 6.0, 286.0), (-hw + 6.0, 286.0)],
                     295.0, 406.0)
    cbox(mb, 'MI_Pintura_Blanca', -430.0, 222.0, -hw - 3.0, hw + 3.0, 70.0, 360.0, 3.0, 'x')
    box(mb, 'MI_Cartel_Azul', -400.0, 190.0, -hw - 3.4, -hw - 3.0, 90.0, 150.0)
    box(mb, 'MI_Cartel_Azul', -400.0, 190.0, hw + 3.0, hw + 3.4, 90.0, 150.0)
    box(mb, M_HIERRO, -430.0, 410.0, -70.0, 70.0, 40.0, 70.0)
    box(mb, 'MI_Plastico_Negro', 400.0, 418.0, -hw, hw, 40.0, 70.0)
    _lights(mb, 410.0, -432.0, hw, 95.0, 80.0)
    for s in (-1.0, 1.0):
        cbox(mb, M_HIERRO, 380.0, 395.0, s * hw, s * (hw + 22.0), 230.0, 262.0, 1.5, 'y')
    _wheels(mb, (330.0,), hw - 30.0, hw - 2.0, 48.0)
    _wheels(mb, (-230.0, -330.0), hw - 50.0, hw - 2.0, 48.0)
    mb.col(-432.0, 412.0, -hw - 3.0, hw + 3.0, 0.0, 360.0)
    return mb


def build_colectivo():
    """Colectivo urbano genérico (sin líneas ni marcas)."""
    mb = MB('Colectivo')
    hw = 128.0
    side = [(-600.0, 30.0), (590.0, 30.0), (602.0, 60.0), (604.0, 250.0), (595.0, 300.0), (-596.0, 305.0), (-602.0, 280.0)]
    front = [(-hw, 30.0), (hw, 30.0), (hw, 290.0), (hw - 10.0, 308.0), (-hw + 10.0, 308.0), (-hw, 290.0)]
    cuts = [((x, -160.0, 50.0), (x, 160.0, 50.0), 56.0) for x in (-330.0, 380.0)]
    k.body_two_views(mb, BODY, side, -hw, hw, front, -605.0, 606.0, cuts)
    for s in (-1.0, 1.0):
        box(mb, 'MI_Vidrio', -560.0, 560.0, s * hw - 0.8, s * hw + 0.8, 145.0, 262.0)
        x = -560.0
        while x < 560.0:
            box(mb, M_HIERRO, x - 3.0, x + 3.0, s * hw - 1.2, s * hw + 1.2, 145.0, 262.0)
            x += 140.0
        box(mb, 'MI_Cartel_Rojo', -600.0, 600.0, s * hw - 0.6, s * hw + 0.6, 95.0, 125.0)
        box(mb, 'MI_Cartel_Azul', -600.0, 600.0, s * hw - 0.6, s * hw + 0.6, 268.0, 280.0)
    box(mb, 'MI_Vidrio', 598.0, 606.0, -hw + 8.0, hw - 8.0, 120.0, 262.0)
    box(mb, 'MI_Plastico_Negro', 602.0, 607.0, -90.0, 90.0, 266.0, 292.0)
    box(mb, 'MI_Emisivo_Calido', 607.0, 607.5, -80.0, 80.0, 272.0, 286.0)
    box(mb, 'MI_Vidrio', -606.0, -598.0, -hw + 15.0, hw - 15.0, 170.0, 260.0)
    # puertas (hojas oscuras)
    for (x0, x1) in ((470.0, 580.0), (-40.0, 70.0)):
        box(mb, 'MI_Plastico_Negro', x0, x1, -hw - 1.6, -hw - 0.8, 35.0, 262.0)
    cbox(mb, 'MI_Plastico_Negro', 598.0, 612.0, -hw + 2.0, hw - 2.0, 30.0, 58.0, 3.0, 'y')
    cbox(mb, 'MI_Plastico_Negro', -612.0, -598.0, -hw + 2.0, hw - 2.0, 30.0, 58.0, 3.0, 'y')
    _lights(mb, 605.0, -606.0, hw, 70.0, 80.0)
    cbox(mb, 'MI_Chapa_Gris', -300.0, 100.0, -70.0, 70.0, 305.0, 330.0, 4.0, 'x')
    for s in (-1.0, 1.0):
        cbox(mb, M_HIERRO, 590.0, 600.0, s * hw, s * (hw + 20.0), 230.0, 255.0, 1.5, 'y')
    _wheels(mb, (380.0,), hw - 30.0, hw - 2.0, 50.0)
    _wheels(mb, (-330.0,), hw - 55.0, hw - 2.0, 50.0)
    mb.col(-606.0, 606.0, -hw, hw, 0.0, 308.0)
    return mb


def build_formacion():
    """Dos coches de tren de pasajeros acoplados (4000 cm), detenidos: cierran la vía en los extremos."""
    mb = MB('Formacion')
    hw = 150.0
    for (x0, x1) in ((-2000.0, -10.0), (10.0, 2000.0)):
        cbox(mb, 'MI_Pintura_Blanca', x0, x1, -hw, hw, 95.0, 395.0, 8.0, 'x')
        prism(mb, 'MI_Chapa_Gris', [(-hw + 10.0, 395.0), (hw - 10.0, 395.0), (hw - 40.0, 420.0), (-hw + 40.0, 420.0)], 'x',
              x0 + 20.0, x1 - 20.0)
        for s in (-1.0, 1.0):
            box(mb, 'MI_Cartel_Azul', x0, x1, s * hw - 0.6, s * hw + 0.6, 120.0, 165.0)
            box(mb, 'MI_Vidrio', x0 + 60.0, x1 - 60.0, s * hw - 0.8, s * hw + 0.8, 215.0, 300.0)
            x = x0 + 60.0
            while x < x1 - 60.0:
                box(mb, 'MI_Pintura_Blanca', x - 6.0, x + 6.0, s * hw - 1.2, s * hw + 1.2, 215.0, 300.0)
                x += 160.0
            for xd in (x0 + 450.0, x1 - 450.0):
                box(mb, 'MI_Chapa_Gris', xd - 70.0, xd + 70.0, s * hw - 1.6, s * hw + 1.6, 100.0, 340.0)
        # bogies y faldón hasta el riel (no se pasa por abajo)
        for xb in (x0 + 300.0, x1 - 300.0):
            box(mb, M_HIERRO, xb - 140.0, xb + 140.0, -hw + 20.0, hw - 20.0, 45.0, 95.0)
            for xw in (xb - 90.0, xb + 90.0):
                cyl(mb, M_HIERRO, (xw, -95.0, 48.0 + 45.0), (xw, 95.0, 48.0 + 45.0), 46.0, 14)
        box(mb, M_HIERRO, x0 + 450.0, x1 - 450.0, -hw + 15.0, hw - 15.0, 30.0, 100.0)
    box(mb, M_HIERRO, -12.0, 12.0, -60.0, 60.0, 120.0, 330.0)
    mb.col(-2000.0, 2000.0, -hw, hw, 0.0, 420.0)
    return mb


# =====================================================================================
# REJA DE PUERTA, REFUGIO, CONO
# =====================================================================================
def build_reja_puerta():
    """Reja de seguridad delante de una puerta (100 x 220, se escala por instancia) con candado.
    Marco: x = espesor hacia la calle (0..4), y centrado, z desde el umbral."""
    mb = MB('RejaPuerta')
    k.k_reja_plano(mb, M_HIERRO, 0.5, -50.0, 50.0, 0.0, 220.0, axis='y', spacing=11.0, bar=1.6, frame=3.0,
                   rails=(70.0, 150.0))
    for z in (30.0, 190.0):
        cyl(mb, M_HIERRO, (2.0, -51.5, z - 6.0), (2.0, -51.5, z + 6.0), 1.5, 8)
    box(mb, M_HIERRO, 0.0, 6.0, 40.0, 49.0, 100.0, 112.0)
    cbox(mb, 'MI_Chapa_Gris', 4.0, 7.5, 41.0, 49.0, 88.0, 99.0, 0.6, 'z')
    torus(mb, 'MI_Chapa_Gris', (5.8, 45.0, 101.5), 3.0, 0.6, (1, 0, 0), 10, 4)
    return mb


def build_parada():
    """Refugio de colectivo (frente hacia +X, largo a lo largo de Y)."""
    mb = MB('Parada')
    for y in (-150.0, 150.0):
        box(mb, M_HIERRO, -70.0, -64.0, y - 3.0, y + 3.0, 0.0, 250.0)
        box(mb, M_HIERRO, 40.0, 46.0, y - 3.0, y + 3.0, 0.0, 250.0)
    prism(mb, 'MI_Chapa_Gris', [(-85.0, 250.0), (70.0, 258.0), (70.0, 263.0), (-85.0, 256.0)], 'y', -170.0, 170.0)
    box(mb, 'MI_Vidrio', -68.0, -66.5, -147.0, 147.0, 40.0, 230.0)
    box(mb, M_HIERRO, -68.5, -66.0, -147.0, 147.0, 120.0, 124.0)
    for y in (-150.0, 150.0):
        box(mb, 'MI_Vidrio', -64.0, 40.0, y - 0.7, y + 0.7, 40.0, 230.0)
    cbox(mb, 'MI_Madera', -60.0, -25.0, -120.0, 120.0, 45.0, 50.0, 1.0, 'y')
    for y in (-110.0, 110.0):
        box(mb, M_HIERRO, -50.0, -40.0, y - 2.0, y + 2.0, 0.0, 45.0)
    # poste con cartel en blanco (sin línea ni texto)
    cyl(mb, M_HIERRO, (60.0, 200.0, 0.0), (60.0, 200.0, 290.0), 3.0, 8)
    cbox(mb, 'MI_Cartel_Azul', 57.0, 63.0, 175.0, 225.0, 230.0, 285.0, 1.0, 'z')
    box(mb, 'MI_Cartel_Blanco', 63.0, 63.4, 180.0, 220.0, 240.0, 275.0)
    mb.col(-70.0, -64.0, -150.0, 150.0, 0.0, 250.0)
    mb.col(-60.0, -25.0, -120.0, 120.0, 0.0, 50.0)
    return mb


def build_bolsas_pila():
    mb = MB('Bolsas')
    rng = random.Random(9)
    for j in range(4):
        r = rng.uniform(16.0, 23.0)
        blob(mb, 'MI_Plastico_Negro', (rng.uniform(-30, 30), rng.uniform(-25, 25), r * 0.8), r, r * 0.9, r,
             yaw=rng.uniform(0, 180), pitch=rng.uniform(-15, 15), steps=(7, 10))
    return mb


# =====================================================================================
# v5: ARCO DECORATIVO DE LA CALLE COMERCIAL (tipo 3 de Febrero)
# =====================================================================================
def build_arco_comercial(ancho):
    """Arco de caño que cruza la calle comercial de vereda a vereda, con dos guirnaldas de lamparitas en
    catenaria (MI_Emisivo_Calido: apagadas de día, encendidas de noche) y una estrella de caño en la clave.
    Origen en el centro de la calle a nivel calzada (Z=0); el arco está en el plano XZ y cruza a lo largo de X
    (build_barrio lo rota 90° para las calles E-O). Columnas en x = ±ancho/2 apoyadas en la vereda.
    Altura libre mínima de las guirnaldas: 5,4 m. Colisión: solo las columnas."""
    mb = MB('ArcoComercial')
    a = 0.5 * ancho
    h0, apex = 650.0, 800.0
    n = 18

    def arc_z(x, top=apex, base=h0):
        t = (x + a) / (2.0 * a)
        return base + (top - base) * (1.0 - (2.0 * t - 1.0) ** 2)
    # columnas con base, anillos y remate
    for sx in (-1.0, 1.0):
        x = sx * a
        box(mb, 'MI_Hormigon', x - 18.0, x + 18.0, -18.0, 18.0, Z_VER - 1.0, Z_VER + 6.0)
        box(mb, M_HIERRO, x - 12.0, x + 12.0, -12.0, 12.0, Z_VER + 6.0, Z_VER + 7.5)
        cyl(mb, M_HIERRO, (x, 0.0, Z_VER + 7.0), (x, 0.0, h0 + 10.0), 5.0, 12)
        for zz in (Z_VER + 40.0, 250.0):
            cyl(mb, M_HIERRO, (x, 0.0, zz), (x, 0.0, zz + 6.0), 6.6, 12)
        mb.col(x - 9.0, x + 9.0, -9.0, 9.0, Z_VER, h0)
    # arco doble (cordón superior e inferior) con montantes en zigzag
    top = [(-a + 2.0 * a * i / n, 0.0, arc_z(-a + 2.0 * a * i / n)) for i in range(n + 1)]
    low = [(x, y, z - 38.0 * (1.0 - abs(x) / a) - 4.0) for (x, y, z) in top]
    tube(mb, M_HIERRO, top, 3.2, 8)
    tube(mb, M_HIERRO, low, 2.4, 8)
    for i in range(1, n):
        p, q = (top[i], low[i + 1]) if i % 2 else (low[i], top[i + 1])
        cyl(mb, M_HIERRO, p, q, 1.1, 6)
    # estrella en la clave (cinco puntas de caño) con lamparitas
    cz = apex + 45.0
    pts = []
    for j in range(10):
        ang = math.pi * 0.5 + j * math.pi / 5.0
        r = 40.0 if j % 2 == 0 else 17.0
        pts.append((r * math.cos(ang), 0.0, cz + r * math.sin(ang)))
    tube(mb, M_HIERRO, pts + [pts[0]], 1.4, 6)
    cyl(mb, M_HIERRO, (0.0, 0.0, apex), (0.0, 0.0, cz - 17.0), 1.4, 6)
    for (x, y, z) in pts[::2]:
        blob(mb, 'MI_Emisivo_Calido', (x, 0.0, z), 3.4, 3.4, 4.2, steps=(4, 6))
    # lamparitas a lo largo del cordón superior
    i = 0
    for (x, y, z) in k.catenary((-a + 20.0, 0.0, arc_z(-a + 20.0)), (a - 20.0, 0.0, arc_z(a - 20.0)), 0.0, 30):
        if i % 2 == 0:
            blob(mb, 'MI_Emisivo_Calido', (x, 0.0, arc_z(x) + 5.0), 3.0, 3.0, 3.8, steps=(4, 6))
        i += 1
    # dos guirnaldas colgantes (una a cada lado del arco) con portalámparas y lamparitas cada ~35 cm
    for (yy, sag) in ((-22.0, 70.0), (22.0, 95.0)):
        p0, p1 = (-a + 12.0, yy, h0 - 10.0), (a - 12.0, yy, h0 - 10.0)
        cat = k.catenary(p0, p1, sag, 28)
        tube(mb, 'MI_Cable', cat, 0.45, 4)
        L_ = 2.0 * a
        nb = int(L_ / 35.0)
        for b in range(1, nb):
            t = b / float(nb)
            x = p0[0] + (p1[0] - p0[0]) * t
            z = p0[2] - sag * 4.0 * t * (1.0 - t)
            cyl(mb, M_HIERRO, (x, yy, z), (x, yy, z - 5.0), 0.9, 5)
            blob(mb, 'MI_Emisivo_Calido', (x, yy, z - 9.0), 3.2, 3.2, 4.0, steps=(4, 6))
        for sx in (-1.0, 1.0):
            cyl(mb, M_HIERRO, (sx * (a - 2.0), 0.0, h0 - 10.0), (sx * (a - 12.0), yy, h0 - 10.0), 0.8, 5)
    return mb
