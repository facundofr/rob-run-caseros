# -*- coding: utf-8 -*-
"""
barrio_kit.py  -  Kit procedural de Barrio (Geometry Script, UE 5.8.4).

Derivado de build_facade.py (pase v1, que se deja intacto). Este módulo NO hace nada al importarse:
build_barrio.py llama a init() / reset_state() al principio de cada corrida (no queda estado de
Unreal vivo entre corridas: dicts y caches se vacían; el módulo además se vuelve a importar).

Cambios respecto del v1:
  * Materiales v2 (CONVENCIONES.md v2): tierra/follaje/plástico/puertas con sus MI propias.
  * Espejado en construcción (MIRROR): y -> W - y en todas las primitivas (variantes espejadas).
  * Casas con profundidad y ancho parametrizables, puertas de madera con MI_Madera_Puerta.
  * Mallas en /Game/Barrio/Art/Mapa/SM_M_*; un SM existente se actualiza con copy_mesh_to_static_mesh
    (nunca se borra: si la copia falla se crea con otro nombre).
  * Colisión: cajas alineadas, o casco convexo por componente si la malla tiene rampas.
  * Trace a archivo con flush (sin fsync por llamada: el flush ya sobrevive a un crash del proceso).

Notas de API (UE 5.x; las firmas cambian entre versiones; todo pasa por call(), que reintenta posicional):
  append_box(mesh, opts, transform, dimension_x, dimension_y, dimension_z, steps_x, steps_y, steps_z, origin)
  append_cylinder(mesh, opts, transform, radius, height, radial_steps, height_steps, capped, origin)
  append_cone(mesh, opts, transform, base_radius, top_radius, height, radial_steps, height_steps, capped, origin)
  append_sphere_lat_long(mesh, opts, transform, radius, steps_phi, steps_theta, origin)
  append_simple_extrude_polygon(mesh, opts, transform, polygon_vertices, height, height_steps, capped, origin)
  append_simple_swept_polygon(mesh, opts, transform, polygon_vertices, sweep_path, loop, capped, start_scale,
                              end_scale, rotation_angle_deg, mitre_limit)
  append_revolve_path / append_torus / append_linear_stairs (ver uso)
  GeometryScript_MeshBooleans.apply_mesh_boolean(target, target_transform, tool, tool_transform, op, options)
  GeometryScript_MeshEdits.append_mesh(target, append_mesh, append_transform, defer_change_notifications)
  GeometryScript_Materials.clear_material_i_ds(mesh, clear_value)
  GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh, path, options) -> (SM, Outcome)
  GeometryScript_AssetUtils.copy_mesh_to_static_mesh(mesh, sm, options, target_lod) -> (SM, Outcome)
  GeometryScript_Collision.set_static_mesh_collision_from_mesh(mesh, sm, options)
"""

import unreal
import math
import random
import time
import traceback
import os

_TRACE = None
TRACE_CALLS = False          # True: cada llamada a Geometry Script va al trace (lento; solo para cazar crashes)


def trace_open(path):
    global _TRACE
    trace_close()
    try:
        _TRACE = open(path, 'w', encoding='utf-8')
    except Exception:
        _TRACE = None


def trace_close():
    global _TRACE
    try:
        if _TRACE is not None:
            _TRACE.close()
    except Exception:
        pass
    _TRACE = None


def trace(msg):
    if _TRACE is None:
        return
    try:
        _TRACE.write(msg + '\n')
        _TRACE.flush()
    except Exception:
        pass

# =====================================================================================
# CONFIGURACIÓN
# =====================================================================================
ASSET_DIR = '/Game/Barrio/Art/Mapa'
MAT_DIR = '/Game/Barrio/Art/Materials'
MAP_PATH = '/Game/Barrio/Maps/L_Greybox'
FOLDER = 'Barrio'
GEN_TAG = 'BarrioGen'
ASSET_PREFIX = 'SM_M_'

USE_BOOLEANS = True          # recorte de vanos con apply_mesh_boolean (si falla, se arma por paños)
USE_NANITE = True            # Nanite en las mallas opacas (vidrios/agua/alambrado en malla aparte sin Nanite)
SPLIT_NORMAL_ANGLE = 40.0    # aristas de más de 40° quedan duras (cajas y chaflanes), cilindros suaves
SEED = 5258

Z_VER = 16.0                 # cara superior de la vereda (cordón de 16 cm; calzada en Z~0-5)
Z_PISO = 30.0                # piso interior de las casas
WALL_T = 30.0                # espesor de muro

MATS = ['MI_Revoque_Blanco', 'MI_Revoque_Gris', 'MI_Revoque_Rosa', 'MI_Revoque_VerdeAgua',
        'MI_Revoque_Amarillo', 'MI_Ladrillo', 'MI_Baldosa', 'MI_Asfalto', 'MI_Hormigon',
        'MI_Chapa_Gris', 'MI_Chapa_Verde', 'MI_Madera', 'MI_Tejas', 'MI_Metal_Negro',
        'MI_Metal_Verde', 'MI_PiedraLaja', 'MI_Vidrio', 'MI_PosteMadera', 'MI_Cable',
        # v2
        'MI_Corteza', 'MI_PosteHormigon', 'MI_Tierra', 'MI_Pasto', 'MI_Agua', 'MI_Hormigon_Bacheo',
        'MI_Madera_Puerta', 'MI_Follaje', 'MI_Plastico_Negro', 'MI_Neumatico',
        'MI_Auto_Blanco', 'MI_Auto_Gris', 'MI_Auto_Rojo', 'MI_Auto_Azul', 'MI_Auto_Negro',
        'MI_Pintura_Blanca', 'MI_Pintura_Amarilla', 'MI_Comisaria_Azul', 'MI_Cartel_Blanco',
        'MI_Cartel_Rojo', 'MI_Cartel_Verde', 'MI_Cartel_Azul', 'MI_Vidrio_Local', 'MI_Emisivo_Calido',
        'MI_Emisivo_Baliza_Azul', 'MI_Emisivo_Baliza_Roja', 'MI_Riel', 'MI_Durmiente', 'MI_Balasto',
        'MI_Alambrado']
