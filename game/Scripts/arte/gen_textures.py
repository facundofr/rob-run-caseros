#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de texturas PBR procedurales tileables para "Barrio" (Caseros, conurbano bonaerense).

Salida (2048x2048, sin costura):
    textures/<Set>/T_<Set>_BC.png   base color sRGB
    textures/<Set>/T_<Set>_N.png    normal convención DirectX (verde invertido, Y-)
    textures/<Set>/T_<Set>_ORM.png  R=oclusión, G=rugosidad, B=metálico (lineal)
    textures/preview_contact_sheet.jpg

Flujo por material:
    1) layout físico en cm (según el tamaño real que cubre la textura, ver CONVENCIONES.md)
    2) mapa de altura en cm (todo periódico: ruido espectral FFT, Worley periódico, wrap)
    3) normal (Sobel con escala física cm/px), oclusión por cavidades multiescala
    4) color y rugosidad correlacionados con altura/cavidad/bordes

Uso:
    python3 gen_textures.py                 # todos los sets
    python3 gen_textures.py Ladrillo Chapa  # sólo algunos
    python3 gen_textures.py --jobs 1        # sin paralelismo
    python3 gen_textures.py Carteles        # v4: sólo los atlas de carteles con texto (ver gen_carteles)
Dependencias: numpy, scipy, Pillow.
"""
import os
import sys
import time
import argparse

import numpy as np
import scipy.fft as sfft
import scipy.ndimage as ndi
from PIL import Image, ImageDraw, ImageFont

N = 2048
F = np.float32
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(ROOT, 'textures')

# Tamaño real (cm) que cubre cada textura — CONVENCIONES.md
TILE_CM = {
    'Revoque': 200.0, 'Ladrillo': 240.0, 'Baldosa': 80.0, 'Asfalto': 400.0,
    'Hormigon': 150.0, 'Chapa': 100.0, 'Madera': 120.0, 'Tejas': 120.0,
    'MetalPintado': 100.0, 'PiedraLaja': 150.0,
    # v2: sets nuevos para el mapa jugable
    'Corteza': 120.0, 'Pasto': 200.0, 'Tierra': 200.0, 'Balasto': 120.0, 'Riel': 80.0, 'Follaje': 150.0,
}
# v2: Ladrillo pasa de 120 a 240 cm (36 hiladas x 10 ladrillos): la repetición cada 1,32 m se notaba;
# a 240 cm (264 con el TileSizeCM de la instancia) baja a ~770 px/m, densidad de sobra para tercera persona.
SETS = list(TILE_CM.keys())


def log(msg):
    print(f'[TEXTURAS] {msg}', flush=True)


# ----------------------------------------------------------------------------
# Utilidades básicas
# ----------------------------------------------------------------------------
_cache = {}


def grid():
    """Coordenadas de píxel (yy, xx) float32."""
    if 'g' not in _cache:
        yy, xx = np.mgrid[0:N, 0:N].astype(F)
        _cache['g'] = (yy, xx)
    return _cache['g']


def kgrid():
    """Frecuencias enteras (ciclos por textura) para rfft2: garantizan periodicidad."""
    if 'k' not in _cache:
        ky = (sfft.fftfreq(N) * N).astype(F)[:, None]
        kx = (sfft.rfftfreq(N) * N).astype(F)[None, :]
        _cache['k'] = (ky, kx)
    return _cache['k']


def clamp(a, lo=0.0, hi=1.0):
    return np.clip(a, lo, hi)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def rgb(r, g, b):
    return np.array([r, g, b], dtype=F) / 255.0


def mixc(base, col, m):
    """Mezcla un color (3,) o imagen (H,W,3) sobre base con máscara m (H,W)."""
    m = np.asarray(m, dtype=F)
    if m.ndim == 2:
        m = m[..., None]
    return base * (1.0 - m) + col * m


def wrapd(a, c, n=N):
    """Distancia periódica con signo de la coordenada a al centro c."""
    return (a - c + n * 0.5) % n - n * 0.5


def noise(rng, kmin=1.0, kmax=1024.0, beta=1.0, ex=1.0, ey=1.0, angle=0.0):
    """Ruido espectral periódico normalizado (media 0, desvío 1).
    kmin/kmax: banda en ciclos por textura. beta: pendiente de amplitud (k^-beta).
    ex/ey > 1 alargan los rasgos en x / y (anisotropía). angle rota la anisotropía."""
    ky, kx = kgrid()
    if angle:
        c, s = np.cos(angle), np.sin(angle)
        kx2 = kx * c - ky * s
        ky2 = kx * s + ky * c
    else:
        kx2, ky2 = kx, ky
    k = np.sqrt((kx2 * ex) ** 2 + (ky2 * ey) ** 2).astype(F)
    k[0, 0] = 1.0
    amp = k ** (-beta) * np.exp(-(k / kmax) ** 2) * (1.0 - np.exp(-(k / kmin) ** 2))
    amp[0, 0] = 0.0
    w = rng.standard_normal((N, N), dtype=F)
    W = sfft.rfft2(w, workers=-1)
    W *= amp
    out = sfft.irfft2(W, s=(N, N), workers=-1).astype(F)
    out -= out.mean()
    out /= (out.std() + 1e-8)
    return out


def gblur(a, sigma_px):
    """Desenfoque gaussiano periódico (FFT para sigmas grandes)."""
    if sigma_px <= 0:
        return a
    if a.ndim == 3:
        return np.stack([gblur(a[..., i], sigma_px) for i in range(a.shape[2])], -1)
    if sigma_px < 5:
        return ndi.gaussian_filter(a, sigma_px, mode='wrap').astype(F)
    ky, kx = kgrid()
    g = np.exp(-2.0 * np.pi ** 2 * sigma_px ** 2 * ((ky / N) ** 2 + (kx / N) ** 2)).astype(F)
    A = sfft.rfft2(a, workers=-1)
    A *= g
    return sfft.irfft2(A, s=(N, N), workers=-1).astype(F)


def worley(rng, C, jitter=0.9, xs=None, ys=None):
    """Worley/Voronoi periódico en grilla C x C (C celdas por textura).
    Devuelve F1, F2 (en unidades de celda) e id de la celda más cercana."""
    yy, xx = grid()
    if xs is None:
        xs, ys = xx, yy
    gx = xs * (C / N)
    gy = ys * (C / N)
    ix = np.floor(gx).astype(np.int32)
    iy = np.floor(gy).astype(np.int32)
    fx = (gx - ix).astype(F)
    fy = (gy - iy).astype(F)
    jx = (rng.random(C * C).astype(F) * jitter + (1 - jitter) * 0.5)
    jy = (rng.random(C * C).astype(F) * jitter + (1 - jitter) * 0.5)
    F1 = np.full((N, N), 9.0, F)
    F2 = np.full((N, N), 9.0, F)
    ID = np.zeros((N, N), np.int32)
    for dy in (-1, 0, 1):
        cy = (iy + dy) % C
        for dx in (-1, 0, 1):
            cx = (ix + dx) % C
            cid = cy * C + cx
            px = dx + jx[cid] - fx
            py = dy + jy[cid] - fy
            d = px * px + py * py
            closer = d < F1
            F2 = np.where(closer, F1, np.minimum(F2, d))
            ID = np.where(closer, cid, ID)
            F1 = np.where(closer, d, F1)
    return np.sqrt(F1), np.sqrt(F2), ID


def warp(a, dx, dy, order=1):
    """Deformación de dominio periódica (dx, dy en píxeles)."""
    yy, xx = grid()
    return ndi.map_coordinates(a, [yy + dy, xx + dx], order=order, mode='grid-wrap').astype(F)


def draw_polylines(lines, width=2, ss=1):
    """Rasteriza polilíneas (en píxeles) con wrap periódico. Devuelve máscara float 0..1."""
    img = Image.new('L', (N, N), 0)
    dr = ImageDraw.Draw(img)
    for pts, wdt in lines:
        p = [(float(x), float(y)) for x, y in pts]
        for ox in (-N, 0, N):
            for oy in (-N, 0, N):
                q = [(x + ox, y + oy) for x, y in p]
                xs_ = [a for a, _ in q]
                ys_ = [b for _, b in q]
                if max(xs_) < -10 or min(xs_) > N + 10 or max(ys_) < -10 or min(ys_) > N + 10:
                    continue
                dr.line(q, fill=255, width=max(1, int(round(wdt))), joint='curve')
    return np.asarray(img, dtype=F) / 255.0


def crack_path(rng, start, length_px, step_px, angle, jitter=0.35, drift=0.0):
    """Camino aleatorio para fisuras (puntos en píxeles)."""
    pts = [np.array(start, dtype=float)]
    a = angle
    n = max(2, int(length_px / step_px))
    for _ in range(n):
        a += rng.normal(0, jitter) + drift
        a = angle + np.clip(a - angle, -0.9, 0.9)
        st = step_px * rng.uniform(0.6, 1.4)
        pts.append(pts[-1] + st * np.array([np.cos(a), np.sin(a)]))
    return np.array(pts)


def normal_dx(h, px_cm, strength=1.0):
    """Normal tangente en convención DirectX a partir de altura en cm.
    n = (-dh/dx, -dh/dfila, 1): verde claro hacia abajo de cada relieve (Y-)."""
    gx = ndi.sobel(h, axis=1, mode='wrap').astype(F) / (8.0 * px_cm)
    gy = ndi.sobel(h, axis=0, mode='wrap').astype(F) / (8.0 * px_cm)
    nx = -gx * strength
    ny = -gy * strength
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1.0)
    return np.stack([nx * inv, ny * inv, inv], -1)


def cavity_ao(h, px_cm, radii_cm, strength=1.0):
    """Oclusión ambiental aproximada por cavidades multiescala (periódica).
    Para cada radio compara la altura local contra el promedio del entorno."""
    ao = np.ones_like(h)
    for r in radii_cm:
        b = gblur(h, r / px_cm)
        occ = np.clip((b - h) / r, 0.0, None)
        ao *= np.exp(-strength * 2.0 * occ)
    return ao.astype(F)


def convexity(h, px_cm, r_cm):
    """Positivo en aristas/convexidades (para desgaste de bordes)."""
    return (h - gblur(h, r_cm / px_cm)).astype(F)


def to8(a):
    return (np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)


def save_set(name, bc, h, px_cm, nstrength, ao, rough, metal):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    n = normal_dx(h, px_cm, nstrength)
    Image.fromarray(to8(bc)).save(os.path.join(d, f'T_{name}_BC.png'), compress_level=6)
    Image.fromarray(to8(n * 0.5 + 0.5)).save(os.path.join(d, f'T_{name}_N.png'), compress_level=6)
    orm = np.stack([ao, rough, metal], -1)
    Image.fromarray(to8(orm)).save(os.path.join(d, f'T_{name}_ORM.png'), compress_level=6)


def per_cell(rng, n, lo, hi):
    return rng.uniform(lo, hi, n).astype(F)


# ----------------------------------------------------------------------------
# LADRILLO — ladrillo común argentino, aparejo trabado (soga), junta tomada
# ----------------------------------------------------------------------------
def gen_ladrillo(seed=101):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Ladrillo']
    px = T / N
    yy, xx = grid()
    S = T / 120.0                     # factor de escala: las bandas de ruido se dan por cada 120 cm
    K = lambda k: min(1024.0, k * S)  # ciclos por textura conservando el tamaño físico de los rasgos
    C = lambda c: int(round(c * S))   # celdas de Worley idem
    # hiladas de 6,67 cm (ladrillo 5,4 + junta 1,3); 5 ladrillos por hilada cada 120 cm (módulo 24 cm)
    rows, nb = int(round(18 * S)), int(round(5 * S))
    course = T / rows
    mod = T / nb
    # bordes levemente irregulares (ladrillo de horno, no prensado)
    wx = noise(rng, K(15), K(300), 1.2) * 0.07 + noise(rng, K(150), 1024, 0.6) * 0.025
    wy = noise(rng, K(15), K(300), 1.2) * 0.07 + noise(rng, K(150), 1024, 0.6) * 0.025
    X = xx * px + wx
    Y = yy * px + wy
    rowf = np.floor(Y / course)
    row = (rowf.astype(np.int32)) % rows
    v = (Y - rowf * course).astype(F)
    u = np.zeros((N, N), F)
    bw = np.zeros((N, N), F)
    bid = np.zeros((N, N), np.int32)
    for r in range(rows):
        off = (r % 2) * mod * 0.5 + rng.uniform(-1.6, 1.6)
        L = mod + rng.normal(0, 0.7, nb)
        L *= T / L.sum()
        cum = np.concatenate([[0.0], np.cumsum(L)])
        m = row == r
        xs = (X[m] - off) % T
        idx = np.clip(np.searchsorted(cum, xs, side='right') - 1, 0, nb - 1)
        u[m] = xs - cum[idx]
        bw[m] = L[idx]
        bid[m] = r * nb + idx
    nbr = rows * nb
    jl = (0.62 + rng.normal(0, 0.12, nbr)).astype(F)[bid]
    jr = (0.62 + rng.normal(0, 0.12, nbr)).astype(F)[bid]
    jt = (0.62 + rng.normal(0, 0.10, nbr)).astype(F)[bid]
    jb = (0.62 + rng.normal(0, 0.10, nbr)).astype(F)[bid]
    bh = course - jt - jb
    lu = u - jl
    lv = v - jt
    bl = bw - jl - jr
    d = np.minimum(np.minimum(lu, bl - lu), np.minimum(lv, bh - lv))  # distancia al borde (cm)

    # --- altura del ladrillo
    R = per_cell(rng, nbr, 0.2, 0.45)[bid]                   # radio de arista
    dd = np.clip(d, 0, None)
    edge = np.where(dd >= R, 0.0, -R + np.sqrt(np.clip(R * R - (R - dd) ** 2, 0, None)))
    tilt_x = rng.normal(0, 0.006, nbr).astype(F)[bid]
    tilt_y = rng.normal(0, 0.012, nbr).astype(F)[bid]
    base = rng.normal(0, 0.07, nbr).astype(F)[bid]
    face = base + (lu - bl * 0.5) * tilt_x + (lv - bh * 0.5) * tilt_y
    face += noise(rng, K(6), K(120), 1.4) * 0.05                        # alabeo del ladrillo
    face += noise(rng, K(80), 1024, 0.7) * 0.018                     # textura de arena
    # poros/picaduras
    cp = C(130)
    F1, F2, pid = worley(rng, cp)
    pr = per_cell(rng, cp * cp, 0.04, 0.22)[pid]
    pk = (rng.random(cp * cp) < 0.18)[pid]
    pits = np.where(pk, np.sqrt(clamp(1 - (F1 / pr) ** 2)), 0) * 0.06
    face -= pits
    # descascarados en aristas
    chipn = noise(rng, K(25), K(500), 1.1)
    chipp = per_cell(rng, nbr, 0.0, 1.0)[bid]
    chip_depth = np.clip(chipn - 1.4 + chipp * 0.9, 0, None) * 0.9
    chip = sstep(0.0, 0.08, chip_depth - d)
    hb = face + edge
    hb = np.where(d > 0, hb, -3.0)
    hb = hb - chip * (0.18 + 0.25 * np.clip(chip_depth - d, 0, 0.6))
    # --- mortero (junta rehundida, granulosa, con rebabas)
    hm = -0.42 + noise(rng, K(4), K(200), 1.0) * 0.07 + noise(rng, K(250), 1024, 0.3) * 0.035
    cg = min(C(520), 900)               # granos de arena: a 240 cm quedan en ~2 px, se limita
    Fg, _, gid = worley(rng, cg)
    hm += np.sqrt(clamp(1 - (Fg / 0.45) ** 2)) * 0.05 * (rng.random(cg * cg) < 0.5)[gid]
    smear = sstep(0.9, 1.6, noise(rng, K(4), K(60), 1.4)) * sstep(0.7, 0.0, d)
    hm = hm + gblur(smear, 2.0 / S) * 0.5
    h = np.maximum(hb, hm).astype(F)
    bmask = sstep(-0.02, 0.04, hb - hm)

    ao = cavity_ao(h, px, [0.25, 0.8, 2.5], 0.8)
    conv = convexity(h, px, 0.3)

    # --- color (ladrillo común de horno: naranja-rojizo, con piezas requemadas)
    pal = np.array([rgb(178, 90, 62), rgb(196, 110, 74), rgb(160, 74, 52), rgb(124, 60, 45),
                    rgb(186, 100, 70), rgb(150, 82, 62), rgb(204, 126, 88)])
    wts = np.array([0.26, 0.18, 0.2, 0.07, 0.15, 0.07, 0.07])
    choice = rng.choice(len(pal), nbr, p=wts)
    bcol = pal[choice] * rng.uniform(0.93, 1.07, (nbr, 1)).astype(F)
    bcol[:, 1] *= rng.uniform(0.95, 1.05, nbr)
    col = bcol[bid]
    mott = noise(rng, K(6), K(250), 1.0)
    col = col * (1 + 0.07 * mott[..., None])
    grad = per_cell(rng, nbr, -0.18, 0.18)[bid]
    col = col * (1 + grad * (lu / np.maximum(bl, 1) - 0.5))[..., None]
    # flameado oscuro en algunos ladrillos
    flash = sstep(0.2, 1.3, noise(rng, K(8), K(120), 1.2)) * (rng.random(nbr) < 0.22)[bid]
    col = mixc(col, rgb(78, 44, 36), flash * 0.55)
    # pintitas de cal y de hierro
    cs_ = C(230)
    Fs, _, sid = worley(rng, cs_)
    lime = (rng.random(cs_ * cs_) < 0.04)[sid] * sstep(0.22, 0.1, Fs)
    iron = (rng.random(cs_ * cs_) < 0.06)[sid] * sstep(0.18, 0.08, Fs)
    col = mixc(col, rgb(214, 190, 158), lime * 0.8)
    col = mixc(col, rgb(70, 38, 30), iron * 0.6)
    col = mixc(col, rgb(204, 124, 88), chip * 0.6)                 # rotura: cerámica más fresca
    col = col * (0.85 + 0.15 * ao)[..., None]
    col = col * (1 + np.clip(conv, 0, 0.2)[..., None] * 0.6)
    # mortero (cemento-cal-arena, gris claro algo cálido)
    mcol = rgb(178, 172, 160) * (1 + 0.06 * noise(rng, K(3), K(120), 1.0))[..., None]
    mcol = mcol * (1 + 0.08 * noise(rng, K(300), 1024, 0.2))[..., None]
    mcol = mcol * (0.62 + 0.38 * ao)[..., None]
    mcol = mixc(mcol, rgb(110, 104, 96), sstep(0.3, 1.5, noise(rng, K(2), K(40), 1.3)) * 0.35)
    bc = mixc(mcol, col, bmask)
    # macro: hollín y eflorescencias
    macro = noise(rng, 1, K(6), 1.5)
    bc = bc * (1 + 0.05 * macro)[..., None]
    eff = sstep(0.8, 2.0, noise(rng, K(2), K(30), 1.3)) * sstep(-0.2, 0.8, noise(rng, K(30), K(300), 1.0))
    bc = mixc(bc, rgb(205, 196, 186), eff * 0.22)
    bc = clamp(bc)

    rough = np.where(bmask > 0.5, 0.85, 0.93) + 0.03 * noise(rng, K(20), K(600), 0.8)
    rough += pits * 0.4 + chip * 0.03 + eff * 0.04 + (1 - ao) * 0.04
    rough = clamp(rough, 0.78, 0.97)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# REVOQUE — revoque grueso salpicado pintado, gris claro neutro (se tiñe)
# ----------------------------------------------------------------------------
def gen_revoque(seed=202):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Revoque']
    px = T / N
    h = noise(rng, 1, 25, 1.6) * 0.22                    # planitud del fratacho
    h += noise(rng, 20, 200, 1.0) * 0.025
    # parches reparados con revoque más fino
    patch_n = noise(rng, 1, 6, 1.7)
    patch = sstep(-0.2, 1.8, patch_n) * 0.6        # zonas de salpicado más fino (variación suave)
    spl = np.zeros((N, N), F)
    acc = np.zeros((N, N), F)
    for C, rmin, rmax, amp, frac in [(70, 0.18, 0.36, 0.30, 0.25),
                                     (160, 0.22, 0.46, 0.24, 0.65),
                                     (330, 0.25, 0.5, 0.14, 0.85),
                                     (600, 0.25, 0.5, 0.06, 0.9)]:
        F1, F2, cid = worley(rng, C)
        r = per_cell(rng, C * C, rmin, rmax)[cid]
        keep = (rng.random(C * C) < frac)[cid]
        a = amp * per_cell(rng, C * C, 0.5, 1.2)[cid]
        t = clamp(1 - (F1 / r) ** 2)
        blob = a * t ** 0.6 * keep
        spl = np.maximum(spl, blob)
        acc += blob
    spl = 0.7 * spl + 0.3 * acc
    # gotas irregulares (no círculos)
    spl = warp(spl, noise(rng, 60, 600, 0.8) * 2.2, noise(rng, 60, 600, 0.8) * 2.2)
    spl = gblur(spl, 0.6)                                 # la pintura redondea todo
    h += spl * (1 - 0.65 * patch)
    h += noise(rng, 300, 1024, 0.3) * 0.006 * (1 - 0.5 * patch)
    # microfisuras (craquelado) en una zona
    w1 = noise(rng, 4, 60, 1.2) * 6
    w2 = noise(rng, 4, 60, 1.2) * 6
    Fa, Fb, _ = worley(rng, 9)
    edge = warp(Fb - Fa, w1, w2)
    creg = sstep(0.5, 1.2, noise(rng, 1, 5, 1.6))
    crack = sstep(0.012, 0.0, edge) * creg
    crack *= sstep(-0.3, 0.6, noise(rng, 6, 60, 1.0))
    h -= crack * 0.12
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.15, 0.6, 3.0], 1.4)
    conv = convexity(h, px, 0.4)

    base = 0.83
    val = base + 0.02 * noise(rng, 1, 8, 1.5) + 0.008 * noise(rng, 8, 120, 1.0)
    val += 0.01 * patch
    val += np.clip(conv, 0, 0.1) * 0.25
    # suciedad en cavidades (gris apenas cálido) y chorreadas de lluvia verticales
    dirt = clamp((1 - ao) * 1.4)
    streak = sstep(0.6, 1.8, noise(rng, 2, 80, 1.0, ey=8.0)) * sstep(-0.2, 0.9, noise(rng, 1, 6, 1.5))
    val = val * (1 - 0.16 * dirt) * (1 - 0.05 * streak) * (1 - 0.3 * crack)
    bc = np.stack([val, val * 0.995, val * 0.985], -1)
    bc = mixc(bc, bc * rgb(240, 236, 228), clamp(dirt + streak * 0.5))
    bc = clamp(bc)

    rough = 0.9 + 0.015 * noise(rng, 10, 400, 0.8) - 0.025 * patch + 0.03 * dirt + 0.02 * streak
    rough = clamp(rough, 0.85, 0.96)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# BALDOSA — vereda de baldosas "vainilla" 20x20 de cemento gris
# ----------------------------------------------------------------------------
def gen_baldosa(seed=303):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Baldosa']
    px = T / N
    yy, xx = grid()
    nt = 4
    tsz = T / nt
    wx = noise(rng, 8, 200, 1.3) * 0.05
    wy = noise(rng, 8, 200, 1.3) * 0.05
    X = xx * px + wx
    Y = yy * px + wy
    tx = np.floor(X / tsz).astype(np.int32) % nt
    ty = np.floor(Y / tsz).astype(np.int32) % nt
    tid = ty * nt + tx
    lu = (X % tsz) - tsz * 0.5
    lv = (Y % tsz) - tsz * 0.5
    ntl = nt * nt
    # tipos: 0 vainilla, 1 vainilla rotada 90°, 2 parche de cemento, 3 vainilla partida, 4 esquina rota
    types = np.zeros(ntl, int)
    order = rng.permutation(ntl)
    types[order[0]] = 2
    types[order[1]] = 3
    types[order[2]] = 4
    types[order[3]] = 1
    T_ = types[tid]
    rot = T_ == 1
    au = np.where(rot, lv, lu)
    av = np.where(rot, -lu, lv)
    half = tsz * 0.5 - per_cell(rng, ntl, 0.12, 0.22)[tid]       # junta ~3 mm
    d = np.minimum(half - np.abs(lu), half - np.abs(lv))
    # perfil de canto
    R = 0.35
    dd = np.clip(d, 0, None)
    edge = np.where(dd >= R, 0.0, -R + np.sqrt(np.clip(R * R - (R - dd) ** 2, 0, None))) * 0.6
    tilt_u = rng.normal(0, 0.008, ntl).astype(F)[tid]
    tilt_v = rng.normal(0, 0.008, ntl).astype(F)[tid]
    zoff = rng.normal(0, 0.06, ntl).astype(F)[tid]
    face = zoff + lu * tilt_u + lv * tilt_v + noise(rng, 30, 1024, 0.9) * 0.012
    # vainillas en relieve: 6 filas x 4 barras por baldosa
    pitch_v, pitch_u = 3.0, 4.5
    iv = np.clip(np.round((av + 7.5) / pitch_v), 0, 5)
    cy = -7.5 + iv * pitch_v
    iu = np.clip(np.round((au + 6.75) / pitch_u), 0, 3)
    cx = -6.75 + iu * pitch_u
    hl, hw = 1.75, 0.62
    ddx = np.clip(np.abs(au - cx) - (hl - hw), 0, None)
    ddy = np.abs(av - cy)
    rr = np.sqrt(ddx ** 2 + ddy ** 2) / hw
    bar = np.sqrt(clamp(1 - rr ** 3)) * 0.3
    wearl = per_cell(rng, ntl, 0.17, 0.3)[tid] + noise(rng, 2, 40, 1.2) * 0.03
    bar_worn = np.minimum(bar, wearl)
    worn_top = sstep(-0.01, 0.0, bar - wearl) * (bar > 0.05)
    has_bars = (T_ != 2)
    face = face + np.where(has_bars, bar_worn, 0.0)
    # parche de cemento: llaneado, más bajo
    face = np.where(T_ == 2, face - 0.12 + noise(rng, 20, 400, 1.0) * 0.03, face)
    # baldosas partidas: fisura con un lado hundido
    ang = per_cell(rng, ntl, 0, np.pi)[tid]
    off = per_cell(rng, ntl, -4, 4)[tid]
    jag = noise(rng, 15, 250, 1.3) * 0.3
    sd = lu * np.cos(ang) + lv * np.sin(ang) - off + jag
    brk = (T_ == 3)
    crack = sstep(0.11, 0.02, np.abs(sd)) * brk
    sunk = (sd > 0) & brk
    face = face - sunk * (0.18 + 0.012 * np.abs(sd)) - crack * 0.5
    # esquina faltante
    cs = per_cell(rng, ntl, 0, 4).astype(int)[tid]
    sx = np.where(cs % 2 == 0, 1, -1)
    sy = np.where(cs // 2 == 0, 1, -1)
    corner = (lu * sx + lv * sy) - 12.5 + noise(rng, 20, 400, 1.2) * 0.6
    hole = sstep(-0.05, 0.05, corner) * (T_ == 4)
    hb = np.where(d > 0, face + edge, -3)
    # junta / tierra
    hj = -0.45 + noise(rng, 50, 1024, 0.5) * 0.05 + noise(rng, 5, 100, 1.0) * 0.06
    hfill = -0.35 + noise(rng, 60, 1024, 0.6) * 0.08
    hb = lerp(hb, hfill, hole)
    h = np.maximum(hb, hj).astype(F)
    # chicles/manchas redondas (levemente en relieve)
    gum = np.zeros((N, N), F)
    for _ in range(14):
        c = rng.uniform(0, N, 2)
        rad = rng.uniform(0.35, 0.9) / px
        dist = np.sqrt(wrapd(xx, c[0]) ** 2 + wrapd(yy, c[1]) ** 2) / rad
        gum = np.maximum(gum, sstep(1.0, 0.75, dist))
    h = (h + gum * 0.04).astype(F)
    tmask = sstep(-0.02, 0.03, hb - hj) * (1 - hole)

    ao = cavity_ao(h, px, [0.2, 0.7, 2.5], 1.0)
    ao = lerp(ao, np.maximum(ao, 0.55), hole)
    conv = convexity(h, px, 0.4)

    # color de baldosa: cemento gris con leve variación cálida por pieza
    tc = np.tile(rgb(170, 168, 160), (ntl, 1)) * rng.uniform(0.9, 1.07, (ntl, 1)).astype(F)
    tc[:, 2] *= rng.uniform(0.94, 1.02, ntl)
    tc[types == 2] = rgb(138, 137, 133)
    old = order[4]
    tc[old] = rgb(160, 152, 134)                       # una baldosa más vieja, apenas amarillenta
    col = tc[tid]
    col = col * (1 + 0.06 * noise(rng, 3, 120, 1.1)[..., None] + 0.05 * noise(rng, 200, 1024, 0.3)[..., None])
    col = col * (1 + 0.1 * worn_top)[..., None]           # cima gastada, más limpia
    dirtm = clamp((1 - ao) * 1.6)
    col = mixc(col, col * rgb(170, 158, 138), dirtm)
    col = col * (0.8 + 0.2 * ao)[..., None]
    col = col * (1 + np.clip(conv, 0, 0.15)[..., None] * 0.4)
    # manchas (agua, aceite, óxido)
    stain = sstep(0.9, 1.8, noise(rng, 3, 60, 1.4)) * sstep(0, 0.8, noise(rng, 20, 200, 1.0))
    col = col * (1 - 0.28 * stain)[..., None]
    rust = sstep(1.6, 2.4, noise(rng, 4, 80, 1.4))
    col = mixc(col, rgb(130, 92, 60), rust * 0.35)
    col = mixc(col, rgb(60, 58, 56), gum * 0.85)
    col = col * (1 - 0.5 * crack)[..., None]
    # junta y tierra
    jcol = rgb(104, 96, 82) * (1 + 0.15 * noise(rng, 60, 900, 0.5))[..., None]
    moss = sstep(0.6, 1.6, noise(rng, 6, 150, 1.0))
    jcol = mixc(jcol, rgb(70, 82, 50), moss * 0.5)
    jcol = jcol * (0.7 + 0.3 * ao)[..., None]
    dirtfill = rgb(122, 108, 86) * (1 + 0.2 * noise(rng, 80, 1024, 0.4))[..., None]
    jcol = mixc(jcol, dirtfill, hole)
    bc = mixc(jcol, col, tmask)
    bc = bc * (1 + 0.04 * noise(rng, 1, 4, 1.5))[..., None]
    bc = clamp(bc)

    rough = 0.83 + 0.03 * noise(rng, 10, 500, 0.8) - 0.07 * worn_top + 0.06 * dirtm
    rough = np.where(tmask > 0.5, rough, 0.94) - 0.2 * stain * tmask + gum * 0.02
    rough = clamp(rough, 0.55, 0.97)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# ASFALTO — calle de barrio gastada: árido expuesto, fisuras, sellado, bacheo
# ----------------------------------------------------------------------------
def gen_asfalto(seed=404):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Asfalto']
    px = T / N
    yy, xx = grid()
    h = noise(rng, 1, 10, 1.8) * 0.35 + noise(rng, 10, 120, 1.1) * 0.04
    # bacheo: un parche rectangular (corte aserrado), apenas elevado y más oscuro
    pc = rng.uniform(0, N, 2)
    pw, ph = 130 / px, 95 / px
    jag = noise(rng, 30, 400, 1.2) * 0.25 / px
    dxp = np.abs(wrapd(xx, pc[0])) - pw / 2 + jag
    dyp = np.abs(wrapd(yy, pc[1])) - ph / 2 + jag
    pdist = np.maximum(dxp, dyp) * px
    patch = sstep(0.4, -0.4, pdist)
    seam = sstep(1.2, 0.2, np.abs(pdist))
    # áridos: piedra partida angulosa (Voronoi deformado) separada por mastic
    sx_ = xx + noise(rng, 100, 800, 1.0) * 1.6
    sy_ = yy + noise(rng, 100, 800, 1.0) * 1.6
    F1, F2, sid = worley(rng, 280, 0.95, sx_, sy_)
    e1 = F2 - F1
    keep1 = (rng.random(280 * 280) < 0.55)[sid]
    thr = per_cell(rng, 280 * 280, 0.12, 0.3)[sid]
    st1 = sstep(thr, thr + 0.18, e1) * keep1
    F1b, F2b, sidb = worley(rng, 640, 0.95)
    e2 = F2b - F1b
    keep2 = (rng.random(640 * 640) < 0.5)[sidb]
    st2 = sstep(0.12, 0.35, e2) * keep2
    expn = sstep(-1.2, 1.2, noise(rng, 2, 30, 1.3))
    exposure = (1 - 0.4 * patch) * (0.6 + 0.4 * expn)
    amp1 = per_cell(rng, 280 * 280, 0.6, 1.2)[sid]
    stones = np.maximum(np.sqrt(st1) * 0.14 * amp1, np.sqrt(st2) * 0.06) * exposure
    binder = -0.03 + noise(rng, 200, 1024, 0.4) * 0.015
    Fv, _, vid = worley(rng, 520)
    vr = per_cell(rng, 520 * 520, 0.15, 0.4)[vid]
    ravel_n = sstep(0.4, 1.8, noise(rng, 3, 40, 1.3))
    vk = (rng.random(520 * 520) < 0.015)[vid] | ((rng.random(520 * 520) < 0.25)[vid] & (ravel_n > 0.6))
    voids = np.sqrt(clamp(1 - (Fv / vr) ** 2)) * vk * (1 - 0.8 * patch)
    micro = np.maximum(binder, stones) - voids * 0.12
    h = h + micro + patch * 0.1
    # fisuras serpenteantes con ramas
    lines = []
    for _ in range(3):
        start = rng.uniform(0, N, 2)
        a0 = rng.uniform(0, 2 * np.pi)
        L = rng.uniform(260, 520) / px
        path = crack_path(rng, start, L, 5 / px, a0, 0.3)
        lines.append((path, 2))
        for _ in range(rng.integers(1, 4)):
            k = rng.integers(1, len(path) - 1)
            br = crack_path(rng, path[k], rng.uniform(30, 120) / px, 4 / px,
                            a0 + rng.choice([-1, 1]) * rng.uniform(0.6, 1.2), 0.35)
            lines.append((br, 1))
    cmask = draw_polylines(lines)
    # piel de cocodrilo, zona acotada, bordes irregulares
    Fa, Fb, _ = worley(rng, 18)
    w1 = noise(rng, 10, 120, 1.2) * 4 + noise(rng, 100, 600, 0.8) * 0.8
    w2 = noise(rng, 10, 120, 1.2) * 4 + noise(rng, 100, 600, 0.8) * 0.8
    ed = warp(Fb - Fa, w1, w2)
    allig = sstep(0.014, 0.003, ed) * sstep(1.1, 1.7, noise(rng, 1, 5, 1.6)) * (1 - patch)
    allig *= sstep(-0.6, 0.4, noise(rng, 10, 100, 1.0))
    cmask = np.maximum(cmask, allig)
    cmask = warp(cmask, noise(rng, 50, 500, 1.0) * 1.0, noise(rng, 50, 500, 1.0) * 1.0)
    width_mod = 0.6 + 0.4 * sstep(-1, 1, noise(rng, 10, 100, 1.0))
    cmask = clamp(gblur(cmask, 0.7) * 1.6 * width_mod) * (1 - patch * 0.9)
    crack_zone = clamp(gblur(cmask, 6.0) * 4)
    # sellado bituminoso sobre la fisura principal y sobre la junta del bacheo
    seal_l = draw_polylines([lines[0]])
    seal = clamp(gblur(seal_l, 3.0) * 3) * sstep(0.0, 1.0, noise(rng, 2, 20, 1.2) + 0.6)
    seal = np.maximum(seal, seam * 0.75 * sstep(-0.8, 0.4, noise(rng, 6, 60, 1.2)))
    seal = sstep(0.3, 0.55, seal + noise(rng, 30, 400, 1.0) * 0.08)
    h = h - cmask * 1.0 * (1 - seal) + seal * 0.05
    h = h - crack_zone * voids * 0.1
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.3, 1.0, 4.0], 0.8)

    # color: mastic oxidado gris + piedra granítica gris/rosada pulida por el tránsito
    sc = np.stack([rng.uniform(0.42, 0.7, 280 * 280)] * 3, -1).astype(F)
    sc *= rng.uniform(0.97, 1.03, (280 * 280, 3)).astype(F)
    red = rng.random(280 * 280) < 0.12
    sc[red] *= rgb(255, 226, 212)
    scol = sc[sid]
    bind_old = rgb(88, 89, 93) * (1 + 0.07 * noise(rng, 2, 60, 1.2))[..., None]
    bind_new = rgb(76, 76, 79) * (1 + 0.05 * noise(rng, 4, 80, 1.2))[..., None]
    bcol = mixc(bind_old, bind_new, patch)
    fine_c = 0.42 + 0.1 * noise(rng, 300, 1024, 0.2)
    fine = np.stack([fine_c] * 3, -1) * rgb(250, 250, 255)
    col = mixc(bcol, fine, st2 * exposure * 0.45)
    col = mixc(col, scol, st1 * exposure * 0.8)
    col = col * (1 - 0.3 * voids)[..., None]
    col = col * (0.62 + 0.38 * ao)[..., None]
    col = mixc(col, rgb(32, 32, 33), cmask * 0.85 * (1 - seal))
    col = mixc(col, rgb(112, 106, 96), crack_zone * 0.15)
    col = mixc(col, rgb(30, 30, 32), seal * 0.92)
    oil = sstep(1.6, 2.4, noise(rng, 3, 50, 1.5)) * (1 - seal)
    col = col * (1 - 0.25 * oil)[..., None]
    col = col * (1 + 0.06 * noise(rng, 1, 5, 1.5))[..., None]
    tire = sstep(0.8, 2.0, noise(rng, 1, 30, 1.2, ey=12.0)) * 0.06
    col = col * (1 - tire)[..., None]
    bc = clamp(col)

    stone_m = clamp(st1 * exposure)
    rough = 0.9 - 0.06 * stone_m + 0.03 * noise(rng, 20, 800, 0.6) - 0.05 * patch
    rough = rough - 0.4 * seal - 0.28 * oil + 0.03 * (1 - ao)
    rough = clamp(rough, 0.45, 0.97)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# HORMIGON — cordón de hormigón con poros, árido expuesto por desgaste
# ----------------------------------------------------------------------------
def gen_hormigon(seed=505):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Hormigon']
    px = T / N
    yy, xx = grid()
    h = noise(rng, 1, 10, 1.8) * 0.12 + noise(rng, 10, 200, 1.2) * 0.02 + noise(rng, 200, 1024, 0.4) * 0.006
    h += noise(rng, 6, 300, 1.0, ex=6.0, angle=0.35) * 0.008        # marcas de llana
    # árido (canto rodado/piedra partida) redondeado, sólo asoma donde la lechada se gastó
    wear = sstep(0.4, 1.4, noise(rng, 2, 25, 1.4))
    sx_ = xx + noise(rng, 30, 400, 1.0) * 3.0
    sy_ = yy + noise(rng, 30, 400, 1.0) * 3.0
    F1, F2, sid = worley(rng, 110, 0.95, sx_, sy_)
    sr = per_cell(rng, 110 * 110, 0.22, 0.42)[sid]
    keep = (rng.random(110 * 110) < 0.7)[sid]
    stone = sstep(sr, sr * 0.6, F1) * keep
    spall = sstep(2.0, 2.4, noise(rng, 2, 30, 1.5) + noise(rng, 30, 300, 1.0) * 0.2)
    spall = gblur(spall, 1.5)
    h -= wear * 0.06 + spall * 0.25
    expo = clamp(wear * 0.8 + spall)
    h += np.sqrt(stone) * 0.07 * expo + spall * noise(rng, 100, 1024, 0.7) * 0.04
    pores = np.zeros((N, N), F)
    for C, frac, rmin, rmax, dep in [(150, 0.12, 0.05, 0.28, 0.1), (60, 0.05, 0.1, 0.25, 0.22), (320, 0.18, 0.08, 0.35, 0.04)]:
        Fp, _, pid = worley(rng, C)
        pk = (rng.random(C * C) < frac)[pid]
        pr = per_cell(rng, C * C, rmin, rmax)[pid]
        pores = np.maximum(pores, np.sqrt(clamp(1 - (Fp / pr) ** 2)) * pk * dep * per_cell(rng, C * C, 0.5, 1.2)[pid])
    h -= pores
    lines = []
    for _ in range(2):
        p = crack_path(rng, rng.uniform(0, N, 2), rng.uniform(60, 160) / px, 3 / px, rng.uniform(0, 6.28), 0.3)
        lines.append((p, 1))
    cr = gblur(draw_polylines(lines), 0.6)
    cr = warp(cr, noise(rng, 50, 500, 1.0), noise(rng, 50, 500, 1.0))
    h -= cr * 0.12
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.15, 0.6, 2.5], 1.0)
    conv = convexity(h, px, 0.3)

    val = 0.68 + 0.022 * noise(rng, 2, 50, 1.2) + 0.018 * noise(rng, 50, 600, 0.8) + 0.025 * noise(rng, 1, 4, 1.5)
    col = np.stack([val, val * 0.99, val * 0.96], -1)
    lime = sstep(1.0, 2.0, noise(rng, 4, 80, 1.2))
    col = mixc(col, rgb(200, 198, 192), lime * 0.3)
    sc = rng.uniform(0.5, 0.82, (110 * 110, 1)).astype(F) * rgb(255, 247, 238)
    pinkish = rng.random(110 * 110) < 0.25
    sc[pinkish] *= rgb(255, 228, 214)
    col = mixc(col, sc[sid], stone * expo * 0.75)
    col = mixc(col, col * rgb(255, 250, 244) * 1.06, spall * 0.5)     # rotura: hormigón fresco, más claro
    dirt = clamp((1 - ao) * 1.4)
    col = mixc(col, rgb(92, 88, 80), dirt * 0.55)
    col = col * (1 + np.clip(conv, 0, 0.1)[..., None] * 0.6)
    grime = sstep(0.5, 1.8, noise(rng, 1, 12, 1.4)) * sstep(-0.5, 1.0, noise(rng, 20, 200, 1.0))
    col = col * (1 - 0.07 * grime)[..., None]
    scuff = sstep(2.0, 2.8, noise(rng, 2, 80, 1.0, ex=10.0)) * 0.18
    col = mixc(col, rgb(50, 50, 52), scuff)
    bc = clamp(col)

    rough = 0.86 + 0.03 * noise(rng, 10, 600, 0.8) + 0.05 * dirt + 0.03 * expo - 0.05 * scuff
    rough = clamp(rough, 0.78, 0.97)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# CHAPA — chapa acanalada sinusoidal galvanizada, canaletas verticales
# ----------------------------------------------------------------------------
def gen_chapa(seed=606):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Chapa']
    px = T / N
    yy, xx = grid()
    nper = 13                                   # 100 cm / 13 = 7,69 cm por onda
    P = N / nper
    phase = 2 * np.pi * xx / P
    wave = np.cos(phase)                        # 1 = cresta, -1 = valle (canaleta)
    h = 0.9 * wave                              # 18 mm pico a pico
    h += noise(rng, 1, 6, 1.6) * 0.12           # chapa no perfectamente plana
    # abolladuras
    dent = np.zeros((N, N), F)
    for _ in range(5):
        c = rng.uniform(0, N, 2)
        sx_ = rng.uniform(3, 10) / px
        sy_ = rng.uniform(3, 14) / px
        dent += np.exp(-(wrapd(xx, c[0]) ** 2 / sx_ ** 2 + wrapd(yy, c[1]) ** 2 / sy_ ** 2)) * rng.uniform(0.2, 0.55)
    h -= dent * (0.6 + 0.4 * wave)              # las crestas se aplastan más
    # fila de tornillos autoperforantes en crestas, cada 2 ondas
    yrow = rng.uniform(0, N)
    screws = np.zeros((N, N), F)
    washer = np.zeros((N, N), F)
    streak = np.zeros((N, N), F)
    for i in range(0, nper, 2):
        cxp = i * P + rng.normal(0, 0.3 / px)
        cyp = yrow + rng.normal(0, 0.6 / px)
        dx_ = wrapd(xx, cxp) * px
        dy_ = wrapd(yy, cyp) * px
        r = np.sqrt(dx_ ** 2 + dy_ ** 2)
        washer = np.maximum(washer, sstep(1.1, 0.95, r))
        screws = np.maximum(screws, sstep(0.62, 0.5, r))
        # chorreado de óxido hacia abajo del tornillo
        below = np.clip(dy_, 0, None)
        wid = 0.5 + below * 0.06
        s = np.exp(-(dx_ / wid) ** 2) * np.exp(-below / rng.uniform(12, 30)) * (dy_ > -0.5)
        streak = np.maximum(streak, s)
    h += washer * 0.12 + screws * 0.3
    h = h.astype(F)
    # óxido: en canaletas (por donde corre el agua) y desde los tornillos
    valley = sstep(0.1, -0.85, wave)
    rn = noise(rng, 2, 80, 1.2, ey=4.0) + 0.35 * noise(rng, 60, 700, 0.8)
    rzone = sstep(0.2, 1.6, noise(rng, 1, 5, 1.7))                    # zonas más castigadas
    rust = sstep(0.7, 1.5, rn + valley * 0.8 - 1.0 + rzone * 1.2) * (0.35 + 0.65 * valley)
    rust = clamp(rust + sstep(0.15, 0.6, streak * (1 + 0.5 * noise(rng, 20, 400, 1.0))))
    rust_heavy = sstep(0.55, 0.95, rust) * sstep(0.0, 0.8, noise(rng, 20, 300, 1.0))
    white = sstep(0.5, 1.6, noise(rng, 3, 120, 1.1, ey=3.0)) * (1 - rust)
    h += rust_heavy * noise(rng, 150, 1024, 0.6) * 0.03 + rust * 0.01
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.2, 1.0, 3.0], 0.6)
    ao = ao * (1 - 0.18 * valley)
    # zinc: lentejuelas del galvanizado + manchas de intemperie
    Fz, _, zid = worley(rng, 55, 0.95)
    spang = per_cell(rng, 55 * 55, -1, 1)[zid]
    spang_dir = noise(rng, 200, 1024, 0.5)
    zinc_v = 0.72 + 0.02 * spang + 0.01 * spang_dir
    weather = sstep(-0.6, 1.2, noise(rng, 1, 20, 1.5))
    zinc_v = zinc_v - 0.14 * weather
    zinc = np.stack([zinc_v, zinc_v * 1.005, zinc_v * 1.02], -1)
    rust_c = mixc(np.ones((N, N, 3), F) * rgb(140, 72, 38), np.ones((N, N, 3), F) * rgb(92, 48, 30),
                  sstep(-0.5, 1.0, noise(rng, 30, 500, 0.8)))
    col = mixc(zinc, rgb(196, 196, 190), white * 0.6)
    col = mixc(col, rust_c, rust)
    col = mixc(col, rgb(60, 60, 62), screws * 0.7)
    col = mixc(col, rgb(40, 40, 42), sstep(0.9, 1.0, washer) * (1 - screws) * 0.8)   # arandela de goma
    col = col * (0.85 + 0.15 * ao)[..., None]
    bc = clamp(col)

    metal = clamp(1 - rust * 1.1 - white * 0.6 - washer * (1 - screws))
    rough = 0.42 + 0.035 * spang + 0.16 * weather + 0.02 * noise(rng, 50, 1000, 0.6)
    rough = rough + white * 0.25 + rust * 0.4 + rust_heavy * 0.05 + (washer - screws) * 0.3
    rough = clamp(rough, 0.40, 0.95)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# MADERA — tablas verticales machihembradas de portón, barniz gastado
# ----------------------------------------------------------------------------
def gen_madera(seed=707):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Madera']
    px = T / N
    yy, xx = grid()
    nb = 10                                    # tablas de 12 cm
    bwid = T / nb
    X = xx * px
    Y = yy * px
    bi = np.floor(X / bwid).astype(np.int32) % nb
    u = X - np.floor(X / bwid) * bwid
    # veta: anillos de un tronco cuya médula queda fuera de la tabla; la profundidad del corte
    # varía en forma periódica a lo largo de la tabla -> "catedrales" (corte tangencial)
    pu = per_cell(rng, nb, -8, 20)[bi]
    pd0 = per_cell(rng, nb, 9, 22)[bi]
    pa = per_cell(rng, nb, 0.6, 2.6)[bi]
    pf = per_cell(rng, nb, 0, 6.283)[bi]
    pk = rng.integers(1, 3, nb)[bi].astype(F)
    depth = pd0 + pa * np.sin(2 * np.pi * pk * Y / T + pf) + 0.6 * np.sin(2 * np.pi * 3 * Y / T + 2 * pf)
    wn = noise(rng, 2, 40, 1.4, ey=6.0) * 0.22 + noise(rng, 30, 300, 1.0, ey=10.0) * 0.025
    knot_r = np.zeros((N, N), F)
    knot = np.zeros((N, N), F)
    for _ in range(3):
        kb = rng.integers(0, nb)
        kc = np.array([(kb + rng.uniform(0.3, 0.7)) * bwid / px, rng.uniform(0, N)])
        kr = rng.uniform(0.5, 1.0)
        dxk = wrapd(xx, kc[0]) * px
        dyk = wrapd(yy, kc[1]) * px
        rk = np.sqrt((dxk / kr) ** 2 + (dyk / (kr * 1.5)) ** 2)
        inb = (bi == kb)
        knot_r += np.exp(-(rk / 2.5) ** 2) * 1.6 * inb
        knot = np.maximum(knot, sstep(1.0, 0.7, rk) * inb)
    rad = np.sqrt((u - pu) ** 2 + depth ** 2) + wn + knot_r
    rings_pc = per_cell(rng, nb, 1.4, 2.6)[bi]
    rr = rad * rings_pc
    rr = rr + 0.25 * np.sin(rr * 0.37 + per_cell(rng, nb, 0, 6.28)[bi])   # años de crecimiento desparejo
    t = rr % 1.0
    ring_i = np.floor(rr).astype(np.int32) % 997
    ring_k = rng.uniform(0.45, 1.0, 997).astype(F)[ring_i]          # intensidad distinta por anillo
    lw0 = rng.uniform(0.55, 0.75, 997).astype(F)[ring_i]
    late = sstep(lw0, lw0 + 0.22, t) * (1 - sstep(0.94, 1.0, t)) * ring_k
    fiber = noise(rng, 40, 1024, 0.6, ey=30.0)
    # desgaste del barniz: más en algunas tablas y en los cantos; descascarado en escamas
    bw_wear = per_cell(rng, nb, -0.35, 0.35)[bi]
    edge_d = np.minimum(u, bwid - u)
    edge_w = sstep(1.0, 0.2, edge_d)
    wear_n = noise(rng, 1, 8, 1.7) * 0.7 + noise(rng, 6, 60, 1.3, ey=3.0) * 0.3 + noise(rng, 60, 400, 0.9) * 0.05 + bw_wear
    wv = wear_n + edge_w * 0.35
    # v2: menos madera expuesta (antes ~22 %, se leía como óxido sobre naranja); ahora ~7 % y en los cantos
    bare = sstep(1.12, 1.2, wv)                                   # madera expuesta, agrisada
    thin = sstep(0.4, 1.12, wv) * (1 - bare)                      # barniz gastado, mate
    flake_edge = sstep(1.1, 1.13, wv) * (1 - sstep(1.18, 1.22, wv))
    # altura
    cup = per_cell(rng, nb, 0.03, 0.1)[bi]
    h = -cup * ((u / bwid - 0.5) * 2) ** 2 + per_cell(rng, nb, -0.05, 0.05)[bi]
    vg = sstep(0.4, 0.0, edge_d)
    h -= vg * 0.3 + sstep(0.07, 0.0, edge_d) * 0.35
    h += late * 0.01 + fiber * 0.003
    h += bare * (late * 0.04 + fiber * 0.01 - 0.02)
    h += (1 - bare) * 0.012 + flake_edge * 0.008
    h -= knot * 0.04
    cr = sstep(2.8, 3.3, noise(rng, 4, 200, 1.0, ey=30.0)) * (1 - vg)
    h -= cr * 0.12
    yn = rng.uniform(0, N)
    nails = np.zeros((N, N), F)
    for b in range(nb):
        for k in (0.28, 0.72):
            cxn = (b + k) * bwid / px
            r = np.sqrt(wrapd(xx, cxn) ** 2 + wrapd(yy, yn + rng.normal(0, 3)) ** 2) * px
            nails = np.maximum(nails, sstep(0.28, 0.22, r))
    nail_rust = np.zeros((N, N), F)
    h += nails * 0.03
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.15, 0.6, 2.0], 0.9)

    tone = per_cell(rng, nb, 0.86, 1.1)[bi]
    early = np.ones((N, N, 3), F) * rgb(184, 148, 114)            # v2: menos naranja (cedro/pino teñido)
    latec = np.ones((N, N, 3), F) * rgb(128, 92, 66)
    wood = mixc(early, latec, late * 0.7)
    wood = wood * (1 + 0.06 * fiber + 0.06 * noise(rng, 2, 40, 1.2, ey=5.0))[..., None] * tone[..., None]
    streaks = noise(rng, 3, 120, 1.0, ey=20.0)                   # vetas de color a lo largo de la fibra
    wood = mixc(wood, wood * rgb(225, 190, 170), sstep(0.3, 1.5, streaks) * 0.5)
    wood = mixc(wood, rgb(80, 48, 30), knot * 0.85)
    var = wood * rgb(228, 198, 170)                              # barniz ambarino (satura y oscurece)
    var_thin = wood * rgb(240, 222, 202)
    gray = wood.mean(-1, keepdims=True)
    # madera a la intemperie: gris cálido (no gris frío, que contra el naranja parecía chapa oxidada)
    weathered = mixc(wood, gray * 0.5 + 0.5 * rgb(150, 136, 118), 0.6)
    weathered = mixc(weathered, rgb(118, 106, 92), late * 0.35)
    col = mixc(var, var_thin, thin)
    col = mixc(col, weathered, bare)
    col = col * (1 - 0.18 * flake_edge)[..., None]
    col = mixc(col, rgb(50, 38, 30), cr * 0.8)
    col = mixc(col, rgb(72, 60, 52), nails * 0.9)
    col = col * (0.72 + 0.28 * ao)[..., None]
    grime = sstep(0.5, 1.8, noise(rng, 1, 15, 1.4, ey=3.0))
    col = col * (1 - 0.1 * grime)[..., None]
    bc = clamp(col)

    craze = sstep(0.4, 1.2, noise(rng, 100, 1024, 0.6))
    rough = 0.38 + 0.05 * craze + 0.03 * noise(rng, 5, 100, 1.0) + 0.04 * late
    rough = lerp(rough, 0.62 + 0.03 * fiber, thin * 0.8)
    rough = lerp(rough, 0.82 + 0.04 * fiber, bare) + 0.06 * (1 - ao) + 0.08 * grime * (1 - bare)
    rough = clamp(rough, 0.32, 0.92)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# TEJAS — teja colonial (portuguesa) cerámica roja, envejecida
# ----------------------------------------------------------------------------
def gen_tejas(seed=808):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Tejas']
    px = T / N
    yy, xx = grid()
    # teja colonial tipo "portuguesa" (como en las referencias de Caseros):
    # perfil en S = cobija convexa + canal cóncavo, 20 cm de paso, 20 cm de exposición por hilada
    ncol, nrow = 6, 6
    P, tl = T / ncol, T / nrow
    X = xx * px + noise(rng, 6, 200, 1.3) * 0.08
    Y = yy * px + noise(rng, 6, 200, 1.3) * 0.08
    rowf = np.floor(Y / tl)
    ry = rowf.astype(np.int32) % nrow
    v = Y - rowf * tl                       # 0 = arriba (bajo la hilada superior) .. tl = nariz
    shift = rng.normal(0, 0.5, nrow).astype(F)[ry]
    Xs = X + shift
    colf = np.floor(Xs / P)
    cx_ = colf.astype(np.int32) % ncol
    s = (Xs - colf * P) / P                 # 0..1 dentro del paso
    tid = ry * ncol + cx_
    nt = ncol * nrow
    # pequeñas diferencias por pieza (cerámica artesanal)
    ox = rng.normal(0, 0.012, nt).astype(F)[tid]
    s2 = s + ox
    hw0 = 0.33 + rng.normal(0, 0.012, nt).astype(F)[tid]             # semiancho de la cobija
    # nariz de la cobija redondeada en planta (forma de U) y en alto
    rcap = 5.5
    tcap = clamp((v - (tl - rcap)) / rcap)
    capw = np.sqrt(clamp(1 - tcap ** 2))
    hw = hw0 * (0.35 + 0.65 * capw)
    xh = clamp(np.abs(s2 - 0.34) / hw, 0, 1)
    hump = clamp(np.cos(xh * np.pi / 2)) ** 1.3 * (np.abs(s2 - 0.34) < hw)  # cobija: perfil redondeado
    chan = np.cos(np.clip((s2 - 0.84) / 0.18, -1, 1) * np.pi / 2) ** 2  # canal
    cross = 4.2 * hump * (0.25 + 0.75 * capw) - 0.8 * chan
    rise = 0.4 + 1.4 * (v / tl)              # cada hilada monta sobre la inferior
    h = rise + cross
    h += sstep(tl, tl - 0.6, v) * 0.15 * (1 - hump)                  # canto del labio
    h += rng.normal(0, 0.12, nt).astype(F)[tid] + (v - tl / 2) * rng.normal(0, 0.01, nt).astype(F)[tid]
    h += noise(rng, 40, 1024, 0.8) * 0.012 + noise(rng, 4, 80, 1.3) * 0.05
    chip = sstep(1.9, 2.4, noise(rng, 15, 300, 1.2)) * sstep(2.5, 0.3, tl - v) * hump
    h -= chip * 0.6
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.4, 1.5, 5.0], 0.7)
    conv = convexity(h, px, 1.0)

    pal = np.array([rgb(186, 92, 62), rgb(172, 82, 57), rgb(198, 108, 72), rgb(156, 74, 54),
                    rgb(180, 100, 72), rgb(140, 68, 52), rgb(204, 122, 86)])
    wts = np.array([0.27, 0.22, 0.14, 0.13, 0.1, 0.07, 0.07])
    tc = pal[rng.choice(len(pal), nt, p=wts)] * rng.uniform(0.94, 1.06, (nt, 1)).astype(F)
    col = tc[tid]
    col = col * (1 + 0.05 * noise(rng, 6, 200, 1.0) + 0.035 * noise(rng, 200, 1024, 0.3))[..., None]
    gdir = per_cell(rng, nt, -0.1, 0.1)[tid]
    col = col * (1 + gdir * (v / tl - 0.5) * 2)[..., None]          # gradiente de cocción por pieza
    burn = sstep(0.6, 2.0, noise(rng, 3, 30, 1.5)) * (rng.random(nt) < 0.3)[tid]
    col = mixc(col, col * rgb(170, 140, 128), burn * 0.35)
    # lomo de la cobija desteñido por el sol; canales con mugre que baja con el agua
    col = mixc(col, col * rgb(255, 236, 222) * 1.08, clamp(conv * 0.8) * hump)
    col = col * (0.9 + 0.14 * hump - 0.06 * chan)[..., None]
    runoff = sstep(0.3, 1.5, noise(rng, 3, 200, 1.0, ey=10.0)) * (0.25 + 0.75 * chan)
    col = col * (1 - 0.25 * runoff)[..., None]
    col = mixc(col, rgb(62, 48, 40), sstep(tl * 0.15, 0, v) * (1 - hump * 0.5) * 0.4)
    # líquenes (gris claro y naranja) y verdín en solapes y canales
    Fl, _, lid = worley(rng, 150)
    lsz = per_cell(rng, 150 * 150, 0.15, 0.45)[lid]
    lk = (rng.random(150 * 150) < 0.1)[lid] * sstep(lsz, lsz * 0.5, Fl)
    lreg = sstep(0.2, 1.2, noise(rng, 2, 30, 1.3))
    lich = lk * lreg * sstep(-0.5, 0.5, noise(rng, 100, 800, 0.8))
    lc = np.where((rng.random(150 * 150) < 0.6)[lid][..., None], rgb(176, 170, 150), rgb(200, 146, 76))
    col = mixc(col, lc, lich * 0.75)
    moss = sstep(0.3, 1.5, noise(rng, 6, 150, 1.0)) * clamp(sstep(tl * 0.25, 0, v) + chan * 0.4)
    col = mixc(col, rgb(70, 76, 46), moss * 0.5)
    col = mixc(col, rgb(206, 128, 92), chip * 0.6)
    col = col * (0.72 + 0.28 * ao)[..., None]
    col = col * (1 + 0.04 * noise(rng, 1, 5, 1.5))[..., None]
    bc = clamp(col)

    rough = 0.76 + 0.03 * noise(rng, 10, 500, 0.8) + 0.07 * runoff + 0.12 * lich + 0.1 * moss - 0.04 * clamp(conv)
    rough = clamp(rough, 0.66, 0.96)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# METAL PINTADO — esmalte sintético sobre chapa/hierro, gris neutro (se tiñe)
# ----------------------------------------------------------------------------
def gen_metalpintado(seed=909):
    rng = np.random.default_rng(seed)
    T = TILE_CM['MetalPintado']
    px = T / N
    yy, xx = grid()
    h = noise(rng, 1, 8, 1.8) * 0.05                                     # chapa base
    h += noise(rng, 60, 700, 1.0) * 0.0035                               # piel de naranja
    h += noise(rng, 4, 250, 1.0, ex=18.0) * 0.003                        # pinceladas horizontales
    # chorreaduras de esmalte (sags): gotas alargadas hacia abajo con frente redondeado
    for _ in range(5):
        c = rng.uniform(0, N, 2)
        wd = rng.uniform(0.25, 0.6) / px
        ln = rng.uniform(1.5, 6.0) / px
        dx_ = wrapd(xx, c[0])
        dy_ = wrapd(yy, c[1])
        along = clamp(dy_ / ln + 1.0)                                    # 0 arriba .. 1 en el frente
        prof_ = np.exp(-(dx_ / (wd * (0.6 + 0.4 * along))) ** 2) * (dy_ < 0) * (dy_ > -ln)
        front = np.exp(-((dx_ / wd) ** 2 + (dy_ / (wd * 0.8)) ** 2))
        h += np.maximum(prof_ * along * 0.025, front * 0.04)
    # micro rayas
    lines = []
    for _ in range(420):
        p0 = rng.uniform(0, N, 2)
        a = rng.normal(0.1, 0.5) if rng.random() < 0.6 else rng.uniform(0, np.pi)
        L = rng.uniform(0.5, 12) / px
        n = max(2, int(L / 8))
        pts = [p0 + (i / n) * L * np.array([np.cos(a), np.sin(a)]) + rng.normal(0, 0.8, 2) for i in range(n + 1)]
        lines.append((np.array(pts), 1))
    scr = draw_polylines(lines)
    scr = gblur(scr, 0.45) * clamp(0.5 + 0.5 * noise(rng, 10, 200, 1.0))
    scr = clamp(scr * 1.4)
    deep = scr * sstep(1.0, 2.0, noise(rng, 20, 300, 1.0))
    h -= scr * 0.004 + deep * 0.008
    # saltaduras de pintura con antióxido debajo
    Fc, _, cid = worley(rng, 40)
    clus = sstep(0.8, 1.6, noise(rng, 2, 12, 1.4))
    ck = ((rng.random(1600) < 0.003)[cid] | ((rng.random(1600) < 0.12)[cid] & (clus > 0.6)))
    cr = per_cell(rng, 1600, 0.04, 0.22)[cid]
    chipn = noise(rng, 60, 800, 1.0) * 0.05
    chip = sstep(0.02, -0.02, Fc - cr + chipn) * ck
    rustcore = sstep(0.02, -0.02, Fc - cr * 0.55 + chipn) * ck * (per_cell(rng, 1600, 0, 1)[cid] > 0.4)
    h -= chip * 0.012 + rustcore * 0.006
    h += rustcore * noise(rng, 200, 1024, 0.5) * 0.003
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.1, 0.5], 0.4)

    val = 0.8 + 0.012 * noise(rng, 1, 10, 1.5) + 0.006 * noise(rng, 20, 300, 1.0)
    col = np.stack([val, val, val * 0.995], -1)
    dust = sstep(0.0, 1.5, noise(rng, 1, 12, 1.4)) * 0.6
    col = col * (1 - 0.06 * dust)[..., None]
    col = mixc(col, rgb(215, 215, 213), scr * 0.35)
    col = mixc(col, rgb(120, 60, 42), chip)                  # antióxido rojizo
    col = mixc(col, rgb(84, 50, 36), rustcore * 0.9)
    col = col * (0.9 + 0.1 * ao)[..., None]
    bc = clamp(col)

    rough = 0.42 + 0.025 * noise(rng, 30, 700, 0.8) + 0.04 * noise(rng, 2, 40, 1.2) + 0.08 * dust
    rough += scr * 0.1 + chip * 0.3 + rustcore * 0.1
    rough = clamp(rough, 0.35, 0.9)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# PIEDRA LAJA — enchapado de laja en hiladas irregulares (frente de casa)
# ----------------------------------------------------------------------------
def gen_piedralaja(seed=1010):
    rng = np.random.default_rng(seed)
    T = TILE_CM['PiedraLaja']
    px = T / N
    yy, xx = grid()
    # hiladas de alturas irregulares que suman exactamente 150 cm
    hs = []
    while sum(hs) < T - 4:
        hs.append(rng.choice([rng.uniform(4, 7), rng.uniform(6, 11), rng.uniform(9, 15)], p=[0.35, 0.45, 0.2]))
    hs = np.array(hs)
    hs *= T / hs.sum()
    nr = len(hs)
    cum_r = np.concatenate([[0.0], np.cumsum(hs)])
    wamp = 0.28
    wx = noise(rng, 6, 200, 1.4) * wamp + noise(rng, 100, 900, 0.7) * 0.03
    wy = noise(rng, 6, 200, 1.4) * wamp + noise(rng, 100, 900, 0.7) * 0.03
    X = (xx * px + wx) % T
    Y = (yy * px + wy) % T
    ri = np.clip(np.searchsorted(cum_r, Y, side='right') - 1, 0, nr - 1)
    v = Y - cum_r[ri]
    rh = hs[ri]
    u = np.zeros((N, N), F)
    sw = np.zeros((N, N), F)
    sid = np.zeros((N, N), np.int32)
    base_id = 0
    for r in range(nr):
        L = []
        while sum(L) < T - 12:
            L.append(rng.uniform(14, 52))
        L = np.array(L)
        L *= T / L.sum()
        off = rng.uniform(0, T)
        cum = np.concatenate([[0.0], np.cumsum(L)])
        m = ri == r
        xs = (X[m] - off) % T
        idx = np.clip(np.searchsorted(cum, xs, side='right') - 1, 0, len(L) - 1)
        u[m] = xs - cum[idx]
        sw[m] = L[idx]
        sid[m] = base_id + idx
        base_id += len(L)
    ns = base_id
    jl = per_cell(rng, ns, 0.25, 0.6)[sid]
    jr = per_cell(rng, ns, 0.25, 0.6)[sid]
    jt = per_cell(rng, ns, 0.2, 0.5)[sid]
    jb = per_cell(rng, ns, 0.2, 0.5)[sid]
    lu = u - jl
    lv = v - jt
    bl = sw - jl - jr
    bh = rh - jt - jb
    d = np.minimum(np.minimum(lu, bl - lu), np.minimum(lv, bh - lv))
    # relieve de piedra partida: estratos horizontales escalonados
    # estratos alargados en x (ex>1) + desprendimientos en escalón
    strat = noise(rng, 3, 300, 1.3, ex=5.0) * 0.75 + noise(rng, 6, 300, 1.2) * 0.25
    q = 3.0
    sq = strat * q
    terr = (np.floor(sq) + sstep(0.75, 1.0, sq % 1.0)) / q
    zb = per_cell(rng, ns, 0.1, 0.7)[sid]
    tx_ = rng.normal(0, 0.012, ns).astype(F)[sid]
    ty_ = rng.normal(0, 0.03, ns).astype(F)[sid]
    face = zb + (lu - bl / 2) * tx_ + (lv - bh / 2) * ty_ + terr * 0.3
    face += noise(rng, 20, 300, 1.2, ex=3.0) * 0.06 + noise(rng, 150, 1024, 0.6) * 0.015
    R = per_cell(rng, ns, 0.4, 1.0)[sid]
    dd = np.clip(d, 0, None)
    edge = np.where(dd >= R, 0.0, -R + np.sqrt(np.clip(R * R - (R - dd) ** 2, 0, None))) * 0.9
    chip = sstep(0.0, 0.1, np.clip(noise(rng, 20, 400, 1.1) - 1.0, 0, None) * 1.2 - d)
    hs_ = np.where(d > 0, face + edge - chip * 0.35, -4)
    hm = -0.55 + noise(rng, 80, 1024, 0.4) * 0.05 + noise(rng, 5, 100, 1.0) * 0.08
    h = np.maximum(hs_, hm).astype(F)
    smask = sstep(-0.03, 0.05, hs_ - hm)

    ao = cavity_ao(h, px, [0.3, 1.0, 3.0], 0.7)
    conv = convexity(h, px, 0.5)

    pal = np.array([rgb(186, 168, 132), rgb(160, 152, 136), rgb(178, 150, 98), rgb(150, 116, 82),
                    rgb(138, 138, 124), rgb(196, 184, 156), rgb(120, 108, 90)])
    wts = np.array([0.24, 0.2, 0.16, 0.1, 0.12, 0.1, 0.08])
    c1 = pal[rng.choice(len(pal), ns, p=wts)] * rng.uniform(0.92, 1.06, (ns, 1)).astype(F)
    c2 = pal[rng.choice(len(pal), ns, p=wts)]
    band = sstep(-0.8, 0.8, noise(rng, 4, 200, 1.1, ex=6.0))
    col = mixc(c1[sid], c2[sid], band * 0.4)
    col = col * (1 + 0.06 * noise(rng, 8, 300, 1.0) + 0.04 * noise(rng, 300, 1024, 0.3))[..., None]
    ox = sstep(0.9, 2.0, noise(rng, 6, 120, 1.2)) * (rng.random(ns) < 0.4)[sid]
    col = mixc(col, rgb(150, 92, 50), ox * 0.45)
    lich = sstep(1.5, 2.3, noise(rng, 30, 400, 1.0)) * sstep(0, 1, noise(rng, 2, 20, 1.3))
    col = mixc(col, rgb(70, 68, 60), lich * 0.6)
    col = col * (1 + np.clip(conv, 0, 0.2)[..., None] * 0.5)
    col = col * (0.8 + 0.2 * ao)[..., None]
    mcol = rgb(168, 163, 152) * (1 + 0.08 * noise(rng, 100, 1024, 0.3))[..., None]
    mcol = mcol * (0.62 + 0.38 * ao)[..., None]
    bc = mixc(mcol, col, smask)
    bc = bc * (1 + 0.04 * noise(rng, 1, 5, 1.5))[..., None]
    bc = clamp(bc)

    rough = np.where(smask > 0.5, 0.82, 0.93) + 0.03 * noise(rng, 20, 600, 0.8) + 0.06 * lich + 0.04 * (1 - ao) - 0.03 * clamp(conv * 3)
    rough = clamp(rough, 0.74, 0.97)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# v2 — utilidades para los sets nuevos
# ----------------------------------------------------------------------------
def worley2(rng, Cx, Cy, jitter=0.9, xs=None, ys=None):
    """Worley periódico anisótropo: Cx x Cy celdas por textura (celdas alargadas si Cx != Cy).
    Distancias en unidades de celda. Devuelve F1, F2, id."""
    yy, xx = grid()
    if xs is None:
        xs, ys = xx, yy
    gx = xs * (Cx / N)
    gy = ys * (Cy / N)
    ix = np.floor(gx).astype(np.int32)
    iy = np.floor(gy).astype(np.int32)
    fx = (gx - ix).astype(F)
    fy = (gy - iy).astype(F)
    jx = (rng.random(Cx * Cy).astype(F) * jitter + (1 - jitter) * 0.5)
    jy = (rng.random(Cx * Cy).astype(F) * jitter + (1 - jitter) * 0.5)
    F1 = np.full((N, N), 9.0, F)
    F2 = np.full((N, N), 9.0, F)
    ID = np.zeros((N, N), np.int32)
    for dy in (-1, 0, 1):
        cy = (iy + dy) % Cy
        for dx in (-1, 0, 1):
            cx = (ix + dx) % Cx
            cid = cy * Cx + cx
            px_ = dx + jx[cid] - fx
            py_ = dy + jy[cid] - fy
            d = px_ * px_ + py_ * py_
            closer = d < F1
            F2 = np.where(closer, F1, np.minimum(F2, d))
            ID = np.where(closer, cid, ID)
            F1 = np.where(closer, d, F1)
    return np.sqrt(F1), np.sqrt(F2), ID


def stamp_layer(rng, C, T, half_len, half_w, keep=1.0, angle=None, angle_jit=np.pi, taper=1.0,
                z_range=(0.0, 1.0), best=None):
    """Estampa una pieza alargada (hoja, brizna) por celda de una grilla periódica C x C.
    half_len/half_w: (min, max) en cm; la mitad del largo no debe pasar de una celda (T/C).
    angle: ángulo medio (None = al azar); angle_jit: dispersión. taper: 1 = punta aguda en los extremos.
    Se queda, por píxel, con la pieza más alta (z). 'best' permite acumular capas sucesivas.
    Devuelve dict con z (altura), m (cubierta 0/1), u (-1..1 a lo largo), v (-1..1 a lo ancho), id global."""
    yy, xx = grid()
    cell = T / C
    gx = xx * (C / N)
    gy = yy * (C / N)
    ix = np.floor(gx).astype(np.int32)
    iy = np.floor(gy).astype(np.int32)
    fx = (gx - ix).astype(F)
    fy = (gy - iy).astype(F)
    n = C * C
    jx = rng.random(n).astype(F)
    jy = rng.random(n).astype(F)
    a = (rng.uniform(0, np.pi, n) if angle is None else angle + rng.normal(0, angle_jit, n)).astype(F)
    ca, sa = np.cos(a).astype(F), np.sin(a).astype(F)
    L = rng.uniform(*half_len, n).astype(F)
    W = rng.uniform(*half_w, n).astype(F)
    Z = rng.uniform(*z_range, n).astype(F)
    K = rng.random(n) < keep
    gid0 = 0 if best is None else best['next_id']
    if best is None:
        best = {'z': np.full((N, N), -1e3, F), 'm': np.zeros((N, N), F), 'u': np.zeros((N, N), F),
                'v': np.zeros((N, N), F), 'id': np.full((N, N), -1, np.int32)}
    pxw = T / N
    for dy in (-1, 0, 1):
        cy = (iy + dy) % C
        for dx in (-1, 0, 1):
            cx = (ix + dx) % C
            cid = cy * C + cx
            ok = K[cid]
            ox = (fx - dx - jx[cid]) * cell           # del centro de la pieza al píxel (cm)
            oy = (fy - dy - jy[cid]) * cell
            c_, s_ = ca[cid], sa[cid]
            u = ox * c_ + oy * s_
            v = -ox * s_ + oy * c_
            Lc = L[cid]
            un = u / Lc
            prof = W[cid] * np.power(clamp(1.0 - un * un), 0.5 * taper)
            inside = (np.abs(un) < 1.0) & (np.abs(v) < prof) & ok
            vn = v / np.maximum(prof, 1e-4)
            dome = np.sqrt(clamp(1.0 - vn * vn))
            z = Z[cid] + dome * W[cid] * 0.6 - np.abs(un) * 0.15 * Lc * 0.1
            upd = inside & (z > best['z'])
            best['z'] = np.where(upd, z, best['z'])
            best['m'] = np.where(upd, 1.0, best['m']).astype(F)
            best['u'] = np.where(upd, un, best['u']).astype(F)
            best['v'] = np.where(upd, vn, best['v']).astype(F)
            best['id'] = np.where(upd, gid0 + cid, best['id'])
    best['next_id'] = gid0 + n
    return best


def pebbles(rng, C, frac, rmin, rmax, warp_px=0.0):
    """Piedritas redondeadas sueltas (cúpula por celda de Worley). Devuelve altura relativa 0..1 e id."""
    yy, xx = grid()
    xs, ys = xx, yy
    if warp_px:
        xs = xx + noise(rng, 20, 400, 1.0) * warp_px
        ys = yy + noise(rng, 20, 400, 1.0) * warp_px
    F1, _, cid = worley(rng, C, 0.9, xs, ys)
    r = per_cell(rng, C * C, rmin, rmax)[cid]
    k = (rng.random(C * C) < frac)[cid]
    dome = np.sqrt(clamp(1 - (F1 / r) ** 2)) * k
    return dome.astype(F), cid


# ----------------------------------------------------------------------------
# CORTEZA — fresno americano (el árbol de vereda más común del conurbano):
# surcos en rombo alargados y crestas angostas entrelazadas, gris pardo con líquenes
# ----------------------------------------------------------------------------
def gen_corteza(seed=1111):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Corteza']
    px = T / N
    yy, xx = grid()
    # dominio deformado: las crestas serpentean y se bifurcan
    wx = noise(rng, 1, 10, 1.6) * 38 + noise(rng, 10, 80, 1.2) * 5 + noise(rng, 80, 600, 0.8) * 1.2
    wy = noise(rng, 1, 10, 1.6) * 20
    xs, ys = xx + wx, yy + wy
    # rombos: 17 x 5 celdas en 120 cm -> ~7 cm de ancho x 24 cm de alto
    F1, F2, cid = worley2(rng, 16, 4, 0.85, xs, ys)
    e = F2 - F1                                     # 0 en el borde entre celdas = cresta
    ncell = 16 * 4
    rw = per_cell(rng, ncell, 0.16, 0.26)[cid]     # ancho de cresta por celda
    # cresta con lomo plano y surco en V (no fondo plano)
    ridge = 0.75 * sstep(rw, 0.03, e) + 0.25 * sstep(rw + 0.28, 0.0, e)
    # una segunda red más fina parte las crestas anchas
    G1, G2, gid = worley2(rng, 30, 6, 0.85, xs + 400, ys + 300)
    ridge2 = sstep(0.09, 0.02, G2 - G1) * 0.7
    rid = np.maximum(ridge, ridge2 * sstep(0.6, 1.4, noise(rng, 2, 20, 1.3)))
    depth = per_cell(rng, ncell, 1.2, 2.2)[cid]     # profundidad del surco (cm)
    h = (rid ** 0.7 - 1.0) * depth
    # placas escamosas en la cara de las crestas, cortadas por fisuras horizontales
    plates = noise(rng, 20, 300, 1.2, ey=0.35) * 0.18
    hcr = sstep(1.9, 2.5, noise(rng, 6, 200, 1.1, ey=0.15)) * rid
    h += rid * (plates - hcr * 0.5)
    # fibra vertical en el fondo de los surcos
    fib = noise(rng, 30, 1024, 0.7, ex=0.12)
    h += (1 - rid) * fib * 0.08
    h += noise(rng, 200, 1024, 0.5) * 0.02
    h = gblur(h, 0.8).astype(F)

    ao = cavity_ao(h, px, [0.3, 1.0, 3.0], 0.7)
    conv = convexity(h, px, 0.8)

    # color: crestas gris pardo (lavadas por la lluvia), surcos pardo oscuro con fondo rojizo
    top = rgb(146, 138, 124) * (1 + 0.08 * noise(rng, 3, 60, 1.2))[..., None]
    side = rgb(108, 94, 80) * np.ones((N, N, 3), F)
    furrow = mixc(np.ones((N, N, 3), F) * rgb(78, 62, 50), np.ones((N, N, 3), F) * rgb(110, 78, 56),
                  sstep(0.0, 1.5, fib + noise(rng, 6, 80, 1.0)) * 0.6)
    col = mixc(furrow, side, sstep(0.1, 0.5, rid))
    col = mixc(col, top, sstep(0.55, 0.95, rid) * sstep(-0.1, 0.25, conv + 0.1))
    # líquenes gris verdoso claro (manchas) y alga verde (zonas)
    Fl, _, lid = worley(rng, 60)
    lk = (rng.random(3600) < 0.12)[lid] * sstep(per_cell(rng, 3600, 0.2, 0.5)[lid], 0.08, Fl)
    lreg = sstep(0.0, 1.2, noise(rng, 1, 8, 1.5))
    lich = clamp(lk * lreg * (0.4 + 0.6 * rid) * sstep(-0.6, 0.4, noise(rng, 60, 600, 0.9)))
    col = mixc(col, rgb(150, 152, 128), lich * 0.75)
    alga = sstep(0.4, 1.6, noise(rng, 1, 6, 1.6)) * sstep(-0.5, 0.8, noise(rng, 20, 200, 1.0))
    col = mixc(col, rgb(82, 94, 54), alga * 0.45 * (0.5 + 0.5 * rid))
    col = col * (0.72 + 0.28 * ao)[..., None]
    col = col * (1 + 0.04 * noise(rng, 1, 4, 1.5))[..., None]
    bc = clamp(col)

    rough = 0.9 + 0.03 * noise(rng, 10, 400, 0.8) + 0.04 * (1 - rid) - 0.04 * lich - 0.03 * alga
    rough = clamp(rough, 0.8, 0.98)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# PASTO — césped corto de vereda/plaza visto desde arriba: briznas, trébol, matas secas y tierra
# ----------------------------------------------------------------------------
def gen_pasto(seed=1212):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Pasto']
    px = T / N
    yy, xx = grid()
    # suelo debajo
    soil_h = noise(rng, 1, 20, 1.6) * 0.3 + noise(rng, 20, 400, 1.0) * 0.05
    # densidad: zonas ralas (pisoteadas) y matas densas
    dens = sstep(-1.3, 0.9, noise(rng, 1, 12, 1.6) + 0.35 * noise(rng, 12, 80, 1.2))
    # briznas: 7 capas de 60x60 celdas (3,3 cm), medio largo 1,2-3 cm, medio ancho 0,10-0,18 cm
    best = None
    for i in range(12):
        best = stamp_layer(rng, 64, T, (1.0, 2.9), (0.14, 0.26), keep=0.97, angle=None,
                           taper=1.2, z_range=(0.1 + 0.15 * i, 0.5 + 0.15 * i), best=best)
    blade = best['m'] * (rng.random(best['next_id'] + 1)[best['id']] < 0.5 + 0.5 * dens)
    bz = np.where(blade > 0, best['z'], -1)
    # trébol: hojitas redondas en grupos de 3 en manchones
    clov_reg = sstep(0.7, 1.4, noise(rng, 2, 25, 1.5))
    cb = stamp_layer(rng, 110, T, (0.6, 0.85), (0.45, 0.6), keep=0.85, taper=1.0, z_range=(1.6, 2.6))
    clover = cb['m'] * clov_reg
    h = soil_h + np.where(blade > 0, 0.3 + bz * 0.45, 0)
    clov_h = soil_h + cb['z'] * 0.6
    clover_top = (clover > 0.5) & (clov_h > h)                       # trébol por encima de las briznas
    h = np.where(clover_top, clov_h, h)
    h += noise(rng, 300, 1024, 0.3) * 0.01
    h = gblur(h.astype(F), 0.6)

    ao = cavity_ao(h, px, [0.2, 0.8, 2.5], 0.7)

    # color
    nid = best['next_id'] + 1
    gpal = np.array([rgb(76, 98, 44), rgb(92, 112, 50), rgb(64, 86, 38), rgb(108, 120, 58), rgb(84, 104, 40)])
    gcol = gpal[rng.integers(0, len(gpal), nid)] * rng.uniform(0.88, 1.12, (nid, 1)).astype(F)
    bc_bl = gcol[best['id']]
    dry_reg = sstep(0.4, 1.5, noise(rng, 1, 10, 1.6))                # matas secas / invierno
    dry_b = (rng.random(nid) < 0.07)[best['id']] | (rng.random(nid)[best['id']] < dry_reg * 0.45)
    bc_bl = np.where(dry_b[..., None], rgb(152, 140, 88) * rng.uniform(0.85, 1.1, (nid, 1)).astype(F)[best['id']], bc_bl)
    tip = clamp((np.abs(best['u']) - 0.6) / 0.4)                       # puntas más claras/secas
    bc_bl = mixc(bc_bl, rgb(158, 150, 96), tip * 0.35)
    bc_bl = bc_bl * (0.8 + 0.35 * clamp(bz / 2.2))[..., None]          # las de arriba reciben más luz
    soil = rgb(92, 78, 62) * (1 + 0.12 * noise(rng, 6, 300, 1.0))[..., None]
    soil = mixc(soil, rgb(122, 110, 92), sstep(0.5, 1.8, noise(rng, 30, 400, 1.0)) * 0.5)  # tosca/piedritas
    thatch = rgb(96, 98, 60) * (1 + 0.1 * noise(rng, 80, 1024, 0.6))[..., None]             # colchón de pasto
    under = mixc(soil, thatch, sstep(-1.2, 0.4, noise(rng, 10, 200, 1.1)) * (0.5 + 0.5 * dens))
    col = mixc(under, bc_bl, blade)
    ccol = rgb(70, 104, 46) * (1 + 0.1 * noise(rng, 20, 200, 1.0))[..., None]
    col = mixc(col, ccol * (0.85 + 0.3 * clamp(cb['z'] - 1.2))[..., None], clover_top.astype(F))
    col = col * (0.72 + 0.28 * ao)[..., None]
    col = col * (1 + 0.06 * noise(rng, 1, 6, 1.5))[..., None]
    bc = clamp(col)

    rough = np.where(blade > 0, 0.74, 0.94) + 0.04 * noise(rng, 30, 800, 0.6) + 0.1 * dry_reg * blade
    rough = clamp(rough - 0.05 * clover_top, 0.65, 0.97)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# TIERRA — tierra/barro seco del baldío y canteros: terrones, grietas de secado, piedritas,
# pedazos de ladrillo y tosca (relleno típico del conurbano), ramitas
# ----------------------------------------------------------------------------
def gen_tierra(seed=1313):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Tierra']
    px = T / N
    yy, xx = grid()
    h = noise(rng, 1, 12, 1.8) * 0.5 + noise(rng, 12, 200, 1.2) * 0.08 + noise(rng, 200, 1024, 0.5) * 0.02
    low = sstep(0.2, -0.8, noise(rng, 1, 8, 1.7))                    # bajos donde se junta agua
    # grietas de secado (polígonos) sólo en los bajos
    w1 = noise(rng, 8, 120, 1.2) * 5
    w2 = noise(rng, 8, 120, 1.2) * 5
    Fa, Fb, _ = worley(rng, 26)
    ed = warp(Fb - Fa, w1, w2)
    cracks = sstep(0.03, 0.005, ed) * low * sstep(-0.4, 0.6, noise(rng, 10, 100, 1.0))
    # placas levemente curvadas hacia arriba en los bordes (barro seco)
    curl = sstep(0.25, 0.0, ed) * low * 0.12
    h += curl - cracks * 0.6
    # terrones
    clod, _ = pebbles(rng, 45, 0.25, 0.25, 0.45, 6)
    h += clod * 0.35 * (1 - low)
    # piedritas: granza fina, piedras chicas y alguna grande
    p1, id1 = pebbles(rng, 330, 0.3, 0.2, 0.42, 2)
    p2, id2 = pebbles(rng, 95, 0.12, 0.25, 0.45, 3)
    p3, id3 = pebbles(rng, 28, 0.05, 0.22, 0.38, 4)
    stone = np.maximum(np.maximum(p1 * 0.12, p2 * 0.5), p3 * 1.4)
    h = np.maximum(h, h * 0.6 + stone)
    # ramitas
    lines = []
    for _ in range(26):
        p0 = rng.uniform(0, N, 2)
        lines.append((crack_path(rng, p0, rng.uniform(4, 18) / px, 1.2 / px, rng.uniform(0, 6.28), 0.15), 1))
    twig = gblur(draw_polylines(lines), 1.2)
    twig = clamp(twig * 2.5)
    h += twig * 0.25
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.25, 0.9, 3.0], 1.0)
    conv = convexity(h, px, 0.5)

    # color: tierra negra pampeana seca (pardo grisáceo), más oscura y húmeda en los bajos
    base = mixc(np.ones((N, N, 3), F) * rgb(118, 101, 82), np.ones((N, N, 3), F) * rgb(138, 122, 100),
                sstep(-1.0, 1.0, noise(rng, 2, 40, 1.4)))
    base = base * (1 + 0.07 * noise(rng, 40, 800, 0.7))[..., None]
    base = mixc(base, rgb(92, 78, 62), low * 0.35)
    base = mixc(base, rgb(150, 136, 114), clamp(conv * 2.0) * (1 - low) * 0.5)   # costra seca más clara
    base = mixc(base, rgb(60, 50, 42), cracks * 0.8)
    # piedras: grises, tosca blanquecina y pedazos de ladrillo
    def stone_cols(n):
        t = rng.random(n)
        c = np.where((t < 0.55)[:, None], rgb(128, 124, 116), np.where((t < 0.8)[:, None], rgb(176, 164, 140), rgb(150, 86, 62)))
        return (c * rng.uniform(0.8, 1.15, (n, 1))).astype(F)
    col = mixc(base, stone_cols(330 * 330)[id1], sstep(0.05, 0.35, p1) * 0.8)
    col = mixc(col, stone_cols(95 * 95)[id2], sstep(0.05, 0.3, p2))
    col = mixc(col, stone_cols(28 * 28)[id3], sstep(0.05, 0.25, p3))
    col = mixc(col, rgb(84, 66, 50), twig * 0.85)
    col = col * (0.6 + 0.4 * ao)[..., None]
    col = col * (1 + 0.05 * noise(rng, 1, 5, 1.5))[..., None]
    bc = clamp(col)

    stones_m = clamp(sstep(0.05, 0.3, p2) + sstep(0.05, 0.25, p3) + sstep(0.05, 0.35, p1) * 0.5)
    rough = 0.93 + 0.03 * noise(rng, 20, 800, 0.6) - 0.12 * stones_m - 0.08 * low + 0.02 * (1 - ao)
    rough = clamp(rough, 0.72, 0.98)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# BALASTO — piedra partida granítica de vía (3-6 cm), angulosa, manchada de óxido de frenos
# ----------------------------------------------------------------------------
def gen_balasto(seed=1414):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Balasto']
    px = T / N
    yy, xx = grid()
    layers = []
    # tres capas de piedras: atrás (más baja) -> adelante; aristas = medial axis de Voronoi (facetas)
    for C, z0, amp in ((26, -1.5, 3.2), (30, 0.0, 3.0), (60, -2.6, 1.6)):
        wxl = noise(rng, 4, 40, 1.4) * 14 + noise(rng, 40, 160, 1.0) * 2.0
        wyl = noise(rng, 4, 40, 1.4) * 14 + noise(rng, 40, 160, 1.0) * 2.0
        F1, F2, cid = worley(rng, C, 0.95, xx + wxl, yy + wyl)
        e = F2 - F1
        nc = C * C
        keep = (rng.random(nc) < (0.62 if C < 50 else 1.0))[cid]
        # pirámide de facetas + leve redondeo + inclinación por piedra
        prof = np.sqrt(clamp(e / per_cell(rng, nc, 0.35, 0.6)[cid])) * 0.35 + clamp(e * 1.6) * 0.65
        hl = z0 + per_cell(rng, nc, -0.6, 0.6)[cid] + amp * prof
        hl = np.where(keep, hl, -9.0)
        layers.append((hl, cid, e, nc))
    h = np.full((N, N), -4.0, F)
    sel = np.full((N, N), -1, np.int32)
    for i, (hl, _, _, _) in enumerate(layers):
        upd = hl > h
        h = np.where(upd, hl, h)
        sel = np.where(upd, i, sel)
    # textura de fractura (grano) y astillado en aristas
    h += noise(rng, 200, 1024, 0.5) * 0.015 + noise(rng, 15, 90, 1.4) * 0.06
    h = gblur(h, 1.2).astype(F)

    ao = cavity_ao(h, px, [0.4, 1.5, 4.0], 1.0)
    conv = convexity(h, px, 0.5)

    col = np.zeros((N, N, 3), F)
    for i, (hl, cid, e, nc) in enumerate(layers):
        v = rng.uniform(0.4, 0.66, nc)
        tint = np.where((rng.random(nc) < 0.25)[:, None], rgb(255, 232, 222), rgb(250, 250, 255))
        dark = rng.random(nc) < 0.12
        c = (v[:, None] * tint).astype(F)
        c[dark] *= 0.55                                        # alguna piedra basáltica oscura
        col = np.where((sel == i)[..., None], c[cid], col)
    gr = noise(rng, 300, 1024, 0.2)
    col = col * (1 + 0.06 * gr)[..., None]                       # grano del granito
    spk = sstep(1.6, 2.4, noise(rng, 400, 1024, 0.1))
    col = mixc(col, rgb(52, 50, 50), spk * 0.35)                  # biotita
    col = mixc(col, rgb(225, 215, 205), sstep(1.8, 2.6, noise(rng, 400, 1024, 0.1)) * 0.4)  # feldespato
    col = col * (1 + np.clip(conv, 0, 0.3)[..., None] * 0.6)
    # óxido de frenos y polvo: pardo rojizo en general, más en las cavidades
    rust = sstep(-0.6, 1.4, noise(rng, 1, 8, 1.6)) * 0.4 + clamp((1 - ao) * 1.3) * 0.4
    col = mixc(col, rgb(108, 74, 52), clamp(rust))
    col = col * (0.55 + 0.45 * ao)[..., None]
    col = col * (1 + 0.05 * noise(rng, 1, 5, 1.5))[..., None]
    bc = clamp(col)

    rough = 0.8 + 0.05 * noise(rng, 30, 800, 0.6) + 0.08 * clamp(rust) + 0.04 * (1 - ao)
    rough = clamp(rough, 0.68, 0.96)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# RIEL — acero de vía: costado oxidado con cascarilla, picaduras y vetas longitudinales (eje u = largo del riel);
# la cabeza pulida la pone el material (PolishTop) según la normal de mundo
# ----------------------------------------------------------------------------
def gen_riel(seed=1515):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Riel']
    px = T / N
    yy, xx = grid()
    h = noise(rng, 1, 10, 1.6) * 0.03
    # vetas a lo largo (ex > 1 alarga en x = eje u) y laminado
    streak = noise(rng, 2, 400, 1.0, ex=14.0)
    h += streak * 0.004
    # óxido en costra: escamas levantadas
    scale_n = noise(rng, 8, 300, 1.2) + 0.3 * noise(rng, 100, 1024, 0.7)
    flake = sstep(0.4, 0.9, scale_n)
    h += flake * 0.03 + noise(rng, 150, 1024, 0.6) * 0.006 * flake
    # picaduras
    pit, _ = pebbles(rng, 260, 0.25, 0.15, 0.4)
    h -= pit * 0.02
    # zonas de acero visible (golpes, roce de pestañas) y cascarilla de laminación
    bare = sstep(1.3, 1.9, noise(rng, 2, 80, 1.2, ex=6.0)) * (1 - flake)
    mill = sstep(-0.2, 0.8, noise(rng, 2, 40, 1.4)) * (1 - bare)
    h = h.astype(F)

    ao = cavity_ao(h, px, [0.1, 0.4, 1.5], 0.8)

    rust_a = np.ones((N, N, 3), F) * rgb(112, 66, 40)
    rust_b = np.ones((N, N, 3), F) * rgb(78, 48, 32)
    col = mixc(rust_a, rust_b, sstep(-1.0, 1.0, noise(rng, 6, 300, 1.0) + 0.5 * streak))
    col = mixc(col, rgb(138, 84, 50), flake * sstep(0, 1, noise(rng, 50, 600, 0.8)) * 0.6)   # óxido fresco
    col = mixc(col, rgb(62, 60, 60), mill * 0.55)                                             # cascarilla
    col = mixc(col, rgb(150, 150, 152), bare)                                                  # acero
    col = mixc(col, rgb(48, 34, 26), pit * 0.7)
    grease = sstep(1.0, 2.0, noise(rng, 2, 60, 1.3, ex=5.0)) * 0.5
    col = mixc(col, rgb(36, 32, 30), grease)                                                   # grasa/hollín
    col = col * (0.75 + 0.25 * ao)[..., None]
    bc = clamp(col)

    metal = clamp(bare + mill * 0.25 - grease * 0.3)
    rough = 0.86 + 0.04 * noise(rng, 20, 800, 0.6) - 0.5 * bare - 0.22 * mill - 0.3 * grease + 0.04 * flake
    rough = clamp(rough, 0.3, 0.96)
    return bc, h, px, 1.0, ao, rough, metal


# ----------------------------------------------------------------------------
# FOLLAJE — masa de hojas para copas lejanas (fresno/plátano): hojas en capas, huecos oscuros
# ----------------------------------------------------------------------------
def gen_follaje(seed=1616):
    rng = np.random.default_rng(seed)
    T = TILE_CM['Follaje']
    px = T / N
    yy, xx = grid()
    best = None
    # 4 capas de hojas lanceoladas (folíolos de fresno ~8 x 3 cm), de atrás hacia adelante
    for i in range(4):
        best = stamp_layer(rng, 36, T, (2.6, 4.0), (1.0, 1.6), keep=0.78 + 0.05 * i, angle=None,
                           taper=0.9, z_range=(i * 1.3, i * 1.3 + 1.4), best=best)
    leaf = best['m']
    z = np.where(leaf > 0, best['z'], -2.0)
    v = best['v']
    u = best['u']
    # perfil de hoja: cúpula + nervadura central hundida + leve curvatura a lo largo
    hl = z + np.sqrt(clamp(1 - v * v)) * 0.35 - np.exp(-(v / 0.09) ** 2) * 0.12 - u * u * 0.2
    h = np.where(leaf > 0, hl, -2.5 + noise(rng, 20, 300, 1.0) * 0.3)
    h = gblur(h.astype(F), 0.7)

    ao = cavity_ao(h, px, [0.5, 1.5, 4.0], 1.2)

    nid = best['next_id'] + 1
    pal = np.array([rgb(62, 88, 40), rgb(76, 102, 46), rgb(54, 78, 36), rgb(90, 112, 52), rgb(70, 96, 50)])
    lc = pal[rng.integers(0, len(pal), nid)] * rng.uniform(0.85, 1.15, (nid, 1)).astype(F)
    yel = rng.random(nid) < 0.06
    lc[yel] = rgb(140, 128, 60) * rng.uniform(0.85, 1.1, (yel.sum(), 1))
    col = lc[best['id']]
    col = mixc(col, rgb(112, 130, 70), np.exp(-(v / 0.08) ** 2) * leaf * 0.35)        # nervadura más clara
    col = col * (0.8 + 0.25 * clamp(z / 5.0))[..., None]                                 # capas de arriba más claras
    gap = rgb(22, 30, 18)
    col = mixc(np.ones((N, N, 3), F) * gap, col, leaf)
    col = col * (0.5 + 0.5 * ao)[..., None]
    col = col * (1 + 0.08 * noise(rng, 1, 6, 1.5))[..., None]
    bc = clamp(col)

    rough = np.where(leaf > 0, 0.62, 0.9) + 0.05 * noise(rng, 20, 600, 0.7)
    rough = clamp(rough, 0.5, 0.95)
    metal = np.zeros((N, N), F)
    return bc, h, px, 1.0, ao, rough, metal


# ============================================================================
# v4: CARTELES CON TEXTO (atlas UV, no tileables)
# ----------------------------------------------------------------------------
# Salida: textures/Carteles/
#   T_Carteles_Calle_BC.png / _ORM.png       2048x2048  (16 placas de calle 1024x256, 4:1)
#   T_Carteles_Comercio_BC.png / _ORM.png    2048x4096  (16 marquesinas 2048x256, 8:1)
#   T_Carteles_Varios_BC.png (RGBA) / _ORM   2048x2048  (comisaría, estación, salidas, afiches, bandera, pintadas)
#   T_Carteles_N.png                         256x256    normal plana (128,128,255), compartida por los tres atlas
#   carteles_atlas.json                      manifiesto: MI -> atlas, rectángulo en px y en UV
#   preview_carteles.jpg                     hoja de revisión
# Cada cartel ocupa un rectángulo del atlas; la malla mapea su cara de texto a UV0 0..1 y el material
# (M_Barrio_Cartel) remapea UV' = AtlasRect.xy + UV0 * AtlasRect.zw. Alfa del atlas Varios = máscara (pintadas).
# Todo inventado: nombres de comercio ficticios, sin marcas, logos, escudos ni cruces de farmacia; las calles son
# nombres reales de Caseros sobre una placa municipal genérica (azul, letras blancas, sin escudo).
# ============================================================================
CARTELES_DIR = os.path.join(OUT, 'Carteles')

_FONT_DIRS = ['/usr/share/fonts/truetype', '/usr/share/fonts/opentype', '/usr/share/fonts',
              os.path.expanduser('~/.fonts'), os.path.expanduser('~/.local/share/fonts'),
              'C:/Windows/Fonts']
# Familias libres (OFL / GPL+FE / Liberation). Se usa la primera que exista; si no hay ninguna, la de Pillow.
FUENTES = {
    'calle':   ['LiberationSans-Bold.ttf', 'DejaVuSansCondensed-Bold.ttf', 'FreeSansBold.ttf', 'arialbd.ttf'],
    'calle_n': ['LiberationSansNarrow-Bold.ttf', 'DejaVuSansCondensed-Bold.ttf', 'FreeSansBold.ttf'],
    'display': ['Anton-Regular.ttf', 'LiberationSansNarrow-Bold.ttf', 'DejaVuSansCondensed-Bold.ttf'],
    'negra':   ['ArchivoBlack-Regular.ttf', 'FiraSans-Black.ttf', 'DejaVuSans-Bold.ttf'],
    'fira':    ['FiraSans-ExtraBold.ttf', 'FiraSans-Bold.ttf', 'DejaVuSans-Bold.ttf'],
    'fira_it': ['FiraSans-BlackItalic.ttf', 'FiraSans-BoldItalic.ttf', 'DejaVuSans-BoldOblique.ttf'],
    'serif':   ['DejaVuSerifCondensed-Bold.ttf', 'DejaVuSerif-Bold.ttf', 'LiberationSerif-Bold.ttf'],
    'serif_it': ['DejaVuSerifCondensed-BoldItalic.ttf', 'LiberationSerif-BoldItalic.ttf', 'DejaVuSerif-Bold.ttf'],
    'mano':    ['ComicRelief-Bold.ttf', 'DejaVuSans-Bold.ttf'],
    'chica':   ['DejaVuSansCondensed-Bold.ttf', 'LiberationSansNarrow-Bold.ttf', 'FreeSansBold.ttf'],
}
_FONT_CACHE = {}


def _font_path(estilo):
    if estilo in _FONT_CACHE:
        return _FONT_CACHE[estilo]
    found = None
    for fname in FUENTES[estilo]:
        for d in _FONT_DIRS:
            if not os.path.isdir(d):
                continue
            for root, _dirs, files in os.walk(d):
                if fname in files:
                    found = os.path.join(root, fname)
                    break
            if found:
                break
        if found:
            break
    if not found:
        log(f'AVISO: no hay fuente para "{estilo}" ({FUENTES[estilo]}); uso la de Pillow')
    _FONT_CACHE[estilo] = found
    return found


def _font(estilo, size):
    p = _font_path(estilo)
    if p:
        return ImageFont.truetype(p, int(size))
    try:
        return ImageFont.load_default(size=int(size))
    except TypeError:
        return ImageFont.load_default()


def _fit(draw, text, estilo, max_w, max_h, start=None):
    """Tamaño de fuente más grande que entra en max_w x max_h (alto = caja de tinta)."""
    lo, hi = 6, int(start or max_h * 1.6)
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        b = draw.textbbox((0, 0), text, font=_font(estilo, mid))
        if b[2] - b[0] <= max_w and b[3] - b[1] <= max_h:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return _font(estilo, best)


def _text_c(draw, text, estilo, cx, cy, max_w, max_h, fill, stroke=0, stroke_fill=None):
    """Texto centrado (caja de tinta centrada en cx, cy) ajustado a max_w x max_h."""
    f = _fit(draw, text, estilo, max_w, max_h)
    b = draw.textbbox((0, 0), text, font=f)
    x = cx - (b[0] + b[2]) * 0.5
    y = cy - (b[1] + b[3]) * 0.5
    draw.text((x, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return f


def _hx(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _ruido2(rng, h, w, sigma, ay=1.0, ax=1.0):
    """Ruido suave no periódico (gauss de ruido blanco), normalizado media 0 desvío 1."""
    a = rng.standard_normal((h, w)).astype(F)
    a = ndi.gaussian_filter(a, (max(sigma * ay, 0.5), max(sigma * ax, 0.5)), mode='reflect')
    a -= a.mean()
    a /= (a.std() + 1e-8)
    return a


def _desgaste(rgb8, rng, sol=0.3, mugre=0.3, oxido=0.2, chapa=True, rayas=0.3, rough_base=0.48, tela=False):
    """Intemperie de un cartel (sRGB uint8 -> bc float, ao, rough, metal).
    sol: decoloración (los rojos se van a rosa, todo se aclara y pierde saturación) con manchas grandes.
    mugre: chorreaduras verticales desde el borde superior y polvo en el borde inferior.
    oxido: manchas de óxido que nacen en bordes y agujeros de bulones (solo chapa).
    chapa: saltaduras de pintura que dejan ver acero (metálico) o fondo; tela=True: sin metal, rugoso."""
    h, w = rgb8.shape[:2]
    c = rgb8.astype(F) / 255.0
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    s = min(h, w)
    # --- sol: más fuerte arriba (más expuesto) y en manchas grandes
    if sol > 0:
        f = clamp(0.55 + 0.25 * _ruido2(rng, h, w, s * 0.6) + 0.25 * (1.0 - yy / h)) * sol
        L = (c * np.array([0.2126, 0.7152, 0.0722], F)).sum(-1, keepdims=True)
        des = lerp(c, L, 0.55)
        des = des + (1.0 - des) * 0.35                       # se "lava" hacia el blanco
        des[..., 0] = des[..., 0] * 1.0
        des[..., 2] = des[..., 2] * 0.97                     # leve amarilleo del barniz
        c = lerp(c, des, f[..., None])
    # --- mugre: chorreaduras (columnas finas alargadas) y polvo abajo
    dirt = np.zeros((h, w), F)
    if mugre > 0:
        col = clamp((_ruido2(rng, h, w, s * 0.05, ay=12.0, ax=1.0) - 0.4) * 0.7)
        topw = clamp(1.0 - yy / (h * 0.9)) ** 0.7
        dirt += col * topw * 0.8
        dirt += clamp(1.0 - (h - yy) / (h * 0.18)) * 0.5 * clamp(0.6 + 0.4 * _ruido2(rng, h, w, s * 0.1))
        dirt += clamp(_ruido2(rng, h, w, s * 0.02) * 0.25)
        dirt = clamp(dirt * mugre)
        c = lerp(c, c * np.array([0.52, 0.47, 0.40], F), dirt[..., None])
    # --- óxido: bordes + bulones
    rust = np.zeros((h, w), F)
    metal = np.zeros((h, w), F)
    if chapa and oxido > 0:
        edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
        ed = clamp(1.0 - edge / (s * 0.12))
        holes = np.zeros((h, w), F)
        for (hx_, hy_) in ((s * 0.09, h * 0.5), (w - s * 0.09, h * 0.5)):
            d = np.sqrt((xx - hx_) ** 2 + (yy - hy_) ** 2)
            holes = np.maximum(holes, clamp(1.0 - d / (s * 0.16)))
            # chorreadura de óxido bajo el bulón
            under = clamp(1.0 - np.abs(xx - hx_) / (s * 0.035)) * clamp((yy - hy_) / (h * 0.5)) * \
                (yy > hy_) * clamp(1.0 - (yy - hy_) / (h * 0.6))
            holes = np.maximum(holes, under * 0.8)
        n = _ruido2(rng, h, w, s * 0.04) * 0.6 + _ruido2(rng, h, w, s * 0.012) * 0.4
        rust = clamp((np.maximum(ed, holes) * 1.3 + n * 0.45 - 0.75) * 2.5) * oxido
        rc = np.stack([0.40 + 0.08 * n, 0.20 + 0.04 * n, 0.09 + 0.02 * n], -1).astype(F)
        c = lerp(c, clamp(rc), rust[..., None])
        # bulones (gris oscuro)
        for (hx_, hy_) in ((s * 0.09, h * 0.5), (w - s * 0.09, h * 0.5)):
            d = np.sqrt((xx - hx_) ** 2 + (yy - hy_) ** 2)
            m = clamp((s * 0.035 - d) / 1.5)
            c = lerp(c, np.array([0.30, 0.29, 0.27], F) * (0.7 + 0.3 * clamp(1 - d / (s * 0.035)))[..., None], m[..., None])
            metal = np.maximum(metal, m * 0.8)
    # --- saltaduras: manchitas donde se ve el acero o la imprimación
    if chapa and rayas > 0:
        # agrupadas cerca de los bordes y en manchones (no un "granito" parejo), en dos tamaños
        edge2 = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy))
        grupo = clamp(_ruido2(rng, h, w, s * 0.25) * 0.6 + clamp(1.0 - edge2 / (s * 0.25)) * 1.2 - 0.55)
        ch = clamp((_ruido2(rng, h, w, s * 0.008) - (2.7 - 0.8 * rayas)) * 3.0)
        ch = np.maximum(ch, clamp((_ruido2(rng, h, w, s * 0.02) - (2.9 - 0.8 * rayas)) * 4.0))
        ch = ch * grupo
        c = lerp(c, np.array([0.55, 0.55, 0.56], F), ch[..., None])
        metal = np.maximum(metal, ch)
        # rayones finos horizontales-diagonales
        img = Image.new('L', (w, h), 0)
        dr = ImageDraw.Draw(img)
        for _ in range(int(rayas * 40)):
            x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
            a = rng.uniform(-0.5, 0.5)
            L_ = rng.uniform(0.05, 0.25) * w
            dr.line([(x0, y0), (x0 + L_ * np.cos(a), y0 + L_ * np.sin(a))], fill=int(rng.uniform(60, 160)), width=1)
        sc = np.asarray(img, F) / 255.0
        c = lerp(c, clamp(c + 0.18), sc[..., None])
    if tela:
        weave = (np.sin(xx * 1.9) * np.sin(yy * 1.9)) * 0.02
        c = clamp(c * (1.0 + weave[..., None]))
    # --- grano de pintura muy leve (que no se vea "vectorial")
    c = clamp(c * (1.0 + 0.025 * _ruido2(rng, h, w, 1.2))[..., None])
    ao = clamp(1.0 - dirt * 0.25 - rust * 0.1)
    rough = rough_base + 0.12 * (sol > 0) * clamp(0.5 + 0.2 * _ruido2(rng, h, w, s * 0.3)) + dirt * 0.25 + rust * 0.4
    rough = np.where(metal > 0.5, 0.42, rough)
    if tela:
        rough = np.full((h, w), 0.88, F)
        metal[:] = 0.0
    return clamp(c), ao.astype(F), clamp(rough, 0.05, 1.0).astype(F), clamp(metal).astype(F)


# ---------------------------------------------------------------------------- dibujantes por tipo de cartel
def _canvas(w, h, bg):
    im = Image.new('RGB', (w, h), _hx(bg) if isinstance(bg, str) else bg)
    return im, ImageDraw.Draw(im)


def _rr(dr, box, r, fill=None, outline=None, width=1):
    dr.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def dib_calle(w, h, nombre, rng):
    """Placa municipal genérica: azul, filete blanco redondeado, nombre en blanco (sin escudo)."""
    im, dr = _canvas(w, h, '#1D4E96')
    m = int(h * 0.075)
    _rr(dr, (m, m, w - m, h - m), int(h * 0.09), outline=_hx('#F2F2EE'), width=max(3, int(h * 0.028)))
    # Altura de letra FIJA para toda la serie (como una placa municipal): se mide con 'ÁHg' y solo se achica
    # (o se pasa a la variante angosta) si el nombre no entra a lo ancho.
    maxw = w - 6 * m
    estilo = 'calle'
    f = _fit(dr, 'ÁHg', estilo, 10 * w, h * 0.56)
    if dr.textbbox((0, 0), nombre, font=f)[2] > maxw:
        estilo = 'calle_n'
        f = _fit(dr, 'ÁHg', estilo, 10 * w, h * 0.56)
    size = f.size
    while size > 8 and dr.textbbox((0, 0), nombre, font=_font(estilo, size))[2] > maxw:
        size -= 2
    f = _font(estilo, size)
    b = dr.textbbox((0, 0), 'Hx', font=f)       # centrado por la altura de mayúscula, no por la tinta del nombre
    x = w * 0.5 - dr.textlength(nombre, font=f) * 0.5
    y = h * 0.5 - (b[1] + b[3]) * 0.5
    dr.text((x, y), nombre, font=f, fill=_hx('#F4F4F0'))
    return im


def _ico(dr, kind, cx, cy, r, col, col2):
    """Iconos simples dibujados (nada de logos)."""
    if kind == 'fruta':
        dr.ellipse((cx - r, cy - r * 0.9, cx + r, cy + r), fill=col)
        dr.polygon([(cx, cy - r * 0.8), (cx + r * 0.7, cy - r * 1.4), (cx + r * 0.2, cy - r * 0.7)], fill=col2)
    elif kind == 'porcion':
        dr.polygon([(cx - r, cy - r * 0.8), (cx + r, cy - r * 0.8), (cx, cy + r)], fill=col)
        dr.rectangle((cx - r, cy - r * 0.95, cx + r, cy - r * 0.7), fill=col2)
        for (ox, oy) in ((-0.35, -0.4), (0.3, -0.35), (0.0, 0.15)):
            dr.ellipse((cx + ox * r - r * 0.13, cy + oy * r - r * 0.13, cx + ox * r + r * 0.13, cy + oy * r + r * 0.13),
                       fill=col2)
    elif kind == 'tornillo':
        dr.polygon([(cx - r * 0.7, cy - r), (cx + r * 0.7, cy - r), (cx + r * 0.7, cy - r * 0.55),
                    (cx - r * 0.7, cy - r * 0.55)], fill=col)
        dr.rectangle((cx - r * 0.22, cy - r * 0.55, cx + r * 0.22, cy + r * 0.8), fill=col)
        for k_ in range(5):
            y = cy - r * 0.45 + k_ * r * 0.25
            dr.line([(cx - r * 0.32, y), (cx + r * 0.32, y + r * 0.1)], fill=col2, width=max(2, int(r * 0.07)))
        dr.polygon([(cx - r * 0.22, cy + r * 0.8), (cx + r * 0.22, cy + r * 0.8), (cx, cy + r)], fill=col)
    elif kind == 'espiga':
        dr.line([(cx, cy + r), (cx, cy - r)], fill=col, width=max(2, int(r * 0.1)))
        for k_ in range(4):
            y = cy - r * 0.7 + k_ * r * 0.4
            for sgn in (-1, 1):
                dr.ellipse((cx + sgn * r * 0.05 - (r * 0.32 if sgn < 0 else 0), y - r * 0.15,
                            cx + sgn * r * 0.05 + (r * 0.32 if sgn > 0 else 0), y + r * 0.15), fill=col)
    elif kind == 'tijera':
        for sgn in (-1, 1):
            dr.ellipse((cx + sgn * r * 0.45 - r * 0.28, cy + r * 0.35, cx + sgn * r * 0.45 + r * 0.28, cy + r * 0.9),
                       outline=col, width=max(2, int(r * 0.12)))
            dr.line([(cx + sgn * r * 0.35, cy + r * 0.4), (cx - sgn * r * 0.45, cy - r)], fill=col,
                    width=max(2, int(r * 0.14)))
    elif kind == 'estrella':
        pts = []
        for k_ in range(10):
            a = -np.pi / 2 + k_ * np.pi / 5
            rr = r if k_ % 2 == 0 else r * 0.45
            pts.append((cx + rr * np.cos(a), cy + rr * np.sin(a)))
        dr.polygon(pts, fill=col)
    elif kind == 'gota':
        dr.ellipse((cx - r * 0.7, cy - r * 0.2, cx + r * 0.7, cy + r), fill=col)
        dr.polygon([(cx - r * 0.62, cy + r * 0.15), (cx + r * 0.62, cy + r * 0.15), (cx, cy - r)], fill=col)
    elif kind == 'rayo':
        dr.polygon([(cx + r * 0.2, cy - r), (cx - r * 0.55, cy + r * 0.1), (cx - r * 0.05, cy + r * 0.1),
                    (cx - r * 0.25, cy + r), (cx + r * 0.55, cy - r * 0.15), (cx + r * 0.05, cy - r * 0.15)], fill=col)


def dib_comercio(w, h, spec, rng):
    """Marquesina de chapa pintada 8:1. spec: dict(bg, fg, titulo, estilo, sub, fg2, borde, franja, ico)."""
    im, dr = _canvas(w, h, spec['bg'])
    fg = _hx(spec['fg'])
    fg2 = _hx(spec.get('fg2', spec['fg']))
    if spec.get('franja'):
        fr = _hx(spec['franja'])
        dr.rectangle((0, 0, w, int(h * 0.11)), fill=fr)
        dr.rectangle((0, h - int(h * 0.11), w, h), fill=fr)
    if spec.get('borde'):
        m = int(h * 0.16)
        dr.rectangle((m, m, w - m, h - m), outline=_hx(spec['borde']), width=max(3, int(h * 0.025)))
    ico = spec.get('ico')
    x0, x1 = w * 0.06, w * 0.94
    if ico:
        r = h * 0.28
        for cx in (w * 0.075, w * 0.925):
            _ico(dr, ico, cx, h * 0.5, r, fg2, _hx(spec['bg']))
        x0, x1 = w * 0.14, w * 0.86
    sub = spec.get('sub')
    if sub:
        _text_c(dr, spec['titulo'], spec['estilo'], w * 0.5, h * 0.40, x1 - x0, h * 0.44, fg,
                stroke=spec.get('stroke', 0), stroke_fill=_hx(spec.get('stroke_col', spec['bg'])))
        _text_c(dr, sub, 'chica', w * 0.5, h * 0.79, (x1 - x0) * 0.8, h * 0.13, fg2)
    else:
        _text_c(dr, spec['titulo'], spec['estilo'], w * 0.5, h * 0.5, x1 - x0, h * 0.56, fg,
                stroke=spec.get('stroke', 0), stroke_fill=_hx(spec.get('stroke_col', spec['bg'])))
    return im


def dib_comisaria(w, h, rng):
    """Comisaría ficticia: chapa blanca, letras azul oscuro, franjas celeste-azul (sin escudo ni insignias)."""
    im, dr = _canvas(w, h, '#EDEDE8')
    dr.rectangle((0, 0, w, int(h * 0.12)), fill=_hx('#1C3566'))
    dr.rectangle((0, h - int(h * 0.12), w, h), fill=_hx('#1C3566'))
    dr.rectangle((0, int(h * 0.12), w, int(h * 0.16)), fill=_hx('#6FA3D6'))
    dr.rectangle((0, h - int(h * 0.16), w, h - int(h * 0.12)), fill=_hx('#6FA3D6'))
    _text_c(dr, 'DESTACAMENTO CASEROS', 'calle', w * 0.5, h * 0.44, w * 0.86, h * 0.36, _hx('#1C3566'))
    _text_c(dr, 'ATENCIÓN AL PÚBLICO LAS 24 HS', 'chica', w * 0.5, h * 0.73, w * 0.5, h * 0.1, _hx('#1C3566'))
    return im


def dib_estacion(w, h, rng):
    """Cartel de andén genérico: esmalte crema, letras negras, filete bordó (sin logos de operadoras)."""
    im, dr = _canvas(w, h, '#E9E3D2')
    m = int(h * 0.08)
    dr.rectangle((m, m, w - m, h - m), outline=_hx('#5E1F1D'), width=max(4, int(h * 0.04)))
    _text_c(dr, 'CASEROS', 'calle', w * 0.5, h * 0.5, w * 0.6, h * 0.55, _hx('#151515'))
    return im


def _flecha(dr, cx, cy, s, d, col):
    """Flecha gruesa: d = 'arriba' | 'der' | 'izq'."""
    shaft = [(-0.18, 0.95), (0.18, 0.95), (0.18, -0.1), (0.5, -0.1), (0.0, -0.95), (-0.5, -0.1), (-0.18, -0.1)]
    out = []
    for (x, y) in shaft:
        if d == 'der':
            x, y = -y, x
        elif d == 'izq':
            x, y = y, -x
        out.append((cx + x * s, cy + y * s))
    dr.polygon(out, fill=col)


def dib_salida(w, h, d, rng):
    """Cartel diegético común a las tres salidas: verde vial, 'SALIDA' + flecha (variantes por dirección)."""
    im, dr = _canvas(w, h, '#1B6236')
    m = int(h * 0.07)
    _rr(dr, (m, m, w - m, h - m), int(h * 0.08), outline=_hx('#F0F0EA'), width=max(3, int(h * 0.03)))
    s = h * 0.3
    if d == 'izq':
        _flecha(dr, w * 0.17, h * 0.5, s, 'izq', _hx('#F0F0EA'))
        _text_c(dr, 'SALIDA', 'calle', w * 0.6, h * 0.5, w * 0.6, h * 0.48, _hx('#F0F0EA'))
    elif d == 'der':
        _flecha(dr, w * 0.83, h * 0.5, s, 'der', _hx('#F0F0EA'))
        _text_c(dr, 'SALIDA', 'calle', w * 0.4, h * 0.5, w * 0.6, h * 0.48, _hx('#F0F0EA'))
    else:
        _flecha(dr, w * 0.15, h * 0.5, s, 'arriba', _hx('#F0F0EA'))
        _flecha(dr, w * 0.85, h * 0.5, s, 'arriba', _hx('#F0F0EA'))
        _text_c(dr, 'SALIDA', 'calle', w * 0.5, h * 0.5, w * 0.56, h * 0.48, _hx('#F0F0EA'))
    return im


def dib_no_estacionar(w, h, rng):
    """'NO ESTACIONAR' pintado a mano en chapa blanca (típico portón de garage)."""
    im, dr = _canvas(w, h, '#E8E6DF')
    _text_c(dr, 'NO ESTACIONAR', 'display', w * 0.5, h * 0.4, w * 0.86, h * 0.48, _hx('#B3201B'))
    _text_c(dr, 'ENTRADA DE VEHÍCULOS', 'mano', w * 0.5, h * 0.8, w * 0.62, h * 0.15, _hx('#1E1E1E'))
    return im


def dib_afiche(w, h, kind, rng):
    if kind == 'se_vende':
        im, dr = _canvas(w, h, '#C3261F')
        dr.rectangle((0, int(h * 0.62), w, h), fill=_hx('#F1EFE8'))
        _text_c(dr, 'SE', 'display', w * 0.5, h * 0.17, w * 0.5, h * 0.17, _hx('#F7F5EE'))
        _text_c(dr, 'VENDE', 'display', w * 0.5, h * 0.42, w * 0.86, h * 0.28, _hx('#F7F5EE'))
        _text_c(dr, 'DUEÑO', 'negra', w * 0.5, h * 0.73, w * 0.7, h * 0.1, _hx('#C3261F'))
        _text_c(dr, 'DIRECTO', 'negra', w * 0.5, h * 0.87, w * 0.7, h * 0.1, _hx('#C3261F'))
    else:
        im, dr = _canvas(w, h, '#F0C419')
        _text_c(dr, 'ALQUILO', 'display', w * 0.5, h * 0.32, w * 0.88, h * 0.3, _hx('#151515'))
        dr.rectangle((int(w * 0.08), int(h * 0.56), int(w * 0.92), int(h * 0.58)), fill=_hx('#151515'))
        _text_c(dr, 'LOCAL', 'negra', w * 0.5, h * 0.71, w * 0.5, h * 0.1, _hx('#151515'))
        _text_c(dr, 'INFORMES AQUÍ', 'chica', w * 0.5, h * 0.85, w * 0.7, h * 0.07, _hx('#151515'))
    return im


def dib_bandera(w, h, rng, sol=True):
    """Bandera argentina (símbolo patrio): franjas celeste #75AADB / blanca / celeste, Sol de Mayo simple."""
    im, dr = _canvas(w, h, '#75AADB')
    dr.rectangle((0, int(h / 3), w, int(2 * h / 3)), fill=_hx('#F6F6F2'))
    if sol:
        cx, cy = w * 0.5, h * 0.5
        r = h * 0.085
        col = _hx('#F2B632')
        for k_ in range(32):
            a = k_ * np.pi / 16
            if k_ % 2 == 0:       # rayos rectos
                p = [(cx + r * 1.05 * np.cos(a - 0.07), cy + r * 1.05 * np.sin(a - 0.07)),
                     (cx + r * 1.75 * np.cos(a), cy + r * 1.75 * np.sin(a)),
                     (cx + r * 1.05 * np.cos(a + 0.07), cy + r * 1.05 * np.sin(a + 0.07))]
            else:                 # rayos más cortos (versión simplificada de los flamígeros)
                p = [(cx + r * 1.05 * np.cos(a - 0.05), cy + r * 1.05 * np.sin(a - 0.05)),
                     (cx + r * 1.45 * np.cos(a), cy + r * 1.45 * np.sin(a)),
                     (cx + r * 1.05 * np.cos(a + 0.05), cy + r * 1.05 * np.sin(a + 0.05))]
            dr.polygon(p, fill=col)
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col, outline=_hx('#B5832A'), width=2)
    return im


