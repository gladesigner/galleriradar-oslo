"""Kilder som ikke lar seg beskrive med CSS-velgere alene.

Nasjonalmuseet kjører oversikten sin i Vue, så listesiden er tom for en
innhøster. Utstillingssidene er derimot vanlige serversider, og de står alle
i sitemap.xml – derfor plukkes de derfra.
"""
from __future__ import annotations

import re
from datetime import date

from hent import hent_detalj, hent_side

NM_SITEMAP = "https://www.nasjonalmuseet.no/sitemap.xml"
NM_MONSTER = re.compile(r"/utstillinger-og-arrangementer/[^/]+/utstillinger/(20\d{2})/([^/]+)/?$")


def nasjonalmuseet(kilde: dict) -> list[dict]:
    r = hent_side(NM_SITEMAP)
    i_ar = date.today().year
    adresser: list[tuple[int, str]] = []
    for m in re.finditer(r"<loc>([^<]+)</loc>", r.text):
        url = m.group(1)
        t = NM_MONSTER.search(url)
        if not t:
            continue
        ar = int(t.group(1))
        if ar < i_ar - 1:
            continue
        adresser.append((ar, url.rstrip("/") + "/"))

    adresser = sorted(set(adresser), reverse=True)[:60]
    ut = []
    for ar, url in adresser:
        d = hent_detalj(url, kilde)
        tittel = (d.get("tittel") or "").split(" - Nasjonalmuseet")[0].strip()
        if not tittel:
            continue
        ut.append({
            "tittel": tittel,
            "kunstnere": "",
            "dato_tekst": d.get("dato_tekst", ""),
            "url": url,
            "bilde": d.get("bilde", ""),
            "sammendrag": d.get("sammendrag", ""),
            "merkelapp": "utstilling",
            "ar_hint": ar,
        })
    return ut
