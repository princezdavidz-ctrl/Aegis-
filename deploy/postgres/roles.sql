-- Run as the database administrator before the first AEGIS migration.
-- Supply the target database with: psql -v db_name=aegis -f roles.sql
\if :{?db_name}
\else
\echo 'Missing required psql variable: db_name'
\quit 3
\endif

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegis_migrator') THEN
        CREATE ROLE aegis_migrator LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegis_runtime') THEN
        CREATE ROLE aegis_runtime LOGIN;
    END IF;
END
$$;

ALTER ROLE aegis_migrator
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
ALTER ROLE aegis_runtime
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;

GRANT CONNECT ON DATABASE :"db_name" TO aegis_migrator;
GRANT CONNECT ON DATABASE :"db_name" TO aegis_runtime;
GRANT USAGE, CREATE ON SCHEMA public TO aegis_migrator;
GRANT USAGE ON SCHEMA public TO aegis_runtime;
