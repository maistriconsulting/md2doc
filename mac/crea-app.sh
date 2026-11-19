#!/bin/sh
# Crea "MD in documento.app" in ~/Applications, collegata a questa cartella.
# Uso:  ./mac/crea-app.sh
# Se sposti la cartella del progetto, rilancia questo script.
set -e
PROG="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/MD in documento.app"
PY="$PROG/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3.12 || command -v python3)"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>MD in documento</string>
<key>CFBundleDisplayName</key><string>MD in documento</string>
<key>CFBundleIdentifier</key><string>local.md2doc.launcher</string>
<key>CFBundleExecutable</key><string>avvia</string>
<key>CFBundleIconFile</key><string>icona</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/avvia" <<LAUNCH
#!/bin/sh
PROG="$PROG"
URL="http://127.0.0.1:5055"
LOG="\$HOME/Library/Logs/md2doc.log"
if ! curl -s -o /dev/null "\$URL/api/brands"; then
  cd "\$PROG"
  [ -d /opt/homebrew/lib ] && export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
  nohup "\$PROG/.venv/bin/python" app.py >"\$LOG" 2>&1 &
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    curl -s -o /dev/null "\$URL/api/brands" && break
    sleep 0.5
  done
fi
open "\$URL"
LAUNCH
chmod +x "$APP/Contents/MacOS/avvia"

# icona: quadrato arrotondato con "MD"
"$PY" "$PROG/mac/icona.py" "$APP/Contents/Resources"
touch "$APP"
echo "Creata: $APP"
