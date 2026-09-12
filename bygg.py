"""Bygger den statiske utgaven av Galleriradaren.

Kjøres både lokalt og av GitHub Actions:

    .venv/bin/python bygg.py --ut _side --forrige https://<bruker>.github.io/<repo>/data.json

Stegene er de samme hver gang:
  1. les forrige data.json, så vi vet hva som allerede var kjent
  2. hent alle kilder
  3. skriv ny data.json, hent ned og skaler bildene
  4. si fra på ntfy om noe er nytt

Det finnes ingen database her. Forrige publiserte data.json *er* hukommelsen,
og det holder – da slipper vi å dra en binærfil med i hver eneste kjøring.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import requests

import bilder
from datotolk import periodetekst
from hent import hent_kilde
from kilder import KILDER

HER = os.path.dirname(os.path.abspath(__file__))
FRONT = os.path.join(HER, "front")
BILDECACHE = os.path.join(HER, "data", "bilder")

BEHOLD_DAGER = 730          # hvor lenge avsluttede utstillinger blir liggende
MAKS_RADER = 1500
BILDE_VINDU = 90            # bare hent bilder for det som er aktuelt eller nylig


def _na() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ────────────────────────── forrige kjøring ──────────────────────────

def les_forrige(peker: str | None) -> dict:
    """Henter forrige data.json – fra nett eller fra disk. Tåler at den mangler."""
    if not peker:
        return {}
    try:
        if peker.startswith(("http://", "https://")):
            r = requests.get(peker, timeout=30)
            if r.status_code == 404:
                print("  forrige data.json finnes ikke ennå – dette er første kjøring")
                return {}
            r.raise_for_status()
            return r.json()
        with open(peker, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:                # noqa: BLE001 – første kjøring skal ikke velte
        print(f"  klarte ikke lese forrige data.json ({type(e).__name__}: {e})")
        return {}


# ────────────────────────── innhøsting ──────────────────────────

def hent_alt(parallelle: int = 6) -> tuple[list[dict], list[dict]]:
    def en(kilde):
        t0 = time.time()
        treff, feil = hent_kilde(kilde)
        return kilde, treff, feil, round(time.time() - t0, 1)

    rader: list[dict] = []
    status: list[dict] = []
    with ThreadPoolExecutor(parallelle) as ex:
        for kilde, treff, feil, brukt in ex.map(en, KILDER):
            rader += treff
            status.append({
                "id": kilde["id"], "navn": kilde["navn"], "url": kilde["url"],
                "kategori": kilde.get("kategori", "galleri"),
                "region": kilde.get("region", "oslo"),
                "bydel": kilde.get("bydel", ""),
                "adresse": kilde.get("adresse", ""),
                "lat": kilde.get("lat"), "lon": kilde.get("lon"),
                "antall": len(treff), "feil": feil, "sekunder": brukt,
            })
            merke = "FEIL" if feil else ("tom " if not treff else "ok  ")
            print(f"  {merke} {kilde['id']:20} {len(treff):3} treff {brukt:5.1f}s {feil or ''}")
    return rader, status


def flett(ferske: list[dict], forrige: dict,
          status: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Setter sammen nytt og kjent. Returnerer (alle rader, nye rader)."""
    kjent = {u["nokkel"]: u for u in forrige.get("utstillinger", [])}
    forste_kjoring = not kjent
    na = _na()
    i_dag = date.today()
    grense = (i_dag - timedelta(days=BEHOLD_DAGER)).isoformat()

    # Kilder som feilet denne gangen sier ingenting om hva som fortsatt henger.
    # Utstillingene deres får stå som de sto, i stedet for å bli meldt avsluttet.
    stumme = {k["id"] for k in (status or []) if k.get("feil") or not k.get("antall")}

    ut: dict[str, dict] = {}
    nye: list[dict] = []

    for r in ferske:
        gammel = kjent.get(r["nokkel"])
        rad = dict(r)
        rad["forste_gang"] = gammel["forste_gang"] if gammel else na
        rad["sist_sett"] = na
        rad["borte"] = False
        if not gammel:
            nye.append(rad)
        ut[rad["nokkel"]] = rad

    # Det kilden ikke nevner lenger blir liggende en stund, så «Tidligere» har innhold.
    for nokkel, gammel in kjent.items():
        if nokkel in ut:
            continue
        if (gammel.get("slutt_dato") or gammel.get("start_dato") or "9999") < grense:
            continue
        gammel = dict(gammel)
        gammel["borte"] = gammel.get("borte", False) if gammel.get("kilde_id") in stumme else True
        ut[nokkel] = gammel

    rader = sorted(ut.values(), key=lambda u: (u.get("slutt_dato") or "9999", u["galleri"]))
    if len(rader) > MAKS_RADER:                    # eldste avsluttede ryker først
        rader = sorted(rader, key=lambda u: (u.get("slutt_dato") or "9999"), reverse=True)[:MAKS_RADER]

    return rader, ([] if forste_kjoring else nye)


