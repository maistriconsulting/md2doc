"""Nome del file generato: nome del markdown + data di release (AAAA-MM-GG)."""
import datetime
import re
from pathlib import Path

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _data_da_valore(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    t = str(v or "").strip().lower()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$", t)
        if m:
            d, mo, y = map(int, m.groups())
        else:
            m = re.match(r"^(\d{1,2})\s+([a-zà-ù]+)\s+(\d{4})$", t)
            if not (m and m.group(2) in MESI):
                return None
            d, y, mo = int(m.group(1)), int(m.group(3)), MESI.index(m.group(2)) + 1
    try:
        return datetime.date(y, mo, d)
    except ValueError:
        return None


def data_release(meta):
    """Data del front matter (date o data) se leggibile, altrimenti oggi."""
    for k in ("date", "data"):
        d = _data_da_valore((meta or {}).get(k))
        if d:
            return d.isoformat()
    return datetime.date.today().isoformat()


def pulisci(testo):
    """Tiene lettere, numeri, punto, trattino e trattino basso; il resto diventa un trattino."""
    t = re.sub(r"[^\w.\-]+", "-", str(testo), flags=re.UNICODE).strip("-._")
    return t[:80].strip("-._")


def nome_file(meta, nome_base, titolo_slug, estensione):
    """nome_base = nome del file markdown caricato (con o senza estensione); se manca, il titolo."""
    stem = pulisci(Path(str(nome_base)).stem) if nome_base else ""
    return f"{stem or titolo_slug or 'documento'}_{data_release(meta)}.{estensione}"
