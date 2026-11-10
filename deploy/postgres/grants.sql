-- Run as aegis_migrator after applying Alembic migrations.
-- Runtime is deliberately read-only for tenant/membership tables and append-only for audit.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO aegis_runtime;
GRANT SELECT, INSERT ON TABLE audit_events TO aegis_runtime;

-- Provisioner receives no table privileges; it can execute only the audited function.
GRANT EXECUTE ON FUNCTION
    public.aegis_provision_tenant(text, text, text, text, text, uuid)
    TO aegis_provisioner;

-- Future tables default to SELECT only. Add write grants only with reviewed APIs/RLS.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO aegis_runtime;
