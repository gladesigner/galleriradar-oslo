"""Tolker norske (og engelske) datoer og datointervaller fra fritekst.

Gallerisidene skriver datoer på alle tenkelige måter: «13. aug – 19. sep»,
«02. jan. 2026 – 31.12.2026», «Fra 5. september», «12.09.26», «2026-09-12».
Her gjøres alt om til (start, slutt) som ISO-datoer, eller None der det mangler.
"""
from __future__ import annotations

import re
from datetime import date

MANEDER = {
    "januar": 1, "jan": 1, "january": 1,
    "februar": 2, "feb": 2, "february": 2,
    "mars": 3, "mar": 3, "march": 3,
    "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juni": 6, "jun": 6, "june": 6,
    "juli": 7, "jul": 7, "july": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "okt": 10, "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "desember": 12, "des": 12, "december": 12, "dec": 12,
}

MANED_NAVN = ["januar", "februar", "mars", "april", "mai", "juni",
              "juli", "august", "september", "oktober", "november", "desember"]

# «13. aug 2026», «13 september», «13. sept. 2026»
_RE_DMY_TEKST = re.compile(
    r"(?<!\d)(\d{1,2})\.?\s*(" + "|".join(sorted(MANEDER, key=len, reverse=True)) + r")\.?"
    r"(?:\s*,?\s*(\d{4}))?", re.IGNORECASE)
# «10.–20. september 2026» – to dager som deler månedsnavn
_RE_DAG_DAG_MND = re.compile(
    r"(?<!\d)(\d{1,2})\.?\s*[-–—]\s*(\d{1,2})\.?\s*("
    + "|".join(sorted(MANEDER, key=len, reverse=True)) + r")\.?(?:\s*,?\s*(\d{4}))?",
    re.IGNORECASE)
# «August 13, 2026» – engelsk rekkefølge
_RE_MDY_TEKST = re.compile(
    r"\b(" + "|".join(sorted(MANEDER, key=len, reverse=True)) + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*,?\s*(\d{4}))?\b", re.IGNORECASE)
# «september 2026» uten dag
_RE_MY_TEKST = re.compile(
    r"\b(" + "|".join(sorted(MANEDER, key=len, reverse=True)) + r")\.?\s+(\d{4})\b", re.IGNORECASE)
# «12.09.2026», «12/9-26»
_RE_DMY_TALL = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?(?!\d)")
# ISO
_RE_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")

# Ordene må ha ordgrenser. Uten dem deler «to» ordet «ok-to-ber» i to, og
# hele datoen faller fra hverandre.
SKILLETEGN = re.compile(
    r"\s*(?:–|—|−|-{1,2}|\b(?:til og med|t\.?o\.?m\.?|til|through|until|to)\b)\s*",
    re.IGNORECASE)
_RE_APEN_START = re.compile(r"^\s*(?:fra og med|fra|f\.?o\.?m\.?|åpner|opens|from)\b", re.IGNORECASE)
_RE_APEN_SLUTT = re.compile(
    r"^\s*(?:til og med|til|t\.?o\.?m\.?|fram til|frem til|until|through|ends)\b"
    r"|\b(?:vises til|varer til|står til|st\u00e5r til|open until|on view until|ends)\b",
    re.IGNORECASE)

PERMANENT = re.compile(r"\b(permanent|fast utstilling|løpende|pågående|ongoing|the collection)\b", re.IGNORECASE)


def _lag_dato(d: int, m: int, a: int | None, hint_ar: int | None = None) -> date | None:
    if not (1 <= m <= 12):
        return None
    if a is None:
        a = hint_ar if hint_ar else date.today().year
    if a < 100:
        a += 2000
    try:
        return date(a, m, min(d, 31))
    except ValueError:
        return None


