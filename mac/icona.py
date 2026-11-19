"""Genera icona.icns (Pillow + iconutil di macOS).
Stile: sfondo sfumato scuro, simbolo bianco a tratto spesso e arrotondato, sigla in corsivo."""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = Path(sys.argv[1])
SS = 2          # supersampling
S = 1024 * SS   # lato del disegno


def k(v):
    return int(v * SS)


def sfondo():
    """Sfumatura diagonale blu notte, piu' chiara in alto a sinistra, con un lieve riflesso."""
    base = Image.new("RGB", (S, S))
    px = base.load()
    c0, c1 = (62, 108, 168), (18, 32, 62)       # chiaro -> scuro
    for y in range(S):
        for x in range(S):
            t = (x * 0.55 + y * 0.9) / (S * 1.45)
            t = min(max(t, 0), 1)
            px[x, y] = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
    glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(glow).ellipse((-k(250), -k(300), k(650), k(450)), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(k(160)))
    return Image.composite(Image.new("RGB", (S, S), (120, 170, 225)), base, glow)


def _arrotonda(punti, raggio, chiuso=True):
    """Polilinea con angoli arrotondati (curve quadratiche)."""
    n = len(punti)
    out = []
    for i in range(n):
        if not chiuso and i in (0, n - 1):
            out.append(punti[i])
            continue
        p0, p1, p2 = punti[i - 1], punti[i], punti[(i + 1) % n]
        def vers(a, b):
            dx, dy = b[0] - a[0], b[1] - a[1]
            l = (dx * dx + dy * dy) ** 0.5
            return dx / l, dy / l, l
        ux, uy, lu = vers(p1, p0)
        vx, vy, lv = vers(p1, p2)
        r = min(raggio, lu / 2, lv / 2)
        a_ = (p1[0] + ux * r, p1[1] + uy * r)
        b_ = (p1[0] + vx * r, p1[1] + vy * r)
        for t in [j / 14 for j in range(15)]:
            x = (1 - t) ** 2 * a_[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * b_[0]
            y = (1 - t) ** 2 * a_[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * b_[1]
            out.append((x, y))
    return out


def _tratto(d, pts, w, chiuso=False):
    seq = pts + [pts[0]] if chiuso else pts
    d.line(seq, fill=255, width=w, joint="curve")
    for p in ([pts[0], pts[-1]] if not chiuso else []):
        d.ellipse((p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2), fill=255)


X0, X1, Y0, Y1, CH = 175, 520, 200, 790, 130   # foglio (spazio 1024)
SP = 44                                        # spessore tratto


def glifo():
    g = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(g)
    w = k(SP)
    sc = lambda pts: [(k(x), k(y)) for x, y in pts]
    contorno = sc([(X1 - CH, Y0), (X0, Y0), (X0, Y1), (X1, Y1), (X1, Y0 + CH)])
    pts = _arrotonda(contorno, k(60), chiuso=False)
    _tratto(d, pts, w)
    # chiusura obliqua del contorno e piega
    diag = sc([(X1, Y0 + CH), (X1 - CH, Y0)])
    _tratto(d, [diag[0], diag[1]], w)
    piega = _arrotonda(sc([(X1 - CH, Y0), (X1 - CH, Y0 + CH), (X1, Y0 + CH)]), k(26), chiuso=False)
    _tratto(d, piega, w)
    for (xa, xb, y) in ((255, 440, 420), (255, 440, 520), (255, 360, 620)):
        _tratto(d, sc([(xa, y), (xb, y)]), w)
    return g


def sigla():
    m = Image.new("L", (S, S), 0)
    font = None
    for f, idx in (("/System/Library/Fonts/Supplemental/SnellRoundhand.ttc", 1),
                   ("/System/Library/Fonts/Supplemental/SnellRoundhand.ttc", 0),
                   ("/System/Library/Fonts/Supplemental/Apple Chancery.ttf", 0)):
        try:
            font = ImageFont.truetype(f, k(340), index=idx)
            break
        except Exception:
            continue
    font = font or ImageFont.load_default()
    ImageDraw.Draw(m).text((k(512), k(790)), "md", font=font, fill=255, anchor="ls", stroke_width=k(5), stroke_fill=255)
    return m


def disegno():
    img = sfondo().convert("RGBA")
    bianco = Image.new("RGBA", (S, S), (255, 255, 255, 255))
    ombra = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    glifi = ImageChops.lighter(glifo(), sigla())
    # leggera ombra dietro il simbolo
    sh = glifi.filter(ImageFilter.GaussianBlur(k(14)))
    ombra.paste((0, 10, 30, 110), mask=sh.point(lambda v: int(v * 0.45)))
    img = Image.alpha_composite(img, ImageChops.offset(ombra, 0, k(8)))
    img.paste(bianco, mask=glifi)
    return img


def forma_mac(img):
    """Quadrato arrotondato in stile macOS (824 px dentro 1024) con ombra."""
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    lato, marg = k(824), k(100)
    ridim = img.resize((lato, lato), Image.LANCZOS)
    mask = Image.new("L", (lato, lato), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, lato - 1, lato - 1), radius=k(185), fill=255)
    ombra = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ombra.paste((0, 0, 0, 90), (marg, marg + k(12)), mask)
    ombra = ombra.filter(ImageFilter.GaussianBlur(k(18)))
    out = Image.alpha_composite(out, ombra)
    out.paste(ridim, (marg, marg), mask)
    return out.resize((1024, 1024), Image.LANCZOS)


finale = forma_mac(disegno())
with tempfile.TemporaryDirectory() as t:
    iset = Path(t) / "icona.iconset"
    iset.mkdir()
    for s in (16, 32, 128, 256, 512):
        finale.resize((s, s), Image.LANCZOS).save(iset / f"icon_{s}x{s}.png")
        finale.resize((s * 2, s * 2), Image.LANCZOS).save(iset / f"icon_{s}x{s}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iset), "-o", str(OUT / "icona.icns")], check=True)
finale.save(OUT / "icona.png")
