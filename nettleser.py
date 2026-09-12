"""Henter sider som bygger innholdet sitt i nettleseren.

Noen gallerier leverer en tom side til en vanlig innhøster – all utstillings-
listen settes sammen av JavaScript etterpå. Da må siden faktisk kjøres. Det
koster tid, så det brukes bare på kildene som er merket med «js».

Nettleseren startes én gang og gjenbrukes, og lukkes når prosessen er ferdig.
"""
from __future__ import annotations

import atexit
import threading

_laas = threading.Lock()
_spiller = None
_nettleser = None

HODER = {
    "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
}


def _start():
    global _spiller, _nettleser
    if _nettleser is not None:
        return _nettleser
    from playwright.sync_api import sync_playwright
    _spiller = sync_playwright().start()
    _nettleser = _spiller.chromium.launch(args=["--disable-dev-shm-usage"])
    atexit.register(lukk)
    return _nettleser


def lukk() -> None:
    global _spiller, _nettleser
    try:
        if _nettleser is not None:
            _nettleser.close()
        if _spiller is not None:
            _spiller.stop()
    except Exception:                    # noqa: BLE001 – opprydding skal ikke velte noe
        pass
    _nettleser = _spiller = None


def hent_html(url: str, vent_paa: str | None = None, tidsavbrudd: int = 25000) -> tuple[str, str]:
    """Returnerer (html, endelig adresse) etter at siden har kjørt ferdig."""
    with _laas:                          # Playwrights sync-API tåler bare én tråd
        nettleser = _start()
        side = nettleser.new_page(extra_http_headers=HODER, locale="nb-NO",
                                  viewport={"width": 1280, "height": 1600})
        try:
            side.goto(url, wait_until="domcontentloaded", timeout=tidsavbrudd)
            if vent_paa:
                try:
                    side.wait_for_selector(vent_paa, timeout=8000)
                except Exception:        # noqa: BLE001 – vi tar det vi har
                    pass
            else:
                side.wait_for_timeout(1800)
            # rull litt, så det som lastes ved scrolling blir med
            side.mouse.wheel(0, 2500)
            side.wait_for_timeout(700)
            return side.content(), side.url
        finally:
            side.close()