MAT_INDEX = dict((m, i) for i, m in enumerate(MATS))
# posibles materiales translúcidos/enmascarados: van en una malla aparte sin Nanite y sin sombra
NANITE_EXCLUDE = set(['MI_Vidrio', 'MI_Vidrio_Local', 'MI_Agua', 'MI_Alambrado'])

# Materiales "de función" (antes eran placeholders del v1)
M_TIERRA = 'MI_Tierra'
M_FOLLAJE = 'MI_Follaje'
M_PLASTICO = 'MI_Plastico_Negro'
M_AC = 'MI_Pintura_Blanca'
M_PORCELANA = 'MI_Pintura_Blanca'
M_TELA = 'MI_Cartel_Blanco'
M_ALUMINIO = 'MI_Chapa_Gris'
M_HIERRO = 'MI_Metal_Negro'
M_PUERTA = 'MI_Madera_Puerta'

# =====================================================================================
# LOG
# =====================================================================================
_ERR_COUNT = {}
STATS = {'ok': 0, 'fail': 0}


def log(msg):
    trace("LOG " + str(msg))
    unreal.log('[BARRIO] ' + msg)


def warn(msg):
    trace("WARN " + str(msg))
    unreal.log_warning('[BARRIO] ' + msg)


def err(msg):
    trace("ERR " + str(msg))
    unreal.log_error('[BARRIO] ' + msg)


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
        STATS.setdefault('fail_names', []).append(str(name))
        if STATS['fail'] <= 40:
            err('Pieza "%s" falló: %s\n%s' % (name, e, traceback.format_exc()))
        elif STATS['fail'] == 41:
            err('Más de 40 piezas con error: se silencian los detalles (ver el resumen final)')
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
    ('stairs', 'prim', ['append_linear_stairs']),
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
    if TRACE_CALLS:
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
# -------------------------------------------------------------------------------------
# Mallas dinámicas: SIEMPRE de un DynamicMeshPool (el pool es su dueño para el GC de Unreal).
# Crear unreal.DynamicMesh() sueltos desde Python y guardarlos en caches provocó crashes
# (EXCEPTION_ACCESS_VIOLATION en python311.dll desde la recolección de basura, minutos después).
# Al terminar cada pieza se devuelven al pool (free_mesh / MB.release) y al final shutdown()
# hace free_all_meshes(), vacía todos los caches del módulo y fuerza gc + collect_garbage.
# -------------------------------------------------------------------------------------
POOL = {'pool': None, 'requested': 0, 'returned': 0}


def pool_open():
    POOL['requested'] = 0
    POOL['returned'] = 0
    POOL['pool'] = None
    try:
        POOL['pool'] = unreal.DynamicMeshPool()
    except Exception:
        try:
            POOL['pool'] = unreal.new_object(unreal.DynamicMeshPool)
        except Exception as e:
            POOL['pool'] = None
            warn('No hay DynamicMeshPool (%s): se usan DynamicMesh sueltos' % e)


def new_mesh():
    pool = POOL.get('pool')
    if pool is not None:
        try:
            m = pool.request_mesh()
            POOL['requested'] += 1
            try:
                m.reset()
            except Exception:
                pass
            return m
        except Exception as e:
            err_once('pool', 'DynamicMeshPool.request_mesh falló (%s)' % e)
    try:
        return unreal.DynamicMesh()
    except Exception:
        return unreal.new_object(unreal.DynamicMesh)


def free_mesh(m):
    """Devuelve una malla al pool (se resetea y se reutiliza)."""
    pool = POOL.get('pool')
    if pool is None or m is None:
        return
    try:
        pool.return_mesh(m)
        POOL['returned'] += 1
    except Exception as e:
        err_once('pool_ret', 'DynamicMeshPool.return_mesh falló (%s)' % e)


def pool_close():
    pool = POOL.get('pool')
    if pool is not None:
        try:
            pool.free_all_meshes()
        except Exception as e:
            warn('free_all_meshes falló: %s' % e)
    POOL['pool'] = None


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


# Espejado en construcción: con MIRROR['on'] todas las primitivas reflejan y -> W - y.
MIRROR = {'on': False, 'W': 0.0}


def mirror_begin(W):
    MIRROR['on'] = True
    MIRROR['W'] = float(W)


def mirror_end():
    MIRROR['on'] = False


def _my(y):
    return MIRROR['W'] - y if MIRROR['on'] else y


def _mp(p):
    return (p[0], MIRROR['W'] - p[1], p[2]) if MIRROR['on'] else p


