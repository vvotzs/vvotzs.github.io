#!/usr/bin/env python3
"""Rebuild assets/img/sw-penguin.webp — the little waving penguin that paces on top of
the Sendwave badge on the home / category pages.

Why this script exists
----------------------
The source is a screenshot the site owner sent of the old official Sendwave penguin on a
flat cyan card (74, 210, 250). The first export was cropped straight through the raised
wing, which left a hard vertical cut (a thin line) along the image's left edge and clipped
the feet. This script re-extracts the whole figure with margin on all four sides, keys out
the cyan background, un-blends the antialiased rim so no cyan survives, then decontaminates
the edge colours at the final 41x60 size (partial-alpha pixels borrow their colour from the
nearest opaque neighbour). The result is saved losslessly, so the browser never shows a
compressed halo around the silhouette.

Usage
-----
    python3 scripts/make_sw_penguin.py PATH/TO/reference-screenshot.jpg [out.webp]

Requires Pillow + numpy only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BG = np.array([74, 210, 250], dtype=np.float32)   # flat cyan background of the reference card
TARGET_H = 60                                     # 3x the 20px it is drawn at, so it stays crisp
MARGIN = 10                                       # transparent margin kept around the figure


def load_crop(src: Path) -> np.ndarray:
    """Crop the penguin out with a margin, using the cyan background to find its bbox.

    A plain colour mask would also pick up the screenshot's card border and the phone's
    status bar, so the bbox comes from the connected blob the penguin belongs to: flood
    fill from a dark pixel near the middle of the card.
    """
    from collections import deque

    rgb = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
    h, w, _ = rgb.shape
    mask = np.abs(rgb - BG).max(axis=2) > 60

    seed = None
    for y in range(int(h * 0.35), int(h * 0.65)):
        for x in range(int(w * 0.3), int(w * 0.7)):
            if mask[y, x] and rgb[y, x].max() < 90:      # a black pixel of the body outline
                seed = (y, x)
                break
        if seed:
            break
    if seed is None:
        raise SystemExit("penguin not found in the reference image")

    seen = np.zeros_like(mask)
    seen[seed] = True
    q = deque([seed])
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))

    ys, xs = np.nonzero(seen)
    x0, x1 = xs.min(), xs.max() + 1
    y0, y1 = ys.min(), ys.max() + 1
    x0, y0 = max(0, x0 - MARGIN), max(0, y0 - MARGIN)
    x1, y1 = min(w, x1 + MARGIN), min(h, y1 + MARGIN)
    return rgb[y0:y1, x0:x1]


def matte(crop: np.ndarray) -> Image.Image:
    """Key out the cyan, un-blend the rim, return RGBA at source resolution."""
    h, w, _ = crop.shape
    d = crop - BG
    dist = np.abs(d).max(axis=2)

    # object colour spread outward from the solid core (fallback colour for near-zero alpha)
    solid = dist > 38
    rgb = crop.copy()
    known = solid.copy()
    for _ in range(16):
        if known.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros((h, w), dtype=np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            k = np.roll(known, (dy, dx), axis=(0, 1))
            c = np.roll(rgb, (dy, dx), axis=(0, 1))
            acc += c * k[..., None]
            cnt += k
        fill = (~known) & (cnt > 0)
        rgb[fill] = acc[fill] / cnt[fill][:, None]
        known |= fill

    # alpha = least-squares projection of (p - BG) onto (C - BG)
    cb = rgb - BG
    denom = (cb * cb).sum(axis=2)
    alpha = np.where(denom < 400, 0.0,
                     np.clip((d * cb).sum(axis=2) / np.maximum(denom, 1e-3), 0.0, 1.0))
    alpha[dist < 8] = 0.0

    # exact un-blend where alpha is meaningful: C = (p - (1-a)BG) / a
    a3 = alpha[..., None]
    colour = np.clip(np.where(a3 > 0.06, (crop - (1 - a3) * BG) / np.maximum(a3, 1e-6), rgb),
                     0, 255)
    return Image.fromarray(np.dstack([colour, alpha * 255]).astype(np.uint8), "RGBA")


def downscale(rgba: Image.Image, margin_px: int) -> Image.Image:
    """Premultiplied BOX downscale (no ringing), then edge-colour decontamination."""
    w, h = rgba.size
    target_w = int(round(TARGET_H * (w - 2 * margin_px) / (h - 2 * margin_px)))
    arr = np.asarray(rgba).astype(np.float32)
    a = arr[..., 3:4] / 255.0
    pm = Image.fromarray(np.dstack([arr[..., :3] * a, arr[..., 3]]).astype(np.uint8), "RGBA")
    pm = pm.resize((target_w, TARGET_H), Image.BOX)
    p = np.asarray(pm).astype(np.float32)
    aa = p[..., 3:4] / 255.0
    small = np.dstack([np.where(aa > 0, p[..., :3] / np.maximum(aa, 1e-6), 0), aa * 255])

    # partial-alpha pixels borrow colour from opaque neighbours, so the rim is never tinted
    rgb_s = small[..., :3].copy()
    a_s = small[..., 3] / 255.0
    opaque = a_s >= 0.96
    for _ in range(3):
        acc = np.zeros_like(rgb_s)
        cnt = np.zeros(a_s.shape, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                k = np.roll(opaque, (dy, dx), axis=(0, 1)).astype(np.float32)
                acc += np.roll(rgb_s, (dy, dx), axis=(0, 1)) * k[..., None]
                cnt += k
        need = (~opaque) & (a_s > 0.02) & (cnt > 0)
        rgb_s[need] = acc[need] / cnt[need][:, None]
        opaque = opaque | need

    out = np.dstack([np.clip(rgb_s, 0, 255), small[..., 3]]).astype(np.uint8)
    # fully transparent 1px ring: guarantees no residual line on any edge
    out[0, :, 3] = 0
    out[-1, :, 3] = 0
    out[:, 0, 3] = 0
    out[:, -1, 3] = 0
    return Image.fromarray(out, "RGBA")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "assets" / "img" / "sw-penguin.webp"
    img = downscale(matte(load_crop(src)), MARGIN)
    img.save(dst, "WEBP", lossless=True, quality=100, method=6, exact=True)
    print(f"{dst} · {img.size[0]}x{img.size[1]} · {dst.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
