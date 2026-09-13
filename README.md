# Galleriradar Oslo

Samler utstillinger og arrangementer fra gallerier, kunsthaller og museer i Oslo.
Innhøstingen kjøres av GitHub Actions hver fjerde time, siden publiseres på GitHub
Pages, og varsler går til telefonen via ntfy. Ingen tjener å passe på, og ingen
maskin som må stå på hjemme.

## Slik henger det sammen

    GitHub Actions (hver 4. time)
        └── bygg.py ── kilder.py + hent.py ──> galleriens nettsider
                    ├── data.json          (hele listen, med bilder)
                    ├── ntfy.sh            (varsel til telefonene)
                    └── GitHub Pages       (selve appen)

| Fil | Rolle |
| --- | --- |
| `kilder.py` | Ett oppslag per visningssted – nettadresse og CSS-velgere |
| `hent.py` | Innhøstingsmotoren. Fire adaptertyper: `css`, `jsonld`, `wp`, `funk` |
| `egne.py` | Kilder som trenger egen kode (Nasjonalmuseet hentes fra sitemap) |
| `datotolk.py` | Tolker «13. aug – 19. sep», «August 13, 2026», «Vises til 11.10.2026» |
| `bilder.py` | Skalerer gallerienes bilder ned før de legges på siden |
| `bygg.py` | Bygger hele siden: henter, fletter, skriver `data.json`, varsler |
| `front/` | Selve appen – ren HTML, CSS og JavaScript, ingen rammeverk |
| `.github/workflows/hent.yml` | Jobben som kjører det hele |

Det finnes ingen database. **Forrige publiserte `data.json` er hukommelsen**:
hver kjøring leser den fra den publiserte siden, og beholder `forste_gang` for alt
som allerede var kjent. Det som ikke fantes der fra før, er nytt.

Avsluttede utstillinger blir liggende i to år, slik at «Tidligere» har innhold,
med et tak på 1500 rader.

## Varsling

Jobben legger en melding på en ntfy-kanal når noe nytt dukker opp. Kanalnavnet
ligger i repo-hemmeligheten `NTFY_EMNE` – aldri i koden, for hvem som helst kan
lese en kanal de kjenner navnet på.

På telefonen: installer **ntfy** fra App Store, trykk +, skriv inn samme
kanalnavn. Ferdig – da kommer varslene som vanlige push-varsler.

Første kjøring varsler ikke. Da ville hele listen ha lyst opp som ny.

## På iPhone

1. Åpne Pages-adressen i Safari
2. Del-knappen → **Legg til på Hjem-skjerm**

Da får appen eget ikon, starter i fullskjerm, og husker listen slik at den virker
også uten dekning. Hver telefon husker selv når den sist så listen, så «NY» blir
riktig for begge to uavhengig av hverandre. Stjernemerkene ligger også lokalt på
hver telefon.

## Sju dager om gangen

Den native appen signeres med gratis utviklerkonto, og en slik signatur varer
bare sju dager. `ios/forny.sh` gjør det om til noe ingen trenger å huske:

```
./ios/forny.sh            # vanlig runde – signerer det som nærmer seg utløp
./ios/forny.sh --tving    # signer på nytt uansett
./ios/forny.sh --status   # hvem ble sist fornyet, og hvor lenge den varer
```

`~/Library/LaunchAgents/no.gladesigner.galleriradar.forny.plist` kjører den
03.30 hver natt. Jobben leter etter telefonene på nettet, hopper over dem som
ikke er der, og bygger bare når det faktisk trengs – på femte dag, med to dagers
margin. Installasjonen skriver over den gamle appen, så Min liste og
kildevalgene står. Logg: `~/Library/Application Support/Galleriradar/forny.log`.

Nye telefoner legges til i `TELEFONER` øverst i skriptet, med navnet slik
`xcrun devicectl list devices` skriver det.

## Kjøre lokalt

    .venv/bin/python -m pip install -r krav.txt
    ./start.sh                  # bygger og serverer på http://localhost:8140/
    ./start.sh --bare-server    # hopper over innhøstingen

## Legge til et galleri

Skriv et nytt oppslag i `kilder.py` og prøv det alene:

    .venv/bin/python hent.py <id>

Motoren tar seg av datoer, bilder, avduplisering og detaljsider. `krev_dato: True`
kaster alt som ikke har en dato – nyttig mot menylenker og annen støy.

## Når et galleri legger om nettsiden

`kilder.html` på den publiserte siden viser siste innhøsting per sted. Står det
«ingen treff» over tid, er velgeren i `kilder.py` utdatert og må justeres.

## Steder som ikke lar seg høste ennå

Peder Lund, Mesén, Tenthaus, PRAKSIS, RAM galleri, Kunstverket, Buer Gallery,
Destiny's Atelier og VI, VII bygger listene sine i nettleseren, og gir ingenting
fra seg til en vanlig innhøster. De må enten hentes med en hodeløs nettleser eller
vente på at nettsidene endrer seg.
