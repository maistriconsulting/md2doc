"""Motore PDF: markdown -> HTML -> WeasyPrint, con carta intestata via CSS @page."""
import html
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

from weasyprint import HTML, URLFetcher

from .config import footer_text
from .parser import md_instance, split_front_matter, parse_markdown, runs_text

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def data_it(d=None):
    d = d or date.today()
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


def _fetcher(allowed_dir):
    """Consente solo data:, https: e file dentro la cartella del marchio."""
    allowed_dir = Path(allowed_dir).resolve()

    class SafeFetcher(URLFetcher):
        def fetch(self, url, headers=None):
            if url.startswith(("data:", "https://")):
                return super().fetch(url, headers)
            if url.startswith("file://"):
                p = Path(unquote(urlparse(url).path)).resolve()
                if allowed_dir in p.parents:
                    return super().fetch(url, headers)
            raise ValueError(f"Risorsa bloccata: {url}")
    return SafeFetcher()


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "documento"


def _css(prof):
    c, f, m = prof["colori"], prof["font"], prof["modello"]["pdf"]
    mt, mr, mb, ml = m["margini_mm"]
    return f"""
@page {{
  size: {m['dimensione']};
  margin: {mt}mm {mr}mm {mb}mm {ml}mm;
  @top-left {{ content: element(hdr); width: 100%; vertical-align: top; }}
  @bottom-left {{ content: element(ftr); width: 78%; vertical-align: top; }}
  {"@bottom-right { content: 'Pagina ' counter(page) ' di ' counter(pages); font: 8pt " + f['testo'] + ", sans-serif; color: " + c['tenue'] + "; vertical-align: top; }" if m['numera_pagine'] else ""}
}}
@page cover {{
  margin: 0;
  @top-left {{ content: none; }} @bottom-left {{ content: none; }} @bottom-right {{ content: none; }}
}}
html {{ font-family: '{f['testo']}', 'Liberation Sans', 'DejaVu Sans', sans-serif;
        font-size: {m['corpo_pt']}pt; color: {c['testo']}; line-height: {m['interlinea']}; }}
#hdr {{ position: running(hdr); border-bottom: 1.2pt solid {c['primario']}; padding-bottom: 3mm;
        display: flex; justify-content: space-between; align-items: flex-end; }}
#hdr img {{ height: {prof['logo_altezza_mm']}mm; }}
#hdr .brand {{ font: 8pt '{f['testo']}', sans-serif; color: {c['tenue']}; text-align: right; }}
#ftr {{ position: running(ftr); font: 8pt '{f['testo']}', sans-serif; color: {c['tenue']};
        border-top: 0.5pt solid {c['secondario']}; padding-top: 2mm; }}
h1, h2, h3, h4 {{ font-family: '{f['titoli']}', 'Liberation Sans', 'DejaVu Sans', sans-serif;
                  color: {c['primario']}; line-height: 1.2; break-after: avoid; }}
h1 {{ font-size: 1.7em; margin: 1.4em 0 .5em; border-bottom: 0.8pt solid {c['secondario']}; padding-bottom: .2em; }}
h2 {{ font-size: 1.35em; margin: 1.3em 0 .4em; }}
h3 {{ font-size: 1.12em; margin: 1.1em 0 .3em; }}
h4 {{ font-size: 1em; margin: 1em 0 .3em; text-transform: uppercase; letter-spacing: .03em; color: {c['secondario']}; }}
p {{ margin: 0 0 .7em; orphans: 3; widows: 3; }}
a {{ color: {c['secondario']}; }}
ul, ol {{ margin: 0 0 .8em 0; padding-left: 1.4em; }}
li {{ margin-bottom: .25em; }}
li > p {{ margin: 0 0 .3em; }}
blockquote {{ margin: .8em 0; padding: .4em 1em; border-left: 3pt solid {c['secondario']};
             background: {c['sfondo_chiaro']}; color: {c['tenue']}; break-inside: avoid; }}
blockquote p:last-child {{ margin-bottom: 0; }}
code {{ font-family: '{f['monospazio']}', 'DejaVu Sans Mono', monospace; font-size: .88em;
        background: {c['sfondo_chiaro']}; padding: 0 .25em; }}
pre {{ background: {c['sfondo_chiaro']}; padding: .6em .8em; border-left: 3pt solid {c['primario']};
       white-space: pre-wrap; word-wrap: break-word; break-inside: avoid; margin: .8em 0; }}
pre code {{ background: none; padding: 0; font-size: .85em; }}
hr {{ border: 0; border-top: 0.6pt solid {c['secondario']}; margin: 1.2em 0; }}
table {{ width: 100%; border-collapse: collapse; margin: .9em 0; font-size: .92em; }}
th {{ background: {c['primario']}; color: #fff; text-align: left; padding: .4em .6em; }}
td {{ padding: .35em .6em; border-bottom: 0.5pt solid #d6dae0; vertical-align: top; }}
tr {{ break-inside: avoid; }}
tbody tr:nth-child(even) td {{ background: {c['sfondo_chiaro']}; }}
thead {{ display: table-header-group; }}
img {{ max-width: 100%; }}
.titleblock {{ margin: 0 0 1.4em; }}
.titleblock .kind {{ font: 600 8.5pt '{f['testo']}', sans-serif; letter-spacing: .12em;
                     text-transform: uppercase; color: {c['secondario']}; }}
.titleblock h1.doc {{ font-size: 2em; border: 0; margin: .15em 0 .15em; padding: 0; }}
.titleblock .sub {{ font-size: 1.2em; color: {c['tenue']}; margin: 0 0 .5em; }}
.titleblock .meta {{ font-size: .85em; color: {c['tenue']}; border-top: 0.5pt solid #d6dae0;
                     padding-top: .5em; }}
.titleblock .meta span {{ margin-right: 1.6em; }}
/* copertina */
.cover {{ page: cover; break-after: page; height: 297mm; position: relative; }}
.cover .band {{ position: absolute; left: 0; top: 0; bottom: 0; width: 18mm; background: {c['primario']}; }}
.cover .inner {{ position: absolute; left: 38mm; right: 22mm; top: 36mm; }}
.cover img.logo {{ height: {prof['logo_altezza_mm'] * 1.6}mm; margin-bottom: 70mm; }}
.cover .kind {{ font: 600 10pt '{f['testo']}', sans-serif; letter-spacing: .15em;
                text-transform: uppercase; color: {c['secondario']}; }}
.cover h1 {{ font-size: 30pt; border: 0; margin: 4mm 0; padding: 0; color: {c['primario']}; }}
.cover .sub {{ font-size: 15pt; color: {c['tenue']}; }}
.cover .meta {{ position: absolute; top: 175mm; left: 0; font-size: 10pt; color: {c['tenue']}; line-height: 1.8; }}
.cover .foot {{ position: absolute; top: 235mm; left: 0; right: 0; font-size: 8pt; color: {c['tenue']};
                border-top: 0.5pt solid {c['secondario']}; padding-top: 3mm; }}
.toc {{ break-after: page; }}
.toc h2 {{ margin-top: 0; }}
.toc ol {{ list-style: none; padding: 0; }}
.toc li {{ margin: .35em 0; }}
.toc a {{ text-decoration: none; color: {c['testo']}; }}
.toc li.l2 {{ margin-left: 1.2em; font-size: .95em; color: {c['tenue']}; }}
"""


