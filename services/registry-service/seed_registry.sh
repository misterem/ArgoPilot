#!/usr/bin/env bash
# Build a small SQLite file for registry-service.
# Safe to run again: it deletes the file and writes a fresh one.
#
# Usage, from services/registry-service:
#   bash seed_registry.sh
#   bash seed_registry.sh /path/to/registry.db

set -euo pipefail

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 is not installed." >&2
  exit 1
fi

db="${1:-registry.db}"
rm -f "$db"

here="$(cd "$(dirname "$0")" && pwd)"

{
  echo "PRAGMA foreign_keys = ON;"
  cat "$here/schema.sql" "$here/catalogue.sql" "$here/demo.sql"
} | sqlite3 "$db"

echo "Wrote $db"
echo "  2 farms, 4 plots, 2 crops, 3 soils, 4 emitters"
