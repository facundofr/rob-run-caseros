# -*- coding: utf-8 -*-
"""
setup_lighting.py - Ambiente / iluminación de L_Greybox (Barrio, Caseros).  Pase v4 (tarde con nubes y bruma).

Correr en el editor de UE 5.8 (Tools > Execute Python Script, o desde la consola):
    py "C:/.../setup_lighting.py"              -> preset de la variable PRESET (o del archivo, ver abajo)
    py "C:/.../setup_lighting.py" noche        -> preset por argumento
Idempotente: se puede correr N veces y cambiar de preset sin dejar basura.

ELECCIÓN DEL PRESET (prioridad de mayor a menor):
  1. Argumento de línea de comandos (sys.argv[1:]): `noche`, `tarde`, `--preset=noche`...
  2. Archivo <proyecto>/Saved/lighting_preset.txt (primera línea no vacía que no empiece con #).
     Sirve cuando el `py` de UE no pasa argumentos (Execute Python Script, scripts de arranque).
     OJO: si el archivo existe, MANDA sobre la variable. Borrarlo para volver a usar PRESET.
  3. Variable PRESET de abajo.

Criterio general (lighting lead):
  * Unidades físicas con un corrimiento global: sol/luna en lux, luminarias en candelas, exposición en EV100.
    Los presets diurnos cargan el sol a 64 klux en el tope de la atmósfera (la mitad de los 128 klux reales,
    -1 EV para TODO lo diurno: sol, cielo, nubes, niebla). Las relaciones sol/cielo/sombra quedan físicas y la
    exposición diurna baja ~1 EV, así entra en el rango seguro de la luz cacheada de Lumen (ver
    verificar_preexposicion). La noche es absoluta (luminarias reales en candelas).
    Requiere r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange=True (ver DefaultEngine_render.ini).
  * El sol se carga "en el tope de la atmósfera" (atmosphere_sun_light): la SkyAtmosphere lo atenúa
    y lo enrojece según la elevación. Por eso la temperatura de la luz va casi neutra (6000 K): si la luz
    ya es cálida, la atmósfera la enrojece DOS veces (crítica del pase v1).
  * Bruma de Buenos Aires: Mie moderado (BRUMA_MULT) para que el cielo quede celeste pálido arriba y
    blanco cálido solo en el horizonte, como en las refs de Street View.
  * Todo lo que un preset toca, lo tocan TODOS los presets (para que cambiar de preset sea limpio).
  * Coordenadas del mapa (MAPA.md): X este, Y norte, Z arriba. El sol se define por azimut (0 = norte,
    90 = este) y elevación; el script lo convierte a yaw de UE.
"""

import math
import os
import sys

import unreal

# =====================================================================================
# CONFIGURACIÓN (lo único que hace falta tocar)
# =====================================================================================
PRESET = "tarde"          # "tarde" (jugar, por defecto) | "atardecer" | "mediodia_nublado" | "noche"

MAPA = "/Game/Barrio/Maps/L_Greybox"
GUARDAR = True
ARCHIVO_PRESET = "lighting_preset.txt"     # en <proyecto>/Saved/

# Sol diurno en el tope de la atmósfera (lux). Real: ~128000. Ver docstring (-1 EV global diurno).
SOL_TOA_LUX = 64000.0

# Multiplicador global de bruma (Mie). v4: 0.6 -> 0.85. Con 0.6 el cielo quedaba azul marino de altura (crítica
# del director, 5/10); 0.85 = aerosol húmedo del AMBA: celeste lechoso arriba y blanco cálido en el horizonte.
# Los presets que no querían más bruma compensan su mie_scat (ver atardecer / nublado / noche).
BRUMA_MULT = 0.85

# Luna: sus sombras cuestan un VSM direccional entero (~1 ms en la 5050) y a 0.8 lux casi no se ven
# al lado de los charcos de las luminarias. Palanca de presupuesto: False recupera ese tiempo.
LUNA_SOMBRAS = True

# Sharpen post-TSR (cvar de sesión; para que persista va en DefaultEngine.ini, ver DefaultEngine_render.ini)
SHARPEN = 0.4

# ------------------------------------------------------------------ Luminarias (preset noche)
# Contrato v2 (CONVENCIONES.md): TargetPoint con tag LUMINARIA en la cabeza de cada lámpara, mirando abajo.
LUM_TAG = "LUMINARIA"
LUZ_PREFIJO = "ARTE_Lum_"              # label de las SpotLight que crea este script
LUZ_TAG = "ARTE_LuzLuminaria"          # tag de las SpotLight que crea este script (borrado idempotente)
LUZ_CARPETA = "Ambiente/Luminarias"
# Luces de prueba del pase v1 sobre FacadeTest (4 postes + 4 farolitos): se borran siempre.
VIEJAS_PREFIJO = "ARTE_LuzCalle_"
VIEJAS_TAG = "ARTE_Luminaria"

LUX_PIE_CALLE = 12.0       # iluminancia horizontal al pie del poste (calle residencial: 10-15 lux)
LUX_PIE_AVENIDA = 16.0     # avenida y estación: un escalón más (clase vial más alta, LED neutro)
SOMBRA_CADA = 3            # 1 de cada N luminarias proyecta sombra (presupuesto, ver docstring de configurar_luminarias)
CONO_INTERIOR = 62.0       # grados desde el eje. Ancho a propósito: imita la óptica "batwing" del alumbrado vial
CONO_EXTERIOR = 78.0       # (UE no tiene batwing sin IES): el charco llega a 16 m del poste y se solapa con el vecino
ATENUACION_CM = 3000.0     # cubre el punto medio entre postes a 30 m (17 m en diagonal) y la fachada de enfrente
DIST_DIBUJO_CM = 12000.0   # 120 m: MAPA.md garantiza que ninguna visual abierta pasa de 120 m sin cortes
DIST_FADE_CM = 2000.0
BAJAR_LUZ_CM = 20.0        # la luz va 20 cm por debajo del TargetPoint: que la carcasa no la tape si proyecta sombra
CELDA_TRAMO_CM = 8660.0    # una manzana: la mezcla sodio/LED va por tramos, como los recambios reales del municipio
PROPORCION_SODIO = 0.40    # en calles; la avenida y la estación ya son LED
AVENIDA_X = (31000.0, 34000.0)   # MAPA.md: avenida LM 31.176 - 33.776
AFUERA_NORTE_Y = 26016.0         # MAPA.md: estación / andén / playón

PPV_LABEL = "ARTE_PPV_Global"
NUBES_MI_DIR = "/Game/Barrio/Art/Materials/Sky"
NUBES_MI_NOMBRE = "MI_Barrio_Nubes"
# Parámetros del material de motor m_SimpleVolumetricCloud_Inst (nombres vistos en el log del pase v1).
# Doc de Epic: "positive values increase cloud cover and negative values decrease" => es un BIAS
# (default -0.20, aditivo sobre el ruido del layout). Se setea en valor absoluto por preset.
NUBES_PARAM_COBERTURA = ("Cloud_GlobalCoverage", "Layout_GlobalCoverage")
NUBES_PARAM_DENSIDAD = ("Cloud_GlobalDensity",)
NUBES_COBERTURA_RANGO_DEFECTO = (-1.0, 1.0)   # si no se puede leer el slider del material

# Rango seguro de la luz cacheada (Lumen + captura del SkyLight) en función de la cvar de pre-exposición.
# EMPÍRICO, deducido de los avisos del editor en este proyecto: con el default (8) el aviso dice [-8, 12];
# con 4 seguía avisando a exposición ~13.6; con 10 dejó de avisar  =>  [N-16, N+4].
PREEXP_CVARS = ("r.EyeAdaptation.CachedLightingPreExposure", "r.Lumen.CachedLightingPreExposure")
PREEXP_DEFECTO = 8.0
PREEXP_ABAJO, PREEXP_ARRIBA = 16.0, 4.0
EV_A_EXPOSICION = math.log2(1.2)    # UE informa exposición = EV100 + log2(1.2) (~0.26) en ese aviso
MARGEN_EV = 0.25

ALIAS = {
    "tarde": "tarde", "dia": "tarde", "día": "tarde", "juego": "tarde", "jugar": "tarde", "default": "tarde",
    "atardecer": "atardecer", "ocaso": "atardecer", "sunset": "atardecer",
    "mediodia_nublado": "mediodia_nublado", "nublado": "mediodia_nublado", "mediodia": "mediodia_nublado",
    "noche": "noche", "night": "noche",
}

