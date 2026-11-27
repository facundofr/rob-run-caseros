# -*- coding: utf-8 -*-
"""setup_hojas.py - Material de tarjetas de hojas para las copas (v5). Correr en el editor:
    py "<ruta>/setup_hojas.py"
1. Importa game/ArtSource/Textures/Hojas/T_Hojas_BC.png (RGBA) y T_Hojas_N.png (de gen_hojas.py).
2. Crea M_Barrio_Hojas: enmascarado, dos caras, sombreado de follaje de dos caras (la luz pasa por la hoja),
   UV0 directa (la tarjeta ya trae su cuadrante del atlas 2x2), color = textura * Tint con variación suave por
   posición (que no todas las copas sean del mismo verde), normal de la textura.
3. Crea MI_Hojas_Fresno / MI_Hojas_Paraiso / MI_Hojas_Platano.
Imprime "[ARTE] HOJAS LISTAS".
"""
import os

import unreal

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()

PROJ = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SRC = os.path.join(PROJ, "ArtSource", "Textures", "Hojas")
TEX_DIR = "/Game/Barrio/Art/Textures/Hojas"
MAT_DIR = "/Game/Barrio/Art/Materials"
MASTER = f"{MAT_DIR}/M_Barrio_Hojas"
F3 = unreal.CustomMaterialOutputType.CMOT_FLOAT3

# tinte lineal sobre la textura (gris-verde medio); Tint2 = extremo de la variación (más amarillo / más oscuro)
INSTANCIAS = {
    # v5b: más oscuros y menos saturados (de contraluz se iban a verde lima) y menos transmisión
    "MI_Hojas_Fresno": dict(Tint=(0.36, 0.46, 0.24), Tint2=(0.44, 0.48, 0.22), SSS=(0.20, 0.30, 0.06)),
    "MI_Hojas_Paraiso": dict(Tint=(0.30, 0.42, 0.22), Tint2=(0.36, 0.44, 0.20), SSS=(0.16, 0.26, 0.05)),
    "MI_Hojas_Platano": dict(Tint=(0.42, 0.50, 0.24), Tint2=(0.52, 0.52, 0.22), SSS=(0.24, 0.32, 0.07)),
}


def log(m):
    unreal.log(f"[ARTE] {m}")


def err(m):
    unreal.log_error(f"[ARTE] {m}")


def importar():
    tasks = []
    for fn in ("T_Hojas_BC.png", "T_Hojas_N.png"):
        f = os.path.join(SRC, fn)
        if not os.path.exists(f):
            err(f"Falta {f} (correr gen_hojas.py)")
            continue
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", f)
        t.set_editor_property("destination_path", TEX_DIR)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", False)
        tasks.append(t)
    if tasks:
        tools.import_asset_tasks(tasks)
    TC = unreal.TextureCompressionSettings
    bc = eal.load_asset(f"{TEX_DIR}/T_Hojas_BC")
    nt = eal.load_asset(f"{TEX_DIR}/T_Hojas_N")
    if bc:
        bc.set_editor_property("srgb", True)
        bc.set_editor_property("compression_settings", TC.TC_DEFAULT)
        eal.save_asset(f"{TEX_DIR}/T_Hojas_BC", only_if_is_dirty=False)
    if nt:
        nt.set_editor_property("srgb", False)
        nt.set_editor_property("compression_settings", TC.TC_NORMALMAP)
        nt.set_editor_property("flip_green_channel", False)
        eal.save_asset(f"{TEX_DIR}/T_Hojas_N", only_if_is_dirty=False)
    log("Texturas de hojas importadas")
    return bc, nt


def expr(mat, cls, x, y):
    return mel.create_material_expression(mat, cls, x, y)


def conn(a, ao, b, bi):
    if not mel.connect_material_expressions(a, ao, b, bi):
        err(f"No conecté {a.get_name()}[{ao}] -> {b.get_name()}[{bi}]")


