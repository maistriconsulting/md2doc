#!/bin/sh
cd "$(dirname "$0")"
[ -d /opt/homebrew/lib ] && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
if [ ! -d .venv ]; then
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then PY="$c"; break; fi
  done
  [ -n "$PY" ] || { echo "Serve Python 3.10 o superiore."; exit 1; }
  "$PY" -m venv .venv && .venv/bin/pip install -r requirements.txt || exit 1
fi
(sleep 2; command -v open >/dev/null && open http://127.0.0.1:5055 || xdg-open http://127.0.0.1:5055) &
.venv/bin/python app.py
