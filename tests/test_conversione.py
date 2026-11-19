"""Un markdown per ogni elemento: i tre formati devono generarsi e contenere il testo."""
import io
import zipfile
from pathlib import Path

import pytest
from docx import Document
from pptx import Presentation

from engine import convert, list_brands
from engine.parser import md_instance, parse_markdown

MARCHIO = "esempio-cliente"
MODELLI = ["lettera", "proposta", "presentazione"]
FORMATI = ["pdf", "docx", "pptx"]

# nome elemento: (markdown, testo che deve comparire nel documento generato)
ELEMENTI = {
    "titoli": ("# Titolo uno\n\n## Titolo due\n\n### Titolo tre\n\nTesto sotto i titoli.", "Titolo due"),
    "paragrafo": ("# Doc\n\nUn paragrafo semplice con parole ordinarie.", "paragrafo semplice"),
    "stili_in_linea": ("# Doc\n\n**grassetto**, *corsivo*, `codice`, ~~barrato~~ e [link](https://example.com).", "grassetto"),
    "elenco_puntato": ("# Doc\n\n## Sezione\n\n- uno\n- due\n  - annidato\n    - terzo livello\n- tre", "annidato"),
    "elenco_numerato": ("# Doc\n\n## Sezione\n\n1. primo\n2. secondo\n3. terzo", "secondo"),
    "citazione": ("# Doc\n\n## Sezione\n\n> Una citazione di prova.", "citazione di prova"),
    "codice": ("# Doc\n\n## Sezione\n\n```\ndef f(x):\n    return x\n```", "return x"),
    "tabella": ("# Doc\n\n## Sezione\n\n| A | B | C |\n|:--|--:|:-:|\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |", "5"),
    "linea": ("# Doc\n\n## Sezione\n\nPrima.\n\n---\n\nDopo.", "Dopo"),
    "front_matter": ("---\ntitle: Titolo da intestazione\nsubtitle: Sottotitolo\nclient: Azienda Demo Srl\nversion: \"1.0\"\n---\n\n# Introduzione\n\nTesto.", "Titolo da intestazione"),
    "html_grezzo": ("# Doc\n\n## Sezione\n\n<script>alert(1)</script>\n\nTesto dopo.", "Testo dopo"),
    "caratteri_italiani": ("# Perche' e' cosi'\n\nCitta', perche', è à ò ì ù € 1.234,56.", "1.234,56"),
    "tabella_lunga": ("# Doc\n\n## Sezione\n\n| N | Voce |\n|--|--|\n" + "".join(f"| {i} | Voce {i} |\n" for i in range(60)), "Voce 59"),
    "elenco_lungo": ("# Doc\n\n## Sezione\n\n" + "".join(f"- punto numero {i}\n" for i in range(60)), "punto numero 59"),
    "solo_titolo": ("# Solo un titolo", "Solo un titolo"),
}


def estrai_docx(data):
    d = Document(io.BytesIO(data))
    parti = [p.text for p in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            parti += [c.text for c in r.cells]
    return "\n".join(parti)


def estrai_pptx(data):
    out = []
    for s in Presentation(io.BytesIO(data)).slides:
        for sh in s.shapes:
            if sh.has_text_frame:
                out.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                for r in sh.table.rows:
                    out += [c.text for c in r.cells]
    return "\n".join(out)


def test_marchio_di_esempio_presente():
    marchi = {b["id"]: [m["id"] for m in b["modelli"]] for b in list_brands()}
    assert MARCHIO in marchi
    for m in MODELLI:
        assert m in marchi[MARCHIO]


@pytest.mark.parametrize("fmt", FORMATI)
@pytest.mark.parametrize("modello", MODELLI)
@pytest.mark.parametrize("nome", list(ELEMENTI))
def test_elemento_si_genera(nome, modello, fmt):
    md, atteso = ELEMENTI[nome]
    data, filename, _ = convert(md, MARCHIO, modello, fmt)
    assert filename.endswith("." + fmt)
    assert len(data) > 1000
    if fmt == "pdf":
        assert data[:5] == b"%PDF-"
    else:
        assert zipfile.is_zipfile(io.BytesIO(data))
        testo = estrai_docx(data) if fmt == "docx" else estrai_pptx(data)
        assert atteso in testo


@pytest.mark.parametrize("fmt", FORMATI)
def test_esempio_completo(fmt):
    md = (Path(__file__).resolve().parent.parent / "esempi" / "prova.md").read_text(encoding="utf-8")
    data, _, _ = convert(md, MARCHIO, "proposta", fmt)
    assert len(data) > 5000


def test_html_grezzo_non_eseguito():
    html = md_instance().render("<script>alert(1)</script>")
    assert "<script>" not in html


def test_titolo_da_primo_h1():
    meta, blocchi, _ = parse_markdown("# Il mio titolo\n\nTesto.")
    assert meta["title"] == "Il mio titolo"
    assert all(not (b["type"] == "heading" and b["level"] == 1) for b in blocchi)


def test_formato_non_supportato():
    with pytest.raises(ValueError):
        convert("# a", MARCHIO, "lettera", "xls")


def test_pptx_tabella_lunga_su_piu_slide():
    md, _ = ELEMENTI["tabella_lunga"]
    data, _, _ = convert(md, MARCHIO, "presentazione", "pptx")
    assert len(Presentation(io.BytesIO(data)).slides) > 3


def test_risorsa_http_bloccata_non_rompe_il_pdf():
    # un'immagine http (non https) non deve essere scaricata ne' far fallire la conversione
    data, _, _ = convert("# Doc\n\n![x](http://127.0.0.1:9/a.png)\n\nTesto.", MARCHIO, "lettera", "pdf")
    assert data[:5] == b"%PDF-"
