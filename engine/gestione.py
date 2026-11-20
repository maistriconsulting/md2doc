"""Gestione dei marchi dall'interfaccia: lettura, creazione, modifica, logo, eliminazione.

Tutto passa da qui, con validazione: il programma e' locale ma i file scritti
(brand.yaml, logo) vengono poi letti dal motore di conversione."""
import copy
import io
import re
import shutil
import time
from pathlib import Path

import yaml
from PIL import Image

from .config import (ROOT, DEFAULT_MODEL, MARGINE_SICUREZZA_DEFAULT, MARGINE_SICUREZZA_MAX,
                     MARGINE_SICUREZZA_MIN, TEMPLATES_DIR, _deep_merge, margine_sicurezza)

CESTINO = TEMPLATES_DIR / "_eliminati"
MODELLO_BASE_DA = "esempio-cliente"
DIMENSIONI_PAGINA = ["A4", "A3", "A5", "Letter", "Legal"]
RE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
RE_COLORE = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_LOGO = 3 * 1024 * 1024


def sola_lettura(brand_id):
    """Il marchio di esempio e' nel repository pubblico: non va riempito con dati reali."""
    return brand_id == MODELLO_BASE_DA and TEMPLATES_DIR.resolve() == (ROOT / "templates").resolve()


def _blocca_se_sola_lettura(brand_id):
    if sola_lettura(brand_id):
        raise ErroreGestione("Il marchio di esempio fa parte del repository pubblico e non si modifica: "
                             "crea un nuovo marchio (partendo da questo) e inserisci lì i dati reali.")


class ErroreGestione(ValueError):
    """Errore leggibile da mostrare all'utente."""


def slug(testo):
    s = re.sub(r"[^a-z0-9]+", "-", (testo or "").lower()).strip("-")
    return s[:40].strip("-")


def _cartella(brand_id):
    if not RE_ID.match(brand_id or ""):
        raise ErroreGestione("Identificativo marchio non valido.")
    d = (TEMPLATES_DIR / brand_id).resolve()
    if d.parent != TEMPLATES_DIR.resolve():
        raise ErroreGestione("Percorso non valido.")
    return d


def _leggi_yaml(d):
    f = d / "brand.yaml"
    if not f.exists():
        raise ErroreGestione("Marchio non trovato.")
    try:
        return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        raise ErroreGestione("Il file brand.yaml di questo marchio non e' leggibile.")


def _scrivi_yaml(d, cfg):
    testo = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, default_flow_style=None, width=100)
    (d / "brand.yaml").write_text(testo, encoding="utf-8")


def elenco_id():
    if not TEMPLATES_DIR.exists():
        return []
    return [d.name for d in sorted(TEMPLATES_DIR.iterdir())
            if d.is_dir() and RE_ID.match(d.name) and (d / "brand.yaml").exists()]


def leggi_marchio(brand_id):
    """Configurazione completa per il modulo di modifica (con i valori predefiniti dei modelli)."""
    d = _cartella(brand_id)
    cfg = _leggi_yaml(d)
    logo = cfg.get("logo") or ""
    modelli = {}
    for mid, m in (cfg.get("modelli") or {}).items():
        modelli[mid] = _deep_merge(DEFAULT_MODEL, m or {})
    return {
        "id": brand_id,
        "sola_lettura": sola_lettura(brand_id),
        "marchio": {k: str((cfg.get("marchio") or {}).get(k, "") or "")
                    for k in ("nome", "ragione_sociale", "indirizzo", "piva", "cf", "rea")},
        "logo": logo,
        "logo_presente": bool(logo) and (d / logo).exists(),
        "logo_altezza_mm": cfg.get("logo_altezza_mm", 12),
        "margine_sicurezza_mm": margine_sicurezza(cfg.get("margine_sicurezza_mm")),
        "margine_sicurezza_min": MARGINE_SICUREZZA_MIN,
        "margine_sicurezza_max": MARGINE_SICUREZZA_MAX,
        "colori": _deep_merge({"primario": "#1F3A5F", "secondario": "#5B7FA6", "testo": "#222222",
                               "tenue": "#6B7280", "sfondo_chiaro": "#F2F4F7"}, cfg.get("colori") or {}),
        "font": _deep_merge({"titoli": "Arial", "testo": "Arial", "monospazio": "Courier New"},
                            cfg.get("font") or {}),
        "footer": cfg.get("footer", "") or "",
        "modelli": modelli,
    }


