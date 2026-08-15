#!/usr/bin/env python3
"""Generate the Elder Weathers Nexus banners.

The original set was produced inline in a session and the generator was never
saved, so the artwork could only be edited by hand. This rebuilds it from
source: a planetary limb at sunrise, the runic wordmark with one amber letter,
a metadata strip, and a tagline.

    python scripts/make_banners.py            # writes media/nexus/
    python scripts/make_banners.py --out DIR  # writes elsewhere

media/ is gitignored, so the outputs stay out of the repository. This script
and assets/fonts are the committed source of truth for them.
"""
from __future__ import annotations

import argparse
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "assets", "fonts")

RUNIC = os.path.join(FONTS, "zentropy-runic.ttf")
GROTESK_MED = os.path.join(FONTS, "hanken-grotesk-medium.ttf")
GROTESK_REG = os.path.join(FONTS, "hanken-grotesk-regular.ttf")

# Copy. The count is the whole reason this script exists: the first banners
# said "7 ARCHETYPES", which is the archetype count, not the weather count.
WORDMARK_LEFT = "ELDER"
WORDMARK_ACCENT = "W"
WORDMARK_RIGHT = "EATHERS"
STRIP_HEADER = "WEATHER PLUGIN   ·   EWWeathers.esp (ESL)   ·   19 WEATHERS   ·   FULL REGION PASS"
STRIP_AVATAR = "WEATHER  ·  ESL  ·  19 WEATHERS"
TAGLINE = "Original Skyrim weathers, generated from a physical sky."

# Palette, sampled from the original artwork.
SKY_TOP = (8, 14, 30)
SKY_HORIZON = (26, 42, 70)
PLANET_DARK = (22, 30, 45)
PLANET_LIT = (196, 132, 62)
RIM = (208, 236, 255)
INK = (243, 245, 248)
AMBER = (240, 176, 74)
STRIP_INK = (150, 170, 196)


def _vertical_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    w, h = size
    band = Image.new("RGB", (1, h))
    px = band.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return band.resize(size, Image.BILINEAR)


# Sunrise direction.
#
# The visible cap is a thin slice off the top of a very large sphere, so every
# point in frame has a strongly negative dy. That makes dy useless as a driver:
# weight it and the whole planet lights up as a desert. The warmth has to come
# from +x, with just enough +z to keep the lit area off the limb itself.
#
# Checked against the four corners of the visible cap: bottom-right lands near
# 0.68, top-centre limb near 0.10, both left corners at or below 0.05.
LIGHT = (0.80, -0.10, 0.59)


def _planet(size, cx, cy, radius):
    """Planet body: dark limb shading with a warm sunrise terminator."""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius], fill=255)

    lx, ly, lz = LIGHT
    norm = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / norm, ly / norm, lz / norm

    body = Image.new("RGB", (w, h), PLANET_DARK)
    px = body.load()
    rng = random.Random(11)
    for y in range(h):
        dy = (y - cy) / radius
        for x in range(w):
            dx = (x - cx) / radius
            d2 = dx * dx + dy * dy
            if d2 > 1.0:
                continue
            nz = math.sqrt(max(0.0, 1.0 - d2))
            lam = max(0.0, dx * lx + dy * ly + nz * lz)
            # Narrow the lit band so it reads as a sunrise, not a day side.
            lam = lam ** 3.2
            col = tuple(
                round(PLANET_DARK[i] + (PLANET_LIT[i] - PLANET_DARK[i]) * lam)
                for i in range(3))
            px[x, y] = col

    # Faint mottling so the body is not a clean gradient.
    mottle = _grain(size, 23, 18).filter(ImageFilter.GaussianBlur(9))
    body = Image.blend(body, Image.merge("RGB", [mottle] * 3), 0.035)
    return body, mask


def _rim_glow(size, cx, cy, radius, width):
    """The bright atmosphere arc sitting just outside the limb."""
    w, h = size
    glow = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(glow)
    for i in range(width, 0, -1):
        v = round(255 * (1.0 - i / width) ** 1.8)
        d.ellipse([cx - radius - i, cy - radius - i,
                   cx + radius + i, cy + radius + i], outline=v, width=2)
    inner = Image.new("L", (w, h), 0)
    ImageDraw.Draw(inner).ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius], fill=255)
    glow.paste(0, (0, 0), inner)
    return glow.filter(ImageFilter.GaussianBlur(width * 0.18))


def _streaks(size, count, seed, limb_y):
    """A few faint vertical light streaks, in the sky only.

    The original has roughly half a dozen, barely visible. They must stop at
    the limb: a streak drawn across the planet body reads as a scratch.
    """
    w, h = size
    layer = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(layer)
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.randrange(int(w * 0.05), int(w * 0.95))
        top = rng.randrange(0, int(h * 0.16))
        length = rng.randrange(int(h * 0.10), int(h * 0.26))
        bottom = min(top + length, limb_y(x) - h * 0.02)
        if bottom <= top:
            continue
        d.line([(x, top), (x, bottom)], fill=rng.randrange(14, 34), width=1)
    return layer.filter(ImageFilter.GaussianBlur(0.8))


def _grain(size, seed, strength):
    w, h = size
    rng = random.Random(seed)
    noise = Image.new("L", (w, h))
    noise.putdata([rng.gauss(128, strength) for _ in range(w * h)])
    return noise


