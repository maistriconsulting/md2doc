"""Interfaccia web locale. Avvio: python app.py  ->  http://127.0.0.1:5055
Nessuna intelligenza artificiale, nessuna chiamata esterna: solo regole."""
import io
import secrets
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, request, send_file

from engine import convert, list_brands
from engine import gestione

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024   # 5 MB


HOST_AMMESSI = {"127.0.0.1:5055", "localhost:5055"}

# Anteprime in memoria (ultime 20): l'indirizzo contiene il nome del file, cosi' "Salva" dal
# visualizzatore PDF propone il nome giusto invece di un codice casuale.
ANTEPRIME = OrderedDict()


def memorizza_anteprima(data, name):
    token = secrets.token_urlsafe(9)
    ANTEPRIME[token] = (data, name)
    while len(ANTEPRIME) > 20:
        ANTEPRIME.popitem(last=False)
    return f"/api/anteprima/{token}/{name}"


@app.get("/api/anteprima/<token>/<path:nome>")
def anteprima(token, nome):
    voce = ANTEPRIME.get(token)
    if not voce:
        return jsonify(error="Anteprima scaduta: rigenerala."), 404
    r = send_file(io.BytesIO(voce[0]), mimetype="application/pdf", download_name=voce[1], as_attachment=False)
    r.headers["Cache-Control"] = "no-store"
    return r


@app.before_request
def proteggi_scritture():
    """Le operazioni che modificano file accettano solo richieste partite da questa stessa pagina."""
    if request.method in ("POST", "PUT", "DELETE"):
        if request.host not in HOST_AMMESSI:
            return jsonify(error="Richiesta non consentita."), 403
        origine = request.headers.get("Origin")
        if origine and urlparse(origine).netloc not in HOST_AMMESSI:
            return jsonify(error="Richiesta non consentita."), 403
        if request.path.startswith("/api/brand") and request.headers.get("X-MD2DOC") != "1":
            return jsonify(error="Richiesta non consentita."), 403


@app.errorhandler(gestione.ErroreGestione)
def errore_gestione(e):
    return jsonify(error=str(e)), 400


@app.get("/")
def index():
    return send_file(Path(__file__).with_name("web") / "index.html", mimetype="text/html")


@app.get("/favicon.ico")
@app.get("/apple-touch-icon.png")
def icona_pagina():
    """Icona della scheda del browser: file generato da mac/icona.py (se manca, nessuna icona)."""
    nome = request.path.lstrip("/")
    f = Path(__file__).with_name("web") / nome
    if not f.is_file():
        return "", 404
    r = send_file(f, mimetype="image/x-icon" if nome.endswith(".ico") else "image/png")
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.get("/api/brands")
def brands():
    return jsonify(list_brands())


@app.get("/api/brand/<brand_id>")
def brand_leggi(brand_id):
    return jsonify(gestione.leggi_marchio(brand_id))


@app.post("/api/brand")
def brand_crea():
    dati = request.get_json(silent=True) or {}
    nuovo = gestione.crea_marchio(dati.get("nome"), dati.get("copia_da"))
    return jsonify(id=nuovo)


@app.put("/api/brand/<brand_id>")
def brand_salva(brand_id):
    return jsonify(gestione.salva_marchio(brand_id, request.get_json(silent=True)))


@app.delete("/api/brand/<brand_id>")
def brand_elimina(brand_id):
    return jsonify(spostato_in=gestione.elimina_marchio(brand_id))


@app.post("/api/brand/<brand_id>/logo")
def brand_logo_carica(brand_id):
    f = request.files.get("logo")
    if not f:
        raise gestione.ErroreGestione("Nessun file ricevuto.")
    gestione.salva_logo(brand_id, f.read())
    return jsonify(ok=True)


@app.get("/api/brand/<brand_id>/logo")
def brand_logo(brand_id):
    r = send_file(gestione.percorso_logo(brand_id), mimetype="image/png")
    r.headers["Cache-Control"] = "no-store"
    return r


@app.get("/api/brand/<brand_id>/prova")
def brand_prova(brand_id):
    """PDF di prova con esempi/prova.md, per vedere subito l'effetto delle impostazioni."""
    md = (Path(__file__).with_name("esempi") / "prova.md").read_text(encoding="utf-8")
    try:
        data, name, mime = convert(md, brand_id, request.args.get("model", ""), "pdf", nome_base=f"prova-{brand_id}")
    except ValueError as e:
        raise gestione.ErroreGestione(str(e))
    except Exception as e:
        return jsonify(error=f"Errore di generazione: {e}"), 500
    return jsonify(url=memorizza_anteprima(data, name))


@app.post("/api/convert")
def api_convert():
    md = request.form.get("markdown", "")
    nome_base = request.form.get("filename", "").strip() or None
    f = request.files.get("file")
    if f and f.filename:
        md = f.read().decode("utf-8-sig", errors="replace")
        nome_base = f.filename
    if not md.strip():
        return jsonify(error="Nessun testo markdown ricevuto."), 400
    try:
        data, name, mime = convert(md, request.form.get("brand", ""), request.form.get("model", ""),
                                   request.form.get("format", "pdf"), nome_base=nome_base)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:  # errore di impaginazione: messaggio leggibile
        return jsonify(error=f"Errore di generazione: {e}"), 500
    if request.form.get("inline") == "1":
        return jsonify(url=memorizza_anteprima(data, name))
    return send_file(io.BytesIO(data), mimetype=mime, download_name=name, as_attachment=True)


if __name__ == "__main__":
    # 127.0.0.1: raggiungibile solo dal tuo computer
    app.run(host="127.0.0.1", port=5055, debug=False)
