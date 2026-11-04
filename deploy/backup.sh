#!/bin/sh
# Dump the database to deploy/backups/profrating-<date>.sql.gz and keep the last 14.
# Run from anywhere; for a daily backup add to crontab (crontab -e):
#   0 3 * * * /home/ubuntu/Prof_Rating/deploy/backup.sh >> /home/ubuntu/backup.log 2>&1
set -eu
cd "$(dirname "$0")"
mkdir -p backups
file="backups/profrating-$(date +%Y%m%d-%H%M).sql.gz"
docker compose exec -T db pg_dump -U profrating profrating | gzip > "$file"
ls -1t backups/profrating-*.sql.gz | tail -n +15 | xargs -r rm --
echo "Saved $file"
