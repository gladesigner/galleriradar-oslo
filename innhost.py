"""Kjører innhøstingen: alle kilder, lagring, varsling.

Kan kjøres fra kommandolinjen (også fra launchd) eller fra bakgrunnstråden
i app.py:
    .venv/bin/python innhost.py            – alle kilder
    .venv/bin/python innhost.py --stille   – uten systemvarsel
"""
from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import db
import varsel
from hent import hent_kilde
from kilder import KILDER

_laas = threading.Lock()
_gaar = False
PARALLELLE = 6


def gar_akkurat_na() -> bool:
    return _gaar


def kjor_alle(med_varsel: bool = True, app_url: str = "http://localhost:8140/") -> dict:
    """Henter alle kilder. Returnerer et sammendrag av kjøringen."""
    global _gaar
    if not _laas.acquire(blocking=False):
        return {"status": "kjører allerede"}
    _gaar = True
    start = time.time()
    alle_nye: list[dict] = []
    resultat = []
    try:
        def en(kilde):
            t0 = time.time()
            treff, feil = hent_kilde(kilde)
            return kilde, treff, feil, time.time() - t0

        with ThreadPoolExecutor(PARALLELLE) as ex:
            for kilde, treff, feil, brukt in ex.map(en, KILDER):
                for_lagring = db.na()
                nye = db.lagre_treff(treff) if treff else []
                if treff and not feil:
                    db.merk_borte(kilde["id"], for_lagring)
                db.logg_innhosting(kilde["id"], len(treff), len(nye), brukt, feil)
                alle_nye += nye
                resultat.append({"kilde": kilde["id"], "navn": kilde["navn"],
                                 "antall": len(treff), "nye": len(nye), "feil": feil})

        forste_gang = db.innstilling("har_kjort") is None
        db.sett_innstilling("har_kjort", True)
        db.sett_innstilling("sist_kjort", db.na())

        if alle_nye and med_varsel and not forste_gang:
            if db.innstilling("varsling", True):
                varsel.varsle_om_nye(alle_nye, app_url)
        return {
            "status": "ok",
            "sekunder": round(time.time() - start, 1),
            "kilder": len(KILDER),
            "treff": sum(r["antall"] for r in resultat),
            "nye": 0 if forste_gang else len(alle_nye),
            "forste_gang": forste_gang,
            "detaljer": resultat,
        }
    finally:
        _gaar = False
        _laas.release()


if __name__ == "__main__":
    svar = kjor_alle(med_varsel="--stille" not in sys.argv)
    print(f"{svar.get('status')}: {svar.get('treff')} treff, {svar.get('nye')} nye "
          f"på {svar.get('sekunder')}s")
    for r in svar.get("detaljer", []):
        if r["feil"] or not r["antall"]:
            print(f"  ⚠ {r['kilde']:20} {r['antall']:3} treff  {r['feil'] or 'ingen treff'}")
