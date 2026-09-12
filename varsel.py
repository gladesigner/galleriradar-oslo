"""Systemvarsler på macOS.

Bruker terminal-notifier om den finnes (da kan varselet klikkes og åpne appen),
ellers osascript, som alltid er der. Feiler stille – et varsel som ikke kommer
fram skal aldri velte en innhøsting.
"""
from __future__ import annotations

import shutil
import subprocess


def _rens(s: str) -> str:
    return (s or "").replace('"', "'").replace("\\", "")[:220]


def varsle(tittel: str, undertittel: str, tekst: str, url: str | None = None) -> bool:
    tn = shutil.which("terminal-notifier")
    try:
        if tn:
            kmd = [tn, "-title", _rens(tittel), "-subtitle", _rens(undertittel),
                   "-message", _rens(tekst), "-group", "nb-galleri", "-sound", "Glass"]
            if url:
                kmd += ["-open", url]
            subprocess.run(kmd, timeout=10, capture_output=True, check=False)
        else:
            skript = (f'display notification "{_rens(tekst)}" '
                      f'with title "{_rens(tittel)}" subtitle "{_rens(undertittel)}" '
                      f'sound name "Glass"')
            subprocess.run(["osascript", "-e", skript], timeout=10, capture_output=True, check=False)
        return True
    except Exception:                     # noqa: BLE001 – varsling er ekstrautstyr
        return False


def varsle_om_nye(nye: list[dict], app_url: str) -> bool:
    if not nye:
        return False
    if len(nye) == 1:
        n = nye[0]
        return varsle("Ny utstilling", n["galleri"], n["tittel"], app_url)
    gallerier = sorted({n["galleri"] for n in nye})
    smakebit = ", ".join(gallerier[:3]) + (" m.fl." if len(gallerier) > 3 else "")
    return varsle(f"{len(nye)} nye utstillinger", smakebit,
                  " · ".join(n["tittel"] for n in nye[:4]), app_url)
