"""Bildemellomtjener.

Gallerienes egne bilder er ofte flere megabyte store. Her hentes de én gang,
skaleres til noe en telefon kan leve med, og legges i data/bilder/.
"""
from __future__ import annotations

import hashlib
import io
import os

import requests
from PIL import Image, ImageOps

from hent import HODER

MAPPE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "bilder")
BREDDE = 900
MAKS_NED = 12 * 1024 * 1024


def filnavn(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest() + ".jpg"


def _sti(url: str, mappe: str | None = None) -> str:
    return os.path.join(mappe or MAPPE, filnavn(url))


def hent_bilde(url: str, mappe: str | None = None) -> str | None:
    """Returnerer stien til et nedskalert bilde, eller None om det ikke går."""
    if not url.startswith(("http://", "https://")):
        return None
    mappe = mappe or MAPPE
    sti = _sti(url, mappe)
    if os.path.exists(sti) and os.path.getsize(sti) > 0:
        return sti
    os.makedirs(mappe, exist_ok=True)
    try:
        r = requests.get(url, headers=HODER, timeout=20, stream=True)
        r.raise_for_status()
        raa = r.raw.read(MAKS_NED + 1, decode_content=True)
        if len(raa) > MAKS_NED:
            return None
        bilde = Image.open(io.BytesIO(raa))
        bilde = ImageOps.exif_transpose(bilde)
        if bilde.mode not in ("RGB", "L"):
            bilde = bilde.convert("RGB")
        if bilde.width > BREDDE:
            h = round(bilde.height * BREDDE / bilde.width)
            bilde = bilde.resize((BREDDE, h), Image.LANCZOS)
        bilde.save(sti, "JPEG", quality=82, optimize=True, progressive=True)
        return sti
    except Exception:                     # noqa: BLE001 – manglende bilde er ikke kritisk
        if os.path.exists(sti) and os.path.getsize(sti) == 0:
            os.remove(sti)
        return None


def rydd(maks_filer: int = 3000, mappe: str | None = None) -> int:
    """Sletter de eldste bildene når mappa vokser seg for stor."""
    MAPPE_ = mappe or MAPPE
    if not os.path.isdir(MAPPE_):
        return 0
    filer = [(os.path.getmtime(os.path.join(MAPPE_, f)), f) for f in os.listdir(MAPPE_)]
    if len(filer) <= maks_filer:
        return 0
    filer.sort()
    for _, f in filer[: len(filer) - maks_filer]:
        try:
            os.remove(os.path.join(MAPPE_, f))
        except OSError:
            pass
    return len(filer) - maks_filer
