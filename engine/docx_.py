"""Motore DOCX con python-docx."""
import io
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from .config import footer_text
from .parser import parse_markdown, runs_text
from .pdf import data_it, _slug


def _rgb(h):
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _set_font(style_or_run, name, size=None, bold=None, color=None, italic=None):
    f = style_or_run.font
    f.name = name
    rpr = style_or_run.element.get_or_add_rPr() if hasattr(style_or_run.element, "get_or_add_rPr") else None
    if rpr is not None:
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.append(rf)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(a), name)
    if size:
        f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if italic is not None:
        f.italic = italic
    if color:
        f.color.rgb = _rgb(color)


def _shade(cell_or_par_pr, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill.lstrip("#"))
    cell_or_par_pr.append(shd)


def _border(parent, side, color, sz=6, space=1, val="single"):
    b = parent.find(qn("w:pBdr"))
    if b is None:
        b = OxmlElement("w:pBdr")
        parent.append(b)
    e = OxmlElement(f"w:{side}")
    e.set(qn("w:val"), val)
    e.set(qn("w:sz"), str(sz))
    e.set(qn("w:space"), str(space))
    e.set(qn("w:color"), color.lstrip("#"))
    b.append(e)


def _field(par, instr, font, size, color):
    def mk(t):
        r = par.add_run()
        _set_font(r, font, size, color=color)
        fc = OxmlElement("w:fldChar")
        fc.set(qn("w:fldCharType"), t)
        r._r.append(fc)
        return r
    mk("begin")
    r = par.add_run()
    _set_font(r, font, size, color=color)
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r._r.append(it)
    mk("separate")
    r = par.add_run("1")
    _set_font(r, font, size, color=color)
    mk("end")


def _add_link(par, text, url, font, size, color, bold=False, italic=False):
    rid = par.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                             is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), rid)
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi"):
        rf.set(qn(a), font)
    rpr.append(rf)
    if bold:
        rpr.append(OxmlElement("w:b"))
    if italic:
        rpr.append(OxmlElement("w:i"))
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color.lstrip("#"))
    rpr.append(c)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rpr.append(u)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size * 2)))
    rpr.append(sz)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    h.append(r)
    par._p.append(h)


_ORDER = {
    "pPr": "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange".split(),
    "rPr": "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath".split(),
    "trPr": "cnfStyle divId gridBefore gridAfter wBefore wAfter cantSplit trHeight tblHeader tblCellSpacing jc hidden".split(),
    "tcPr": "cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark".split(),
    "tblPr": "tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook".split(),
}


def _fix_order(root):
    """Word e' rigido sull'ordine degli elementi figli: li riordina secondo lo schema."""
    for tag, order in _ORDER.items():
        for el in root.iter(qn(f"w:{tag}")):
            kids = list(el)
            def key(k):
                name = k.tag.split("}")[1]
                return order.index(name) if name in order else len(order)
            srt = sorted(kids, key=key)
            if srt != kids:
                for k in kids:
                    el.remove(k)
                for k in srt:
                    el.append(k)


