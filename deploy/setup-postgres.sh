#!/bin/bash

set -euo pipefail
BIN=/usr/lib/postgresql/16/bin
DATA=/var/lib/postgresql/data

# Ensure dirs/ownership
mkdir -p "$DATA" /var/run/postgresql
chown -R postgres:postgres "$DATA" /var/run/postgresql
chmod 700 "$DATA"
chmod 2775 /var/run/postgresql

# Initialize cluster if missing
if [ ! -s "$DATA/PG_VERSION" ]; then
  echo "[initdb] creating cluster in $DATA ..."
  runuser -u postgres -- $BIN/initdb -D "$DATA" --encoding=UTF8 --locale=C.UTF-8
fi

# Write a simple, robust supervisor program (no shell, no env vars in command)
cat >/etc/supervisor/conf.d/postgres.conf <<EOF
[program:postgres]
command=/usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/data -c listen_addresses=localhost
user=postgres
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/postgres.out.log
stderr_logfile=/var/log/supervisor/postgres.err.log
stopasgroup=true
killasgroup=true
EOF

supervisorctl reread
supervisorctl update
supervisorctl restart postgres || supervisorctl start postgres
sleep 2
supervisorctl status postgres
runuser -u postgres -- $BIN/pg_isready || true

BIN=/usr/lib/postgresql/16/bin
DATA=/var/lib/postgresql/data
DBNAME=${CMS_DB_NAME:-cmsdb}
DBUSER=${CMS_DB_USER:-cmsuser}
DBPASS=${CMS_DB_PASS:-cmspassword}

# Ensure server is running
runuser -u postgres -- $BIN/pg_ctl -D "$DATA" status || \
  runuser -u postgres -- $BIN/pg_ctl -D "$DATA" -l "$DATA/logfile" -w start

# Role
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='\''$DBUSER'\''" | grep -q 1; then
  runuser -u postgres -- psql -v ON_ERROR_STOP=1 -c "CREATE ROLE $DBUSER LOGIN PASSWORD '\''$DBPASS'\'';"
fi

# Database
if ! runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname='\''$DBNAME'\''" | grep -q 1; then
  runuser -u postgres -- createdb --owner="$DBUSER" "$DBNAME"
fi

# Grants expected by CMS
runuser -u postgres -- psql -d "$DBNAME" -v ON_ERROR_STOP=1 \
  -c "ALTER SCHEMA public OWNER TO $DBUSER;" \
  -c "GRANT SELECT ON pg_largeobject TO $DBUSER;"

echo "[ok] role=$DBUSER db=$DBNAME ready"