# =====================================================================================
# PRESETS
# =====================================================================================
PRESETS = {
    # ---------------------------------------------------------------- TARDE (por defecto, para JUGAR)
    # v4 (revisión del director, 5/10: "parece mediodía, cielo azul marino sin nubes ni bruma, locales negros"):
    #  * Sol a 22° al ONO (azimut 302: tarde de otoño ~17 h). Sigue diagonal a la grilla, así TODAS las calles
    #    tienen una vereda al sol. Casa baja (4 m): sombra de 9,9 m (7,8 m de calle N-S, 5,2 m de calle E-O);
    #    casa de 2 plantas (7 m): 17 m de largo, la calle N-S queda casi entera en sombra cerca de esas casas
    #    -> el relleno lo da el cielo (SkyLight 1.45 + leaking + exposición local más suave).
    #  * Cúmulos de buen tiempo sueltos (cobertura 0.05, capa baja y fina) + bruma 0.85 + niebla de altura
    #    levemente cálida que arranca a 45 m (nada de velo sobre el jugador) y a ~300 m ya se come el 55 %:
    #    el borde del mundo (Afuera es relleno) se funde en el horizonte.
    #  * Exposición +0.3 EV y sombras con menos contraste local (0.62): un jugador a la sombra se lee a 40 m.
    "tarde": {
        "sol": dict(
            elevacion=22.0, azimut=302.0, lux=SOL_TOA_LUX, temperatura=6000.0, angulo_fuente=0.53,
            contact_shadow=0.03, scattering_vol=0.35, sombra_vol=False, sombras=True, disco=1.0,
            nube_sombra_superficie=0.45,       # sombras de nubes suaves: que no "apaguen" una calle en medio de un tiroteo
        ),
        "atmosfera": dict(mie_scat=0.040, mie_abs=0.005, mie_dist_km=1.2, mie_aniso=0.76, factor_cielo=(1.0, 1.0, 1.0),
                          dist_aerea=1.6),     # perspectiva aérea x1.6: la torre y Afuera se azulan/aclaran con la distancia
        # Cúmulos humilis: base 1,4 km, capa fina (1,6 km), cobertura apenas por encima de 0 (-0.45 = cielo vacío)
        "nubes": dict(base_km=1.4, espesor_km=1.6, cobertura=0.05, densidad_mult=0.7,
                      oclusion_base=0.45, transmitancia_por_muestra=False),
        "skylight": dict(intensidad=1.45, cloud_ao=0.4),
        "niebla": dict(
            # Densidad 0.032 (x1/1000 del motor => 3.2e-5/cm): 100 m 16 %, 200 m 40 %, 300 m 56 %, 500 m 77 %.
            # Caída 0.45 => la capa se adelgaza a la mitad cada ~22 m de altura: la torre (hito) sigue leyendo.
            densidad=0.032, caida=0.45, densidad2=0.0, caida2=0.5, inicio_cm=4500.0, opacidad_max=0.96,
            inscat_con_atm=(150.0, 115.0, 70.0),              # tinte cálido SUMADO al color que pone la atmósfera
            inscat_sin_atm=(2900.0, 2850.0, 2750.0), dir_inscat_sin_atm=(1300.0, 950.0, 520.0),
            # v5: (900, 650, 330) con exponente 6 lavaba de blanco medio cielo (lóbulo de ~±40° alrededor del sol,
            # se veía como un corte vertical en las calles N-S y en la aérea NE). Lóbulo angosto y más tenue:
            dir_inscat_con_atm=(300.0, 215.0, 110.0),         # resplandor cálido hacia el sol, solo a distancia
            dir_exp=20.0, dir_inicio_cm=8000.0,
            cielo_amb_escala=(1.06, 1.0, 0.9),                # el aporte de la atmósfera a la niebla, apenas cálido
            volumetrica=False,                 # de día no aporta a la lectura y cuesta ~0.6 ms: apagada
            vol_dist=0.35, vol_albedo=(245, 245, 245), vol_extincion=0.5, vol_distancia_cm=6000.0, vol_inicio_cm=1000.0,
        ),
        "post": dict(
            # ev_max baja de 13.3 a 13.1: con bias 0.3 la ventana [11.3-0.3, 13.1+0.3] (+0.26) queda dentro del rango
            # seguro de la luz cacheada con CachedLightingPreExposure=10 ([-6, 14] con margen 0.25).
            ev_min=11.3, ev_max=13.1, ev_bias=0.3,
            white_temp=6100.0, saturacion=1.0, contraste=1.0,
            bloom=0.22, skylight_leaking=0.12,
            gain_sombras=(0.99, 1.0, 1.04), gain_altas=(1.02, 1.0, 0.975),
            le_altas=0.78, le_sombras=0.62, le_detalle=1.1, offset=(0.0, 0.0, 0.0),
        ),
        "luminarias": False,
    },
    # ---------------------------------------------------------------- ATARDECER (capturas / ambiente)
    # Correcciones de la crítica v1: sol 6000 K (la atmósfera pone el naranja), WB 5900, saturación 1.0,
    # sombras levemente frías, niebla volumétrica que arranca a 10 m con anisotropía baja, sin light shafts,
    # bruma 0.6 y Mie g 0.76 => cielo celeste pálido arriba, blanco cálido solo en el horizonte.
    "atardecer": {
        "sol": dict(
            elevacion=12.0, azimut=290.0, lux=SOL_TOA_LUX, temperatura=6000.0, angulo_fuente=0.53,
            contact_shadow=0.03, scattering_vol=0.35, sombra_vol=True, sombras=True, disco=1.0,
            nube_sombra_superficie=1.0,
        ),
        # v4: mie_scat 0.040 -> 0.034 compensa BRUMA_MULT 0.85 (el ocaso ya enrojecía bien con 0.6)
        "atmosfera": dict(mie_scat=0.034, mie_abs=0.0047, mie_dist_km=1.5, mie_aniso=0.76, factor_cielo=(1.0, 1.0, 1.0),
                          dist_aerea=1.6),
        "nubes": dict(base_km=1.5, espesor_km=2.0, cobertura=-0.10, densidad_mult=0.9,
                      oclusion_base=0.5, transmitancia_por_muestra=True),
        "skylight": dict(intensidad=1.25, cloud_ao=0.6),
        "niebla": dict(
            # v4: misma lógica que la tarde (tapar el borde del mundo, nada de velo en los primeros 40 m)
            densidad=0.026, caida=0.45, densidad2=0.0, caida2=0.5, inicio_cm=4000.0, opacidad_max=0.96,
            inscat_con_atm=(120.0, 80.0, 40.0), inscat_sin_atm=(2400.0, 2300.0, 2200.0), dir_inscat_sin_atm=(1500.0, 1150.0, 750.0),
            dir_inscat_con_atm=(1400.0, 900.0, 420.0), dir_exp=5.0, dir_inicio_cm=5000.0,
            cielo_amb_escala=(1.08, 0.98, 0.86),
            volumetrica=True,
            vol_dist=0.35, vol_albedo=(245, 245, 245), vol_extincion=0.5, vol_distancia_cm=6000.0, vol_inicio_cm=1000.0,
        ),
        "post": dict(
            ev_min=10.5, ev_max=12.8, ev_bias=-0.2,
            white_temp=5900.0, saturacion=1.0, contraste=1.03,
            bloom=0.30, skylight_leaking=0.05,
            gain_sombras=(0.95, 0.985, 1.07), gain_altas=(1.02, 1.0, 0.975),
            le_altas=0.85, le_sombras=0.9, le_detalle=1.05, offset=(0.0, 0.0, 0.0),
        ),
        "luminarias": False,
    },
    # ---------------------------------------------------------------- MEDIODÍA NUBLADO (invierno conurbano)
    "mediodia_nublado": {
        "sol": dict(
            # 90 - 34.6 (latitud) - 23.4 = 32° al mediodía de junio, sol al norte.
            # Cubierto "falsificado" de forma controlable: sol directo atenuado y enorme (la mancha clara
            # detrás de las nubes) + cielo multiplicado. Relación difusa:directa ~2:1.
            elevacion=32.0, azimut=350.0, lux=20000.0, temperatura=6800.0, angulo_fuente=6.0,
            contact_shadow=0.0, scattering_vol=0.3, sombra_vol=False, sombras=True, disco=1.0,
            nube_sombra_superficie=1.0,
        ),
        # v4: 0.110 -> 0.078 compensa BRUMA_MULT 0.85 (mismo Mie efectivo que antes)
        "atmosfera": dict(mie_scat=0.078, mie_abs=0.007, mie_dist_km=2.0, mie_aniso=0.75, factor_cielo=(3.0, 3.0, 3.1),
                          dist_aerea=1.3),
        "nubes": dict(base_km=0.8, espesor_km=2.5, cobertura=0.40, densidad_mult=1.5,
                      oclusion_base=0.8, transmitancia_por_muestra=False),
        "skylight": dict(intensidad=1.1, cloud_ao=1.0),
        "niebla": dict(
            # Antes 0.018 / 0.12: velo pegado a la cámara. Ahora bruma de fondo + neblina rasante de 2ª capa.
            # v4: algo más densa para tapar el borde del mundo (Afuera) y arranque a 30 m
            densidad=0.014, caida=0.25, densidad2=0.016, caida2=0.8, inicio_cm=3000.0, opacidad_max=0.97,
            inscat_con_atm=(2000.0, 2050.0, 2200.0), inscat_sin_atm=(3800.0, 3900.0, 4100.0), dir_inscat_sin_atm=(0.0, 0.0, 0.0),
            dir_inscat_con_atm=(0.0, 0.0, 0.0), dir_exp=8.0, dir_inicio_cm=5000.0,
            cielo_amb_escala=(1.0, 1.0, 1.0),
            volumetrica=False,
            vol_dist=0.2, vol_albedo=(235, 237, 240), vol_extincion=0.5, vol_distancia_cm=6000.0, vol_inicio_cm=1000.0,
        ),
        "post": dict(
            ev_min=10.5, ev_max=12.5, ev_bias=0.0,
            white_temp=6500.0, saturacion=0.97, contraste=1.04,
            bloom=0.15, skylight_leaking=0.08,     # cubierto: la luz entra en galerías y zaguanes
            gain_sombras=(0.98, 0.99, 1.02), gain_altas=(1.01, 1.0, 0.985),
            le_altas=0.85, le_sombras=0.85, le_detalle=1.1, offset=(0.0, 0.0, 0.0),
        ),
        "luminarias": False,
    },
    # ---------------------------------------------------------------- NOCHE (jugable)
    # Luz principal: luminarias del contrato (12 lux al pie, 16 en avenida, charcos solapados ~2-3 lux entre postes).
    # Piso de ambiente ~0.8 lux (luna 0.8 lux "jugable" + SkyLight x3 del cielo urbano naranja) => las zonas
    # entre luces quedan ~3.5 EV por debajo del charco: oscuras, nunca negras. Red de seguridad: color_offset.
    "noche": {
        "sol": dict(
            elevacion=40.0, azimut=120.0,
            lux=0.8,               # luna llena real ~0.1-0.25 lux; x3-4 por jugabilidad (siluetas en calles sin luz)
            temperatura=7000.0,    # físicamente ~4100 K; frío para emular la visión escotópica (Purkinje)
            angulo_fuente=0.53, contact_shadow=0.0, scattering_vol=0.5, sombra_vol=False,
            sombras=LUNA_SOMBRAS, disco=0.25,   # disco de la luna más tenue: que no queme con bloom
            nube_sombra_superficie=0.8,
        ),
        "atmosfera": dict(mie_scat=0.035, mie_abs=0.0056, mie_dist_km=1.0, mie_aniso=0.76, factor_cielo=(1.0, 1.0, 1.0),
                          dist_aerea=1.0),
        "nubes": dict(base_km=1.5, espesor_km=3.0, cobertura=-0.30, densidad_mult=1.0,
                      oclusion_base=0.5, transmitancia_por_muestra=False),
        "skylight": dict(intensidad=3.0, cloud_ao=0.5),   # trampa jugable: el cielo nocturno capturado es ~0.03 cd/m2
        "niebla": dict(
            # Contaminación lumínica: resplandor naranja del sodio sobre la bruma. Con caída 0.25 el naranja se junta
            # en el horizonte (~0.08 cd/m2) y el cenit queda casi negro-azul (cielo lunar de la atmósfera).
            # v4: 0.006 -> 0.012 e inicio 20 m: el borde del mundo se funde en el resplandor naranja
            densidad=0.012, caida=0.25, densidad2=0.0, caida2=0.5, inicio_cm=2000.0, opacidad_max=0.95,
            inscat_con_atm=(0.14, 0.08, 0.04), inscat_sin_atm=(0.14, 0.08, 0.04), dir_inscat_sin_atm=(0.0, 0.0, 0.0),
            dir_inscat_con_atm=(0.0, 0.0, 0.0), dir_exp=8.0, dir_inicio_cm=5000.0,
            cielo_amb_escala=(1.0, 1.0, 1.0),
            volumetrica=True,      # conos de las luminarias en la humedad
            vol_dist=0.4, vol_albedo=(235, 230, 222), vol_extincion=1.0, vol_distancia_cm=5000.0, vol_inicio_cm=200.0,
        ),
        "post": dict(
            # Calibración: pavimento 18% bajo ~10 lux = gris medio con EV ~1.4. Ventana estrecha: entrar a un
            # pasillo oscuro abre como mucho ~1 EV (la noche nunca se "convierte" en día).
            ev_min=0.3, ev_max=2.0, ev_bias=0.0,
            white_temp=4300.0,     # sodio (2100 K) sigue naranja, LED 3000 K cálido, LED 4000 K blanco, luna azulada
            saturacion=0.95, contraste=1.0,
            bloom=0.40, skylight_leaking=0.05,
            gain_sombras=(0.96, 0.985, 1.06), gain_altas=(1.0, 1.0, 1.0),
            le_altas=0.75, le_sombras=0.75, le_detalle=1.1,
            offset=(0.003, 0.0035, 0.005),   # piso de negro frío (~sRGB 8-13/255): nunca negro total
        ),
        "luminarias": True,
    },
}