class _Builder:
    def __init__(self, prof):
        self.p = prof
        self.c = prof["colori"]
        self.f = prof["font"]
        self.m = prof["modello"]["docx"]
        self.body_pt = self.m["corpo_pt"]
        self.doc = Document()
        self._setup()

    def _setup(self):
        d, c, f = self.doc, self.c, self.f
        mt, mr, mb, ml = self.m["margini_mm"]
        sec = d.sections[0]
        sec.page_width, sec.page_height = Mm(210), Mm(297)
        s = self.p["margine_sicurezza_mm"]
        mt = max(mt, s + self.p["logo_altezza_mm"] + 8)
        mb = max(mb, 25)          # spazio tra testo e piede di pagina
        sec.top_margin, sec.right_margin, sec.bottom_margin, sec.left_margin = Mm(mt), Mm(mr), Mm(mb), Mm(ml)
        sec.header_distance, sec.footer_distance = Mm(s), Mm(10)
        st = d.styles
        _set_font(st["Normal"], f["testo"], self.body_pt, color=c["testo"])
        st["Normal"].paragraph_format.space_after = Pt(6)
        st["Normal"].paragraph_format.line_spacing = 1.25
        for name, size, before, after in (("Heading 1", 18, 16, 6), ("Heading 2", 14, 14, 4),
                                          ("Heading 3", 12, 12, 3), ("Heading 4", self.body_pt, 10, 2)):
            s = st[name]
            _set_font(s, f["titoli"], size, bold=True, color=c["primario"] if name != "Heading 4" else c["secondario"])
            s.paragraph_format.space_before = Pt(before)
            s.paragraph_format.space_after = Pt(after)
            s.paragraph_format.keep_with_next = True
        for name in ("List Bullet", "List Bullet 2", "List Bullet 3"):
            _set_font(st[name], f["testo"], self.body_pt, color=c["testo"])
            st[name].paragraph_format.space_after = Pt(2)
        self._header_footer(sec)

    def _header_footer(self, sec):
        c, f = self.c, self.f
        hp = sec.header.paragraphs[0]
        hp.paragraph_format.space_after = Pt(0)
        if self.p["logo_path"]:
            hp.add_run().add_picture(str(self.p["logo_path"]), height=Mm(self.p["logo_altezza_mm"]))
        else:
            r = hp.add_run(self.p["marchio"].get("nome", ""))
            _set_font(r, f["titoli"], 12, bold=True, color=c["primario"])
        _border(hp._p.get_or_add_pPr(), "bottom", c["primario"], sz=10, space=4)
        fp = sec.footer.paragraphs[0]
        fp.paragraph_format.space_before = Pt(0)
        _border(fp._p.get_or_add_pPr(), "top", c["secondario"], sz=4, space=4)
        r = fp.add_run(footer_text(self.p))
        _set_font(r, f["testo"], 7.5, color=c["tenue"])
        fp2 = sec.footer.add_paragraph()
        fp2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = fp2.add_run("Pagina ")
        _set_font(r, f["testo"], 7.5, color=c["tenue"])
        _field(fp2, "PAGE", f["testo"], 7.5, c["tenue"])
        r = fp2.add_run(" di ")
        _set_font(r, f["testo"], 7.5, color=c["tenue"])
        _field(fp2, "NUMPAGES", f["testo"], 7.5, c["tenue"])

    # --- inline ---
    def runs(self, par, runs, size=None, color=None, italic_all=False):
        size = size or self.body_pt
        for r in runs:
            txt = r["text"]
            if r["href"]:
                _add_link(par, txt, r["href"], self.f["testo"], size, self.c["secondario"], r["bold"], r["italic"])
                continue
            run = par.add_run(txt)
            font = self.f["monospazio"] if r["code"] else self.f["testo"]
            _set_font(run, font, size * (0.9 if r["code"] else 1), bold=r["bold"] or None,
                      italic=(r["italic"] or italic_all) or None, color=color)
            if r["strike"]:
                run.font.strike = True
            if r["code"]:
                _shade(run._r.get_or_add_rPr(), self.c["sfondo_chiaro"])

    # --- blocchi ---
    def blocks(self, blocks, level=0, in_quote=False):
        for b in blocks:
            t = b["type"]
            if t == "heading":
                lvl = min(b["level"], 4)
                p = self.doc.add_paragraph(style=f"Heading {lvl}")
                self.runs(p, b["runs"], size={1: 18, 2: 14, 3: 12}.get(lvl, self.body_pt),
                          color=self.c["primario"] if lvl < 4 else self.c["secondario"])
                for r in p.runs:
                    r.font.bold = True
                    r.font.name = self.f["titoli"]
            elif t == "paragraph":
                p = self.doc.add_paragraph()
                if in_quote:
                    self._quote_fmt(p)
                self.runs(p, b["runs"], color=self.c["tenue"] if in_quote else None)
            elif t == "list":
                self.lst(b, level)
            elif t == "quote":
                self.quote(b)
            elif t == "code":
                self.code(b["text"])
            elif t == "hr":
                p = self.doc.add_paragraph()
                _border(p._p.get_or_add_pPr(), "bottom", self.c["secondario"], sz=6, space=1)
            elif t == "table":
                self.table(b)

    def _quote_fmt(self, p):
        pf = p.paragraph_format
        pf.left_indent = Mm(6)
        pf.space_before = Pt(4)
        pf.space_after = Pt(4)
        ppr = p._p.get_or_add_pPr()
        _border(ppr, "left", self.c["secondario"], sz=24, space=8)
        _shade(ppr, self.c["sfondo_chiaro"])

    def quote(self, b):
        self.blocks(b["blocks"], in_quote=True)

    def code(self, text):
        for line in text.split("\n") or [""]:
            p = self.doc.add_paragraph()
            pf = p.paragraph_format
            pf.space_after = Pt(0)
            pf.line_spacing = 1.0
            pf.left_indent = Mm(3)
            ppr = p._p.get_or_add_pPr()
            _border(ppr, "left", self.c["primario"], sz=18, space=6)
            _shade(ppr, self.c["sfondo_chiaro"])
            r = p.add_run(line if line else " ")
            _set_font(r, self.f["monospazio"], self.body_pt * 0.85, color=self.c["testo"])
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def lst(self, b, level):
        for idx, it in enumerate(b["items"], 1):
            first = True
            for sub in it["blocks"]:
                if first and sub["type"] == "paragraph":
                    if b["ordered"]:
                        p = self.doc.add_paragraph()
                        pf = p.paragraph_format
                        pf.left_indent = Mm(7 + 6 * level)
                        pf.first_line_indent = Mm(-6)
                        pf.space_after = Pt(2)
                        r = p.add_run(f"{idx}.\t")
                        _set_font(r, self.f["testo"], self.body_pt, color=self.c["primario"], bold=True)
                        pf.tab_stops.add_tab_stop(Mm(7 + 6 * level))
                    else:
                        style = "List Bullet" if level == 0 else f"List Bullet {min(level + 1, 3)}"
                        p = self.doc.add_paragraph(style=style)
                    self.runs(p, sub["runs"])
                    first = False
                elif sub["type"] == "list":
                    self.lst(sub, level + 1)
                else:
                    self.blocks([sub], level=level + 1)
                    first = False

    def table(self, b):
        ncol = max(len(b["header"]), max((len(r) for r in b["rows"]), default=0))
        if ncol == 0:
            return
        t = self.doc.add_table(rows=0, cols=ncol)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        tblPr = t._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{side}")
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), "4")
            e.set(qn("w:color"), "D6DAE0")
            borders.append(e)
        tblPr.append(borders)
        aligns = b["aligns"] or ["left"] * ncol
        amap = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
                "right": WD_ALIGN_PARAGRAPH.RIGHT}

        def add_row(cells, header=False, zebra=False):
            row = t.add_row()
            if header:  # ripete l'intestazione sulle pagine successive
                trpr = row._tr.get_or_add_trPr()
                th = OxmlElement("w:tblHeader")
                th.set(qn("w:val"), "true")
                trpr.append(th)
            cs = OxmlElement("w:cantSplit")
            row._tr.get_or_add_trPr().append(cs)
            for i in range(ncol):
                cell = row.cells[i]
                par = cell.paragraphs[0]
                par.paragraph_format.space_after = Pt(2)
                par.paragraph_format.space_before = Pt(2)
                al = aligns[i] if i < len(aligns) else "left"
                par.alignment = amap.get(al, WD_ALIGN_PARAGRAPH.LEFT)
                runs = cells[i] if i < len(cells) else []
                if header:
                    for r in runs:
                        r = dict(r, bold=True)
                        self.runs(par, [r], size=self.body_pt * 0.92, color="#FFFFFF")
                    _shade(cell._tc.get_or_add_tcPr(), self.c["primario"])
                else:
                    self.runs(par, runs, size=self.body_pt * 0.92)
                    if zebra:
                        _shade(cell._tc.get_or_add_tcPr(), self.c["sfondo_chiaro"])
        if b["header"]:
            add_row(b["header"], header=True)
        for k, r in enumerate(b["rows"]):
            add_row(r, zebra=(k % 2 == 1))
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # --- titolo / copertina ---
    def title_block(self, meta):
        c, f = self.c, self.f
        title = str(meta.get("title", "Documento"))
        sub = str(meta.get("subtitle") or meta.get("sottotitolo") or "")
        kind = str(meta.get("doc_type") or meta.get("tipo") or "")
        meta_items = [str(meta.get("date") or meta.get("data") or data_it())]
        for key, lab in (("client", "Cliente"), ("cliente", "Cliente"), ("author", "A cura di"),
                         ("autore", "A cura di"), ("version", "Versione"), ("versione", "Versione")):
            if meta.get(key):
                meta_items.append(f"{lab}: {meta[key]}")
        cover = self.p["modello"]["copertina"]
        if cover:
            for _ in range(7):
                self.doc.add_paragraph()
        if kind:
            p = self.doc.add_paragraph()
            r = p.add_run(kind.upper())
            _set_font(r, f["testo"], 9, bold=True, color=c["secondario"])
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(title)
        _set_font(r, f["titoli"], 30 if cover else 24, bold=True, color=c["primario"])
        if sub:
            p = self.doc.add_paragraph()
            r = p.add_run(sub)
            _set_font(r, f["testo"], 14, color=c["tenue"])
        p = self.doc.add_paragraph()
        _border(p._p.get_or_add_pPr(), "top", "D6DAE0", sz=4, space=4)
        r = p.add_run("    ".join(meta_items))
        _set_font(r, f["testo"], 9, color=c["tenue"])
        if cover:
            self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def finish(self):
        sec = self.doc.sections[0]
        for root in (self.doc.element, sec.header._element, sec.footer._element,
                     self.doc.styles.element):
            _fix_order(root)
        buf = io.BytesIO()
        self.doc.save(buf)
        return buf.getvalue()


def build_docx(md_text, prof):
    meta, blocks, _ = parse_markdown(md_text)
    b = _Builder(prof)
    b.title_block(meta)
    b.blocks(blocks)
    return b.finish(), _slug(str(meta.get("title", "documento")))