class MB(object):
    """Constructor de malla: una DynamicMesh por material + cajas de colisión + rampas + anclajes."""

    def __init__(self, name):
        self.name = name
        self.subs = {}
        self.order = []
        self.coll = []
        self.ramps = []      # colisión convexa: (pts, axis, a0, a1) en coordenadas finales
        self.anchors = {}
        self.meta = {}

    def m(self, mat):
        if mat not in self.subs:
            self.subs[mat] = new_mesh()
            self.order.append(mat)
        return self.subs[mat]

    def release(self):
        """Devuelve las submallas al pool. Después de esto el MB no se puede usar."""
        for k in list(self.subs.keys()):
            free_mesh(self.subs[k])
        self.subs = {}
        self.order = []

    def col(self, x0, x1, y0, y1, z0, z1):
        y0, y1 = _my(y0), _my(y1)
        self.coll.append((min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)))

    def ramp(self, pts, axis, a0, a1):
        """Pieza de colisión con pendiente (perfil extruido), se genera como casco convexo."""
        pts, axis, a0, a1 = _mirror_prism(pts, axis, a0, a1)
        self.ramps.append((list(pts), axis, a0, a1))


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


def place(mb, mat, src, loc, yaw=0.0):
    """Agrega una plantilla (DynamicMesh) en loc con yaw, respetando el espejado."""
    if MIRROR['on']:
        loc = _mp(loc)
        yaw = -yaw
    append_into(mb.m(mat), src, T(loc, R(yaw=yaw)))


def _mirror_prism(pts, axis, a0, a1):
    if not MIRROR['on']:
        return pts, axis, a0, a1
    W = MIRROR['W']
    if axis == 'y':
        return pts, axis, W - a1, W - a0
    if axis == 'x':
        return [(W - p, q) for (p, q) in pts], axis, a0, a1
    return [(p, W - q) for (p, q) in pts], axis, a0, a1


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
    _box_raw(mb.m(mat), popts(mat), T(((x0 + x1) * 0.5, _my((y0 + y1) * 0.5), z0)), dx, dy, dz, ORIGIN['base'])


def rbox(mb, mat, cx, cy, z0, dx, dy, dz, yaw=0.0, pitch=0.0, roll=0.0):
    """Caja rotada alrededor del centro de su base."""
    if MIRROR['on']:
        cy, yaw, roll = _my(cy), -yaw, -roll
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
    if MIRROR['on']:
        pts, axis, a0, a1 = _mirror_prism(pts, axis, a0, a1)
        MIRROR['on'] = False
        try:
            prism(mb, mat, pts, axis, a0, a1)
        finally:
            MIRROR['on'] = True
        return
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
    p0, p1 = _mp(p0), _mp(p1)
    d = v_sub(p1, p0)
    L = v_len(d)
    if L < 0.02 or r <= 0:
        return
    mid = v_lerp(p0, p1, 0.5)
    _cyl_raw(mb.m(mat), popts(mat), T(mid, rot_z_to(d)), r, L, sides, capped, ORIGIN['center'])


def cone(mb, mat, p0, p1, r0, r1, sides=10):
    p0, p1 = _mp(p0), _mp(p1)
    d = v_sub(p1, p0)
    L = v_len(d)
    if L < 0.02:
        return
    _cone_raw(mb.m(mat), popts(mat), T(p0, rot_z_to(d)), r0, max(r1, 0.0), L, sides, True, ORIGIN['base'])


def blob(mb, mat, c, rx, ry, rz, yaw=0.0, steps=(8, 12), pitch=0.0, roll=0.0):
    """Elipsoide (esfera escalada), con rotación opcional."""
    if MIRROR['on']:
        c, yaw, roll = _mp(c), -yaw, -roll
        MIRROR['on'] = False
        try:
            blob(mb, mat, c, rx, ry, rz, yaw, steps, pitch, roll)
        finally:
            MIRROR['on'] = True
        return
    if not F.get('sphere'):
        cbox(mb, mat, c[0] - rx * 0.8, c[0] + rx * 0.8, c[1] - ry * 0.8, c[1] + ry * 0.8,
             c[2] - rz * 0.8, c[2] + rz * 0.8, min(rx, ry, rz) * 0.3, 'z')
        return
    call('sphere', mb.m(mat), popts(mat), T(c, R(roll=roll, pitch=pitch, yaw=yaw), (rx / 50.0, ry / 50.0, rz / 50.0)),
         radius=50.0, steps_phi=int(steps[0]), steps_theta=int(steps[1]), origin=ORIGIN['center'])


