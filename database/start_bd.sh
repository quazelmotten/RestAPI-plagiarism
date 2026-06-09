#!/bin/bash

cd ~
number_of_files=$(ls -A "/var/lib/postgresql/data/" | wc -l)
if [ "$number_of_files" == "0" ]; then
  initdb -D /var/lib/postgresql/data/ -U postgres
  cp /database/pg_hba.conf /var/lib/postgresql/data/
  # Configure PostgreSQL to listen on all interfaces and use custom port
  echo "listen_addresses = '*'" >> /var/lib/postgresql/data/postgresql.conf
  echo "port = ${PGPORT:-5432}" >> /var/lib/postgresql/data/postgresql.conf
fi

if ! pg_isready -q -p "${PGPORT:-5432}" 2>/dev/null; then
  pg_ctl -D /var/lib/postgresql/data/ -l ./db_log start -o "-p ${PGPORT:-5432}"
fi

echo "Waiting for PostgreSQL to accept connections..."
for i in $(seq 1 30); do
  if pg_isready -q -p "${PGPORT:-5432}" 2>/dev/null; then
    echo "PostgreSQL is ready"
    break
  fi
  echo "Waiting for PostgreSQL... ($i/30)"
  sleep 1
done

if ! pg_isready -q -p "${PGPORT:-5432}" 2>/dev/null; then
  echo "ERROR: PostgreSQL failed to start within 30 seconds"
  cat ./db_log
  exit 1
fi

psql -U postgres -d postgres -c "CREATE USER ${DB_USER:-appuser} WITH PASSWORD '${DB_PASS:-password}' CREATEDB;" || echo "User might already exist"
createdb -U postgres -O ${DB_USER:-appuser} ${DB_NAME:-appdb} || echo "Database might already exist"

cd /database && alembic upgrade head

tail -f /dev/null