def dib_pintada(w, h, rng):
    """Tag ilegible en aerosol (RGBA): trazos en bucle, contorno, salpicado y chorreaduras. Alfa = máscara."""
    S = 2
    W_, H_ = w * S, h * S
    pal = [('#141414', '#E8E8E8'), ('#C7C9CC', '#1A1A1A'), ('#B8241C', '#151515'), ('#2048A8', '#EDEDED'),
           ('#1C1C1C', None), ('#2E7D3A', '#111111')]
    fill, outl = pal[rng.integers(0, len(pal))]
    mask = Image.new('L', (W_, H_), 0)
    md = ImageDraw.Draw(mask)
    # 4-7 "letras": curvas de Catmull-Rom con bucles, encadenadas a lo ancho
    n = int(rng.integers(4, 8))
    x = W_ * 0.12
    base = H_ * rng.uniform(0.5, 0.62)
    slope = rng.uniform(-0.18, 0.12)
    width = int(H_ * rng.uniform(0.035, 0.06))
    strokes = []
    for i in range(n):
        cw = (W_ * 0.76) / n * rng.uniform(0.8, 1.2)
        pts = []
        for j in range(int(rng.integers(5, 9))):
            pts.append((x + rng.uniform(0, cw), base - rng.uniform(0.0, H_ * 0.33) + slope * (x - W_ * 0.5)
                        + rng.uniform(-H_ * 0.05, H_ * 0.12)))
        pts.sort(key=lambda p: p[0] + rng.uniform(-cw * 0.5, cw * 0.5))
        # suavizado Catmull-Rom
        P = np.array([pts[0]] + pts + [pts[-1]], float)
        curve = []
        for k_ in range(1, len(P) - 2):
            p0, p1, p2, p3 = P[k_ - 1], P[k_], P[k_ + 1], P[k_ + 2]
            for t in np.linspace(0, 1, 10):
                t2, t3 = t * t, t * t * t
                curve.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                                          (-p0 + 3 * p1 - 3 * p2 + p3) * t3)))
        strokes.append(curve)
        x += cw * rng.uniform(0.75, 0.95)
    # subrayado / flecha de firma
    strokes.append([(W_ * 0.1, base + H_ * 0.12), (W_ * 0.5, base + H_ * 0.16 + slope * 50), (W_ * 0.9, base + H_ * 0.08)])
    out_m = Image.new('L', (W_, H_), 0)
    od = ImageDraw.Draw(out_m)
    for c_ in strokes:
        od.line(c_, fill=255, width=width + int(H_ * 0.025), joint='curve')
    for c_ in strokes:
        md.line(c_, fill=255, width=width, joint='curve')
    # chorreaduras bajo los trazos
    for _ in range(int(rng.integers(4, 10))):
        c_ = strokes[int(rng.integers(0, len(strokes)))]
        p = c_[int(rng.integers(0, len(c_)))]
        L_ = rng.uniform(0.05, 0.25) * H_
        md.line([p, (p[0] + rng.uniform(-2, 2), p[1] + L_)], fill=255, width=max(2, int(width * 0.25)))
        md.ellipse((p[0] - width * 0.2, p[1] + L_ - width * 0.2, p[0] + width * 0.2, p[1] + L_ + width * 0.25), fill=255)
    m_in = np.asarray(mask, F) / 255.0
    m_out = np.asarray(out_m, F) / 255.0 if outl else np.zeros_like(m_in)
    # bordes de aerosol: desenfoque + salpicado
    m_in = ndi.gaussian_filter(m_in, 1.2 * S)
    m_out = ndi.gaussian_filter(m_out, 1.6 * S)
    spr = (rng.random(m_in.shape) < 0.02).astype(F) * clamp(ndi.gaussian_filter(m_in, 8 * S) * 3.0)
    m_in = clamp(m_in * 1.4 + spr)
    m_out = clamp(m_out * 1.4)
    fc = np.array(_hx(fill), F) / 255.0
    oc = np.array(_hx(outl), F) / 255.0 if outl else fc
    alpha = clamp(np.maximum(m_in, m_out))
    col = lerp(oc[None, None, :] * np.ones_like(m_in)[..., None], fc[None, None, :] * np.ones_like(m_in)[..., None],
               (m_in / (alpha + 1e-4))[..., None])
    # pintura gastada: el alfa se come en manchas (pared rugosa)
    wear = clamp(0.95 + 0.2 * _ruido2(rng, H_, W_, 10 * S))
    alpha = clamp(alpha * wear)
    rgba = np.concatenate([col, alpha[..., None]], -1)
    im = Image.fromarray(to8(rgba), 'RGBA').resize((w, h), Image.LANCZOS)
    return im