def torus(mb, mat, center, rmaj, rmin, normal=(0, 0, 1), smaj=20, smin=6):
    if MIRROR['on']:
        center, normal = _mp(center), (normal[0], -normal[1], normal[2])
        MIRROR['on'] = False
        try:
            torus(mb, mat, center, rmaj, rmin, normal, smaj, smin)
        finally:
            MIRROR['on'] = True
        return
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
    if MIRROR['on']:
        pts = [_mp(p) for p in pts]
        MIRROR['on'] = False
        try:
            tube(mb, mat, pts, r, sides)
        finally:
            MIRROR['on'] = True
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
    if MIRROR['on']:
        W = MIRROR['W']
        holes = [(W - h[1], W - h[0], h[2], h[3]) for h in holes]
        MIRROR['on'] = False
        try:
            wall_holes(mb, mat, x0, x1, W - y1, W - y0, z0, z1, holes)
        finally:
            MIRROR['on'] = True
        return
    hs = [h for h in holes if h[1] > h[0] and h[3] > h[2]]
    if USE_BOOLEANS and F.get('boolean') and hs and CAPS.get('boolean_ok', True):
        wm = tool = None
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
        finally:
            free_mesh(wm)
            free_mesh(tool)
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
    lm = o.get('hoja', M_PUERTA)
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
def build_casa_a(W, depth=860.0, alto=False):
    mb = MB('CasaA')
    wm, sm_ = 'MI_Revoque_Blanco', 'MI_Revoque_Gris'
    xf = 0.0
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
          dict(hoja=M_PUERTA, estilo='tablero', aplique=True))
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
    zt_base = zr + 2.0
    if alto:
        # ampliación en planta alta, retirada 2,2 m del frente, de ladrillo hueco sin revocar
        # (muy de Caseros), con columnas y losa de hormigón y una ventana al frente
        ax0, ax1 = xb + 40.0, xf - 220.0
        za0, za1 = zr + 2.0, zr + 282.0
        wa = (300.0, 520.0, za0 + 95.0, za0 + 215.0)
        piece('A2 frente', wall_holes, mb, 'MI_Ladrillo', ax1 - 20.0, ax1, 15.0, W - 15.0, za0, za1, [win_hole(*wa)])
        piece('A2 ventana', k_window, mb, 'MI_Ladrillo', ax1, wa[0], wa[1], wa[2], wa[3],
              dict(persiana='enrollar', cerrada=0.35, marco=M_ALUMINIO, persiana_mat=M_TELA, alfeizar='MI_Hormigon',
                   cortina=False))
        box(mb, 'MI_Ladrillo', ax0, ax1 - 20.0, 15.0, 35.0, za0, za1)
        box(mb, 'MI_Ladrillo', ax0, ax1 - 20.0, W - 35.0, W - 15.0, za0, za1)
        box(mb, 'MI_Ladrillo', ax0, ax0 + 20.0, 35.0, W - 35.0, za0, za1)
        for (cy0, cy1) in ((10.0, 40.0), (W - 40.0, W - 10.0), (0.5 * W - 12.0, 0.5 * W + 12.0)):
            box(mb, 'MI_Hormigon', ax1 - 24.0, ax1 + 1.5, cy0, cy1, za0, za1)
        cbox(mb, 'MI_Hormigon', ax0 - 4.0, ax1 + 6.0, 6.0, W - 6.0, za1, za1 + 16.0, 1.2, 'y')
        for (cy0, cy1) in ((10.0, 40.0), (W - 40.0, W - 10.0)):      # hierros esperando la próxima losa
            for k in range(3):
                cyl(mb, M_HIERRO, (ax1 - 12.0, cy0 + 8.0 + k * 7.0, za1 + 16.0),
                    (ax1 - 12.0 + RNG.uniform(-3, 3), cy0 + 8.0 + k * 7.0, za1 + 16.0 + RNG.uniform(45.0, 70.0)), 0.6, 5)
        mb.col(ax0, ax1, 15.0, W - 15.0, za0, za1 + 16.0)
        zt_base = za1 + 16.0
        tx = ax0 + 200.0
    else:
        tx = xb + 260.0
    piece('A tanque', k_tanque_plastico, mb, tx, 250.0, zt_base, 55.0, 120.0, 'hormigon')
    if not alto:
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


