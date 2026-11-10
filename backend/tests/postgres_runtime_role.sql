-- CI-only restricted application role. Never reuse this password outside CI.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegis_runtime') THEN
        CREATE ROLE aegis_runtime LOGIN PASSWORD 'aegis_ci_only_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE aegis_test TO aegis_runtime;
GRANT USAGE ON SCHEMA public TO aegis_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE tenants, tenant_memberships, audit_events
    TO aegis_runtime;
