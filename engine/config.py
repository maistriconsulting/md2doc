"""Caricamento di marchi e modelli.

Struttura:
  templates/<marchio>/brand.yaml      identita' (nome, dati societari, colori, font, logo)
  templates/<marchio>/logo.png        logo
  brand.yaml -> sezione "modelli":    uno o piu' modelli con le regole di impaginazione

Un modello puo' sovrascrivere qualsiasi chiave del marchio (colori, font, footer)
e definisce le regole per pdf / docx / pptx.
"""
from pathlib import Path
import copy
import re
import yaml

ROOT = Path(__file__).resolve().parent.parent
MARGINE_SICUREZZA_MIN = 5      # mm: distanza minima del logo dal bordo superiore
MARGINE_SICUREZZA_DEFAULT = 8
MARGINE_SICUREZZA_MAX = 20
TEMPLATES_DIR = ROOT / "templates"

DEFAULT_MODEL = {
    "nome": "Documento",
    "descrizione": "",
    "copertina": False,
    "pdf": {"margini_mm": [32, 20, 25, 20], "dimensione": "A4", "numera_pagine": True,
            "interlinea": 1.45, "corpo_pt": 10},
    "docx": {"margini_mm": [30, 20, 25, 20], "corpo_pt": 10},
    "pptx": {"corpo_pt": 18, "livello_slide": 0},
}


def _deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def margine_sicurezza(v):
    """Distanza del logo dal bordo superiore: mai sotto il minimo, anche se il file dice altrimenti."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        n = MARGINE_SICUREZZA_DEFAULT
    return min(max(n, MARGINE_SICUREZZA_MIN), MARGINE_SICUREZZA_MAX)


def list_brands():
    """[{id, nome, modelli:[{id, nome, descrizione}]}]"""
    res = []
    if not TEMPLATES_DIR.exists():
        return res
    for d in sorted(TEMPLATES_DIR.iterdir()):
        f = d / "brand.yaml"
        if not (d.is_dir() and f.exists()):
            continue
        try:
            cfg = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        models = []
        for mid, m in (cfg.get("modelli") or {}).items():
            models.append({"id": mid, "nome": (m or {}).get("nome", mid),
                           "descrizione": (m or {}).get("descrizione", "")})
        res.append({"id": d.name, "nome": (cfg.get("marchio") or {}).get("nome", d.name),
                    "modelli": models})
    return res


def load_profile(brand_id, model_id):
    """Ritorna la configurazione risolta (marchio + modello) e la cartella del marchio."""
    bdir = (TEMPLATES_DIR / brand_id).resolve()
    if TEMPLATES_DIR.resolve() not in bdir.parents or not (bdir / "brand.yaml").exists():
        raise ValueError(f"Marchio non trovato: {brand_id}")
    cfg = yaml.safe_load((bdir / "brand.yaml").read_text(encoding="utf-8")) or {}
    models = cfg.get("modelli") or {}
    if model_id not in models:
        raise ValueError(f"Modello non trovato: {model_id}")
    model = _deep_merge(DEFAULT_MODEL, models[model_id] or {})
    prof = {
        "marchio": cfg.get("marchio") or {},
        "colori": _deep_merge({"primario": "#1F3A5F", "secondario": "#5B7FA6", "testo": "#222222",
                               "tenue": "#6B7280", "sfondo_chiaro": "#F2F4F7"},
                              _deep_merge(cfg.get("colori") or {}, model.pop("colori", {}))),
        "font": _deep_merge({"titoli": "Arial", "testo": "Arial", "monospazio": "Courier New"},
                            _deep_merge(cfg.get("font") or {}, model.pop("font", {}))),
        "logo": cfg.get("logo"),
        "logo_altezza_mm": cfg.get("logo_altezza_mm", 12),
        "margine_sicurezza_mm": margine_sicurezza(cfg.get("margine_sicurezza_mm")),
        "footer": model.pop("footer", cfg.get("footer", "")),
        "lingua": cfg.get("lingua", "it"),
        "modello": model,
    }
    prof["dir"] = bdir
    prof["logo_path"] = (bdir / prof["logo"]) if prof["logo"] and (bdir / prof["logo"]).exists() else None
    return prof


def _unisci_etichette(testo):
    """P.IVA, C.F. e REA non vanno a capo separati dal loro numero."""
    return re.sub(r"(P\.?\s?IVA|C\.\s?F\.|REA)[ \t]+(?=\S)", lambda m: m.group(1) + "\u00a0", testo, flags=re.I)


def footer_text(prof):
    """Se non c'e' un footer esplicito, lo compone dai dati societari."""
    if prof["footer"]:
        return _unisci_etichette(prof["footer"])
    m = prof["marchio"]
    parts = [m.get("ragione_sociale") or m.get("nome", ""), m.get("indirizzo", "")]
    ids = []
    for k, lab in (("piva", "P.IVA"), ("cf", "C.F."), ("rea", "REA")):
        if m.get(k):
            ids.append(f"{lab} {m[k]}")
    parts.append(" - ".join(ids))
    return _unisci_etichette(" | ".join(p for p in parts if p))
