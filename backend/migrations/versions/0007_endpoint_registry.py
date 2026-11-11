"""Add tenant-isolated endpoint enrollment invitations and device registry."""

from alembic import op

revision = "0007_endpoint_registry"
down_revision = "0006_cve_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.endpoint_enrollment_invitations (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
            token_digest char(64) NOT NULL UNIQUE,
            platform varchar(16) NOT NULL,
            expires_at timestamptz NOT NULL,
            consumed_at timestamptz,
            created_by varchar(128) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_endpoint_invite_platform CHECK (platform IN ('windows','linux','macos')),
            CONSTRAINT ck_endpoint_invite_digest_length CHECK (length(token_digest) = 64),
            CONSTRAINT ck_endpoint_invite_creator CHECK (length(btrim(created_by)) BETWEEN 1 AND 128)
        )
    """)
    op.execute("""
        CREATE TABLE public.endpoint_devices (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
            invitation_id uuid NOT NULL REFERENCES public.endpoint_enrollment_invitations(id) ON DELETE RESTRICT,
            public_key_b64 varchar(64) NOT NULL,
            public_key_fingerprint char(64) NOT NULL UNIQUE,
            platform varchar(16) NOT NULL,
            hostname varchar(255) NOT NULL,
            agent_version varchar(64) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'active',
            last_sequence bigint NOT NULL DEFAULT 0,
            enrolled_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at timestamptz,
            revoked_at timestamptz,
            CONSTRAINT ck_endpoint_device_platform CHECK (platform IN ('windows','linux','macos')),
            CONSTRAINT ck_endpoint_device_status CHECK (status IN ('active','revoked')),
            CONSTRAINT ck_endpoint_device_sequence CHECK (last_sequence >= 0),
            CONSTRAINT ck_endpoint_device_public_key_length CHECK (length(public_key_b64) BETWEEN 40 AND 64),
            CONSTRAINT ck_endpoint_device_fingerprint_length CHECK (length(public_key_fingerprint) = 64),
            CONSTRAINT ck_endpoint_device_hostname CHECK (length(btrim(hostname)) BETWEEN 1 AND 255),
            CONSTRAINT ck_endpoint_device_agent_version CHECK (length(btrim(agent_version)) BETWEEN 1 AND 64),
            CONSTRAINT uq_endpoint_device_invitation UNIQUE (invitation_id)
        )
    """)
    op.execute("CREATE INDEX ix_endpoint_invites_tenant_expiry ON public.endpoint_enrollment_invitations (tenant_id, expires_at)")
    op.execute("CREATE INDEX ix_endpoint_devices_tenant_status ON public.endpoint_devices (tenant_id, status)")
    op.execute("CREATE INDEX ix_endpoint_devices_tenant_last_seen ON public.endpoint_devices (tenant_id, last_seen_at DESC)")
    for table, policy in (
        ("endpoint_enrollment_invitations", "endpoint_invites_tenant_scope"),
        ("endpoint_devices", "endpoint_devices_tenant_scope"),
    ):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {policy} ON public.{table} FOR ALL
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1 FROM public.tenant_memberships m
                    WHERE m.tenant_id = {table}.tenant_id
                      AND m.subject = current_setting('aegis.subject', true)
                      AND m.status = 'active'
                )
            )
            WITH CHECK (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1 FROM public.tenant_memberships m
                    WHERE m.tenant_id = {table}.tenant_id
                      AND m.subject = current_setting('aegis.subject', true)
                      AND m.status = 'active'
                )
            )
        """)
        op.execute(f"CREATE POLICY {table}_migrator_manage ON public.{table} FOR ALL TO aegis_migrator USING (true) WITH CHECK (true)")
    op.execute("REVOKE ALL ON public.endpoint_enrollment_invitations, public.endpoint_devices FROM PUBLIC, aegis_runtime, aegis_provisioner, aegis_ingestor")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.endpoint_devices")
    op.execute("DROP TABLE IF EXISTS public.endpoint_enrollment_invitations")