def _meta_line(meta, prof):
    items = []
    d = meta.get("date") or meta.get("data") or data_it()
    items.append(f"<span>{html.escape(str(d))}</span>")
    for key, lab in (("client", "Cliente"), ("cliente", "Cliente"), ("author", "A cura di"),
                     ("autore", "A cura di"), ("version", "Versione"), ("versione", "Versione")):
        if meta.get(key):
            items.append(f"<span>{lab}: {html.escape(str(meta[key]))}</span>")
    return "".join(items)


def _slugify_headings(html_body):
    """Aggiunge id ai titoli e restituisce (html, [(livello, testo, id)])."""
    out, toc, n = [], [], [0]

    def repl(mo):
        n[0] += 1
        lvl, attrs, inner = mo.group(1), mo.group(2), mo.group(3)
        hid = f"h{n[0]}"
        toc.append((int(lvl), re.sub(r"<[^>]+>", "", inner), hid))
        return f'<h{lvl} id="{hid}"{attrs}>{inner}</h{lvl}>'
    out = re.sub(r"<h([1-3])([^>]*)>(.*?)</h\1>", repl, html_body, flags=re.S)
    return out, toc


def build_pdf(md_text, prof):
    meta, blocks, body = parse_markdown(md_text)
    model = prof["modello"]
    brand = prof["marchio"]
    md = md_instance()
    # se il titolo e' stato preso dal primo H1, lo si toglie dal corpo
    fm, raw = split_front_matter(md_text)
    if not fm.get("title"):
        raw = re.sub(r"^\s*#\s+.+\n?", "", raw, count=1)
    body_html = md.render(raw)
    body_html, toc = _slugify_headings(body_html)

    logo_uri = prof["logo_path"].as_uri() if prof["logo_path"] else ""
    logo_tag = f'<img src="{logo_uri}">' if logo_uri else f'<b>{html.escape(brand.get("nome", ""))}</b>'
    title = html.escape(str(meta.get("title", "Documento")))
    sub = html.escape(str(meta.get("subtitle") or meta.get("sottotitolo") or ""))
    kind = html.escape(str(meta.get("doc_type") or meta.get("tipo") or ""))
    footer = html.escape(footer_text(prof))

    parts = [f'<div id="hdr">{logo_tag}<div class="brand">{html.escape(brand.get("nome", ""))}</div></div>',
             f'<div id="ftr">{footer}</div>']

    if model["copertina"]:
        parts.append(
            f'<section class="cover"><div class="band"></div><div class="inner">{logo_tag.replace("<img", "<img class=logo")}'
            f'<div class="kind">{kind}</div><h1>{title}</h1><div class="sub">{sub}</div>'
            f'<div class="meta">{_meta_line(meta, prof).replace("</span><span>", "<br>").replace("<span>", "").replace("</span>", "")}</div>'
            f'<div class="foot">{footer}</div></div></section>')
        if toc and meta.get("indice", True):
            items = "".join(f'<li class="l{2 if l > 1 else 1}"><a href="#{i}">{html.escape(t)}</a></li>'
                            for l, t, i in toc if l <= 2)
            parts.append(f'<section class="toc"><h2>Indice</h2><ol>{items}</ol></section>')
    else:
        parts.append(f'<div class="titleblock"><div class="kind">{kind}</div><h1 class="doc">{title}</h1>'
                     f'{f"<div class=sub>{sub}</div>" if sub else ""}<div class="meta">{_meta_line(meta, prof)}</div></div>')

    parts.append(body_html)
    doc = (f'<!doctype html><html lang="{prof["lingua"]}"><head><meta charset="utf-8">'
           f'<title>{title}</title><style>{_css(prof)}</style></head><body>{"".join(parts)}</body></html>')
    pdf = HTML(string=doc, base_url=str(prof["dir"]), url_fetcher=_fetcher(prof["dir"])).write_pdf()
    return pdf, _slug(str(meta.get("title", "documento")))
