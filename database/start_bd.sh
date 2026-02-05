#!/bin/bash

cd ~
number_of_files=$(ls -A "/var/lib/postgresql/data/" | wc -l)
if [ "$number_of_files" == "0" ]; then
  initdb -D /var/lib/postgresql/data/ -U postgres
  cp /database/pg_hba.conf /var/lib/postgresql/data/
fi
pg_ctl -D /var/lib/postgresql/data/ -l ./db_log start

sleep 5
psql -U postgres -d postgres -c "CREATE USER ${DB_USER:-appuser} WITH PASSWORD '${DB_PASS:-password}' CREATEDB;" || echo "User might already exist"
createdb -U postgres -O ${DB_USER:-appuser} ${DB_NAME:-appdb} || echo "Database might already exist"

cd /database && alembic upgrade head

# Keep PostgreSQL running
tail -f /dev/null
