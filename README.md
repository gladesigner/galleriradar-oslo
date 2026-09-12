# Galleriradar Oslo

Samler utstillinger og arrangementer fra gallerier, kunsthaller og museer i Oslo,
holder seg selv oppdatert, og sier fra når noe nytt dukker opp.

    ./start.sh                  # http://localhost:8140/

## Slik henger det sammen

| Fil | Rolle |
| --- | --- |
| `kilder.py` | Ett oppslag per visningssted – nettadresse og CSS-velgere |
| `hent.py` | Innhøstingsmotoren. Fire adaptertyper: `css`, `jsonld`, `wp`, `funk` |
| `egne.py` | Kilder som trenger egen kode (Nasjonalmuseet henter fra sitemap) |
| `datotolk.py` | Tolker «13. aug – 19. sep», «August 13, 2026», «Vises til 11.10.2026» |
| `db.py` | SQLite i `data/galleri.db` – én rad per utstilling, med historikk |
| `innhost.py` | Kjører alle kilder, lagrer, varsler |
| `varsel.py` | Systemvarsel på macOS |
| `bilder.py` | Skalerer gallerienes bilder ned før de sendes til telefonen |
| `app.py` | Flask-tjeneren og API-et |

## Oppdatering og varsling

Appen henter alle kilder hver 4. time så lenge den kjører (`NB_GALLERI_INTERVALL`
styrer intervallet), og med én gang du trykker på oppdater-knappen. Utstillinger
som ikke er sett før, blir merket **NY** og utløser et systemvarsel på Mac-en.

Første kjøring varsler ikke – da ville hele basen ha lyst opp som ny.

Hver telefon husker selv når den sist så listen (`localStorage`), så «NY» blir
riktig for begge to, uavhengig av hverandre.

### Alltid i gang

For at appen skal hente nytt også når du ikke har startet den manuelt:

    cp no.trondm.galleriradar.plist ~/Library/LaunchAgents/
    launchctl load ~/Library/LaunchAgents/no.trondm.galleriradar.plist

Stopp igjen med `launchctl unload ~/Library/LaunchAgents/no.trondm.galleriradar.plist`.

## På iPhone

Appen er en PWA og kan legges på hjem-skjermen:

1. Mac-en og telefonen må være på samme wifi. Finn maskinens adresse med
   `ipconfig getifaddr en0` – for eksempel `192.168.1.24`.
2. Åpne `http://192.168.1.24:8140/` i Safari på telefonen.
3. Del-knappen → **Legg til på Hjem-skjerm**. Da får den eget ikon, egen
   oppstartsside og ingen adresselinje.

Over vanlig `http://` på lokalnettet lar ikke Safari appen mellomlagre sidene
(servicearbeidere krever HTTPS eller localhost). Ikonet og fullskjermvisningen
virker likevel – det er bare offline-visningen som uteblir.

Utenfor hjemmenettet trengs en tunnel – Tailscale er det enkleste: installer det
på Mac-en og på begge telefonene, så nås appen på maskinens Tailscale-adresse
uansett hvor dere er.

## Legge til et galleri

Skriv et nytt oppslag i `kilder.py` og prøv det:

    .venv/bin/python hent.py <id>

Motoren tar seg av datoer, bilder, avduplisering og detaljsider. `krev_dato: True`
kaster alt som ikke har en dato – nyttig mot menylenker og annen støy.

## Når et galleri legger om nettsiden

`/kilder` viser siste innhøsting per sted. Står det «ingen treff» over tid, er
velgeren i `kilder.py` utdatert og må justeres.

## Steder som ikke lar seg høste ennå

Peder Lund, Mesén, Tenthaus, PRAKSIS, RAM galleri, Kunstverket, Buer Gallery,
Destiny's Atelier og VI, VII bygger listene sine i nettleseren (JavaScript), og gir
ingenting fra seg til en vanlig innhøster. De må enten hentes med en hodeløs
nettleser eller vente på at nettsidene endrer seg.
