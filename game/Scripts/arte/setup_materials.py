# Importa las texturas PBR de ArtSource y arma el material maestro M_Barrio_Surface (v2) y sus instancias MI_*
# (ver CONVENCIONES.md, sección v2).
# v4: + M_Barrio_Cartel / M_Barrio_Cartel_Mascara (UV0 de la malla sobre los atlas de texto de gen_textures.py) y sus
#     MI (placas de calle, comercios, comisaría, estación, salidas, afiches, pintadas, bandera); + MI_Ladrillo_Torre,
#     MI_Hormigon_Pilar. Ver CONVENCIONES.md, sección v4.
# Uso en el editor: py "<repo>/game/Scripts/arte/setup_materials.py"
#
# v2 (26/11), cambios respecto del pase v1:
#  - Maestro reutilizado (no se borra el asset: se vacían sus nodos), así las instancias y mallas no pierden el padre.
#  - Triplanar con salto dinámico de proyecciones sin peso (en caras alineadas a ejes = 1 proyección, no 3)
#    y muestreo con gradientes explícitos (SampleGrad) para poder ramificar sin artefactos de mip.
#  - Anti-tiling: segunda muestra rotada 37° a escala x2.73, mezclada por ruido de mundo con mezcla que conserva
#    la varianza (no lava el contraste). Parámetro AntiTile (0 = apagado, para texturas con patrón: ladrillo, tejas...).
#  - Normal: mezcla UDN en espacio de mundo sobre la normal de vértice (v1 reemplazaba la normal geométrica por el eje
#    de proyección: postes y troncos se veían facetados/planos). Normales en BC5 (TC_NORMALMAP), sólo se leen RG.
#  - Color: Saturation, variación macro de valor 0.72..1.28 y de tono (±4 % R/B, HueVariation), suciedad de base con
#    altura modulada 0.6x..2x, chorreaduras bajo antepechos/dinteles/cornisas, verdín en zócalos y cavidades,
#    suciedad de contacto con DistanceToNearestSurface (Mesh Distance Fields), cabeza pulida para rieles.
#  - Ruido: hash entero pcg3d (sin sin(): estable en coordenadas grandes y entre GPUs), 3 canales por evaluación.
#  - Emisivo opcional (color, intensidad en nits, destello tipo baliza), Specular, RoughnessAdd, MetallicAdd.
#
# COSTO ESTIMADO (por píxel, pase base):
#   Muestras de textura, cara alineada a un eje (el 90 % de un barrio de cajas):
#     AntiTile = 0: BC 1 + ORM 1 + N 1 = 3   (+ campo de distancia global ~2 lecturas si UseContactGrime)
#     AntiTile > 0: BC 2 + ORM 2 + N 2 = 6   (+ 2 lecturas del mip 1x1 para la media, siempre en caché)
#   Peor caso (esquinas biseladas / superficies curvas que mezclan 3 proyecciones): 9 / 18 (+2).
#   v1 hacía siempre 9 muestras: el caso típico de v2 es más barato aun con anti-tiling.
#   ALU: ruido de mundo 2 octavas (16 pcg3d) ~300 instr; chorreaduras (sólo paredes, rama) +~250; verdín +~130;
#   resto ~150. Total ~450-800 instrucciones según la superficie. Para mallas lejanas o muy repetidas (autos,
#   cables, vidrios, emisivos) las instancias apagan UseContactGrime (permutación estática sin campo de distancia)
#   y ponen StreakAmount/MossAmount en 0, que corta las ramas dinámicas.

import os
import unreal

def log(m): unreal.log(f"[ARTE] {m}")
def warn(m): unreal.log_warning(f"[ARTE] {m}")
def err(m): unreal.log_error(f"[ARTE] {m}")

PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SRC_DIR = os.path.join(PROJECT_DIR, "ArtSource", "Textures")
TEX_ROOT = "/Game/Barrio/Art/Textures"
MAT_DIR = "/Game/Barrio/Art/Materials"
MASTER = f"{MAT_DIR}/M_Barrio_Surface"

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

SETS = {  # set: tamaño real en cm que cubre la textura (gen_textures.py TILE_CM)
    "Revoque": 200, "Ladrillo": 240, "Baldosa": 80, "Asfalto": 400, "Hormigon": 150,
    "Chapa": 100, "Madera": 120, "Tejas": 120, "MetalPintado": 100, "PiedraLaja": 150,
    # v2
    "Corteza": 120, "Pasto": 200, "Tierra": 200, "Balasto": 120, "Riel": 80, "Follaje": 150,
}

# Color medio lineal de cada _BC (medido sobre los PNG). Sirve para que las instancias pidan el albedo FINAL
# ("color") y el script calcule el Tint = objetivo / media.
BASE_MEAN = {
    "Revoque": (0.573, 0.560, 0.536), "Ladrillo": (0.393, 0.147, 0.093), "Baldosa": (0.313, 0.296, 0.247),
    "Asfalto": (0.107, 0.108, 0.116), "Hormigon": (0.400, 0.390, 0.362), "Chapa": (0.368, 0.356, 0.358),
    "Madera": (0.318, 0.149, 0.068), "Tejas": (0.328, 0.081, 0.039), "MetalPintado": (0.592, 0.592, 0.585),
    "PiedraLaja": (0.355, 0.283, 0.178), "Corteza": (0.117, 0.089, 0.063), "Pasto": (0.097, 0.117, 0.034),
    "Tierra": (0.180, 0.134, 0.090), "Balasto": (0.166, 0.140, 0.131), "Riel": (0.100, 0.047, 0.029),
    "Follaje": (0.062, 0.099, 0.023),
}

