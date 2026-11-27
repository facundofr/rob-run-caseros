# -*- coding: utf-8 -*-
"""
build_facade.py  -  Cuadra de prueba de Caseros ("FacadeTest") modelada con Geometry Script.

Cómo correrlo (UE 5.8.4, plugins GeometryScripting + PythonScriptPlugin + EditorScriptingUtilities,
mapa /Game/Barrio/Maps/L_Greybox abierto):

    py "C:/Users/facufr/Desktop/rob-run-caseros/rob-run-caseros/game/ArtSource/Scripts/build_facade.py"

(o la ruta donde se haya copiado). Es idempotente: borra los actores de la carpeta "FacadeTest",
regenera las mallas en /Game/Barrio/Art/Facade/SM_FT_* (las existentes se actualizan en el lugar),
vuelve a colocar todo y guarda mallas + nivel. Al final loguea "[ARTE] FACHADA LISTA".

Qué genera (todo dentro de la zona FacadeTest: X -3800..-600, Y 1500..5500, frentes mirando a +X):
  - 5 lotes contiguos (8,66 m salvo el local de 4,33 m) con medianeras:
      A casa baja (revoque blanco): portón de chapa, puerta de madera, ventana con reja + persiana,
        nicho de medidor de luz y gas, caño de bajada con pipeta, número, split, gárgola, tanque y antena.
      B casa antigua con retiro de 3 m (verde agua): pilastras, cornisa con dentículos, postigos de
        madera, banderola, patio, canteros, reja baja con lanzas, pilares y pilar de medidor.
      C 2 plantas (amarillo): portón de madera de 3 hojas, puerta de chapa, balcón corrido con baranda
        de hierro y macetas, split, caño pluvial, terraza con parapeto, tanque sobre torre con escalera.
      D chalet 2 plantas con techo de tejas (rosa), retiro de 4,5 m: balcón con balaustrada torneada,
        chimenea, reja alta de 2 m con portón corredizo, puerta peatonal, pilar con medidor.
      E local comercial (ladrillo visto): cortina metálica con candados, cartel en blanco, split, tanque.
  - Vereda de 3 m (baldosa / hormigón / laja según lote, desniveles), cordón de hormigón de 16 cm con
    rebajes para garajes, canteros con borde de ladrillo, tapas, baldosas flojas, tocón.
  - Calle de 5 m (asfalto con bombeo, cordón cuneta, parches de hormigón), vereda y tapial de enfrente.
  - Postes de madera de 8-9 m levemente inclinados, con cruceta, aisladores, luminaria de brazo,
    rulos de fibra, caja de empalme, caño de bajada a tierra.
  - CABLES en catenaria: línea de baja tensión, telefonía/fibra/coaxil, acometidas a cada casa,
    cruces de calle, cables corridos por las fachadas con grampas y lazos colgando.
  - Árboles de vereda simplificados (fresno podado sin hojas y uno con copa de silueta), canastos
    de basura elevados de reja.

Materiales: solo los MI_* fijos de CONVENCIONES.md. Si una MI no existe, el slot queda vacío y se avisa.
Placeholders deliberados (no hay MI específica en la lista): tierra de canteros = MI_Asfalto,
copa/plantas = MI_Metal_Verde, tanque plástico = MI_Metal_Negro, carcasa de split / aisladores /
cortinas = MI_Revoque_Blanco.

Notas de API (UE 5.x; documentadas porque las firmas cambian entre versiones):
  * GeometryScript_Primitives.append_box(target_mesh, primitive_options, transform, dimension_x,
        dimension_y, dimension_z, steps_x, steps_y, steps_z, origin, debug)        -> DynamicMesh
  * append_cylinder(target_mesh, primitive_options, transform, radius, height, radial_steps,
        height_steps, capped, origin, debug)
  * append_cone(target_mesh, primitive_options, transform, base_radius, top_radius, height,
        radial_steps, height_steps, capped, origin, debug)
  * append_sphere_lat_long(target_mesh, primitive_options, transform, radius, steps_phi, steps_theta,
        origin, debug)
  * append_simple_extrude_polygon(target_mesh, primitive_options, transform, polygon_vertices
        (Array[Vector2D]), height, height_steps, capped, origin, debug)   [el nombre C++ es
        AppendSimpleExtrudePolygon; probamos también "append_simple_extruded_polygon"]
  * append_simple_swept_polygon(target_mesh, primitive_options, transform, polygon_vertices,
        sweep_path (Array[Vector]), loop, capped, start_scale, end_scale, rotation_angle_deg,
        mitre_limit, debug)
  * append_revolve_path(target_mesh, primitive_options, transform, path_vertices (X=radio, Y=altura),
        revolve_options, steps, capped, debug)           [se verifica con bounding box al inicio]
  * append_torus(target_mesh, primitive_options, transform, revolve_options, major_radius,
        minor_radius, major_steps, minor_steps, origin, debug)
  * GeometryScriptPrimitiveOptions: polygroup_mode, flip_orientation, uv_mode y (5.4+?) material_id.
  * GeometryScript_MeshBooleans.apply_mesh_boolean(target_mesh, target_transform, tool_mesh,
        tool_transform, operation, options, debug)
  * GeometryScript_MeshBasicEditing.append_mesh(target_mesh, append_mesh, append_transform,
        defer_change_notifications, debug)
  * GeometryScript_MeshMaterials.clear_material_i_ds(target_mesh, clear_value, debug)
        (Python convierte "IDs" en "i_ds"; probamos ambos nombres)
  * GeometryScript_AssetUtils.create_new_static_mesh_asset_from_mesh(from_dynamic_mesh,
        asset_path_and_name, options, debug) -> (StaticMesh, Outcome)  [Outcome es parámetro de salida]
  * GeometryScript_AssetUtils.copy_mesh_to_static_mesh(from_dynamic_mesh, to_static_asset, options,
        target_lod, [use_section_materials 5.4+], debug) -> (StaticMesh, Outcome)
  * GeometryScript_Collision.set_static_mesh_collision_from_mesh(from_dynamic_mesh,
        to_static_mesh_asset, options, debug)  con method = ALIGNED_BOXES (una caja por componente).
  Toda llamada pasa por call(): primero con keywords y, si da TypeError (nombres de parámetros
  distintos), reintenta posicional en el orden de arriba.
"""

import unreal
import math
import random
import time
import traceback
import os
_TRACE_PATH = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), 'facade_trace.txt')
_TRACE = open(_TRACE_PATH, 'w', encoding='utf-8')


def trace(msg):
    _TRACE.write(msg + '\n')
    _TRACE.flush()
    os.fsync(_TRACE.fileno())

# =====================================================================================
# CONFIGURACIÓN
# =====================================================================================
FACADE_DIR = '/Game/Barrio/Art/Facade'
MAT_DIR = '/Game/Barrio/Art/Materials'
MAP_PATH = '/Game/Barrio/Maps/L_Greybox'
FOLDER = 'FacadeTest'
ASSET_PREFIX = 'SM_FT_'

USE_BOOLEANS = True          # recorte de vanos con apply_mesh_boolean (si falla, se arma por paños)
USE_NANITE = True            # Nanite en las mallas opacas (los vidrios van en malla aparte sin Nanite)
SPLIT_NORMAL_ANGLE = 40.0    # aristas de más de 40° quedan duras (cajas y chaflanes), cilindros suaves
SEED = 5258

LM_X = -1950.0               # línea municipal (frente de los lotes) en X de mundo
Z_VER = 18.0                 # cara superior de la vereda (el terreno "Afuera" está en Z=0)
Z_PISO = 30.0                # piso interior de las casas
WALL_T = 30.0                # espesor de muro

MATS = ['MI_Revoque_Blanco', 'MI_Revoque_Gris', 'MI_Revoque_Rosa', 'MI_Revoque_VerdeAgua',
        'MI_Revoque_Amarillo', 'MI_Ladrillo', 'MI_Baldosa', 'MI_Asfalto', 'MI_Hormigon',
        'MI_Chapa_Gris', 'MI_Chapa_Verde', 'MI_Madera', 'MI_Tejas', 'MI_Metal_Negro',
        'MI_Metal_Verde', 'MI_PiedraLaja', 'MI_Vidrio', 'MI_PosteMadera', 'MI_Cable']
MAT_INDEX = dict((m, i) for i, m in enumerate(MATS))
NANITE_EXCLUDE = set(['MI_Vidrio'])   # posible material translúcido: malla aparte sin Nanite

# Placeholders (no existe MI específica en la lista fija)
M_TIERRA = 'MI_Asfalto'
M_FOLLAJE = 'MI_Metal_Verde'
M_PLASTICO = 'MI_Metal_Negro'
M_AC = 'MI_Revoque_Blanco'
M_PORCELANA = 'MI_Revoque_Blanco'
M_TELA = 'MI_Revoque_Blanco'
M_ALUMINIO = 'MI_Chapa_Gris'
M_HIERRO = 'MI_Metal_Negro'

# =====================================================================================
# LOG
# =====================================================================================
_ERR_COUNT = {}
STATS = {'ok': 0, 'fail': 0}


def log(msg):
    trace("LOG " + str(msg))
    unreal.log('[ARTE] ' + msg)


def warn(msg):
    trace("WARN " + str(msg))
    unreal.log_warning('[ARTE] ' + msg)


def err(msg):
    trace("ERR " + str(msg))
    unreal.log_error('[ARTE] ' + msg)


def err_once(key, msg, limit=3):
    n = _ERR_COUNT.get(key, 0)
    _ERR_COUNT[key] = n + 1
    if n < limit:
        err(msg)
    elif n == limit:
        err('(%s) hay más errores iguales; se silencian' % key)


def piece(name, fn, *a, **k):
    """Ejecuta una pieza aislada: si falla, loguea y sigue con el resto."""
    trace('ENTER piece ' + repr(name)[:120])
    try:
        r = fn(*a, **k)
        STATS['ok'] += 1
        return r
    except Exception as e:
        STATS['fail'] += 1
        err('Pieza "%s" falló: %s\n%s' % (name, e, traceback.format_exc()))
        return None


# =====================================================================================
# CHEQUEO DE API
# =====================================================================================
F = {}       # funciones resueltas
CAPS = {}    # capacidades/calibraciones detectadas
PRISM_CFG = {}

LIBS = {
    'prim': 'GeometryScript_Primitives',
    'bool': 'GeometryScript_MeshBooleans',
    'edit': 'GeometryScript_MeshEdits',
    'xf': 'GeometryScript_MeshTransforms',
    'asset': 'GeometryScript_AssetUtils',
    'normals': 'GeometryScript_Normals',
    'mats': 'GeometryScript_Materials',
    'newasset': 'GeometryScript_NewAssetUtils',
    'query': 'GeometryScript_MeshQueries',
    'coll': 'GeometryScript_Collision',
}

API_FUNCS = [
    ('box', 'prim', ['append_box']),
    ('cyl', 'prim', ['append_cylinder']),
    ('cone', 'prim', ['append_cone']),
    ('sphere', 'prim', ['append_sphere_lat_long']),
    ('extrude', 'prim', ['append_simple_extrude_polygon', 'append_simple_extruded_polygon']),
    ('sweep', 'prim', ['append_simple_swept_polygon']),
    ('revolve', 'prim', ['append_revolve_path']),
    ('torus', 'prim', ['append_torus']),
    ('boolean', 'bool', ['apply_mesh_boolean']),
    ('append_mesh', 'edit', ['append_mesh']),
    ('transform_mesh', 'xf', ['transform_mesh']),
    ('create_sm', 'newasset', ['create_new_static_mesh_asset_from_mesh']),
    ('copy_sm', 'asset', ['copy_mesh_to_static_mesh']),
    ('split_normals', 'normals', ['compute_split_normals']),
    ('clear_ids', 'mats', ['clear_material_i_ds', 'clear_material_ids']),
    ('bbox', 'query', ['get_mesh_bounding_box']),
    ('volume', 'query', ['get_mesh_volume_area']),
    ('tri_count', 'query', ['get_num_triangle_i_ds', 'get_num_triangle_ids', 'get_triangle_count']),
    ('coll_from_mesh', 'coll', ['set_static_mesh_collision_from_mesh']),
]

STRUCTS = ['DynamicMesh', 'GeometryScriptPrimitiveOptions', 'GeometryScriptPrimitiveOriginMode',
           'GeometryScriptPrimitivePolygroupMode', 'GeometryScriptMeshBooleanOptions',
           'GeometryScriptBooleanOperation', 'GeometryScriptRevolveOptions',
           'GeometryScriptCreateNewStaticMeshAssetOptions', 'GeometryScriptCopyMeshToAssetOptions',
           'GeometryScriptMeshWriteLOD', 'GeometryScriptSplitNormalsOptions',
           'GeometryScriptCalculateNormalsOptions', 'GeometryScriptCollisionFromMeshOptions',
           'GeometryScriptCollisionGenerationMethod', 'MeshNaniteSettings', 'EditorActorSubsystem',
           'LevelEditorSubsystem', 'UnrealEditorSubsystem']


def probe_api():
    log('---- Chequeo de API de Geometry Script (UE %s) ----' % _engine_version())
    for key, lib_key, names in API_FUNCS:
        lib = getattr(unreal, LIBS[lib_key], None)
        found = None
        if lib is not None:
            for n in names:
                if hasattr(lib, n):
                    found = getattr(lib, n)
                    F[key] = found
                    log('  OK    %s.%s' % (LIBS[lib_key], n))
                    break
        if found is None:
            F[key] = None
            (err if key in ('box', 'append_mesh', 'create_sm') else warn)(
                '  FALTA %s.%s  (lib %s)' % (LIBS[lib_key], '/'.join(names),
                                            'presente' if lib is not None else 'AUSENTE'))
    for s in STRUCTS:
        if not hasattr(unreal, s):
            warn('  FALTA tipo unreal.%s' % s)
    # opción material_id en GeometryScriptPrimitiveOptions
    CAPS['matid_opt'] = False
    try:
        o = unreal.GeometryScriptPrimitiveOptions()
        o.set_editor_property('material_id', 3)
        CAPS['matid_opt'] = (int(o.get_editor_property('material_id')) == 3)
    except Exception:
        CAPS['matid_opt'] = False
    log('  GeometryScriptPrimitiveOptions.material_id: %s' % ('SI' if CAPS['matid_opt'] else 'NO'))


def _engine_version():
    try:
        return unreal.SystemLibrary.get_engine_version()
    except Exception:
        return '?'


def call(key, *args, **kw):
    """Llama una función de Geometry Script: keywords primero, posicional si cambiaron los nombres."""
    f = F.get(key)
    if f is None:
        raise RuntimeError('API faltante: ' + key)
    trace('CALL %s nargs=%d kw=%s' % (key, len(args), sorted(kw.keys())))
    try:
        return f(*args, **kw)
    except TypeError:
        return f(*(list(args) + list(kw.values())))


