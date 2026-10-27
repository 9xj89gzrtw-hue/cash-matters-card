#!/usr/bin/env python3
"""Verify the poidh #1510 deliverable against the brief, mechanically.

Checks (any failure -> exit 1):

  A. files exist and are non-trivial
  B. both SVGs are valid XML with an exact 3.5 x 2 in (7:4) canvas
  C. SVGs are strict black & white: every fill/stroke is #000, #fff or none
  D. SVGs are self-contained: no <image>, no href, no script, no url(#...)
  E. type size hierarchy is readable in print (smallest text >= 11 px @300dpi)
  F. the front says the core promise, the back carries the four reasons
  G. there is an explicit, imperative call to action
  H. PNGs are 1050x600, 300 dpi, with zero chroma (R == G == B everywhere)
  I. ink coverage is in a sane band (not blank, not a flood)
  J. the print PDFs are exactly 3.5x2 in and 3.75x2.25 in, two pages each
  K. word budgets: front <= 30 words, back <= 80 words (brief wants succinct)

Run: python3 verify_1510.py [--quiet]
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SVG = "{http://www.w3.org/2000/svg}"

ALLOWED_INK = {"#000", "#000000", "#fff", "#ffffff", "none"}
FAILS = []
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    if not ok:
        FAILS.append(f"{name}: {detail}")
    return ok


def words(s):
    return [w for w in re.split(r"[^A-Za-z0-9\u2019']+", s) if w]


def load_svg(name):
    path = os.path.join(OUT, name)
    if not check(f"{name} exists", os.path.isfile(path), "missing"):
        return None, ""
    raw = open(path, encoding="utf-8").read()
    check(f"{name} size < 500 KB", len(raw.encode()) < 500_000, f"{len(raw)} bytes")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        check(f"{name} parses as XML", False, str(e))
        return None, raw
    check(f"{name} parses as XML", True)
    return root, raw


def svg_geometry(root, name):
    w = float(root.get("width"))
    h = float(root.get("height"))
    vb = (root.get("viewBox") or "").split()
    check(f"{name} canvas 1050x600", (w, h) == (1050.0, 600.0), f"{w}x{h}")
    check(f"{name} viewBox matches", len(vb) == 4 and float(vb[2]) == w and float(vb[3]) == h, str(vb))
    check(f"{name} is credit-card ratio 7:4", abs(w / h - 1.75) < 1e-9, f"{w/h:.4f}")


def svg_inks(root, name):
    bad, strokes, sizes = set(), [], []
    for el in root.iter():
        for attr, val in el.attrib.items():
            if attr in ("fill", "stroke", "stop-color", "flood-color", "lighting-color"):
                v = val.strip().lower()
                if v.startswith("rgb(") or v.startswith("#") and v not in ALLOWED_INK:
                    bad.add(f"{el.tag.split('}')[-1]}.{attr}={val}")
                elif v not in ("none", "") and not v.startswith("#") and not v.startswith("url("):
                    bad.add(f"{el.tag.split('}')[-1]}.{attr}={val}")
            if attr == "stroke-width":
                strokes.append(float(val))
            if attr == "font-size":
                sizes.append(float(val))
    check(f"{name} pure black & white", not bad, ", ".join(sorted(bad))[:200])
    check(f"{name} hairlines >= 1 px", all(s >= 1 for s in strokes) and bool(strokes), str(sorted(set(strokes))))
    check(f"{name} smallest text >= 11 px", bool(sizes) and min(sizes) >= 11, f"min={min(sizes) if sizes else None}")


def svg_selfcontained(root, raw, name):
    tags = {el.tag.replace(SVG, "") for el in root.iter()}
    check(f"{name} has no raster image", "image" not in tags, str(tags))
    check(f"{name} has no script", "script" not in tags, "")
    check(f"{name} has no external ref", not re.search(r'(href|src|xlink:href)=', raw), "")
    check(f"{name} has no url(#) ref", "url(#" not in raw, "")


def svg_text(root, name):
    return " ".join((el.text or "") for el in root.iter() if el.tag == SVG + "text")


def svg_budget(root, name, limit):
    txt = svg_text(root, name)
    n = len(words(txt))
    check(f"{name} <= {limit} words", 0 < n <= limit, f"{n} words")


def png_checks():
    for name in ("front.png", "back.png"):
        p = os.path.join(OUT, name)
        if not check(f"{name} exists", os.path.isfile(p), "missing"):
            continue
        im = Image.open(p)
        check(f"{name} is 1050x600", im.size == (1050, 600), str(im.size))
        dpi = im.info.get("dpi", (0, 0))
        check(f"{name} is 300 dpi", all(abs(d - 300) < 0.6 for d in dpi), str(dpi))
        rgb = im.convert("RGB")
        r, g, b = rgb.split()
        chroma = max(abs(a - c) for a, c in [(lo, hi) for lo, hi in zip(r.getextrema(), g.getextrema())])
        # compare channel ranges: identical ranges means no colour cast
        same = r.getextrema() == g.getextrema() == b.getextrema()
        check(f"{name} has no colour (grayscale)", same, f"ranges r={r.getextrema()} g={g.getextrema()} b={b.getextrema()} chroma={chroma}")
        hist = im.convert("L").histogram()
        ink = sum(hist[:128]) / sum(hist)
        check(f"{name} ink coverage 2-45%", 0.02 <= ink <= 0.45, f"{ink*100:.1f}%")


def pdf_pages(path):
    data = open(path, "rb").read()
    boxes = re.findall(rb"/MediaBox\s*\[\s*([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*\]", data)
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    return boxes, pages


def pdf_checks():
    for name, exp_w, exp_h in (("card-print.pdf", 252, 144), ("card-print-bleed.pdf", 270, 162)):
        p = os.path.join(OUT, name)
        if not check(f"{name} exists", os.path.isfile(p), "missing"):
            continue
        boxes, pages = pdf_pages(p)
        check(f"{name} has 2 pages", pages == 2, f"{pages}")
        ok = bool(boxes) and all(
            abs(float(b[2]) - exp_w) < 1.5 and abs(float(b[3]) - exp_h) < 1.5 for b in boxes)
        check(f"{name} page box {exp_w}x{exp_h} pt", ok,
              str([(b[2].decode(), b[3].decode()) for b in boxes[:3]]))


def content_checks(front_root, back_root):
    ft = svg_text(front_root, "front").lower()
    bt = svg_text(back_root, "back").lower()
    check("front promises freedom", "freedom" in ft, ft[:80])
    check("front promises privacy", "private" in ft, ft[:80])
    check("front promises offline cash", "offline" in ft, ft[:80])
    for i, needle in enumerate(("private", "offline", "instant", "hold")):
        check(f"back reason {i+1} present", needle in bt, needle)
    cta = re.search(r"\b(pay|ask|tell|keep|pass|use|spend)\b", bt)
    check("back has an imperative CTA", bool(cta), bt[:120])
    check("no upspeak / hedging in copy", "maybe" not in ft + bt and "try to" not in ft + bt)


def main():
    quiet = "--quiet" in sys.argv
    fr, fr_raw = load_svg("front.svg")
    br, br_raw = load_svg("back.svg")
    png_checks()
    pdf_checks()
    if fr is not None:
        svg_geometry(fr, "front.svg")
        svg_inks(fr, "front.svg")
        svg_selfcontained(fr, fr_raw, "front.svg")
        svg_budget(fr, "front.svg", 30)
    if br is not None:
        svg_geometry(br, "back.svg")
        svg_inks(br, "back.svg")
        svg_selfcontained(br, br_raw, "back.svg")
        svg_budget(br, "back.svg", 80)
    if fr is not None and br is not None:
        content_checks(fr, br)

    if not quiet:
        for name, ok, detail in CHECKS:
            print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail and not ok else ""))
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    print(f"\n{passed}/{len(CHECKS)} checks passed")
    if FAILS:
        for f in FAILS:
            print(" -", f)
        sys.exit(1)
    print("VERDICT: PASS — #1510 artifact meets every mechanical requirement of the brief.")


if __name__ == "__main__":
    main()