def _finn_datoer(tekst: str, hint_ar: int | None = None) -> list[date]:
    """Alle datoer i teksten, i rekkefølgen de står."""
    funn: list[tuple[int, date]] = []
    for m in _RE_ISO.finditer(tekst):
        d = _lag_dato(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d:
            funn.append((m.start(), d))
    brukt = {(p, p + 10) for p, _ in funn}

    def overlapper(start: int) -> bool:
        return any(a <= start < b for a, b in brukt)

    for m in _RE_DMY_TEKST.finditer(tekst):
        if overlapper(m.start()):
            continue
        mnd = MANEDER[m.group(2).lower().rstrip(".")]
        ar = int(m.group(3)) if m.group(3) else None
        d = _lag_dato(int(m.group(1)), mnd, ar, hint_ar)
        if d:
            funn.append((m.start(), d))
            brukt.add((m.start(), m.end()))
    for m in _RE_MDY_TEKST.finditer(tekst):
        if overlapper(m.start()):
            continue
        mnd = MANEDER[m.group(1).lower().rstrip(".")]
        ar = int(m.group(3)) if m.group(3) else None
        d = _lag_dato(int(m.group(2)), mnd, ar, hint_ar)
        if d:
            funn.append((m.start(), d))
            brukt.add((m.start(), m.end()))
    for m in _RE_DMY_TALL.finditer(tekst):
        if overlapper(m.start()):
            continue
        ar = int(m.group(3)) if m.group(3) else None
        d = _lag_dato(int(m.group(1)), int(m.group(2)), ar, hint_ar)
        if d:
            funn.append((m.start(), d))
            brukt.add((m.start(), m.end()))
    if not funn:
        for m in _RE_MY_TEKST.finditer(tekst):
            d = _lag_dato(1, MANEDER[m.group(1).lower().rstrip(".")], int(m.group(2)))
            if d:
                funn.append((m.start(), d))
    funn.sort(key=lambda t: t[0])
    return [d for _, d in funn]


def tolk_periode(tekst: str | None, hint_ar: int | None = None) -> tuple[str | None, str | None]:
    """Returnerer (start_iso, slutt_iso). Begge kan være None.

    hint_ar brukes når teksten mangler årstall – typisk «14.08 – 03.10» under
    en overskrift som sier hvilket år raden gjelder.
    """
    if not tekst:
        return None, None
    t = re.sub(r"\s+", " ", str(tekst)).strip()
    raa = t                       # før klokkeslettene fjernes
    # klokkeslett ser ut som datoer for en maskin – «kl. 21:15-02:00» må bort først
    t = re.sub(r"\bkl\.?\s*\d{1,2}[:.]\d{2}(?:\s*[-–—]\s*\d{1,2}[:.]\d{2})?", " ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b\d{1,2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}\b", " ", t)
    # NB: strekene må stå. En hale som «27.05.2025 —» er nettopp det som
    # skiller en pågående utstilling fra en som varte én dag.
    t = re.sub(r"\s+", " ", t).strip(" ,")
    if not t:
        return None, None

    apen_start = bool(_RE_APEN_START.match(t))
    apen_hode = bool(re.match(r"^\s*[–—−-]\s*\d", t))   # «— 19.09» = startet før
    apen_slutt = bool(_RE_APEN_SLUTT.search(t))
    # «27.05.2025 —» betyr at utstillingen går videre. Streken må stå i
    # originalteksten – ellers er det bare en rest etter et fjernet klokkeslett.
    apen_hale = bool(re.search(r"[–—−-]\s*$", raa))

    # «10.–20. september»: begge dagene hører til samme måned, og en vanlig
    # deling på streken ville mistet den første.
    m = _RE_DAG_DAG_MND.search(t)
    if m:
        mnd = MANEDER[m.group(3).lower().rstrip(".")]
        ar = int(m.group(4)) if m.group(4) else None
        a = _lag_dato(int(m.group(1)), mnd, ar, hint_ar)
        b = _lag_dato(int(m.group(2)), mnd, ar, hint_ar)
        if a and b and a <= b:
            return a.isoformat(), b.isoformat()

    # Del på skilletegn, men bare når det faktisk skiller to datoer
    deler = SKILLETEGN.split(t)
    deler = [d for d in deler if d.strip()]

    if len(deler) >= 2:
        hale = _finn_datoer(deler[-1], hint_ar=hint_ar)
        hint = hale[0].year if hale else hint_ar
        hode = _finn_datoer(" ".join(deler[:-1]), hint_ar=hint)
        if hode and hale:
            start, slutt = hode[0], hale[-1]
            if slutt < start:
                # Årsskifte. Står årstallet bare bakerst – «25. november –
                # 09. januar 2022» – hører starten til året før slutten.
                # Ellers er det slutten som skal et år fram: «13. nov – 28. feb».
                ar_bak = bool(re.search(r"\b(20\d{2})\b", deler[-1]))
                ar_foran = bool(re.search(r"\b(20\d{2})\b", " ".join(deler[:-1])))
                try:
                    if ar_bak and not ar_foran:
                        start = start.replace(year=start.year - 1)
                    else:
                        slutt = slutt.replace(year=slutt.year + 1)
                except ValueError:
                    pass
            return start.isoformat(), slutt.isoformat()

    datoer = _finn_datoer(t, hint_ar=hint_ar)
    if not datoer:
        return None, None
    if len(datoer) == 1:
        d = datoer[0].isoformat()
        if apen_hode or (apen_slutt and not apen_hale):
            return None, d
        if apen_start or apen_hale:
            return d, None
        return d, d
    return datoer[0].isoformat(), datoer[-1].isoformat()


def datostart(tekst: str | None) -> int | None:
    """Posisjonen der datodelen av en tekst begynner, om den finnes."""
    if not tekst:
        return None
    treff = [m.start() for m in (_RE_ISO.search(tekst), _RE_DMY_TEKST.search(tekst),
                                 _RE_MDY_TEKST.search(tekst), _RE_DMY_TALL.search(tekst))
             if m]
    return min(treff) if treff else None


def er_permanent(tekst: str | None) -> bool:
    return bool(tekst and PERMANENT.search(tekst))


def norsk_dato(iso: str | None) -> str:
    """2026-09-12 -> 12. september 2026"""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day}. {MANED_NAVN[d.month - 1]} {d.year}"


def kort_dato(iso: str | None) -> str:
    """2026-09-12 -> 12. sep."""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day}. {MANED_NAVN[d.month - 1][:3]}."


def periodetekst(start: str | None, slutt: str | None, fallback: str = "") -> str:
    if start and slutt:
        if start == slutt:
            return norsk_dato(start)
        s = date.fromisoformat(start)
        e = date.fromisoformat(slutt)
        if s.year == e.year:
            return f"{kort_dato(start)} – {norsk_dato(slutt)}"
        return f"{norsk_dato(start)} – {norsk_dato(slutt)}"
    if slutt:
        return f"Til {norsk_dato(slutt)}"
    if start:
        return f"Fra {norsk_dato(start)}"
    return fallback
