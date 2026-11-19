#!/bin/sh
cd "$(dirname "$0")"
[ -d /opt/homebrew/lib ] && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
(sleep 2; command -v open >/dev/null && open http://127.0.0.1:5055 || xdg-open http://127.0.0.1:5055) &
.venv/bin/python app.py