def _fit_font(path, text, target_px, draw):
    """Binary-search a font size so `text` is target_px wide."""
    lo, hi = 8, 600
    best = ImageFont.truetype(path, 12)
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(path, mid)
        wpx = draw.textlength(text, font=f)
        if wpx <= target_px:
            best = f
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def _tracked(draw, xy, text, font, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


def _tracked_width(draw, text, font, tracking):
    return sum(draw.textlength(c, font=font) for c in text) + tracking * (len(text) - 1)


def compose(width, height, *, avatar=False, seed=7):
    size = (width, height)
    w, h = size
    s = height / 900.0  # scale everything off the 1600x900 reference

    img = _vertical_gradient(size, SKY_TOP, SKY_HORIZON)

    if avatar:
        cx, cy, radius = width * 0.5, height * 1.52, height * 1.02
    else:
        cx, cy, radius = width * 0.46, height * 1.62, height * 1.30

    def limb_y(x):
        dx = x - cx
        inside = radius * radius - dx * dx
        return cy - math.sqrt(inside) if inside > 0 else h

    img.paste(Image.new("RGB", size, (255, 255, 255)), (0, 0),
              _streaks(size, 7, seed, limb_y))

    glow = _rim_glow(size, cx, cy, radius, max(4, int(13 * s)))
    img.paste(Image.new("RGB", size, RIM), (0, 0), glow)

    body, mask = _planet(size, cx, cy, radius)
    img.paste(body, (0, 0), mask)

    img = Image.blend(img, Image.merge("RGB", [_grain(size, seed + 1, 26)] * 3), 0.055)

    draw = ImageDraw.Draw(img)

    # The avatar is a different composition from the header: a large amber W
    # monogram carries the square, with the wordmark small underneath it.
    if avatar:
        mono = _fit_font(RUNIC, WORDMARK_ACCENT, width * 0.46, draw)
        mw = draw.textlength(WORDMARK_ACCENT, font=mono)
        box = draw.textbbox((0, 0), WORDMARK_ACCENT, font=mono)
        mx, my = (width - mw) / 2, height * 0.30 - box[1]
        # Soft dark halo so the glyph holds against the lit part of the planet.
        halo = Image.new("L", size, 0)
        ImageDraw.Draw(halo).text((mx, my), WORDMARK_ACCENT, font=mono, fill=170)
        halo = halo.filter(ImageFilter.GaussianBlur(max(3, int(10 * s))))
        img.paste(Image.new("RGB", size, (6, 10, 22)), (0, 0), halo)
        draw = ImageDraw.Draw(img)
        draw.text((mx, my), WORDMARK_ACCENT, font=mono, fill=AMBER)

    # Wordmark: ELDER + amber W + EATHERS, drawn as one tracked line.
    target = width * (0.60 if avatar else 0.82)
    wm_font = _fit_font(RUNIC, WORDMARK_LEFT + WORDMARK_ACCENT + WORDMARK_RIGHT,
                        target, draw)
    tracking = max(1.0, 4.0 * s)
    parts = ((WORDMARK_LEFT, INK), (WORDMARK_ACCENT, AMBER), (WORDMARK_RIGHT, INK))
    total = sum(_tracked_width(draw, p, wm_font, tracking) + tracking
                for p, _ in parts) - tracking
    x = (width - total) / 2 if avatar else width * 0.06
    y = height * (0.80 if avatar else 0.40)
    for text, fill in parts:
        x = _tracked(draw, (x, y), text, wm_font, fill, tracking)

    # Metadata strip.
    strip_text = STRIP_AVATAR if avatar else STRIP_HEADER
    strip_font = ImageFont.truetype(GROTESK_MED, max(9, int(21 * s)))
    strip_track = max(1.0, 3.2 * s)
    sw = _tracked_width(draw, strip_text, strip_font, strip_track)
    sx = (width - sw) / 2 if avatar else width * 0.06
    _tracked(draw, (sx, height * 0.085), strip_text, strip_font, STRIP_INK, strip_track)

    if not avatar:
        tag_font = ImageFont.truetype(GROTESK_REG, max(11, int(27 * s)))
        draw.text((width * 0.06, height * 0.82), TAGLINE, font=tag_font, fill=INK)

    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "media", "nexus"))
    ap.add_argument("--format", choices=("png", "jpg"), default="jpg",
                    help="jpg by default: the art is grain over gradients, which "
                         "PNG cannot compress (18 MB vs 2.7 MB for the same set)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    targets = [
        ("elder-weathers-nexus-header-1600", 1600, 900, False),
        ("elder-weathers-nexus-header-3200", 3200, 1800, False),
        ("elder-weathers-nexus-avatar-1400", 1400, 1400, True),
    ]
    for name, w, h, avatar in targets:
        img = compose(w, h, avatar=avatar)
        path = os.path.join(args.out, f"{name}.{args.format}")
        if args.format == "jpg":
            img.save(path, "JPEG", quality=95, optimize=True, progressive=True)
        else:
            img.save(path, "PNG", optimize=True)
        print(f"  {os.path.basename(path):46s} {os.path.getsize(path) / 1048576:5.2f} MB")


if __name__ == "__main__":
    main()
