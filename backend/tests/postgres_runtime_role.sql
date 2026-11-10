-- CI-only credentials and test-only mutation role. Never use these passwords in production.
ALTER ROLE aegis_migrator PASSWORD 'aegis_ci_migrator_password';
ALTER ROLE aegis_runtime PASSWORD 'aegis_ci_runtime_password';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegis_test_mutator') THEN
        CREATE ROLE aegis_test_mutator LOGIN;
    END IF;
END
$$;

ALTER ROLE aegis_test_mutator
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS
    PASSWORD 'aegis_ci_mutator_password';
GRANT CONNECT ON DATABASE aegis_test TO aegis_test_mutator;
GRANT USAGE ON SCHEMA public TO aegis_test_mutator;
ALTER ROLE aegis_provisioner PASSWORD 'aegis_ci_provisioner_password';