# =====================================================================================
# UTILIDADES
# =====================================================================================
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
_FALLAS = []
_OPCIONALES_AUSENTES = []


def log(msg):
    unreal.log("[ARTE] " + msg)


def warn(msg):
    unreal.log_warning("[ARTE] " + msg)


def err(msg):
    unreal.log_error("[ARTE] " + msg)


def _nombre_tipo(obj):
    return type(obj).__name__


def set_prop(obj, nombres, valor):
    """Setea una propiedad por nombre snake_case. `nombres` puede ser tupla de alternativas
    (por renombres entre versiones). Al fallar loguea el nombre EXACTO que no existe."""
    if isinstance(nombres, str):
        nombres = (nombres,)
    ultimo = None
    for i, n in enumerate(nombres):
        try:
            obj.set_editor_property(n, valor)
            if i > 0:
                warn("%s.%s no existe en esta versión; se usó '%s'" % (_nombre_tipo(obj), nombres[0], n))
            return True
        except Exception as e:  # noqa
            ultimo = e
    etiqueta = "%s.%s" % (_nombre_tipo(obj), "|".join(nombres))
    _FALLAS.append(etiqueta)
    if len(_FALLAS) == 1:
        err("PRIMER FALLO DE PROPIEDAD -> %s = %r :: %s" % (etiqueta, valor, ultimo))
    else:
        err("Fallo propiedad -> %s :: %s" % (etiqueta, ultimo))
    return False


def set_props(obj, pares):
    ok = 0
    for nombres, valor in pares:
        if set_prop(obj, nombres, valor):
            ok += 1
    return ok


def set_prop_opcional(obj, nombres, valor):
    """Como set_prop pero para mejoras no esenciales: si no existe, solo deja una nota (no cuenta como fallo)."""
    if isinstance(nombres, str):
        nombres = (nombres,)
    for n in nombres:
        try:
            obj.set_editor_property(n, valor)
            return True
        except Exception:  # noqa
            pass
    _OPCIONALES_AUSENTES.append("%s.%s" % (_nombre_tipo(obj), "|".join(nombres)))
    return False


def pp(s, nombres, valor, opcional=False):
    """Setea un campo de FPostProcessSettings activando su override_<campo>."""
    if isinstance(nombres, str):
        nombres = (nombres,)
    ultimo = None
    for i, n in enumerate(nombres):
        try:
            s.set_editor_property(n, valor)                 # primero el valor: si no existe, no queda el override colgado
            s.set_editor_property("override_" + n, True)
            if i > 0:
                warn("PostProcessSettings.%s no existe; se usó '%s'" % (nombres[0], n))
            return True
        except Exception as e:  # noqa
            ultimo = e
    etiqueta = "PostProcessSettings.%s" % "|".join(nombres)
    if opcional:
        _OPCIONALES_AUSENTES.append(etiqueta)
        return False
    _FALLAS.append(etiqueta)
    if len(_FALLAS) == 1:
        err("PRIMER FALLO DE PROPIEDAD -> %s = %r :: %s" % (etiqueta, valor, ultimo))
    else:
        err("Fallo propiedad -> %s :: %s" % (etiqueta, ultimo))
    return False


def lc(r, g, b, a=1.0):
    return unreal.LinearColor(r=float(r), g=float(g), b=float(b), a=float(a))


def col(r, g, b, a=255):
    return unreal.Color(r=int(r), g=int(g), b=int(b), a=int(a))


def v4(x, y, z, w=1.0):
    return unreal.Vector4(x=float(x), y=float(y), z=float(z), w=float(w))


def enum_val(enum_cls_name, *candidatos):
    """Devuelve el primer valor de enum que exista (los nombres de enum a veces cambian)."""
    cls = getattr(unreal, enum_cls_name, None)
    if cls is None:
        return None
    for c in candidatos:
        if hasattr(cls, c):
            return getattr(cls, c)
    return None


def cvar_int(nombre):
    try:
        return int(unreal.SystemLibrary.get_console_variable_int_value(nombre))
    except Exception as e:  # noqa
        warn("No pude leer la cvar %s: %s" % (nombre, e))
        return -1


