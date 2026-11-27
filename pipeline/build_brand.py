"""Render the README's brand assets: a wordmark with a hex-drawn China, and rounded 3-D badges.

    python3 pipeline/build_brand.py      (needs Pillow: pip install pillow)

Everything is drawn from the site's own palette and, for the map, from web/data/world.json — the silhouette is the
same 5,843 land hexes the site paints, at the same 25 km pitch. Outputs into docs/images/.
"""

from __future__ import annotations

import json
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "images")
DATA = os.path.join(ROOT, "web", "data", "world.json")
FONT_BOLD = os.path.join(ROOT, "pipeline", "vendor", "NotoSerifSC-Bold.otf")
FONT_REG = os.path.join(ROOT, "pipeline", "vendor", "NotoSerifSC-Regular.otf")

NAVY = (16, 26, 38)
GOLD = (201, 164, 92)
GOLD_HI = (240, 217, 154)
GOLD_LO = (146, 111, 48)
RED = (163, 39, 28)
RED_HI = (198, 62, 46)
INK_LIGHT = (26, 26, 28)
GREY_LIGHT = (108, 108, 112)

S = 2  # supersampling factor for the wordmark


def hexagon(draw, cx, cy, r, fill):
    pts = [(cx + r * math.cos(math.radians(-90 + 60 * k)), cy + r * math.sin(math.radians(-90 + 60 * k)))
           for k in range(6)]
    draw.polygon(pts, fill=fill)