# ────────────────────────── bilder ──────────────────────────

def ordne_bilder(rader: list[dict], utmappe: str, parallelle: int = 8) -> int:
    """Laster ned og skalerer bildene som skal vises, én gang per adresse."""
    vindu = (date.today() - timedelta(days=BILDE_VINDU)).isoformat()
    trengs = [r for r in rader
              if r.get("bilde", "").startswith("http")
              and (r.get("slutt_dato") or "9999") >= vindu]
    os.makedirs(BILDECACHE, exist_ok=True)
    målmappe = os.path.join(utmappe, "bilder")
    os.makedirs(målmappe, exist_ok=True)

    adresser = sorted({r["bilde"] for r in trengs})

    def en(url):
        return url, bilder.hent_bilde(url, BILDECACHE)

    kart: dict[str, str] = {}
    with ThreadPoolExecutor(parallelle) as ex:
        for url, sti in ex.map(en, adresser):
            if sti:
                navn = bilder.filnavn(url)
                shutil.copyfile(sti, os.path.join(målmappe, navn))
                kart[url] = f"bilder/{navn}"

    for r in rader:
        url = r.get("bilde", "")
        r["bilde"] = kart.get(url, "") if url.startswith("http") else url
    return len(kart)


# ────────────────────────── varsling ──────────────────────────

def si_fra(nye: list[dict], emne: str | None, side_url: str) -> None:
    if not nye or not emne:
        return
    gallerier = sorted({n["galleri"] for n in nye})
    if len(nye) == 1:
        tittel = f"Ny utstilling: {gallerier[0]}"
        tekst = f"{nye[0]['tittel']}\n{nye[0].get('kunstnere') or ''}".strip()
    else:
        tittel = f"{len(nye)} nye utstillinger i Oslo"
        tekst = "\n".join(f"· {n['galleri']}: {n['tittel']}" for n in nye[:6])
        if len(nye) > 6:
            tekst += f"\n… og {len(nye) - 6} til"
    try:
        r = requests.post(
            f"https://ntfy.sh/{emne}",
            data=tekst.encode("utf-8"),
            headers={"Title": tittel.encode("utf-8"), "Tags": "art",
                     "Click": side_url, "Priority": "default"},
            timeout=20)
        print(f"  ntfy: {r.status_code}")
    except Exception as e:                # noqa: BLE001 – varsling er ekstrautstyr
        print(f"  ntfy feilet: {type(e).__name__}: {e}")


# ────────────────────────── selve byggingen ──────────────────────────

def bygg(utmappe: str, forrige_peker: str | None, side_url: str, emne: str | None) -> dict:
    print(f"Bygger Galleriradar → {utmappe}")
    forrige = les_forrige(forrige_peker)
    ferske, status = hent_alt()
    rader, nye = flett(ferske, forrige, status)

    os.makedirs(utmappe, exist_ok=True)
    for navn in os.listdir(FRONT):
        kilde = os.path.join(FRONT, navn)
        mål = os.path.join(utmappe, navn)
        if os.path.isdir(kilde):
            shutil.copytree(kilde, mål, dirs_exist_ok=True)
        else:
            shutil.copyfile(kilde, mål)

    antall_bilder = ordne_bilder(rader, utmappe)

    for r in rader:
        r["periode"] = periodetekst(r.get("start_dato"), r.get("slutt_dato"),
                                    r.get("dato_tekst") or "")

    from kilder import REGIONER
    data = {
        "bygget": _na(),
        "regioner": REGIONER,
        "i_dag": date.today().isoformat(),
        "antall": len(rader),
        "nye": [n["nokkel"] for n in nye],
        "kilder": status,
        "utstillinger": rader,
    }
    with open(os.path.join(utmappe, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    bilder.rydd(4000, BILDECACHE)
    si_fra(nye, emne, side_url)

    print(f"Ferdig: {len(rader)} utstillinger, {antall_bilder} bilder, {len(nye)} nye")
    return data


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Bygger den statiske Galleriradaren")
    p.add_argument("--ut", default="_side", help="mappa siden bygges til")
    p.add_argument("--forrige", default=os.environ.get("FORRIGE_DATA"),
                   help="adresse eller sti til forrige data.json")
    p.add_argument("--url", default=os.environ.get("SIDE_URL", "http://localhost:8140/"),
                   help="adressen siden ligger på (brukes i varselet)")
    p.add_argument("--ntfy", default=os.environ.get("NTFY_EMNE"), help="ntfy-kanal for varsler")
    a = p.parse_args()
    d = bygg(a.ut, a.forrige, a.url, a.ntfy)
    sys.exit(0 if d["antall"] else 1)
