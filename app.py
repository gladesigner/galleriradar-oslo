"""Galleriradaren – hva skjer på gallerier og museer i Oslo.

Start med:  ./start.sh      (eller .venv/bin/python app.py)
Åpnes på:   http://localhost:8140/
"""
from __future__ import annotations

import os
import threading
import time
from datetime import date, datetime

from flask import (Flask, jsonify, redirect, render_template, request,
                   send_file, send_from_directory)

import bilder
import db
import innhost
from datotolk import periodetekst
from kilder import KILDER, KILDE_ETTER_ID

PORT = int(os.environ.get("PORT", "8140"))
INTERVALL_TIMER = float(os.environ.get("NB_GALLERI_INTERVALL", "4"))

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


# ───────────────────────────── sider ─────────────────────────────

@app.get("/")
def forside():
    return render_template("index.html", gallerier=db.gallerier(), antall_kilder=len(KILDER))


@app.get("/kilder")
def kildeside():
    return render_template("kilder.html", kilder=KILDER, status={s["kilde_id"]: s
                                                                 for s in db.kildestatus()})


# ───────────────────────────── api ─────────────────────────────

def _pynt(r: dict) -> dict:
    r["periode"] = periodetekst(r.get("start_dato"), r.get("slutt_dato"), r.get("dato_tekst") or "")
    i_dag = date.today().isoformat()
    slutt = r.get("slutt_dato")
    r["dager_igjen"] = None
    if slutt and slutt >= i_dag:
        r["dager_igjen"] = (date.fromisoformat(slutt) - date.today()).days
    r["nettsted"] = (KILDE_ETTER_ID.get(r["kilde_id"], {}) or {}).get("url", "")
    return r


@app.get("/api/utstillinger")
def api_utstillinger():
    rader = db.hent(
        visning=request.args.get("visning", "aktuelt"),
        galleri=request.args.get("galleri", ""),
        kategori=request.args.get("kategori", ""),
        sok=request.args.get("sok", "").strip(),
        grense=int(request.args.get("grense", 400)),
    )
    return jsonify({"antall": len(rader), "utstillinger": [_pynt(r) for r in rader],
                    "tall": db.tall()})


@app.get("/api/status")
def api_status():
    status = db.kildestatus()
    return jsonify({
        "tall": db.tall(),
        "sist_kjort": db.innstilling("sist_kjort"),
        "kjorer": innhost.gar_akkurat_na(),
        "varsling": db.innstilling("varsling", True),
        "intervall_timer": INTERVALL_TIMER,
        "kilder": [{**s, "navn": KILDE_ETTER_ID.get(s["kilde_id"], {}).get("navn", s["kilde_id"])}
                   for s in status],
        "kilder_med_feil": [s["kilde_id"] for s in status if s["feil"] or not s["antall"]],
    })


@app.post("/api/oppdater")
def api_oppdater():
    if innhost.gar_akkurat_na():
        return jsonify({"status": "kjører allerede"}), 202
    svar = innhost.kjor_alle(med_varsel=True, app_url=f"http://localhost:{PORT}/")
    return jsonify(svar)


@app.post("/api/merk")
def api_merk():
    data = request.get_json(force=True)
    db.merk(data["nokkel"], bool(data.get("pa")))
    return jsonify({"ok": True, "merket": db.tall()["merket"]})


@app.post("/api/varsling")
def api_varsling():
    pa = bool(request.get_json(force=True).get("pa"))
    db.sett_innstilling("varsling", pa)
    return jsonify({"varsling": pa})


@app.get("/bilde")
def bildeproxy():
    """Nedskalert kopi av galleriets bilde – sparer mobildata og lastetid."""
    url = request.args.get("u", "")
    sti = bilder.hent_bilde(url)
    if not sti:
        return redirect(url) if url.startswith("http") else ("", 404)
    svar = send_file(sti, mimetype="image/jpeg", conditional=True)
    svar.headers["Cache-Control"] = "public, max-age=2592000"
    return svar


# ───────────────────── app for hjem-skjermen ─────────────────────

@app.get("/manifest.webmanifest")
def manifest():
    svar = jsonify({
        "name": "Galleriradar Oslo",
        "short_name": "Galleriradar",
        "description": "Hva skjer på gallerier og museer i Oslo",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f6f4f0",
        "theme_color": "#1b1a18",
        "icons": [
            {"src": "/static/ikon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/ikon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/static/ikon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
    })
    svar.headers["Content-Type"] = "application/manifest+json"
    return svar


@app.get("/sw.js")
def servicearbeider():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")


# ───────────────────── innhøsting i bakgrunnen ─────────────────────

def bakgrunn():
    """Henter kildene med jevne mellomrom så lenge appen kjører."""
    time.sleep(8)
    while True:
        try:
            sist = db.innstilling("sist_kjort")
            moden = True
            if sist:
                gikk = (datetime.now() - datetime.fromisoformat(sist)).total_seconds()
                moden = gikk >= INTERVALL_TIMER * 3600
            if moden:
                innhost.kjor_alle(med_varsel=True, app_url=f"http://localhost:{PORT}/")
        except Exception as e:                      # noqa: BLE001 – tråden skal aldri dø
            print(f"[bakgrunn] {type(e).__name__}: {e}", flush=True)
        time.sleep(600)


if __name__ == "__main__":
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Thread(target=bakgrunn, daemon=True, name="innhosting").start()
    print(f"Galleriradar kjører på http://localhost:{PORT}/  (henter nytt hver "
          f"{INTERVALL_TIMER:g}. time)", flush=True)
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