def cvar_float(nombre):
    try:
        return float(unreal.SystemLibrary.get_console_variable_float_value(nombre))
    except Exception:  # noqa
        return None


def consola(world, comando):
    try:
        unreal.SystemLibrary.execute_console_command(world, comando)
        log("cvar de sesión: %s" % comando)
    except Exception as e:  # noqa
        warn("No pude ejecutar '%s': %s" % (comando, e))


def movible(actor):
    try:
        actor.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    except Exception as e:  # noqa
        err("No pude poner Movable a %s: %s" % (actor.get_actor_label(), e))


def actores_de(clase):
    return [a for a in EAS.get_all_level_actors() if isinstance(a, clase)]


def obtener_o_crear(clase, etiqueta, ubicacion=None, rotacion=None):
    """Reutiliza primero el actor con NUESTRO label (orden estable entre corridas); si no, el primero de la clase."""
    existentes = actores_de(clase)
    propios = [x for x in existentes if x.get_actor_label() == etiqueta]
    if propios or existentes:
        a = (propios or existentes)[0]
        if len(existentes) > 1:
            warn("Hay %d %s en el nivel; uso '%s'. Borrá los duplicados (compiten entre sí)."
                 % (len(existentes), clase.__name__, a.get_actor_label()))
        log("%s: existe ('%s'), se reutiliza" % (clase.__name__, a.get_actor_label()))
    else:
        a = EAS.spawn_actor_from_class(clase, ubicacion or unreal.Vector(0, 0, 0),
                                       rotacion or unreal.Rotator(0, 0, 0))
        log("%s: no existía, creado" % clase.__name__)
    try:
        a.set_actor_label(etiqueta)
    except Exception:  # noqa
        pass
    return a


def comp_de(actor, clase_comp):
    c = actor.get_component_by_class(clase_comp)
    if c is None:
        raise RuntimeError("%s no tiene %s" % (actor.get_actor_label(), clase_comp.__name__))
    return c


def carpeta(actor, ruta):
    try:
        actor.set_folder_path(ruta)
    except Exception:  # noqa
        pass  # cosmético


def tiene_tag(actor, tag):
    try:
        return bool(actor.actor_has_tag(tag))
    except Exception:  # noqa
        try:
            return tag in [str(t) for t in actor.get_editor_property("tags")]
        except Exception:  # noqa
            return False


def yaw_desde_azimut(azimut_sol):
    """Azimut del SOL (de dónde viene: 0 = norte +Y, 90 = este +X) -> yaw de UE de la luz (hacia dónde viaja).
    Forward de UE = (cos yaw, sin yaw). La luz viaja en sentido opuesto al vector hacia el sol (sin az, cos az)."""
    az = math.radians(azimut_sol)
    return math.degrees(math.atan2(-math.cos(az), -math.sin(az)))


# =====================================================================================
# ELECCIÓN DE PRESET
# =====================================================================================
def _normalizar(token):
    t = str(token).strip().strip('"').strip("'").lower()
    t = t.lstrip("-")
    if t.startswith("preset="):
        t = t[len("preset="):]
    return ALIAS.get(t, t)


def _ruta_archivo_preset():
    try:
        saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
        return os.path.join(saved, ARCHIVO_PRESET)
    except Exception as e:  # noqa
        warn("No pude resolver <proyecto>/Saved: %s" % e)
        return None


def elegir_preset():
    """argv > <proyecto>/Saved/lighting_preset.txt > variable PRESET. Devuelve (preset, origen)."""
    # 1) argumentos. En el `py` de UE, sys.argv = [script, args...] cuando se pasan; con
    #    Execute Python Script puede venir vacío, [''] o (en algunas versiones) con restos de otra corrida.
    args = []
    try:
        args = [a for a in list(getattr(sys, "argv", []) or [])[1:] if str(a).strip()]
    except Exception:  # noqa
        args = []
    try:
        if getattr(sys, "argv", None):
            sys.argv = sys.argv[:1]      # consumirlos: que la próxima corrida sin argumentos no herede "noche"
    except Exception:  # noqa
        pass
    for a in args:
        p = _normalizar(a)
        if p in PRESETS:
            return p, "argumento '%s'" % a
    if args:
        warn("Argumentos sin preset válido: %s (opciones: %s)" % (args, list(PRESETS.keys())))

    # 2) archivo
    ruta = _ruta_archivo_preset()
    if ruta and os.path.isfile(ruta):
        try:
            with open(ruta, "r", encoding="utf-8-sig") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea or linea.startswith("#"):
                        continue
                    p = _normalizar(linea.split()[0])
                    if p in PRESETS:
                        if p != PRESET:
                            warn("Preset '%s' tomado de %s: la variable PRESET='%s' se ignora mientras exista el archivo"
                                 % (p, ruta, PRESET))
                        return p, "archivo %s" % ruta
                    warn("%s dice '%s', que no es un preset (opciones: %s). Uso la variable."
                         % (ruta, linea, list(PRESETS.keys())))
                    break
        except Exception as e:  # noqa
            warn("No pude leer %s: %s" % (ruta, e))
    # 3) variable
    return _normalizar(PRESET), "variable PRESET (archivo opcional: %s)" % ruta


# =====================================================================================
# BLOQUES
# =====================================================================================
def asegurar_nivel():
    ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ues.get_editor_world()
    ruta = world.get_path_name() if world else ""
    if MAPA not in ruta:
        log("Nivel abierto: '%s'. Cargo %s" % (ruta, MAPA))
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if not les.load_level(MAPA):
            raise RuntimeError("No se pudo cargar " + MAPA)
        world = ues.get_editor_world()
    log("Nivel OK: %s" % world.get_path_name())
    return world


def inventario():
    for nombre in ("DirectionalLight", "SkyAtmosphere", "SkyLight", "ExponentialHeightFog",
                   "VolumetricCloud", "PostProcessVolume", "TargetPoint", "SpotLight"):
        cls = getattr(unreal, nombre)
        n = len(actores_de(cls))
        log("Inventario: %s x%d" % (nombre, n))


def quitar_skysphere():
    """SM_SkySphere/BP_Sky_Sphere es un domo opaco: tapa la SkyAtmosphere, lo captura el SkyLight
    y rompe la coherencia física. Se borra (se puede recrear desde la plantilla Basic si hiciera falta)."""
    borrados = 0
    for a in EAS.get_all_level_actors():
        etiqueta = a.get_actor_label().lower()
        clase = a.get_class().get_name().lower()
        malla = ""
        try:
            smc = a.get_component_by_class(unreal.StaticMeshComponent)
            if smc is not None:
                m = smc.get_editor_property("static_mesh")
                malla = m.get_name().lower() if m else ""
        except Exception:  # noqa
            pass
        if "skysphere" in etiqueta or "sky_sphere" in etiqueta or "skysphere" in malla \
                or "sky_sphere" in clase or "skysphere" in clase:
            nombre = a.get_actor_label()
            EAS.destroy_actor(a)
            borrados += 1
            log("SkySphere borrado: '%s' (competía con SkyAtmosphere)" % nombre)
    if borrados == 0:
        log("SkySphere: no hay (OK)")


def configurar_sol(P):
    s = P["sol"]
    a = obtener_o_crear(unreal.DirectionalLight, "ARTE_SolLuna")
    carpeta(a, "Ambiente")
    movible(a)
    yaw = yaw_desde_azimut(s["azimut"])
    # Pitch negativo = apunta hacia abajo. Elevación e => pitch -e.
    a.set_actor_rotation(unreal.Rotator(roll=0.0, pitch=-s["elevacion"], yaw=yaw), False)
    c = comp_de(a, unreal.DirectionalLightComponent)
    d = s["disco"]
    n = set_props(c, [
        ("intensity", s["lux"]),
        ("light_color", col(255, 255, 255)),
        ("use_temperature", True),
        ("temperature", s["temperatura"]),
        ("indirect_lighting_intensity", 1.0),           # físico: Lumen hace el rebote real
        ("atmosphere_sun_light", True),
        ("atmosphere_sun_light_index", 0),
        ("per_pixel_atmosphere_transmittance", True),   # degradé correcto del sol rasante sobre el terreno
        ("atmosphere_sun_disk_color_scale", lc(d, d, d)),
        ("light_source_angle", s["angulo_fuente"]),
        ("light_source_soft_angle", 0.0),
        ("cast_shadows", s["sombras"]),
        ("cast_dynamic_shadows", s["sombras"]),
        ("contact_shadow_length", s["contact_shadow"]),
        ("contact_shadow_length_in_ws", False),
        # Light shafts APAGADOS en todos los presets (crítica v1: pegaban el velo a la cámara en contraluz)
        ("enable_light_shaft_bloom", False),
        ("bloom_scale", 0.0),
        ("enable_light_shaft_occlusion", False),
        ("occlusion_mask_darkness", 0.0),
        ("cast_cloud_shadows", True),
        ("cloud_shadow_on_surface_strength", s["nube_sombra_superficie"]),
        ("cloud_shadow_on_atmosphere_strength", 0.5),
        ("cast_shadows_on_clouds", True),
        ("cast_shadows_on_atmosphere", False),          # caro y casi invisible con edificios bajos
        ("volumetric_scattering_intensity", s["scattering_vol"]),
        ("cast_volumetric_shadow", s["sombra_vol"]),
    ])
    sombra_7m = 7.0 / math.tan(math.radians(max(s["elevacion"], 1.0)))
    log("Sol/Luna: elev %.1f° azimut %.0f° (yaw UE %.1f°) | %.2f lux TOA | %.0f K | ángulo %.2f° | sombras %s | "
        "sombra de una casa de 7 m: %.1f m  (%d props OK)"
        % (s["elevacion"], s["azimut"], yaw, s["lux"], s["temperatura"], s["angulo_fuente"],
           s["sombras"], sombra_7m, n))
    for o in actores_de(unreal.DirectionalLight):
        if o == a:
            continue
        try:
            comp_de(o, unreal.DirectionalLightComponent).set_editor_property("atmosphere_sun_light", False)
            warn("DirectionalLight extra '%s': le saqué Atmosphere Sun Light" % o.get_actor_label())
        except Exception:  # noqa
            pass


