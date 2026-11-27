# -*- coding: utf-8 -*-
"""gen_hojas.py - Texturas de racimos de hojas para las copas de los árboles (tarjetas enmascaradas).

Genera, en <salida>/Hojas/:
  T_Hojas_BC.png  RGBA 2048: 2x2 racimos distintos (ramita + 30-60 hojas). Alfa = máscara de hoja.
                  Color en gris-verde medio: el tono final lo pone el Tint de cada MI (fresno, paraíso, plátano).
  T_Hojas_N.png   normal DirectX (G hacia abajo, como el resto del proyecto): nervadura central + curvatura.
Cada cuadrante es una tarjeta: el árbol usa AtlasRect para elegir uno (mismo esquema que los carteles).
Uso: python3 gen_hojas.py [salida]   (por defecto ./textures)
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = 2048
Q = S // 2
SS = 2                      # supersampling


def _leaf_poly(cx, cy, L, W, ang, bend):
    """Hoja lanceolada (punta aguda, base redondeada) curvada, como polígono."""
    pts_l, pts_r = [], []
    n = 18
    ca, sa = math.cos(ang), math.sin(ang)
    for i in range(n + 1):
        t = i / n
        w = W * (math.sin(math.pi * t) ** 0.8) * (1.0 - 0.35 * t)
        x = t * L
        y = bend * L * t * t
        nx, ny = -2 * bend * t, 1.0
        nn = math.hypot(nx, ny)
        nx, ny = nx / nn, ny / nn
        for (sgn, arr) in ((1, pts_l), (-1, pts_r)):
            px, py = x + sgn * nx * w * 0.5 * 0 , y + sgn * w * 0.5
            arr.append((cx + px * ca - py * sa, cy + px * sa + py * ca))
    return pts_l + pts_r[::-1], [(cx + (t / n * L) * ca - (bend * L * (t / n) ** 2) * sa,
                                   cy + (t / n * L) * sa + (bend * L * (t / n) ** 2) * ca) for t in range(n + 1)]


def racimo(rng, size):
    """Un racimo: rama que entra por abajo y se abre en 3-5 ramitas con hojas alternas."""
    W = size * SS
    rgba = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    hgt = Image.new('L', (W, W), 0)
    dr = ImageDraw.Draw(rgba)
    dh = ImageDraw.Draw(hgt)
    base = (W * rng.uniform(0.42, 0.58), W * 0.98)
    ramas = []
    nram = rng.integers(4, 7)
    for r in range(nram):
        a = -math.pi / 2 + rng.uniform(-0.9, 0.9)
        L = W * rng.uniform(0.45, 0.78)
        mid = (base[0] + math.cos(a) * L * 0.5 + rng.uniform(-0.06, 0.06) * W, base[1] + math.sin(a) * L * 0.5)
        end = (base[0] + math.cos(a) * L, base[1] + math.sin(a) * L)
        ramas.append((base, mid, end))
        dr.line([base, mid, end], fill=(88, 70, 52, 255), width=int(W * 0.007))
    leaves = []
    for (p0, p1, p2) in ramas:
        nl = rng.integers(15, 24)
        for i in range(nl):
            t = 0.25 + 0.75 * i / nl
            if t < 0.5:
                u = t / 0.5
                px, py = p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            else:
                u = (t - 0.5) / 0.5
                px, py = p1[0] + (p2[0] - p1[0]) * u, p1[1] + (p2[1] - p1[1]) * u
                dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            ad = math.atan2(dy, dx)
            side = 1 if i % 2 else -1
            ang = ad + side * rng.uniform(0.5, 1.1)
            L = W * rng.uniform(0.11, 0.17) * (0.75 + 0.25 * t)
            Wd = L * rng.uniform(0.32, 0.42)
            leaves.append((px, py, L, Wd, ang, rng.uniform(-0.18, 0.18)))
        # hoja terminal
        ad = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        L = W * 0.15
        leaves.append((p2[0], p2[1], L, L * 0.38, ad + rng.uniform(-0.2, 0.2), rng.uniform(-0.1, 0.1)))
    order = rng.permutation(len(leaves))
    for idx in order:
        (px, py, L, Wd, ang, bend) = leaves[idx]
        poly, rib = _leaf_poly(px, py, L, Wd, ang, bend)
        g = rng.uniform(0.75, 1.15)
        yl = rng.uniform(-0.08, 0.10)
        col = (int(np.clip(118 * g * (1 + yl), 0, 255)), int(np.clip(138 * g, 0, 255)), int(np.clip(96 * g * (1 - yl), 0, 255)), 255)
        dr.polygon(poly, fill=col)
        lev = int(rng.uniform(120, 230))
        dh.polygon(poly, fill=lev)
        dr.line(rib, fill=(int(col[0] * 1.12), int(col[1] * 1.12), int(col[2] * 1.05), 255), width=max(1, int(W * 0.0022)))
        dh.line(rib, fill=min(255, lev + 25), width=max(1, int(W * 0.003)))
    rgba = rgba.resize((size, size), Image.LANCZOS)
    hgt = hgt.filter(ImageFilter.GaussianBlur(SS * 1.5)).resize((size, size), Image.LANCZOS)
    return rgba, hgt


def normal_dx(h, strength=2.2):
    a = np.asarray(h).astype(np.float32) / 255.0
    gy, gx = np.gradient(a)
    nx, ny, nz = -gx * strength * 8, gy * strength * 8, np.ones_like(a)   # DirectX: Y hacia abajo
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    out = np.stack([nx / n, ny / n, nz / n], -1) * 0.5 + 0.5
    return (out * 255).astype(np.uint8)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'textures')
    d = os.path.join(out, 'Hojas')
    os.makedirs(d, exist_ok=True)
    rng = np.random.default_rng(7319)
    bc = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    hh = Image.new('L', (S, S), 0)
    for qi in range(4):
        r, h = racimo(rng, Q)
        x, y = (qi % 2) * Q, (qi // 2) * Q
        bc.paste(r, (x, y))
        hh.paste(h, (x, y))
    # sangrado de color bajo el alfa (evita halos negros con mips)
    a = np.asarray(bc).astype(np.float32)
    rgb, al = a[..., :3], a[..., 3:4] / 255.0
    blur = np.asarray(Image.fromarray(rgb.astype(np.uint8)).filter(ImageFilter.GaussianBlur(10))).astype(np.float32)
    wb = np.asarray(Image.fromarray((al[..., 0] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10))).astype(np.float32)[..., None] / 255.0
    fill = np.where(wb > 1e-3, blur / np.maximum(wb, 1e-3), np.array([110, 128, 90], np.float32))
    rgb2 = np.where(al > 0.0, rgb, np.clip(fill, 0, 255))
    bc2 = np.concatenate([rgb2, a[..., 3:4]], -1).astype(np.uint8)
    Image.fromarray(bc2, 'RGBA').save(os.path.join(d, 'T_Hojas_BC.png'), compress_level=6)
    Image.fromarray(normal_dx(hh)).save(os.path.join(d, 'T_Hojas_N.png'), compress_level=6)
    prev = Image.new('RGB', (S, S), (128, 128, 128))
    prev.paste(Image.fromarray(bc2, 'RGBA'), (0, 0), Image.fromarray(bc2, 'RGBA'))
    prev.resize((1024, 1024)).save(os.path.join(d, 'preview_hojas.jpg'), quality=88)
    print('Hojas ->', d)


if __name__ == '__main__':
    main()