# ---------------------------------------------------------------------------- catálogo
CALLES = [  # (slug de la MI, texto)  — nombres reales de calles de Caseros
    ('ValentinGomez', 'Valentín Gómez'), ('Urquiza', 'Justo José de Urquiza'), ('AvSanMartin', 'Av. San Martín'),
    ('Ferreyra', 'Andrés Ferreyra'), ('Alberdi', 'Juan Bautista Alberdi'), ('Nicaragua', 'Nicaragua'),
    ('Sabattini', 'Sabattini'), ('Fischetti', 'Fischetti'), ('MarianoMoreno', 'Mariano Moreno'),
    ('EstebanMerlo', 'Esteban Merlo'), ('Bonifacini', 'Bonifacini'), ('Puan', 'Puan'), ('Rauch', 'Rauch'),
    ('MarcoPolo', 'Marco Polo'), ('Espana', 'España'), ('Constitucion', 'Constitución'),
]
COMERCIOS = [  # comercios INVENTADOS (sin marcas reales)
    ('AlmacenDonTito', dict(bg='#EFE6CC', fg='#8E1F1B', titulo='ALMACÉN DON TITO', estilo='serif',
                            sub='FIAMBRES · LÁCTEOS · BEBIDAS', fg2='#2B2B2B', franja='#8E1F1B')),
    ('Kiosco24hs', dict(bg='#F2C21B', fg='#151515', titulo='KIOSCO 24 HS', estilo='display',
                        sub='GOLOSINAS · BEBIDAS · CARGA VIRTUAL', ico='estrella', fg2='#B3201B')),
    ('VerduleriaLaEsquina', dict(bg='#2D7A3A', fg='#F4F1E6', titulo='VERDULERÍA LA ESQUINA', estilo='negra',
                                 sub='FRUTAS Y VERDURAS FRESCAS', ico='fruta', fg2='#F09A2A')),
    ('FerreteriaElTornillo', dict(bg='#B3241D', fg='#F5F3EC', titulo='FERRETERÍA EL TORNILLO', estilo='negra',
                                  sub='PINTURERÍA · SANITARIOS · ELECTRICIDAD', ico='tornillo', fg2='#F5F3EC')),
    ('PizzeriaLoDeCacho', dict(bg='#1B1B1B', fg='#F2C21B', titulo='Pizzería Lo de Cacho', estilo='serif_it',
                               sub='PIZZA · FAINÁ · EMPANADAS · DELIVERY', ico='porcion', fg2='#E65B2A')),
    ('FarmaciaDelBarrio', dict(bg='#F2F2EE', fg='#1C7A46', titulo='FARMACIA DEL BARRIO', estilo='calle',
                               sub='PERFUMERÍA · OBRAS SOCIALES', franja='#1C7A46', fg2='#1C7A46')),
    ('CarniceriaLosHermanos', dict(bg='#F1EEE6', fg='#A3191A', titulo='CARNICERÍA LOS HERMANOS', estilo='display',
                                   sub='CARNES · ACHURAS · POLLOS', borde='#A3191A', fg2='#2B2B2B')),
    ('PanaderiaLaEspiga', dict(bg='#8A5A2B', fg='#F4E6C4', titulo='PANADERÍA LA ESPIGA', estilo='serif',
                               sub='CONFITERÍA · FACTURAS · PAN CASERO', ico='espiga', fg2='#F4E6C4')),
    ('PeluqueriaEstilo', dict(bg='#B23A78', fg='#FAF2F6', titulo='Peluquería Estilo', estilo='fira_it',
                              sub='DAMAS · CABALLEROS · NIÑOS', ico='tijera', fg2='#FAF2F6')),
    ('RotiseriaDonaRosa', dict(bg='#E2702A', fg='#FFF8EC', titulo='ROTISERÍA DOÑA ROSA', estilo='fira',
                               sub='COMIDAS PARA LLEVAR', fg2='#3A1F10', franja='#3A1F10')),
    ('LibreriaElLapiz', dict(bg='#1F4FA0', fg='#F6D23A', titulo='LIBRERÍA EL LÁPIZ', estilo='negra',
                             sub='FOTOCOPIAS · ÚTILES ESCOLARES', fg2='#F4F4F0')),
    ('GomeriaElRayo', dict(bg='#242424', fg='#F2C21B', titulo='GOMERÍA EL RAYO', estilo='display',
                           sub='MOTOS · BICIS · AUXILIO', ico='rayo', fg2='#F2C21B')),
    ('LavaderoBurbujas', dict(bg='#5FB4D9', fg='#FFFFFF', titulo='LAVADERO BURBUJAS', estilo='fira',
                              sub='LAVADO · SECADO · PLANCHADO', ico='gota', fg2='#1B4E78', stroke=4,
                              stroke_col='#1B4E78')),
    ('PolirrubroLosChicos', dict(bg='#178A86', fg='#FFF7DC', titulo='POLIRRUBRO LOS CHICOS', estilo='negra',
                                 sub='REGALERÍA · JUGUETES · LIBRERÍA', fg2='#FFF7DC')),
    ('DespensaMary', dict(bg='#F4F0E2', fg='#1F6B2E', titulo='Despensa Mary', estilo='mano',
                          sub='ALMACÉN · BEBIDAS · LIMPIEZA', borde='#E0A21C', fg2='#7A3B12')),
    ('BazarElSol', dict(bg='#D79A22', fg='#3B220C', titulo='BAZAR EL SOL', estilo='serif',
                        sub='TODO PARA EL HOGAR', ico='estrella', fg2='#FFF3D6')),
]

