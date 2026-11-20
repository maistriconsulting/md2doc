"""Nome del file generato e margine di sicurezza del logo."""
import datetime
import io
import shutil
from pathlib import Path

import pytest
from docx import Document
from docx.shared import Mm
from pptx import Presentation

import app as app_mod
from engine import config, convert, gestione, pdf
from engine.nomi import data_release, nome_file

ORIGINE = Path(__file__).resolve().parent.parent / "templates" / "esempio-cliente"
OGGI = datetime.date.today().isoformat()


@pytest.fixture()
def tpl(tmp_path, monkeypatch):
    d = tmp_path / "templates"
    d.mkdir()
    shutil.copytree(ORIGINE, d / "esempio-cliente")
    monkeypatch.setattr(config, "TEMPLATES_DIR", d)
    monkeypatch.setattr(gestione, "TEMPLATES_DIR", d)
    monkeypatch.setattr(gestione, "CESTINO", d / "_eliminati")
    return d


def imposta_margine(tpl, valore):
    f = tpl / "esempio-cliente" / "brand.yaml"
    righe = [r for r in f.read_text(encoding="utf-8").splitlines() if not r.startswith("margine_sicurezza_mm")]
    f.write_text("\n".join(righe) + f"\nmargine_sicurezza_mm: {valore}\n", encoding="utf-8")


# ---------- nome del file ----------

@pytest.mark.parametrize("meta,atteso", [
    ({"date": datetime.date(2026, 3, 9)}, "2026-03-09"),
    ({"date": "2026-11-19"}, "2026-11-19"),
    ({"data": "9/3/2026"}, "2026-03-09"),
    ({"date": "19.11.2026"}, "2026-11-19"),
    ({"date": "19 novembre 2026"}, "2026-11-19"),
    ({"date": "prossimamente"}, OGGI),
    ({"date": "31/02/2026"}, OGGI),
    ({}, OGGI),
])
def test_data_release(meta, atteso):
    assert data_release(meta) == atteso


def test_nome_dal_file_markdown():
    assert nome_file({"date": "2026-11-19"}, "Piano commerciale 2027.md", "titolo", "pdf") == "Piano-commerciale-2027_2026-11-19.pdf"
    assert nome_file({}, None, "titolo-del-doc", "docx") == f"titolo-del-doc_{OGGI}.docx"
    assert nome_file({}, "../../etc/passwd.md", "t", "pdf") == f"passwd_{OGGI}.pdf"


@pytest.mark.parametrize("fmt", ["pdf", "docx", "pptx"])
def test_convert_usa_il_nome_del_markdown(tpl, fmt):
    md = "---\ndate: 2026-11-19\ntitle: Un titolo\n---\n\n# Corpo\n\nTesto."
    _, nome, _ = convert(md, "esempio-cliente", "lettera", fmt, nome_base="relazione-clienti.md")
    assert nome == f"relazione-clienti_2026-11-19.{fmt}"
    _, nome, _ = convert(md, "esempio-cliente", "lettera", fmt)          # incollato: si usa il titolo
    assert nome == f"un-titolo_2026-11-19.{fmt}"


def test_web_nome_file_caricato_e_anteprima(tpl):
    c = app_mod.app.test_client()
    base = "http://127.0.0.1:5055"
    dati = {"brand": "esempio-cliente", "model": "lettera", "format": "pdf",
            "file": (io.BytesIO(b"# Titolo\n\nTesto."), "Offerta Rossi.md")}
    r = c.post("/api/convert", data=dati, base_url=base)
    assert "Offerta-Rossi_" in r.headers["Content-Disposition"]
    r = c.post("/api/convert", data={"markdown": "# T\n\nx", "filename": "mio.md", "brand": "esempio-cliente",
                                      "model": "lettera", "format": "pdf", "inline": "1"}, base_url=base)
    url = r.get_json()["url"]
    assert url.endswith(f"/mio_{OGGI}.pdf")
    anteprima = c.get(url, base_url=base)
    assert anteprima.data[:5] == b"%PDF-"
    assert f"mio_{OGGI}.pdf" in anteprima.headers["Content-Disposition"]


# ---------- margine di sicurezza ----------

def test_minimo_5mm_anche_se_il_file_dice_meno(tpl):
    imposta_margine(tpl, 1)
    assert config.load_profile("esempio-cliente", "lettera")["margine_sicurezza_mm"] == 5
    imposta_margine(tpl, "boh")
    assert config.load_profile("esempio-cliente", "lettera")["margine_sicurezza_mm"] == config.MARGINE_SICUREZZA_DEFAULT
    imposta_margine(tpl, 999)
    assert config.load_profile("esempio-cliente", "lettera")["margine_sicurezza_mm"] == config.MARGINE_SICUREZZA_MAX