def configurar_atmosfera(P):
    s = P["atmosfera"]
    a = obtener_o_crear(unreal.SkyAtmosphere, "ARTE_SkyAtmosphere")
    carpeta(a, "Ambiente")
    c = comp_de(a, unreal.SkyAtmosphereComponent)
    modo = enum_val("SkyAtmosphereTransformMode", "PLANET_TOP_AT_ABSOLUTE_WORLD_ORIGIN")
    pares = []
    if modo is not None:
        pares.append(("transform_mode", modo))   # suelo del planeta en Z=0 = suelo del barrio
    fc = s["factor_cielo"]
    pares += [
        ("bottom_radius", 6360.0),                       # Tierra (km)
        ("atmosphere_height", 60.0),                     # 60 km: cubre Rayleigh (H=8 km) y la capa de ozono (10-40 km)
        ("ground_albedo", col(105, 105, 103)),           # suelo urbano ~0.14 lineal, NEUTRO (antes tiraba a marrón)
        ("multi_scattering_factor", 1.0),
        # Rayleigh físico (aire limpio): lo que pone el celeste
        ("rayleigh_scattering_scale", 0.0331),
        ("rayleigh_exponential_distribution", 8.0),
        # Mie: aerosoles húmedos y urbanos del AMBA
        ("mie_scattering_scale", s["mie_scat"] * BRUMA_MULT),
        ("mie_scattering", lc(1, 1, 1)),
        ("mie_absorption_scale", s["mie_abs"] * BRUMA_MULT),
        ("mie_absorption", lc(1, 1, 1)),
        ("mie_anisotropy", s["mie_aniso"]),
        ("mie_exponential_distribution", s["mie_dist_km"]),
        # Ozono físico: es el que da el azul del cielo en el crepúsculo
        ("other_absorption_scale", 0.001881),
        (("sky_and_aerial_perspective_luminance_factor", "sky_luminance_factor"), lc(fc[0], fc[1], fc[2])),
        (("aerial_pespective_view_distance_scale", "aerial_perspective_view_distance_scale"), s.get("dist_aerea", 1.0)),
        ("height_fog_contribution", 1.0),
    ]
    n = set_props(c, pares)
    aod = (s["mie_scat"] + s["mie_abs"]) * BRUMA_MULT * s["mie_dist_km"]
    log("SkyAtmosphere: Mie %.4f/km abs %.4f dist %.1f km g=%.2f => AOD~%.3f | factor cielo %s | persp. aérea x%.2f "
        "(%d props OK)" % (s["mie_scat"] * BRUMA_MULT, s["mie_abs"] * BRUMA_MULT, s["mie_dist_km"], s["mie_aniso"], aod,
                           fc, s.get("dist_aerea", 1.0), n))


def configurar_skylight(P):
    s = P["skylight"]
    a = obtener_o_crear(unreal.SkyLight, "ARTE_SkyLight")
    carpeta(a, "Ambiente")
    movible(a)
    c = comp_de(a, unreal.SkyLightComponent)
    n = set_props(c, [
        ("source_type", unreal.SkyLightSourceType.SLS_CAPTURED_SCENE),
        ("real_time_capture", True),
        ("intensity", s["intensidad"]),
        ("light_color", col(255, 255, 255)),
        ("lower_hemisphere_is_black", False),   # usa el suelo de la atmósfera (albedo urbano) en vez de negro
        ("cast_shadows", True),
        ("cast_volumetric_shadow", True),
        ("cloud_ambient_occlusion", True),
        ("cloud_ambient_occlusion_strength", s["cloud_ao"]),
        ("indirect_lighting_intensity", 1.0),
        ("volumetric_scattering_intensity", 1.0),
    ])
    try:
        c.recapture_sky()
    except Exception:  # noqa
        pass
    log("SkyLight: captura en tiempo real, intensidad %.2f, cloud AO %.2f (%d props OK)"
        % (s["intensidad"], s["cloud_ao"], n))


def _rango_slider(mat_base, nombre):
    """Intenta leer slider_min/slider_max del nodo ScalarParameter en el material de motor (solo informativo
    y para acotar). Devuelve (min, max) o None. No es API estable: todo en try."""
    try:
        base = mat_base.get_base_material()
        prefijo = base.get_path_name() if base else ""
        for expr in unreal.ObjectIterator(unreal.MaterialExpressionScalarParameter):
            try:
                if str(expr.get_editor_property("parameter_name")) != nombre:
                    continue
                ruta = expr.get_path_name()
                if not (prefijo and ruta.startswith(prefijo)) and "/Engine/EngineSky/" not in ruta:
                    continue
                mn = float(expr.get_editor_property("slider_min"))
                mx = float(expr.get_editor_property("slider_max"))
                if mx > mn:
                    return (mn, mx)
            except Exception:  # noqa
                continue
    except Exception:  # noqa
        pass
    return None


def _valor_defecto(mel, base, nombre):
    if isinstance(base, unreal.MaterialInstance):
        return float(mel.get_material_instance_scalar_parameter_value(base, nombre))
    return float(mel.get_material_default_scalar_parameter_value(base, nombre))


def _material_nubes(comp, s):
    """MI propio sobre el material de nubes de motor. Cobertura = bias absoluto por preset (acotado al slider del
    material si se puede leer, si no a [-1, 1]); densidad = multiplicador del default del motor (leído del padre,
    nunca de nuestro MI: así es idempotente)."""
    mel = unreal.MaterialEditingLibrary
    mat = comp.get_editor_property("material")
    if mat is None:
        warn("VolumetricCloud sin material: no ajusto cobertura")
        return
    ruta_mi = NUBES_MI_DIR + "/" + NUBES_MI_NOMBRE
    base = mat.get_editor_property("parent") if mat.get_path_name().startswith(ruta_mi) else mat
    if base is None:
        warn("MI de nubes sin padre; no ajusto cobertura")
        return
    if unreal.EditorAssetLibrary.does_asset_exist(ruta_mi):
        mi = unreal.EditorAssetLibrary.load_asset(ruta_mi)
    else:
        mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            NUBES_MI_NOMBRE, NUBES_MI_DIR, unreal.MaterialInstanceConstant,
            unreal.MaterialInstanceConstantFactoryNew())
        log("Creado %s (padre: %s)" % (ruta_mi, base.get_path_name()))
    mel.set_material_instance_parent(mi, base)
    nombres = [str(x) for x in mel.get_scalar_parameter_names(base)]
    log("Nubes: material base %s | escalares %s" % (base.get_path_name(), nombres))

    # --- cobertura
    p_cob = next((n for n in NUBES_PARAM_COBERTURA if n in nombres), None)
    if p_cob is None:
        p_cob = next((n for n in nombres if "coverage" in n.lower()), None)
    if p_cob is None:
        warn("Nubes: no encontré parámetro de cobertura entre %s" % nombres)
    else:
        try:
            defecto = _valor_defecto(mel, base, p_cob)
        except Exception:  # noqa
            defecto = float("nan")
        rango = _rango_slider(base, p_cob)
        lo, hi = rango if rango else NUBES_COBERTURA_RANGO_DEFECTO
        valor = min(max(s["cobertura"], lo), hi)
        mel.set_material_instance_scalar_parameter_value(mi, p_cob, valor)
        log("Nubes: '%s' (bias; + = más nubes) default %.2f -> %.2f | rango %s [%.2f, %.2f]"
            % (p_cob, defecto, valor, "del slider" if rango else "supuesto", lo, hi))

    # --- densidad
    p_den = next((n for n in NUBES_PARAM_DENSIDAD if n in nombres), None)
    if p_den is None:
        warn("Nubes: no encontré parámetro de densidad entre %s" % nombres)
    else:
        try:
            defecto = _valor_defecto(mel, base, p_den)
        except Exception:  # noqa
            defecto = 0.0
        if defecto > 0.0:
            valor = defecto * s["densidad_mult"]
            mel.set_material_instance_scalar_parameter_value(mi, p_den, valor)
            log("Nubes: '%s' default %.3f x %.2f -> %.3f" % (p_den, defecto, s["densidad_mult"], valor))
        else:
            warn("Nubes: '%s' default %.3f no positivo; no lo toco" % (p_den, defecto))

    mel.update_material_instance(mi)
    comp.set_editor_property("material", mi)


