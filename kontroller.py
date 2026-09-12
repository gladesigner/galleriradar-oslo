"""Kontrollerer at datoene vi har lagret faktisk står på galleriets egen side.

Henter utstillingssiden, plukker ut alle datoer som står der, og sammenlikner
med det innhøstingen kom fram til. Brukes når noe ser rart ut:

    .venv/bin/python kontroller.py             – alt som går nå og kommer
    .venv/bin/python kontroller.py --alle      – hele basen
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from datotolk import _finn_datoer
from hent import Hentefeil, _suppe, _tekst, hent_side
from kilder import KILDE_ETTER_ID


def datoer_på_siden(url: str, kilde: dict, hint_ar: int | None = None) -> set[str] | None:
    """Alle datoer på siden. hint_ar fyller inn året der siden bare skriver
    dag og måned – ellers ville «6. juni» alltid blitt lest som i år."""
    try:
        r = hent_side(url, forsok=1, hoder=kilde.get("hoder"),
                      reserve=kilde.get("reserve", False))
    except Hentefeil:
        return None
    s = _suppe(r)
    for t in s(["script", "style", "nav", "footer"]):
        t.decompose()
    tekst = _tekst(s.select_one("main") or s.body or s)[:6000]
    return {d.isoformat() for d in _finn_datoer(tekst, hint_ar=hint_ar)}


def kontroller(rader: list[dict], parallelle: int = 6) -> list[dict]:
    def en(u):
        kilde = KILDE_ETTER_ID.get(u["kilde_id"], {})
        ar = None
        for felt in ("start_dato", "slutt_dato"):
            if u.get(felt):
                ar = int(u[felt][:4])
                break
        funnet = datoer_på_siden(u["url"], kilde, hint_ar=ar)
        if funnet is None:
            return {**u, "dom": "siden svarte ikke"}
        mangler = [d for d in (u["start_dato"], u["slutt_dato"]) if d and d not in funnet]
        if not mangler:
            return {**u, "dom": "ok"}
        return {**u, "dom": "avvik", "mangler": mangler,
                "påsiden": sorted(funnet)[:6]}

    with ThreadPoolExecutor(parallelle) as ex:
        return list(ex.map(en, rader))


if __name__ == "__main__":
    data = json.load(open("_side/data.json", encoding="utf-8"))
    i_dag = data["i_dag"]
    if "--alle" in sys.argv:
        rader = [u for u in data["utstillinger"] if u["start_dato"] or u["slutt_dato"]]
    else:
        rader = [u for u in data["utstillinger"]
                 if (u["start_dato"] or u["slutt_dato"])
                 and (not u["slutt_dato"] or u["slutt_dato"] >= i_dag)]
    print(f"Kontrollerer {len(rader)} utstillinger mot galleriens egne sider …\n")

    svar = kontroller(rader)
    avvik = [r for r in svar if r["dom"] == "avvik"]
    stumme = [r for r in svar if r["dom"] == "siden svarte ikke"]
    print(f"  ok:      {sum(1 for r in svar if r['dom'] == 'ok')}")
    print(f"  avvik:   {len(avvik)}")
    print(f"  ingen svar fra siden: {len(stumme)}\n")

    for r in sorted(avvik, key=lambda x: x["kilde_id"]):
        print(f"AVVIK  {r['galleri'][:24]:26} {r['tittel'][:36]:38}")
        print(f"       vi sier {r['start_dato']} .. {r['slutt_dato']}  (fra {r['dato_tekst']!r})")
        print(f"       på siden: {', '.join(r['påsiden']) or 'ingen datoer funnet'}")
        print(f"       {r['url']}")
