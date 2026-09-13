"""Kilder som ikke lar seg beskrive med CSS-velgere alene.

Nasjonalmuseet kjører oversikten sin i Vue, så listesiden er tom for en
innhøster. Utstillingssidene er derimot vanlige serversider, og de står alle
i sitemap.xml – derfor plukkes de derfra.
"""
from __future__ import annotations

import re
from datetime import date

from urllib.parse import urljoin

from hent import _suppe, _tekst, hent_detalj, hent_side

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


# Det Gule Huset skriver forsiden sin for hånd i én tekstblokk: først én
# overskrift med perioden alle utstillingene deler, så én overskrift per
# kunstner med en «Les mer»-lenke under. Tittelen står altså *utenfor* det
# som er lenken, og ingen CSS-velger kan uttrykke det.
DGH_FORSIDE = "https://www.detgulehuset.no/"


def detgulehuset(kilde: dict) -> list[dict]:
    from datotolk import tolk_periode

    s = _suppe(hent_side(DGH_FORSIDE))
    # Forsiden har flere tekstblokker. Den vi vil ha er den som har en
    # overskrift med en ekte periode i seg.
    # Overskriftene er delt med <br>: «12. september - 11. oktober 2026»
    # på én linje, «Velkommen til åpning lørdag 12. september kl. 14» på
    # neste. Leses de under ett, blir perioden til én enkelt dag.
    def linjer(h):
        return [d.strip() for d in h.get_text("\n").split("\n") if d.strip()]

    def periodelinje(h):
        for linje in linjer(h):
            a, b = tolk_periode(linje)
            if a and b and a != b:
                return linje
        return ""

    blokk = None
    for kandidat in s.select(".sqs-html-content"):
        if any(periodelinje(h) for h in kandidat.select("h1, h2, h3")):
            blokk = kandidat
            break
    if blokk is None:
        return []

    periode = ""
    ut: list[dict] = []
    for h in blokk.select("h1, h2, h3"):
        tekst = _tekst(h)
        if not tekst:
            continue
        # Den første overskriften med en ekte periode gjelder dem alle.
        if not periode:
            funnet = periodelinje(h)
            if funnet:
                periode = funnet
                continue
        lenke = None
        for sosken in h.find_next_siblings():
            if sosken.name in ("h1", "h2", "h3"):
                break
            lenke = sosken.select_one("a[href]")
            if lenke:
                break
        if lenke is None:
            continue
        url = urljoin(DGH_FORSIDE, lenke["href"])
        if not re.search(r"detgulehuset\.no/[a-z0-9-]{4,}", url) or "medlem" in url:
            continue
        # «RIRI GREEN» og undertittelen står i samme overskrift, delt med <br>.
        deler = linjer(h)
        ut.append({
            "tittel": deler[0],
            "kunstnere": " ".join(deler[1:])[:200],
            "dato_tekst": periode,
            "url": url,
            "bilde": "",
            "sammendrag": "",
            "merkelapp": "utstilling",
        })
    return ut
