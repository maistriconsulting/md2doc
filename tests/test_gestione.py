"""Gestione marchi dall'interfaccia: i file vengono scritti in una cartella temporanea."""
import io
import shutil
from pathlib import Path

import pytest
from PIL import Image

import app as app_mod
from engine import config, convert, gestione

ORIGINE = Path(__file__).resolve().parent.parent / "templates" / "esempio-cliente"


@pytest.fixture()
def tpl(tmp_path, monkeypatch):
    d = tmp_path / "templates"
    d.mkdir()
    shutil.copytree(ORIGINE, d / "esempio-cliente")
    monkeypatch.setattr(config, "TEMPLATES_DIR", d)
    monkeypatch.setattr(gestione, "TEMPLATES_DIR", d)
    monkeypatch.setattr(gestione, "CESTINO", d / "_eliminati")
    return d


def png(w=40, h=20):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (10, 100, 50)).save(b, "PNG")
    return b.getvalue()


def test_crea_e_converte(tpl):
    nuovo = gestione.crea_marchio("Studio Verde")
    assert nuovo == "studio-verde"
    d = gestione.leggi_marchio(nuovo)
    assert d["marchio"]["nome"] == "Studio Verde"
    assert d["marchio"]["piva"] == ""          # i dati del marchio di partenza non si copiano
    for fmt in ("pdf", "docx", "pptx"):
        assert len(convert("# Titolo\n\nTesto.", nuovo, "proposta", fmt)[0]) > 1000


def test_nome_duplicato_e_non_valido(tpl):
    gestione.crea_marchio("Uno")
    with pytest.raises(gestione.ErroreGestione):
        gestione.crea_marchio("Uno")
    with pytest.raises(gestione.ErroreGestione):
        gestione.crea_marchio("***")


def test_salva_modifiche_e_nuovo_modello(tpl):
    d = gestione.leggi_marchio("esempio-cliente")
    d["colori"]["primario"] = "#116644"
    d["modelli"]["offerta"] = {**d["modelli"]["proposta"], "nome": "Offerta"}
    d["modelli"]["offerta"]["pdf"]["margini_mm"] = [40, 20, 20, 20]
    gestione.salva_marchio("esempio-cliente", d)
    r = gestione.leggi_marchio("esempio-cliente")
    assert r["colori"]["primario"] == "#116644"
    assert r["modelli"]["offerta"]["pdf"]["margini_mm"] == [40, 20, 20, 20]
    assert len(convert("# A\n\nTesto", "esempio-cliente", "offerta", "pdf")[0]) > 1000


@pytest.mark.parametrize("modifica", [
    lambda d: d["colori"].update(primario="rosso"),
    lambda d: d["marchio"].update(nome=""),
    lambda d: d["marchio"].update(nome="a\nb"),
    lambda d: d["modelli"]["lettera"]["pdf"].update(margini_mm=[1, 2, 3]),
    lambda d: d["modelli"]["lettera"]["pdf"].update(corpo_pt=500),
    lambda d: d["modelli"]["lettera"]["pdf"].update(dimensione="A0"),
    lambda d: d["modelli"].update({"../x": d["modelli"]["lettera"]}),
    lambda d: d.update(modelli={}),
    lambda d: d.update(logo_altezza_mm="abc"),
])
def test_valori_non_validi_rifiutati(tpl, modifica):
    d = gestione.leggi_marchio("esempio-cliente")
    prima = (tpl / "esempio-cliente" / "brand.yaml").read_text(encoding="utf-8")
    modifica(d)
    with pytest.raises(gestione.ErroreGestione):
        gestione.salva_marchio("esempio-cliente", d)
    assert (tpl / "esempio-cliente" / "brand.yaml").read_text(encoding="utf-8") == prima


def test_chiavi_sconosciute_conservate(tpl):
    f = tpl / "esempio-cliente" / "brand.yaml"
    f.write_text(f.read_text(encoding="utf-8") + "lingua: it\n", encoding="utf-8")
    gestione.salva_marchio("esempio-cliente", gestione.leggi_marchio("esempio-cliente"))
    assert "lingua: it" in f.read_text(encoding="utf-8")


def test_logo(tpl):
    gestione.salva_logo("esempio-cliente", png())
    assert gestione.percorso_logo("esempio-cliente").name == "logo.png"
    with pytest.raises(gestione.ErroreGestione):
        gestione.salva_logo("esempio-cliente", b"non e' un'immagine")
    with pytest.raises(gestione.ErroreGestione):
        gestione.salva_logo("esempio-cliente", b"0" * (gestione.MAX_LOGO + 1))


def test_elimina_sposta_e_protegge_l_ultimo(tpl):
    gestione.crea_marchio("Da togliere")
    dest = gestione.elimina_marchio("da-togliere")
    assert "_eliminati" in dest
    assert "da-togliere" not in gestione.elenco_id()
    assert "da-togliere" not in [b["id"] for b in config.list_brands()]
    with pytest.raises(gestione.ErroreGestione):
        gestione.elimina_marchio("esempio-cliente")      # e' l'ultimo


@pytest.mark.parametrize("brand_id", ["../x", "..", "a/b", "", "A", "x" * 60, "_eliminati"])
def test_identificativi_pericolosi(tpl, brand_id):
    with pytest.raises(gestione.ErroreGestione):
        gestione.leggi_marchio(brand_id)


def test_rotte_protette(tpl):
    c = app_mod.app.test_client()
    ok = {"X-MD2DOC": "1"}
    base = "http://127.0.0.1:5055"
    assert c.post("/api/brand", json={"nome": "A"}, base_url=base).status_code == 403            # manca l'intestazione
    assert c.post("/api/brand", json={"nome": "A"}, headers={**ok, "Origin": "https://evil.example"}, base_url=base).status_code == 403
    assert c.post("/api/brand", json={"nome": "A"}, headers=ok, base_url="http://evil.example:5055").status_code == 403
    r = c.post("/api/brand", json={"nome": "Alfa"}, headers={**ok, "Origin": base}, base_url=base)
    assert r.status_code == 200 and r.get_json()["id"] == "alfa"
    assert c.get("/api/brand/alfa", base_url=base).status_code == 200
    assert c.get("/api/brand/alfa/prova?model=proposta", base_url=base).data[:5] == b"%PDF-"
    assert c.get("/api/brand/..%2fx", base_url=base).status_code in (400, 404)