# ---------- validazione ----------

def _testo(v, nome, max_len=200, obbligatorio=False):
    v = ("" if v is None else str(v)).strip()
    if "\n" in v or "\r" in v:
        raise ErroreGestione(f"{nome}: va scritto su una riga sola.")
    if len(v) > max_len:
        raise ErroreGestione(f"{nome}: troppo lungo (massimo {max_len} caratteri).")
    if obbligatorio and not v:
        raise ErroreGestione(f"{nome}: obbligatorio.")
    return v


def _numero(v, nome, minimo, massimo):
    try:
        n = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        raise ErroreGestione(f"{nome}: serve un numero.")
    if not (minimo <= n <= massimo):
        raise ErroreGestione(f"{nome}: deve essere tra {minimo} e {massimo}.")
    return int(n) if n == int(n) else round(n, 2)


def _margini(v, nome):
    if not isinstance(v, (list, tuple)) or len(v) != 4:
        raise ErroreGestione(f"{nome}: servono 4 valori (sopra, destra, sotto, sinistra).")
    return [_numero(x, nome, 0, 100) for x in v]


def _modello(mid, m):
    if not RE_ID.match(mid or ""):
        raise ErroreGestione(f"Identificativo modello non valido: {mid!r} (lettere minuscole, numeri, trattino).")
    if not isinstance(m, dict):
        raise ErroreGestione(f"Modello {mid}: dati non validi.")
    out = {k: v for k, v in m.items() if k not in ("nome", "descrizione", "copertina", "pdf", "docx")}
    out["nome"] = _testo(m.get("nome"), f"Modello {mid}: nome", 60, True)
    out["descrizione"] = _testo(m.get("descrizione"), f"Modello {mid}: descrizione", 120)
    out["copertina"] = bool(m.get("copertina"))
    p, w = (m.get("pdf") or {}), (m.get("docx") or {})
    dim = p.get("dimensione", "A4")
    if dim not in DIMENSIONI_PAGINA:
        raise ErroreGestione(f"Modello {mid}: formato pagina non valido.")
    out["pdf"] = {
        "dimensione": dim,
        "margini_mm": _margini(p.get("margini_mm"), f"Modello {mid}: margini PDF"),
        "corpo_pt": _numero(p.get("corpo_pt"), f"Modello {mid}: dimensione testo PDF", 6, 24),
        "interlinea": _numero(p.get("interlinea"), f"Modello {mid}: interlinea", 1, 2.5),
        "numera_pagine": bool(p.get("numera_pagine")),
    }
    out["docx"] = {
        "margini_mm": _margini(w.get("margini_mm"), f"Modello {mid}: margini Word"),
        "corpo_pt": _numero(w.get("corpo_pt"), f"Modello {mid}: dimensione testo Word", 6, 24),
    }
    return out


def salva_marchio(brand_id, dati):
    d = _cartella(brand_id)
    _blocca_se_sola_lettura(brand_id)
    cfg = _leggi_yaml(d)          # si conservano le chiavi che l'interfaccia non conosce
    if not isinstance(dati, dict):
        raise ErroreGestione("Dati non validi.")

    mar = dati.get("marchio") or {}
    cfg["marchio"] = _deep_merge(cfg.get("marchio") or {}, {
        "nome": _testo(mar.get("nome"), "Nome del marchio", 80, True),
        "ragione_sociale": _testo(mar.get("ragione_sociale"), "Ragione sociale", 120),
        "indirizzo": _testo(mar.get("indirizzo"), "Indirizzo", 160),
        "piva": _testo(mar.get("piva"), "Partita IVA", 30),
        "cf": _testo(mar.get("cf"), "Codice fiscale", 30),
        "rea": _testo(mar.get("rea"), "REA", 30),
    })
    cfg["logo_altezza_mm"] = _numero(dati.get("logo_altezza_mm", 12), "Altezza logo", 4, 40)
    cfg["margine_sicurezza_mm"] = _numero(dati.get("margine_sicurezza_mm", MARGINE_SICUREZZA_DEFAULT),
                                          "Distanza del logo dal bordo superiore", MARGINE_SICUREZZA_MIN, MARGINE_SICUREZZA_MAX)

    colori = dati.get("colori") or {}
    cfg["colori"] = {}
    for k in ("primario", "secondario", "testo", "tenue", "sfondo_chiaro"):
        v = str(colori.get(k, "")).strip()
        if not RE_COLORE.match(v):
            raise ErroreGestione(f"Colore '{k}': usa il formato #RRGGBB.")
        cfg["colori"][k] = v.upper()

    font = dati.get("font") or {}
    cfg["font"] = {k: _testo(font.get(k), f"Font {k}", 60, True) for k in ("titoli", "testo", "monospazio")}
    cfg["footer"] = _testo(dati.get("footer"), "Piede di pagina", 240)

    modelli = dati.get("modelli")
    if not isinstance(modelli, dict) or not modelli:
        raise ErroreGestione("Serve almeno un modello.")
    vecchi = cfg.get("modelli") or {}
    nuovi = {}
    for mid, m in modelli.items():
        validato = _modello(mid, m)
        # chiavi extra gia' presenti nel file (per esempio colori o font del modello) restano
        extra = {k: v for k, v in (vecchi.get(mid) or {}).items() if k not in validato}
        nuovi[mid] = {**validato, **extra}
    cfg["modelli"] = nuovi

    _scrivi_yaml(d, cfg)
    return leggi_marchio(brand_id)


