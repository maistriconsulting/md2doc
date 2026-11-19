"""Interfaccia web locale. Avvio: python app.py  ->  http://127.0.0.1:5055
Nessuna intelligenza artificiale, nessuna chiamata esterna: solo regole."""
import io
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, request, send_file

from engine import convert, list_brands
from engine import gestione

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024   # 5 MB


HOST_AMMESSI = {"127.0.0.1:5055", "localhost:5055"}


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
        data, name, mime = convert(md, brand_id, request.args.get("model", ""), "pdf")
    except ValueError as e:
        raise gestione.ErroreGestione(str(e))
    except Exception as e:
        return jsonify(error=f"Errore di generazione: {e}"), 500
    r = send_file(io.BytesIO(data), mimetype=mime, download_name=name)
    r.headers["Cache-Control"] = "no-store"
    return r


@app.post("/api/convert")
def api_convert():
    md = request.form.get("markdown", "")
    f = request.files.get("file")
    if f and f.filename:
        md = f.read().decode("utf-8-sig", errors="replace")
    if not md.strip():
        return jsonify(error="Nessun testo markdown ricevuto."), 400
    try:
        data, name, mime = convert(md, request.form.get("brand", ""), request.form.get("model", ""),
                                   request.form.get("format", "pdf"))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:  # errore di impaginazione: messaggio leggibile
        return jsonify(error=f"Errore di generazione: {e}"), 500
    inline = request.form.get("inline") == "1"
    return send_file(io.BytesIO(data), mimetype=mime, download_name=name, as_attachment=not inline)


if __name__ == "__main__":
    # 127.0.0.1: raggiungibile solo dal tuo computer
    app.run(host="127.0.0.1", port=5055, debug=False)