def china_plate(size, pad_ratio=0.10, plate=None, radius_ratio=0.26, ramp=None):
    """A rounded square plate with China drawn as its own hexagons."""
    world = json.load(open(DATA, encoding="utf-8"))
    cols, rows = world["grid"]["cols"], world["grid"]["rows"]
    owner = world["owner"]
    elev = world.get("elev") or [0] * len(owner)

    cells = []
    for i, o in enumerate(owner):
        if o >= 0:
            col, row = i % cols, i // cols
            x = math.sqrt(3) * (col + 0.5 * (row & 1))
            y = 1.5 * row
            cells.append((x, y, i))

    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if plate:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * radius_ratio), fill=plate + (255,),
                            outline=GOLD + (110,), width=max(2, size // 160))

    pad = size * pad_ratio
    span_x, span_y = (maxx - minx) or 1, (maxy - miny) or 1
    # pointy-top hexes are √3·r wide and 2·r tall; leave a hex radius of slack all round
    scale = min((size - 2 * pad) / (span_x + math.sqrt(3)), (size - 2 * pad) / (span_y + 2))
    r = scale  # one hex radius in pixels
    cx_off = (size - (span_x * scale)) / 2 - minx * scale
    cy_off = (size - (span_y * scale)) / 2 - miny * scale

    lo, hi = ramp or (GOLD, GOLD_HI)
    for x, y, i in cells:
        px, py = x * scale + cx_off, y * scale + cy_off
        e = elev[i] if i < len(elev) else 0
        # higher ground reads brighter, so the plateau and the Himalaya edge show up in the mark
        t = max(0.0, min(1.0, (e or 0) / 5000.0))
        top = tuple(int(lo[k] + (hi[k] - lo[k]) * (0.3 + 0.7 * t)) for k in range(3))
        hexagon(d, px, py, r * 0.97, top + (255,))
    return img


def star(img, cx, cy, R, fill):
    d = ImageDraw.Draw(img)
    pts = [(cx + (R if k % 2 == 0 else R * 0.382) * math.cos(math.radians(-90 + 36 * k)),
            cy + (R if k % 2 == 0 else R * 0.382) * math.sin(math.radians(-90 + 36 * k))) for k in range(10)]
    d.polygon(pts, fill=fill + (255,))


def trim(img, pad=0):
    """Crop to the visible pixels so the mark sits flush against the text that follows it in the README."""
    box = img.getchannel("A").getbbox()
    if not box:
        return img
    left, top, right, bottom = box
    left, top = max(0, left - pad), max(0, top - pad)
    right, bottom = min(img.width, right + pad), min(img.height, bottom + pad)
    return img.crop((left, top, right, bottom))


def wordmark(path, text_fill, sub_fill, plate=None, ramp=None):
    W, H = 1180 * S, 300 * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    icon_size = 210 * S
    plate_img = china_plate(icon_size, plate=plate, ramp=ramp)
    img.alpha_composite(plate_img, (10 * S, (H - icon_size) // 2))

    f_cn = ImageFont.truetype(FONT_BOLD, 104 * S)
    f_dot = ImageFont.truetype(FONT_REG, 74 * S)
    f_lat = ImageFont.truetype(FONT_REG, 62 * S)
    x = 10 * S + icon_size + 46 * S
    baseline = H // 2

    cn = "文明中国"
    d = ImageDraw.Draw(img)
    b = d.textbbox((0, 0), cn, font=f_cn)
    d.text((x, baseline - (b[3] + b[1]) / 2 - 6 * S), cn, font=f_cn, fill=text_fill + (255,))
    x += b[2] - b[0] + 24 * S

    dot = "·"
    bd = d.textbbox((0, 0), dot, font=f_dot)
    d.text((x, baseline - (bd[3] + bd[1]) / 2 - 2 * S), dot, font=f_dot, fill=sub_fill + (255,))
    x += bd[2] - bd[0] + 20 * S

    lat = "chinaciv"
    bl = d.textbbox((0, 0), lat, font=f_lat)
    d.text((x, baseline - (bl[3] + bl[1]) / 2 - 1 * S), lat, font=f_lat, fill=sub_fill + (255,))

    out = img.resize((W // S, H // S), Image.LANCZOS)
    out = trim(out, pad=2)
    out.save(path, optimize=True)
    print("wrote", path, out.size, os.path.getsize(path) // 1024, "KB")


def pill(path, label, value, tone):
    """A rounded, glossy badge: vertical gradient, top highlight, inner shading, soft shadow, hairline rim."""
    H, R = 30 * 3, 15 * 3
    f_lab = ImageFont.truetype(FONT_REG, 15 * 3)
    f_val = ImageFont.truetype(FONT_BOLD, 15 * 3)
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w_lab = tmp.textlength(label, font=f_lab)
    w_val = tmp.textlength(value, font=f_val) if value else 0
    gap = 10 * 3 if value else 0
    pad = 15 * 3
    W = max(H, int(pad * 2 + w_lab + gap + w_val))

    light, dark = tone
    # 1. vertical gradient body
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for yy in range(H):
        t = yy / (H - 1)
        c = tuple(int(light[k] + (dark[k] - light[k]) * t) for k in range(3))
        ImageDraw.Draw(body).line([(0, yy), (W, yy)], fill=c + (255,))

    # 2. gloss: a highlight that fades down from the top edge and a soft shade along the bottom
    gloss = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gloss)
    top = int(H * 0.58)
    for yy in range(top):
        a = int(72 * (1 - yy / top) ** 1.4)
        if a:
            gd.line([(0, yy), (W, yy)], fill=(255, 255, 255, a))
    for yy in range(int(H * 0.62), H):
        a = int(55 * (yy - H * 0.62) / (H * 0.38))
        if a:
            gd.line([(0, yy), (W, yy)], fill=(0, 0, 0, a))
    body = Image.alpha_composite(body, gloss)
    rim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle([1, 1, W - 2, H - 2], radius=R - 1, outline=(255, 255, 255, 66), width=2)
    body = Image.alpha_composite(body, rim)

    # 3. clip to the rounded shape
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=R, fill=255)
    clipped = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    clipped.paste(body, (0, 0), mask)

    # 4. text (opaque, drawn after clipping)
    d = ImageDraw.Draw(clipped)
    d.text((pad, H / 2 + 1), label, font=f_lab, fill=(255, 255, 255, 224), anchor="lm")
    if value:
        d.text((pad + w_lab + gap, H / 2 + 1), value, font=f_val, fill=(255, 255, 255, 255), anchor="lm")

    # 5. drop shadow underneath
    out = Image.new("RGBA", (W + 10, H + 10), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W + 10, H + 10), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([6, 8, W + 4, H + 8], radius=R, fill=(0, 0, 0, 80))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
    out.alpha_composite(clipped, (5, 3))
    out.resize(((W + 10) // 2, (H + 10) // 2), Image.LANCZOS).save(path, optimize=True)
    print("wrote", path, os.path.getsize(path) // 1024, "KB")


def unify_frame(paths):
    """Centre both variants on identical transparent canvases so the light and dark marks render the same size."""
    imgs = [Image.open(p).convert("RGBA") for p in paths]
    w = max(i.width for i in imgs)
    h = max(i.height for i in imgs)
    for p, im in zip(paths, imgs):
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
        canvas.save(p, optimize=True)
        print("unified", p, canvas.size)


if __name__ == "__main__":
    light_path = os.path.join(OUT, "logo.png")
    dark_path = os.path.join(OUT, "logo-dark.png")
    wordmark(light_path, text_fill=INK_LIGHT, sub_fill=GREY_LIGHT, plate=None,
             ramp=((150, 112, 46), (206, 170, 92)))
    wordmark(dark_path, text_fill=GOLD_HI, sub_fill=GOLD, plate=NAVY)
    unify_frame([light_path, dark_path])

    # square icon: the same China mark on the site's navy plate
    china_plate(512, plate=NAVY, pad_ratio=0.13).save(os.path.join(OUT, "icon.png"), optimize=True)

    tags = [
        ("27", "个数据图层", ((176, 52, 38), (112, 28, 22))),
        ("344", "座城市", ((176, 52, 38), (112, 28, 22))),
        ("5,843", "个地块", ((176, 52, 38), (112, 28, 22))),
        ("Apache-2.0", "", ((52, 74, 96), (28, 42, 58))),
    ]
    for k, (a, b, tone) in enumerate(tags):
        pill(os.path.join(OUT, f"tag-{k}.png"), a, b, tone)
