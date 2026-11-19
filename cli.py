"""Uso da terminale:  python cli.py file.md --marchio mio-marchio --modello documento --formato pdf"""
import argparse
from pathlib import Path
from engine import convert, list_brands

ap = argparse.ArgumentParser(description="Markdown in PDF / Word / PowerPoint su carta intestata")
ap.add_argument("file", nargs="?")
ap.add_argument("--marchio")
ap.add_argument("--modello")
ap.add_argument("--formato", choices=["pdf", "docx", "pptx"], default="pdf")
ap.add_argument("--out", default=".")
ap.add_argument("--elenco", action="store_true", help="mostra marchi e modelli disponibili")
a = ap.parse_args()
if a.elenco or not a.file:
    for b in list_brands():
        print(f"{b['id']}  ({b['nome']})")
        for m in b["modelli"]:
            print(f"    {m['id']}: {m['nome']}")
    raise SystemExit
data, name, _ = convert(Path(a.file).read_text(encoding="utf-8-sig"), a.marchio, a.modello, a.formato)
out = Path(a.out) / name
out.write_bytes(data)
print(out)
