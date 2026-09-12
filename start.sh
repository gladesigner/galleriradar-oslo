#!/usr/bin/env bash
# Bygger siden lokalt og serverer den på http://localhost:8140/
# Hopp over innhøstingen med:  ./start.sh --bare-server
cd "$(dirname "$0")" || exit 1
if [ "$1" != "--bare-server" ]; then
  .venv/bin/python bygg.py --ut _side --forrige _side/data.json || exit 1
fi
echo "Galleriradar på http://localhost:8140/"
exec .venv/bin/python -m http.server 8140 --directory _side --bind 0.0.0.0