# ---------------------------------------------------------------- 1) Texturas
def import_textures():
    tasks = []
    for s in SETS:
        for suf in ("BC", "N", "ORM"):
            f = os.path.join(SRC_DIR, s, f"T_{s}_{suf}.png")
            if not os.path.exists(f):
                err(f"Falta {f}")
                continue
            t = unreal.AssetImportTask()
            t.set_editor_property("filename", f)
            t.set_editor_property("destination_path", f"{TEX_ROOT}/{s}")
            t.set_editor_property("automated", True)
            t.set_editor_property("replace_existing", True)
            t.set_editor_property("save", False)
            tasks.append(t)
    tools.import_asset_tasks(tasks)
    for s in SETS:
        for suf in ("BC", "N", "ORM"):
            p = f"{TEX_ROOT}/{s}/T_{s}_{suf}"
            tex = eal.load_asset(p)
            if not tex:
                continue
            if suf == "BC":
                tex.set_editor_property("srgb", True)
                tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_DEFAULT)
            elif suf == "N":
                # BC5: dos canales de 8 bits reales; el nodo Custom lee .rg y reconstruye con la normal de mundo.
                # El PNG ya está en convención DirectX: no invertir verde.
                tex.set_editor_property("srgb", False)
                tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
                tex.set_editor_property("flip_green_channel", False)
                try:
                    tex.set_editor_property("lod_group", unreal.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
                except Exception:  # noqa: BLE001
                    pass
            else:
                tex.set_editor_property("srgb", False)
                tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
            eal.save_asset(p, only_if_is_dirty=False)
    log("Texturas importadas")

# ---------------------------------------------------------------- 2) HLSL de los nodos Custom
# Ruido de valor 3D con hash entero pcg3d (Jarzynski & Olano 2020): 3 canales independientes por evaluación.
# Se declara como struct local con métodos (truco estándar para "funciones" dentro de un nodo Custom).
HLSL_NOISE_LIB = r"""
struct FBarrioRuido
{
    float3 H(int3 c)
    {
        uint3 v = uint3(c) * 1664525u + 1013904223u;
        v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
        v ^= v >> 16u;
        v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
        return float3(v >> 8u) * (1.0 / 16777216.0);
    }
    float3 VN(float3 p)
    {
        float3 i = floor(p);
        float3 f = p - i;
        float3 u = f * f * (3.0 - 2.0 * f);
        int3 c = int3(i);
        float3 a = H(c);
        float3 b = H(c + int3(1, 0, 0));
        float3 d = H(c + int3(0, 1, 0));
        float3 e = H(c + int3(1, 1, 0));
        float3 g = H(c + int3(0, 0, 1));
        float3 h = H(c + int3(1, 0, 1));
        float3 k = H(c + int3(0, 1, 1));
        float3 l = H(c + int3(1, 1, 1));
        return lerp(lerp(lerp(a, b, u.x), lerp(d, e, u.x), u.y),
                    lerp(lerp(g, h, u.x), lerp(k, l, u.x), u.y), u.z);
    }
};
FBarrioRuido R;
"""

# Ruido de mundo compartido por todos los efectos (se calcula una vez por píxel).
# x = variación macro de valor (8 m + 2,5 m), y = tono (8 m), z = máscara de anti-tiling (2,5 m), w = altura de suciedad.
HLSL_WORLD_NOISE = HLSL_NOISE_LIB + r"""
float3 a = R.VN(WP / 800.0);
float3 b = R.VN(WP / 250.0 + 17.31);
float n = saturate((a.x * 0.65 + b.x * 0.35 - 0.5) * 2.4 + 0.5);
float hue = saturate((a.y - 0.5) * 2.2 + 0.5);
float m = saturate((b.z - 0.5) * 2.2 + 0.5);
float g = saturate((lerp(a.z, b.y, 0.6) - 0.5) * 2.2 + 0.5);
return float4(n, hue, m, g);
"""

# Proyecciones: (nombre, uv en función de WP)
_PROJ = (("X", "float2(WP.y, -WP.z)", "w.x"), ("Y", "float2(WP.x, -WP.z)", "w.y"), ("Z", "float2(WP.x, WP.y)", "w.z"))

_TRI_HEAD = r"""
// Pesos triplanares afilados; se descartan los < 3 % para poder saltear la muestra entera.
float3 an = abs(N);
float3 w = an * an; w = w * w * w;
w /= (w.x + w.y + w.z + 1e-6);
w = saturate(w - 0.03);
w /= (w.x + w.y + w.z + 1e-6);
float iT = 1.0 / max(Tile, 1.0);
// Anti-tiling: segunda muestra rotada 37 grados y a escala x2.73, mezclada por ruido de mundo.
float bt = AT * smoothstep(0.3, 0.7, Mask);
const float cr = 0.79864;
const float sr = 0.60182;
const float kr = 0.36630;
"""


def _rot(e):
    return f"(float2(cr * ({e}).x - sr * ({e}).y, sr * ({e}).x + cr * ({e}).y) * kr)"


def _hlsl_triplanar_color():
    code = [_TRI_HEAD, "float4 acc = 0.0;"]
    for nm, uv, wv in _PROJ:
        code.append(f"""
float2 u{nm} = {uv} * iT;
float2 dx{nm} = ddx(u{nm});
float2 dy{nm} = ddy(u{nm});
[branch] if ({wv} > 0.0)
{{
    float4 s = Texture2DSampleGrad(Tex, TexSampler, u{nm}, dx{nm}, dy{nm});
    [branch] if (bt > 0.002)
    {{
        float4 s2 = Texture2DSampleGrad(Tex, TexSampler, {_rot('u' + nm)} + float2(0.37, 0.71), {_rot('dx' + nm)}, {_rot('dy' + nm)});
        s = lerp(s, s2, bt);
    }}
    acc += s * {wv};
}}""")
    code.append(r"""
// Mezcla que conserva la varianza (Heitz-Neyret): sin esto la zona mezclada pierde contraste y se nota el parche.
[branch] if (bt > 0.002)
{
    float3 mu = Texture2DSampleLevel(Tex, TexSampler, float2(0.5, 0.5), 14.0).rgb;
    acc.rgb = mu + (acc.rgb - mu) * rsqrt(bt * bt + (1.0 - bt) * (1.0 - bt));
}
return saturate(acc.rgb);
""")
    return "\n".join(code)


def _hlsl_triplanar_normal():
    code = [_TRI_HEAD, "float3 t = 0.0;  // perturbación en mundo (mezcla UDN)",
            "float vf = rsqrt(bt * bt + (1.0 - bt) * (1.0 - bt));"]
    # Normales DirectX: verde = -dh/dv. u/v de cada proyección en ejes de mundo:
    #  X: u=+Y v=-Z | Y: u=+X v=-Z | Z: u=+X v=+Y
    to_world = {"X": "float3(0.0, s.x, -s.y)", "Y": "float3(s.x, 0.0, -s.y)", "Z": "float3(s.x, s.y, 0.0)"}
    for nm, uv, wv in _PROJ:
        code.append(f"""
float2 u{nm} = {uv} * iT;
float2 dx{nm} = ddx(u{nm});
float2 dy{nm} = ddy(u{nm});
[branch] if ({wv} > 0.0)
{{
    float2 s = Texture2DSampleGrad(Tex, TexSampler, u{nm}, dx{nm}, dy{nm}).rg * 2.0 - 1.0;
    [branch] if (bt > 0.002)
    {{
        float2 q = Texture2DSampleGrad(Tex, TexSampler, {_rot('u' + nm)} + float2(0.37, 0.71), {_rot('dx' + nm)}, {_rot('dy' + nm)}).rg * 2.0 - 1.0;
        q = float2(cr * q.x + sr * q.y, -sr * q.x + cr * q.y);   // R^T: de vuelta al marco sin rotar
        s = lerp(s, q, bt) * vf;
    }}
    t += {to_world[nm]} * {wv};
}}""")
    code.append("return normalize(N + t * Strength);")
    return "\n".join(code)


HLSL_SAMPLE = _hlsl_triplanar_color()
HLSL_NORMAL = _hlsl_triplanar_normal()

HLSL_CONTACT = r"""
// Contacto: distancia a la superficie más cercana medida a ContactRadius de la cara, a lo largo de la normal.
// En una pared libre la distancia es ~R (0); en el encuentro muro-piso, esquinas y vanos baja (sube la suciedad).
float c = saturate(1.0 - DF / max(Rad, 1.0));
return c * c * Amt;
"""

HLSL_COLOR = HLSL_NOISE_LIB + r"""
float3 c = Base * Tint.rgb;   // Tint llega como float4 (VectorParameter)
// 1) Saturación hacia la luminancia (Rec. 709 lineal)
float L = dot(c, float3(0.2126, 0.7152, 0.0722));
c = max(lerp(L.xxx, c, Sat), 0.0);
// 2) Variación macro de valor y de tono (rojo contra azul, ±4 % por unidad de HueVar)
float n = Nz.x;
c *= lerp(1.0, 0.72 + 0.56 * n, Macro);
float hv = (Nz.y * 2.0 - 1.0) * 0.04 * HueVar;
c *= float3(1.0 + hv, 1.0, 1.0 - hv);
float wall = 1.0 - saturate(abs(N.z) * 1.5);
float flo = saturate(N.z * 2.0 - 1.0);
float z = WP.z - GroundZ;
float dirt = 0.0;
// 3) Humedad y tierra en la base de los muros, con altura variable 0.6x..2x
float Hg = max(GrimeH, 1.0) * lerp(0.6, 2.0, smoothstep(0.15, 0.85, Nz.w));
float g = saturate(1.0 - z / Hg);
g = saturate(g * g * (0.6 + 0.8 * n) * Grime * wall);
c = lerp(c, c * float3(0.48, 0.44, 0.38), g);
dirt += g;
// 4) Chorreaduras verticales: columnas de ~30 cm, alargadas 4 m, más fuertes bajo antepechos (~1 m),
//    dinteles/cornisa de planta baja (~3 m) y cornisa de planta alta (~6,2 m)
[branch] if (Streak * wall > 0.002)
{
    float3 s1 = R.VN(float3(WP.x / 30.0, WP.y / 30.0, WP.z / 400.0));
    float3 s2 = R.VN(float3(WP.x / 9.0, WP.y / 9.0, WP.z / 120.0) + 5.7);
    float col = smoothstep(0.5, 0.78, s1.x * 0.75 + s2.x * 0.25);
    float3 Hs = float3(100.0, 300.0, 620.0);
    float3 Ls = float3(80.0, 170.0, 240.0);
    float3 ts = (Hs - z) / Ls;
    float3 pr = saturate(ts * 6.0) * exp(-max(ts, 0.0));
    float prof = 0.3 + 0.7 * max(max(pr.x, pr.y), pr.z);
    float st = saturate(col * prof * Streak * wall * (0.7 + 0.6 * s1.y));
    c = lerp(c, c * float3(0.6, 0.58, 0.55), st);
    dirt += st * 0.5;
}
// 5) Suciedad de contacto (ya escalada por ContactGrime)
float ct = saturate(Contact);
c = lerp(c, c * float3(0.55, 0.52, 0.48), ct);
dirt += ct * 0.6;
// 6) Verdín: franja baja de los muros (~35 cm variable), cavidades (AO de la textura) y piso junto a los muros
[branch] if (Moss > 0.002)
{
    float3 mv = R.VN(WP / 40.0 + 3.1);
    float cav = saturate((1.0 - ORM.r) * 2.5);
    float zone = wall * pow(saturate(1.0 - z / (35.0 * (0.5 + Nz.w))), 1.5);
    float pat = smoothstep(0.3, 0.65, mv.x);
    float m = saturate((zone * (0.35 + 0.65 * cav) + flo * ct * (0.4 + 0.6 * cav)) * pat * Moss);
    float3 mc = lerp(float3(0.045, 0.055, 0.022), float3(0.085, 0.095, 0.038), mv.y);
    c = lerp(c, mc, m);
    dirt += m;
}
// 7) Cabeza pulida (rieles): cara superior a acero brillante
float pol = smoothstep(0.85, 0.97, N.z) * PolishTop;
c = lerp(c, float3(0.40, 0.40, 0.41) * (0.9 + 0.2 * n), pol);
return float4(saturate(c), saturate(dirt) * (1.0 - pol));
"""

HLSL_ORM = r"""
float pol = smoothstep(0.85, 0.97, N.z) * PolishTop;
float ao = ORM.r * (1.0 - 0.5 * saturate(Contact));
float r = saturate(ORM.g * RMul + RAdd + Dirt * 0.15);
float m = saturate(ORM.b * MMul + MAdd);
r = lerp(r, 0.22, pol);
m = lerp(m, 1.0, pol);
return float3(ao, r, m);
"""

HLSL_EMISSIVE = r"""
// Emisivo en nits (cd/m2) con exposición física. Hz > 0: destello doble de baliza (dos pulsos por ciclo).
float k = 1.0;
[branch] if (Hz > 0.0)
{
    float ph = frac(Tm * Hz + Phase);
    k = smoothstep(0.0, 0.02, ph) * (1.0 - smoothstep(0.12, 0.16, ph))
      + smoothstep(0.24, 0.26, ph) * (1.0 - smoothstep(0.36, 0.40, ph));
    k = 0.04 + 0.96 * k;
}
return Col.rgb * Str * k;
"""

# ---------------------------------------------------------------- 3) Construcción del grafo
F1T = unreal.CustomMaterialOutputType.CMOT_FLOAT1
F3T = unreal.CustomMaterialOutputType.CMOT_FLOAT3
F4T = unreal.CustomMaterialOutputType.CMOT_FLOAT4


def new_expr(mat, cls, x, y):
    return mel.create_material_expression(mat, cls, x, y)


def connect(a, a_out, b, b_in):
    if not mel.connect_material_expressions(a, a_out, b, b_in):
        err(f"No conecté {a.get_name()}[{a_out}] -> {b.get_name()}[{b_in}]")
        return False
    return True


def scalar_param(mat, name, default, x, y, group="Superficie"):
    e = new_expr(mat, unreal.MaterialExpressionScalarParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", float(default))
    e.set_editor_property("group", group)
    return e


def vector_param(mat, name, default, x, y, group="Color"):
    e = new_expr(mat, unreal.MaterialExpressionVectorParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", default)
    e.set_editor_property("group", group)
    return e


def tex_param(mat, name, x, y, sampler, default_tex):
    e = new_expr(mat, unreal.MaterialExpressionTextureObjectParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("group", "Texturas")
    if default_tex:
        e.set_editor_property("texture", default_tex)
    e.set_editor_property("sampler_type", sampler)
    return e


def custom(mat, code, inputs, out_type, x, y, desc):
    e = new_expr(mat, unreal.MaterialExpressionCustom, x, y)
    e.set_editor_property("code", code)
    e.set_editor_property("output_type", out_type)
    e.set_editor_property("description", desc)
    ins = []
    for n in inputs:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        ins.append(ci)
    e.set_editor_property("inputs", ins)
    return e


def mask(mat, src, ch, x, y):
    m = new_expr(mat, unreal.MaterialExpressionComponentMask, x, y)
    for c in "rgba":
        m.set_editor_property(c, c == ch)
    connect(src, "", m, "")
    return m


def get_master():
    """Reutiliza el asset si existe (vaciando el grafo) para no romper las referencias de instancias y mallas."""
    eal.make_directory(MAT_DIR)
    mat = eal.load_asset(MASTER) if eal.does_asset_exist(MASTER) else None
    if isinstance(mat, unreal.Material):
        mel.delete_all_material_expressions(mat)
        log("M_Barrio_Surface existente: grafo vaciado y reconstruido")
    else:
        if mat is not None:
            eal.delete_asset(MASTER)
        mat = tools.create_asset("M_Barrio_Surface", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    return mat


def build_master():
    mat = get_master()
    for prop, val in (("blend_mode", unreal.BlendMode.BLEND_OPAQUE),
                      ("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT),
                      ("tangent_space_normal", False),
                      ("two_sided", False),
                      # usos: evita recompilaciones/"needs resave" al asignarlo a Nanite, ISM/HISM y splines (cables)
                      ("used_with_nanite", True),
                      ("used_with_instanced_static_meshes", True),
                      ("used_with_spline_meshes", True)):
        try:
            mat.set_editor_property(prop, val)
        except Exception as e:  # noqa: BLE001
            warn(f"Material: no pude fijar {prop}: {e}")

    P = unreal.MaterialSamplerType
    dflt = {suf: eal.load_asset(f"{TEX_ROOT}/Revoque/T_Revoque_{suf}") for suf in ("BC", "N", "ORM")}

    # --- entradas comunes
    wp = new_expr(mat, unreal.MaterialExpressionWorldPosition, -2600, 0)
    nrm = new_expr(mat, unreal.MaterialExpressionVertexNormalWS, -2600, 150)
    tile = scalar_param(mat, "TileSizeCM", 200.0, -2600, 300, "Texturas")
    at = scalar_param(mat, "AntiTile", 0.0, -2600, 380, "Texturas")
    bc_t = tex_param(mat, "BaseColorTex", -2600, -500, P.SAMPLERTYPE_COLOR, dflt["BC"])
    n_t = tex_param(mat, "NormalTex", -2600, 550, P.SAMPLERTYPE_NORMAL, dflt["N"])
    orm_t = tex_param(mat, "ORMTex", -2600, 850, P.SAMPLERTYPE_MASKS, dflt["ORM"])

    # --- ruido de mundo compartido
    wn = custom(mat, HLSL_WORLD_NOISE, ["WP"], F4T, -2200, 150, "Ruido de mundo (macro, tono, antitile, suciedad)")
    connect(wp, "", wn, "WP")
    wmask = mask(mat, wn, "b", -1950, 250)

    # --- muestras triplanares
    s_bc = custom(mat, HLSL_SAMPLE, ["Tex", "WP", "N", "Tile", "Mask", "AT"], F3T, -1600, -500, "Triplanar BaseColor + antitile")
    s_orm = custom(mat, HLSL_SAMPLE, ["Tex", "WP", "N", "Tile", "Mask", "AT"], F3T, -1600, 850, "Triplanar ORM + antitile")
    s_n = custom(mat, HLSL_NORMAL, ["Tex", "WP", "N", "Tile", "Mask", "AT", "Strength"], F3T, -1600, 500, "Triplanar normal UDN (mundo)")
    for node, tex in ((s_bc, bc_t), (s_orm, orm_t), (s_n, n_t)):
        connect(tex, "", node, "Tex")
        connect(wp, "", node, "WP")
        connect(nrm, "", node, "N")
        connect(tile, "", node, "Tile")
        connect(wmask, "", node, "Mask")
        connect(at, "", node, "AT")
    connect(scalar_param(mat, "NormalStrength", 1.0, -1900, 650), "", s_n, "Strength")

    # --- suciedad de contacto (campo de distancia global), detrás de un switch estático
    crad = scalar_param(mat, "ContactRadiusCM", 40.0, -2600, 1250, "Intemperie")
    off = new_expr(mat, unreal.MaterialExpressionMultiply, -2350, 1200)
    connect(nrm, "", off, "A")
    connect(crad, "", off, "B")
    pos = new_expr(mat, unreal.MaterialExpressionAdd, -2200, 1150)
    connect(wp, "", pos, "A")
    connect(off, "", pos, "B")
    dfn = new_expr(mat, unreal.MaterialExpressionDistanceToNearestSurface, -2050, 1150)
    if not mel.connect_material_expressions(pos, "", dfn, "Position"):
        connect(pos, "", dfn, "")
    far = new_expr(mat, unreal.MaterialExpressionConstant, -2050, 1260)
    far.set_editor_property("r", 100000.0)
    sw = new_expr(mat, unreal.MaterialExpressionStaticSwitchParameter, -1850, 1180)
    sw.set_editor_property("parameter_name", "UseContactGrime")
    sw.set_editor_property("default_value", True)
    sw.set_editor_property("group", "Intemperie")
    if not mel.connect_material_expressions(dfn, "", sw, "True"):
        connect(dfn, "", sw, "A")
    if not mel.connect_material_expressions(far, "", sw, "False"):
        connect(far, "", sw, "B")
    cont = custom(mat, HLSL_CONTACT, ["DF", "Rad", "Amt"], F1T, -1600, 1180, "Suciedad de contacto")
    connect(sw, "", cont, "DF")
    connect(crad, "", cont, "Rad")
    connect(scalar_param(mat, "ContactGrime", 0.5, -1850, 1320, "Intemperie"), "", cont, "Amt")

    # --- color
    tint = vector_param(mat, "Tint", unreal.LinearColor(1, 1, 1, 1), -1600, -750)
    polish = scalar_param(mat, "PolishTop", 0.0, -1300, 1400, "Superficie")
    col = custom(mat, HLSL_COLOR,
                 ["Base", "ORM", "Tint", "WP", "N", "Nz", "Sat", "Macro", "HueVar", "Grime", "GrimeH", "GroundZ",
                  "Streak", "Moss", "Contact", "PolishTop"],
                 F4T, -1000, -400, "Color: saturación, macro, tono, suciedad, chorreaduras, contacto, verdín")
    connect(s_bc, "", col, "Base")
    connect(s_orm, "", col, "ORM")
    connect(tint, "", col, "Tint")
    connect(wp, "", col, "WP")
    connect(nrm, "", col, "N")
    connect(wn, "", col, "Nz")
    params = (("Sat", "Saturation", 1.0, "Color"), ("Macro", "MacroVariation", 0.5, "Color"),
              ("HueVar", "HueVariation", 1.0, "Color"), ("Grime", "GrimeAmount", 0.6, "Intemperie"),
              ("GrimeH", "GrimeHeightCM", 60.0, "Intemperie"), ("GroundZ", "GroundZ", 0.0, "Intemperie"),
              ("Streak", "StreakAmount", 0.3, "Intemperie"), ("Moss", "MossAmount", 0.1, "Intemperie"))
    for i, (pin, pname, dv, grp) in enumerate(params):
        connect(scalar_param(mat, pname, dv, -1300, -300 + 70 * i, grp), "", col, pin)
    connect(cont, "", col, "Contact")
    connect(polish, "", col, "PolishTop")
    col_rgb = mask(mat, col, "r", -650, -450)
    col_rgb.set_editor_property("g", True)
    col_rgb.set_editor_property("b", True)
    col_dirt = mask(mat, col, "a", -650, -330)

    # --- AO / rugosidad / metálico
    ormf = custom(mat, HLSL_ORM, ["ORM", "Dirt", "Contact", "N", "RMul", "RAdd", "MMul", "MAdd", "PolishTop"],
                  F3T, -650, 850, "ORM final")
    connect(s_orm, "", ormf, "ORM")
    connect(col_dirt, "", ormf, "Dirt")
    connect(cont, "", ormf, "Contact")
    connect(nrm, "", ormf, "N")
    connect(polish, "", ormf, "PolishTop")
    for i, (pin, pname, dv) in enumerate((("RMul", "RoughnessMult", 1.0), ("RAdd", "RoughnessAdd", 0.0),
                                          ("MMul", "MetallicMult", 1.0), ("MAdd", "MetallicAdd", 0.0))):
        connect(scalar_param(mat, pname, dv, -950, 950 + 70 * i), "", ormf, pin)
    m_ao = mask(mat, ormf, "r", -350, 800)
    m_r = mask(mat, ormf, "g", -350, 900)
    m_m = mask(mat, ormf, "b", -350, 1000)

    # --- emisivo
    tm = new_expr(mat, unreal.MaterialExpressionTime, -950, 1350)
    emi = custom(mat, HLSL_EMISSIVE, ["Col", "Str", "Hz", "Phase", "Tm"], F3T, -650, 1300, "Emisivo (nits) + baliza")
    connect(vector_param(mat, "EmissiveColor", unreal.LinearColor(1, 1, 1, 1), -950, 1200, "Emisivo"), "", emi, "Col")
    connect(scalar_param(mat, "EmissiveStrength", 0.0, -950, 1420, "Emisivo"), "", emi, "Str")
    connect(scalar_param(mat, "EmissivePulseHz", 0.0, -950, 1490, "Emisivo"), "", emi, "Hz")
    connect(scalar_param(mat, "EmissivePhase", 0.0, -950, 1560, "Emisivo"), "", emi, "Phase")
    connect(tm, "", emi, "Tm")

    spec = scalar_param(mat, "Specular", 0.5, -350, 1150)

    MP = unreal.MaterialProperty
    for node, prop in ((col_rgb, MP.MP_BASE_COLOR), (s_n, MP.MP_NORMAL), (m_r, MP.MP_ROUGHNESS),
                       (m_m, MP.MP_METALLIC), (m_ao, MP.MP_AMBIENT_OCCLUSION), (emi, MP.MP_EMISSIVE_COLOR),
                       (spec, MP.MP_SPECULAR)):
        if not mel.connect_material_property(node, "", prop):
            err(f"No conecté {node.get_name()} -> {prop}")

    mel.recompile_material(mat)
    eal.save_asset(MASTER, only_if_is_dirty=False)
    log("Material maestro M_Barrio_Surface v2 listo")
    return mat

# ---------------------------------------------------------------- 4) Instancias
def srgb_lin(hexcol):
    h = hexcol.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def lc(r, g, b):
    return unreal.LinearColor(float(r), float(g), float(b), 1.0)


def tint_for(set_name, spec):
    """spec: ('color', '#hex') = albedo final buscado (tint = objetivo/media del set), ('tint', (r,g,b)) = multiplicador
    directo, None = blanco."""
    if spec is None:
        return lc(1, 1, 1)
    kind, v = spec
    if kind == "tint":
        return lc(*v)
    tgt = srgb_lin(v)
    mean = BASE_MEAN[set_name]
    return lc(*[min(t / max(m, 1e-3), 4.0) for t, m in zip(tgt, mean)])


# Valores por defecto que se escriben explícitos en TODAS las instancias (así cada MI es autodescriptiva
# y re-correr el script no deja overrides viejos).
COMMON = {
    "NormalStrength": 1.0, "RoughnessMult": 1.0, "RoughnessAdd": 0.0, "MetallicMult": 1.0, "MetallicAdd": 0.0,
    "Specular": 0.5, "Saturation": 1.0, "MacroVariation": 0.5, "HueVariation": 1.0, "AntiTile": 0.0,
    "GrimeAmount": 0.5, "GrimeHeightCM": 60.0, "GroundZ": 0.0, "StreakAmount": 0.3, "MossAmount": 0.1,
    "ContactGrime": 0.5, "ContactRadiusCM": 40.0, "PolishTop": 0.0,
    "EmissiveStrength": 0.0, "EmissivePulseHz": 0.0, "EmissivePhase": 0.0,
}
# Perfiles reutilizables
LIMPIO = {"GrimeAmount": 0.0, "StreakAmount": 0.0, "MossAmount": 0.0, "ContactGrime": 0.0, "UseContactGrime": False}
PINTURA_AUTO = {"RoughnessMult": 0.72, "NormalStrength": 0.35, "MacroVariation": 0.18, "HueVariation": 0.3,
                "AntiTile": 0.3, "GrimeAmount": 0.45, "GrimeHeightCM": 45.0, "StreakAmount": 0.12, "MossAmount": 0.0,
                "ContactGrime": 0.35}
REVOQUE = {"NormalStrength": 0.5, "AntiTile": 0.55, "MacroVariation": 0.55, "HueVariation": 0.8,
           "GrimeAmount": 0.7, "StreakAmount": 0.75, "MossAmount": 0.15, "ContactGrime": 0.6}
CARTEL = {"RoughnessMult": 1.0, "NormalStrength": 0.5, "MacroVariation": 0.2, "HueVariation": 0.3, "AntiTile": 0.3,
          "GrimeAmount": 0.15, "GrimeHeightCM": 40.0, "StreakAmount": 0.3, "MossAmount": 0.0, "UseContactGrime": False}


def merge(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out


# nombre: (set, color/tint, overrides)   — los colores son albedos finales (sRGB) salvo ('tint', ...)
INSTANCES = {
    # ---------------- v1 (nombres fijos que usa la fachada)
    "MI_Revoque_Blanco":    ("Revoque", ("color", "#D3CDBF"), merge(REVOQUE, {"StreakAmount": 0.85, "GrimeAmount": 0.75})),
    "MI_Revoque_Gris":      ("Revoque", ("color", "#9C9A93"), merge(REVOQUE, {"StreakAmount": 0.55, "GrimeAmount": 0.6})),
    "MI_Revoque_Rosa":      ("Revoque", ("color", "#C6A396"), REVOQUE),
    "MI_Revoque_VerdeAgua": ("Revoque", ("color", "#A0B8AB"), REVOQUE),
    "MI_Revoque_Amarillo":  ("Revoque", ("color", "#D2BE8E"), REVOQUE),
    "MI_Ladrillo":          ("Ladrillo", ("tint", (1.0, 0.97, 0.9)),
                             {"Saturation": 0.7, "TileSizeCM": 264.0, "MacroVariation": 0.6, "HueVariation": 1.0,
                              "GrimeAmount": 0.5, "StreakAmount": 0.45, "MossAmount": 0.12, "ContactGrime": 0.5}),
    "MI_Baldosa":           ("Baldosa", None, {"Saturation": 0.9, "GrimeAmount": 0.0, "MacroVariation": 0.7,
                                                "HueVariation": 0.6, "MossAmount": 0.25, "ContactGrime": 0.55}),
    "MI_Asfalto":           ("Asfalto", None, {"GrimeAmount": 0.0, "MacroVariation": 0.8, "HueVariation": 0.4,
                                                "AntiTile": 0.5, "MossAmount": 0.05, "ContactGrime": 0.35,
                                                "StreakAmount": 0.0}),
    "MI_Hormigon":          ("Hormigon", None, {"AntiTile": 0.5, "MacroVariation": 0.6, "HueVariation": 0.6,
                                                 "GrimeAmount": 0.45, "StreakAmount": 0.5, "MossAmount": 0.2,
                                                 "ContactGrime": 0.55}),
    "MI_Chapa_Gris":        ("Chapa", ("tint", (1.0, 1.0, 1.02)), {"Saturation": 0.8, "GrimeAmount": 0.4,
                                                                    "StreakAmount": 0.3, "MossAmount": 0.05,
                                                                    "MacroVariation": 0.45}),
    "MI_Chapa_Verde":       ("Chapa", ("color", "#566F5B"), {"MetallicMult": 0.0, "RoughnessMult": 1.15,
                                                             "Saturation": 0.85, "GrimeAmount": 0.4,
                                                             "StreakAmount": 0.35, "MacroVariation": 0.45}),
    "MI_Madera":            ("Madera", ("tint", (0.85, 0.78, 0.72)), {"Saturation": 0.6, "GrimeAmount": 0.35,
                                                                       "GrimeHeightCM": 45.0, "StreakAmount": 0.25,
                                                                       "MacroVariation": 0.45, "HueVariation": 0.7,
                                                                       "MossAmount": 0.05}),
    "MI_Tejas":             ("Tejas", ("tint", (1.0, 0.97, 0.92)), {"Saturation": 0.65, "NormalStrength": 0.75,
                                                                     "GrimeAmount": 0.0, "StreakAmount": 0.0,
                                                                     "MossAmount": 0.0, "MacroVariation": 0.6,
                                                                     "HueVariation": 1.0, "ContactGrime": 0.3}),
    "MI_Metal_Negro":       ("MetalPintado", ("color", "#2B2B2B"), {"RoughnessMult": 1.1, "GrimeAmount": 0.25,
                                                                    "StreakAmount": 0.15, "MacroVariation": 0.3,
                                                                    "MossAmount": 0.0, "AntiTile": 0.3}),
    "MI_Metal_Verde":       ("MetalPintado", ("color", "#34553F"), {"RoughnessMult": 1.1, "GrimeAmount": 0.25,
                                                                    "StreakAmount": 0.15, "MacroVariation": 0.3,
                                                                    "MossAmount": 0.0, "AntiTile": 0.3}),
    "MI_PiedraLaja":        ("PiedraLaja", None, {"Saturation": 0.7, "GrimeAmount": 0.45, "StreakAmount": 0.35,
                                                   "MossAmount": 0.2, "MacroVariation": 0.5}),
    "MI_Vidrio":            ("MetalPintado", ("color", "#1A2023"),
                             merge(LIMPIO, {"RoughnessMult": 0.08, "NormalStrength": 0.05, "MacroVariation": 0.15,
                                            "HueVariation": 0.0, "GrimeAmount": 0.25, "GrimeHeightCM": 40.0,
                                            "StreakAmount": 0.2})),
    # poste de madera creosotado: gris pardo; tablas a 36 cm => en un poste de 25 cm se lee a lo sumo una grieta
    "MI_PosteMadera":       ("Madera", ("tint", (0.55, 0.52, 0.5)),
                             {"Saturation": 0.3, "TileSizeCM": 360.0, "NormalStrength": 0.5, "MacroVariation": 0.8,
                              "GrimeAmount": 0.5, "StreakAmount": 0.3, "MossAmount": 0.25, "RoughnessMult": 1.6}),
    "MI_Cable":             ("MetalPintado", ("color", "#2C2C2C"),
                             merge(LIMPIO, {"RoughnessMult": 1.4, "NormalStrength": 0.2, "MacroVariation": 0.0,
                                            "HueVariation": 0.0})),
    # ---------------- v2
    "MI_Corteza":           ("Corteza", ("tint", (1.25, 1.25, 1.22)),
                             {"Saturation": 0.8, "GrimeAmount": 0.4, "GrimeHeightCM": 50.0, "MossAmount": 0.35,
                              "StreakAmount": 0.0, "MacroVariation": 0.5, "HueVariation": 0.8, "ContactGrime": 0.3}),
    "MI_PosteHormigon":     ("Hormigon", ("color", "#9E9C96"),
                             {"AntiTile": 0.4, "GrimeAmount": 0.5, "StreakAmount": 0.6, "MossAmount": 0.2,
                              "MacroVariation": 0.5, "ContactGrime": 0.3}),
    "MI_Tierra":            ("Tierra", None, {"GrimeAmount": 0.0, "StreakAmount": 0.0, "MossAmount": 0.0,
                                               "MacroVariation": 0.8, "HueVariation": 1.0, "AntiTile": 0.5,
                                               "ContactGrime": 0.2}),
    "MI_Pasto":             ("Pasto", ("tint", (1.05, 1.0, 1.0)),
                             {"Saturation": 0.85, "MacroVariation": 0.9, "HueVariation": 1.5, "AntiTile": 0.5,
                              "GrimeAmount": 0.0, "StreakAmount": 0.0, "MossAmount": 0.0, "ContactGrime": 0.25,
                              "Specular": 0.4}),
    # charco: agua barrosa oscura, casi espejo (F0 0.02 = Specular 0.25)
    "MI_Agua":              ("MetalPintado", ("color", "#1D1F1C"),
                             merge(LIMPIO, {"RoughnessMult": 0.05, "NormalStrength": 0.02, "MacroVariation": 0.2,
                                            "HueVariation": 0.3, "Specular": 0.25})),
    "MI_Hormigon_Bacheo":   ("Hormigon", ("color", "#8A8780"),
                             {"Saturation": 0.9, "AntiTile": 0.5, "MacroVariation": 0.7, "HueVariation": 0.5,
                              "RoughnessMult": 0.95, "GrimeAmount": 0.0, "StreakAmount": 0.0, "MossAmount": 0.05,
                              "ContactGrime": 0.3}),
    "MI_Madera_Puerta":     ("Madera", ("tint", (0.62, 0.54, 0.48)),
                             {"Saturation": 0.55, "GrimeAmount": 0.35, "GrimeHeightCM": 40.0, "StreakAmount": 0.25,
                              "MacroVariation": 0.4, "HueVariation": 0.6, "RoughnessMult": 0.95, "MossAmount": 0.0}),
    "MI_Follaje":           ("Follaje", ("tint", (1.05, 1.0, 0.95)),
                             merge(LIMPIO, {"Saturation": 0.85, "MacroVariation": 0.9, "HueVariation": 1.5,
                                            "AntiTile": 0.4, "Specular": 0.35})),
    "MI_Plastico_Negro":    ("MetalPintado", ("color", "#2E2E2E"),
                             {"RoughnessMult": 1.3, "MacroVariation": 0.2, "HueVariation": 0.0, "GrimeAmount": 0.2,
                              "StreakAmount": 0.1, "MossAmount": 0.0, "ContactGrime": 0.3}),
    "MI_Neumatico":         ("MetalPintado", ("color", "#353331"),
                             {"RoughnessMult": 2.1, "NormalStrength": 0.3, "MacroVariation": 0.15,
                              "HueVariation": 0.0, "GrimeAmount": 0.5, "GrimeHeightCM": 30.0, "StreakAmount": 0.0,
                              "MossAmount": 0.0, "ContactGrime": 0.4, "Specular": 0.4}),
    "MI_Auto_Blanco":       ("MetalPintado", ("color", "#D8D8D3"), PINTURA_AUTO),
    "MI_Auto_Gris":         ("MetalPintado", ("color", "#9A9C9E"), merge(PINTURA_AUTO, {"MetallicAdd": 0.5,
                                                                                         "RoughnessMult": 0.8})),
    "MI_Auto_Rojo":         ("MetalPintado", ("color", "#8A2B23"), merge(PINTURA_AUTO, {"Saturation": 0.9})),
    "MI_Auto_Azul":         ("MetalPintado", ("color", "#2D4566"), PINTURA_AUTO),
    "MI_Auto_Negro":        ("MetalPintado", ("color", "#232325"), merge(PINTURA_AUTO, {"GrimeAmount": 0.55})),
    "MI_Pintura_Blanca":    ("Hormigon", ("color", "#D6D4CC"),
                             {"RoughnessMult": 0.78, "AntiTile": 0.5, "MacroVariation": 0.6, "HueVariation": 0.3,
                              "GrimeAmount": 0.4, "GrimeHeightCM": 20.0, "StreakAmount": 0.0, "MossAmount": 0.05,
                              "ContactGrime": 0.3}),
    "MI_Pintura_Amarilla":  ("Hormigon", ("color", "#C9A43E"),
                             {"Saturation": 0.9, "RoughnessMult": 0.78, "AntiTile": 0.5, "MacroVariation": 0.6,
                              "HueVariation": 0.5, "GrimeAmount": 0.4, "GrimeHeightCM": 20.0, "StreakAmount": 0.0,
                              "MossAmount": 0.05, "ContactGrime": 0.3}),
    # azul institucional ficticio (no copia ninguna fuerza real), revoque pintado algo desteñido
    "MI_Comisaria_Azul":    ("Revoque", ("color", "#38598A"), merge(REVOQUE, {"Saturation": 0.9, "StreakAmount": 0.7,
                                                                             "GrimeAmount": 0.6, "HueVariation": 0.5})),
    "MI_Cartel_Blanco":     ("MetalPintado", ("color", "#E0E0DA"), CARTEL),
    "MI_Cartel_Rojo":       ("MetalPintado", ("color", "#A3241E"), CARTEL),
    "MI_Cartel_Verde":      ("MetalPintado", ("color", "#1F5A3B"), CARTEL),
    "MI_Cartel_Azul":       ("MetalPintado", ("color", "#1F4079"), CARTEL),
    "MI_Vidrio_Local":      ("MetalPintado", ("color", "#22292C"),
                             merge(LIMPIO, {"RoughnessMult": 0.12, "NormalStrength": 0.05, "MacroVariation": 0.2,
                                            "HueVariation": 0.0, "GrimeAmount": 0.3, "GrimeHeightCM": 50.0,
                                            "StreakAmount": 0.15})),
    # Emisivos en nits (cd/m2, exposición física). Noche EV100 -1..2 => gris medio ~1-5 nits:
    # 40 nits se lee como ventana/difusor encendido sin quemar; de día (~5000 nits) se ve apagado, como en la realidad.
    "MI_Emisivo_Calido":    ("MetalPintado", ("color", "#D9CDB4"),
                             merge(LIMPIO, {"RoughnessMult": 0.8, "NormalStrength": 0.1, "MacroVariation": 0.0,
                                            "HueVariation": 0.0, "EmissiveStrength": 40.0})),
    "MI_Emisivo_Verde":     ("MetalPintado", ("color", "#1E5A34"),
                             merge(LIMPIO, {"RoughnessMult": 0.5, "NormalStrength": 0.1, "MacroVariation": 0.0,
                                            "HueVariation": 0.0, "EmissiveStrength": 45.0})),
    "MI_Emisivo_Baliza_Azul": ("MetalPintado", ("color", "#1B2E66"),
                               merge(LIMPIO, {"RoughnessMult": 0.5, "NormalStrength": 0.1, "MacroVariation": 0.0,
                                              "HueVariation": 0.0, "EmissiveStrength": 60.0,
                                              "EmissivePulseHz": 1.2, "EmissivePhase": 0.0})),
    "MI_Emisivo_Baliza_Roja": ("MetalPintado", ("color", "#6A1712"),
                               merge(LIMPIO, {"RoughnessMult": 0.5, "NormalStrength": 0.1, "MacroVariation": 0.0,
                                              "HueVariation": 0.0, "EmissiveStrength": 50.0,
                                              "EmissivePulseHz": 1.2, "EmissivePhase": 0.5})),
    # extra opcional: cabeza de luminaria LED más intensa que una ventana (la geometría puede seguir usando Calido)
    "MI_Emisivo_Luminaria": ("MetalPintado", ("color", "#E6E4DC"),
                             merge(LIMPIO, {"RoughnessMult": 0.6, "NormalStrength": 0.05, "MacroVariation": 0.0,
                                            "HueVariation": 0.0, "EmissiveStrength": 150.0})),
    "MI_Riel":              ("Riel", None, {"Saturation": 0.75, "PolishTop": 1.0, "MacroVariation": 0.4,
                                             "HueVariation": 0.5, "GrimeAmount": 0.0, "StreakAmount": 0.0,
                                             "MossAmount": 0.0, "ContactGrime": 0.3}),
    # durmiente de hormigón pretensado (línea renovada), manchado de óxido y grasa
    "MI_Durmiente":         ("Hormigon", ("color", "#7D7469"),
                             {"Saturation": 0.9, "AntiTile": 0.4, "MacroVariation": 0.6, "HueVariation": 0.8,
                              "GrimeAmount": 0.5, "GrimeHeightCM": 15.0, "StreakAmount": 0.0, "MossAmount": 0.1,
                              "ContactGrime": 0.5}),
    "MI_Balasto":           ("Balasto", ("tint", (1.2, 1.2, 1.2)),
                             {"AntiTile": 0.45, "MacroVariation": 0.6, "HueVariation": 0.6, "GrimeAmount": 0.0,
                              "StreakAmount": 0.0, "MossAmount": 0.05, "ContactGrime": 0.3}),
    # ---------------- v4 (pedidos de la geometría)
    # ladrillo visto de la torre (hito): más oscuro y parejo que el de las casas, juntas sucias, mucha chorreadura
    "MI_Ladrillo_Torre":    ("Ladrillo", ("tint", (0.82, 0.8, 0.76)),
                             {"Saturation": 0.62, "TileSizeCM": 264.0, "MacroVariation": 0.45, "HueVariation": 0.6,
                              "GrimeAmount": 0.35, "StreakAmount": 0.7, "MossAmount": 0.05, "ContactGrime": 0.4}),
    # pilar / viga de hormigón armado a la vista (encofrado), más claro y con chorreaduras de agua
    "MI_Hormigon_Pilar":    ("Hormigon", ("color", "#A29F97"),
                             {"AntiTile": 0.45, "MacroVariation": 0.5, "HueVariation": 0.5, "GrimeAmount": 0.55,
                              "GrimeHeightCM": 80.0, "StreakAmount": 0.75, "MossAmount": 0.12, "ContactGrime": 0.5}),
    # alambre galvanizado: metálico, el color es el F0 del zinc gastado
    "MI_Alambrado":         ("MetalPintado", ("color", "#A3A6A8"),
                             merge(LIMPIO, {"MetallicAdd": 0.85, "RoughnessMult": 1.2, "NormalStrength": 0.2,
                                            "MacroVariation": 0.3, "HueVariation": 0.2, "GrimeAmount": 0.2,
                                            "GrimeHeightCM": 40.0})),
}

# Colores de emisión (lineales, normalizados a luminancia 1: EmissiveStrength = luminancia en nits)
EMISSIVE_COLORS = {
    "MI_Emisivo_Calido": (1.0, 0.62, 0.30),       # ~2700 K
    "MI_Emisivo_Luminaria": (1.0, 0.86, 0.68),    # LED ~4000 K
    "MI_Emisivo_Baliza_Azul": (0.03, 0.18, 1.0),
    "MI_Emisivo_Baliza_Roja": (1.0, 0.035, 0.02),
    "MI_Emisivo_Verde": (0.10, 1.0, 0.35),       # marca común de las salidas
}


def _lum_norm(c):
    lum = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    return lc(*[x / max(lum, 1e-4) for x in c])


def set_switch(mi, name, value):
    fn = getattr(mel, "set_material_instance_static_switch_parameter_value", None)
    if fn is None:
        warn(f"{mi.get_name()}: esta versión no expone set_material_instance_static_switch_parameter_value; "
             f"{name} queda en el valor del maestro")
        return
    try:
        fn(mi, name, bool(value))
    except Exception as e:  # noqa: BLE001
        warn(f"{mi.get_name()}: no pude fijar el switch {name}: {e}")


def build_instances(master):
    clear = getattr(mel, "clear_all_material_instance_parameters", None)
    for name, (s, color, extra) in INSTANCES.items():
        path = f"{MAT_DIR}/{name}"
        mi = eal.load_asset(path) if eal.does_asset_exist(path) else None
        if mi is None:
            mi = tools.create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, master)
        if clear:
            clear(mi)                                   # idempotente: nada de overrides viejos (p. ej. Tint de v1)
        for suf, pname in (("BC", "BaseColorTex"), ("N", "NormalTex"), ("ORM", "ORMTex")):
            tex = eal.load_asset(f"{TEX_ROOT}/{s}/T_{s}_{suf}")
            if tex:
                mel.set_material_instance_texture_parameter_value(mi, pname, tex)
            else:
                err(f"{name}: falta textura {s}_{suf}")
        vals = dict(COMMON)
        vals["TileSizeCM"] = float(SETS[s])
        vals.update(extra)
        use_contact = vals.pop("UseContactGrime", True)
        for k, v in vals.items():
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
        mel.set_material_instance_vector_parameter_value(mi, "Tint", tint_for(s, color))
        if name in EMISSIVE_COLORS:
            mel.set_material_instance_vector_parameter_value(mi, "EmissiveColor", _lum_norm(EMISSIVE_COLORS[name]))
        if not use_contact:
            set_switch(mi, "UseContactGrime", False)
        mel.update_material_instance(mi)
        eal.save_asset(path, only_if_is_dirty=False)
    log(f"{len(INSTANCES)} instancias de material listas")


# ---------------------------------------------------------------- 5) v4: carteles con texto (UV0 + atlas)
# Las mallas de cartel (barrio_props.placa_texto / build_cartel_calle) mapean la cara de texto a UV0 0..1.
# El material lleva ese 0..1 al rectángulo del cartel en el atlas: UV' = AtlasRect.rg + UV0 * AtlasRect.ba.
# Sin triplanar: el texto tiene que caer exacto sobre la placa.
CART_DIR = "Carteles"
CART_TEX = f"{TEX_ROOT}/{CART_DIR}"
CART_MASTER = f"{MAT_DIR}/M_Barrio_Cartel"
CART_MASTER_MASK = f"{MAT_DIR}/M_Barrio_Cartel_Mascara"
CART_ATLAS = {"Calle": (2048, 2048), "Comercio": (2048, 4096), "Varios": (2048, 2048)}

# Tabla de RESPALDO (idéntica a gen_textures.catalogo_carteles). Si existe carteles_atlas.json manda el json.
_CALLES = ["ValentinGomez", "Urquiza", "AvSanMartin", "Ferreyra", "Alberdi", "Nicaragua", "Sabattini", "Fischetti",
           "MarianoMoreno", "EstebanMerlo", "Bonifacini", "Puan", "Rauch", "MarcoPolo", "Espana", "Constitucion"]
_COMERCIOS = ["AlmacenDonTito", "Kiosco24hs", "VerduleriaLaEsquina", "FerreteriaElTornillo", "PizzeriaLoDeCacho",
              "FarmaciaDelBarrio", "CarniceriaLosHermanos", "PanaderiaLaEspiga", "PeluqueriaEstilo",
              "RotiseriaDonaRosa", "LibreriaElLapiz", "GomeriaElRayo", "LavaderoBurbujas", "PolirrubroLosChicos",
              "DespensaMary", "BazarElSol"]


def _tabla_respaldo():
    t = {}
    for i, slug in enumerate(_CALLES):
        t["MI_CartelCalle_" + slug] = ("Calle", ((i % 2) * 1024, (i // 2) * 256, 1024, 256), False)
    for i, slug in enumerate(_COMERCIOS):
        t["MI_Comercio_" + slug] = ("Comercio", (0, i * 256, 2048, 256), False)
    t.update({
        "MI_Cartel_Comisaria": ("Varios", (0, 0, 2048, 256), False),
        "MI_Cartel_Estacion": ("Varios", (0, 256, 2048, 256), False),
        "MI_Cartel_Salida": ("Varios", (0, 512, 1024, 256), False),
        "MI_Cartel_Salida_Der": ("Varios", (1024, 512, 1024, 256), False),
        "MI_Cartel_Salida_Izq": ("Varios", (0, 768, 1024, 256), False),
        "MI_Cartel_NoEstacionar": ("Varios", (1024, 768, 1024, 256), False),
        "MI_Bandera_Celeste": ("Varios", (0, 1024, 1024, 512), False),
        "MI_Afiche_SeVende": ("Varios", (1024, 1024, 512, 512), False),
        "MI_Afiche_Alquilo": ("Varios", (1536, 1024, 512, 512), False),
    })
    for i in range(4):
        t["MI_Pintada_%d" % (i + 1)] = ("Varios", (i * 512, 1536, 512, 512), True)
    return t


def tabla_carteles():
    """MI -> (atlas, (x, y, w, h) px, enmascarado). Lee carteles_atlas.json (lo escribe gen_textures.py)."""
    resp = _tabla_respaldo()
    jp = os.path.join(SRC_DIR, CART_DIR, "carteles_atlas.json")
    if not os.path.exists(jp):
        warn(f"No está {jp}: uso la tabla de respaldo del script")
        return resp
    try:
        import json
        with open(jp, encoding="utf-8") as f:
            data = json.load(f)
        t = {}
        for mi, d in data["carteles"].items():
            t[mi] = (d["atlas"], tuple(d["rect_px"]), bool(d.get("mascara", False)))
        dif = sorted(set(t) ^ set(resp))
        if dif:
            warn(f"carteles_atlas.json y la tabla de respaldo difieren en: {dif} (manda el json)")
        return t
    except Exception as e:  # noqa: BLE001
        err(f"carteles_atlas.json ilegible ({e}); uso la tabla de respaldo")
        return resp


# Placas "slot" del cartel de calle: la malla CartelCalle usa estos dos nombres de slot y cada instancia los
# reemplaza (swaps) por el nombre de calle que corresponde. Default: la primera y la sexta calle.
CARTEL_SLOTS = {"MI_CartelCalle_X": "MI_CartelCalle_ValentinGomez", "MI_CartelCalle_Y": "MI_CartelCalle_Nicaragua"}

# Ajustes por tipo (escalares del maestro de carteles)
CART_PARAMS_DEF = {"RoughnessMult": 1.0, "MetallicMult": 1.0, "NormalStrength": 1.0, "Specular": 0.5,
                   "EmissiveStrength": 0.0, "Saturation": 1.0}
CART_PARAMS = {
    "MI_Bandera_Celeste": {"Specular": 0.35},
    "MI_Afiche_SeVende": {"Specular": 0.4},
    "MI_Afiche_Alquilo": {"Specular": 0.4},
}


def import_cartel_textures():
    d = os.path.join(SRC_DIR, CART_DIR)
    files = [f"T_Carteles_{a}_{suf}.png" for a in CART_ATLAS for suf in ("BC", "ORM")] + ["T_Carteles_N.png"]
    tasks = []
    for fn in files:
        f = os.path.join(d, fn)
        if not os.path.exists(f):
            err(f"Falta {f} (correr gen_textures.py Carteles y copiar textures/Carteles)")
            continue
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", f)
        t.set_editor_property("destination_path", CART_TEX)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", False)
        tasks.append(t)
    if tasks:
        tools.import_asset_tasks(tasks)
    for fn in files:
        name = fn[:-4]
        p = f"{CART_TEX}/{name}"
        tex = eal.load_asset(p)
        if not tex:
            continue
        TC = unreal.TextureCompressionSettings
        if name.endswith("_BC"):
            tex.set_editor_property("srgb", True)
            tex.set_editor_property("compression_settings", TC.TC_DEFAULT)   # Varios lleva alfa (máscara) -> BC3
        elif name.endswith("_ORM"):
            tex.set_editor_property("srgb", False)
            tex.set_editor_property("compression_settings", TC.TC_MASKS)
        else:
            tex.set_editor_property("srgb", False)
            tex.set_editor_property("compression_settings", TC.TC_NORMALMAP)
            tex.set_editor_property("flip_green_channel", False)
        # Texto: que no se borronee de lejos tan rápido (sharpen en la generación de mips si existe)
        try:
            tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_SHARPEN2)
        except Exception:  # noqa: BLE001
            pass
        eal.save_asset(p, only_if_is_dirty=False)
    log("Texturas de carteles importadas")


HLSL_ATLAS_UV = r"""
// UV0 de la placa (0..1) -> rectángulo del cartel en el atlas (V hacia abajo, origen arriba-izquierda)
// El parámetro vectorial entra como RGB: el alto del rectángulo viene aparte por el pin A.
return Rect.rg + saturate(UV) * float2(Rect.b, RectA);
"""


def _get_or_reset_material(path):
    name = path.rsplit("/", 1)[1]
    mat = eal.load_asset(path) if eal.does_asset_exist(path) else None
    if isinstance(mat, unreal.Material):
        mel.delete_all_material_expressions(mat)
        log(f"{name} existente: grafo vaciado y reconstruido")
        return mat
    if mat is not None:
        eal.delete_asset(path)
    return tools.create_asset(name, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())


def _tex_sample(mat, name, x, y, sampler, default_tex):
    e = new_expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("group", "Texturas")
    if default_tex:
        e.set_editor_property("texture", default_tex)
    e.set_editor_property("sampler_type", sampler)
    return e


def _out(src, names, dst, dst_in):
    """Conecta probando nombres de salida (cambian entre versiones: 'RGB'/'' , 'A'/...)."""
    for n in names:
        if mel.connect_material_expressions(src, n, dst, dst_in):
            return True
    err(f"No conecté {src.get_name()}{names} -> {dst.get_name()}[{dst_in}]")
    return False


def build_cartel_master(path, masked):
    """Maestro simple para carteles: UV0 remapeada al atlas, BC*Tint, ORM, normal, emisivo opcional (nits)."""
    mat = _get_or_reset_material(path)
    BM = unreal.BlendMode
    props = [("blend_mode", BM.BLEND_MASKED if masked else BM.BLEND_OPAQUE),
             ("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT),
             ("two_sided", False),
             ("used_with_nanite", True),
             ("used_with_instanced_static_meshes", True)]
    if masked:
        props.append(("opacity_mask_clip_value", 0.4))
    for prop, val in props:
        try:
            mat.set_editor_property(prop, val)
        except Exception as e:  # noqa: BLE001
            warn(f"{path}: no pude fijar {prop}: {e}")
    P = unreal.MaterialSamplerType
    dflt_bc = eal.load_asset(f"{CART_TEX}/T_Carteles_{'Varios' if masked else 'Calle'}_BC")
    dflt_orm = eal.load_asset(f"{CART_TEX}/T_Carteles_{'Varios' if masked else 'Calle'}_ORM")
    dflt_n = eal.load_asset(f"{CART_TEX}/T_Carteles_N")

    tc = new_expr(mat, unreal.MaterialExpressionTextureCoordinate, -1600, 0)
    rect = vector_param(mat, "AtlasRect", unreal.LinearColor(0.0, 0.0, 1.0, 1.0), -1600, 120, "Atlas")
    uv = custom(mat, HLSL_ATLAS_UV, ["UV", "Rect", "RectA"], unreal.CustomMaterialOutputType.CMOT_FLOAT2, -1300, 40,
                "UV0 -> rectángulo del atlas")
    connect(tc, "", uv, "UV")
    connect(rect, "", uv, "Rect")
    connect(rect, "A", uv, "RectA")

    bc = _tex_sample(mat, "BaseColorTex", -1000, -300, P.SAMPLERTYPE_COLOR, dflt_bc)
    orm = _tex_sample(mat, "ORMTex", -1000, 100, P.SAMPLERTYPE_MASKS, dflt_orm)
    nt = _tex_sample(mat, "NormalTex", -1000, 450, P.SAMPLERTYPE_NORMAL, dflt_n)
    for t in (bc, orm, nt):
        connect(uv, "", t, "UVs")

    # color: BC * Tint, con saturación ajustable (decolorar por instancia)
    tint = vector_param(mat, "Tint", unreal.LinearColor(1, 1, 1, 1), -700, -420)
    col = custom(mat, r"""
float3 c = Base * Tint.rgb;
float L = dot(c, float3(0.2126, 0.7152, 0.0722));
return max(lerp(L.xxx, c, Sat), 0.0);
""", ["Base", "Tint", "Sat"], F3T, -450, -350, "Color del cartel")
    _out(bc, ["RGB", ""], col, "Base")
    connect(tint, "", col, "Tint")
    connect(scalar_param(mat, "Saturation", 1.0, -700, -280, "Color"), "", col, "Sat")

    ormf = custom(mat, r"""
return float3(ORM.r, saturate(ORM.g * RMul), saturate(ORM.b * MMul));
""", ["ORM", "RMul", "MMul"], F3T, -450, 100, "ORM del cartel")
    _out(orm, ["RGB", ""], ormf, "ORM")
    connect(scalar_param(mat, "RoughnessMult", 1.0, -700, 200), "", ormf, "RMul")
    connect(scalar_param(mat, "MetallicMult", 1.0, -700, 270), "", ormf, "MMul")
    m_ao = mask(mat, ormf, "r", -200, 60)
    m_r = mask(mat, ormf, "g", -200, 140)
    m_m = mask(mat, ormf, "b", -200, 220)

    # sampler de tipo Normal: ya llega decodificada (-1..1, z reconstruida); hoy la textura es plana
    nrm = custom(mat, r"""
return normalize(lerp(float3(0.0, 0.0, 1.0), N, S));
""", ["N", "S"], F3T, -450, 450, "Normal del cartel")
    _out(nt, ["RGB", ""], nrm, "N")
    connect(scalar_param(mat, "NormalStrength", 1.0, -700, 520), "", nrm, "S")

    # emisivo: el propio color del cartel * EmissiveStrength (nits) -> marquesinas encendidas de noche
    emi = custom(mat, r"""
float3 c = Base;
float L = max(dot(c, float3(0.2126, 0.7152, 0.0722)), 1e-3);
return c / L * Str * saturate(L * 2.0) * Col.rgb;
""", ["Base", "Str", "Col"], F3T, -450, 700, "Emisivo del cartel (nits)")
    connect(col, "", emi, "Base")
    connect(scalar_param(mat, "EmissiveStrength", 0.0, -700, 720, "Emisivo"), "", emi, "Str")
    connect(vector_param(mat, "EmissiveColor", unreal.LinearColor(1, 1, 1, 1), -700, 790, "Emisivo"), "", emi, "Col")

    MP = unreal.MaterialProperty
    links = [(col, MP.MP_BASE_COLOR), (nrm, MP.MP_NORMAL), (m_r, MP.MP_ROUGHNESS), (m_m, MP.MP_METALLIC),
             (m_ao, MP.MP_AMBIENT_OCCLUSION), (emi, MP.MP_EMISSIVE_COLOR),
             (scalar_param(mat, "Specular", 0.5, -200, 320), MP.MP_SPECULAR)]
    for node, prop in links:
        if not mel.connect_material_property(node, "", prop):
            err(f"No conecté {node.get_name()} -> {prop}")
    if masked:
        ok = False
        for n in ("A", "Alpha"):
            if mel.connect_material_property(bc, n, MP.MP_OPACITY_MASK):
                ok = True
                break
        if not ok:
            a = mask(mat, bc, "a", -200, 420)     # respaldo: máscara del RGBA
            if not mel.connect_material_property(a, "", MP.MP_OPACITY_MASK):
                err(f"{path}: no conecté la máscara de opacidad")
    mel.recompile_material(mat)
    eal.save_asset(path, only_if_is_dirty=False)
    log(f"Material {path.rsplit('/', 1)[1]} listo ({'enmascarado' if masked else 'opaco'})")
    return mat


def build_cartel_instances(m_opaco, m_mask):
    tabla = tabla_carteles()
    todo = dict(tabla)
    for slot, src in CARTEL_SLOTS.items():
        if src in tabla:
            todo[slot] = tabla[src]
    clear = getattr(mel, "clear_all_material_instance_parameters", None)
    n = 0
    for name, (atlas, (x, y, w, h), masked) in todo.items():
        path = f"{MAT_DIR}/{name}"
        mi = eal.load_asset(path) if eal.does_asset_exist(path) else None
        if mi is None:
            mi = tools.create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant,
                                    unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, m_mask if masked else m_opaco)
        if clear:
            clear(mi)
        for suf, pname in (("BC", "BaseColorTex"), ("ORM", "ORMTex")):
            tex = eal.load_asset(f"{CART_TEX}/T_Carteles_{atlas}_{suf}")
            if tex:
                mel.set_material_instance_texture_parameter_value(mi, pname, tex)
            else:
                err(f"{name}: falta T_Carteles_{atlas}_{suf}")
        tn = eal.load_asset(f"{CART_TEX}/T_Carteles_N")
        if tn:
            mel.set_material_instance_texture_parameter_value(mi, "NormalTex", tn)
        W, H = CART_ATLAS.get(atlas, (2048, 2048))
        mel.set_material_instance_vector_parameter_value(mi, "AtlasRect", unreal.LinearColor(x / W, y / H, w / W, h / H))
        vals = dict(CART_PARAMS_DEF)
        vals.update(CART_PARAMS.get(name, {}))
        for k, v in vals.items():
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
        mel.set_material_instance_vector_parameter_value(mi, "Tint", lc(1, 1, 1))
        mel.update_material_instance(mi)
        eal.save_asset(path, only_if_is_dirty=False)
        n += 1
    log(f"{n} instancias de carteles listas (UV0 + atlas)")


try:
    import_textures()
except Exception as e:  # noqa: BLE001
    err(f"Importando texturas: {e}")
master = build_master()
build_instances(master)
try:
    import_cartel_textures()
except Exception as e:  # noqa: BLE001
    err(f"Importando texturas de carteles: {e}")
try:
    m_cart = build_cartel_master(CART_MASTER, False)
    m_cart_mask = build_cartel_master(CART_MASTER_MASK, True)
    build_cartel_instances(m_cart, m_cart_mask)
except Exception as e:  # noqa: BLE001
    import traceback
    err(f"Carteles: {e}\n{traceback.format_exc()}")
log("MATERIALES LISTOS")