def build_casa_b(W, depth=900.0):
    mb = MB('CasaB')
    wm, sm_ = 'MI_Revoque_VerdeAgua', 'MI_Revoque_Gris'
    xf = -300.0
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
          dict(hoja=M_PUERTA, estilo='tablero', banderola=62.0, marco='MI_Madera', base_z=z_patio,
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


def build_casa_c(W, depth=860.0):
    mb = MB('CasaC')
    wm, sm_ = 'MI_Revoque_Amarillo', 'MI_Ladrillo'
    xf = 0.0
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
            place(mb, mat, tpl, (xc, y, zb + 10.0))       # place() respeta el espejado
        y += 15.0
    x = xf + 14.0
    while x < xe - 26.0:
        for yy in (y0 + 8.0, y1 - 8.0):
            place(mb, mat, tpl, (x, yy, zb + 10.0))
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


def build_casa_d(W, depth=900.0):
    mb = MB('CasaD')
    wm, sm_ = 'MI_Revoque_Rosa', 'MI_Revoque_Gris'
    xf = -450.0
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
          dict(hoja=M_PUERTA, estilo='vidriada', marco='MI_Madera', base_z=z_patio, aplique=True))
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
def build_local_e(W, depth=860.0, toldo=True):
    """Local comercial de un lote (W ~866): cortina metálica, puerta vidriada, vidriera con reja,
    cartel corrido en blanco (slot MI_Cartel_Verde, se recolorea por instancia) y toldo de lona."""
    mb = MB('LocalE')
    wm, sm_ = 'MI_Ladrillo', 'MI_Revoque_Gris'
    xf = 0.0
    xb = xf - depth
    zr, zp = 400.0, 470.0
    cort = (30.0, 0.52 * W, Z_VER, 285.0)
    door = (cort[1] + 30.0, cort[1] + 120.0, Z_PISO, 240.0)
    vid = (door[1] + 45.0, W - 40.0, 70.0, 250.0)
    holes = [cort, door]
    if vid[1] - vid[0] > 80.0:
        holes.append(win_hole(*vid))
    piece('E cascaron', shell, mb, W, xf, depth, zr, zp, wm, sm_, holes, parapet_mat='MI_Revoque_Gris',
          coping_mat='MI_Hormigon')
    piece('E faja', cbox, mb, 'MI_Revoque_Gris', xf - 1.0, xf + 2.0, 0.0, W, zr - 12.0, zr + 1.0, 0.8, 'y')
    piece('E cortina', k_cortina_local, mb, xf, cort[0], cort[1], cort[2], cort[3])
    piece('E dintel', cbox, mb, 'MI_Hormigon', xf - 30.0, xf + 1.0, cort[0] - 15.0, cort[1] + 15.0, cort[3],
          cort[3] + 20.0, 0.6, 'y')
    piece('E umbral', k_umbral, mb, 'MI_Hormigon', xf, cort[0], cort[1], Z_VER, Z_VER + 1.0)
    piece('E puerta', k_door, mb, xf, door[0], door[1], door[2], door[3],
          dict(hoja='MI_Chapa_Gris', estilo='vidriada', marco=M_HIERRO, umbral_mat='MI_Hormigon'))
    if vid[1] - vid[0] > 80.0:
        piece('E vidriera', k_window, mb, wm, xf, vid[0], vid[1], vid[2], vid[3],
              dict(reja='cuadricula', persiana=None, marco=M_ALUMINIO, alfeizar='MI_Hormigon', cortina=False))
        # interior de la vidriera: estantes con mercadería (cajas de colores)
        for k in range(3):
            zz = vid[2] + 20.0 + k * 55.0
            box(mb, M_ALUMINIO, xf - 75.0, xf - 45.0, vid[0] + 6.0, vid[1] - 6.0, zz, zz + 2.0)
            y = vid[0] + 10.0
            while y < vid[1] - 25.0:
                w = RNG.uniform(10.0, 24.0)
                box(mb, RNG.choice(['MI_Cartel_Rojo', 'MI_Cartel_Azul', 'MI_Cartel_Blanco', 'MI_Cartel_Verde']),
                    xf - 72.0, xf - 50.0, y, y + w, zz + 2.0, zz + 2.0 + RNG.uniform(12.0, 30.0))
                y += w + RNG.uniform(2.0, 8.0)
        box(mb, 'MI_Emisivo_Calido', xf - 120.0, xf - 118.0, vid[0], vid[1], vid[3] - 20.0, vid[3])
    # cartel corrido sin texto
    piece('E cartel', cbox, mb, 'MI_Cartel_Verde', xf, xf + 9.0, 25.0, W - 25.0, 300.0, 372.0, 1.0, 'y')
    piece('E cartel panel', box, mb, 'MI_Cartel_Blanco', xf + 9.0, xf + 9.5, 40.0, W - 40.0, 312.0, 360.0)
    for yb in (70.0, 0.5 * W, W - 70.0):
        piece('E cartel soporte', box, mb, M_HIERRO, xf, xf + 9.0, yb - 1.0, yb + 1.0, 292.0, 300.0)
    if toldo and vid[1] - vid[0] > 80.0:
        # toldo de lona rebatible sobre la vidriera
        y0t, y1t = vid[0] - 15.0, vid[1] + 15.0
        prism(mb, 'MI_Cartel_Rojo', [(xf, 282.0), (xf + 4.0, 282.0), (xf + 115.0, 236.0), (xf + 115.0, 222.0),
                                     (xf + 111.0, 222.0), (xf + 111.0, 234.0)], 'y', y0t, y1t)
        for yb in (y0t + 5.0, y1t - 5.0):
            cyl(mb, M_HIERRO, (xf + 2.0, yb, 282.0), (xf + 112.0, yb, 236.0), 1.2, 6)
    piece('E zocalo', k_zocalo, mb, 'MI_Hormigon', xf, 0.0, W, 40.0, [(cort[0] - 1.0, cort[1] + 1.0),
                                                                      (door[0] - 6.0, door[1] + 6.0)])
    anc = piece('E bajada', k_bajada, mb, xf, W - 20.0, 120.0, 500.0)
    piece('E split', k_split, mb, xf, door[1] + 10.0 if door[1] + 60.0 < W else door[0] - 50.0, 300.0, -1)
    tx, ty = xb + 200.0, 220.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(mb, 'MI_Hormigon', tx + sx * 48.0 - 6.0, tx + sx * 48.0 + 6.0, ty + sy * 48.0 - 6.0,
                ty + sy * 48.0 + 6.0, zr + 2.0, zr + 40.0)
    piece('E tanque', cbox, mb, 'MI_Hormigon', tx - 60.0, tx + 60.0, ty - 60.0, ty + 60.0, zr + 40.0, zr + 140.0, 3.0, 'z')
    piece('E tapa', cbox, mb, 'MI_Hormigon', tx - 63.0, tx + 63.0, ty - 63.0, ty + 63.0, zr + 140.0, zr + 145.0, 1.5, 'y')
    mb.col(tx - 60.0, tx + 60.0, ty - 60.0, ty + 60.0, zr, zr + 145.0)
    mb.anchors = {'power': anc or (xf + 20.0, W - 20.0, 495.0), 'tel': [(xf + 2.0, 120.0, 440.0)],
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



def _sm_path(name):
    return ASSET_DIR + '/' + name


def write_static_mesh(dm, name, slot_mats, nanite):
    """Crea o actualiza el StaticMesh. Un SM existente NUNCA se borra: se le copia la malla encima
    (copy_mesh_to_static_mesh); si eso falla se crea uno nuevo con sufijo _b, _c..."""
    path = _sm_path(name)
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
            for suf in ('_b', '_c', '_d', '_e'):
                if not eal.does_asset_exist(path + suf):
                    warn('%s no se pudo actualizar: se crea %s%s (el viejo queda sin uso)' % (path, name, suf))
                    path = path + suf
                    break
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



def set_collision(sm, boxes, ramps=None):
    """Colisión simple. Sin rampas: una caja alineada por caja pedida. Con rampas: un casco convexo
    por componente (las cajas siguen siendo cajas; las rampas quedan con su pendiente)."""
    ramps = ramps or []
    if not boxes and not ramps:
        return
    if F.get('coll_from_mesh'):
        cm = None
        try:
            cm = new_mesh()
            o = popts(MATS[0])
            for (x0, x1, y0, y1, z0, z1) in boxes:
                if x1 - x0 < 0.5 or y1 - y0 < 0.5 or z1 - z0 < 0.5:
                    continue
                _box_raw(cm, o, T(((x0 + x1) * 0.5, (y0 + y1) * 0.5, z0)), x1 - x0, y1 - y0, z1 - z0, ORIGIN['base'])
            one = _One(cm)
            for (pts, axis, a0, a1) in ramps:
                prism(one, MATS[0], pts, axis, a0, a1)
            co = unreal.GeometryScriptCollisionFromMeshOptions()
            _sp(co, 'emit_transaction', False)
            meth = unreal.GeometryScriptCollisionGenerationMethod
            _sp(co, 'method', meth.CONVEX_HULLS if ramps else meth.ALIGNED_BOXES)
            _sp(co, 'auto_detect_spheres', False)
            _sp(co, 'auto_detect_capsules', False)
            _sp(co, 'auto_detect_boxes', True)
            _sp(co, 'simplify_hulls', False)
            _sp(co, 'remove_fully_contained_shapes', False)
            call('coll_from_mesh', cm, sm, co)
            return
        except Exception as e:
            err_once('coll', 'set_static_mesh_collision_from_mesh falló (%s); colisión de caja envolvente' % e)
        finally:
            free_mesh(cm)
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



ASSETS_MADE = []


def finalize(mb, asset_name, nanite=True, collision=True):
    """Combina las submallas por material, recalcula normales y crea/actualiza el/los StaticMesh.
    Devuelve lista de StaticMesh (principal + vidrios si hay). Siempre devuelve las mallas al pool."""
    trace('ENTER finalize ' + asset_name)
    out = []
    if mb is None:
        return out
    try:
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
                    set_collision(sm, mb.coll, mb.ramps)
                out.append(sm)
                ASSETS_MADE.append(name)
                STATS['meshes'] = STATS.get('meshes', 0) + 1
                if VERBOSE_MESHES:
                    log('Malla %s: %d triángulos, %d materiales, nanite=%s' % (name, tri_count(final), len(mats), nan))
            except Exception as e:
                STATS['mesh_fail'] = STATS.get('mesh_fail', 0) + 1
                err('No se pudo crear la malla %s: %s\n%s' % (name, e, traceback.format_exc()))
    finally:
        mb.release()
    return out


VERBOSE_MESHES = False


def slot_index(sm, mat_name):
    """Índice del slot cuyo nombre es mat_name (los slots se nombran como su MI)."""
    try:
        for i, smat in enumerate(sm.get_editor_property('static_materials')):
            if str(smat.get_editor_property('material_slot_name')) == mat_name:
                return i
    except Exception:
        pass
    return -1


def _actor_setup(a, label, folder):
    a.set_actor_label(label)
    a.set_folder_path(folder)
    try:
        a.set_editor_property('tags', [unreal.Name(GEN_TAG)])
    except Exception:
        pass


def spawn(sms, label, loc, rot=None, collision=True, folder=None, scale=None, swaps=None, shadow=True):
    """Coloca un actor StaticMeshActor por malla (principal + vidrios).
    swaps: {nombre_slot: nombre_MI} -> override de material en el componente (variantes de color)."""
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = []
    folder = folder or FOLDER
    for i, sm in enumerate(sms or []):
        if sm is None:
            continue
        try:
            a = eas.spawn_actor_from_object(sm, V(loc), rot if rot is not None else R())
            if a is None:
                err_once('spawn_none', 'spawn_actor_from_object devolvió None para %s' % label)
                continue
            _actor_setup(a, label if i == 0 else label + '_Vidrios', folder)
            if scale is not None:
                a.set_actor_scale3d(V(scale))
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
                    try:
                        comp.set_editor_property('can_ever_affect_navigation', False)
                    except Exception:
                        pass
                if i > 0 or not shadow:
                    try:
                        comp.set_cast_shadow(False)
                    except Exception:
                        _sp(comp, 'cast_shadow', False)
                if swaps:
                    for slot_name, mi_name in swaps.items():
                        idx = slot_index(sm, slot_name)
                        mi = MI.get(mi_name)
                        if idx >= 0 and mi is not None:
                            try:
                                comp.set_material(idx, mi)
                            except Exception as e:
                                err_once('swap', 'set_material en %s falló: %s' % (label, e))
            actors.append(a)
            STATS['actors'] = STATS.get('actors', 0) + 1
        except Exception as e:
            err_once('spawn', 'No se pudo colocar %s: %s' % (label, e))
    return actors


def spawn_class(cls, label, loc, rot=None, folder=None):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    a = eas.spawn_actor_from_class(cls, V(loc), rot if rot is not None else R())
    if a is not None:
        _actor_setup(a, label, folder or FOLDER)
    return a


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
        unreal.EditorAssetLibrary.save_directory(ASSET_DIR, only_if_is_dirty=False, recursive=True)
        log('Mallas guardadas en %s' % ASSET_DIR)
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
# CICLO DE VIDA (sin estado entre corridas)
# =====================================================================================
def reset_state(seed):
    F.clear()
    CAPS.clear()
    PRISM_CFG.clear()
    _OPTS.clear()
    _TEMPLATES.clear()
    MI.clear()
    ORIGIN.clear()
    _ERR_COUNT.clear()
    STATS.clear()
    STATS.update({'ok': 0, 'fail': 0})
    del ASSETS_MADE[:]
    MIRROR['on'] = False
    MIRROR['W'] = 0.0
    RNG.seed(seed)


def shutdown():
    """Suelta TODO lo que el módulo tiene de Unreal: pool de mallas, plantillas, materiales, opciones."""
    for k in list(_TEMPLATES.keys()):
        _TEMPLATES[k] = None
    _TEMPLATES.clear()
    pool_close()
    _OPTS.clear()
    MI.clear()
    F.clear()
    PRISM_CFG.clear()
    ORIGIN.clear()
    trace_close()


RNG = random.Random(SEED)


# =====================================================================================
# HELPERS v2 (mapa)
# =====================================================================================
def merge_mb(dst, src, loc=(0.0, 0.0, 0.0), yaw=0.0):
    """Agrega todas las submallas de src a dst con traslación+yaw y transforma la colisión.
    Las cajas se transforman exactas si yaw es múltiplo de 90; si no, pasan como prismas convexos."""
    t = T(loc, R(yaw=yaw))
    for mat in src.order:
        append_into(dst.m(mat), src.subs[mat], t)
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))

    def rot(x, y):
        return (loc[0] + x * c - y * s, loc[1] + x * s + y * c)
    right = abs(round(yaw / 90.0) * 90.0 - yaw) < 1e-3
    for (x0, x1, y0, y1, z0, z1) in src.coll:
        pts = [rot(x0, y0), rot(x1, y0), rot(x1, y1), rot(x0, y1)]
        if right:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            dst.coll.append((min(xs), max(xs), min(ys), max(ys), z0 + loc[2], z1 + loc[2]))
        else:
            dst.ramps.append((pts, 'z', z0 + loc[2], z1 + loc[2]))
    for (pts, axis, a0, a1) in src.ramps:
        if axis == 'z':
            dst.ramps.append(([rot(p, q) for (p, q) in pts], 'z', a0 + loc[2], a1 + loc[2]))
        elif abs(yaw) < 1e-3:
            if axis == 'y':
                dst.ramps.append(([(p + loc[0], q + loc[2]) for (p, q) in pts], 'y', a0 + loc[1], a1 + loc[1]))
            else:
                dst.ramps.append(([(p + loc[1], q + loc[2]) for (p, q) in pts], 'x', a0 + loc[0], a1 + loc[0]))
        else:
            # rampa en otro eje con rotación: aproximación por su caja envolvente en z (rara vez se usa)
            warn_once('merge_ramp', 'merge_mb: rampa en eje %s con yaw %.0f aproximada' % (axis, yaw))
    src.release()


