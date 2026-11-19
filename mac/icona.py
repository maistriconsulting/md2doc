"""Genera icona.icns (usa Pillow e iconutil di macOS)."""
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(sys.argv[1])
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((60, 60, S - 60, S - 60), radius=210, fill=(166, 38, 38, 255))
d.rounded_rectangle((60, 60, S - 60, S // 2), radius=210, fill=(178, 52, 52, 255))
d.rectangle((60, 330, S - 60, S // 2 + 10), fill=(178, 52, 52, 255))
font = None
for f in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
    try:
        font = ImageFont.truetype(f, 430, index=1 if f.endswith(".ttc") else 0)
        break
    except Exception:
        pass
font = font or ImageFont.load_default()
d.text((S / 2, S / 2 - 20), "MD", font=font, fill="white", anchor="mm")
d.polygon([(330, 760), (694, 760), (512, 880)], fill=(255, 255, 255, 235))

with tempfile.TemporaryDirectory() as t:
    iset = Path(t) / "icona.iconset"
    iset.mkdir()
    for s in (16, 32, 128, 256, 512):
        img.resize((s, s), Image.LANCZOS).save(iset / f"icon_{s}x{s}.png")
        img.resize((s * 2, s * 2), Image.LANCZOS).save(iset / f"icon_{s}x{s}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iset), "-o", str(out / "icona.icns")], check=True)
