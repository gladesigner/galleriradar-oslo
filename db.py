"""Lagring: én rad per utstilling, med historikk over når den dukket opp.

Basen ligger i data/galleri.db. Den er liten nok til at SQLite holder, og
holdes åpen én tilkobling per tråd.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import date, datetime

MAPPE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STI = os.path.join(MAPPE, "galleri.db")
_lokal = threading.local()

SKJEMA = """
CREATE TABLE IF NOT EXISTS utstilling (
    nokkel      TEXT PRIMARY KEY,
    kilde_id    TEXT NOT NULL,
    galleri     TEXT NOT NULL,
    kategori    TEXT,
    bydel       TEXT,
    tittel      TEXT NOT NULL,
    kunstnere   TEXT,
    dato_tekst  TEXT,
    start_dato  TEXT,
    slutt_dato  TEXT,
    url         TEXT,
    bilde       TEXT,
    sammendrag  TEXT,
    type        TEXT,
    forste_gang TEXT NOT NULL,
    sist_sett   TEXT NOT NULL,
    endret      TEXT,
    borte       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS i_utstilling_start ON utstilling (start_dato);
CREATE INDEX IF NOT EXISTS i_utstilling_slutt ON utstilling (slutt_dato);
CREATE INDEX IF NOT EXISTS i_utstilling_ny    ON utstilling (forste_gang);

CREATE TABLE IF NOT EXISTS innhosting (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    kilde_id TEXT NOT NULL,
    tid      TEXT NOT NULL,
    antall   INTEGER NOT NULL DEFAULT 0,
    nye      INTEGER NOT NULL DEFAULT 0,
    sekunder REAL,
    feil     TEXT
);
CREATE INDEX IF NOT EXISTS i_innhosting_tid ON innhosting (tid);

CREATE TABLE IF NOT EXISTS merket (
    nokkel TEXT PRIMARY KEY,
    tid    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS innstilling (
    nokkel TEXT PRIMARY KEY,
    verdi  TEXT
);
"""


def kobling() -> sqlite3.Connection:
    if not getattr(_lokal, "k", None):
        os.makedirs(MAPPE, exist_ok=True)
        k = sqlite3.connect(STI, timeout=30, check_same_thread=False)
        k.row_factory = sqlite3.Row
        k.execute("PRAGMA journal_mode=WAL")
        k.executescript(SKJEMA)
        _lokal.k = k
    return _lokal.k


def na() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ────────────────────────── skriving ──────────────────────────

FELT_SOM_TELLER = ("tittel", "kunstnere", "dato_tekst", "start_dato", "slutt_dato",
                   "bilde", "sammendrag")


def lagre_treff(rader: list[dict]) -> list[dict]:
    """Legger inn nye utstillinger og oppdaterer kjente. Returnerer de nye."""
    k = kobling()
    tid = na()
    nye = []
    for r in rader:
        gammel = k.execute("SELECT * FROM utstilling WHERE nokkel=?", (r["nokkel"],)).fetchone()
        if gammel is None:
            k.execute("""INSERT INTO utstilling
                (nokkel, kilde_id, galleri, kategori, bydel, tittel, kunstnere, dato_tekst,
                 start_dato, slutt_dato, url, bilde, sammendrag, type,
                 forste_gang, sist_sett, endret, borte)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                      (r["nokkel"], r["kilde_id"], r["galleri"], r["kategori"], r["bydel"],
                       r["tittel"], r["kunstnere"], r["dato_tekst"], r["start_dato"],
                       r["slutt_dato"], r["url"], r["bilde"], r["sammendrag"], r["type"],
                       tid, tid, tid))
            nye.append(r)
        else:
            endret = any((gammel[f] or "") != (r.get(f) or "") for f in FELT_SOM_TELLER)
            k.execute("""UPDATE utstilling SET galleri=?, kategori=?, bydel=?, tittel=?,
                         kunstnere=?, dato_tekst=?, start_dato=?, slutt_dato=?, url=?,
                         bilde=COALESCE(NULLIF(?,''), bilde), sammendrag=?, type=?,
                         sist_sett=?, endret=?, borte=0 WHERE nokkel=?""",
                      (r["galleri"], r["kategori"], r["bydel"], r["tittel"], r["kunstnere"],
                       r["dato_tekst"], r["start_dato"], r["slutt_dato"], r["url"],
                       r["bilde"], r["sammendrag"], r["type"], tid,
                       tid if endret else gammel["endret"], r["nokkel"]))
    k.commit()
    return nye


def logg_innhosting(kilde_id: str, antall: int, nye: int, sekunder: float, feil: str | None) -> None:
    k = kobling()
    k.execute("INSERT INTO innhosting (kilde_id, tid, antall, nye, sekunder, feil) VALUES (?,?,?,?,?,?)",
              (kilde_id, na(), antall, nye, round(sekunder, 1), feil))
    k.execute("""DELETE FROM innhosting WHERE id NOT IN
                 (SELECT id FROM innhosting ORDER BY id DESC LIMIT 2000)""")
    k.commit()


def merk_borte(kilde_id: str, tid_for: str) -> None:
    """Utstillinger kilden ikke nevner lenger regnes som avsluttet."""
    k = kobling()
    k.execute("UPDATE utstilling SET borte=1 WHERE kilde_id=? AND sist_sett < ?", (kilde_id, tid_for))
    k.commit()


# ────────────────────────── lesing ──────────────────────────

def _rad(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["merket"] = bool(d.pop("er_merket", 0))
    return d


def hent(visning: str = "aktuelt", galleri: str = "", kategori: str = "",
         sok: str = "", grense: int = 400) -> list[dict]:
    k = kobling()
    i_dag = date.today().isoformat()
    hvor = ["1=1"]
    arg: list = []

    if visning == "aktuelt":
        hvor.append("(slutt_dato IS NULL OR slutt_dato >= ?)")
        arg.append(i_dag)
        hvor.append("(start_dato IS NULL OR start_dato <= ?)")
        arg.append(i_dag)
        hvor.append("borte = 0")
    elif visning == "kommer":
        hvor.append("start_dato > ?")
        arg.append(i_dag)
    elif visning == "nytt":
        hvor.append("(slutt_dato IS NULL OR slutt_dato >= ?)")
        arg.append(i_dag)
    elif visning == "merket":
        hvor.append("u.nokkel IN (SELECT nokkel FROM merket)")
    elif visning == "tidligere":
        hvor.append("slutt_dato < ?")
        arg.append(i_dag)

    if galleri:
        hvor.append("kilde_id = ?")
        arg.append(galleri)
    if kategori:
        hvor.append("kategori = ?")
        arg.append(kategori)
    if sok:
        hvor.append("(tittel LIKE ? OR kunstnere LIKE ? OR galleri LIKE ? OR sammendrag LIKE ?)")
        arg += [f"%{sok}%"] * 4

    if visning == "kommer":
        sortering = "start_dato ASC"
    elif visning == "nytt":
        sortering = "forste_gang DESC"
    elif visning == "tidligere":
        sortering = "slutt_dato DESC"
    else:
        sortering = "CASE WHEN slutt_dato IS NULL THEN 1 ELSE 0 END, slutt_dato ASC"

    rader = k.execute(f"""
        SELECT u.*, (SELECT 1 FROM merket m WHERE m.nokkel = u.nokkel) AS er_merket
        FROM utstilling u WHERE {' AND '.join(hvor)}
        ORDER BY {sortering} LIMIT ?""", (*arg, grense)).fetchall()
    return [_rad(r) for r in rader]


def tall() -> dict:
    k = kobling()
    i_dag = date.today().isoformat()
    def n(sp, *a):
        return k.execute(sp, a).fetchone()[0]
    return {
        "aktuelt": n("""SELECT COUNT(*) FROM utstilling WHERE borte=0
                        AND (slutt_dato IS NULL OR slutt_dato >= ?)
                        AND (start_dato IS NULL OR start_dato <= ?)""", i_dag, i_dag),
        "kommer": n("SELECT COUNT(*) FROM utstilling WHERE start_dato > ?", i_dag),
        "merket": n("SELECT COUNT(*) FROM merket"),
        "totalt": n("SELECT COUNT(*) FROM utstilling"),
        "gallerier": n("SELECT COUNT(DISTINCT kilde_id) FROM utstilling"),
    }


def nye_siden(tidspunkt: str) -> list[dict]:
    k = kobling()
    i_dag = date.today().isoformat()
    rader = k.execute("""SELECT * FROM utstilling
                         WHERE forste_gang > ? AND (slutt_dato IS NULL OR slutt_dato >= ?)
                         ORDER BY forste_gang DESC""", (tidspunkt, i_dag)).fetchall()
    return [dict(r) for r in rader]


def gallerier() -> list[dict]:
    k = kobling()
    rader = k.execute("""SELECT kilde_id, galleri, kategori, COUNT(*) AS antall
                         FROM utstilling GROUP BY kilde_id ORDER BY galleri""").fetchall()
    return [dict(r) for r in rader]


def kildestatus() -> list[dict]:
    """Siste innhøsting per kilde – grunnlaget for helsesiden."""
    k = kobling()
    rader = k.execute("""
        SELECT i.* FROM innhosting i
        JOIN (SELECT kilde_id, MAX(id) AS siste FROM innhosting GROUP BY kilde_id) s
          ON i.id = s.siste ORDER BY i.kilde_id""").fetchall()
    return [dict(r) for r in rader]


# ────────────────────────── småting ──────────────────────────

def sett_innstilling(nokkel: str, verdi) -> None:
    k = kobling()
    k.execute("INSERT OR REPLACE INTO innstilling VALUES (?,?)", (nokkel, json.dumps(verdi)))
    k.commit()


def innstilling(nokkel: str, standard=None):
    r = kobling().execute("SELECT verdi FROM innstilling WHERE nokkel=?", (nokkel,)).fetchone()
    return json.loads(r["verdi"]) if r else standard


def merk(nokkel: str, pa: bool) -> None:
    k = kobling()
    if pa:
        k.execute("INSERT OR REPLACE INTO merket VALUES (?,?)", (nokkel, na()))
    else:
        k.execute("DELETE FROM merket WHERE nokkel=?", (nokkel,))
    k.commit()
