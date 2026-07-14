#!/usr/bin/env bash
# Backup zilnic SQLite: copie consistentă + păstrează ultimele 14.
# Instalare (pe VPS, din directorul proiectului):
#   chmod +x deploy/backup.sh
#   (crontab -l 2>/dev/null; echo "20 3 * * * $(pwd)/deploy/backup.sh $(pwd)") | crontab -
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
DB="$PROJECT_DIR/data/forex.db"
OUT_DIR="$PROJECT_DIR/backups"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUT_DIR"
[ -f "$DB" ] || { echo "nu există $DB"; exit 1; }

if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB" ".backup '$OUT_DIR/forex_$STAMP.db'"
else
    # fallback: copie simplă (SQLite e în mod jurnal implicit — acceptabil)
    cp "$DB" "$OUT_DIR/forex_$STAMP.db"
fi
gzip "$OUT_DIR/forex_$STAMP.db"

# păstrează doar ultimele 14 arhive
ls -1t "$OUT_DIR"/forex_*.db.gz 2>/dev/null | tail -n +15 | xargs -r rm --
echo "backup ok: $OUT_DIR/forex_$STAMP.db.gz"