def warn_once(key, msg):
    if key in _ERR_COUNT:
        return
    _ERR_COUNT[key] = 1
    warn(msg)


def stairs_probe():
    """Calibra append_linear_stairs: eje de profundidad, sentido de subida y origen (fracciones)."""
    CAPS['stairs'] = None
    if not F.get('stairs') or not F.get('bbox'):
        warn('Calibración: sin append_linear_stairs (o sin bbox): escaleras con cajas')
        return
    m = top = None
    try:
        m = new_mesh()
        call('stairs', m, popts('MI_Hormigon'), T(), step_width=100.0, step_height=20.0, step_depth=30.0,
             num_steps=4, floating=False)
        bb = mesh_bbox(m)
        if bb is None:
            raise RuntimeError('bbox vacío')
        ext = [bb[1][i] - bb[0][i] for i in range(3)]
        if abs(ext[0] - 120.0) < 2.0 and abs(ext[1] - 100.0) < 2.0:
            ax = 0
        elif abs(ext[1] - 120.0) < 2.0 and abs(ext[0] - 100.0) < 2.0:
            ax = 1
        else:
            raise RuntimeError('medidas inesperadas %s' % (ext,))
        if abs(ext[2] - 80.0) > 2.0:
            raise RuntimeError('alto inesperado %s' % (ext,))
        sign = 1.0
        if F.get('boolean'):
            top = new_mesh()
            cx = 0.5 * (bb[0][0] + bb[1][0])
            cy = 0.5 * (bb[0][1] + bb[1][1])
            _box_raw(top, popts('MI_Hormigon'), T((cx, cy, bb[0][2] + 65.0)), 400.0, 400.0, 100.0, ORIGIN['base'])
            bo = unreal.GeometryScriptMeshBooleanOptions()
            _sp(bo, 'fill_holes', True)
            F['boolean'](m, T(), top, T(), unreal.GeometryScriptBooleanOperation.INTERSECTION, bo)
            bb2 = mesh_bbox(m)
            if bb2 is not None:
                sign = 1.0 if 0.5 * (bb2[0][ax] + bb2[1][ax]) > 0.5 * (bb[0][ax] + bb[1][ax]) else -1.0
        oth = 1 - ax
        CAPS['stairs'] = {'ax': ax, 'sign': sign, 'f_d0': bb[0][ax] / 120.0, 'f_d1': bb[1][ax] / 120.0,
                          'f_w0': bb[0][oth] / 100.0, 'f_w1': bb[1][oth] / 100.0, 'f_z0': bb[0][2] / 80.0}
        log('Calibración: escaleras OK %s' % CAPS['stairs'])
    except Exception as e:
        CAPS['stairs'] = None
        warn('Calibración: append_linear_stairs no usable (%s): escaleras con cajas' % e)
    finally:
        free_mesh(m)
        free_mesh(top)