def configurar_nubes(P):
    s = P["nubes"]
    a = obtener_o_crear(unreal.VolumetricCloud, "ARTE_VolumetricCloud")
    carpeta(a, "Ambiente")
    c = comp_de(a, unreal.VolumetricCloudComponent)
    n = set_props(c, [
        ("layer_bottom_altitude", s["base_km"]),
        ("layer_height", s["espesor_km"]),
        ("view_sample_count_scale", 0.75),                  # nubes lejanas: -25% muestras, imperceptible a 60 fps
        ("shadow_view_sample_count_scale", 0.5),
        ("sky_light_cloud_bottom_occlusion", s["oclusion_base"]),
        ("use_per_sample_atmospheric_light_transmittance", s["transmitancia_por_muestra"]),
    ])
    # Muestras de la captura del SkyLight: la propiedad del pase v1 no existe en 5.8. La doc la llama
    # "Reflection View Sample Count Scale Value"; se intenta sin contar como fallo (el tope real lo pone
    # r.VolumetricCloud.ReflectionRaySampleMaxCount en escalabilidad).
    if set_prop_opcional(c, "reflection_view_sample_count_scale_value", 0.25):
        log("VolumetricCloud: muestras de reflejo/captura x0.25")
    set_prop_opcional(c, "shadow_reflection_view_sample_count_scale_value", 0.25)
    log("VolumetricCloud: base %.1f km, espesor %.1f km (%d props OK)" % (s["base_km"], s["espesor_km"], n))
    try:
        _material_nubes(c, s)
    except Exception as e:  # noqa
        err("Material de nubes: %s" % e)


def configurar_niebla(P):
    s = P["niebla"]
    atm_afecta = cvar_int("r.SupportSkyAtmosphereAffectsHeightFog") == 1
    log("Niebla: r.SupportSkyAtmosphereAffectsHeightFog=%s" % atm_afecta)
    if not atm_afecta:
        warn("La atmósfera NO alimenta la niebla todavía (falta el ini + reinicio). Uso color de niebla de respaldo; "
             "volvé a correr el script después de reiniciar.")
    inscat = s["inscat_con_atm"] if atm_afecta else s["inscat_sin_atm"]
    dirinscat = s.get("dir_inscat_con_atm", (0.0, 0.0, 0.0)) if atm_afecta else s["dir_inscat_sin_atm"]

    a = obtener_o_crear(unreal.ExponentialHeightFog, "ARTE_HeightFog")
    carpeta(a, "Ambiente")
    loc = a.get_actor_location()
    a.set_actor_location(unreal.Vector(loc.x, loc.y, 0.0), False, False)   # la densidad base se mide desde Z=0 (suelo)
    c = comp_de(a, unreal.ExponentialHeightFogComponent)
    n = set_props(c, [
        ("fog_density", s["densidad"]),
        ("fog_height_falloff", s["caida"]),
        ("start_distance", s["inicio_cm"]),          # no ensuciar al personaje ni la cuadra inmediata
        ("fog_max_opacity", s["opacidad_max"]),
        # 0 = la niebla también tiñe el cielo. Con densidad baja y caída 0.35 solo blanquea el horizonte
        # (opacidad al cenit ~1%, a 5° ~11%), y de noche es el resplandor naranja de la ciudad.
        ("fog_cutoff_distance", 0.0),
        (("fog_inscattering_luminance", "fog_inscattering_color"), lc(*inscat)),
        (("directional_inscattering_luminance", "directional_inscattering_color"), lc(*dirinscat)),
        ("directional_inscattering_exponent", s.get("dir_exp", 8.0)),
        ("directional_inscattering_start_distance", s.get("dir_inicio_cm", 5000.0)),
        ("enable_volumetric_fog", s["volumetrica"]),
        ("volumetric_fog_scattering_distribution", s["vol_dist"]),
        ("volumetric_fog_albedo", col(*s["vol_albedo"])),
        ("volumetric_fog_extinction_scale", s["vol_extincion"]),
        ("volumetric_fog_distance", s["vol_distancia_cm"]),
        ("volumetric_fog_start_distance", s["vol_inicio_cm"]),   # v1 = 0: el velo nacía en la cámara
    ])
    set_prop_opcional(c, "volumetric_fog_near_fade_in_distance", 500.0)
    # v4: tinte del aporte de la atmósfera a la niebla (UE5: SkyAtmosphereAmbientContributionColorScale)
    ce = s.get("cielo_amb_escala", (1.0, 1.0, 1.0))
    set_prop_opcional(c, "sky_atmosphere_ambient_contribution_color_scale", lc(*ce))
    # Segunda capa: neblina rasante (solo nublado; en los demás queda en 0)
    try:
        d = c.get_editor_property("second_fog_data")
        d.set_editor_property("fog_density", s["densidad2"])
        d.set_editor_property("fog_height_falloff", s["caida2"])
        d.set_editor_property("fog_height_offset", 0.0)
        c.set_editor_property("second_fog_data", d)
        n += 1
    except Exception as e:  # noqa
        _FALLAS.append("ExponentialHeightFogComponent.second_fog_data")
        err("Fallo propiedad -> ExponentialHeightFogComponent.second_fog_data (struct ExponentialHeightFogData) :: %s" % e)
    log("HeightFog: densidad %.4f caída %.2f inicio %.0f cm | 2ª capa %.3f | inscattering %s | volumétrica %s "
        "(g %.2f, ext %.2f, %.0f-%.0f cm) (%d props OK)"
        % (s["densidad"], s["caida"], s["inicio_cm"], s["densidad2"], inscat, s["volumetrica"], s["vol_dist"],
           s["vol_extincion"], s["vol_inicio_cm"], s["vol_distancia_cm"], n))


def verificar_preexposicion(s):
    """Chequea que la ventana de exposición del preset caiga dentro del rango seguro de la luz cacheada."""
    n, fuente = None, None
    for cv in PREEXP_CVARS:
        v = cvar_float(cv)
        if v is not None and v != 0.0:
            n, fuente = v, cv
            break
    if n is None:
        n, fuente = PREEXP_DEFECTO, "default supuesto"
        warn("No pude leer %s; asumo %.0f. Poné r.EyeAdaptation.CachedLightingPreExposure=10 en DefaultEngine.ini"
             % (" / ".join(PREEXP_CVARS), PREEXP_DEFECTO))
    lo, hi = n - PREEXP_ABAJO, n + PREEXP_ARRIBA
    b = abs(s["ev_bias"])
    a_min = s["ev_min"] - b + EV_A_EXPOSICION
    a_max = s["ev_max"] + b + EV_A_EXPOSICION
    if a_min < lo + MARGEN_EV or a_max > hi - MARGEN_EV:
        warn("Exposición del preset [%.2f, %.2f] (en unidades del aviso) FUERA del rango seguro [%.1f, %.1f] "
             "(pre-exposición %.1f, %s). La luz cacheada de Lumen/SkyLight se va a recortar."
             % (a_min, a_max, lo, hi, n, fuente))
    else:
        log("Pre-exposición %.1f (%s): rango seguro ~[%.1f, %.1f]; preset [%.2f, %.2f] OK"
            % (n, fuente, lo, hi, a_min, a_max))