# v5: segundo atlas de comercios (calle comercial tipo 3 de Febrero). Todos INVENTADOS.
COMERCIOS2 = [
    ('ZapateriaPasoFirme', dict(bg='#2B2B2B', fg='#F1E3C6', titulo='ZAPATERÍA PASO FIRME', estilo='serif',
                                sub='CALZADO · MARROQUINERÍA · CARTERAS', fg2='#D9A441', franja='#D9A441')),
    ('TiendaMarelu', dict(bg='#F6E9EE', fg='#9B2D5A', titulo='Tienda Marelu', estilo='fira_it',
                          sub='ROPA · LENCERÍA · BLANCO', borde='#9B2D5A', fg2='#4A4A4A')),
    ('ConexionCelulares', dict(bg='#0F2F5C', fg='#3FD0F2', titulo='CONEXIÓN CELULARES', estilo='display',
                               sub='FUNDAS · ACCESORIOS · SERVICE TÉCNICO', ico='rayo', fg2='#F4F4F0')),
    ('OpticaVisionClara', dict(bg='#F3F5F7', fg='#1F4F8A', titulo='ÓPTICA VISIÓN CLARA', estilo='calle',
                               sub='ANTEOJOS · LENTES DE CONTACTO · RECETAS', franja='#1F4F8A', fg2='#1F4F8A')),
    ('MerceriaElHilo', dict(bg='#E9D8B4', fg='#6B2D2D', titulo='Mercería El Hilo', estilo='mano',
                            sub='LANAS · BOTONES · CIERRES · PUNTILLAS', borde='#6B2D2D', fg2='#3A2A1A')),
    ('DeportesLaCancha', dict(bg='#1E7A3A', fg='#FFFFFF', titulo='DEPORTES LA CANCHA', estilo='negra',
                              sub='CALZADO · INDUMENTARIA · PELOTAS', ico='estrella', fg2='#F2C21B')),
    ('PintureriaArcoiris', dict(bg='#F4F1EA', fg='#C2321F', titulo='PINTURERÍA ARCOÍRIS', estilo='display',
                                sub='LÁTEX · ESMALTES · ACCESORIOS', borde='#2F6FB3', fg2='#2F6FB3')),
    ('JugueteriaElTrompo', dict(bg='#F2C21B', fg='#C2241F', titulo='JUGUETERÍA EL TROMPO', estilo='negra',
                                sub='JUGUETES · RODADOS · DIDÁCTICOS', ico='estrella', fg2='#1F3F8A')),
    ('CotillonFiestita', dict(bg='#7A2FA0', fg='#FFE45C', titulo='COTILLÓN FIESTITA', estilo='display',
                              sub='DISFRACES · GLOBOS · DESCARTABLES', ico='estrella', fg2='#FFFFFF')),
    ('HeladeriaLaNieve', dict(bg='#EAF6FB', fg='#1F6FA8', titulo='Heladería La Nieve', estilo='serif_it',
                              sub='HELADO ARTESANAL · DELIVERY', ico='gota', fg2='#C2416B')),
    ('RegaleriaElMono', dict(bg='#C2416B', fg='#FFF4F6', titulo='REGALERÍA EL MOÑO', estilo='fira',
                             sub='BIJOUTERIE · REGALOS · PERFUMES', fg2='#FFF4F6', franja='#7A1F3A')),
    ('ForrajeriaLaHuella', dict(bg='#5A3A1E', fg='#F2D68A', titulo='FORRAJERÍA LA HUELLA', estilo='negra',
                                sub='ALIMENTO BALANCEADO · ACCESORIOS', ico='espiga', fg2='#F2D68A')),
]