def stairs_flight(mb, mat, base, up, width, n, h, d, collision=True):
    """Tramo de escalera recta. base = punto medio del borde del primer escalón (x, y, z);
    up = dirección horizontal de subida (unitaria). Colisión: una caja por escalón (si up es axial)."""
    ux, uy = up
    L = n * d
    cfg = CAPS.get('stairs')
    done = False
    if cfg:
        tmp = None
        try:
            tmp = new_mesh()
            call('stairs', tmp, popts(mat), T(), step_width=float(width), step_height=float(h), step_depth=float(d),
                 num_steps=int(n), floating=False)
            ax = cfg['ax']
            lo = (cfg['f_d0'] if cfg['sign'] > 0 else cfg['f_d1']) * L
            wc = 0.5 * (cfg['f_w0'] + cfg['f_w1']) * width
            z0 = cfg['f_z0'] * n * h
            c0 = [0.0, 0.0]
            c0[ax] = lo
            c0[1 - ax] = wc
            r0 = [0.0, 0.0]
            r0[ax] = cfg['sign']
            yaw = math.degrees(math.atan2(uy, ux) - math.atan2(r0[1], r0[0]))
            cs, sn = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            rc = (c0[0] * cs - c0[1] * sn, c0[0] * sn + c0[1] * cs)
            append_into(mb.m(mat), tmp, T((base[0] - rc[0], base[1] - rc[1], base[2] - z0), R(yaw=yaw)))
            done = True
        except Exception as e:
            err_once('stairs', 'append_linear_stairs falló (%s): escalones con cajas' % e)
            CAPS['stairs'] = None
        finally:
            free_mesh(tmp)
    px, py = -uy, ux
    for i in range(n):
        a0, a1 = i * d, (i + 1) * d
        ztop = base[2] + (i + 1) * h
        pts = []
        for (a, w) in ((a0, -0.5 * width), (a1, -0.5 * width), (a1, 0.5 * width), (a0, 0.5 * width)):
            pts.append((base[0] + ux * a + px * w, base[1] + uy * a + py * w))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if not done:
            box(mb, mat, min(xs), max(xs), min(ys), max(ys), base[2], ztop)
        if collision:
            if abs(ux) < 1e-6 or abs(uy) < 1e-6:
                mb.col(min(xs), max(xs), min(ys), max(ys), base[2], ztop)
            else:
                mb.ramps.append((pts, 'z', base[2], ztop))


