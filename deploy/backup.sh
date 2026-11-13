#!/bin/sh
# A consistent copy of the agent's database (SQLite's online backup, safe while AERA runs), kept on the host.
#   sh deploy/backup.sh            -> deploy/backups/aera-YYYYmmdd-HHMM.db (the last 14 are kept)
set -eu
cd "$(dirname "$0")/.."
mkdir -p deploy/backups
stamp=$(date +%Y%m%d-%H%M)
docker compose exec -T agents python -c "import sqlite3; s=sqlite3.connect('/app/data/aera.db'); d=sqlite3.connect('/app/data/backup.db'); s.backup(d); d.close()"
docker compose cp agents:/app/data/backup.db "deploy/backups/aera-$stamp.db"
docker compose exec -T agents rm -f /app/data/backup.db
chmod 600 "deploy/backups/aera-$stamp.db"
ls -1t deploy/backups/aera-*.db | tail -n +15 | xargs -r rm -f
echo "backed up: deploy/backups/aera-$stamp.db"