def configurar_postproceso(P, world):
    s = P["post"]
    ppv = None
    for a in actores_de(unreal.PostProcessVolume):
        if a.get_actor_label() == PPV_LABEL:
            ppv = a
            break
    if ppv is None:
        ppv = EAS.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
        ppv.set_actor_label(PPV_LABEL)
        log("PostProcessVolume creado: %s" % PPV_LABEL)
    else:
        log("PostProcessVolume existente: %s" % PPV_LABEL)
    carpeta(ppv, "Ambiente")
    set_props(ppv, [("unbound", True), ("enabled", True), ("priority", 0.0), ("blend_weight", 1.0)])
    otros = [a for a in actores_de(unreal.PostProcessVolume) if a != ppv]
    if otros:
        warn("Hay %d PostProcessVolume más: pueden pisar estos valores (%s)"
             % (len(otros), [o.get_actor_label() for o in otros]))

    st = ppv.get_editor_property("settings")

    # ---------------- Exposición: histograma con rango estrecho por preset y adaptación lenta
    extendido = cvar_int("r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange") == 1
    if extendido:
        ev_min, ev_max = s["ev_min"], s["ev_max"]
    else:
        # sin rango extendido los min/max son luminancias promedio: L = 1.2 * 2^EV100
        warn("ExtendDefaultLuminanceRange=0: convierto EV100 a luminancia. Volvé a correr tras el ini + reinicio.")
        ev_min, ev_max = 1.2 * 2.0 ** s["ev_min"], 1.2 * 2.0 ** s["ev_max"]
    verificar_preexposicion(s)
    pp(st, "auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM)
    pp(st, "auto_exposure_min_brightness", ev_min)
    pp(st, "auto_exposure_max_brightness", ev_max)
    pp(st, "auto_exposure_bias", s["ev_bias"])
    pp(st, "auto_exposure_speed_up", 1.0)           # EV/s: entrar a la luz sin "golpe"
    pp(st, "auto_exposure_speed_down", 0.8)         # salir de la luz más lento todavía: que no respire
    pp(st, "auto_exposure_low_percent", 50.0)       # ignora la mitad más oscura (zaguanes, bajo autos)
    pp(st, "auto_exposure_high_percent", 92.0)      # ignora cielo/sol/cabezas de luminaria/reflejos
    pp(st, "auto_exposure_apply_physical_camera_exposure", False)
    if extendido:
        pp(st, "histogram_log_min", -6.0)
        pp(st, "histogram_log_max", 18.0)

    # ---------------- Exposición local: LA herramienta de legibilidad de gameplay.
    # < 1 comprime el contraste de sombras/altas alrededor de la exposición global: un jugador en la sombra
    # de una fachada sube ~0.5 EV sin aplanar la imagen. Detail > 1 = "claridad": siluetas y bordes.
    pp(st, "local_exposure_highlight_contrast_scale", s["le_altas"])
    pp(st, "local_exposure_shadow_contrast_scale", s["le_sombras"])
    pp(st, "local_exposure_detail_strength", s["le_detalle"], opcional=True)

    # ---------------- Lumen (calidad alta, presupuesto 60 fps)
    pp(st, "dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN)
    pp(st, "reflection_method", unreal.ReflectionMethod.LUMEN)
    pp(st, "lumen_scene_lighting_quality", 1.5)     # estabilidad temporal de la escena Lumen (cables/rejas)
    pp(st, "lumen_scene_detail", 1.5)               # entran a la escena Lumen objetos chicos: autos, medidores, rejas
    pp(st, "lumen_scene_view_distance", 20000.0)    # 200 m: más allá manda la niebla
    pp(st, "lumen_final_gather_quality", 1.5)       # menos ruido bajo galerías/aleros
    pp(st, "lumen_max_trace_distance", 20000.0)
    pp(st, "lumen_skylight_leaking", s["skylight_leaking"])
    pp(st, "lumen_reflection_quality", 1.5)         # vidrios y charcos
    pp(st, "lumen_max_reflection_bounces", 1)
    pp(st, "lumen_max_roughness_to_trace_reflections", 0.45)
    pp(st, "lumen_front_layer_translucency_reflections", True)
    modo_rayo = enum_val("LumenRayLightingModeOverride", "SURFACE_CACHE", "DEFAULT")
    if modo_rayo is not None:
        pp(st, "lumen_ray_lighting_mode", modo_rayo)  # hit lighting no entra en 60 fps en una 5050
    else:
        warn("No existe el enum LumenRayLightingModeOverride; no seteo lumen_ray_lighting_mode")

    # ---------------- AO (respaldo SSAO cuando la escalabilidad apaga Lumen)
    pp(st, "ambient_occlusion_intensity", 0.5)
    pp(st, "ambient_occlusion_radius", 80.0)

    # ---------------- Bloom / lens
    pp(st, "bloom_method", unreal.BloomMethod.BM_SOG)
    pp(st, "bloom_intensity", s["bloom"])
    pp(st, "bloom_threshold", -1.0)                 # -1 = umbral físico (sin corte duro)
    pp(st, "lens_flare_intensity", 0.0)

    # ---------------- Tone mapping filmic (curva ACES de UE apenas más suave)
    pp(st, "film_slope", 0.86)
    pp(st, "film_toe", 0.55)
    pp(st, "film_shoulder", 0.28)
    pp(st, "film_black_clip", 0.0)
    pp(st, "film_white_clip", 0.04)
    pp(st, "expand_gamut", 0.75)

    # ---------------- Gradación (el calor lo pone la luz; la gradación solo separa cálido/frío)
    sat, con = s["saturacion"], s["contraste"]
    pp(st, "white_temp", s["white_temp"])
    pp(st, "color_saturation", v4(sat, sat, sat, 1.0))
    pp(st, "color_contrast", v4(con, con, con, 1.0))
    gs, ga, of = s["gain_sombras"], s["gain_altas"], s["offset"]
    pp(st, "color_gain_shadows", v4(gs[0], gs[1], gs[2], 1.0))      # sombras levemente frías
    pp(st, "color_gain_highlights", v4(ga[0], ga[1], ga[2], 1.0))   # altas apenas cálidas
    pp(st, "color_saturation_highlights", v4(0.97, 0.97, 0.97, 1.0))
    pp(st, "color_correction_shadows_max", 0.12)
    pp(st, "color_correction_highlights_min", 0.55)
    pp(st, "color_offset", v4(of[0], of[1], of[2], 0.0))           # piso de negro (solo noche)

    # ---------------- Lente / cámara
    pp(st, "vignette_intensity", 0.2)
    pp(st, ("film_grain_intensity", "grain_intensity"), 0.05)
    pp(st, "scene_fringe_intensity", 0.0)
    pp(st, "motion_blur_amount", 0.25)
    pp(st, "motion_blur_max", 2.0)
    pp(st, "motion_blur_target_fps", 30)

    ppv.set_editor_property("settings", st)

    # ---------------- Sharpen post-TSR (TSR al 67-75% ablanda rejas, cables y siluetas lejanas)
    consola(world, "r.Tonemapper.Sharpen %.2f" % SHARPEN)

    log("PostProcess: EV100 [%.1f, %.1f] bias %.1f | white %.0f K | sat %.2f | LE %.2f/%.2f | bloom %.2f"
        % (s["ev_min"], s["ev_max"], s["ev_bias"], s["white_temp"], sat, s["le_altas"], s["le_sombras"], s["bloom"]))


# =====================================================================================
# LUMINARIAS
# =====================================================================================
def _borrar_luces_propias():
    """Borra las SpotLight de luminarias de corridas anteriores y las 8 luces de prueba del pase v1."""
    nuevas, viejas = 0, 0
    for a in EAS.get_all_level_actors():
        etiqueta = a.get_actor_label()
        if etiqueta.startswith(LUZ_PREFIJO) or tiene_tag(a, LUZ_TAG):
            EAS.destroy_actor(a)
            nuevas += 1
        elif etiqueta.startswith(VIEJAS_PREFIJO) or tiene_tag(a, VIEJAS_TAG):
            EAS.destroy_actor(a)
            viejas += 1
    if viejas:
        log("Luces de prueba del pase v1 (FacadeTest) borradas: %d" % viejas)
    if nuevas:
        log("Luces de luminaria de la corrida anterior borradas: %d" % nuevas)


def _numero(etiqueta, defecto):
    try:
        return int(etiqueta.split("LUM_")[-1].split("_")[0])
    except Exception:  # noqa
        return defecto


def _es_led_neutro(p):
    return AVENIDA_X[0] <= p.x <= AVENIDA_X[1] or p.y >= AFUERA_NORTE_Y


def _celda(p):
    return (int(math.floor(p.x / CELDA_TRAMO_CM)), int(math.floor(p.y / CELDA_TRAMO_CM)))


def _hash_celda(c):
    v = (c[0] * 374761393 + c[1] * 668265263) & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    return v ^ (v >> 16)


def _celdas_sodio(posiciones):
    """Elige qué tramos (celdas de una manzana) siguen con sodio: PROPORCION_SODIO de las celdas de calle,
    ordenadas por un hash estable (misma semilla de mapa => misma mezcla en cada corrida)."""
    celdas = sorted({_celda(p) for p in posiciones if not _es_led_neutro(p)}, key=_hash_celda)
    n = int(round(len(celdas) * PROPORCION_SODIO))
    return set(celdas[:n])


def _tipo_luminaria(p, celdas_sodio):
    """Mezcla del conurbano real: la avenida y la estación ya tienen LED neutro; en las calles el recambio va
    por tramos, así que hay cuadras todavía naranjas de sodio y cuadras de LED cálido. Determinista."""
    if _es_led_neutro(p):
        return "led_neutro"
    return "sodio" if _celda(p) in celdas_sodio else "led_calido"


TIPOS_LUMINARIA = {
    #               temperatura, radio fuente (cm), largo fuente (cm), lux al pie
    "sodio":      dict(temp=2100.0, radio=10.0, largo=0.0, lux=LUX_PIE_CALLE),
    "led_calido": dict(temp=3000.0, radio=5.0, largo=40.0, lux=LUX_PIE_CALLE),
    "led_neutro": dict(temp=4000.0, radio=5.0, largo=50.0, lux=LUX_PIE_AVENIDA),
}


def configurar_luminarias(P):
    """Una SpotLight por cada TargetPoint con tag LUMINARIA (contrato v2). Solo en 'noche'; en los diurnos se borran.

    PRESUPUESTO (RTX 5050, 1440p TSR 67%, estimado; medir con `stat gpu` / `stat lightrendering`):
      * Barrio + Afuera según MAPA.md: ~90-110 luminarias (postes cada 25-30 m). 1 de cada SOMBRA_CADA=3 con
        sombra => ~30-35 con VSM local en el mapa entero.
      * En pantalla, vista típica de calle (visual <= 120 m): 8-14 luces, 3-5 con sombra; avenida: ~20 y ~7.
      * Sin sombra: ~0.02-0.04 ms c/u (deferred, radio 30 m) => ~0.4 ms.
      * Con sombra VSM (páginas cacheadas: geometría estática, luz quieta): ~0.15-0.25 ms c/u => ~0.8-1.2 ms.
      * Niebla volumétrica + inyección de luces (sombra volumétrica solo en las que tienen sombra): ~0.5 ms.
      * Lumen (iluminación directa de la surface cache para ~100 luces): ~0.3 ms.
      => Noche ~2-2.5 ms de luces locales. Se compensa con: niebla volumétrica apagada en 'tarde', luna sin
         sombras si hace falta (LUNA_SOMBRAS=False, ~1 ms), y SOMBRA_CADA=6 en escalabilidad Medio.
      * Si con 16 jugadores no entra: MegaLights (5.8) da sombras a todas con costo fijo; evaluarlo antes que
        bajar la cantidad de luminarias.
    """
    _borrar_luces_propias()
    if not P["luminarias"]:
        log("Luminarias: preset diurno, no se crean (de día están apagadas por fotocélula)")
        return

    tps = [a for a in actores_de(unreal.TargetPoint) if tiene_tag(a, LUM_TAG)]
    if not tps:
        warn("No hay TargetPoint con tag '%s' (contrato v2). Corré primero la geometría del mapa: "
             "la noche va a quedar solo con luna y cielo." % LUM_TAG)
        return
    tps.sort(key=lambda a: (_numero(a.get_actor_label(), 10 ** 6), a.get_actor_label()))

    unidades = enum_val("LightUnits", "CANDELAS")
    if unidades is None:
        raise RuntimeError("No existe unreal.LightUnits.CANDELAS")
    celdas_sodio = _celdas_sodio([tp.get_actor_location() for tp in tps])
    cuenta = {"sodio": 0, "led_calido": 0, "led_neutro": 0}
    con_sombra, mal_orientadas, alturas = 0, 0, []
    for k, tp in enumerate(tps):
        etiqueta_tp = tp.get_actor_label()
        num = _numero(etiqueta_tp, k)
        p = tp.get_actor_location()
        rot = tp.get_actor_rotation()
        fwd = tp.get_actor_forward_vector()
        if fwd.z > -0.7:     # el contrato dice "mirando hacia abajo"; si no, se fuerza a nadir
            mal_orientadas += 1
            rot = unreal.Rotator(roll=0.0, pitch=-90.0, yaw=rot.yaw)
            fwd = unreal.Vector(0.0, 0.0, -1.0)
        ubic = unreal.Vector(p.x + fwd.x * BAJAR_LUZ_CM, p.y + fwd.y * BAJAR_LUZ_CM, p.z + fwd.z * BAJAR_LUZ_CM)
        h_m = max(ubic.z / 100.0, 3.0)
        alturas.append(h_m)
        tipo = _tipo_luminaria(p, celdas_sodio)
        t = TIPOS_LUMINARIA[tipo]
        cuenta[tipo] += 1
        variacion = 0.92 + 0.08 * ((num * 37) % 3)     # 0.92 / 1.00 / 1.08: lámparas viejas y nuevas
        candelas = t["lux"] * h_m * h_m * variacion    # E al pie = I / h²  (I en cd, h en m)
        sombra = (k % SOMBRA_CADA == 0)
        con_sombra += int(sombra)

        a = EAS.spawn_actor_from_class(unreal.SpotLight, ubic, rot)
        a.set_actor_label("%s%03d_%s%s" % (LUZ_PREFIJO, num, tipo, "_S" if sombra else ""))
        carpeta(a, LUZ_CARPETA)
        try:
            a.set_editor_property("tags", [unreal.Name(LUZ_TAG), unreal.Name("src_" + etiqueta_tp)])
        except Exception:  # noqa
            pass
        movible(a)
        c = comp_de(a, unreal.SpotLightComponent)
        set_props(c, [
            ("intensity_units", unidades),
            ("intensity", candelas),
            ("use_temperature", True),
            ("temperature", t["temp"]),
            ("light_color", col(255, 255, 255)),
            ("use_inverse_squared_falloff", True),
            ("attenuation_radius", ATENUACION_CM),
            ("inner_cone_angle", CONO_INTERIOR),
            ("outer_cone_angle", CONO_EXTERIOR),
            ("source_radius", t["radio"]),
            ("soft_source_radius", 0.0),
            ("source_length", t["largo"]),
            ("cast_shadows", sombra),
            ("volumetric_scattering_intensity", 1.5),
            ("cast_volumetric_shadow", sombra),
            ("specular_scale", 1.0),
            ("indirect_lighting_intensity", 1.0),       # el rebote del charco en la fachada es relleno gratis
            ("max_draw_distance", DIST_DIBUJO_CM),
            ("max_distance_fade_range", DIST_FADE_CM),
        ])

    if mal_orientadas:
        warn("%d TargetPoint LUMINARIA no miraban hacia abajo: forcé nadir (avisar a geometría)" % mal_orientadas)
    h_media = sum(alturas) / len(alturas)
    log("Luminarias: %d SpotLight | con sombra %d (1 de cada %d) | sodio %d, LED 3000 K %d, LED 4000 K %d | "
        "altura media %.1f m | %.0f lux al pie (avenida %.0f) | cono %.0f°/%.0f° | radio %.0f m | dibujo %.0f m"
        % (len(tps), con_sombra, SOMBRA_CADA, cuenta["sodio"], cuenta["led_calido"], cuenta["led_neutro"],
           h_media, LUX_PIE_CALLE, LUX_PIE_AVENIDA, CONO_INTERIOR, CONO_EXTERIOR,
           ATENUACION_CM / 100.0, DIST_DIBUJO_CM / 100.0))
    if unreal.EditorAssetLibrary.does_asset_exist("/Game/Barrio/Art/Materials/MI_Emisivo_Calido"):
        log("MI_Emisivo_Calido existe (cabezas/ventanas): la iluminación no lo toca")


def guardar():
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    ok = les.save_current_level()
    ok2 = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)  # MI de nubes + actores externos (OFPA)
    if ok and ok2:
        log("Nivel y assets guardados")
    else:
        err("Guardado incompleto (save_current_level=%s, save_dirty_packages=%s)" % (ok, ok2))


# =====================================================================================
# MAIN
# =====================================================================================
def main():
    preset, origen = elegir_preset()
    if preset not in PRESETS:
        err("PRESET '%s' no existe. Opciones: %s" % (preset, list(PRESETS.keys())))
        return
    P = PRESETS[preset]
    log("===== setup_lighting v4: preset '%s' (elegido por %s) =====" % (preset, origen))
    try:
        world = asegurar_nivel()
    except Exception as e:  # noqa
        err("Nivel: %s" % e)
        return

    pasos = [
        ("Inventario", lambda: inventario()),
        ("SkySphere", lambda: quitar_skysphere()),
        ("Sol/Luna", lambda: configurar_sol(P)),
        ("SkyAtmosphere", lambda: configurar_atmosfera(P)),
        ("SkyLight", lambda: configurar_skylight(P)),
        ("VolumetricCloud", lambda: configurar_nubes(P)),
        ("HeightFog", lambda: configurar_niebla(P)),
        ("PostProcess", lambda: configurar_postproceso(P, world)),
        ("Luminarias", lambda: configurar_luminarias(P)),
    ]
    bloques_fallidos = []
    with unreal.ScopedEditorTransaction("ARTE: ambiente %s" % preset):
        for nombre, fn in pasos:
            try:
                fn()
            except Exception as e:  # noqa
                bloques_fallidos.append(nombre)
                err("BLOQUE '%s' FALLÓ: %s" % (nombre, e))

    if GUARDAR:
        try:
            guardar()
        except Exception as e:  # noqa
            err("Guardar: %s" % e)

    if _OPCIONALES_AUSENTES:
        log("Opcionales que esta versión no tiene (no es error): %s" % ", ".join(_OPCIONALES_AUSENTES))
    if _FALLAS:
        err("Propiedades que fallaron (%d): %s" % (len(_FALLAS), ", ".join(_FALLAS)))
    if bloques_fallidos:
        err("Bloques con error: %s" % ", ".join(bloques_fallidos))
    log("AMBIENTE LISTO (%s)" % preset)


main()
