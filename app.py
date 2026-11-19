"""Interfaccia web locale. Avvio: python app.py  ->  http://127.0.0.1:5055
Nessuna intelligenza artificiale, nessuna chiamata esterna: solo regole."""
import io
from flask import Flask, jsonify, request, send_file

from engine import convert, list_brands

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024   # 5 MB


@app.get("/")
def index():
    from pathlib import Path
    return send_file(Path(__file__).with_name("web") / "index.html", mimetype="text/html")


@app.get("/api/brands")
def brands():
    return jsonify(list_brands())


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
