FROM timescale/timescaledb-ha:pg16

COPY postgres-init.sql /docker-entrypoint-initdb.d/postgres-init.sql
