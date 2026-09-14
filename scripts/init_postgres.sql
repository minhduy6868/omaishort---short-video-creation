-- Run once as a PostgreSQL superuser (Windows: postgresql-x64-16 is already running).
-- psql -h 127.0.0.1 -U postgres -f scripts/init_postgres.sql

CREATE USER omaishort WITH PASSWORD 'omaishort';
CREATE DATABASE omaishort OWNER omaishort;
GRANT ALL PRIVILEGES ON DATABASE omaishort TO omaishort;
