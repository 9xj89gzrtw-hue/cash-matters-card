#!/usr/bin/env python3
"""Build the poidh #1510 deliverable: a two-sided, black-and-white, credit-card
sized handout about cash.

Outputs (all in ./out):
  front.svg, back.svg          vector source, 1050x600 px = 3.5x2 in at 300 dpi
  front.png, back.png          raster, 300 dpi, grayscale, no colour channel left
  card-print.pdf               2 pages, exact 3.5x2 in trim
  card-print-bleed.pdf         2 pages, 3.75x2.25 in (0.125 in bleed each side)
  card-preview.png             both sides side by side, for the claim page

Run:  python3 build_1510.py
"""
import html
import os
import shutil
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
W, H = 1050, 600          # 3.5 x 2 in at 300 dpi
BLEED = 38                # 0.125 in at 300 dpi, rounded
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def t(x, y, s, size, weight=400, ls=0, anchor="start", fill="#000", italic=False):
    attrs = [
        f'x="{x}"', f'y="{y}"', f'font-family="{FONT}"', f'font-size="{size}"',
        f'font-weight="{weight}"', f'fill="{fill}"',
    ]
    if ls:
        attrs.append(f'letter-spacing="{ls}"')
    if anchor != "start":
        attrs.append(f'text-anchor="{anchor}"')
    if italic:
        attrs.append('font-style="italic"')
    return f'<text {" ".join(attrs)}>{html.escape(s)}</text>'


def rule(x1, y1, x2, y2, width=1, color="#000"):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{width}"/>')


def svg(body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}" role="img">\n'
            f'<rect width="{W}" height="{H}" fill="#fff"/>\n'
            + "\n".join(body) + "\n</svg>\n")


# ---------------------------------------------------------------- front ----
front = [
    # top label + hairline
    t(72, 78, "KEEP CASH ALIVE", 13, 700, 5.2),
    rule(72, 96, 978, 96),
    # headline
    t(70, 210, "Cash is", 86, 700, -2.4),
    t(70, 298, "freedom you", 86, 700, -2.4),
    t(70, 386, "can hold.", 86, 700, -2.4),
    # one-line promise
    t(72, 438, "Private by default. Instant. Offline. Nobody can freeze it.", 22),
    rule(72, 480, 978, 480),
    t(72, 518, "WHY CASH MATTERS \u2192", 13, 700, 3.4),
    t(978, 518, "TURN OVER", 13, 700, 3.4, anchor="end"),
    # bottom band
    '<rect x="0" y="548" width="1050" height="52" fill="#000"/>',
    t(525, 581, "PRIVATE  \u00b7  FUNGIBLE  \u00b7  OFFLINE  \u00b7  UNTRACEABLE  \u00b7  YOURS",
      12, 500, 3.0, anchor="middle", fill="#fff"),
]

# ----------------------------------------------------------------- back ----
BULLETS = [
    ("Private by default", "No one records what you buy or where."),
    ("Works offline", "No power, no signal, no bank required."),
    ("Instant and final", "No fees, no holds, no middleman."),
    ("Money you hold", "Not a number someone else can freeze."),
]

back = [
    t(72, 104, "Why cash matters", 32, 700, -0.6),
    t(72, 136, "What disappears without cash.", 14),
]
y = 196
for head, body in BULLETS:
    back.append(f'<rect x="72" y="{y - 13}" width="8" height="8" fill="#000"/>')
    back.append(t(96, y, head, 18, 700))
    back.append(t(96, y + 24, body, 15))
    y += 82

# call-to-action block
back += [
    '<rect x="620" y="60" width="358" height="452" fill="#000"/>',
    t(648, 104, "WHAT YOU CAN DO", 11, 700, 3.0, fill="#fff"),
    t(648, 198, "Pay cash.", 27, 700, -0.4, fill="#fff"),
    t(648, 242, "Ask for cash.", 27, 700, -0.4, fill="#fff"),
    t(648, 286, "Tell one person.", 27, 700, -0.4, fill="#fff"),
    rule(648, 322, 950, 322, 1, "#fff"),
    t(648, 354, "Every cash payment is a vote", 13, 400, 0, fill="#fff"),
    t(648, 374, "for a free economy.", 13, 400, 0, fill="#fff"),
    t(648, 470, "Keep this card. Pass it on.", 12, 500, 0, fill="#fff"),
]

back += [
    rule(72, 548, 978, 548),
    t(72, 578, "Cash works when nothing else does.", 13),
]

FRONT_SVG = svg(front)
BACK_SVG = svg(back)


def chrome_render(svg_path, png_path):
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", f"--window-size={W},{H}",
        f"--screenshot={png_path}", "file://" + svg_path,
    ], check=True, capture_output=True)
    im = Image.open(png_path).convert("L")
    if im.size != (W, H):
        raise SystemExit(f"chrome produced {im.size}, expected {(W, H)}")
    im.save(png_path, dpi=(300, 300), optimize=True)
    return im


def two_page_pdf(imgs, path, inch_w, inch_h):
    """Multi-page PDF whose physical page size is exactly inch_w x inch_h."""
    imgs[0].save(
        path, save_all=True, append_images=imgs[1:], resolution=300.0,
        quality=95, optimize=True,
    )
    # PIL derives the page box from pixel size / resolution, which is what we want:
    # 1050/300 = 3.5 in, 600/300 = 2 in.


def bleed_page(im, pad_px):
    """Padded page at 300 dpi: white margin added around the trim area."""
    canvas = Image.new("L", (W + 2 * pad_px, H + 2 * pad_px), 255)
    canvas.paste(im, (pad_px, pad_px))
    return canvas


def main():
    os.makedirs(OUT, exist_ok=True)
    fsvg = os.path.join(OUT, "front.svg")
    bsvg = os.path.join(OUT, "back.svg")
    open(fsvg, "w").write(FRONT_SVG)
    open(bsvg, "w").write(BACK_SVG)

    fpng = os.path.join(OUT, "front.png")
    bpng = os.path.join(OUT, "back.png")
    fim = chrome_render(fsvg, fpng)
    bim = chrome_render(bsvg, bpng)

    two_page_pdf([fim, bim], os.path.join(OUT, "card-print.pdf"), 3.5, 2.0)

    fb = bleed_page(fim, BLEED)
    bb = bleed_page(bim, BLEED)
    two_page_pdf([fb, bb], os.path.join(OUT, "card-print-bleed.pdf"),
                 (W + 2 * BLEED) / 300.0, (H + 2 * BLEED) / 300.0)

    # side-by-side proof sheet
    gap, label_h = 40, 44
    sheet = Image.new("L", (W, 2 * H + gap * 3 + label_h * 2 + 30), 255)
    yy = gap
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    d.text((2, yy - 30), "FRONT  \u2014  3.5 x 2 in", fill=0)
    sheet.paste(fim, (0, yy))
    yy += H + gap + label_h
    d.text((2, yy - 30), "BACK  \u2014  3.5 x 2 in", fill=0)
    sheet.paste(bim, (0, yy))
    sheet.save(os.path.join(OUT, "card-preview.png"), dpi=(150, 150), optimize=True)

    for name in ("front.svg", "back.svg", "front.png", "back.png",
                 "card-print.pdf", "card-print-bleed.pdf", "card-preview.png"):
        p = os.path.join(OUT, name)
        print(f"{name:24s} {os.path.getsize(p):8d} bytes")


if __name__ == "__main__":
    main()