def test_interfaccia_rifiuta_meno_di_5mm(tpl):
    d = gestione.leggi_marchio("esempio-cliente")
    d["margine_sicurezza_mm"] = 3
    with pytest.raises(gestione.ErroreGestione):
        gestione.salva_marchio("esempio-cliente", d)
    d["margine_sicurezza_mm"] = 12
    assert gestione.salva_marchio("esempio-cliente", d)["margine_sicurezza_mm"] == 12


def _y_logo_pdf_mm(tpl, modello, margine):
    """Posizione verticale (mm dal bordo superiore) del logo nell'intestazione di pagina, misurata sul layout reale."""
    from weasyprint import HTML
    imposta_margine(tpl, margine)
    catturato = {}
    originale = pdf.HTML

    def finto(**kw):
        catturato.update(kw)
        return originale(**kw)
    pdf.HTML = finto
    try:
        convert("# Doc\n\n## Sezione\n\nTesto.\n\n" * 3, "esempio-cliente", modello, "pdf")
    finally:
        pdf.HTML = originale
    doc = originale(**catturato).render()
    trovati = []

    def cerca(box):
        if getattr(box, "element_tag", None) == "img":
            trovati.append(box.content_box_y() if hasattr(box, "content_box_y") else box.position_y)
        for f in getattr(box, "children", []) or []:
            cerca(f)
    cerca(doc.pages[-1]._page_box)
    assert trovati, "logo non trovato nel layout"
    return min(trovati) * 25.4 / 96


@pytest.mark.parametrize("margine", [5, 8, 15])
def test_pdf_logo_non_tocca_il_bordo(tpl, margine):
    y = _y_logo_pdf_mm(tpl, "lettera", margine)
    assert y >= margine - 0.01


def test_pdf_margine_alto_si_adatta(tpl):
    # margini del modello troppo piccoli per contenere logo e distanza: il testo non deve finire sotto il logo
    f = tpl / "esempio-cliente" / "brand.yaml"
    f.write_text(f.read_text(encoding="utf-8").replace("margini_mm: [30, 25, 25, 25]", "margini_mm: [10, 25, 25, 25]"), encoding="utf-8")
    imposta_margine(tpl, 15)
    css = pdf._css(config.load_profile("esempio-cliente", "lettera"))
    assert "margin: 36.0mm" in css      # 15 + 11 (logo) + 10


@pytest.mark.parametrize("margine", [5, 14])
def test_docx_intestazione_distanziata(tpl, margine):
    imposta_margine(tpl, margine)
    data, _, _ = convert("# T\n\nTesto", "esempio-cliente", "lettera", "docx")
    sec = Document(io.BytesIO(data)).sections[0]
    assert abs(sec.header_distance - Mm(margine)) < Mm(0.01)
    assert sec.top_margin >= Mm(margine + 11)


@pytest.mark.parametrize("margine", [5, 20])
def test_pptx_logo_sotto_il_margine(tpl, margine):
    imposta_margine(tpl, margine)
    data, _, _ = convert("# T\n\n## Uno\n\n- a\n\n## Due\n\n- b", "esempio-cliente", "presentazione", "pptx")
    visti = 0
    for s in Presentation(io.BytesIO(data)).slides:
        for sh in s.shapes:
            if sh.shape_type == 13:        # immagine
                visti += 1
                assert sh.top >= Mm(margine) - 100
    assert visti >= 3


# ---------- piede di pagina e testo ----------

def test_piva_resta_unita_al_numero():
    from engine.config import footer_text
    prof = {"footer": "", "marchio": {"nome": "X", "ragione_sociale": "X Srl", "indirizzo": "Via A 1",
                                      "piva": "01234567890", "cf": "ABCDEF12G34H567I", "rea": "VR-1"}}
    t = footer_text(prof)
    for etichetta, valore in (("P.IVA", "01234567890"), ("C.F.", "ABCDEF12G34H567I"), ("REA", "VR-1")):
        assert f"{etichetta} {valore}" in t
    # vale anche per un piede di pagina scritto a mano
    assert "P.IVA 123" in footer_text({"footer": "Srl | P.IVA 123", "marchio": {}})


def test_distanza_tra_testo_e_piede(tpl):
    css = pdf._css(config.load_profile("esempio-cliente", "lettera"))
    assert f"padding-top: {pdf.DISTANZA_PIEDE_MM}mm" in css
    assert pdf.DISTANZA_PIEDE_MM >= 6


def test_testo_del_corpo_predefinito_10pt():
    assert config.DEFAULT_MODEL["pdf"]["corpo_pt"] == 10
    assert config.DEFAULT_MODEL["docx"]["corpo_pt"] == 10