ATLAS = {   # nombre: (ancho, alto, con alfa)
    'Calle': (2048, 2048, False),
    'Comercio': (2048, 4096, False),
    'Comercio2': (2048, 4096, False),
    'Varios': (2048, 2048, True),
}


def catalogo_carteles():
    """Lista de (MI, atlas, x, y, w, h, dibujante, desgaste, enmascarado). Orden y rectángulos FIJOS (el
    material los toma de carteles_atlas.json; setup_materials.py tiene la misma tabla de respaldo)."""
    cat = []
    for i, (slug, txt) in enumerate(CALLES):
        x, y = (i % 2) * 1024, (i // 2) * 256
        cat.append(('MI_CartelCalle_' + slug, 'Calle', x, y, 1024, 256,
                    (lambda t: (lambda w, h, r: dib_calle(w, h, t, r)))(txt),
                    dict(sol=0.35, mugre=0.35, oxido=0.35, rayas=0.5, rough_base=0.42), False))
    for i, (slug, spec) in enumerate(COMERCIOS):
        cat.append(('MI_Comercio_' + slug, 'Comercio', 0, i * 256, 2048, 256,
                    (lambda sp: (lambda w, h, r: dib_comercio(w, h, sp, r)))(spec),
                    dict(sol=0.45, mugre=0.45, oxido=0.25, rayas=0.35, rough_base=0.5), False))
    for i, (slug, spec) in enumerate(COMERCIOS2):
        cat.append(('MI_Comercio_' + slug, 'Comercio2', 0, i * 256, 2048, 256,
                    (lambda sp: (lambda w, h, r: dib_comercio(w, h, sp, r)))(spec),
                    dict(sol=0.45, mugre=0.45, oxido=0.25, rayas=0.35, rough_base=0.5), False))
    chapa = dict(sol=0.3, mugre=0.35, oxido=0.25, rayas=0.35, rough_base=0.45)
    cat += [
        ('MI_Cartel_Comisaria', 'Varios', 0, 0, 2048, 256, dib_comisaria, dict(chapa, sol=0.15, oxido=0.12), False),
        ('MI_Cartel_Estacion', 'Varios', 0, 256, 2048, 256, dib_estacion, dict(chapa, oxido=0.35), False),
        ('MI_Cartel_Salida', 'Varios', 0, 512, 1024, 256, lambda w, h, r: dib_salida(w, h, 'arriba', r),
         dict(chapa, sol=0.15, oxido=0.15), False),
        ('MI_Cartel_Salida_Der', 'Varios', 1024, 512, 1024, 256, lambda w, h, r: dib_salida(w, h, 'der', r),
         dict(chapa, sol=0.15, oxido=0.15), False),
        ('MI_Cartel_Salida_Izq', 'Varios', 0, 768, 1024, 256, lambda w, h, r: dib_salida(w, h, 'izq', r),
         dict(chapa, sol=0.15, oxido=0.15), False),
        ('MI_Cartel_NoEstacionar', 'Varios', 1024, 768, 1024, 256, dib_no_estacionar,
         dict(chapa, sol=0.5, mugre=0.5, oxido=0.4), False),
        ('MI_Bandera_Celeste', 'Varios', 0, 1024, 1024, 512, dib_bandera,
         dict(sol=0.12, mugre=0.08, oxido=0.0, rayas=0.0, chapa=False, tela=True), False),
        ('MI_Afiche_SeVende', 'Varios', 1024, 1024, 512, 512, lambda w, h, r: dib_afiche(w, h, 'se_vende', r),
         dict(sol=0.4, mugre=0.3, oxido=0.0, rayas=0.0, chapa=False, rough_base=0.6), False),
        ('MI_Afiche_Alquilo', 'Varios', 1536, 1024, 512, 512, lambda w, h, r: dib_afiche(w, h, 'alquilo', r),
         dict(sol=0.4, mugre=0.3, oxido=0.0, rayas=0.0, chapa=False, rough_base=0.6), False),
    ]
    for i in range(4):
        cat.append(('MI_Pintada_%d' % (i + 1), 'Varios', i * 512, 1536, 512, 512, dib_pintada,
                    dict(sol=0.25, mugre=0.0, oxido=0.0, rayas=0.0, chapa=False, rough_base=0.75), True))
    return cat


def gen_carteles(seed=4040):
    import json
    os.makedirs(CARTELES_DIR, exist_ok=True)
    buf = {}
    for nm, (W, H, alpha) in ATLAS.items():
        bc = np.zeros((H, W, 4), F)
        bc[..., 3] = 1.0 if not alpha else 0.0
        orm = np.zeros((H, W, 3), F)
        orm[..., 0] = 1.0
        orm[..., 1] = 0.8
        buf[nm] = (bc, orm)
    manifest = {'_doc': 'UV del cartel = AtlasRect.xy + UV0 * AtlasRect.zw (V hacia abajo, origen arriba-izquierda). '
                        'rect_px = [x, y, w, h] en el atlas; aspecto = w/h de la placa a modelar.',
                'atlas': {k_: {'size': [v[0], v[1]], 'alpha': v[2],
                               'BC': f'T_Carteles_{k_}_BC', 'ORM': f'T_Carteles_{k_}_ORM'} for k_, v in ATLAS.items()},
                'normal': 'T_Carteles_N', 'carteles': {}}
    for (mi, at, x, y, w, h, fn, wear, masked) in catalogo_carteles():
        sub = np.random.default_rng(seed + sum(map(ord, mi)) * 7)     # semilla estable por cartel (sin hash())
        im = fn(w, h, sub)
        a = None
        if im.mode == 'RGBA':
            arr = np.asarray(im)
            rgb8, a = arr[..., :3], arr[..., 3].astype(F) / 255.0
        else:
            rgb8 = np.asarray(im.convert('RGB'))
        wear = dict(wear)
        c, ao, rough, metal = _desgaste(rgb8, sub, **wear)
        bc, orm = buf[at]
        bc[y:y + h, x:x + w, :3] = c
        bc[y:y + h, x:x + w, 3] = 1.0 if a is None else a
        orm[y:y + h, x:x + w, 0] = ao
        orm[y:y + h, x:x + w, 1] = rough
        orm[y:y + h, x:x + w, 2] = metal
        W, H, _ = ATLAS[at]
        manifest['carteles'][mi] = {'atlas': at, 'rect_px': [x, y, w, h],
                                    'uv': [x / W, y / H, w / W, h / H], 'aspecto': round(w / h, 4), 'mascara': masked}
    for nm, (bc, orm) in buf.items():
        alpha = ATLAS[nm][2]
        img = Image.fromarray(to8(bc if alpha else bc[..., :3]), 'RGBA' if alpha else 'RGB')
        img.save(os.path.join(CARTELES_DIR, f'T_Carteles_{nm}_BC.png'), compress_level=6)
        Image.fromarray(to8(orm)).save(os.path.join(CARTELES_DIR, f'T_Carteles_{nm}_ORM.png'), compress_level=6)
    flat = np.zeros((256, 256, 3), np.uint8)
    flat[...] = (128, 128, 255)
    Image.fromarray(flat).save(os.path.join(CARTELES_DIR, 'T_Carteles_N.png'))
    with open(os.path.join(CARTELES_DIR, 'carteles_atlas.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    preview_carteles()
    log(f'Carteles: {len(manifest["carteles"])} carteles en {len(ATLAS)} atlas -> {CARTELES_DIR}')
    return manifest


def preview_carteles():
    """Hoja de revisión: los tres atlas sobre gris medio (el alfa se ve) + rugosidad del de calles."""
    ims = []
    for nm in ATLAS:
        im = Image.open(os.path.join(CARTELES_DIR, f'T_Carteles_{nm}_BC.png'))
        bg = Image.new('RGBA', im.size, (110, 110, 110, 255))
        bg.alpha_composite(im.convert('RGBA'))
        ims.append(bg.convert('RGB'))
    hmax = 1400
    sc = [hmax / im.size[1] for im in ims]
    tw = sum(int(im.size[0] * s) for im, s in zip(ims, sc)) + 10 * (len(ims) + 1)
    sheet = Image.new('RGB', (tw, hmax + 20), (30, 30, 30))
    x = 10
    for im, s in zip(ims, sc):
        r = im.resize((int(im.size[0] * s), hmax), Image.LANCZOS)
        sheet.paste(r, (x, 10))
        x += r.size[0] + 10
    sheet.save(os.path.join(CARTELES_DIR, 'preview_carteles.jpg'), quality=88)


GENS = {
    'Revoque': gen_revoque, 'Ladrillo': gen_ladrillo, 'Baldosa': gen_baldosa, 'Asfalto': gen_asfalto,
    'Hormigon': gen_hormigon, 'Chapa': gen_chapa, 'Madera': gen_madera, 'Tejas': gen_tejas,
    'MetalPintado': gen_metalpintado, 'PiedraLaja': gen_piedralaja,
    'Corteza': gen_corteza, 'Pasto': gen_pasto, 'Tierra': gen_tierra, 'Balasto': gen_balasto,
    'Riel': gen_riel, 'Follaje': gen_follaje,
}


def run_set(name):
    t0 = time.time()
    bc, h, px, ns, ao, rough, metal = GENS[name]()
    save_set(name, bc, h, px, ns, clamp(ao, 0.0, 1.0), rough, metal)
    dt = time.time() - t0
    log(f'{name}: listo en {dt:.1f}s  (altura {h.min():.2f}..{h.max():.2f} cm, '
        f'rug {rough.mean():.2f}, ao {ao.mean():.2f})')
    return name, dt


# ----------------------------------------------------------------------------
# Hoja de contacto
# ----------------------------------------------------------------------------
def lit_preview(bc, nrm, orm):
    """Render rápido: luz rasante desde arriba-izquierda (decodifica normal DirectX)."""
    n = nrm * 2.0 - 1.0
    n[..., 1] *= -1.0                       # DirectX -> Y arriba
    L = np.array([-0.55, 0.55, 0.63])
    L /= np.linalg.norm(L)
    lam = np.clip((n * L).sum(-1), 0, 1)
    ao = orm[..., 0]
    out = bc * (0.18 + 0.95 * lam[..., None]) * ao[..., None] ** 0.8
    return np.clip(out, 0, 1)


def contact_sheet(names=SETS, thumb=256):
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()
    cols = 2
    cw = thumb * 3 + 30
    ch = thumb + 30
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cw + 10, rows * ch + 10), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for i, nm in enumerate(names):
        d = os.path.join(OUT, nm)
        bcp = os.path.join(d, f'T_{nm}_BC.png')
        if not os.path.exists(bcp):
            continue
        bc = Image.open(bcp).convert('RGB')
        nn = Image.open(os.path.join(d, f'T_{nm}_N.png')).convert('RGB')
        orm = Image.open(os.path.join(d, f'T_{nm}_ORM.png')).convert('RGB')
        small = lambda im: np.asarray(im.resize((512, 512), Image.LANCZOS), dtype=np.float32) / 255.0
        lit = lit_preview(small(bc), small(nn), small(orm))
        x0 = (i % cols) * cw + 10
        y0 = (i // cols) * ch + 10
        dr.text((x0, y0), f'{nm}  ({TILE_CM[nm]:.0f} cm)  BC | N | iluminada', fill=(230, 230, 230), font=font)
        sheet.paste(bc.resize((thumb, thumb), Image.LANCZOS), (x0, y0 + 24))
        sheet.paste(nn.resize((thumb, thumb), Image.LANCZOS), (x0 + thumb + 5, y0 + 24))
        sheet.paste(Image.fromarray(to8(lit)).resize((thumb, thumb), Image.LANCZOS), (x0 + 2 * thumb + 10, y0 + 24))
    p = os.path.join(OUT, 'preview_contact_sheet.jpg')
    sheet.save(p, quality=90)
    log(f'hoja de contacto: {p}')


def main():
    ap = argparse.ArgumentParser(description='Genera texturas PBR tileables de Barrio')
    ap.add_argument('sets', nargs='*', default=SETS)
    ap.add_argument('--jobs', type=int, default=min(2, os.cpu_count() or 1))
    ap.add_argument('--no-sheet', action='store_true')
    a = ap.parse_args()
    sets = list(a.sets)
    # v4: 'Carteles' no es un set tileable (atlas de texto con UV); va siempre en la corrida completa
    carteles = ('Carteles' in sets) or (a.sets == SETS)
    sets = [s for s in sets if s != 'Carteles']
    for s in sets:
        if s not in GENS:
            sys.exit(f'Set desconocido: {s}. Opciones: {", ".join(SETS + ["Carteles"])}')
    t0 = time.time()
    log(f'generando {len(sets)} sets en {OUT} con {a.jobs} procesos')
    if a.jobs > 1 and len(sets) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.jobs) as ex:
            list(ex.map(run_set, sets))
    else:
        for s in sets:
            run_set(s)
    if carteles:
        gen_carteles()
    if sets and not a.no_sheet:
        contact_sheet()
    log(f'total {time.time() - t0:.1f}s')


if __name__ == '__main__':
    main()