# ---------- creazione, logo, eliminazione ----------

def crea_marchio(nome, copia_da=None):
    nome = _testo(nome, "Nome del marchio", 80, True)
    nuovo = slug(nome)
    if not nuovo:
        raise ErroreGestione("Il nome deve contenere almeno una lettera o un numero.")
    dest = TEMPLATES_DIR / nuovo
    if dest.exists():
        raise ErroreGestione(f"Esiste gia' un marchio con identificativo '{nuovo}'.")
    origine_id = copia_da or MODELLO_BASE_DA
    if origine_id not in elenco_id():
        origine_id = elenco_id()[0] if elenco_id() else None
    if not origine_id:
        raise ErroreGestione("Non c'e' nessun marchio da cui partire.")
    origine = _cartella(origine_id)
    shutil.copytree(origine, dest)
    cfg = _leggi_yaml(dest)
    cfg["marchio"] = {"nome": nome, "ragione_sociale": nome, "indirizzo": "", "piva": "", "cf": "", "rea": ""}
    cfg["footer"] = ""
    _scrivi_yaml(dest, cfg)
    return nuovo


def salva_logo(brand_id, contenuto):
    d = _cartella(brand_id)
    _blocca_se_sola_lettura(brand_id)
    cfg = _leggi_yaml(d)
    if len(contenuto) > MAX_LOGO:
        raise ErroreGestione("Il logo supera i 3 MB.")
    try:
        img = Image.open(io.BytesIO(contenuto))
        img.verify()
        img = Image.open(io.BytesIO(contenuto))
    except Exception:
        raise ErroreGestione("Il file non e' un'immagine valida (usa PNG o JPG).")
    if img.format not in ("PNG", "JPEG"):
        raise ErroreGestione("Formati ammessi per il logo: PNG o JPG.")
    if img.width * img.height > 40_000_000:
        raise ErroreGestione("Immagine troppo grande.")
    img = img.convert("RGBA")
    if max(img.size) > 1600:
        img.thumbnail((1600, 1600), Image.LANCZOS)
    img.save(d / "logo.png", format="PNG")
    cfg["logo"] = "logo.png"
    _scrivi_yaml(d, cfg)


def percorso_logo(brand_id):
    d = _cartella(brand_id)
    cfg = _leggi_yaml(d)
    nome = cfg.get("logo") or ""
    p = (d / nome).resolve() if nome else None
    if not p or p.parent != d or not p.is_file():
        raise ErroreGestione("Nessun logo.")
    return p


def elimina_marchio(brand_id):
    """Non cancella: sposta la cartella in templates/_eliminati/, cosi' si puo' recuperare."""
    d = _cartella(brand_id)
    _leggi_yaml(d)
    if len(elenco_id()) <= 1:
        raise ErroreGestione("Non si puo' eliminare l'ultimo marchio.")
    CESTINO.mkdir(exist_ok=True)
    dest = CESTINO / f"{brand_id}-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.move(str(d), str(dest))
    return str(dest.relative_to(TEMPLATES_DIR.parent))
