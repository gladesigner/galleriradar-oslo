#!/usr/bin/env bash
# Starter Galleriradaren. Port kan overstyres:  PORT=8141 ./start.sh
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python app.py