def _sp(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        return False


# =====================================================================================
# MATEMÁTICA BÁSICA
# =====================================================================================
def V(x, y=None, z=None):
    if y is None:
        x, y, z = x
    return unreal.Vector(float(x), float(y), float(z))


def R(roll=0.0, pitch=0.0, yaw=0.0):
    return unreal.Rotator(roll=float(roll), pitch=float(pitch), yaw=float(yaw))


def T(loc=(0.0, 0.0, 0.0), rot=None, scale=(1.0, 1.0, 1.0)):
    return unreal.Transform(location=V(loc), rotation=(rot if rot is not None else R()), scale=V(scale))


def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def v_len(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def v_norm(a):
    l = v_len(a)
    if l < 1e-9:
        return (0.0, 0.0, 1.0)
    return (a[0] / l, a[1] / l, a[2] / l)


def v_lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def poly_area(pts):
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return 0.5 * s


def dedupe(pts, eps=0.01):
    out = []
    for p in pts:
        if not out or abs(out[-1][0] - p[0]) > eps or abs(out[-1][1] - p[1]) > eps:
            out.append(p)
    if len(out) > 2 and abs(out[0][0] - out[-1][0]) <= eps and abs(out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


def _manual_axes(rot):
    """Ejes locales X,Y,Z rotados según FRotationMatrix de UE (filas de la matriz)."""
    r = math.radians(rot.roll)
    p = math.radians(rot.pitch)
    y = math.radians(rot.yaw)
    sr, cr = math.sin(r), math.cos(r)
    sp, cp = math.sin(p), math.cos(p)
    sy, cy = math.sin(y), math.cos(y)
    ex = (cp * cy, cp * sy, sp)
    ey = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp)
    ez = (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp)
    return [ex, ey, ez]


def axes_of(rot):
    """Ejes rotados medidos con la matemática del motor (Transform.transform_location)."""
    t = unreal.Transform(location=V(0, 0, 0), rotation=rot, scale=V(1, 1, 1))
    out = []
    for e in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        p = None
        try:
            p = t.transform_location(V(e))
        except Exception:
            try:
                p = unreal.MathLibrary.transform_location(t, V(e))
            except Exception:
                p = None
        if p is None:
            return _manual_axes(rot)
        out.append((p.x, p.y, p.z))
    return out


def world_pt(loc, rot, p):
    """Punto local p de un actor en loc/rot -> mundo."""
    ex, ey, ez = axes_of(rot)
    return (loc[0] + p[0] * ex[0] + p[1] * ey[0] + p[2] * ez[0],
            loc[1] + p[0] * ex[1] + p[1] * ey[1] + p[2] * ez[1],
            loc[2] + p[0] * ex[2] + p[1] * ey[2] + p[2] * ez[2])


def _rot_z_manual(d):
    h = math.sqrt(d[0] * d[0] + d[1] * d[1])
    return R(pitch=math.degrees(math.atan2(-h, d[2])), yaw=math.degrees(math.atan2(d[1], d[0])))


def rot_z_to(d):
    """Rotator que lleva el eje Z local a la dirección d."""
    d = v_norm(d)
    if CAPS.get('rot_method', 'engine') == 'engine':
        try:
            return unreal.MathLibrary.make_rot_from_z(V(d))
        except Exception:
            CAPS['rot_method'] = 'manual'
    return _rot_z_manual(d)


# =====================================================================================
# MALLAS
# =====================================================================================
def new_mesh():
    try:
        return unreal.DynamicMesh()
    except Exception:
        return unreal.new_object(unreal.DynamicMesh)


_OPTS = {}


def popts(mat, flip=False):
    key = (mat, bool(flip))
    o = _OPTS.get(key)
    if o is not None:
        return o
    o = unreal.GeometryScriptPrimitiveOptions()
    try:
        _sp(o, 'polygroup_mode', unreal.GeometryScriptPrimitivePolygroupMode.PER_FACE)
    except Exception:
        pass
    if CAPS.get('matid_opt'):
        _sp(o, 'material_id', MAT_INDEX.get(mat, 0))
    if flip:
        _sp(o, 'flip_orientation', True)
    _OPTS[key] = o
    return o


class MB(object):
    """Constructor de malla: una DynamicMesh por material + cajas de colisión + anclajes."""

    def __init__(self, name):
        self.name = name
        self.subs = {}
        self.order = []
        self.coll = []
        self.anchors = {}

    def m(self, mat):
        if mat not in self.subs:
            self.subs[mat] = new_mesh()
            self.order.append(mat)
        return self.subs[mat]

    def col(self, x0, x1, y0, y1, z0, z1):
        self.coll.append((min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)))


class _One(object):
    """Adaptador: todas las primitivas van a una sola malla (plantillas)."""

    def __init__(self, mesh):
        self.mesh = mesh

    def m(self, mat):
        return self.mesh


ORIGIN = {}


def _origins():
    ORIGIN['base'] = unreal.GeometryScriptPrimitiveOriginMode.BASE
    ORIGIN['center'] = unreal.GeometryScriptPrimitiveOriginMode.CENTER


def _box_raw(mesh, opts, t, dx, dy, dz, origin):
    call('box', mesh, opts, t, dimension_x=float(dx), dimension_y=float(dy), dimension_z=float(dz),
         steps_x=0, steps_y=0, steps_z=0, origin=origin)


def _cyl_raw(mesh, opts, t, r, h, steps, capped, origin):
    call('cyl', mesh, opts, t, radius=float(r), height=float(h), radial_steps=int(steps),
         height_steps=0, capped=bool(capped), origin=origin)


def _cone_raw(mesh, opts, t, r0, r1, h, steps, capped, origin):
    call('cone', mesh, opts, t, base_radius=float(r0), top_radius=float(r1), height=float(h),
         radial_steps=int(steps), height_steps=0, capped=bool(capped), origin=origin)


def _extrude_raw(mesh, opts, t, poly2d, h):
    call('extrude', mesh, opts, t, polygon_vertices=poly2d, height=float(h), height_steps=0,
         capped=True, origin=ORIGIN['base'])


def _sweep_raw(mesh, opts, t, poly2d, path):
    call('sweep', mesh, opts, t, polygon_vertices=poly2d, sweep_path=path, loop=False, capped=True,
         start_scale=1.0, end_scale=1.0, rotation_angle_deg=0.0, mitre_limit=1.0)


def _revolve_raw(mesh, opts, t, path2d, steps):
    ro = unreal.GeometryScriptRevolveOptions()
    call('revolve', mesh, opts, t, path_vertices=path2d, revolve_options=ro, steps=int(steps), capped=True)


def _torus_raw(mesh, opts, t, rmaj, rmin, smaj, smin):
    ro = unreal.GeometryScriptRevolveOptions()
    call('torus', mesh, opts, t, revolve_options=ro, major_radius=float(rmaj), minor_radius=float(rmin),
         major_steps=int(smaj), minor_steps=int(smin), origin=ORIGIN['center'])


def append_into(target, src, t=None):
    call('append_mesh', target, src, t if t is not None else T(), defer_change_notifications=False)


# ---------------------------------------------------------------------------------
# primitivas de alto nivel (coordenadas locales del constructor)
# ---------------------------------------------------------------------------------
def box(mb, mat, x0, x1, y0, y1, z0, z1):
    """Caja alineada a ejes por mínimos/máximos."""
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    if dx < 0.02 or dy < 0.02 or dz < 0.02:
        return
    _box_raw(mb.m(mat), popts(mat), T(((x0 + x1) * 0.5, (y0 + y1) * 0.5, z0)), dx, dy, dz, ORIGIN['base'])


def rbox(mb, mat, cx, cy, z0, dx, dy, dz, yaw=0.0, pitch=0.0, roll=0.0):
    """Caja rotada alrededor del centro de su base."""
    _box_raw(mb.m(mat), popts(mat), T((cx, cy, z0), R(roll=roll, pitch=pitch, yaw=yaw)), dx, dy, dz,
             ORIGIN['base'])


_PLANE = {'x': (1, 2, 0), 'y': (0, 2, 1), 'z': (0, 1, 2)}   # (eje p, eje q, eje de extrusión)


def prism(mb, mat, pts, axis, a0, a1):
    """Extruye un perfil 2D a lo largo de un eje de mundo-local.
    axis 'y': pts=(x,z) extruido de y=a0 a y=a1;  'x': pts=(y,z);  'z': pts=(x,y)."""
    if not pts or len(pts) < 3:
        return
    if a1 < a0:
        a0, a1 = a1, a0
    L = a1 - a0
    if L < 0.02:
        return
    pts = dedupe(pts)
    pi, qi, ai = _PLANE[axis]
    cfg = PRISM_CFG.get(axis)
    if cfg is None or not F.get('extrude'):
        lo = [0.0, 0.0, 0.0]
        hi = [0.0, 0.0, 0.0]
        lo[pi], hi[pi] = min(p for p, q in pts), max(p for p, q in pts)
        lo[qi], hi[qi] = min(q for p, q in pts), max(q for p, q in pts)
        lo[ai], hi[ai] = a0, a1
        box(mb, mat, lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
        return
    rot, ex, ey, ez = cfg
    uv = [(p * ex[pi] + q * ex[qi], p * ey[pi] + q * ey[qi]) for (p, q) in pts]
    if poly_area(uv) < 0:
        uv.reverse()
    loc = [0.0, 0.0, 0.0]
    loc[ai] = a0 if ez[ai] > 0 else a1
    _extrude_raw(mb.m(mat), popts(mat, CAPS.get('extrude_flip', False)), T(tuple(loc), rot),
                 [unreal.Vector2D(u, v) for (u, v) in uv], L)


def chamfer_rect(p0, p1, q0, q1, c, mask=(1, 1, 1, 1)):
    """Rectángulo con esquinas chaflanadas (orden antihorario). mask: (p0q0, p1q0, p1q1, p0q1)."""
    c = max(0.0, min(c, (p1 - p0) * 0.45, (q1 - q0) * 0.45))
    pts = []
    if mask[0] and c > 0:
        pts += [(p0, q0 + c), (p0 + c, q0)]
    else:
        pts.append((p0, q0))
    if mask[1] and c > 0:
        pts += [(p1 - c, q0), (p1, q0 + c)]
    else:
        pts.append((p1, q0))
    if mask[2] and c > 0:
        pts += [(p1, q1 - c), (p1 - c, q1)]
    else:
        pts.append((p1, q1))
    if mask[3] and c > 0:
        pts += [(p0 + c, q1), (p0, q1 - c)]
    else:
        pts.append((p0, q1))
    return pts


def cbox(mb, mat, x0, x1, y0, y1, z0, z1, c=1.0, axis=None, mask=(1, 1, 1, 1)):
    """Caja con aristas chaflanadas a lo largo de 'axis' (por defecto el lado más largo)."""
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    z0, z1 = min(z0, z1), max(z0, z1)
    if axis is None:
        d = {'x': x1 - x0, 'y': y1 - y0, 'z': z1 - z0}
        axis = max(d, key=d.get)
    if c <= 0.0:
        box(mb, mat, x0, x1, y0, y1, z0, z1)
        return
    if axis == 'x':
        prism(mb, mat, chamfer_rect(y0, y1, z0, z1, c, mask), 'x', x0, x1)
    elif axis == 'y':
        prism(mb, mat, chamfer_rect(x0, x1, z0, z1, c, mask), 'y', y0, y1)
    else:
        prism(mb, mat, chamfer_rect(x0, x1, y0, y1, c, mask), 'z', z0, z1)


def cyl(mb, mat, p0, p1, r, sides=10, capped=True):
    d = v_sub(p1, p0)
    L = v_len(d)
    if L < 0.02 or r <= 0:
        return
    mid = v_lerp(p0, p1, 0.5)
    _cyl_raw(mb.m(mat), popts(mat), T(mid, rot_z_to(d)), r, L, sides, capped, ORIGIN['center'])


def cone(mb, mat, p0, p1, r0, r1, sides=10):
    d = v_sub(p1, p0)
    L = v_len(d)
    if L < 0.02:
        return
    _cone_raw(mb.m(mat), popts(mat), T(p0, rot_z_to(d)), r0, max(r1, 0.0), L, sides, True, ORIGIN['base'])


def blob(mb, mat, c, rx, ry, rz, yaw=0.0, steps=(8, 12)):
    """Elipsoide (esfera escalada)."""
    if not F.get('sphere'):
        cbox(mb, mat, c[0] - rx * 0.8, c[0] + rx * 0.8, c[1] - ry * 0.8, c[1] + ry * 0.8,
             c[2] - rz * 0.8, c[2] + rz * 0.8, min(rx, ry, rz) * 0.3, 'z')
        return
    call('sphere', mb.m(mat), popts(mat), T(c, R(yaw=yaw), (rx / 50.0, ry / 50.0, rz / 50.0)),
         radius=50.0, steps_phi=int(steps[0]), steps_theta=int(steps[1]), origin=ORIGIN['center'])


def torus(mb, mat, center, rmaj, rmin, normal=(0, 0, 1), smaj=20, smin=6):
    if CAPS.get('torus_ok'):
        try:
            _torus_raw(mb.m(mat), popts(mat), T(center, rot_z_to(normal)), rmaj, rmin, smaj, smin)
            return
        except Exception as e:
            err_once('torus', 'append_torus falló (%s); se usan cilindros' % e)
            CAPS['torus_ok'] = False
    # aproximación: polilínea cerrada
    n = v_norm(normal)
    a = v_norm((n[1], -n[0], 0.0)) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    b = (n[1] * a[2] - n[2] * a[1], n[2] * a[0] - n[0] * a[2], n[0] * a[1] - n[1] * a[0])
    pts = []
    for k in range(smaj + 1):
        ang = 2.0 * math.pi * k / smaj
        pts.append(v_add(center, v_add(v_mul(a, rmaj * math.cos(ang)), v_mul(b, rmaj * math.sin(ang)))))
    for i in range(len(pts) - 1):
        cyl(mb, mat, pts[i], pts[i + 1], rmin, 5)


def tube(mb, mat, pts, r, sides=6):
    """Tubo a lo largo de una polilínea (sweep); si no hay sweep, cilindros por tramo."""
    if len(pts) < 2:
        return
    if CAPS.get('sweep_ok'):
        try:
            poly = [unreal.Vector2D(r * math.cos(2.0 * math.pi * k / sides), r * math.sin(2.0 * math.pi * k / sides))
                    for k in range(sides)]
            _sweep_raw(mb.m(mat), popts(mat, CAPS.get('sweep_flip', False)), T(), poly, [V(p) for p in pts])
            return
        except Exception as e:
            err_once('sweep', 'append_simple_swept_polygon falló (%s); se usan cilindros' % e)
            CAPS['sweep_ok'] = False
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        d = v_norm(v_sub(b, a))
        cyl(mb, mat, v_sub(a, v_mul(d, r * 0.5)), v_add(b, v_mul(d, r * 0.5)), r, max(4, sides - 1))


# ---------------------------------------------------------------------------------
# paños con vanos
# ---------------------------------------------------------------------------------
def interval_minus(a0, a1, gaps, min_len=0.5):
    segs = [(a0, a1)]
    for g0, g1 in gaps:
        nxt = []
        for s0, s1 in segs:
            if g1 <= s0 or g0 >= s1:
                nxt.append((s0, s1))
                continue
            if g0 > s0:
                nxt.append((s0, g0))
            if g1 < s1:
                nxt.append((g1, s1))
        segs = nxt
    return [(s0, s1) for s0, s1 in segs if s1 - s0 > min_len]


def rect_minus(a0, a1, b0, b1, holes):
    """Rectángulo [a0,a1]x[b0,b1] menos rectángulos (ha0,ha1,hb0,hb1) -> lista de rectángulos."""
    hs = []
    for h in holes:
        ha0, ha1 = max(a0, h[0]), min(a1, h[1])
        hb0, hb1 = max(b0, h[2]), min(b1, h[3])
        if ha1 - ha0 > 0.01 and hb1 - hb0 > 0.01:
            hs.append((ha0, ha1, hb0, hb1))
    bs = sorted(set([b0, b1] + [h[2] for h in hs] + [h[3] for h in hs]))
    out = []
    open_ = {}
    for i in range(len(bs) - 1):
        z0, z1 = bs[i], bs[i + 1]
        if z1 - z0 < 0.01:
            continue
        zm = 0.5 * (z0 + z1)
        cov = [(h[0], h[1]) for h in hs if h[2] < zm < h[3]]
        segs = interval_minus(a0, a1, cov, 0.001)
        new_open = {}
        for s in segs:
            if s in open_:
                r = open_.pop(s)
                new_open[s] = (r[0], r[1], r[2], z1)
            else:
                new_open[s] = (s[0], s[1], z0, z1)
        out.extend(open_.values())
        open_ = new_open
    out.extend(open_.values())
    return out


def wall_holes(mb, mat, x0, x1, y0, y1, z0, z1, holes):
    """Paño de muro en el plano YZ (espesor en X) con vanos pasantes (y0,y1,z0,z1)."""
    hs = [h for h in holes if h[1] > h[0] and h[3] > h[2]]
    if USE_BOOLEANS and F.get('boolean') and hs and CAPS.get('boolean_ok', True):
        try:
            wm = new_mesh()
            o = popts(mat)
            _box_raw(wm, o, T(((x0 + x1) * 0.5, (y0 + y1) * 0.5, z0)), x1 - x0, y1 - y0, z1 - z0, ORIGIN['base'])
            tool = new_mesh()
            for h in hs:
                _box_raw(tool, o, T(((x0 + x1) * 0.5, (h[0] + h[1]) * 0.5, h[2])),
                         (x1 - x0) + 6.0, h[1] - h[0], h[3] - h[2], ORIGIN['base'])
            bo = unreal.GeometryScriptMeshBooleanOptions()
            _sp(bo, 'fill_holes', True)
            _sp(bo, 'simplify_output', False)
            F['boolean'](wm, T(), tool, T(), unreal.GeometryScriptBooleanOperation.SUBTRACT, bo)
            nt = tri_count(wm)
            if 0 <= nt <= 12:
                raise RuntimeError('el booleano no recortó nada (%d triángulos)' % nt)
            append_into(mb.m(mat), wm)
            return
        except Exception as e:
            err_once('boolean', 'apply_mesh_boolean falló (%s); vanos armados por paños' % e)
            CAPS['boolean_ok'] = False
    for (a0, a1, b0, b1) in rect_minus(y0, y1, z0, z1, hs):
        box(mb, mat, x0, x1, a0, a1, b0, b1)


# ---------------------------------------------------------------------------------
# perfiles
# ---------------------------------------------------------------------------------
def slats_profile(xb, depth, z0, z1, pitch, lip):
    """Perfil (x,z) de lamas horizontales (persiana, cortina, celosía): espalda plana + dientes."""
    if z1 - z0 < 1.0:
        return None
    n = max(1, int(round((z1 - z0) / pitch)))
    h = (z1 - z0) / n
    fd = xb + depth
    pts = [(xb, z0), (fd, z0)]
    for i in range(n):
        za = z0 + i * h
        pts.append((fd + lip, za + h * 0.82))
        pts.append((fd, za + h))
    pts.append((xb, z1))
    return pts


def ribs_profile_xy(xb, depth, y0, y1, pitch, rib):
    """Perfil en planta (x,y) de chapa acanalada trapezoidal (canaletas verticales)."""
    n = max(1, int(round((y1 - y0) / pitch)))
    p = (y1 - y0) / n
    fx = xb + depth
    pts = [(xb, y0), (fx, y0)]
    for i in range(n):
        ya = y0 + i * p
        pts += [(fx, ya + 0.2 * p), (fx + rib, ya + 0.35 * p), (fx + rib, ya + 0.65 * p), (fx, ya + 0.8 * p)]
    pts += [(fx, y1), (xb, y1)]
    return pts


def catenary(p0, p1, sag, n=None):
    L = v_len(v_sub(p1, p0))
    if n is None:
        n = max(6, min(30, int(L / 40.0)))
    pts = []
    for i in range(n + 1):
        t = float(i) / n
        p = v_lerp(p0, p1, t)
        pts.append((p[0], p[1], p[2] - sag * 4.0 * t * (1.0 - t)))
    return pts


def bezier(p0, p1, p2, n=12):
    pts = []
    for i in range(n + 1):
        t = float(i) / n
        a = v_lerp(p0, p1, t)
        b = v_lerp(p1, p2, t)
        pts.append(v_lerp(a, b, t))
    return pts


# =====================================================================================
# CALIBRACIÓN (convenciones de rotación, orientación de caras)
# =====================================================================================
def mesh_volume(m):
    if not F.get('volume'):
        return None
    try:
        r = F['volume'](m)
    except Exception:
        return None
    vals = []

    def walk(x):
        if isinstance(x, (list, tuple)):
            for y in x:
                walk(y)
        elif isinstance(x, float) or (isinstance(x, int) and not isinstance(x, bool)):
            vals.append(float(x))
    walk(r)
    return vals[-1] if vals else None


def mesh_bbox(m):
    if not F.get('bbox'):
        return None
    try:
        b = F['bbox'](m)
        if isinstance(b, (list, tuple)):
            b = [x for x in b if hasattr(x, 'min')][0]
        return (b.min.x, b.min.y, b.min.z), (b.max.x, b.max.y, b.max.z)
    except Exception:
        return None


def calibrate():
    _origins()
    # 1) DynamicMesh + caja de referencia
    m = new_mesh()
    _box_raw(m, popts('MI_Hormigon'), T(), 10, 10, 10, ORIGIN['base'])
    vbox = mesh_volume(m)
    sign_ref = 1.0 if (vbox is None or vbox >= 0) else -1.0
    log('Calibración: volumen caja de prueba = %s' % vbox)

    # 2) make_rot_from_z del motor vs fórmula manual
    d = v_norm((0.3, -0.5, 0.8))
    CAPS['rot_method'] = 'manual'
    for meth in ('engine', 'manual'):
        try:
            rot = unreal.MathLibrary.make_rot_from_z(V(d)) if meth == 'engine' else _rot_z_manual(d)
            ez = axes_of(rot)[2]
            if v_len(v_sub(ez, d)) < 1e-3:
                CAPS['rot_method'] = meth
                break
        except Exception:
            continue
    log('Calibración: rotación eje Z -> dirección: %s' % CAPS['rot_method'])

    # 3) ejes para prismas (perfil 2D extruido a lo largo de X, Y o Z)
    cands = {'z': [R()],
             'y': [R(roll=90.0), R(roll=-90.0), R(pitch=90.0, yaw=90.0)],
             'x': [R(pitch=-90.0), R(pitch=90.0), R(roll=90.0, yaw=90.0)]}
    CAPS['extrude_flip'] = False
    for axis in ('z', 'y', 'x'):
        pi, qi, ai = _PLANE[axis]
        for rot in cands[axis]:
            ex, ey, ez = axes_of(rot)
            if abs(abs(ez[ai]) - 1.0) < 1e-3 and abs(ex[ai]) < 1e-3 and abs(ey[ai]) < 1e-3:
                PRISM_CFG[axis] = (rot, ex, ey, ez)
                break
        if axis not in PRISM_CFG:
            err('Calibración: no se encontró rotación para prismas en eje %s (se usarán cajas)' % axis)
    if F.get('extrude'):
        try:
            # orientación de caras
            tm = new_mesh()
            prism(_One(tm), 'MI_Hormigon', [(0, 0), (10, 0), (10, 10), (0, 10)], 'z', 0, 10)
            ve = mesh_volume(tm)
            if ve is not None and vbox is not None and ve * sign_ref < 0:
                CAPS['extrude_flip'] = True
            log('Calibración: volumen prisma = %s -> flip=%s' % (ve, CAPS['extrude_flip']))
            # verificación de ejes con bounding box
            for axis in ('x', 'y', 'z'):
                if axis not in PRISM_CFG:
                    continue
                tm = new_mesh()
                prism(_One(tm), 'MI_Hormigon', [(10, 20), (60, 20), (10, 90)], axis, 30, 70)
                bb = mesh_bbox(tm)
                if bb is None:
                    continue
                pi, qi, ai = _PLANE[axis]
                exp_lo = [0, 0, 0]
                exp_hi = [0, 0, 0]
                exp_lo[pi], exp_hi[pi] = 10, 60
                exp_lo[qi], exp_hi[qi] = 20, 90
                exp_lo[ai], exp_hi[ai] = 30, 70
                bad = max(abs(bb[0][i] - exp_lo[i]) + abs(bb[1][i] - exp_hi[i]) for i in range(3))
                if bad > 0.5:
                    err('Calibración: prisma eje %s fuera de lugar. bbox=%s esperado=%s/%s. '
                        'Revisar PRISM_CFG / append_simple_extrude_polygon.' % (axis, bb, exp_lo, exp_hi))
                else:
                    log('Calibración: prisma eje %s OK' % axis)
        except Exception as e:
            err('Calibración de prismas falló: %s\n%s' % (e, traceback.format_exc()))
            F['extrude'] = None

    # 4) sweep
    CAPS['sweep_ok'] = False
    CAPS['sweep_flip'] = False
    if F.get('sweep'):
        try:
            tm = new_mesh()
            poly = [unreal.Vector2D(-1, -1), unreal.Vector2D(1, -1), unreal.Vector2D(1, 1), unreal.Vector2D(-1, 1)]
            _sweep_raw(tm, popts('MI_Cable'), T(), poly, [V(0, 0, 0), V(0, 0, 5), V(0, 0, 10)])
            vs = mesh_volume(tm)
            CAPS['sweep_ok'] = True
            if vs is not None and vbox is not None and vs * sign_ref < 0:
                CAPS['sweep_flip'] = True
            log('Calibración: sweep OK (volumen %s, flip=%s)' % (vs, CAPS['sweep_flip']))
        except Exception as e:
            warn('Calibración: sweep no disponible (%s); cables con cilindros' % e)

    # 5) revolve (balaustres)
    CAPS['revolve_ok'] = False
    CAPS['revolve_flip'] = False
    if F.get('revolve'):
        try:
            tm = new_mesh()
            _revolve_raw(tm, popts('MI_Hormigon'), T(), [unreal.Vector2D(4, 0), unreal.Vector2D(4, 50)], 8)
            bb = mesh_bbox(tm)
            if bb is None or (abs((bb[1][2] - bb[0][2]) - 50.0) < 1.0 and abs((bb[1][0] - bb[0][0]) - 8.0) < 1.0):
                CAPS['revolve_ok'] = True
                vr = mesh_volume(tm)
                if vr is not None and vbox is not None and vr * sign_ref < 0:
                    CAPS['revolve_flip'] = True
                log('Calibración: revolve OK (flip=%s)' % CAPS['revolve_flip'])
            else:
                warn('Calibración: revolve con ejes inesperados bbox=%s; balaustres con conos' % (bb,))
        except Exception as e:
            warn('Calibración: revolve no disponible (%s)' % e)

    # 6) toro
    CAPS['torus_ok'] = False
    if F.get('torus'):
        try:
            tm = new_mesh()
            _torus_raw(tm, popts('MI_Cable'), T(), 10, 1, 8, 4)
            CAPS['torus_ok'] = True
        except Exception as e:
            warn('Calibración: append_torus no disponible (%s)' % e)
    log('Calibración: %s' % dict((k, v) for k, v in CAPS.items()))


# =====================================================================================
# KIT DE FACHADA  (coordenadas de lote: x hacia la calle (+X), xf = plano de fachada,
#                  y a lo largo del frente, z arriba; muro de xf-30 a xf)
# =====================================================================================
def k_reja_plano(mb, mat, f0, a0, a1, z0, z1, axis='y', spacing=12.0, bar=1.6, frame=2.5,
                 rails=(), grid=False, lanzas=0.0):
    """Reja de barrotes en un plano vertical. axis = dirección horizontal de la reja.
    f0 = coordenada (x si axis=='y', y si axis=='x') de la cara trasera."""
    dep = max(frame, bar)
    fc = f0 + dep * 0.5

    def B(c0, c1, g0, g1, za, zb):
        if axis == 'y':
            box(mb, mat, g0, g1, c0, c1, za, zb)
        else:
            box(mb, mat, c0, c1, g0, g1, za, zb)
    if frame > 0:
        B(a0, a0 + frame, f0, f0 + frame, z0, z1)
        B(a1 - frame, a1, f0, f0 + frame, z0, z1)
        B(a0 + frame, a1 - frame, f0, f0 + frame, z1 - frame, z1)
        B(a0 + frame, a1 - frame, f0, f0 + frame, z0, z0 + frame)
    ia0, ia1 = a0 + frame, a1 - frame
    n = max(1, int(round((ia1 - ia0) / spacing)))
    step = (ia1 - ia0) / n
    zb0 = z0 + frame
    zb1 = z1 - frame
    if frame <= 0:
        rng_c = range(0, n + 1)
    else:
        rng_c = range(1, n)
    for i in rng_c:
        c = ia0 + i * step
        B(c - bar * 0.5, c + bar * 0.5, fc - bar * 0.5, fc + bar * 0.5, zb0, zb1)
        if lanzas > 0:
            if axis == 'y':
                p = (fc, c, zb1)
            else:
                p = (c, fc, zb1)
            cone(mb, mat, p, (p[0], p[1], p[2] + lanzas), bar * 1.25, 0.05, 4)
    if grid:
        nz = max(1, int(round((zb1 - zb0) / spacing)))
        sz = (zb1 - zb0) / nz
        for k in range(1, nz):
            zc = zb0 + k * sz
            B(ia0, ia1, fc - bar * 0.5, fc + bar * 0.5, zc - bar * 0.5, zc + bar * 0.5)
    for zr in rails:
        B(ia0, ia1, fc - 0.45, fc + 0.45, zr - 1.6, zr + 1.6)


def k_reja_ventana(mb, xf, y0, y1, z0, z1, kind='barrotes', mat=M_HIERRO):
    x0 = xf + 2.0
    if kind == 'cuadricula':
        k_reja_plano(mb, mat, x0, y0, y1, z0, z1, spacing=12.0, bar=1.2, frame=2.5, grid=True)
    else:
        h = z1 - z0
        k_reja_plano(mb, mat, x0, y0, y1, z0, z1, spacing=12.0, bar=1.6, frame=2.5,
                     rails=(z0 + h * 0.33, z0 + h * 0.66))
    # grampas amuradas
    for (ya, za) in ((y0 + 1, z0 + 6), (y1 - 4, z0 + 6), (y0 + 1, z1 - 9), (y1 - 4, z1 - 9)):
        box(mb, mat, xf - 3.0, x0 + 0.5, ya, ya + 3.0, za, za + 3.0)


def k_postigo(mb, x0, y0, y1, z0, z1, mat='MI_Madera'):
    """Hoja de postigo de madera con celosía (dos paños de lamas)."""
    t = 3.5
    f = 6.5
    box(mb, mat, x0, x0 + t, y0, y0 + f, z0, z1)
    box(mb, mat, x0, x0 + t, y1 - f, y1, z0, z1)
    box(mb, mat, x0, x0 + t, y0 + f, y1 - f, z1 - f, z1)
    box(mb, mat, x0, x0 + t, y0 + f, y1 - f, z0, z0 + f + 4.0)
    zm = 0.5 * (z0 + z1)
    box(mb, mat, x0, x0 + t, y0 + f, y1 - f, zm - 4.0, zm + 4.0)
    for (za, zb) in ((z0 + f + 4.0, zm - 4.0), (zm + 4.0, z1 - f)):
        sp = slats_profile(x0 + 0.6, 0.9, za, zb, 5.0, 1.4)
        if sp:
            prism(mb, mat, sp, 'y', y0 + f, y1 - f)


def k_window(mb, wm, xf, y0, y1, zs, zt, o=None):
    """Ventana completa. El vano del muro debe ser (y0, y1, zs-5, zt)."""
    o = o or {}
    fm = o.get('marco', M_ALUMINIO)
    ym = 0.5 * (y0 + y1)
    w = y1 - y0
    # alféizar con pendiente y goterón
    xb = xf - 21.0
    xo = xf + 4.5
    zb = zs - 5.0
    prism(mb, o.get('alfeizar', 'MI_Hormigon'),
          [(xb, zb), (xo - 3.0, zb), (xo - 3.0, zb + 1.0), (xo - 2.0, zb + 1.0), (xo - 2.0, zb),
           (xo, zb), (xo, zs - 1.8), (xo - 0.9, zs - 0.9), (xb, zs)], 'y', y0 - 4.0, y1 + 4.0)
    # moldura saliente (revoque) con dintel
    mm = o.get('moldura')
    if mm:
        mw = 8.0
        cbox(mb, mm, xf - 1.0, xf + 2.5, y0 - mw, y0, zs - 5.0, zt, 0.8, 'z', (0, 1, 1, 0))
        cbox(mb, mm, xf - 1.0, xf + 2.5, y1, y1 + mw, zs - 5.0, zt, 0.8, 'z', (0, 1, 1, 0))
        prism(mb, mm, [(xf - 1.0, zt), (xf + 3.5, zt), (xf + 3.5, zt + mw - 2.0), (xf + 2.3, zt + mw),
                       (xf - 1.0, zt + mw)], 'y', y0 - mw - 1.0, y1 + mw + 1.0)
    # marco y hojas
    fx0, fx1 = xf - 19.0, xf - 13.0
    fw = 5.0
    box(mb, fm, fx0, fx1, y0, y0 + fw, zs, zt)
    box(mb, fm, fx0, fx1, y1 - fw, y1, zs, zt)
    box(mb, fm, fx0, fx1, y0 + fw, y1 - fw, zt - fw, zt)
    box(mb, fm, fx0, fx1, y0 + fw, y1 - fw, zs, zs + fw)
    if w > 70:
        box(mb, fm, fx0 + 0.5, fx1 - 0.5, ym - 2.5, ym + 2.5, zs + fw, zt - fw)
        leaves = ((y0 + fw, ym - 2.5), (ym + 2.5, y1 - fw))
    else:
        leaves = ((y0 + fw, y1 - fw),)
    for (a, b) in leaves:
        box(mb, fm, xf - 17.6, xf - 14.4, a, a + 3.5, zs + fw, zt - fw)
        box(mb, fm, xf - 17.6, xf - 14.4, b - 3.5, b, zs + fw, zt - fw)
        box(mb, fm, xf - 17.6, xf - 14.4, a + 3.5, b - 3.5, zt - fw - 3.5, zt - fw)
        box(mb, fm, xf - 17.6, xf - 14.4, a + 3.5, b - 3.5, zs + fw, zs + fw + 3.5)
    box(mb, 'MI_Vidrio', xf - 16.3, xf - 15.7, y0 + fw, y1 - fw, zs + fw, zt - fw)
    # cortina interior (insinúa habitación)
    if o.get('cortina', True):
        n = max(2, int(w / 24.0))
        pw = (w - 10.0) / n
        for i in range(n):
            ya = y0 + 5.0 + i * pw
            off = 1.6 if (i % 2) else 0.0
            box(mb, M_TELA, xf - 36.0 - off, xf - 35.0 - off, ya, ya + pw + 1.0, zs + 4.0, zt - 3.0)
    # persiana / postigos
    pers = o.get('persiana')
    if pers == 'enrollar':
        closed = o.get('cerrada', 0.5)
        pm = o.get('persiana_mat', 'MI_Madera')
        gx0 = xf - 10.0
        box(mb, fm, gx0, gx0 + 4.0, y0, y0 + 2.5, zs, zt)
        box(mb, fm, gx0, gx0 + 4.0, y1 - 2.5, y1, zs, zt)
        zbp = max(zs + 4.0, zt - closed * (zt - zs))
        sp = slats_profile(gx0 + 1.0, 1.0, zbp, zt - 1.0, 4.5, 0.6)
        if sp:
            prism(mb, pm, sp, 'y', y0 + 1.2, y1 - 1.2)
            box(mb, fm, gx0 + 0.8, gx0 + 3.4, y0 + 1.2, y1 - 1.2, zbp - 3.0, zbp)
        # cinta de la persiana (adentro, al costado)
        box(mb, M_TELA, xf - 33.0, xf - 32.6, y1 + 3.0, y1 + 5.0, zs + 20.0, zt)
    elif pers == 'postigos_abiertos':
        lw = w * 0.5
        k_postigo(mb, xf + 0.5, y0 - lw - 3.0, y0 - 3.0, zs, zt)
        k_postigo(mb, xf + 0.5, y1 + 3.0, y1 + 3.0 + lw, zs, zt)
        for yh in (y0 - 3.0, y1 + 3.0):
            for zh in (zs + 18.0, zt - 18.0):
                cyl(mb, M_HIERRO, (xf + 1.5, yh, zh - 4.0), (xf + 1.5, yh, zh + 4.0), 0.9, 8)
    elif pers == 'postigos_cerrados':
        k_postigo(mb, xf - 7.5, y0 + 0.5, ym - 0.3, zs + 0.5, zt - 0.5)
        k_postigo(mb, xf - 7.5, ym + 0.3, y1 - 0.5, zs + 0.5, zt - 0.5)
    # reja
    if o.get('reja'):
        k_reja_ventana(mb, xf, y0 - 3.0, y1 + 3.0, zs - 4.0, zt + 3.0, o.get('reja'), o.get('reja_mat', M_HIERRO))


def k_umbral(mb, mat, xf, y0, y1, zbase, ztop):
    if ztop - zbase < 0.5:
        return
    prism(mb, mat, [(xf - 12.0, zbase - 2.0), (xf + 24.0, zbase - 2.0), (xf + 24.0, ztop - 1.2),
                    (xf + 22.8, ztop), (xf - 12.0, ztop)], 'y', y0 - 6.0, y1 + 6.0)


def k_door(mb, xf, y0, y1, z0, zt, o=None):
    """Puerta de entrada. El vano del muro debe ser (y0, y1, z0, zt)."""
    o = o or {}
    lm = o.get('hoja', 'MI_Madera')
    fm = o.get('marco', M_HIERRO)
    ban = o.get('banderola', 0.0)
    mx0, mx1 = xf - 12.0, xf - 4.0
    box(mb, fm, mx0, mx1, y0, y0 + 6.0, z0, zt)
    box(mb, fm, mx0, mx1, y1 - 6.0, y1, z0, zt)
    box(mb, fm, mx0, mx1, y0 + 6.0, y1 - 6.0, zt - 6.0, zt)
    ltop = zt - 6.0
    if ban > 0:
        zt0 = zt - 6.0 - ban
        box(mb, fm, mx0, mx1, y0 + 6.0, y1 - 6.0, zt0, zt0 + 5.0)
        box(mb, 'MI_Vidrio', xf - 8.3, xf - 7.7, y0 + 6.0, y1 - 6.0, zt0 + 5.0, zt - 6.0)
        k_reja_plano(mb, M_HIERRO, xf - 6.0, y0 + 6.0, y1 - 6.0, zt0 + 5.0, zt - 6.0, spacing=10.0,
                     bar=1.4, frame=0.0)
        ltop = zt0 - 0.5
    hx0, hx1 = xf - 11.0, xf - 6.5
    ly0, ly1 = y0 + 6.5, y1 - 6.5
    lz0, lz1 = z0 + 1.0, ltop
    box(mb, lm, hx0, hx1, ly0, ly1, lz0, lz1)
    style = o.get('estilo', 'tablero')
    if style == 'tablero':
        st = 11.0
        box(mb, lm, hx1, hx1 + 1.2, ly0, ly0 + st, lz0, lz1)
        box(mb, lm, hx1, hx1 + 1.2, ly1 - st, ly1, lz0, lz1)
        for (za, zb) in ((lz0, lz0 + 22.0), (lz0 + 95.0, lz0 + 109.0), (lz1 - 13.0, lz1)):
            box(mb, lm, hx1, hx1 + 1.2, ly0 + st, ly1 - st, za, zb)
        ymid = 0.5 * (ly0 + ly1)
        box(mb, lm, hx1, hx1 + 1.2, ymid - 5.0, ymid + 5.0, lz0 + 22.0, lz1 - 13.0)
        for (za, zb) in ((lz0 + 22.0, lz0 + 95.0), (lz0 + 109.0, lz1 - 13.0)):
            for (ya, yb) in ((ly0 + st, ymid - 5.0), (ymid + 5.0, ly1 - st)):
                cbox(mb, lm, hx1, hx1 + 0.7, ya + 4.0, yb - 4.0, za + 4.0, zb - 4.0, 0.6, 'z', (0, 1, 1, 0))
    elif style == 'chapa':
        cols, rows = 3, 6
        cw = (ly1 - ly0 - 16.0) / cols
        rh = (lz1 - lz0 - 20.0) / rows
        for i in range(cols):
            for j in range(rows):
                ya = ly0 + 8.0 + i * cw
                za = lz0 + 10.0 + j * rh
                cbox(mb, lm, hx1, hx1 + 0.8, ya + 2.5, ya + cw - 2.5, za + 2.5, za + rh - 2.5, 0.6, 'z', (0, 1, 1, 0))
    elif style == 'vidriada':
        zg0 = lz0 + 105.0
        box(mb, 'MI_Vidrio', hx1 - 2.5, hx1 - 2.0, ly0 + 10.0, ly1 - 10.0, zg0, lz1 - 12.0)
        k_reja_plano(mb, M_HIERRO, hx1 + 0.3, ly0 + 8.0, ly1 - 8.0, zg0 - 2.0, lz1 - 10.0, spacing=11.0,
                     bar=1.4, frame=2.0)
    # picaporte, cerradura
    hy = ly1 - 7.0
    hz = z0 + 100.0
    cyl(mb, M_HIERRO, (hx1, hy, hz), (hx1 + 1.4, hy, hz), 3.0, 12)
    cyl(mb, M_HIERRO, (hx1 + 1.4, hy, hz), (hx1 + 5.0, hy, hz), 0.9, 8)
    box(mb, M_HIERRO, hx1 + 4.2, hx1 + 5.6, hy - 12.0, hy + 0.9, hz - 0.9, hz + 0.9)
    box(mb, M_HIERRO, hx1, hx1 + 0.4, hy - 1.6, hy + 1.6, hz - 12.0, hz - 4.0)
    if o.get('umbral', True):
        k_umbral(mb, o.get('umbral_mat', 'MI_PiedraLaja'), xf, y0, y1, o.get('base_z', Z_VER), z0)
    if o.get('aplique'):
        ya = y1 + 16.0
        cbox(mb, M_HIERRO, xf, xf + 3.0, ya - 6.0, ya + 6.0, zt - 8.0, zt + 10.0, 0.6, 'z')
        cbox(mb, 'MI_Vidrio', xf + 3.0, xf + 10.0, ya - 4.5, ya + 4.5, zt - 6.0, zt + 8.0, 1.0, 'z')
        box(mb, M_HIERRO, xf + 2.0, xf + 11.0, ya - 5.0, ya + 5.0, zt + 8.0, zt + 9.5)


def k_garage_chapa(mb, xf, y0, y1, z0, zt, o=None):
    """Portón de chapa de dos hojas. Vano (y0, y1, z0, zt)."""
    o = o or {}
    mat = o.get('mat', 'MI_Chapa_Gris')
    fm = o.get('marco', M_HIERRO)
    box(mb, fm, xf - 11.0, xf - 5.0, y0, y0 + 5.0, z0, zt)
    box(mb, fm, xf - 11.0, xf - 5.0, y1 - 5.0, y1, z0, zt)
    box(mb, fm, xf - 11.0, xf - 5.0, y0 + 5.0, y1 - 5.0, zt - 5.0, zt)
    ym = 0.5 * (y0 + y1)
    leaves = ((y0 + 5.5, ym - 0.5), (ym + 0.5, y1 - 5.5)) if o.get('hojas', 2) == 2 else ((y0 + 5.5, y1 - 5.5),)
    for (a, b) in leaves:
        zl0, zl1 = z0 + 1.0, zt - 5.5
        box(mb, fm, xf - 10.5, xf - 6.0, a, a + 4.0, zl0, zl1)
        box(mb, fm, xf - 10.5, xf - 6.0, b - 4.0, b, zl0, zl1)
        box(mb, fm, xf - 10.5, xf - 6.0, a + 4.0, b - 4.0, zl1 - 4.0, zl1)
        box(mb, fm, xf - 10.5, xf - 6.0, a + 4.0, b - 4.0, zl0, zl0 + 4.0)
        if o.get('orient', 'v') == 'v':
            prism(mb, mat, ribs_profile_xy(xf - 9.8, 1.2, a + 4.0, b - 4.0, 7.6, 1.6), 'z', zl0 + 4.0, zl1 - 4.0)
        else:
            sp = slats_profile(xf - 9.8, 1.2, zl0 + 4.0, zl1 - 4.0, 24.0, 1.6)
            if sp:
                prism(mb, mat, sp, 'y', a + 4.0, b - 4.0)
        # bisagras
        for zh in (zl0 + 25.0, zl1 - 25.0):
            for yh in (a + 1.0, b - 1.0):
                cyl(mb, fm, (xf - 5.5, yh, zh - 6.0), (xf - 5.5, yh, zh + 6.0), 1.3, 8)
    # manijón y pasador con candado
    zh = z0 + 105.0
    box(mb, fm, xf - 6.0, xf - 3.0, ym - 14.0, ym + 14.0, zh - 1.5, zh + 1.5)
    box(mb, fm, xf - 5.5, xf - 2.0, ym - 2.0, ym + 2.0, zh - 9.0, zh - 1.5)
    box(mb, 'MI_Chapa_Gris', xf - 5.0, xf - 2.5, ym + 3.0, ym + 7.0, zh - 9.0, zh - 3.5)
    box(mb, fm, xf - 6.0, xf - 4.0, ym - 1.0, ym + 1.0, z0 + 1.0, z0 + 40.0)


def k_porton_madera(mb, xf, y0, y1, z0, zt, hojas=3):
    mat = 'MI_Madera'
    box(mb, mat, xf - 12.0, xf - 3.0, y0, y0 + 9.0, z0, zt)
    box(mb, mat, xf - 12.0, xf - 3.0, y1 - 9.0, y1, z0, zt)
    box(mb, mat, xf - 12.0, xf - 3.0, y0 + 9.0, y1 - 9.0, zt - 9.0, zt)
    ia, ib = y0 + 9.0, y1 - 9.0
    box(mb, mat, xf - 12.5, xf - 10.5, ia, ib, z0 + 1.0, zt - 9.0)   # contramarco de fondo
    lw = (ib - ia) / hojas
    for k in range(hojas):
        a = ia + k * lw + 0.8
        b = a + lw - 1.6
        n = max(2, int(round((b - a) / 12.5)))
        pw = (b - a) / n
        for j in range(n):
            ya = a + j * pw + 0.35
            yb = a + (j + 1) * pw - 0.35
            jit = RNG.uniform(-0.35, 0.35)
            box(mb, mat, xf - 10.5 + jit, xf - 6.8 + jit, ya, yb, z0 + 2.0, zt - 10.0)
        box(mb, 'MI_Chapa_Gris', xf - 6.9, xf - 6.4, a, b, z0 + 2.0, z0 + 18.0)
        for zh in (z0 + 30.0, 0.5 * (z0 + zt), zt - 40.0):
            box(mb, M_HIERRO, xf - 6.8, xf - 6.2, a + 2.0, a + 28.0, zh - 2.0, zh + 2.0)
            cyl(mb, M_HIERRO, (xf - 6.0, a + 1.0, zh - 6.0), (xf - 6.0, a + 1.0, zh + 6.0), 1.4, 8)
    yh = ia + lw * 2.0 - 8.0
    box(mb, M_HIERRO, xf - 6.8, xf - 3.5, yh - 1.2, yh + 1.2, z0 + 95.0, z0 + 125.0)


def k_cortina_local(mb, xf, y0, y1, z0, zt):
    """Cortina metálica de enrollar de local, cerrada, con candados."""
    box(mb, M_HIERRO, xf - 9.0, xf - 2.0, y0, y0 + 4.0, z0, zt)
    box(mb, M_HIERRO, xf - 9.0, xf - 2.0, y1 - 4.0, y1, z0, zt)
    sp = slats_profile(xf - 7.0, 1.2, z0 + 8.0, zt, 8.0, 1.0)
    if sp:
        prism(mb, 'MI_Chapa_Gris', sp, 'y', y0 + 2.0, y1 - 2.0)
    box(mb, M_HIERRO, xf - 7.5, xf - 3.5, y0 + 2.0, y1 - 2.0, z0 + 1.0, z0 + 8.0)
    for yc in (y0 + 35.0, y1 - 35.0):
        box(mb, M_HIERRO, xf - 3.5, xf - 1.0, yc - 1.5, yc + 1.5, z0 + 3.0, z0 + 9.0)
        cbox(mb, 'MI_Chapa_Gris', xf - 2.5, xf - 0.5, yc - 2.5, yc + 2.5, z0 + 0.5, z0 + 5.5, 0.4, 'z')
        torus(mb, M_HIERRO, (xf - 1.5, yc, z0 + 6.5), 1.8, 0.35, (1, 0, 0), 10, 4)
    box(mb, M_HIERRO, xf - 3.5, xf - 1.0, 0.5 * (y0 + y1) - 6.0, 0.5 * (y0 + y1) + 6.0, z0 + 12.0, z0 + 14.0)


def k_zocalo(mb, mat, xf, y0, y1, h, gaps, z0=0.0, proud=1.8):
    for (a, b) in interval_minus(y0, y1, gaps):
        prism(mb, mat, [(xf - 1.0, z0), (xf + proud, z0), (xf + proud, h - 1.0), (xf + proud - 1.0, h),
                        (xf - 1.0, h)], 'y', a, b)


def k_cornisa(mb, mat, xf, y0, y1, zb, style=1):
    if style == 1:
        pts = [(xf - 2.0, zb), (xf + 1.5, zb), (xf + 1.5, zb + 4.0), (xf + 4.0, zb + 6.0), (xf + 4.0, zb + 12.0),
               (xf + 6.0, zb + 12.0), (xf + 6.0, zb + 17.0), (xf - 2.0, zb + 17.0)]
    else:
        pts = [(xf - 2.0, zb), (xf + 2.0, zb), (xf + 2.0, zb + 3.0), (xf + 5.0, zb + 3.0), (xf + 5.0, zb + 8.0),
               (xf + 9.0, zb + 14.0), (xf + 12.0, zb + 16.0), (xf + 12.0, zb + 22.0), (xf + 14.0, zb + 22.0),
               (xf + 14.0, zb + 27.0), (xf - 2.0, zb + 27.0)]
        # dentículos
        y = y0 + 8.0
        while y + 5.0 < y1 - 6.0:
            box(mb, mat, xf - 1.0, xf + 4.0, y, y + 5.0, zb - 6.0, zb + 0.5)
            y += 12.0
    prism(mb, mat, pts, 'y', y0, y1)


def k_coping_y(mb, mat, xa, xb, y0, y1, zt):
    """Cupertina sobre un muro (xa..xb, xb del lado de la calle), con goterón y pendiente hacia adentro."""
    prism(mb, mat, [(xa - 3.0, zt - 1.0), (xb + 1.5, zt - 1.0), (xb + 1.5, zt), (xb + 2.3, zt), (xb + 2.3, zt - 1.0),
                    (xb + 3.0, zt - 1.0), (xb + 3.0, zt + 3.2), (xb + 2.2, zt + 4.0), (xa - 3.0, zt + 2.2)],
          'y', y0, y1)


def k_coping_x(mb, mat, ya, yb, x0, x1, zt, inner_side=1):
    """Cupertina a lo largo de X sobre un muro ya..yb; pendiente hacia inner_side (+1 => +y)."""
    if inner_side > 0:
        pts = [(ya + 0.5, zt - 1.0), (yb + 2.5, zt - 1.0), (yb + 2.5, zt + 2.0), (ya + 0.5, zt + 3.8)]
    else:
        pts = [(ya - 2.5, zt - 1.0), (yb - 0.5, zt - 1.0), (yb - 0.5, zt + 3.8), (ya - 2.5, zt + 2.0)]
    prism(mb, mat, pts, 'x', x0, x1)


def k_parapet(mb, wm, xf, y0, y1, zr, zp, t=15.0, coping=None):
    box(mb, wm, xf - t, xf, y0, y1, zr, zp)
    k_coping_y(mb, coping or wm, xf - t, xf, y0 + 0.5, y1 - 0.5, zp)
    xa = xf - t
    # babeta: media caña + reborde con pendiente, del lado de la azotea
    prism(mb, 'MI_Hormigon', [(xa - 10.0, zr + 2.0), (xa + 0.5, zr + 2.0), (xa + 0.5, zr + 12.0)], 'y', y0 + 15.0, y1 - 15.0)
    prism(mb, 'MI_Hormigon', [(xa - 3.5, zr + 22.0), (xa + 0.5, zr + 22.0), (xa + 0.5, zr + 28.0), (xa - 3.5, zr + 26.0)],
          'y', y0 + 15.0, y1 - 15.0)


def k_gargola(mb, xf, yc, zr):
    cbox(mb, 'MI_Hormigon', xf - 16.0, xf + 26.0, yc - 7.0, yc + 7.0, zr + 3.0, zr + 11.0, 1.2, 'x')
    box(mb, 'MI_Hormigon', xf + 18.0, xf + 26.0, yc - 4.0, yc + 4.0, zr + 10.9, zr + 11.6)


def k_medidor_luz(mb, wm, xf, yc, z0):
    """Nicho del medidor de luz: marco saliente de mampostería + gabinete con visor."""
    w, h = 48.0, 62.0
    y0, y1 = yc - w * 0.5, yc + w * 0.5
    cbox(mb, wm, xf - 2.0, xf + 10.0, y0 - 8.0, y0, z0 - 8.0, z0 + h + 8.0, 1.0, 'z')
    cbox(mb, wm, xf - 2.0, xf + 10.0, y1, y1 + 8.0, z0 - 8.0, z0 + h + 8.0, 1.0, 'z')
    prism(mb, wm, [(xf - 2.0, z0 + h), (xf + 12.0, z0 + h), (xf + 12.0, z0 + h + 6.0), (xf + 10.5, z0 + h + 8.0),
                   (xf - 2.0, z0 + h + 8.0)], 'y', y0 - 9.0, y1 + 9.0)
    prism(mb, wm, [(xf - 2.0, z0 - 8.0), (xf + 12.0, z0 - 8.0), (xf + 12.0, z0 - 1.5), (xf + 10.0, z0), (xf - 2.0, z0)],
          'y', y0 - 9.0, y1 + 9.0)
    cbox(mb, 'MI_Chapa_Gris', xf, xf + 7.0, y0 + 1.5, y1 - 1.5, z0 + 1.5, z0 + h - 1.5, 0.8, 'z')
    box(mb, 'MI_Vidrio', xf + 7.0, xf + 7.3, yc - 9.0, yc + 9.0, z0 + h - 28.0, z0 + h - 12.0)
    box(mb, M_HIERRO, xf + 7.0, xf + 7.6, y1 - 6.0, y1 - 4.0, z0 + 24.0, z0 + 34.0)
    box(mb, M_HIERRO, xf + 7.0, xf + 7.2, y0 + 3.0, y1 - 3.0, z0 + 8.0, z0 + 9.0)


def k_medidor_gas(mb, wm, xf, yc, z0):
    w, h = 44.0, 42.0
    y0, y1 = yc - w * 0.5, yc + w * 0.5
    cbox(mb, wm, xf - 2.0, xf + 9.0, y0 - 7.0, y1 + 7.0, z0 + h, z0 + h + 7.0, 1.0, 'y')
    cbox(mb, wm, xf - 2.0, xf + 9.0, y0 - 7.0, y0, z0, z0 + h, 0.8, 'z')
    cbox(mb, wm, xf - 2.0, xf + 9.0, y1, y1 + 7.0, z0, z0 + h, 0.8, 'z')
    box(mb, 'MI_Chapa_Gris', xf, xf + 6.0, y0 + 1.0, y1 - 1.0, z0 + 1.0, z0 + h - 1.0)
    sp = slats_profile(xf + 6.0, 0.4, z0 + h - 16.0, z0 + h - 4.0, 2.4, 0.6)
    if sp:
        prism(mb, 'MI_Chapa_Gris', sp, 'y', y0 + 8.0, y1 - 8.0)
    box(mb, M_HIERRO, xf + 6.0, xf + 6.6, y1 - 6.0, y1 - 4.5, z0 + 15.0, z0 + 22.0)


def k_bajada(mb, xf, y, z0, z1, xoff=8.0, r=3.8):
    """Caño de bajada de la acometida con pipeta. Devuelve el punto de anclaje del cable."""
    x = xf + xoff
    cyl(mb, M_HIERRO, (x, y, z0), (x, y, z1), r, 12)
    z = z0 + 40.0
    while z < z1 - 20.0:
        box(mb, M_HIERRO, xf - 1.0, x + r + 0.6, y - r - 0.8, y + r + 0.8, z, z + 2.5)
        z += 90.0
    # pipeta: curva hacia la calle y abajo
    a = (x, y, z1)
    b = (x + 6.0, y, z1 + 7.0)
    c = (x + 13.0, y, z1 + 4.0)
    d = (x + 15.0, y, z1 - 3.0)
    for p, q in ((a, b), (b, c), (c, d)):
        cyl(mb, M_HIERRO, p, q, r * 1.05, 12)
    blob(mb, M_HIERRO, b, r * 1.1, r * 1.1, r * 1.1)
    blob(mb, M_HIERRO, c, r * 1.1, r * 1.1, r * 1.1)
    # cables que salen de la pipeta
    tube(mb, 'MI_Cable', [d, (d[0] + 1.0, d[1] + 1.0, d[2] - 6.0), (d[0] + 4.0, d[1] + 2.0, d[2] - 9.0)], 0.7)
    return (d[0] + 4.0, d[1] + 2.0, d[2] - 9.0)


def k_numero(mb, xf, yc, zc):
    cbox(mb, M_TELA, xf, xf + 0.9, yc - 10.0, yc + 10.0, zc - 6.0, zc + 6.0, 0.4, 'z')
    for k in range(3):
        y = yc - 6.5 + k * 5.0
        box(mb, M_HIERRO, xf + 0.9, xf + 1.2, y, y + 3.0, zc - 3.5, zc + 3.5)


def k_split(mb, xf, yc, z0, pipe_side=1):
    """Unidad exterior de aire acondicionado split con ménsulas, caños y desagote."""
    w, d, h = 82.0, 30.0, 56.0
    x0 = xf + 6.0
    y0, y1 = yc - w * 0.5, yc + w * 0.5
    cbox(mb, M_AC, x0, x0 + d, y0, y1, z0, z0 + h, 1.5, 'y')
    gy = y0 + 31.0
    gz = z0 + h * 0.5
    cyl(mb, M_HIERRO, (x0 + d - 0.2, gy, gz), (x0 + d + 0.8, gy, gz), 21.0, 24)
    torus(mb, M_AC, (x0 + d + 0.9, gy, gz), 21.5, 0.8, (1, 0, 0), 24, 4)
    for k in (-1, 0, 1):
        box(mb, M_AC, x0 + d + 0.8, x0 + d + 1.6, gy - 21.0, gy + 21.0, gz + k * 7.0 - 0.6, gz + k * 7.0 + 0.6)
    sp = slats_profile(x0 + d - 1.0, 0.5, z0 + 6.0, z0 + h - 6.0, 3.0, 0.5)
    if sp:
        prism(mb, M_AC, sp, 'y', y1 - 26.0, y1 - 4.0)
    for yb in (y0 + 10.0, y1 - 10.0):
        box(mb, M_HIERRO, xf, x0 + d + 3.0, yb - 1.5, yb + 1.5, z0 - 3.0, z0)
        cyl(mb, M_HIERRO, (xf, yb, z0 - 36.0), (x0 + d - 2.0, yb, z0 - 1.5), 1.1, 6)
        box(mb, M_HIERRO, xf - 1.0, xf + 0.8, yb - 3.0, yb + 3.0, z0 - 42.0, z0 + 2.0)
    ys = y1 + 2.0 if pipe_side > 0 else y0 - 2.0
    ye = ys + 14.0 * pipe_side
    for (r, dz) in ((1.3, 12.0), (1.0, 18.0)):
        pts = [(x0 + 10.0, y1 - 2.0 if pipe_side > 0 else y0 + 2.0, z0 + dz), (x0 + 8.0, ys, z0 + dz),
               (x0 + 2.0, ye, z0 + dz - 2.0), (xf + 1.0, ye, z0 + dz - 10.0), (xf - 3.0, ye, z0 + dz - 10.0)]
        tube(mb, M_TELA, pts, r)
    tube(mb, 'MI_Cable', [(x0 + 14.0, y0 + 8.0, z0), (x0 + 16.0, y0 + 9.0, z0 - 20.0), (x0 + 13.0, y0 + 11.0, z0 - 45.0),
                          (x0 + 15.0, y0 + 10.0, z0 - 70.0)], 0.8)


def k_tanque_plastico(mb, cx, cy, z0, r=55.0, h=120.0, base='hormigon'):
    if base == 'hormigon':
        cbox(mb, 'MI_Hormigon', cx - r - 8.0, cx + r + 8.0, cy - r - 8.0, cy + r + 8.0, z0, z0 + 18.0, 1.5, 'z')
        zt = z0 + 18.0
    else:
        zt = z0 + 70.0
        for sx in (-1, 1):
            for sy in (-1, 1):
                box(mb, M_HIERRO, cx + sx * (r - 6.0) - 2.5, cx + sx * (r - 6.0) + 2.5,
                    cy + sy * (r - 6.0) - 2.5, cy + sy * (r - 6.0) + 2.5, z0, zt)
        for sy in (-1, 1):
            box(mb, M_HIERRO, cx - r, cx + r, cy + sy * (r - 6.0) - 2.5, cy + sy * (r - 6.0) + 2.5, zt - 5.0, zt)
        for sx in (-1, 1):
            box(mb, M_HIERRO, cx + sx * (r - 6.0) - 2.5, cx + sx * (r - 6.0) + 2.5, cy - r, cy + r, zt - 5.0, zt)
        box(mb, M_HIERRO, cx - r, cx + r, cy - r, cy + r, zt - 1.0, zt)
        cyl(mb, M_HIERRO, (cx - r + 6, cy - r + 6, z0 + 10), (cx + r - 6, cy + r - 6, zt - 6), 1.0, 6)
    cyl(mb, M_PLASTICO, (cx, cy, zt), (cx, cy, zt + h), r, 24)
    for k in (0.2, 0.45, 0.7):
        cyl(mb, M_PLASTICO, (cx, cy, zt + h * k), (cx, cy, zt + h * k + 4.0), r + 1.5, 24)
    cone(mb, M_PLASTICO, (cx, cy, zt + h), (cx, cy, zt + h + 18.0), r, r * 0.38, 24)
    cyl(mb, M_PLASTICO, (cx, cy, zt + h + 18.0), (cx, cy, zt + h + 24.0), r * 0.42, 20)
    cyl(mb, M_HIERRO, (cx + r - 4.0, cy, zt + 8.0), (cx + r + 22.0, cy, zt + 8.0), 2.2, 8)
    cyl(mb, M_HIERRO, (cx + r + 22.0, cy, zt + 8.0), (cx + r + 22.0, cy, z0 - 2.0), 2.2, 8)
    cyl(mb, M_HIERRO, (cx, cy + r - 4.0, zt + h - 12.0), (cx, cy + r + 16.0, zt + h - 12.0), 1.6, 8)
    cyl(mb, M_HIERRO, (cx, cy + r + 16.0, zt + h - 12.0), (cx, cy + r + 16.0, z0 - 2.0), 1.6, 8)
    return zt + h + 24.0


def k_planta(mb, cx, cy, z0, s=1.0, maceta=True):
    zt = z0
    if maceta:
        cone(mb, 'MI_Ladrillo', (cx, cy, z0), (cx, cy, z0 + 28.0 * s), 11.0 * s, 15.0 * s, 14)
        cyl(mb, M_TIERRA, (cx, cy, z0 + 25.0 * s), (cx, cy, z0 + 27.0 * s), 14.0 * s, 14)
        zt = z0 + 26.0 * s
    n = RNG.randint(3, 5)
    for k in range(n):
        a = RNG.uniform(0, 2 * math.pi)
        rr = RNG.uniform(3.0, 10.0) * s
        blob(mb, M_FOLLAJE, (cx + rr * math.cos(a), cy + rr * math.sin(a), zt + RNG.uniform(12.0, 30.0) * s),
             RNG.uniform(10.0, 16.0) * s, RNG.uniform(10.0, 16.0) * s, RNG.uniform(12.0, 20.0) * s,
             yaw=RNG.uniform(0, 180), steps=(6, 8))


def k_cantero(mb, x0, x1, y0, y1, zbase, h=12.0):
    t = 6.0
    box(mb, 'MI_Ladrillo', x0, x1, y0, y0 + t, zbase, zbase + h)
    box(mb, 'MI_Ladrillo', x0, x1, y1 - t, y1, zbase, zbase + h)
    box(mb, 'MI_Ladrillo', x0, x0 + t, y0 + t, y1 - t, zbase, zbase + h)
    box(mb, 'MI_Ladrillo', x1 - t, x1, y0 + t, y1 - t, zbase, zbase + h)
    box(mb, M_TIERRA, x0 + t, x1 - t, y0 + t, y1 - t, zbase, zbase + h - 3.0)


def k_antena(mb, cx, cy, z0):
    cyl(mb, M_HIERRO, (cx, cy, z0), (cx + 4.0, cy - 3.0, z0 + 330.0), 1.8, 8)
    top = (cx + 4.0, cy - 3.0, z0 + 330.0)
    for k, L in enumerate((150.0, 120.0, 100.0, 80.0, 60.0)):
        z = top[2] - 10.0 - k * 16.0
        x = cx + 4.0 * (z - z0) / 330.0
        cyl(mb, M_HIERRO, (x - 2.0, cy - 3.0 - L * 0.5, z), (x - 2.0, cy - 3.0 + L * 0.5, z), 0.7, 6)
    cyl(mb, M_HIERRO, (top[0] - 2.0, top[1], top[2] - 4.0), (top[0] - 50.0, top[1] + 4.0, top[2] - 16.0), 0.9, 6)
    for (dx, dy) in ((-150.0, -120.0), (-130.0, 140.0), (110.0, 10.0)):
        tube(mb, 'MI_Cable', catenary((cx + 2.0, cy - 1.5, z0 + 200.0), (cx + dx, cy + dy, z0 + 2.0), 6.0, 8), 0.3, 4)
    tube(mb, 'MI_Cable', catenary((cx + 2.0, cy - 2.0, z0 + 300.0), (cx + 10.0, cy + 2.0, z0 + 3.0), 25.0, 10), 0.5, 5)


# =====================================================================================
# CASCARÓN DE CASA
# =====================================================================================
def shell(mb, W, xf, depth, zr, zp, wm, side_mat, holes, floors=(), parapet=True, parapet_mat=None,
          roof=True, coping_mat=None, facade_top=None):
    """Muros de fachada (con vanos), medianeras, contrafrente, azotea y losas interiores."""
    t = WALL_T
    xb = xf - depth
    ftop = facade_top if facade_top is not None else zr
    wall_holes(mb, wm, xf - t, xf, 0.0, W, 0.0, ftop, holes)
    if parapet:
        k_parapet(mb, parapet_mat or wm, xf, 0.0, W, zr, zp, 15.0, coping_mat)
    side_top = zp if parapet else zr
    for (y0, y1, inner) in ((0.0, 15.0, 1), (W - 15.0, W, -1)):
        box(mb, side_mat, xb, xf - t, y0, y1, 0.0, zr)
        if side_top > zr:
            box(mb, side_mat, xb, xf - 15.0, y0, y1, zr, side_top)
            k_coping_x(mb, coping_mat or side_mat, y0, y1, xb - 2.0, xf - 15.5, side_top, inner)
    box(mb, side_mat, xb, xb + t, 15.0, W - 15.0, 0.0, side_top)
    if parapet:
        prism(mb, coping_mat or side_mat, [(xb - 3.0, side_top - 1.0), (xb + t + 3.0, side_top - 1.0),
                                          (xb + t + 3.0, side_top + 2.0), (xb - 3.0, side_top + 3.5)],
              'y', 15.5, W - 15.5)
    if roof:
        box(mb, 'MI_Hormigon', xb + t, xf - 15.0, 15.0, W - 15.0, zr - 18.0, zr + 2.0)
    box(mb, 'MI_Hormigon', xb + t, xf - t, 15.0, W - 15.0, 0.0, Z_PISO)
    for zf in floors:
        box(mb, 'MI_Hormigon', xb + t, xf - t, 15.0, W - 15.0, zf - 15.0, zf)
    mb.col(xb, xf, 0.0, W, 0.0, zr + 2.0)
    if side_top > zr:
        mb.col(xf - 15.0, xf, 0.0, W, zr, side_top)
        mb.col(xb, xf, 0.0, 15.0, zr, side_top)
        mb.col(xb, xf, W - 15.0, W, zr, side_top)
        mb.col(xb, xb + t, 0.0, W, zr, side_top)


def win_hole(y0, y1, zs, zt):
    return (y0, y1, zs - 5.0, zt)


# ---------------------------------------------------------------------------------
# Lote A: casa baja
# ---------------------------------------------------------------------------------
def build_casa_a(W):
    mb = MB('CasaA')
    wm, sm_ = 'MI_Revoque_Blanco', 'MI_Revoque_Gris'
    xf, depth = 0.0, 1150.0
    xb = xf - depth
    zr, zp = 345.0, 428.0
    gar = (40.0, 310.0, Z_VER, 245.0)
    door = (365.0, 455.0, Z_PISO, 240.0)
    win = (545.0, 705.0, 100.0, 240.0)
    piece('A cascaron', shell, mb, W, xf, depth, zr, zp, wm, sm_, [gar, door, win_hole(*win)])
    piece('A ventana', k_window, mb, wm, xf, win[0], win[1], win[2], win[3],
          dict(reja='barrotes', persiana='enrollar', cerrada=0.55, marco=M_ALUMINIO, moldura=wm,
               persiana_mat='MI_Madera'))
    piece('A puerta', k_door, mb, xf, door[0], door[1], door[2], door[3],
          dict(hoja='MI_Madera', estilo='tablero', aplique=True))
    piece('A porton', k_garage_chapa, mb, xf, gar[0], gar[1], gar[2], gar[3], dict(mat='MI_Chapa_Gris', orient='v'))
    piece('A zocalo', k_zocalo, mb, 'MI_Revoque_Gris', xf, 0.0, W, 52.0,
          [(gar[0] - 1.0, gar[1] + 1.0), (door[0] - 6.0, door[1] + 6.0)])
    piece('A cornisa', k_cornisa, mb, wm, xf, 0.0, W, zr - 16.0, 1)
    piece('A medidor luz', k_medidor_luz, mb, wm, xf, 785.0, 125.0)
    piece('A medidor gas', k_medidor_gas, mb, wm, xf, 785.0, 58.0)
    anc = piece('A bajada', k_bajada, mb, xf, 838.0, 190.0, 462.0)
    piece('A numero', k_numero, mb, xf, 337.0, 205.0)
    piece('A split', k_split, mb, xf, 781.0, 262.0, -1)
    piece('A gargola', k_gargola, mb, xf, 520.0, zr)
    piece('A gargola2', k_gargola, mb, xf, 120.0, zr)
    piece('A tanque', k_tanque_plastico, mb, xb + 260.0, 250.0, zr + 2.0, 55.0, 120.0, 'hormigon')
    piece('A antena', k_antena, mb, xb + 420.0, 640.0, zr + 2.0)
    piece('A caja tv', cbox, mb, 'MI_Chapa_Gris', xf, xf + 6.0, 494.0, 506.0, 196.0, 214.0, 0.6, 'z')
    mb.anchors = {'power': anc or (xf + 25.0, 838.0, 455.0),
                  'tel': [(xf + 2.0, 150.0, 395.0), (xf + 2.0, 700.0, 386.0)],
                  'run': [(257.0, 2.5), (252.0, 3.0)], 'xf': xf}
    return mb


# ---------------------------------------------------------------------------------
# Lote B: casa antigua con retiro y jardín, reja baja
# ---------------------------------------------------------------------------------
def k_pilastra(mb, mat, xf, y0, y1, z0, z1):
    cbox(mb, mat, xf - 1.0, xf + 7.0, y0 - 3.0, y1 + 3.0, z0, z0 + 55.0, 1.0, 'z')
    prism(mb, mat, [(xf - 1.0, z0 + 55.0), (xf + 7.0, z0 + 55.0), (xf + 4.0, z0 + 60.0), (xf - 1.0, z0 + 60.0)],
          'y', y0 - 3.0, y1 + 3.0)
    box(mb, mat, xf - 1.0, xf + 4.0, y0, y1, z0 + 60.0, z1 - 24.0)
    cbox(mb, mat, xf - 1.0, xf + 7.0, y0 - 2.0, y1 + 2.0, z1 - 24.0, z1 - 16.0, 0.8, 'y')
    cbox(mb, mat, xf - 1.0, xf + 10.0, y0 - 4.0, y1 + 4.0, z1 - 16.0, z1 - 6.0, 1.0, 'y')
    box(mb, mat, xf - 1.0, xf + 12.0, y0 - 5.0, y1 + 5.0, z1 - 6.0, z1)


def k_pilar(mb, mat, y0, y1, h, cap=True, x0=-26.0, x1=2.0):
    cbox(mb, mat, x0, x1, y0, y1, 0.0, h, 1.0, 'z')
    if cap:
        cbox(mb, mat, x0 - 2.5, x1 + 2.5, y0 - 2.5, y1 + 2.5, h, h + 6.0, 1.5, 'y')
        cone(mb, mat, ((x0 + x1) * 0.5, (y0 + y1) * 0.5, h + 6.0), ((x0 + x1) * 0.5, (y0 + y1) * 0.5, h + 13.0),
             (x1 - x0) * 0.62, 1.0, 4)


def k_cerco_bajo(mb, wm, W, gate, med):
    """Reja baja de frente (≈120 cm) con lanzas, muro bajo, pilares de mampostería y pilar de medidor."""
    hm = 45.0
    for (a, b) in interval_minus(0.0, W, [gate]):
        box(mb, wm, -20.0, 0.0, a, b, 0.0, hm)
        k_coping_y(mb, 'MI_Hormigon', -20.0, 0.0, a + 0.2, b - 0.2, hm)
    pillars = [(0.0, 30.0), (gate[0] - 30.0, gate[0]), (gate[1], gate[1] + 30.0), (W - 30.0, W)]
    for (a, b) in pillars:
        k_pilar(mb, wm, a, b, 125.0)
    # pilar de medidor (más alto y ancho) con caño de bajada
    cbox(mb, wm, -32.0, 4.0, med[0], med[1], 0.0, 185.0, 1.0, 'z')
    cbox(mb, wm, -34.0, 6.0, med[0] - 2.5, med[1] + 2.5, 185.0, 191.0, 1.5, 'y')
    k_medidor_luz(mb, wm, 4.0, 0.5 * (med[0] + med[1]), 95.0)
    anc = k_bajada(mb, -14.0, 0.5 * (med[0] + med[1]), 191.0, 380.0, xoff=0.0, r=3.2)
    # paños de reja
    edges = sorted(pillars + [med])
    for i in range(len(edges) - 1):
        a, b = edges[i][1], edges[i + 1][0]
        if b - a < 5.0 or (abs(a - gate[0]) < 1.0 and abs(b - gate[1]) < 1.0):
            continue
        k_reja_plano(mb, M_HIERRO, -11.0, a + 0.5, b - 0.5, hm + 2.0, 112.0, spacing=12.0, bar=1.6, frame=0.0,
                     rails=(hm + 12.0, 102.0), lanzas=9.0)
    # portón peatonal
    g0, g1 = gate[0] + 1.5, gate[1] - 1.5
    box(mb, 'MI_Hormigon', -22.0, 2.0, gate[0], gate[1], 0.0, Z_VER + 6.0)
    k_reja_plano(mb, M_HIERRO, -11.5, g0, g1, Z_VER + 7.0, 118.0, spacing=11.0, bar=1.6, frame=2.6,
                 rails=(Z_VER + 20.0, 100.0), lanzas=8.0)
    for zh in (Z_VER + 25.0, 105.0):
        cyl(mb, M_HIERRO, (-10.0, g0 - 0.6, zh - 5.0), (-10.0, g0 - 0.6, zh + 5.0), 1.2, 8)
    box(mb, M_HIERRO, -13.0, -6.0, g1 - 6.0, g1 + 1.0, 88.0, 94.0)
    mb.col(-34.0, 6.0, 0.0, W, 0.0, 125.0)
    return anc


def build_casa_b(W):
    mb = MB('CasaB')
    wm, sm_ = 'MI_Revoque_VerdeAgua', 'MI_Revoque_Gris'
    xf, depth = -300.0, 1100.0
    xb = xf - depth
    zr, zp = 380.0, 470.0
    z_patio = 24.0
    w1 = (100.0, 240.0, 95.0, 315.0)
    w2 = (600.0, 740.0, 95.0, 315.0)
    door = (365.0, 475.0, 40.0, 320.0)
    piece('B cascaron', shell, mb, W, xf, depth, zr, zp, wm, sm_, [win_hole(*w1), win_hole(*w2), door])
    piece('B ventana1', k_window, mb, wm, xf, w1[0], w1[1], w1[2], w1[3],
          dict(reja='barrotes', persiana='postigos_cerrados', marco='MI_Madera', moldura=wm, alfeizar='MI_PiedraLaja'))
    piece('B ventana2', k_window, mb, wm, xf, w2[0], w2[1], w2[2], w2[3],
          dict(reja='barrotes', persiana='postigos_abiertos', marco='MI_Madera', moldura=wm, alfeizar='MI_PiedraLaja'))
    piece('B puerta', k_door, mb, xf, door[0], door[1], door[2], door[3],
          dict(hoja='MI_Madera', estilo='tablero', banderola=62.0, marco='MI_Madera', base_z=z_patio,
               umbral_mat='MI_PiedraLaja'))
    piece('B escalon', k_umbral, mb, 'MI_PiedraLaja', xf + 24.0, door[0] - 10.0, door[1] + 10.0, z_patio, z_patio + 8.0)
    piece('B pilastra1', k_pilastra, mb, wm, xf, 15.0, 45.0, 0.0, zr - 27.0)
    piece('B pilastra2', k_pilastra, mb, wm, xf, W - 45.0, W - 15.0, 0.0, zr - 27.0)
    piece('B cornisa', k_cornisa, mb, wm, xf, 0.0, W, zr - 27.0, 2)
    piece('B zocalo', k_zocalo, mb, 'MI_PiedraLaja', xf, 0.0, W, 62.0, [(door[0] - 6.0, door[1] + 6.0)], 0.0, 2.2)
    # paneles en relieve del parapeto + copones
    for (a, b) in ((60.0, 340.0), (500.0, 806.0)):
        for (pa, pb, qa, qb) in ((a, b, zr + 18.0, zr + 21.0), (a, b, zp - 22.0, zp - 19.0),
                                 (a, a + 3.0, zr + 18.0, zp - 19.0), (b - 3.0, b, zr + 18.0, zp - 19.0)):
            box(mb, wm, xf - 1.0, xf + 1.5, pa, pb, qa, qb)
    for yc in (30.0, W - 30.0):
        cbox(mb, wm, xf - 14.0, xf + 2.0, yc - 12.0, yc + 12.0, zp + 3.0, zp + 16.0, 1.0, 'z')
        blob(mb, wm, (xf - 6.0, yc, zp + 30.0), 11.0, 11.0, 14.0)
        cone(mb, wm, (xf - 6.0, yc, zp + 40.0), (xf - 6.0, yc, zp + 52.0), 5.0, 0.5, 10)
    # patio, canteros, plantas
    box(mb, 'MI_Baldosa', xf, -20.0, 0.0, W, 0.0, z_patio)
    mb.col(xf, 0.0, 0.0, W, 0.0, z_patio)
    piece('B cantero1', k_cantero, mb, -62.0, -20.0, 40.0, 330.0, z_patio)
    piece('B cantero2', k_cantero, mb, xf, xf + 45.0, 560.0, 790.0, z_patio)
    for (cx, cy, s) in ((-41.0, 90.0, 1.3), (-41.0, 190.0, 1.0), (-41.0, 280.0, 1.5), (xf + 22.0, 620.0, 1.6),
                        (xf + 22.0, 730.0, 1.2)):
        piece('B planta', k_planta, mb, cx, cy, z_patio + 9.0, s, False)
    piece('B maceta', k_planta, mb, xf + 35.0, door[1] + 22.0, z_patio, 1.0, True)
    anc = piece('B cerco', k_cerco_bajo, mb, wm, W, (365.0, 475.0), (690.0, 750.0))
    piece('B tanque', k_tanque_plastico, mb, xb + 240.0, 640.0, zr + 2.0, 50.0, 110.0, 'metal')
    mb.anchors = {'power': anc or (-10.0, 720.0, 378.0), 'tel': [(xf + 2.0, 62.0, 338.0)], 'run': None, 'xf': xf}
    return mb


# ---------------------------------------------------------------------------------
# Lote C: dos plantas con balcón y terraza
# ---------------------------------------------------------------------------------
def k_losa_balcon(mb, mat, xf, y0, y1, ztop, proj, th=17.0):
    prism(mb, mat, [(xf - 30.0, ztop - th), (xf + proj - 4.0, ztop - th), (xf + proj - 4.0, ztop - th + 1.2),
                    (xf + proj - 3.0, ztop - th + 1.2), (xf + proj - 3.0, ztop - th), (xf + proj, ztop - th),
                    (xf + proj, ztop - 2.6), (xf + proj - 1.2, ztop - 1.5), (xf, ztop), (xf - 30.0, ztop)],
          'y', y0, y1)
    mb.col(xf, xf + proj, y0, y1, ztop - th, ztop)


def k_baranda_hierro(mb, xf, y0, y1, zb, proj, h=95.0, mat=M_HIERRO):
    xe = xf + proj - 6.0
    k_reja_plano(mb, mat, xe, y0 + 2.0, y1 - 2.0, zb, zb + h - 5.0, axis='y', spacing=12.0, bar=1.6, frame=0.0,
                 rails=(zb + 6.0, zb + 70.0))
    n = max(2, int(round((y1 - y0) / 120.0)))
    for k in range(n + 1):
        yc = y0 + 2.0 + (y1 - y0 - 4.0) * k / n
        box(mb, mat, xe - 1.2, xe + 2.8, yc - 2.0, yc + 2.0, zb, zb + h - 4.0)
    cbox(mb, mat, xe - 1.7, xe + 3.3, y0 + 0.5, y1 - 0.5, zb + h - 5.0, zb + h, 0.8, 'y')
    for (yf, ff) in ((y0 + 2.0, y0 + 2.0), (y1 - 2.0 - 1.6, y1 - 2.0 - 1.6)):
        k_reja_plano(mb, mat, ff, xf, xe, zb, zb + h - 5.0, axis='x', spacing=12.0, bar=1.6, frame=0.0,
                     rails=(zb + 6.0, zb + 70.0))
        cbox(mb, mat, xf, xe + 3.3, ff - 1.7, ff + 3.3, zb + h - 5.0, zb + h, 0.8, 'x')
    if CAPS.get('torus_ok'):
        y = y0 + 14.0
        while y < y1 - 14.0:
            torus(mb, mat, (xe + 0.8, y, zb + 38.0), 4.6, 0.45, (1, 0, 0), 14, 4)
            y += 24.0
    mb.col(xe - 2.0, xe + 3.5, y0, y1, zb, zb + h)


def build_casa_c(W):
    mb = MB('CasaC')
    wm, sm_ = 'MI_Revoque_Amarillo', 'MI_Ladrillo'
    xf, depth = 0.0, 1100.0
    xb = xf - depth
    zpa = 330.0
    zr, zp = 630.0, 720.0
    port = (35.0, 335.0, Z_VER, 270.0)
    door = (385.0, 475.0, Z_PISO, 240.0)
    win = (540.0, 700.0, 105.0, 240.0)
    bdoor = (100.0, 280.0, zpa + 15.0, 560.0)
    win2 = (470.0, 690.0, 430.0, 560.0)
    holes = [port, door, win_hole(*win), bdoor, win_hole(*win2)]
    piece('C cascaron', shell, mb, W, xf, depth, zr, zp, wm, sm_, holes, floors=(zpa,))
    piece('C porton', k_porton_madera, mb, xf, port[0], port[1], port[2], port[3], 3)
    piece('C puerta', k_door, mb, xf, door[0], door[1], door[2], door[3],
          dict(hoja='MI_Chapa_Verde', estilo='chapa', marco=M_HIERRO, umbral_mat='MI_Hormigon'))
    piece('C ventana', k_window, mb, wm, xf, win[0], win[1], win[2], win[3],
          dict(reja='cuadricula', persiana='enrollar', cerrada=0.3, marco=M_ALUMINIO, persiana_mat=M_TELA))
    piece('C balcon puerta', k_window, mb, wm, xf, bdoor[0], bdoor[1], bdoor[2] + 5.0, bdoor[3],
          dict(persiana='enrollar', cerrada=0.4, marco=M_ALUMINIO, persiana_mat=M_TELA, alfeizar='MI_Hormigon'))
    piece('C ventana PA', k_window, mb, wm, xf, win2[0], win2[1], win2[2], win2[3],
          dict(persiana='enrollar', cerrada=0.7, marco=M_ALUMINIO, persiana_mat=M_TELA))
    piece('C losa balcon', k_losa_balcon, mb, 'MI_Hormigon', xf, 15.0, W - 15.0, zpa + 6.0, 110.0)
    piece('C baranda', k_baranda_hierro, mb, xf, 15.0, W - 15.0, zpa + 6.0, 110.0)
    piece('C zocalo', k_zocalo, mb, 'MI_Ladrillo', xf, 0.0, W, 55.0, [(port[0] - 1.0, port[1] + 1.0),
                                                                      (door[0] - 6.0, door[1] + 6.0)])
    piece('C cornisa', k_cornisa, mb, wm, xf, 0.0, W, zr - 17.0, 1)
    piece('C medidor', k_medidor_luz, mb, wm, xf, 770.0, 120.0)
    piece('C gas', k_medidor_gas, mb, wm, xf, 770.0, 50.0)
    piece('C numero', k_numero, mb, xf, 360.0, 200.0)
    piece('C split', k_split, mb, xf, 361.0, zpa + 50.0, 1)
    # caño pluvial con gárgola
    piece('C gargola', k_gargola, mb, xf, 845.0, zr)
    piece('C pluvial', cyl, mb, M_ALUMINIO, (xf + 9.0, 845.0, zr + 2.0), (xf + 9.0, 845.0, 25.0), 5.5, 14)
    piece('C pluvial pie', cyl, mb, M_ALUMINIO, (xf + 9.0, 845.0, 25.0), (xf + 22.0, 845.0, 20.0), 5.5, 14)
    for zc in (120.0, 260.0, 420.0, 560.0):
        piece('C abrazadera', box, mb, M_HIERRO, xf - 1.0, xf + 15.0, 838.0, 852.0, zc, zc + 3.0)
    # macetas del balcón
    for (cy, s) in ((720.0, 1.1), (770.0, 1.4), (815.0, 0.9), (60.0, 1.2)):
        piece('C maceta', k_planta, mb, xf + 70.0 + RNG.uniform(-10, 10), cy, zpa + 6.0, s, True)
    # torre de tanque con escalera
    tx0, tx1, ty0, ty1 = xb + 70.0, xb + 240.0, 540.0, 710.0
    piece('C torre', cbox, mb, wm, tx0, tx1, ty0, ty1, zr, zr + 190.0, 1.5, 'z')
    piece('C torre cupertina', cbox, mb, 'MI_Hormigon', tx0 - 4.0, tx1 + 4.0, ty0 - 4.0, ty1 + 4.0, zr + 190.0,
          zr + 197.0, 1.5, 'y')
    piece('C tanque', k_tanque_plastico, mb, 0.5 * (tx0 + tx1), 0.5 * (ty0 + ty1), zr + 197.0, 58.0, 125.0, 'hormigon')
    for yr in (610.0, 650.0):
        piece('C escalera', cyl, mb, M_HIERRO, (tx1 + 12.0, yr, zr + 2.0), (tx1 + 12.0, yr, zr + 230.0), 1.3, 8)
    for k in range(8):
        zz = zr + 25.0 + k * 28.0
        piece('C peldano', cyl, mb, M_HIERRO, (tx1 + 12.0, 610.0, zz), (tx1 + 12.0, 650.0, zz), 1.0, 6)
    for zz in (zr + 40.0, zr + 180.0):
        for yr in (610.0, 650.0):
            box(mb, M_HIERRO, tx1, tx1 + 12.0, yr - 1.0, yr + 1.0, zz, zz + 2.0)
    mb.col(tx0, tx1, ty0, ty1, zr, zr + 197.0)
    mb.anchors = {'power': (xf + 3.0, 822.0, 700.0),
                  'tel': [(xf + 2.0, 740.0, 680.0), (xf + 2.0, 380.0, 596.0)],
                  'run': [(290.0, 2.5), (284.0, 2.5)], 'xf': xf}
    # gancho de retención de la acometida y bajada por la fachada hasta el balcón
    piece('C gancho', cyl, mb, M_HIERRO, (xf - 2.0, 822.0, 700.0), (xf + 6.0, 822.0, 700.0), 1.0, 6)
    piece('C cable fachada', tube, mb, 'MI_Cable',
          [(xf + 6.0, 822.0, 699.0), (xf + 3.0, 821.0, 680.0), (xf + 2.5, 818.0, 600.0), (xf + 2.5, 790.0, 560.0),
           (xf + 2.5, 712.0, 548.0), (xf - 2.0, 712.0, 546.0)], 0.7)
    return mb


# ---------------------------------------------------------------------------------
# Lote D: chalet con techo de tejas, balaustrada y reja alta con portón corredizo
# ---------------------------------------------------------------------------------
def baluster_template(mat):
    key = ('balaustre', mat)
    if key in _TEMPLATES:
        return _TEMPLATES[key]
    m = new_mesh()
    prof = [(4.6, 0.0), (4.6, 4.0), (3.3, 6.0), (3.5, 10.0), (5.8, 22.0), (6.1, 28.0), (4.2, 40.0), (2.7, 48.0),
            (3.3, 52.0), (3.1, 55.0), (4.6, 58.0), (4.6, 62.0)]
    ok = False
    if CAPS.get('revolve_ok'):
        try:
            _revolve_raw(m, popts(mat, CAPS.get('revolve_flip', False)), T(),
                         [unreal.Vector2D(r, z) for (r, z) in prof], 12)
            ok = True
        except Exception as e:
            err_once('revolve', 'append_revolve_path falló (%s); balaustres con conos' % e)
            CAPS['revolve_ok'] = False
    if not ok:
        one = _One(m)
        for i in range(len(prof) - 1):
            (ra, za), (rb, zb) = prof[i], prof[i + 1]
            cone(one, mat, (0.0, 0.0, za), (0.0, 0.0, zb), ra, rb, 10)
    _TEMPLATES[key] = m
    return m


_TEMPLATES = {}


def k_balaustrada(mb, mat, xf, y0, y1, zb, proj):
    """Balaustrada de balcón: zócalo, balaustres torneados, pilarcitos y pasamanos, con retornos laterales."""
    xe = xf + proj
    tpl = baluster_template(mat)
    cbox(mb, mat, xe - 17.0, xe - 1.0, y0, y1, zb - 1.5, zb + 10.0, 1.0, 'y', (0, 1, 1, 0))
    for yy in (y0, y1 - 16.0):
        cbox(mb, mat, xf, xe - 17.0, yy, yy + 16.0, zb - 1.5, zb + 10.0, 1.0, 'x', (0, 1, 1, 0))
    posts_y = [y0, 0.5 * (y0 + y1) - 11.0, y1 - 22.0]
    for py in posts_y:
        cbox(mb, mat, xe - 20.0, xe, py, py + 22.0, zb - 1.5, zb + 84.0, 1.0, 'z')
        cbox(mb, mat, xe - 22.0, xe + 2.0, py - 2.0, py + 24.0, zb + 84.0, zb + 90.0, 1.2, 'y')
    xc = xe - 9.0
    y = y0 + 32.0
    while y < y1 - 30.0:
        if not any(py - 8.0 < y < py + 30.0 for py in posts_y):
            append_into(mb.m(mat), tpl, T((xc, y, zb + 10.0)))
        y += 15.0
    x = xf + 14.0
    while x < xe - 26.0:
        for yy in (y0 + 8.0, y1 - 8.0):
            append_into(mb.m(mat), tpl, T((x, yy, zb + 10.0)))
        x += 15.0
    prism(mb, mat, [(xe - 19.0, zb + 72.0), (xe + 1.0, zb + 72.0), (xe + 1.0, zb + 79.0), (xe - 2.0, zb + 82.0),
                    (xe - 16.0, zb + 82.0), (xe - 19.0, zb + 79.0)], 'y', y0, y1)
    for yy in (y0, y1 - 16.0):
        prism(mb, mat, [(yy - 1.0, zb + 72.0), (yy + 17.0, zb + 72.0), (yy + 17.0, zb + 80.0), (yy + 14.0, zb + 82.0),
                        (yy + 2.0, zb + 82.0), (yy - 1.0, zb + 80.0)], 'x', xf, xe - 19.0)
    mb.col(xe - 20.0, xe, y0, y1, zb, zb + 90.0)


def k_techo_tejas(mb, W, xf, xb, z_e, ang, over=45.0, th=12.0, side_mat='MI_Revoque_Gris'):
    """Techo a dos aguas con cumbrera paralela a la calle; hiladas de tejas en el faldón frontal."""
    ta = math.tan(math.radians(ang))
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    xr = 0.5 * (xf + xb)
    ef = xf + over
    eb = xb - over
    run = ef - xr
    zr_ = z_e + run * ta
    Ls = run / ca
    # faldón frontal con hiladas (dientes de sierra)
    dirv = (-ca, sa)
    nrm = (sa, ca)

    def P(s, off):
        return (ef + s * dirv[0] + off * nrm[0], z_e + s * dirv[1] + off * nrm[1])
    row = 33.0
    lip = 2.6
    n = max(2, int(Ls / row))
    top = [P(0.0, th + lip)]
    for i in range(1, n):
        s = i * row
        top.append(P(s, th))
        top.append(P(s, th + lip))
    top.append(P(Ls, th))
    poly = [P(0.0, 0.0), P(Ls, 0.0)] + list(reversed(top))
    prism(mb, 'MI_Tejas', poly, 'y', 0.0, W)
    # faldón trasero
    tb = th / ca
    prism(mb, 'MI_Tejas', [(eb, z_e), (xr, zr_), (xr, zr_ + tb), (eb, z_e + tb)], 'y', 0.0, W)
    # cumbrera
    zc = zr_ + tb + 1.0
    cyl(mb, 'MI_Tejas', (xr, 0.0, zc), (xr, W, zc), 11.0, 12)
    y = 18.0
    while y < W - 10.0:
        cyl(mb, 'MI_Tejas', (xr, y - 2.0, zc), (xr, y + 2.0, zc), 12.2, 12)
        y += 40.0
    # bocas de teja en el alero
    y = 10.5
    while y < W - 8.0:
        a = P(-3.0, th + lip - 4.0)
        b = P(26.0, th + lip - 4.0)
        cyl(mb, 'MI_Tejas', (a[0], y, a[1]), (b[0], y, b[1]), 6.2, 8)
        y += 21.0
    # frentín (cenefa) y cabios de madera
    box(mb, 'MI_Madera', ef - 3.0, ef + 1.5, 0.0, W, z_e - 14.0, z_e + 4.0)
    box(mb, 'MI_Madera', eb - 1.5, eb + 3.0, 0.0, W, z_e - 14.0, z_e + 4.0)

    def zu(x):
        return z_e + (ef - x) * ta
    y = 30.0
    while y < W - 20.0:
        prism(mb, 'MI_Madera', [(xf - 30.0, zu(xf - 30.0) - 14.0), (ef - 4.0, zu(ef - 4.0) - 10.0),
                                (ef - 4.0, zu(ef - 4.0)), (xf - 30.0, zu(xf - 30.0))], 'y', y, y + 7.0)
        y += 60.0
    # hastiales laterales
    for (y0, y1) in ((0.0, 15.0), (W - 15.0, W)):
        prism(mb, side_mat, [(xb, z_e - 1.0), (xf, z_e - 1.0), (xf, zu(xf) - 1.0), (xr, zr_ - 1.0),
                             (xb, z_e + (xb - eb) * ta - 1.0)], 'y', y0, y1)
    # chimenea de ladrillo
    cx0, cx1 = xr - 210.0, xr - 150.0
    cbox(mb, 'MI_Ladrillo', cx0, cx1, W - 260.0, W - 200.0, zr_ - 160.0, zr_ + 95.0, 0.8, 'z')
    cbox(mb, 'MI_Hormigon', cx0 - 5.0, cx1 + 5.0, W - 265.0, W - 195.0, zr_ + 95.0, zr_ + 101.0, 1.2, 'y')
    box(mb, 'MI_Hormigon', cx0 + 8.0, cx1 - 8.0, W - 252.0, W - 208.0, zr_ + 101.0, zr_ + 116.0)
    cbox(mb, 'MI_Hormigon', cx0 - 2.0, cx1 + 2.0, W - 262.0, W - 198.0, zr_ + 116.0, zr_ + 121.0, 1.0, 'y')
    mb.col(eb, ef, 0.0, W, z_e, zr_ + tb)
    return zr_


def k_cerco_alto(mb, wm, W, ped, slide):
    """Reja alta de 2 m: pilares, puerta peatonal, paño fijo y portón corredizo con riel y ruedas."""
    k_pilar(mb, wm, 0.0, 45.0, 215.0, True, -32.0, 0.0)
    k_pilar(mb, wm, W - 30.0, W, 215.0, True, -30.0, 0.0)
    cbox(mb, 'MI_Chapa_Gris', 0.0, 7.0, 4.0, 41.0, 100.0, 158.0, 0.8, 'z')
    box(mb, 'MI_Vidrio', 7.0, 7.3, 14.0, 31.0, 135.0, 150.0)
    anc = k_bajada(mb, -16.0, 22.5, 221.0, 400.0, xoff=0.0, r=3.4)
    posts = [(ped[1], ped[1] + 7.0), (slide[0] - 7.0, slide[0])]
    for (a, b) in posts:
        cbox(mb, M_HIERRO, -9.0, -2.0, a, b, 0.0, 212.0, 0.5, 'z')
        box(mb, M_HIERRO, -9.5, -1.5, a - 0.5, b + 0.5, 212.0, 213.5)
    # paño fijo
    k_reja_plano(mb, M_HIERRO, -8.5, posts[0][1], posts[1][0], 20.0, 200.0, spacing=12.0, bar=2.0, frame=4.0,
                 rails=(110.0,), lanzas=10.0)
    # puerta peatonal
    k_reja_plano(mb, M_HIERRO, -8.5, ped[0] + 1.5, ped[1] - 1.5, 22.0, 198.0, spacing=11.0, bar=2.0, frame=4.0,
                 rails=(105.0, 150.0), lanzas=9.0)
    box(mb, M_HIERRO, -11.0, -1.0, ped[1] - 9.0, ped[1] - 1.5, 100.0, 108.0)
    for zh in (40.0, 180.0):
        cyl(mb, M_HIERRO, (-6.0, ped[0] + 0.5, zh - 6.0), (-6.0, ped[0] + 0.5, zh + 6.0), 1.4, 8)
    # portón corredizo (cerrado), por detrás del paño fijo
    s0, s1 = slide[0] + 1.0, slide[1] - 1.0
    k_reja_plano(mb, M_HIERRO, -20.0, s0, s1, 26.0, 205.0, spacing=12.0, bar=2.0, frame=5.0,
                 rails=(115.0,), lanzas=10.0)
    box(mb, M_HIERRO, -19.0, -16.0, posts[0][0], slide[1], Z_VER + 3.5, Z_VER + 7.0)   # riel
    for yw in (s0 + 40.0, s1 - 40.0):
        cyl(mb, M_HIERRO, (-21.0, yw, 26.0), (-13.5, yw, 26.0), 5.5, 14)
        box(mb, M_HIERRO, -21.5, -13.0, yw - 8.0, yw + 8.0, 26.0, 30.0)
    box(mb, M_HIERRO, -24.0, -12.0, slide[0] - 10.0, slide[0] - 4.0, 198.0, 212.0)
    cyl(mb, M_HIERRO, (-22.0, slide[0] - 2.0, 202.0), (-14.0, slide[0] - 2.0, 202.0), 2.5, 10)
    box(mb, M_HIERRO, -24.0, -14.0, s1 - 12.0, s1 - 4.0, 95.0, 110.0)
    mb.col(-32.0, 0.0, 0.0, W, 0.0, 212.0)
    return anc


def build_casa_d(W):
    mb = MB('CasaD')
    wm, sm_ = 'MI_Revoque_Rosa', 'MI_Revoque_Gris'
    xf, depth = -450.0, 1000.0
    xb = xf - depth
    z_patio = 22.0
    zpa = 315.0
    z_e = 590.0
    ang = 27.0
    ftop = z_e + 45.0 * math.tan(math.radians(ang))
    win = (70.0, 240.0, 100.0, 240.0)
    door = (330.0, 420.0, Z_PISO + 6.0, 240.0)
    gar = (490.0, 810.0, z_patio, 240.0)
    w2 = (90.0, 300.0, 395.0, 545.0)
    bdoor = (480.0, 640.0, zpa + 5.0, 545.0)
    holes = [win_hole(*win), door, gar, win_hole(*w2), bdoor]
    piece('D cascaron', shell, mb, W, xf, depth, z_e, z_e, wm, sm_, holes, floors=(zpa,), parapet=False,
          roof=False, facade_top=ftop)
    piece('D ventana', k_window, mb, wm, xf, win[0], win[1], win[2], win[3],
          dict(reja='barrotes', persiana='enrollar', cerrada=0.5, marco='MI_Madera', persiana_mat='MI_Madera',
               alfeizar='MI_PiedraLaja'))
    piece('D puerta', k_door, mb, xf, door[0], door[1], door[2], door[3],
          dict(hoja='MI_Madera', estilo='vidriada', marco='MI_Madera', base_z=z_patio, aplique=True))
    piece('D porton', k_garage_chapa, mb, xf, gar[0], gar[1], gar[2], gar[3],
          dict(mat='MI_Metal_Negro', orient='h', marco=M_HIERRO))
    piece('D ventana PA', k_window, mb, wm, xf, w2[0], w2[1], w2[2], w2[3],
          dict(reja='barrotes', persiana='enrollar', cerrada=0.4, marco='MI_Madera', persiana_mat='MI_Madera'))
    piece('D puerta balcon', k_window, mb, wm, xf, bdoor[0], bdoor[1], bdoor[2] + 5.0, bdoor[3],
          dict(persiana='enrollar', cerrada=0.6, marco='MI_Madera', persiana_mat='MI_Madera'))
    piece('D losa balcon', k_losa_balcon, mb, wm, xf, 15.0, W - 15.0, zpa + 3.0, 100.0, 18.0)
    piece('D balaustrada', k_balaustrada, mb, 'MI_Revoque_Blanco', xf, 15.0, W - 15.0, zpa + 3.0, 100.0)
    piece('D zocalo', k_zocalo, mb, 'MI_Ladrillo', xf, 0.0, W, 60.0, [(gar[0] - 1.0, gar[1] + 1.0),
                                                                      (door[0] - 6.0, door[1] + 6.0)])
    piece('D techo', k_techo_tejas, mb, W, xf, xb, z_e, ang, 45.0, 12.0, sm_)
    piece('D split', k_split, mb, xf, 721.0, 450.0, 1)
    piece('D numero', k_numero, mb, xf, 450.0, 200.0)
    # patio de hormigón y lajas sueltas
    box(mb, 'MI_Hormigon', xf, 0.0, 0.0, W, 0.0, z_patio)
    mb.col(xf, 0.0, 0.0, W, 0.0, z_patio)
    for k in range(7):
        t = k / 6.0
        cx = -45.0 + (xf + 60.0 - (-45.0)) * t + RNG.uniform(-6, 6)
        cy = 92.0 + (375.0 - 92.0) * t * t + RNG.uniform(-6, 6)
        piece('D laja', rbox, mb, 'MI_PiedraLaja', cx, cy, z_patio - 0.5, RNG.uniform(34, 46), RNG.uniform(30, 42),
              2.2, RNG.uniform(-25, 25))
    piece('D cantero', k_cantero, mb, xf + 1.0, xf + 40.0, 40.0, 280.0, z_patio)
    for cy in (80.0, 170.0, 250.0):
        piece('D planta', k_planta, mb, xf + 20.0, cy, z_patio + 9.0, RNG.uniform(1.0, 1.6), False)
    anc = piece('D cerco', k_cerco_alto, mb, wm, W, (45.0, 140.0), (340.0, 836.0))
    mb.anchors = {'power': anc or (0.0, 22.0, 398.0), 'tel': [(xf + 2.0, 780.0, 572.0)], 'run': None, 'xf': xf}
    return mb


# ---------------------------------------------------------------------------------
# Lote E: local comercial
# ---------------------------------------------------------------------------------
def build_local_e(W):
    mb = MB('LocalE')
    wm, sm_ = 'MI_Ladrillo', 'MI_Revoque_Gris'
    xf, depth = 0.0, 900.0
    xb = xf - depth
    zr, zp = 400.0, 470.0
    cort = (25.0, 305.0, Z_VER, 285.0)
    door = (325.0, 405.0, Z_PISO, 240.0)
    piece('E cascaron', shell, mb, W, xf, depth, zr, zp, wm, sm_, [cort, door], parapet_mat='MI_Revoque_Gris',
          coping_mat='MI_Hormigon')
    piece('E faja', cbox, mb, 'MI_Revoque_Gris', xf - 1.0, xf + 2.0, 0.0, W, zr - 12.0, zr + 1.0, 0.8, 'y')
    piece('E cortina', k_cortina_local, mb, xf, cort[0], cort[1], cort[2], cort[3])
    piece('E dintel', cbox, mb, 'MI_Hormigon', xf - 30.0, xf + 1.0, 10.0, 320.0, cort[3], cort[3] + 20.0, 0.6, 'y')
    piece('E umbral', k_umbral, mb, 'MI_Hormigon', xf, cort[0], cort[1], Z_VER, Z_VER + 1.0)
    piece('E puerta', k_door, mb, xf, door[0], door[1], door[2], door[3],
          dict(hoja='MI_Chapa_Gris', estilo='vidriada', marco=M_HIERRO, umbral_mat='MI_Hormigon'))
    piece('E cartel', cbox, mb, 'MI_Chapa_Verde', xf, xf + 8.0, 30.0, 300.0, 318.0, 380.0, 1.0, 'y')
    piece('E cartel panel', box, mb, M_TELA, xf + 8.0, xf + 8.5, 36.0, 294.0, 324.0, 374.0)
    for yb in (60.0, 270.0):
        piece('E cartel soporte', box, mb, M_HIERRO, xf, xf + 8.0, yb - 1.0, yb + 1.0, 312.0, 318.0)
    piece('E zocalo', k_zocalo, mb, 'MI_Hormigon', xf, 0.0, W, 40.0, [(cort[0] - 1.0, cort[1] + 1.0),
                                                                      (door[0] - 6.0, door[1] + 6.0)])
    anc = piece('E bajada', k_bajada, mb, xf, 420.0, 120.0, 500.0)
    piece('E split', k_split, mb, xf, 368.0, 330.0, -1)
    # tanque de fibrocemento cúbico sobre patas
    tx, ty = xb + 200.0, 220.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            piece('E pata', box, mb, 'MI_Hormigon', tx + sx * 48.0 - 6.0, tx + sx * 48.0 + 6.0, ty + sy * 48.0 - 6.0,
                  ty + sy * 48.0 + 6.0, zr + 2.0, zr + 40.0)
    piece('E tanque', cbox, mb, 'MI_Hormigon', tx - 60.0, tx + 60.0, ty - 60.0, ty + 60.0, zr + 40.0, zr + 140.0, 3.0, 'z')
    piece('E tapa', cbox, mb, 'MI_Hormigon', tx - 63.0, tx + 63.0, ty - 63.0, ty + 63.0, zr + 140.0, zr + 145.0, 1.5, 'y')
    mb.col(tx - 60.0, tx + 60.0, ty - 60.0, ty + 60.0, zr, zr + 145.0)
    mb.anchors = {'power': anc or (xf + 20.0, 420.0, 495.0), 'tel': [(xf + 2.0, 120.0, 440.0)],
                  'run': [(290.0, 2.5), (282.0, 2.5)], 'xf': xf}
    return mb


# ---------------------------------------------------------------------------------
# Medianeras de los vecinos (cierre de la cuadra)
# ---------------------------------------------------------------------------------
def build_medianera(name, depth, h, face_sign, mat_wall, mat_patch, columns=True):
    """Muro medianero expuesto de 30 cm (y 0..30). face_sign=+1: la cara vista mira a +Y."""
    mb = MB(name)
    rng = random.Random(SEED + len(name))
    box(mb, mat_wall, -depth, 0.0, 0.0, 30.0, 0.0, h)
    yf = 30.0 if face_sign > 0 else 0.0
    s = 1.0 if face_sign > 0 else -1.0
    if columns:
        x = 0.0
        while x > -depth:
            box(mb, 'MI_Hormigon', x - 30.0, x, yf - s * 1.0, yf + s * 2.0, 0.0, h)
            x -= 430.0
        z = 300.0
        while z < h - 20.0:
            box(mb, 'MI_Hormigon', -depth, 0.0, yf - s * 1.0, yf + s * 2.0, z - 12.0, z + 12.0)
            z += 300.0
    for k in range(9):
        px = rng.uniform(-depth + 60.0, -60.0)
        pz = rng.uniform(40.0, h - 80.0)
        w = rng.uniform(60.0, 220.0)
        hh = rng.uniform(40.0, 160.0)
        box(mb, mat_patch, px - w * 0.5, px + w * 0.5, yf - s * 1.0, yf + s * 1.2, pz, pz + hh)
    box(mb, 'MI_Revoque_Gris', -2.0, 1.0, 0.0, 30.0, 0.0, h)
    cbox(mb, 'MI_Hormigon', -depth, 1.0, -3.0, 33.0, h, h + 5.0, 1.0, 'x')
    mb.col(-depth, 0.0, 0.0, 30.0, 0.0, h)
    return mb


# =====================================================================================
# VEREDA, CALLE, TAPIAL
# =====================================================================================
def curb_profile(top, face_x=300.0, back_x=285.0):
    return [(back_x, -8.0), (face_x, -8.0), (face_x, top - 2.5), (face_x - 2.5, top), (back_x, top)]


def build_vereda(name, segs, ramps, pits, extras=None):
    """Vereda de 3 m: x=0 línea municipal, x=300 cara del cordón (hacia la calle). y = y del actor."""
    mb = MB(name)
    for (y0, y1, mat, dz) in segs:
        holes = []
        for (cx, cy) in pits:
            if y0 - 40.0 < cy < y1 + 40.0:
                holes.append((cx - 40.0, cx + 40.0, cy - 40.0, cy + 40.0))
        for (r0, r1) in ramps:
            holes.append((195.0, 285.0, r0 - 25.0, r1 + 25.0))
        for (a0, a1, b0, b1) in rect_minus(0.0, 285.0, y0, y1, holes):
            box(mb, mat, a0, a1, b0, b1, 2.0, Z_VER + dz)
        mb.col(0.0, 300.0, y0, y1, 0.0, Z_VER + max(dz, 0.0))
        # junta entre veredas de distinto frentista
        box(mb, 'MI_Hormigon', 0.0, 285.0, y0 - 1.0, y0 + 1.0, 2.0, Z_VER + dz + 0.25)
    yall0 = segs[0][0]
    yall1 = segs[-1][1]
    curb_specs = []
    for (r0, r1) in ramps:
        dz = 0.0
        for (y0, y1, mat, d) in segs:
            if y0 <= r0 < y1:
                dz = d
        prism(mb, 'MI_Hormigon', [(195.0, 2.0), (285.0, 2.0), (285.0, 7.5), (195.0, Z_VER + dz)], 'y', r0, r1)
        prism(mb, 'MI_Hormigon', [(195.0, 2.0), (285.0, 2.0), (285.0, 12.5), (195.0, Z_VER + dz)], 'y', r0 - 25.0, r0)
        prism(mb, 'MI_Hormigon', [(195.0, 2.0), (285.0, 2.0), (285.0, 12.5), (195.0, Z_VER + dz)], 'y', r1, r1 + 25.0)
        curb_specs += [(r0 - 25.0, r0, 12.5), (r0, r1, 7.5), (r1, r1 + 25.0, 12.5)]
    gaps = [(a, b) for (a, b, h) in curb_specs]
    for (a, b) in interval_minus(yall0, yall1, gaps):
        curb_specs.append((a, b, Z_VER))
    for (a, b, h) in curb_specs:
        # cordón en tramos de 1 a 2 m con juntas (desprolijidad leve)
        y = a
        while y < b - 0.5:
            yn = min(b, y + RNG.uniform(140.0, 220.0))
            hh = h + (RNG.uniform(-0.4, 0.4) if h == Z_VER else 0.0)
            prism(mb, 'MI_Hormigon', curb_profile(hh), 'y', y + 0.25, yn - 0.25)
            y = yn
    mb.col(285.0, 300.0, yall0, yall1, -8.0, Z_VER)
    for (cx, cy) in pits:
        dz = 0.0
        for (y0, y1, mat, d) in segs:
            if y0 <= cy < y1:
                dz = d
        k_cantero(mb, cx - 40.0, cx + 40.0, cy - 40.0, cy + 40.0, 2.0, Z_VER + dz + 1.0)
    for ex in (extras or []):
        kind = ex[0]
        if kind == 'tapa':
            _, x, y, s, dz = ex
            cbox(mb, M_HIERRO, x - s * 0.5, x + s * 0.5, y - s * 0.5, y + s * 0.5, Z_VER + dz - 1.0, Z_VER + dz + 0.4, 0.4, 'z')
        elif kind == 'floja':
            _, x, y, mat, dz = ex
            rbox(mb, mat, x, y, Z_VER + dz - 0.6, 39.5, 39.5, 1.6, RNG.uniform(-6, 6), RNG.uniform(-1.5, 1.5))
        elif kind == 'tocon':
            _, x, y = ex
            cone(mb, 'MI_PosteMadera', (x, y, 4.0), (x, y, 58.0), 27.0, 23.0, 14)
            cone(mb, 'MI_PosteMadera', (x, y, 58.0), (x + 3.0, y - 2.0, 63.0), 23.0, 15.0, 14)
            for k in range(5):
                a = k * 1.3 + 0.4
                p0 = (x + 14.0 * math.cos(a), y + 14.0 * math.sin(a), 58.0)
                p1 = (x + 28.0 * math.cos(a), y + 28.0 * math.sin(a), 58.0 + RNG.uniform(50.0, 110.0))
                cone(mb, 'MI_PosteMadera', p0, p1, 2.2, 0.4, 6)
            for k in range(3):
                a = k * 2.1
                cone(mb, 'MI_PosteMadera', (x, y, 12.0), (x + 38.0 * math.cos(a), y + 38.0 * math.sin(a), Z_VER + 2.0),
                     9.0, 3.0, 8)
            mb.col(x - 25.0, x + 25.0, y - 25.0, y + 25.0, 0.0, 60.0)
    return mb


def crown(x):
    return 4.0 + 3.0 * (1.0 - abs(x - 550.0) / 200.0)


def build_calle(y0, y1):
    """Calzada de 5 m (x 300..800 desde la LM): cordón cuneta, asfalto con bombeo, parches."""
    mb = MB('Calle')
    prism(mb, 'MI_Hormigon', [(300.0, -12.0), (350.0, -12.0), (350.0, 3.6), (300.0, 2.0)], 'y', y0, y1)
    prism(mb, 'MI_Hormigon', [(750.0, -12.0), (800.0, -12.0), (800.0, 2.0), (750.0, 3.6)], 'y', y0, y1)
    prism(mb, 'MI_Asfalto', [(350.0, -12.0), (750.0, -12.0), (750.0, 4.0), (650.0, 5.5), (550.0, 7.0),
                             (450.0, 5.5), (350.0, 4.0)], 'y', y0, y1)
    # juntas de la cuneta cada ~3 m
    y = y0 + 300.0
    while y < y1:
        prism(mb, 'MI_Asfalto', [(300.0, 1.0), (350.0, 1.0), (350.0, 3.8), (300.0, 2.2)], 'y', y - 0.6, y + 0.6)
        prism(mb, 'MI_Asfalto', [(750.0, 1.0), (800.0, 1.0), (800.0, 2.2), (750.0, 3.8)], 'y', y - 0.6, y + 0.6)
        y += 300.0
    # parches de bacheo (hormigón y asfalto nuevo)
    for (xa, xb, ya, yb, mat) in ((380.0, 520.0, 2050.0, 2290.0, 'MI_Hormigon'), (560.0, 700.0, 3320.0, 3480.0, 'MI_Asfalto'),
                                  (420.0, 610.0, 4400.0, 4760.0, 'MI_Hormigon'), (360.0, 430.0, 2950.0, 3010.0, 'MI_Asfalto'),
                                  (600.0, 745.0, 1700.0, 1820.0, 'MI_Hormigon')):
        xs = [xa] + ([550.0] if xa < 550.0 < xb else []) + [xb]
        bottom = [(x, crown(x) - 2.0) for x in xs]
        topl = [(x, crown(x) + (0.6 if mat == 'MI_Asfalto' else 0.35)) for x in reversed(xs)]
        prism(mb, mat, bottom + topl, 'y', ya, yb)
    mb.col(300.0, 800.0, y0, y1, -12.0, 4.0)
    return mb


def build_tapial(L):
    """Tapial de enfrente (se coloca rotado 180°): frente en x=0 mirando a +x local."""
    mb = MB('Tapial')
    wm = 'MI_Revoque_Blanco'
    hole = (2400.0, 2700.0, Z_VER, 215.0)
    wall_holes(mb, wm, -30.0, 0.0, 0.0, L, 0.0, 225.0, [hole])
    k_coping_y(mb, 'MI_Hormigon', -30.0, 0.0, 0.5, L - 0.5, 225.0)
    k_zocalo(mb, 'MI_Revoque_Gris', 0.0, 0.0, L, 45.0, [(hole[0] - 1.0, hole[1] + 1.0)])
    y = 150.0
    while y < L - 20.0:
        if not (hole[0] - 40.0 < y < hole[1] + 40.0):
            cbox(mb, wm, -1.0, 4.0, y - 15.0, y + 15.0, 0.0, 232.0, 0.8, 'z')
            cbox(mb, 'MI_Hormigon', -33.0, 6.0, y - 18.0, y + 18.0, 232.0, 238.0, 1.2, 'y')
        y += 300.0
    k_garage_chapa(mb, 0.0, hole[0], hole[1], hole[2], hole[3], dict(mat='MI_Chapa_Verde', orient='v'))
    # manchas de humedad / reparaciones de revoque
    rng = random.Random(SEED + 99)
    for k in range(10):
        yy = rng.uniform(50.0, L - 300.0)
        if hole[0] - 300.0 < yy < hole[1]:
            continue
        box(mb, 'MI_Revoque_Gris', -1.0, 0.8, yy, yy + rng.uniform(80.0, 260.0), 45.0, 45.0 + rng.uniform(25.0, 120.0))
    mb.col(-30.0, 0.0, 0.0, L, 0.0, 238.0)
    return mb


# =====================================================================================
# POSTES, ÁRBOLES, CANASTOS
# =====================================================================================
POLE_DEF = {
    'lum': {'top': 920.0, 'za': 850.0, 'half': 95.0, 'ins': [-75.0, -28.0, 28.0, 75.0],
            'tel': [700.0, 672.0, 645.0, 620.0, 598.0]},
    'simple': {'top': 810.0, 'za': 765.0, 'half': 45.0, 'ins': [-32.0, 32.0],
               'tel': [735.0, 708.0, 680.0, 655.0, 630.0, 604.0]},
}


def pole_r(kind, z):
    top = POLE_DEF[kind]['top']
    return 15.5 - 5.0 * (z + 40.0) / (top + 40.0)


def build_poste(kind):
    d = POLE_DEF[kind]
    mb = MB('Poste_' + kind)
    top, za, half = d['top'], d['za'], d['half']
    cone(mb, 'MI_PosteMadera', (0.0, 0.0, -40.0), (0.0, 0.0, top), 15.5, 10.5, 14)
    cone(mb, 'MI_PosteMadera', (0.0, 0.0, top), (0.0, 0.0, top + 3.5), 10.5, 7.0, 14)
    cyl(mb, 'MI_Hormigon', (0.0, 0.0, Z_VER - 1.0), (0.0, 0.0, Z_VER + 3.0), 24.0, 16)
    # cruceta perpendicular a la calle (a lo largo de X) con riostras y aisladores
    cbox(mb, 'MI_PosteMadera', -half, half, -5.0, 5.0, za - 9.0, za, 1.0, 'x')
    rr = pole_r(kind, za)
    box(mb, M_HIERRO, -rr - 1.0, rr + 1.0, -6.5, 6.5, za - 7.0, za - 2.0)
    for s in (-1.0, 1.0):
        cyl(mb, M_HIERRO, (s * half * 0.55, 6.0, za - 9.0), (s * (pole_r(kind, za - 60.0) + 0.5), 6.0, za - 60.0), 1.0, 6)
    for xi in d['ins']:
        cyl(mb, M_PORCELANA, (xi, 0.0, za), (xi, 0.0, za + 13.0), 3.0, 10)
        for k in range(3):
            cyl(mb, M_PORCELANA, (xi, 0.0, za + 2.5 + k * 3.6), (xi, 0.0, za + 3.7 + k * 3.6), 5.5, 12)
    # morsetos de telecomunicaciones
    for z in d['tel']:
        r = pole_r(kind, z)
        torus(mb, M_HIERRO, (0.0, 0.0, z), r + 1.2, 1.0, (0, 0, 1), 16, 4)
        box(mb, M_HIERRO, -3.0, 3.0, r - 1.0, r + 4.0, z - 3.0, z + 3.0)
    # rulos de fibra / reserva de cable
    zc = 520.0 if kind == 'lum' else 470.0
    rz = pole_r(kind, zc)
    for k, (R_, dz, tilt) in enumerate(((27.0, 0.0, 0.0), (29.0, 3.0, 0.15), (25.0, -2.0, -0.12))):
        torus(mb, 'MI_Cable', (0.0, rz + 2.0, zc + dz), R_, 0.9, (tilt, 1.0, 0.0), 22, 5)
    box(mb, M_HIERRO, -2.0, 2.0, rz - 1.0, rz + 4.0, zc + 20.0, zc + 30.0)
    # caja de empalme
    zb = 560.0 if kind == 'lum' else 540.0
    rb = pole_r(kind, zb)
    cbox(mb, 'MI_Chapa_Gris', -9.0, 9.0, -rb - 15.0, -rb - 1.0, zb, zb + 38.0, 1.2, 'z')
    for k in range(3):
        tube(mb, 'MI_Cable', [(-4.0 + k * 4.0, -rb - 8.0, zb), (-4.0 + k * 4.0, -rb - 9.0, zb - 25.0 - k * 10.0),
                              (-3.0 + k * 4.0, -rb - 3.0, zb - 60.0 - k * 12.0)], 0.6, 5)
    # caño de bajada a tierra + cable
    cyl(mb, 'MI_Chapa_Gris', (-17.5, 0.0, 0.0), (-16.0, 0.0, 260.0), 2.6, 10)
    tube(mb, 'MI_Cable', [(-16.0, 0.0, 258.0), (-14.0, 0.0, 500.0), (-12.0, 0.0, za - 6.0)], 0.5, 5)
    # placa identificatoria
    r2 = pole_r(kind, 250.0)
    box(mb, 'MI_Chapa_Gris', r2 - 0.6, r2 + 0.2, -6.0, 6.0, 240.0, 258.0)
    if kind == 'lum':
        r7 = pole_r(kind, 770.0)
        torus(mb, M_HIERRO, (0.0, 0.0, 772.0), r7 + 1.5, 1.6, (0, 0, 1), 16, 4)
        pts = [(r7, 0.0, 772.0), (60.0, 0.0, 792.0), (150.0, 0.0, 812.0), (205.0, 0.0, 816.0)]
        for i in range(len(pts) - 1):
            cyl(mb, M_HIERRO, pts[i], pts[i + 1], 2.8, 10)
            if i > 0:
                blob(mb, M_HIERRO, pts[i], 2.9, 2.9, 2.9, steps=(6, 8))
        cyl(mb, M_HIERRO, (r7, 0.0, 740.0), (70.0, 0.0, 793.0), 1.6, 8)
        blob(mb, 'MI_Chapa_Gris', (228.0, 0.0, 814.0), 36.0, 15.0, 8.0)
        blob(mb, 'MI_Vidrio', (232.0, 0.0, 808.5), 27.0, 11.0, 3.0)
        cyl(mb, M_PORCELANA, (220.0, 0.0, 820.0), (220.0, 0.0, 825.0), 3.2, 10)
        tube(mb, 'MI_Cable', [(r7 + 1.0, 2.0, 768.0), (r7 + 2.0, 4.0, 700.0), (r7 + 1.0, 3.0, 640.0)], 0.5, 5)
        light = (232.0, 0.0, 806.0)
    else:
        light = None
    mb.col(-16.0, 16.0, -16.0, 16.0, 0.0, top)
    mb.anchors = {'light': light}
    return mb


def _poda(d):
    """Las ramas hacia las fachadas (-X local) se podan: se acortan en esa dirección."""
    if d[0] < 0:
        d = (d[0] * 0.45, d[1], d[2])
    return v_norm(d)


def build_arbol(seed, copa=False):
    """Árbol de vereda simplificado: tronco encalado y ramas podadas (fresno). copa=True agrega
    una copa de silueta con elipsoides (placeholder hasta el follaje de Fab).
    Convención: -X local = lado de las casas (se coloca con yaw 0 en la vereda propia, 180 enfrente)."""
    rng = random.Random(seed)
    mb = MB('Arbol')
    h = rng.uniform(210.0, 250.0)
    base = (0.0, 0.0, -20.0)
    topp = (rng.uniform(-8, 8), rng.uniform(-8, 8), h)
    cone(mb, 'MI_PosteMadera', base, topp, 16.0, 11.5, 14)
    t_w = (95.0 + 20.0) / (h + 20.0)
    cone(mb, 'MI_Revoque_Blanco', base, v_lerp(base, topp, t_w), 16.8, 16.8 - 4.5 * t_w, 14)
    for k in range(3):
        a = rng.uniform(0, 2 * math.pi)
        cone(mb, 'MI_PosteMadera', (0.0, 0.0, 4.0), (30.0 * math.cos(a), 30.0 * math.sin(a), Z_VER - 2.0), 7.0, 2.0, 8)
    blob(mb, 'MI_PosteMadera', topp, 13.0, 13.0, 11.0)
    n_main = rng.randint(3, 5)
    for i in range(n_main):
        az = (2 * math.pi * i / n_main) + rng.uniform(-0.35, 0.35)
        el = math.radians(rng.uniform(32.0, 55.0))
        L = rng.uniform(150.0, 240.0)
        d = _poda((math.sin(el) * math.cos(az), math.sin(el) * math.sin(az), math.cos(el)))
        p1 = v_add(topp, v_mul(d, L))
        cone(mb, 'MI_PosteMadera', topp, p1, 9.0, 6.0, 10)
        blob(mb, 'MI_PosteMadera', p1, 8.5, 8.5, 9.5, steps=(6, 8))
        pm = v_lerp(topp, p1, rng.uniform(0.4, 0.6))
        az2 = az + rng.choice((-1, 1)) * rng.uniform(0.6, 1.1)
        el2 = math.radians(rng.uniform(40.0, 65.0))
        d2 = _poda((math.sin(el2) * math.cos(az2), math.sin(el2) * math.sin(az2), math.cos(el2)))
        p2 = v_add(pm, v_mul(d2, rng.uniform(80.0, 140.0)))
        cone(mb, 'MI_PosteMadera', pm, p2, 4.5, 2.0, 8)
        for j in range(rng.randint(5, 9) if not copa else rng.randint(3, 5)):
            az3 = az + rng.uniform(-0.9, 0.9)
            el3 = math.radians(rng.uniform(5.0, 35.0))
            d3 = _poda((math.sin(el3) * math.cos(az3), math.sin(el3) * math.sin(az3), math.cos(el3)))
            q0 = v_add(p1, (rng.uniform(-4, 4), rng.uniform(-4, 4), rng.uniform(0, 4)))
            cone(mb, 'MI_PosteMadera', q0, v_add(q0, v_mul(d3, rng.uniform(90.0, 220.0))), rng.uniform(1.6, 2.8), 0.4, 6)
        for j in range(rng.randint(2, 4)):
            d3 = _poda(v_add(d2, (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0.2, 0.8))))
            cone(mb, 'MI_PosteMadera', p2, v_add(p2, v_mul(d3, rng.uniform(60.0, 130.0))), 1.6, 0.3, 6)
    if copa:
        c = (55.0, 0.0, h + 300.0)
        for k in range(14):
            a = rng.uniform(0, 2 * math.pi)
            rr = rng.uniform(40.0, 140.0)
            ca = math.cos(a) * (0.6 if math.cos(a) < 0 else 1.0)
            zz = rng.uniform(-60.0, 110.0) * (1.0 - rr / 300.0)
            blob(mb, M_FOLLAJE, (c[0] + rr * ca, c[1] + rr * math.sin(a), c[2] + zz),
                 rng.uniform(60.0, 100.0), rng.uniform(60.0, 100.0), rng.uniform(50.0, 85.0), yaw=rng.uniform(0, 180),
                 steps=(8, 12))
    mb.col(-17.0, 17.0, -17.0, 17.0, 0.0, h)
    return mb


def build_canasto():
    """Canasto de basura elevado de reja sobre un caño."""
    mb = MB('Canasto')
    cyl(mb, M_HIERRO, (0.0, 0.0, -20.0), (0.0, 0.0, 96.0), 2.4, 10)
    cyl(mb, 'MI_Hormigon', (0.0, 0.0, Z_VER - 1.0), (0.0, 0.0, Z_VER + 2.0), 6.0, 10)
    x0, x1, y0, y1, z0, z1 = -24.0, 24.0, -36.0, 36.0, 96.0, 132.0
    fl = 1.0
    for (xa, ya) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        box(mb, M_HIERRO, xa - fl, xa + fl, ya - fl, ya + fl, z0, z1)
    for z in (z0, z1 - 2.0):
        box(mb, M_HIERRO, x0 - fl, x1 + fl, y0 - fl, y0 + fl, z, z + 2.0)
        box(mb, M_HIERRO, x0 - fl, x1 + fl, y1 - fl, y1 + fl, z, z + 2.0)
        box(mb, M_HIERRO, x0 - fl, x0 + fl, y0 - fl, y1 + fl, z, z + 2.0)
        box(mb, M_HIERRO, x1 - fl, x1 + fl, y0 - fl, y1 + fl, z, z + 2.0)
    sp = 6.0
    bw = 0.35
    y = y0 + sp
    while y < y1 - 1.0:
        for xa in (x0, x1):
            box(mb, M_HIERRO, xa - bw, xa + bw, y - bw, y + bw, z0, z1)
        box(mb, M_HIERRO, x0, x1, y - bw, y + bw, z0, z0 + 2 * bw)
        y += sp
    x = x0 + sp
    while x < x1 - 1.0:
        for ya in (y0, y1):
            box(mb, M_HIERRO, x - bw, x + bw, ya - bw, ya + bw, z0, z1)
        box(mb, M_HIERRO, x - bw, x + bw, y0, y1, z0, z0 + 2 * bw)
        x += sp
    z = z0 + 12.0
    while z < z1 - 4.0:
        box(mb, M_HIERRO, x0 - bw, x1 + bw, y0 - bw, y0 + bw, z, z + 2 * bw)
        box(mb, M_HIERRO, x0 - bw, x1 + bw, y1 - bw, y1 + bw, z, z + 2 * bw)
        box(mb, M_HIERRO, x0 - bw, x0 + bw, y0, y1, z, z + 2 * bw)
        box(mb, M_HIERRO, x1 - bw, x1 + bw, y0, y1, z, z + 2 * bw)
        z += 12.0
    box(mb, M_HIERRO, -3.0, 3.0, y0, y1, z0 - 4.0, z0)
    cyl(mb, M_HIERRO, (0.0, 0.0, 70.0), (0.0, y0 + 6.0, z0 - 3.0), 1.2, 6)
    cyl(mb, M_HIERRO, (0.0, 0.0, 70.0), (0.0, y1 - 6.0, z0 - 3.0), 1.2, 6)
    mb.col(x0, x1, y0, y1, z0, z1)
    mb.col(-3.0, 3.0, -3.0, 3.0, 0.0, z0)
    return mb


# =====================================================================================
# CABLES
# =====================================================================================
def build_cables(poles, houses):
    """poles: nombre -> dict(loc, rot, kind). houses: lista de dict(world_origin, anchors, W).
    Todo en coordenadas de mundo (el actor va en el origen)."""
    mb = MB('Cables')
    rng = random.Random(SEED + 7)

    def pw(name, xi):
        p = poles[name]
        d = POLE_DEF[p['kind']]
        return world_pt(p['loc'], p['rot'], (xi, 0.0, d['za'] + 13.0))

    def tel(name, idx, toward):
        p = poles[name]
        d = POLE_DEF[p['kind']]
        z = d['tel'][idx % len(d['tel'])]
        c = world_pt(p['loc'], p['rot'], (0.0, 0.0, z))
        dx, dy = toward[0] - c[0], toward[1] - c[1]
        l = math.sqrt(dx * dx + dy * dy) or 1.0
        r = pole_r(p['kind'], z) + 2.0
        return (c[0] + dx / l * r, c[1] + dy / l * r, c[2] + rng.uniform(-3.0, 3.0))

    def ins_list(name):
        return POLE_DEF[poles[name]['kind']]['ins']

    def add(p0, p1, sag, r=0.7):
        tube(mb, 'MI_Cable', catenary(p0, p1, sag), r, 6)

    def ctr(name):
        return poles[name]['loc']

    # --- línea de baja tensión (preensamblado y conductores desnudos) ---
    spans = [('PA', 'PB'), ('PB', 'PC'), ('PC', 'PD')]
    for (a, b) in spans:
        ia, ib = ins_list(a), ins_list(b)
        if len(ia) == len(ib):
            pairs = list(zip(ia, ib))
        else:
            short, long_ = (ia, ib) if len(ia) < len(ib) else (ib, ia)
            sel = [long_[1], long_[2]] if len(long_) >= 4 else long_[:len(short)]
            pairs = list(zip(short, sel)) if short is ia else list(zip(sel, short))
        for (xa, xb) in pairs:
            add(pw(a, xa), pw(b, xb), rng.uniform(48.0, 66.0), 0.9)
    for (a, b) in (('PB', 'PE'), ('PE', 'PC')):
        for xi in (75.0, 28.0):
            add(pw(a, xi), pw(b, xi), rng.uniform(62.0, 80.0), 0.9)
    # --- telefonía / fibra / coaxil entre postes ---
    tel_spans = [('PA', 'PB', 5), ('PB', 'PC', 7), ('PC', 'PD', 5), ('PB', 'PE', 3), ('PE', 'PC', 3)]
    for (a, b, n) in tel_spans:
        for k in range(n):
            pa = tel(a, k + rng.randint(0, 2), ctr(b))
            pb = tel(b, k + rng.randint(0, 2), ctr(a))
            r = rng.choice((0.45, 0.55, 0.6, 0.75, 1.0))
            add(pa, pb, rng.uniform(28.0, 95.0), r)
        add(tel(a, 0, ctr(b)), tel(b, 0, ctr(a)), rng.uniform(40.0, 55.0), 1.7)   # haz preensamblado grueso
    # --- acometidas de energía a cada casa ---
    feeders = {'A': 'PA', 'B': 'PB', 'C': 'PC', 'D': 'PC', 'E': 'PD'}
    for h in houses:
        pn = feeders.get(h['key'], 'PB')
        anc = h['anchors'].get('power')
        if not anc:
            continue
        dst = v_add(h['origin'], anc)
        src = pw(pn, ins_list(pn)[0])
        L = v_len(v_sub(dst, src))
        add(src, dst, max(8.0, L * 0.035), 0.75)
        # segunda acometida (otra compañía / vieja sin retirar)
        if rng.random() < 0.6:
            add(pw(pn, ins_list(pn)[1]), v_add(dst, (0.0, 3.0, -4.0)), max(10.0, L * 0.05), 0.6)
    # --- bajadas de telecomunicaciones a las casas ---
    for h in houses:
        pn = feeders.get(h['key'], 'PB')
        for k, anc in enumerate(h['anchors'].get('tel', [])):
            dst = v_add(h['origin'], anc)
            src = tel(pn, k + 2, dst)
            L = v_len(v_sub(dst, src))
            add(src, dst, L * rng.uniform(0.03, 0.08), rng.choice((0.45, 0.55)))
            box(mb, M_HIERRO, dst[0] - 2.0, dst[0] + 1.5, dst[1] - 1.5, dst[1] + 1.5, dst[2] - 2.0, dst[2] + 2.0)
    # --- cables corridos por las fachadas (con grampas) y cruzando los retiros ---
    for lane in (0, 1):
        pts_anchor = []
        for h in houses:
            run = h['anchors'].get('run')
            o = h['origin']
            if not run:
                continue
            z, xoff = run[lane]
            xface = o[0] + h['anchors']['xf']
            y = 20.0
            W = h['W']
            while y < W - 10.0:
                pts_anchor.append(((xface + xoff, o[1] + y, z), xface))
                y += 130.0
            pts_anchor.append(((xface + xoff, o[1] + W - 6.0, z), xface))
        path = []
        for i in range(len(pts_anchor) - 1):
            a, b = pts_anchor[i][0], pts_anchor[i + 1][0]
            span = abs(b[1] - a[1])
            sag = 1.2 if span < 200.0 else span * 0.035
            seg = catenary(a, b, sag, 4 if span < 200.0 else 16)
            path.extend(seg if not path else seg[1:])
        if len(path) > 1:
            tube(mb, 'MI_Cable', path, 0.6 if lane == 0 else 0.5, 6)
        for (p, xface) in pts_anchor:
            box(mb, M_HIERRO, xface, p[0] + 1.0, p[1] - 0.8, p[1] + 0.8, p[2] - 1.2, p[2] + 1.2)
    # bajada a la caja de TV de la casa A
    for h in houses:
        if h['key'] != 'A':
            continue
        o = h['origin']
        tube(mb, 'MI_Cable', [(o[0] + 2.5, o[1] + 500.0, 257.0), (o[0] + 3.0, o[1] + 501.0, 236.0),
                              (o[0] + 6.0, o[1] + 500.0, 214.0)], 0.5, 5)
    # --- lazos sueltos colgando de los postes ---
    for pn, toward in (('PB', (1.0, 0.4)), ('PC', (0.6, -1.0)), ('PE', (-0.8, 0.5))):
        p = poles[pn]
        c = world_pt(p['loc'], p['rot'], (0.0, 0.0, POLE_DEF[p['kind']]['tel'][-1]))
        p0 = (c[0] + 13.0 * toward[0], c[1] + 13.0 * toward[1], c[2])
        p1 = (c[0] + 60.0 * toward[0], c[1] + 60.0 * toward[1], c[2] - 330.0)
        p2 = (c[0] + 18.0 * toward[0] + 8.0, c[1] + 18.0 * toward[1], c[2] - 70.0)
        tube(mb, 'MI_Cable', bezier(p0, p1, p2, 16), 0.55, 5)
    return mb


# =====================================================================================
# ASSETS Y ACTORES
# =====================================================================================
MI = {}


def load_materials():
    missing = []
    for m in MATS:
        path = MAT_DIR + '/' + m
        obj = None
        try:
            if unreal.EditorAssetLibrary.does_asset_exist(path):
                obj = unreal.EditorAssetLibrary.load_asset(path)
        except Exception:
            obj = None
        MI[m] = obj
        if obj is None:
            missing.append(m)
    if missing:
        warn('Materiales que todavía no existen (slots vacíos): %s' % ', '.join(missing))
    else:
        log('Materiales: las %d MI_* existen' % len(MATS))


def recompute_normals(dm):
    if not F.get('split_normals'):
        return
    try:
        so = unreal.GeometryScriptSplitNormalsOptions()
        _sp(so, 'split_by_opening_angle', True)
        _sp(so, 'opening_angle_deg', SPLIT_NORMAL_ANGLE)
        _sp(so, 'split_by_face_group', False)
        co = unreal.GeometryScriptCalculateNormalsOptions()
        _sp(co, 'angle_weighted', True)
        _sp(co, 'area_weighted', True)
        call('split_normals', dm, split_options=so, calculate_options=co)
    except Exception as e:
        err_once('normals', 'compute_split_normals falló: %s' % e)


def _parse_outcome(res):
    sm = None
    ok = None
    items = res if isinstance(res, (list, tuple)) else [res]
    for x in items:
        if isinstance(x, unreal.StaticMesh):
            sm = x
        else:
            s = str(x).upper()
            if 'SUCCESS' in s:
                ok = True
            elif 'FAIL' in s:
                ok = False
    return sm, ok


def _nanite_settings(on):
    try:
        ns = unreal.MeshNaniteSettings()
        _sp(ns, 'enabled', bool(on))
        return ns
    except Exception:
        return None


def write_static_mesh(dm, name, slot_mats, nanite):
    path = FACADE_DIR + '/' + name
    eal = unreal.EditorAssetLibrary
    sm = None
    if eal.does_asset_exist(path):
        existing = eal.load_asset(path)
        if isinstance(existing, unreal.StaticMesh) and F.get('copy_sm'):
            try:
                o = unreal.GeometryScriptCopyMeshToAssetOptions()
                _sp(o, 'enable_recompute_normals', False)
                _sp(o, 'enable_recompute_tangents', True)
                _sp(o, 'enable_remove_degenerates', True)
                _sp(o, 'replace_materials', True)
                _sp(o, 'new_materials', [MI.get(m) for m in slot_mats])
                _sp(o, 'new_material_slot_names', [unreal.Name(m) for m in slot_mats])
                ns = _nanite_settings(nanite)
                if ns is not None:
                    _sp(o, 'apply_nanite_settings', True)
                    _sp(o, 'nanite_settings', ns)
                _sp(o, 'emit_transaction', False)
                lod = unreal.GeometryScriptMeshWriteLOD()
                res = call('copy_sm', dm, existing, o, lod)
                s2, ok = _parse_outcome(res)
                if ok is not False:
                    sm = existing
                else:
                    err('copy_mesh_to_static_mesh devolvió falla para %s' % path)
            except Exception as e:
                err('copy_mesh_to_static_mesh falló para %s: %s' % (path, e))
        if sm is None:
            try:
                eal.delete_asset(path)
            except Exception as e:
                err('No se pudo borrar %s para recrearlo: %s' % (path, e))
    if sm is None:
        o = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
        _sp(o, 'enable_recompute_normals', False)
        _sp(o, 'enable_recompute_tangents', True)
        _sp(o, 'enable_nanite', bool(nanite))
        ns = _nanite_settings(nanite)
        if ns is not None:
            _sp(o, 'nanite_settings', ns)
        _sp(o, 'enable_collision', False)
        res = call('create_sm', dm, path, o)
        sm, ok = _parse_outcome(res)
        if sm is None and eal.does_asset_exist(path):
            sm = eal.load_asset(path)
        if sm is None:
            raise RuntimeError('create_new_static_mesh_asset_from_mesh no creó %s (resultado: %s)' % (path, res))
    apply_materials(sm, slot_mats)
    ensure_nanite(sm, nanite)
    return sm


def apply_materials(sm, slot_mats):
    try:
        cur = list(sm.get_editor_property('static_materials'))
    except Exception:
        cur = None
    if cur is not None:
        if len(cur) < len(slot_mats):
            warn('%s tiene %d slots y se esperaban %d' % (sm.get_name(), len(cur), len(slot_mats)))
        for i, smat in enumerate(cur):
            if i >= len(slot_mats):
                break
            mname = slot_mats[i]
            mi = MI.get(mname)
            if mi is not None:
                _sp(smat, 'material_interface', mi)
            _sp(smat, 'material_slot_name', unreal.Name(mname))
        try:
            sm.set_editor_property('static_materials', cur)
            return
        except Exception as e:
            warn('static_materials no se pudo asignar (%s); se usa set_material' % e)
    for i, mname in enumerate(slot_mats):
        mi = MI.get(mname)
        if mi is None:
            continue
        try:
            sm.set_material(i, mi)
        except Exception as e:
            err_once('set_material', 'set_material(%d) falló en %s: %s' % (i, sm.get_name(), e))


def ensure_nanite(sm, on):
    try:
        ns = sm.get_editor_property('nanite_settings')
        cur = bool(ns.get_editor_property('enabled'))
        if cur != bool(on):
            ns.set_editor_property('enabled', bool(on))
            sm.set_editor_property('nanite_settings', ns)
    except Exception as e:
        err_once('nanite', 'No se pudo fijar Nanite (%s)' % e)


def set_collision(sm, boxes):
    if not boxes:
        return
    if F.get('coll_from_mesh'):
        try:
            cm = new_mesh()
            o = popts(MATS[0])
            for (x0, x1, y0, y1, z0, z1) in boxes:
                if x1 - x0 < 0.5 or y1 - y0 < 0.5 or z1 - z0 < 0.5:
                    continue
                _box_raw(cm, o, T(((x0 + x1) * 0.5, (y0 + y1) * 0.5, z0)), x1 - x0, y1 - y0, z1 - z0, ORIGIN['base'])
            co = unreal.GeometryScriptCollisionFromMeshOptions()
            _sp(co, 'emit_transaction', False)
            _sp(co, 'method', unreal.GeometryScriptCollisionGenerationMethod.ALIGNED_BOXES)
            _sp(co, 'auto_detect_spheres', False)
            _sp(co, 'auto_detect_capsules', False)
            _sp(co, 'auto_detect_boxes', True)
            _sp(co, 'simplify_hulls', False)
            call('coll_from_mesh', cm, sm, co)
            return
        except Exception as e:
            err_once('coll', 'set_static_mesh_collision_from_mesh falló (%s); colisión de caja envolvente' % e)
    try:
        sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        sub.add_simple_collisions(sm, unreal.ScriptCollisionShapeType.BOX)
    except Exception:
        try:
            unreal.EditorStaticMeshLibrary.add_simple_collisions(sm, unreal.ScriptCollisionShapeType.BOX)
        except Exception as e:
            err_once('coll2', 'Sin colisión simple: %s' % e)


def tri_count(dm):
    if not F.get('tri_count'):
        return -1
    try:
        r = F['tri_count'](dm)
        if isinstance(r, (list, tuple)):
            r = [x for x in r if isinstance(x, int)][-1]
        return int(r)
    except Exception:
        return -1


def finalize(mb, asset_name, nanite=True, collision=True):
    """Combina las submallas por material, recalcula normales y crea/actualiza el/los StaticMesh.
    trace('ENTER finalize ' + repr(mb)[:120])
    Devuelve lista de StaticMesh (principal + vidrios si hay)."""
    out = []
    main = [m for m in mb.order if m not in NANITE_EXCLUDE]
    glass = [m for m in mb.order if m in NANITE_EXCLUDE]
    groups = []
    if main:
        groups.append((ASSET_PREFIX + asset_name, main, nanite and USE_NANITE, collision))
    if glass:
        groups.append((ASSET_PREFIX + asset_name + '_Vidrios', glass, False, False))
    for (name, mats, nan, col) in groups:
        try:
            final = None
            slot_mats = list(mats)
            compact = bool(F.get('clear_ids'))
            for i, m in enumerate(mats):
                sub = mb.subs[m]
                if compact:
                    try:
                        call('clear_ids', sub, clear_value=i)
                    except Exception as e:
                        err_once('clear_ids', 'clear_material_ids falló (%s); se usan IDs globales' % e)
                        compact = False
                        F['clear_ids'] = None
                if final is None:
                    final = sub
                else:
                    append_into(final, sub)
            if not compact:
                if CAPS.get('matid_opt'):
                    slot_mats = list(MATS)
                else:
                    err('%s: sin clear_material_ids ni material_id: un solo material' % name)
                    slot_mats = mats[:1]
            recompute_normals(final)
            sm = write_static_mesh(final, name, slot_mats, nan)
            if col:
                set_collision(sm, mb.coll)
            out.append(sm)
            log('Malla %s: %d triángulos, %d materiales, nanite=%s' % (name, tri_count(final), len(mats), nan))
        except Exception as e:
            err('No se pudo crear la malla %s: %s\n%s' % (name, e, traceback.format_exc()))
    return out


def spawn(sms, label, loc, rot=None, collision=True):
    trace('ENTER spawn ' + repr(sms)[:120])
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = []
    for i, sm in enumerate(sms or []):
        if sm is None:
            continue
        try:
            a = eas.spawn_actor_from_object(sm, V(loc), rot if rot is not None else R())
            if a is None:
                err('spawn_actor_from_object devolvió None para %s' % label)
                continue
            lbl = label if i == 0 else label + '_Vidrios'
            a.set_actor_label(lbl)
            a.set_folder_path(FOLDER)
            try:
                a.set_editor_property('tags', [unreal.Name(FOLDER)])
            except Exception:
                pass
            comp = a.get_component_by_class(unreal.StaticMeshComponent)
            if comp is not None:
                try:
                    comp.set_mobility(unreal.ComponentMobility.STATIC)
                except Exception:
                    pass
                if not collision or i > 0:
                    try:
                        comp.set_collision_profile_name('NoCollision')
                        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                    except Exception:
                        pass
            actors.append(a)
        except Exception as e:
            err('No se pudo colocar %s: %s' % (label, e))
    return actors


def clear_previous():
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    n = 0
    for a in eas.get_all_level_actors():
        try:
            fp = str(a.get_folder_path())
            tags = [str(t) for t in a.get_editor_property('tags')]
            if fp == FOLDER or fp.startswith(FOLDER + '/') or FOLDER in tags:
                eas.destroy_actor(a)
                n += 1
        except Exception:
            continue
    log('Borrados %d actores previos de la carpeta %s' % (n, FOLDER))


def ensure_map():
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        path = world.get_path_name() if world else ''
    except Exception:
        path = ''
    if 'L_Greybox' not in path:
        warn('El mapa abierto es "%s"; se abre %s' % (path, MAP_PATH))
        try:
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(MAP_PATH)
        except Exception as e:
            err('No se pudo abrir %s: %s' % (MAP_PATH, e))


def save_all():
    try:
        unreal.EditorAssetLibrary.save_directory(FACADE_DIR, only_if_is_dirty=False, recursive=True)
        log('Mallas guardadas en %s' % FACADE_DIR)
    except Exception as e:
        err('No se pudieron guardar las mallas: %s' % e)
    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
        log('Nivel guardado')
    except Exception:
        try:
            unreal.EditorLevelLibrary.save_current_level()
            log('Nivel guardado')
        except Exception as e:
            err('No se pudo guardar el nivel: %s' % e)


# =====================================================================================
# CUADRA
# =====================================================================================
RNG = random.Random(SEED)

LOTS = [
    # clave, y0 (mundo), frente, constructor, etiqueta
    ('A', 1550.0, 866.0, build_casa_a, 'CasaA_Baja'),
    ('B', 2416.0, 866.0, build_casa_b, 'CasaB_Jardin'),
    ('C', 3282.0, 866.0, build_casa_c, 'CasaC_DosPlantas'),
    ('D', 4148.0, 866.0, build_casa_d, 'CasaD_ChaletTejas'),
    ('E', 5014.0, 433.0, build_local_e, 'LocalE_Comercio'),
]

VEREDA_SEGS = [(1500.0, 1550.0, 'MI_Hormigon', 0.4), (1550.0, 2416.0, 'MI_Baldosa', 0.0),
               (2416.0, 3282.0, 'MI_Baldosa', 1.1), (3282.0, 4148.0, 'MI_Hormigon', -0.5),
               (4148.0, 5014.0, 'MI_Baldosa', 0.7), (5014.0, 5447.0, 'MI_PiedraLaja', 0.3),
               (5447.0, 5500.0, 'MI_Hormigon', 0.0)]
VEREDA_RAMPS = [(1590.0, 1860.0), (3317.0, 3617.0), (4488.0, 4978.0)]
VEREDA_PITS = [(240.0, 2170.0), (240.0, 2600.0), (240.0, 3800.0), (240.0, 4348.0)]
VEREDA_EXTRAS = [('tapa', 55.0, 2330.0, 22.0, 0.0), ('tapa', 40.0, 3700.0, 40.0, -0.5), ('tapa', 70.0, 3000.0, 22.0, 1.1),
                 ('tapa', 45.0, 4300.0, 30.0, 0.7), ('floja', 130.0, 2250.0, 'MI_Baldosa', 0.0),
                 ('floja', 90.0, 2600.0, 'MI_Baldosa', 1.1), ('floja', 170.0, 2640.0, 'MI_Baldosa', 1.1),
                 ('floja', 60.0, 4700.0, 'MI_Baldosa', 0.7), ('tocon', 240.0, 4348.0)]

POLES = {
    'PA': dict(kind='simple', loc=(LM_X + 255.0, 1525.0, 0.0), rot=(1.2, -0.8, 3.0)),
    'PB': dict(kind='lum', loc=(LM_X + 255.0, 2900.0, 0.0), rot=(-1.4, 2.1, -4.0)),
    'PC': dict(kind='lum', loc=(LM_X + 258.0, 4130.0, 0.0), rot=(0.9, 1.6, 6.0)),
    'PD': dict(kind='simple', loc=(LM_X + 255.0, 5420.0, 0.0), rot=(-2.2, -1.0, -2.0)),
    'PE': dict(kind='lum', loc=(LM_X + 855.0, 3500.0, 0.0), rot=(1.0, -2.4, 183.0)),
}

# etiqueta, posición, semilla, con copa, yaw base (0 = casas hacia -X; 180 en la vereda de enfrente)
TREES = [('Arbol_A', (LM_X + 240.0, 2170.0, 0.0), 11, False, 0.0),
         ('Arbol_B', (LM_X + 240.0, 2600.0, 0.0), 23, True, 0.0),
         ('Arbol_C', (LM_X + 240.0, 3800.0, 0.0), 19, False, 0.0),
         ('Arbol_Enfrente1', (LM_X + 860.0, 2300.0, 0.0), 37, False, 180.0),
         ('Arbol_Enfrente2', (LM_X + 860.0, 4500.0, 0.0), 41, False, 180.0)]

CANASTOS = [((LM_X + 255.0, 1930.0, 0.0), 2.0), ((LM_X + 55.0, 3842.0, 0.0), -3.0), ((LM_X + 250.0, 5214.0, 0.0), 4.0)]


def main():
    t0 = time.time()
    RNG.seed(SEED)
    log('==== build_facade.py: cuadra de prueba de Caseros (FacadeTest) ====')
    probe_api()
    if not F.get('box') or not F.get('append_mesh') or not (F.get('create_sm') or F.get('copy_sm')):
        err('Faltan funciones básicas de Geometry Script; ¿está habilitado el plugin GeometryScripting?')
        return
    try:
        calibrate()
    except Exception as e:
        err('Calibración falló: %s\n%s' % (e, traceback.format_exc()))
    ensure_map()
    clear_previous()
    load_materials()
    try:
        unreal.EditorAssetLibrary.make_directory(FACADE_DIR)
    except Exception:
        pass

    total = len(LOTS) + 12
    with unreal.ScopedSlowTask(total, 'Construyendo cuadra FacadeTest...') as task:
        task.make_dialog(True)
        houses = []
        for (key, y0, W, fn, label) in LOTS:
            task.enter_progress_frame(1, 'Lote %s' % label)
            mb = piece('Lote %s' % key, fn, W)
            if mb is None:
                continue
            sms = finalize(mb, label)
            spawn(sms, 'FT_' + label, (LM_X, y0, 0.0))
            houses.append({'key': key, 'origin': (LM_X, y0, 0.0), 'anchors': mb.anchors, 'W': W})

        task.enter_progress_frame(1, 'Medianeras de los vecinos')
        mbl = piece('Medianera L', build_medianera, 'MedianeraL', 1300.0, 960.0, 1, 'MI_Ladrillo', 'MI_Revoque_Gris', True)
        if mbl:
            spawn(finalize(mbl, 'Medianera_Izq'), 'FT_Medianera_Izq', (LM_X, 1520.0, 0.0))
        mbr = piece('Medianera R', build_medianera, 'MedianeraR', 1100.0, 620.0, -1, 'MI_Revoque_Gris', 'MI_Revoque_Blanco', False)
        if mbr:
            spawn(finalize(mbr, 'Medianera_Der'), 'FT_Medianera_Der', (LM_X, 5447.0, 0.0))

        task.enter_progress_frame(1, 'Vereda')
        mbv = piece('Vereda', build_vereda, 'Vereda', VEREDA_SEGS, VEREDA_RAMPS, VEREDA_PITS, VEREDA_EXTRAS)
        if mbv:
            spawn(finalize(mbv, 'Vereda'), 'FT_Vereda', (LM_X, 0.0, 0.0))

        task.enter_progress_frame(1, 'Calle')
        mbc = piece('Calle', build_calle, 1500.0, 5500.0)
        if mbc:
            spawn(finalize(mbc, 'Calle'), 'FT_Calle', (LM_X, 0.0, 0.0))

        task.enter_progress_frame(1, 'Vereda y tapial de enfrente')
        # marco rotado 180°: x local 0 = frente del tapial (LM_X+1100), y local = 5500 - y mundo;
        # la cara del cordón queda en x local 300 = calle x 800 (fin de la cuneta de enfrente)
        mbo = piece('Vereda enfrente', build_vereda, 'VeredaEnfrente', [(0.0, 4000.0, 'MI_Baldosa', 0.5)],
                    [(2400.0, 2700.0)], [(240.0, 3200.0), (240.0, 1000.0)],
                    [('tapa', 60.0, 1800.0, 30.0, 0.5), ('floja', 120.0, 3500.0, 'MI_Baldosa', 0.5)])
        if mbo:
            spawn(finalize(mbo, 'VeredaEnfrente'), 'FT_VeredaEnfrente', (LM_X + 1100.0, 5500.0, 0.0), R(yaw=180.0))
        mbt = piece('Tapial', build_tapial, 4000.0)
        if mbt:
            spawn(finalize(mbt, 'TapialEnfrente'), 'FT_TapialEnfrente', (LM_X + 1100.0, 5500.0, 0.0), R(yaw=180.0))

        task.enter_progress_frame(1, 'Postes')
        pole_assets = {}
        for kind in ('lum', 'simple'):
            mbp = piece('Poste %s' % kind, build_poste, kind)
            if mbp:
                pole_assets[kind] = finalize(mbp, 'Poste_' + ('Luminaria' if kind == 'lum' else 'Simple'))
        poles_rt = {}
        for pn, pd in sorted(POLES.items()):
            rot = R(roll=pd['rot'][0], pitch=pd['rot'][1], yaw=pd['rot'][2])
            poles_rt[pn] = {'kind': pd['kind'], 'loc': pd['loc'], 'rot': rot}
            if pd['kind'] in pole_assets:
                spawn(pole_assets[pd['kind']], 'FT_Poste_' + pn, pd['loc'], rot)

        task.enter_progress_frame(1, 'Árboles')
        tree_cache = {}
        for (lbl, loc, seed, copa, yaw0) in TREES:
            key = 'copa' if copa else 'fresno%d' % (seed % 3)
            if key not in tree_cache:
                mba = piece('Arbol %s' % lbl, build_arbol, seed, copa)
                tree_cache[key] = finalize(mba, 'ArbolVereda_' + key) if mba else []
            spawn(tree_cache[key], 'FT_' + lbl, loc, R(yaw=yaw0 + RNG.uniform(-20.0, 20.0)))

        task.enter_progress_frame(1, 'Canastos')
        mbk = piece('Canasto', build_canasto)
        if mbk:
            ck = finalize(mbk, 'CanastoBasura')
            for i, (loc, yaw) in enumerate(CANASTOS):
                spawn(ck, 'FT_Canasto_%d' % (i + 1), loc, R(yaw=yaw))

        task.enter_progress_frame(1, 'Cables')
        mbw = piece('Cables', build_cables, poles_rt, houses)
        if mbw:
            spawn(finalize(mbw, 'Cables', nanite=True, collision=False), 'FT_Cables', (0.0, 0.0, 0.0), None, False)

        task.enter_progress_frame(1, 'Guardando')
        save_all()

    log('Piezas OK: %d  |  piezas con error: %d  |  %.1f s' % (STATS['ok'], STATS['fail'], time.time() - t0))
    if STATS['fail']:
        warn('Hubo piezas con error: buscar "[ARTE] Pieza" en el Output Log')
    log('FACHADA LISTA')


main()
