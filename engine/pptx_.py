"""Motore PPTX con python-pptx. Slide 16:9 costruite da zero, nessun modello PowerPoint esterno."""
import io
import math

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt
from lxml import etree

from .config import footer_text
from .parser import parse_markdown, runs_text
from .pdf import data_it, _slug

W, H = 13.333, 7.5
MX = 0.7                     # margine orizzontale
BODY_TOP, BODY_BOTTOM = 1.6, 6.7
BODY_W = W - 2 * MX


def _rgb(h):
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _lines(text, width_in, pt):
    cpl = max(10, int(width_in / (pt * 0.47 / 72)))
    n = 0
    for part in (text.split("\n") or [""]):
        n += max(1, math.ceil(len(part) / cpl))
    return n


class _Deck:
    def __init__(self, prof, meta):
        self.p, self.c, self.f = prof, prof["colori"], prof["font"]
        self.meta = meta
        self.body_pt = prof["modello"]["pptx"]["corpo_pt"]
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.blank = self.prs.slide_layouts[6]
        self.footer = footer_text(prof)
        self.cur = None          # slide corrente
        self.y = BODY_TOP
        self.group = []          # elementi testuali in attesa di essere scritti
        self.group_h = 0.0
        self.title = ""

    # ---------- primitive ----------
    def rect(self, slide, x, y, w, h, fill):
        s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        s.fill.solid()
        s.fill.fore_color.rgb = _rgb(fill)
        s.line.fill.background()
        s.shadow.inherit = False
        return s

    def textbox(self, slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        return tb, tf

    def write_runs(self, par, runs, size, color=None, bold=False, italic=False, font=None):
        for r in runs:
            run = par.add_run()
            run.text = r["text"]
            fnt = run.font
            fnt.name = self.f["monospazio"] if r["code"] else (font or self.f["testo"])
            fnt.size = Pt(size * (0.9 if r["code"] else 1))
            fnt.bold = bool(r["bold"] or bold)
            fnt.italic = bool(r["italic"] or italic)
            if r["strike"]:
                run._r.get_or_add_rPr().set("strike", "sngStrike")
            if r["href"]:
                run.hyperlink.address = r["href"]
                fnt.color.rgb = _rgb(self.c["secondario"])
            else:
                fnt.color.rgb = _rgb(color or self.c["testo"])

    def bullet(self, par, marker, level):
        ppr = par._p.get_or_add_pPr()
        for t in ("a:buNone", "a:buChar", "a:buAutoNum", "a:buFont"):
            for e in ppr.findall(qn(t)):
                ppr.remove(e)
        if marker:
            ppr.set("marL", str(int(Inches(0.32 + 0.42 * level))))
            ppr.set("indent", str(int(-Inches(0.32))))
            bf = etree.SubElement(ppr, qn("a:buFont"))
            bf.set("typeface", "Arial")
            bc = etree.SubElement(ppr, qn("a:buChar"))
            bc.set("char", marker)
        else:
            ppr.set("marL", str(int(Inches(0.42 * level))))
            ppr.set("indent", "0")
            etree.SubElement(ppr, qn("a:buNone"))

    def slide_number(self, slide):
        tb, tf = self.textbox(slide, W - MX - 1.0, 7.0, 1.0, 0.25)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        fld = etree.SubElement(p._p, qn("a:fld"))
        fld.set("id", "{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}")
        fld.set("type", "slidenum")
        rpr = etree.SubElement(fld, qn("a:rPr"))
        rpr.set("lang", "it-IT")
        rpr.set("sz", "1000")
        sf = etree.SubElement(rpr, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr")).set("val", self.c["tenue"].lstrip("#"))
        etree.SubElement(rpr, qn("a:latin")).set("typeface", self.f["testo"])
        etree.SubElement(fld, qn("a:t")).text = "‹#›"

    def footer_bar(self, slide):
        self.rect(slide, MX, 6.95, BODY_W, 0.012, self.c["secondario"])
        tb, tf = self.textbox(slide, MX, 7.02, BODY_W - 1.3, 0.25)
        r = tf.paragraphs[0].add_run()
        r.text = self.footer
        r.font.size = Pt(9)
        r.font.name = self.f["testo"]
        r.font.color.rgb = _rgb(self.c["tenue"])
        self.slide_number(slide)

    def logo(self, slide, x, y, h):
        lp = self.p["logo_path"]
        if lp:
            slide.shapes.add_picture(str(lp), Inches(x), Inches(y), height=Inches(h))

    # ---------- slide speciali ----------
    def cover(self):
        s = self.prs.slides.add_slide(self.blank)
        self.rect(s, 0, 0, 0.55, H, self.c["primario"])
        self.logo(s, 1.3, 0.7, 0.9)
        m = self.meta
        kind = str(m.get("doc_type") or m.get("tipo") or "")
        y = 2.5
        if kind:
            tb, tf = self.textbox(s, 1.3, y, W - 2.6, 0.4)
            self.write_runs(tf.paragraphs[0], [dict(text=kind.upper(), bold=True, italic=False, strike=False,
                                                    code=False, href=None)], 14, self.c["secondario"])
            y += 0.5
        tb, tf = self.textbox(s, 1.3, y, W - 2.6, 1.8, MSO_ANCHOR.TOP)
        self.write_runs(tf.paragraphs[0], [dict(text=str(m.get("title", "Documento")), bold=True, italic=False,
                                                strike=False, code=False, href=None)],
                        40, self.c["primario"], font=self.f["titoli"])
        ty = y + 0.4 + 0.75 * _lines(str(m.get("title", "")), W - 2.6, 40)
        sub = str(m.get("subtitle") or m.get("sottotitolo") or "")
        if sub:
            tb, tf = self.textbox(s, 1.3, ty, W - 2.6, 0.8)
            self.write_runs(tf.paragraphs[0], [dict(text=sub, bold=False, italic=False, strike=False,
                                                    code=False, href=None)], 22, self.c["tenue"])
        items = [str(m.get("date") or m.get("data") or data_it())]
        for key, lab in (("client", "Cliente"), ("cliente", "Cliente"), ("author", "A cura di"),
                         ("autore", "A cura di"), ("version", "Versione"), ("versione", "Versione")):
            if m.get(key):
                items.append(f"{lab}: {m[key]}")
        tb, tf = self.textbox(s, 1.3, 5.9, W - 2.6, 0.5)
        self.write_runs(tf.paragraphs[0], [dict(text="    ".join(items), bold=False, italic=False,
                                                strike=False, code=False, href=None)], 14, self.c["tenue"])
        self.rect(s, 1.3, 6.95, W - 2.0, 0.012, self.c["secondario"])
        tb, tf = self.textbox(s, 1.3, 7.02, W - 2.6, 0.25)
        self.write_runs(tf.paragraphs[0], [dict(text=self.footer, bold=False, italic=False, strike=False,
                                                code=False, href=None)], 9, self.c["tenue"])

    def section(self, text):
        self.flush_slide()
        s = self.prs.slides.add_slide(self.blank)
        self.rect(s, 0, 0, W, H, self.c["sfondo_chiaro"])
        self.rect(s, 0, 0, 0.55, H, self.c["primario"])
        tb, tf = self.textbox(s, 1.3, 2.6, W - 2.6, 2.0, MSO_ANCHOR.MIDDLE)
        self.write_runs(tf.paragraphs[0], [dict(text=text, bold=True, italic=False, strike=False,
                                                code=False, href=None)], 38, self.c["primario"],
                        font=self.f["titoli"])
        self.logo(s, W - MX - 2.2, 0.45, 0.5)
        self.footer_bar(s)
        self.cur = None

    # ---------- slide di contenuto ----------
    def new_slide(self, title, cont=False):
        self.flush_slide()
        s = self.prs.slides.add_slide(self.blank)
        self.cur, self.y, self.title = s, BODY_TOP, title
        shown = title + (" (segue)" if cont else "")
        tb, tf = self.textbox(s, MX, 0.45, BODY_W - 2.6, 0.85, MSO_ANCHOR.BOTTOM)
        size = 28 if _lines(shown, BODY_W - 2.6, 28) == 1 else 22
        self.write_runs(tf.paragraphs[0], [dict(text=shown, bold=True, italic=False, strike=False,
                                                code=False, href=None)], size, self.c["primario"],
                        font=self.f["titoli"])
        self.rect(s, MX, 1.36, BODY_W, 0.03, self.c["primario"])
        self.logo(s, W - MX - 2.2, 0.5, 0.5)
        self.footer_bar(s)

    def flush_group(self):
        if not self.group or self.cur is None:
            self.group, self.group_h = [], 0.0
            return
        tb, tf = self.textbox(self.cur, MX, self.y, BODY_W, max(self.group_h, 0.3))
        first = True
        for el in self.group:
            par = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            self.render_text(par, el)
        self.y += self.group_h
        self.group, self.group_h = [], 0.0

    def flush_slide(self):
        self.flush_group()

    def render_text(self, par, el):
        k = el["k"]
        bp = self.body_pt
        par.space_after = Pt(6)
        if k == "p":
            self.bullet(par, el["marker"], el["level"])
            size = bp - 2 * min(el["level"], 2)
            if el["marker"] and el["marker"] not in ("•", "–", "▪"):
                pass
            self.write_runs(par, el["runs"], size)
        elif k == "num":
            self.bullet(par, None, el["level"])
            size = bp - 2 * min(el["level"], 2)
            ml = el["level"]
            par._p.get_or_add_pPr().set("marL", str(int(Inches(0.42 + 0.42 * ml))))
            par._p.get_or_add_pPr().set("indent", str(int(-Inches(0.42))))
            self.write_runs(par, [dict(text=el["num"] + "\t", bold=True, italic=False, strike=False,
                                       code=False, href=None)], size, self.c["primario"])
            self.write_runs(par, el["runs"], size)
        elif k == "sub":
            self.bullet(par, None, 0)
            par.space_before = Pt(6)
            self.write_runs(par, el["runs"], bp + 2, self.c["secondario"], bold=True, font=self.f["titoli"])
        elif k == "quote":
            self.bullet(par, None, 0)
            par._p.get_or_add_pPr().set("marL", str(int(Inches(0.4))))
            self.write_runs(par, el["runs"], bp - 1, self.c["tenue"], italic=True)
        elif k == "code":
            self.bullet(par, None, 0)
            self.write_runs(par, [dict(text=el["text"], bold=False, italic=False, strike=False,
                                       code=True, href=None)], bp - 4)

    def height_of(self, el):
        bp = self.body_pt
        k = el["k"]
        if k in ("p", "num"):
            size = bp - 2 * min(el["level"], 2)
            w = BODY_W - 0.32 - 0.42 * el["level"]
            return _lines(runs_text(el["runs"]), w, size) * size * 1.2 / 72 + 6 / 72
        if k == "sub":
            return _lines(runs_text(el["runs"]), BODY_W, bp + 2) * (bp + 2) * 1.2 / 72 + 12 / 72
        if k == "quote":
            return _lines(runs_text(el["runs"]), BODY_W - 0.4, bp - 1) * (bp - 1) * 1.2 / 72 + 6 / 72
        if k == "code":
            return _lines(el["text"], BODY_W, (bp - 4) * 1.15) * (bp - 4) * 1.2 / 72 + 6 / 72
        return 0.4

    def add_text(self, el):
        h = self.height_of(el)
        if self.cur is None:
            self.new_slide(self.meta.get("title", "Documento"))
        if self.y + self.group_h + h > BODY_BOTTOM and (self.group or self.y > BODY_TOP):
            self.flush_group()
            self.new_slide(self.title, cont=True)
        self.group.append(el)
        self.group_h += h

    # ---------- tabelle ----------
    def add_table(self, el):
        header, rows, aligns = el["header"], el["rows"], el["aligns"]
        ncol = max(len(header), max((len(r) for r in rows), default=0))
        if ncol == 0:
            return
        if self.cur is None:
            self.new_slide(self.meta.get("title", "Documento"))
        self.flush_group()
        tsize = max(10, min(14, self.body_pt - 4)) if ncol <= 4 else max(9, min(12, self.body_pt - 6))
        weights = []
        for i in range(ncol):
            lens = [len(runs_text(header[i])) if i < len(header) else 0]
            lens += [len(runs_text(r[i])) for r in rows if i < len(r)]
            weights.append(max(6, min(40, max(lens))))
        tot = sum(weights)
        widths = [BODY_W * w / tot for w in weights]

        def row_h(cells):
            n = 1
            for i in range(ncol):
                t = runs_text(cells[i]) if i < len(cells) else ""
                n = max(n, _lines(t, widths[i] - 0.2, tsize))
            return n * tsize * 1.2 / 72 + 0.16

        hh = row_h(header) if header else 0
        pending = list(rows)
        first = True
        while pending or first:
            first = False
            avail = BODY_BOTTOM - self.y - hh
            chunk, used = [], 0
            while pending:
                rh = row_h(pending[0])
                if used + rh > avail and chunk:
                    break
                if used + rh > avail and not chunk and self.y > BODY_TOP:
                    break
                chunk.append(pending.pop(0))
                used += rh
            if not chunk and pending:
                self.new_slide(self.title, cont=True)
                continue
            self._draw_table(header, chunk, aligns, widths, tsize, ncol, row_h)
            if pending:
                self.new_slide(self.title, cont=True)

    def _draw_table(self, header, rows, aligns, widths, tsize, ncol, row_h):
        nrows = len(rows) + (1 if header else 0)
        heights = ([row_h(header)] if header else []) + [row_h(r) for r in rows]
        gs = self.cur.shapes.add_table(nrows, ncol, Inches(MX), Inches(self.y), Inches(BODY_W),
                                       Inches(sum(heights)))
        tbl = gs.table
        tblPr = tbl._tbl.tblPr
        for a in ("firstRow", "bandRow"):
            tblPr.set(a, "0")
        sid = tblPr.find(qn("a:tableStyleId"))
        if sid is not None:
            sid.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"   # nessuno stile, niente griglia
        for i, w in enumerate(widths):
            tbl.columns[i].width = Inches(w)
        amap = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
        allrows = ([header] if header else []) + rows
        for ri, cells in enumerate(allrows):
            tbl.rows[ri].height = Inches(heights[ri])
            is_head = bool(header) and ri == 0
            for ci in range(ncol):
                cell = tbl.cell(ri, ci)
                cell.margin_left = cell.margin_right = Inches(0.08)
                cell.margin_top = cell.margin_bottom = Inches(0.04)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                cell.fill.solid()
                if is_head:
                    cell.fill.fore_color.rgb = _rgb(self.c["primario"])
                else:
                    bi = ri - (1 if header else 0)
                    cell.fill.fore_color.rgb = _rgb(self.c["sfondo_chiaro"] if bi % 2 else "#FFFFFF")
                par = cell.text_frame.paragraphs[0]
                par.alignment = amap.get(aligns[ci] if ci < len(aligns) else "left", PP_ALIGN.LEFT)
                runs = cells[ci] if ci < len(cells) else []
                if is_head:
                    self.write_runs(par, runs, tsize, "#FFFFFF", bold=True)
                else:
                    self.write_runs(par, runs, tsize)
                # bordo inferiore sottile
                tcPr = cell._tc.get_or_add_tcPr()
                ln = etree.Element(qn("a:lnB"))
                ln.set("w", "6350")
                sf = etree.SubElement(ln, qn("a:solidFill"))
                etree.SubElement(sf, qn("a:srgbClr")).set("val", "D6DAE0")
                tcPr.insert(0, ln)
        self.y += sum(heights) + 0.15


def _flatten(blocks, level=0, out=None, slide_level=2):
    """Blocchi -> elementi di corpo per le slide (senza titoli di livello slide)."""
    out = out if out is not None else []
    for b in blocks:
        t = b["type"]
        if t == "heading":
            out.append(dict(k="sub", runs=b["runs"]))
        elif t == "paragraph":
            out.append(dict(k="p", runs=b["runs"], level=level, marker=None))
        elif t == "list":
            for idx, it in enumerate(b["items"], 1):
                first = True
                for sub in it["blocks"]:
                    if first and sub["type"] == "paragraph":
                        if b["ordered"]:
                            out.append(dict(k="num", runs=sub["runs"], level=level, num=f"{idx}."))
                        else:
                            out.append(dict(k="p", runs=sub["runs"], level=level,
                                            marker=("•", "–", "▪")[min(level, 2)]))
                        first = False
                    elif sub["type"] == "list":
                        _flatten([sub], level + 1, out, slide_level)
                    else:
                        _flatten([sub], level + 1, out, slide_level)
                        first = False
        elif t == "quote":
            for s in b["blocks"]:
                if s["type"] == "paragraph":
                    out.append(dict(k="quote", runs=s["runs"]))
                else:
                    _flatten([s], level, out, slide_level)
        elif t == "code":
            out.append(dict(k="code", text=b["text"]))
        elif t == "table":
            out.append(dict(k="table", header=b["header"], rows=b["rows"], aligns=b["aligns"]))
    return out


def build_pptx(md_text, prof):
    meta, blocks, _ = parse_markdown(md_text)
    cfg = prof["modello"]["pptx"]
    lvl = int(meta.get("slide_level") or cfg.get("livello_slide") or 0)
    if lvl not in (1, 2):
        lvl = 2 if any(b["type"] == "heading" and b["level"] == 2 for b in blocks) else 1
    deck = _Deck(prof, meta)
    deck.cover()

    pending_title, body = None, []

    def emit():
        nonlocal pending_title, body
        if pending_title is None and not body:
            return
        title = pending_title if pending_title is not None else str(meta.get("title", "Documento"))
        deck.new_slide(title)
        for el in _flatten(body, 0, None, lvl):
            if el["k"] == "table":
                deck.add_table(el)
            else:
                deck.add_text(el)
        deck.flush_slide()
        pending_title, body = None, []

    for b in blocks:
        if b["type"] == "heading" and b["level"] < lvl:
            emit()
            deck.section(runs_text(b["runs"]))
        elif b["type"] == "heading" and b["level"] == lvl:
            emit()
            pending_title = runs_text(b["runs"])
        else:
            body.append(b)
    emit()
    buf = io.BytesIO()
    deck.prs.save(buf)
    return buf.getvalue(), _slug(str(meta.get("title", "documento")))