def sparam(mat, name, v, x, y):
    e = expr(mat, unreal.MaterialExpressionScalarParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", float(v))
    return e


def vparam(mat, name, c, x, y):
    e = expr(mat, unreal.MaterialExpressionVectorParameter, x, y)
    e.set_editor_property("parameter_name", name)
    e.set_editor_property("default_value", unreal.LinearColor(c[0], c[1], c[2], 1.0))
    return e


def custom(mat, code, ins, x, y, desc):
    e = expr(mat, unreal.MaterialExpressionCustom, x, y)
    e.set_editor_property("code", code)
    e.set_editor_property("output_type", F3)
    e.set_editor_property("description", desc)
    arr = []
    for n in ins:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", n)
        arr.append(ci)
    e.set_editor_property("inputs", arr)
    return e


def master(bc, nt):
    m = eal.load_asset(MASTER) if eal.does_asset_exist(MASTER) else None
    if isinstance(m, unreal.Material):
        mel.delete_all_material_expressions(m)
    else:
        if m is not None:
            eal.delete_asset(MASTER)
        m = tools.create_asset("M_Barrio_Hojas", MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    for prop, val in (("blend_mode", unreal.BlendMode.BLEND_MASKED),
                      ("shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE),
                      ("two_sided", True), ("opacity_mask_clip_value", 0.38),
                      ("used_with_nanite", True), ("used_with_instanced_static_meshes", True)):
        try:
            m.set_editor_property(prop, val)
        except Exception as e:  # noqa: BLE001
            err(f"M_Barrio_Hojas: {prop}: {e}")
    S = unreal.MaterialSamplerType
    tb = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, -200)
    tb.set_editor_property("parameter_name", "BaseColorTex")
    tb.set_editor_property("texture", bc)
    tb.set_editor_property("sampler_type", S.SAMPLERTYPE_COLOR)
    tn = expr(m, unreal.MaterialExpressionTextureSampleParameter2D, -900, 300)
    tn.set_editor_property("parameter_name", "NormalTex")
    tn.set_editor_property("texture", nt)
    tn.set_editor_property("sampler_type", S.SAMPLERTYPE_NORMAL)
    wp = expr(m, unreal.MaterialExpressionWorldPosition, -900, -450)
    col = custom(m, r"""
// variación de tono de baja frecuencia (por copa) + un poco por racimo
float3 p = WP / 900.0;
float h = frac(sin(dot(floor(p.xy), float2(12.9898, 78.233))) * 43758.5453);
float h2 = frac(sin(dot(floor(WP.xy / 160.0), float2(39.346, 11.135))) * 24634.6345);
float t = saturate(h * 0.75 + h2 * 0.35);
float3 c = Base * lerp(T1, T2, t) * (0.88 + 0.24 * h2);
return max(c, 0.0);
""", ["Base", "T1", "T2", "WP"], -550, -250, "Color de hojas con variación")
    try:
        conn(tb, "RGB", col, "Base")
    except Exception:  # noqa: BLE001
        conn(tb, "", col, "Base")
    conn(vparam(m, "Tint", (0.62, 0.8, 0.42), -900, -600), "", col, "T1")
    conn(vparam(m, "Tint2", (0.78, 0.86, 0.36), -900, -520), "", col, "T2")
    conn(wp, "", col, "WP")
    sss = vparam(m, "SubsurfaceColor", (0.55, 0.75, 0.18), -550, 100)
    MP = unreal.MaterialProperty
    for node, out, prop in ((col, "", MP.MP_BASE_COLOR), (tn, "RGB", MP.MP_NORMAL),
                            (sparam(m, "Roughness", 0.62, -550, 0), "", MP.MP_ROUGHNESS),
                            (sparam(m, "Specular", 0.35, -550, 50), "", MP.MP_SPECULAR),
                            (sss, "", MP.MP_SUBSURFACE_COLOR)):
        if not mel.connect_material_property(node, out, prop):
            if not mel.connect_material_property(node, "", prop):
                err(f"No conecté {node.get_name()} -> {prop}")
    if not (mel.connect_material_property(tb, "A", MP.MP_OPACITY_MASK)
            or mel.connect_material_property(tb, "Alpha", MP.MP_OPACITY_MASK)):
        err("No conecté la máscara de opacidad de las hojas")
    mel.recompile_material(m)
    eal.save_asset(MASTER, only_if_is_dirty=False)
    log("Material M_Barrio_Hojas listo (enmascarado, follaje de dos caras)")
    return m


def instancias(m):
    for name, p in INSTANCIAS.items():
        path = f"{MAT_DIR}/{name}"
        mi = eal.load_asset(path) if eal.does_asset_exist(path) else None
        if mi is None:
            mi = tools.create_asset(name, MAT_DIR, unreal.MaterialInstanceConstant,
                                    unreal.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, m)
        for k_, key in (("Tint", "Tint"), ("Tint2", "Tint2"), ("SubsurfaceColor", "SSS")):
            c = p[key]
            mel.set_material_instance_vector_parameter_value(mi, k_, unreal.LinearColor(c[0], c[1], c[2], 1.0))
        mel.update_material_instance(mi)
        eal.save_asset(path, only_if_is_dirty=False)
    log(f"{len(INSTANCIAS)} instancias de hojas listas")


try:
    _bc, _nt = importar()
    _m = master(_bc, _nt)
    instancias(_m)
    log("HOJAS LISTAS")
except Exception as _e:  # noqa: BLE001
    import traceback
    err(f"Hojas: {_e}\n{traceback.format_exc()}")
