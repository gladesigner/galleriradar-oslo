"""Innhøstingsmotor: henter utstillinger fra gallerienes egne nettsider.

Hver kilde beskrives deklarativt i kilder.py. Motoren støtter fire typer:

  css      – hent en oversiktsside, plukk elementer med CSS-velgere
  jsonld   – les schema.org Event/ExhibitionEvent fra siden
  wp       – WordPress REST API (wp-json), valgfri innholdstype
  funk     – egen python-funksjon for sider som ikke lar seg beskrive

Alt normaliseres til samme ordbok, slik at resten av appen slipper å vite
hvilken teknologi den enkelte gallerinettsiden er bygget på.
"""
from __future__ import annotations

import html
import json
import os
import re
import socket
import sqlite3
import time
from urllib.parse import urljoin, urlparse

import requests
import soupsieve as sv
import urllib3.util.connection as _tilkobling
from bs4 import BeautifulSoup

# GitHubs tjenere har ikke IPv6. Slår et navneoppslag ut i en AAAA-adresse først,
# ender forespørselen som «Network is unreachable» selv om nettstedet er oppe.
# Vi ber derfor alltid om IPv4.
_tilkobling.allowed_gai_family = lambda: socket.AF_INET

from datotolk import datostart, tolk_periode

HODER = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    # Noen nettsteder slipper bare gjennom forespørsler som ser ut som en ekte
    # faneåpning i en nettleser. Disse feltene koster ingenting og åpner flere dører.
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

TIDSAVBRUDD = 25


class Hentefeil(Exception):
    pass


# Enkelte nettsteder slipper ikke inn forespørsler fra datasentre – da får
# GitHub-jobben 403 selv om det samme virker fint hjemmefra. For de kildene
# hentes siden om igjen gjennom en lesetjeneste som svarer med rå HTML.
RESERVEVEI = "https://r.jina.ai/{}"


def _reservehent(url: str) -> requests.Response:
    # Lesetjenesten vil ha en enkel forespørsel – nettleserhodene våre gir 403 der.
    r = requests.get(RESERVEVEI.format(url),
                     headers={"X-Return-Format": "html", "Accept": "*/*"}, timeout=60)
    r.raise_for_status()
    r.url = url          # så relative lenker fortsatt peker til galleriet selv
    return r


def hent_side(url: str, forsok: int = 3, hoder: dict | None = None,
              reserve: bool = False, bare_reserve: bool = False) -> requests.Response:
    if bare_reserve:
        return _reservehent(url)
    siste = None
    for n in range(forsok):
        try:
            r = requests.get(url, headers={**HODER, **(hoder or {})},
                             timeout=TIDSAVBRUDD, allow_redirects=True)
            if r.status_code in (403, 429) or r.status_code >= 500:
                if n + 1 < forsok:
                    time.sleep(3)
                    continue
            r.raise_for_status()
            return r
        except Exception as e:          # noqa: BLE001 – vi vil ha alle feil som Hentefeil
            siste = e
            if n + 1 < forsok:
                time.sleep(1.5)
    if reserve:
        try:
            return _reservehent(url)
        except Exception as e:            # noqa: BLE001 – da er begge veier prøvd
            raise Hentefeil(f"{type(siste).__name__}: {siste} (reservevei: {e})") from e
    raise Hentefeil(f"{type(siste).__name__}: {siste}")


def _suppe(r: requests.Response) -> BeautifulSoup:
    return BeautifulSoup(r.text, "lxml")


