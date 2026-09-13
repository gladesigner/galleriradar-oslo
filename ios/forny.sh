#!/usr/bin/env bash
# Holder Galleriradar levende på telefonene.
#
# Gratis utviklerkonto signerer bare for sju dager. Denne jobben kjører hver
# natt, ser etter telefonene på nettet, og installerer på nytt når signaturen
# nærmer seg slutten – eller når koden er endret siden sist. Installasjonen
# skriver over den gamle appen; listen og kildevalgene står.
#
#   ./forny.sh            vanlig runde
#   ./forny.sh --tving    installer på nytt selv om det ikke haster
#   ./forny.sh --status   hvem fikk sist en ny installasjon, og når
set -uo pipefail

TELEFONER=("Trondofon" "Marte")
DAGER=5                       # signeringen varer sju – vi tar den på femte
PROSJEKT="$HOME/nb-design-tokens/nb-galleri/ios"
STAT="$HOME/Library/Application Support/Galleriradar"
LOGG="$STAT/forny.log"
BYGG="$STAT/bygg"
APP="Build/Products/Debug-iphoneos/Galleriradar.app"
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"

mkdir -p "$STAT" "$BYGG"

si() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M')" "$*" >> "$LOGG"; }

if [[ "${1:-}" == "--status" ]]; then
  for navn in "${TELEFONER[@]}"; do
    merke="$STAT/sist-$navn"
    if [[ -f "$merke" ]]; then
      dager=$(( ($(date +%s) - $(stat -f %m "$merke")) / 86400 ))
      printf '%-12s fornyet %s (%d dager siden, utløper om %d)\n' \
        "$navn" "$(date -r "$merke" '+%d.%m kl. %H:%M')" "$dager" "$(( 7 - dager ))"
    else
      printf '%-12s aldri fornyet herfra\n' "$navn"
    fi
  done
  exit 0
fi

tving=0
[[ "${1:-}" == "--tving" ]] && tving=1

enheter=$(mktemp)
trap 'rm -f "$enheter"' EXIT
if ! xcrun devicectl list devices --json-output "$enheter" >/dev/null 2>&1; then
  si "fant ingen enheter – devicectl svarte ikke"
  exit 0
fi

for navn in "${TELEFONER[@]}"; do
  id=$(python3 - "$enheter" "$navn" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
for e in d.get("result", {}).get("devices", []):
    if e["deviceProperties"]["name"] == sys.argv[2]:
        print(e["identifier"]); break
PY
)
  if [[ -z "$id" ]]; then
    si "$navn: ikke paret med denne maskinen"
    continue
  fi

  merke="$STAT/sist-$navn"
  if [[ $tving -eq 0 && -f "$merke" ]]; then
    alder=$(( ($(date +%s) - $(stat -f %m "$merke")) / 86400 ))
    # Er koden endret siden sist, skal den ut selv om signaturen holder.
    # Ellers ville en ny versjon blitt liggende til signaturen løp ut.
    endret=$(find "$PROSJEKT" -name '*.swift' -o -name 'project.yml' \
             -o -name '*.png' 2>/dev/null | xargs -I{} find {} -newer "$merke" 2>/dev/null | head -1)
    if (( alder < DAGER )) && [[ -z "$endret" ]]; then
      continue                        # signaturen holder, og ingenting er nytt
    fi
  fi

  # En telefon som ligger i lomma et annet sted skal ikke koste et bygg.
  if ! xcrun devicectl device info details --device "$id" --timeout 25 >/dev/null 2>&1; then
    si "$navn: ikke på nett"
    continue
  fi

  if ! xcodebuild -project "$PROSJEKT/Galleriradar.xcodeproj" -scheme Galleriradar \
       -configuration Debug -destination "id=$id" -allowProvisioningUpdates \
       -derivedDataPath "$BYGG/$navn" build >/dev/null 2>&1; then
    si "$navn: bygget feilet"
    continue
  fi

  if xcrun devicectl device install app --device "$id" "$BYGG/$navn/$APP" >/dev/null 2>&1; then
    touch "$merke"
    si "$navn: fornyet"
  else
    si "$navn: installasjonen feilet"
  fi
done

# Loggen skal ikke vokse i det uendelige.
if [[ -f "$LOGG" ]] && (( $(wc -l < "$LOGG") > 2000 )); then
  tail -500 "$LOGG" > "$LOGG.ny" && mv "$LOGG.ny" "$LOGG"
fi