def boolean_op(target, tool, op):
    bo = unreal.GeometryScriptMeshBooleanOptions()
    _sp(bo, 'fill_holes', True)
    _sp(bo, 'simplify_output', False)
    opv = getattr(unreal.GeometryScriptBooleanOperation, op)
    F['boolean'](target, T(), tool, T(), opv, bo)


def body_two_views(mb, mat, side_pts, y0, y1, front_pts, x0, x1, cut_cyls=()):
    """Volumen "a dos vistas": perfil lateral (x,z) extruido en y  ∩  perfil frontal (y,z) extruido en x,
    menos cilindros (pasaruedas). Si los booleanos no andan, queda el perfil lateral solo."""
    if F.get('boolean') and CAPS.get('boolean_ok', True) and CAPS.get('intersect_ok', True):
        a = b = None
        try:
            a = new_mesh()
            prism(_One(a), mat, side_pts, 'y', y0, y1)
            b = new_mesh()
            prism(_One(b), mat, front_pts, 'x', x0, x1)
            boolean_op(a, b, 'INTERSECTION')
            for (p0, p1, r) in cut_cyls:
                free_mesh(b)
                b = new_mesh()
                cyl(_One(b), mat, p0, p1, r, 16)
                boolean_op(a, b, 'SUBTRACT')
            if tri_count(a) == 0:
                raise RuntimeError('intersección vacía')
            append_into(mb.m(mat), a)
            return
        except Exception as e:
            err_once('intersect', 'Booleano de carrocería falló (%s): perfil lateral solo' % e)
            CAPS['intersect_ok'] = False
        finally:
            free_mesh(a)
            free_mesh(b)
    prism(mb, mat, side_pts, 'y', y0, y1)


def jitter_poly(rng, cx, cy, rx, ry, n=10, jit=15.0, rot=0.0):
    """Polígono irregular (bacheo, charco, mancha): n vértices sobre una elipse con ruido."""
    pts = []
    cr, sr = math.cos(rot), math.sin(rot)
    for i in range(n):
        a = 2.0 * math.pi * i / n + rng.uniform(-0.18, 0.18)
        x = rx * math.cos(a) + rng.uniform(-jit, jit)
        y = ry * math.sin(a) + rng.uniform(-jit, jit)
        pts.append((cx + x * cr - y * sr, cy + x * sr + y * cr))
    return pts


def scale_poly(pts, s, extra=0.0):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    out = []
    for (x, y) in pts:
        dx, dy = x - cx, y - cy
        L = math.hypot(dx, dy) or 1.0
        f = s + extra / L
        out.append((cx + dx * f, cy + dy * f))
    return out


def clip_poly(pts, nx, ny, c):
    """Recorta un polígono convexo/simple con el semiplano nx*x + ny*y >= c (Sutherland-Hodgman)."""
    out = []
    n = len(pts)
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]
        dp = nx * p[0] + ny * p[1] - c
        dq = nx * q[0] + ny * q[1] - c
        if dp >= 0:
            out.append(p)
        if (dp >= 0) != (dq >= 0):
            t = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def tanque_simple(mb, cx, cy, z0, r=50.0, h=110.0):
    """Tanque de agua barato (3 primitivas) para fondos y techos lejanos."""
    box(mb, 'MI_Hormigon', cx - r - 6.0, cx + r + 6.0, cy - r - 6.0, cy + r + 6.0, z0, z0 + 16.0)
    cyl(mb, M_PLASTICO, (cx, cy, z0 + 16.0), (cx, cy, z0 + 16.0 + h), r, 14)
    cone(mb, M_PLASTICO, (cx, cy, z0 + 16.0 + h), (cx, cy, z0 + 32.0 + h), r, r * 0.4, 14)