def _tekst(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _plukk(rot, velger: str | None) -> str:
    if not velger:
        return ""
    if velger == "self":
        return _tekst(rot)
    for v in velger.split("|"):
        el = rot.select_one(v.strip())
        if el is not None:
            # <time datetime="..."> er mer presist enn teksten
            if el.name == "time" and el.get("datetime"):
                return el["datetime"]
            t = _tekst(el)
            if t:
                return t
    return ""


def _plukk_dato(rot, velger: str | None) -> str:
    """Første treff som faktisk lar seg tolke som dato – ellers første treff."""
    if not velger:
        return ""
    forste = ""
    for v in velger.split("|"):
        for el in rot.select(v.strip()):
            if el.name == "time" and el.get("datetime"):
                return el["datetime"]
            t = _tekst(el)
            if not t:
                continue
            forste = forste or t
            if tolk_periode(t)[0] or tolk_periode(t)[1]:
                return t
    return forste


def _plukk_ikke_dato(rot, velger: str | None) -> str:
    """Første treff som ikke er en dato – for felt der dato og navn deler klasse."""
    if not velger:
        return ""
    for v in velger.split("|"):
        for el in rot.select(v.strip()):
            t = _tekst(el)
            if t and not (tolk_periode(t)[0] or tolk_periode(t)[1]):
                return t
    return ""


def _fra_srcset(srcset: str) -> list[tuple[int, str]]:
    """«bilde.jpg 300w, bilde-stor.jpg 1024w» → [(300, ...), (1024, ...)]"""
    ut = []
    # Deles bare på komma etterfulgt av mellomrom: adressene selv kan ha
    # komma i seg, slik MUNCH har det i «crop=151,0,2799,1765».
    for bit in re.split(r",\s+", srcset.strip()):
        deler = bit.strip().split()
        if not deler:
            continue
        bredde = 0
        if len(deler) > 1 and deler[1].endswith("w"):
            try:
                bredde = int(deler[1][:-1])
            except ValueError:
                bredde = 0
        ut.append((bredde, deler[0]))
    return ut


def _bilde(rot, velger: str | None, basis: str) -> str:
    """Finner det største fornuftige bildet i et element.

    Mange nettsteder legger et bitte lite plassholderbilde i src og de ekte
    bildene i srcset – Fotogalleriet bruker 16 piksler brede stubber. Derfor
    leses srcset først, og bredeste variant under 2000 piksler vinner.
    """
    el = rot.select_one(velger) if velger else None
    if el is None:
        el = rot.select_one("img")
    if el is None:
        return ""

    kandidater: list[tuple[int, str]] = []
    for kilde in [el] + rot.select("source"):
        for attr in ("srcset", "data-srcset"):
            if kilde.get(attr):
                kandidater += _fra_srcset(kilde[attr])
    for attr in ("data-src", "data-lazy-src", "data-original", "src", "content"):
        v = el.get(attr)
        if v and not v.startswith("data:"):
            kandidater.append((0, v))

    kandidater = [(b, u) for b, u in kandidater if u and not u.startswith("data:")]
    if not kandidater:
        return ""
    med_bredde = [k for k in kandidater if k[0] > 0]
    if med_bredde:
        brukbare = [k for k in med_bredde if k[0] <= 2000] or med_bredde
        valgt = max(brukbare, key=lambda k: k[0])[1]
    else:
        valgt = kandidater[0][1]
    return urljoin(basis, valgt)


def _rens(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


# ───────────────────────────── adaptere ─────────────────────────────

def _ar_hint(el, oppsett: dict | None) -> int | None:
    """Finner årstallet raden står under, for datoer som «14.08 – 03.10»."""
    if not oppsett:
        return None
    velger_mor = oppsett.get("foreldre")
    for mor in el.parents:
        if not getattr(mor, "name", None) or mor.name == "[document]":
            break
        if velger_mor and not sv.match(velger_mor, mor):
            continue
        kilde_tekst = ""
        if oppsett.get("velger"):
            for v in oppsett["velger"].split("|"):
                kilde_tekst = _tekst(mor.select_one(v.strip()))
                if kilde_tekst:
                    break
        if not kilde_tekst:
            kilde_tekst = _tekst(mor)[:120]
        m = re.search(r"\b(20\d{2})\b", kilde_tekst)
        if m:
            return int(m.group(1))
        if velger_mor:
            return None
    return None


def _fra_css(kilde: dict) -> list[dict]:
    treff: list[dict] = []
    monster = re.compile(kilde["url_monster"]) if kilde.get("url_monster") else None
    for url in kilde.get("sider") or [kilde["url"]]:
        r = hent_side(url, hoder=kilde.get("hoder"), reserve=kilde.get("reserve", False),
                      bare_reserve=kilde.get("_tving_reserve", False))
        s = _suppe(r)
        rammer = s.select(kilde["element"])
        if kilde.get("underelement"):
            par = [(ramme, u) for ramme in rammer for u in ramme.select(kilde["underelement"])]
        else:
            par = [(el, el) for el in rammer]
        for ramme, el in par:
            lenke_el = el.select_one(kilde.get("lenke", "a[href]")) if kilde.get("lenke") != "self" else el
            href = lenke_el.get("href") if lenke_el else None
            if not href and el.name == "a":
                href = el.get("href")
            tittel = _plukk(el, kilde.get("tittel")) or _tekst(lenke_el)
            if not tittel:
                continue
            fullurl = urljoin(r.url, href) if href else r.url
            if monster and not monster.search(fullurl):
                continue
            dato_tekst = _plukk_dato(el, kilde.get("dato")) or _plukk_dato(ramme, kilde.get("dato"))
            treff.append({
                "tittel": tittel,
                "kunstnere": _plukk_ikke_dato(el, kilde.get("kunstnere")),
                "dato_tekst": dato_tekst,
                "url": fullurl,
                "ar_hint": _ar_hint(ramme, kilde.get("ar_hint")),
                "bilde": _bilde(el, kilde.get("bilde"), r.url)
                         or _bilde(ramme, kilde.get("bilde"), r.url),
                "sammendrag": _plukk(el, kilde.get("sammendrag")),
                "merkelapp": _plukk(el, kilde.get("merkelapp")),
            })
    return treff


def _samle_jsonld(s: BeautifulSoup) -> list[dict]:
    ut: list[dict] = []

    def gaa(o):
        if isinstance(o, dict):
            if "@graph" in o:
                gaa(o["@graph"])
            t = o.get("@type")
            t = t if isinstance(t, list) else [t] if t else []
            if any(str(x).lower().endswith("event") or str(x) in ("ExhibitionEvent", "VisualArtsEvent")
                   for x in t):
                ut.append(o)
            for v in o.values():
                if isinstance(v, (dict, list)):
                    gaa(v)
        elif isinstance(o, list):
            for v in o:
                gaa(v)

    for tag in s.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        try:
            gaa(json.loads(raw))
        except Exception:                # noqa: BLE001 – ugyldig JSON-LD er vanlig
            continue
    return ut


def _fra_jsonld(kilde: dict) -> list[dict]:
    treff = []
    for url in kilde.get("sider") or [kilde["url"]]:
        r = hent_side(url)
        for ev in _samle_jsonld(_suppe(r)):
            navn = _rens(ev.get("name") or "")
            if not navn:
                continue
            bilde = ev.get("image")
            if isinstance(bilde, list):
                bilde = bilde[0] if bilde else ""
            if isinstance(bilde, dict):
                bilde = bilde.get("url", "")
            treff.append({
                "tittel": navn,
                "kunstnere": "",
                "dato_tekst": f"{ev.get('startDate','')} {ev.get('endDate','')}".strip(),
                "url": urljoin(r.url, ev.get("url") or ""),
                "bilde": bilde or "",
                "sammendrag": _rens(ev.get("description") or "")[:600],
                "merkelapp": "",
            })
    return treff


def _fra_wp(kilde: dict) -> list[dict]:
    basis = kilde["url"].rstrip("/")
    type_ = kilde.get("posttype", "posts")
    felt = kilde.get("felt", {})
    url = f"{basis}/wp-json/wp/v2/{type_}?per_page={kilde.get('antall', 40)}&_embed=1"
    r = hent_side(url)
    data = r.json()
    if isinstance(data, dict):
        raise Hentefeil(data.get("message", "uventet svar fra wp-json"))
    treff = []
    for p in data:
        tittel = _rens((p.get("title") or {}).get("rendered", ""))
        if not tittel:
            continue
        meta = p.get("acf") or p.get("meta") or {}
        dato_tekst = ""
        for n in (felt.get("dato") or []):
            if meta.get(n):
                dato_tekst += f" {meta[n]}"
        treff.append({
            "tittel": tittel,
            "kunstnere": _rens(str(meta.get(felt.get("kunstnere", "")) or "")),
            "dato_tekst": dato_tekst.strip() or p.get("date", "")[:10],
            "url": p.get("link", ""),
            "bilde": (((p.get("_embedded") or {}).get("wp:featuredmedia") or [{}])[0]
                      .get("source_url", "")),
            "sammendrag": _rens((p.get("excerpt") or {}).get("rendered", ""))[:600],
            "merkelapp": "",
        })
    return treff


ADAPTERE = {"css": _fra_css, "jsonld": _fra_jsonld, "wp": _fra_wp}

# Gallerienes egne merkelapper på norsk og engelsk, samlet til noen få ord
TYPER = {
    "exhibition": "utstilling", "exhibitions": "utstilling", "utstillinger": "utstilling",
    "utstilling": "utstilling", "current": "utstilling", "upcoming": "utstilling",
    "event": "arrangement", "events": "arrangement", "arrangementer": "arrangement",
    "arrangement": "arrangement", "kunstnersamtale": "samtale", "artist talk": "samtale",
    "konsert": "konsert", "kino": "film", "film": "film", "performance": "performance",
    "verksted": "verksted", "workshop": "verksted", "omvisning": "omvisning",
}


# Ord som avslører at dette er et enkeltarrangement og ikke en utstilling.
# Mange gallerier merker ikke slikt selv, men skriver det i tittelen.
ARRANGEMENTSORD = re.compile(
    # Norsk setter sammen ord: «Søndagsomvisning» er like mye en omvisning som
    # «Omvisning», så disse får lov til å ha hva som helst foran seg.
    r"\w*(?:omvisning|verksted|samtale|konsert|foredrag|lansering|vernissage|"
    r"filmvisning|opplesning|forestilling|seminar|konferanse|\u00e5pningsfest|kveldsåpent)"
    r"|\b(?:artist talk|talk|performance|workshop|kurs|quiz|panel|kino|dj|"
    r"familiedag|barnas|markering|fest|jubileumsfest)\b",
    re.IGNORECASE)


def _er_arrangement(type_: str, tittel: str) -> bool:
    """Et enkeltarrangement skjer på et klokkeslett, en utstilling står en periode."""
    if type_ and type_ != "utstilling":
        return True
    return bool(ARRANGEMENTSORD.search(tittel))


def _type(merkelapp: str, standard: str) -> str:
    t = (merkelapp or standard or "utstilling").strip().lower()
    for ord_ in t.replace("/", " ").split():
        if ord_ in TYPER:
            return TYPER[ord_]
    return TYPER.get(t, t[:40])


# ───────────────────────────── kjøring ─────────────────────────────

def _nokkel(url: str, tittel: str) -> str:
    """Stabil identitet for en utstilling, uavhengig av små endringer i tittelen."""
    p = urlparse(url or "")
    sti = (p.path or "").rstrip("/")
    if sti and sti.count("/") >= 1 and len(sti) > 1:
        return f"{p.netloc}{sti}".lower()
    return re.sub(r"[^a-z0-9æøå]+", "-", f"{p.netloc} {tittel}".lower()).strip("-")


DETALJ_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "detaljer.db")


def _cache():
    os.makedirs(os.path.dirname(DETALJ_CACHE), exist_ok=True)
    k = sqlite3.connect(DETALJ_CACHE, timeout=20)
    k.execute("""CREATE TABLE IF NOT EXISTS detalj (
                     url TEXT PRIMARY KEY, hentet REAL,
                     dato_tekst TEXT, bilde TEXT, sammendrag TEXT, tittel TEXT)""")
    return k


def hent_detalj(url: str, kilde: dict) -> dict:
    """Henter datoer/bilde/ingress fra utstillingens egen side. Mellomlagres."""
    k = _cache()
    try:
        rad = k.execute("SELECT hentet, dato_tekst, bilde, sammendrag, tittel FROM detalj WHERE url=?",
                        (url,)).fetchone()
        levetid = 14 * 86400 if (rad and rad[1]) else 2 * 86400
        if rad and time.time() - rad[0] < levetid:
            return {"dato_tekst": rad[1], "bilde": rad[2], "sammendrag": rad[3], "tittel": rad[4]}
        try:
            r = hent_side(url, forsok=1, hoder=kilde.get("hoder"),
                          reserve=kilde.get("reserve", False))
        except Hentefeil:
            return {}
        sup = _suppe(r)
        for tag in sup(["script", "style", "nav", "footer"]):
            tag.decompose()
        dato_tekst = _plukk_dato(sup, kilde.get("detalj_dato") or "") if kilde.get("detalj_dato") else ""
        if not dato_tekst:
            brodtekst = _tekst(sup.select_one("main") or sup.body or sup)[:2500]
            for bit in re.split(r"(?<=[.!?»])\s+|\n", brodtekst):
                if tolk_periode(bit)[0] and len(bit) < 120:
                    dato_tekst = bit.strip()
                    break
        bilde = ""
        og = sup.find("meta", property="og:image")
        if og and og.get("content"):
            bilde = urljoin(r.url, og["content"])
        beskr = sup.find("meta", property="og:description") or sup.find("meta", attrs={"name": "description"})
        sammendrag = _rens(beskr.get("content", "")) if beskr else ""
        ot = sup.find("meta", property="og:title")
        tittel = _rens(ot.get("content", "")) if ot else _rens(sup.title.string if sup.title else "")
        k.execute("INSERT OR REPLACE INTO detalj VALUES (?,?,?,?,?,?)",
                  (url, time.time(), dato_tekst, bilde, sammendrag, tittel))
        k.commit()
        return {"dato_tekst": dato_tekst, "bilde": bilde,
                "sammendrag": sammendrag, "tittel": tittel}
    finally:
        k.close()


def _uten_gjentakelse(kunstnere: str, tittel: str) -> str:
    """Fjerner utstillingstittelen fra kunstnerfeltet når de deler element."""
    if not kunstnere:
        return ""
    ut = re.sub(re.escape(tittel), " ", kunstnere, flags=re.IGNORECASE).strip(" –—-,:·|")
    return re.sub(r"\s+", " ", ut).strip()


def _rydd(t: dict, kilde: dict) -> dict | None:
    tittel = _rens(t.get("tittel", ""))
    if not tittel or len(tittel) < 2:
        return None
    for m in kilde.get("hopp_over", []):
        if re.search(m, tittel, re.IGNORECASE):
            return None
    dato_tekst = _rens(t.get("dato_tekst", ""))
    start, slutt = tolk_periode(dato_tekst, t.get("ar_hint"))
    url = t.get("url", "") or kilde["url"]
    bilde = t.get("bilde", "")
    sammendrag = _rens(t.get("sammendrag", ""))

    # Detaljsiden hentes når listen mangler noe vi vil ha: datoer, bilde
    # eller tittel. Svaret mellomlagres, så det koster lite.
    mangler = (not (start or slutt)) or (not bilde) or kilde.get("tittel_fra_detalj")
    if kilde.get("detalj") and url.startswith("http") and mangler:
        d = hent_detalj(url, kilde)
        if kilde.get("tittel_fra_detalj") and d.get("tittel"):
            tittel = d["tittel"].split(" | ")[0].split(" - ")[0].strip() or tittel
        if d.get("dato_tekst"):
            dato_tekst = _rens(d["dato_tekst"])
            start, slutt = tolk_periode(dato_tekst, t.get("ar_hint"))
        bilde = bilde or d.get("bilde", "")
        sammendrag = sammendrag or d.get("sammendrag", "")

    if kilde.get("krev_dato") and not (start or slutt):
        return None

    if start or slutt:                      # klipp datoen av titler som «Sommerutstilling 18.6-16.8.26»
        i = datostart(tittel)
        if i is not None and i > 3:
            tittel = re.sub(r"\s+", " ", tittel[:i]).strip(" –—-,:·|") or tittel
    kunstnere = _uten_gjentakelse(_rens(t.get("kunstnere", "")), tittel)
    mine_type = _type(t.get("merkelapp", ""), kilde.get("type", "utstilling"))
    return {
        "kilde_id": kilde["id"],
        "galleri": kilde["navn"],
        "kategori": kilde.get("kategori", "galleri"),
        "region": kilde.get("region", "oslo"),
        "bydel": kilde.get("bydel", ""),
        "tittel": tittel[:300],
        "kunstnere": kunstnere[:400],
        "dato_tekst": dato_tekst[:200],
        "start_dato": start,
        "slutt_dato": slutt,
        "url": url,
        "bilde": (bilde or "")[:700],
        "sammendrag": sammendrag[:700],
        "type": mine_type,
        "arrangement": _er_arrangement(mine_type, tittel),
        "nokkel": _nokkel(url, tittel),
    }


def hent_kilde(kilde: dict) -> tuple[list[dict], str | None]:
    """Henter én kilde. Returnerer (treff, feilmelding)."""
    try:
        if kilde.get("type_adapter") == "funk":
            import egne
            raa = getattr(egne, kilde["funksjon"])(kilde)
        else:
            raa = ADAPTERE[kilde.get("type_adapter", "css")](kilde)
    except Hentefeil as e:
        return [], str(e)
    except Exception as e:                # noqa: BLE001 – én ødelagt kilde skal ikke velte resten
        return [], f"{type(e).__name__}: {e}"

    # Enkelte nettsteder svarer 200 med en tom eller annerledes side til
    # datasentre. Da er det verdt å prøve reserveveien før vi gir opp.
    if not raa and kilde.get("reserve") and not kilde.get("_tving_reserve"):
        return hent_kilde({**kilde, "_tving_reserve": True})

    ut, sett = [], set()
    for t in raa[: kilde.get("maks", 200)]:
        rad = _rydd(t, kilde)
        if not rad or rad["nokkel"] in sett:
            continue
        sett.add(rad["nokkel"])
        ut.append(rad)
    return ut, None


if __name__ == "__main__":
    import sys
    from kilder import KILDER
    valgt = sys.argv[1:] or [k["id"] for k in KILDER]
    for k in KILDER:
        if k["id"] not in valgt:
            continue
        t0 = time.time()
        treff, feil = hent_kilde(k)
        merke = "FEIL" if feil else ("TOM " if not treff else "ok  ")
        print(f"{merke} {k['id']:22} {len(treff):3} treff  {time.time()-t0:4.1f}s  {feil or ''}")
        for r in treff[:4]:
            print(f"        · {r['tittel'][:60]:62} {r['start_dato']}..{r['slutt_dato']}  {r['url'][:70]}")
