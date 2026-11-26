"""Create tenant-isolated webhook destinations and a durable delivery outbox.

Secrets are stored only as KMS/envelope-encrypted ciphertext plus a key reference.
This migration does not grant application or worker access and does not enable
delivery; the follow-up API/worker must add narrowly scoped SECURITY DEFINER
operations after the KMS and runtime contracts are configured.
"""

from alembic import op

revision = "0013_webhook_delivery_outbox"
down_revision = "0012_endpoint_heartbeat_health"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.endpoint_webhook_destinations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
            name varchar(120) NOT NULL,
            target_url varchar(2048) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'active',
            event_types text[] NOT NULL,
            secret_ciphertext bytea NOT NULL,
            secret_key_ref varchar(512) NOT NULL,
            secret_encryption_version smallint NOT NULL DEFAULT 1,
            secret_version integer NOT NULL DEFAULT 1,
            created_by varchar(128) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            disabled_at timestamptz,
            CONSTRAINT uq_endpoint_webhook_destinations_tenant_id
                UNIQUE (tenant_id, id),
            CONSTRAINT uq_endpoint_webhook_destinations_tenant_name
                UNIQUE (tenant_id, name),
            CONSTRAINT ck_endpoint_webhook_destination_name
                CHECK (length(btrim(name)) BETWEEN 1 AND 120),
            CONSTRAINT ck_endpoint_webhook_destination_url
                CHECK (length(target_url) BETWEEN 9 AND 2048
                    AND target_url ~ '^https://'),
            CONSTRAINT ck_endpoint_webhook_destination_status
                CHECK (status IN ('active', 'disabled')),
            CONSTRAINT ck_endpoint_webhook_destination_events
                CHECK (cardinality(event_types) BETWEEN 1 AND 32
                    AND array_position(event_types, '') IS NULL),
            CONSTRAINT ck_endpoint_webhook_ciphertext
                CHECK (octet_length(secret_ciphertext) BETWEEN 48 AND 8192),
            CONSTRAINT ck_endpoint_webhook_key_ref
                CHECK (length(btrim(secret_key_ref)) BETWEEN 1 AND 512),
            CONSTRAINT ck_endpoint_webhook_encryption_version
                CHECK (secret_encryption_version = 1),
            CONSTRAINT ck_endpoint_webhook_secret_version
                CHECK (secret_version >= 1),
            CONSTRAINT ck_endpoint_webhook_creator
                CHECK (length(btrim(created_by)) BETWEEN 1 AND 128),
            CONSTRAINT ck_endpoint_webhook_disabled_state
                CHECK ((status = 'disabled' AND disabled_at IS NOT NULL)
                    OR (status = 'active' AND disabled_at IS NULL))
        )
    """)
    op.execute("""
        CREATE INDEX ix_endpoint_webhook_destinations_tenant_status
        ON public.endpoint_webhook_destinations (tenant_id, status, created_at DESC)
    """)

    op.execute("""
        CREATE TABLE public.endpoint_webhook_outbox (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
            destination_id uuid NOT NULL,
            source_event_id uuid,
            event_type varchar(64) NOT NULL,
            idempotency_key varchar(128) NOT NULL,
            payload jsonb NOT NULL,
            payload_sha256 varchar(64) NOT NULL,
            status varchar(16) NOT NULL DEFAULT 'pending',
            attempt_count integer NOT NULL DEFAULT 0,
            next_attempt_at timestamptz NOT NULL DEFAULT now(),
            lease_token uuid,
            lease_expires_at timestamptz,
            delivered_at timestamptz,
            last_http_status smallint,
            last_error_code varchar(64),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_endpoint_webhook_outbox_tenant_destination
                FOREIGN KEY (tenant_id, destination_id)
                REFERENCES public.endpoint_webhook_destinations(tenant_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT uq_endpoint_webhook_outbox_tenant_idempotency
                UNIQUE (tenant_id, idempotency_key),
            CONSTRAINT ck_endpoint_webhook_outbox_event_type
                CHECK (length(btrim(event_type)) BETWEEN 1 AND 64),
            CONSTRAINT ck_endpoint_webhook_outbox_idempotency
                CHECK (length(btrim(idempotency_key)) BETWEEN 1 AND 128),
            CONSTRAINT ck_endpoint_webhook_outbox_payload
                CHECK (jsonb_typeof(payload) = 'object'
                    AND octet_length(payload::text) <= 1048576),
            CONSTRAINT ck_endpoint_webhook_outbox_payload_hash
                CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_endpoint_webhook_outbox_status
                CHECK (status IN ('pending', 'processing', 'retry_wait',
                    'delivered', 'dead_letter', 'cancelled')),
            CONSTRAINT ck_endpoint_webhook_outbox_attempts
                CHECK (attempt_count BETWEEN 0 AND 25),
            CONSTRAINT ck_endpoint_webhook_outbox_http_status
                CHECK (last_http_status IS NULL OR last_http_status BETWEEN 100 AND 599),
            CONSTRAINT ck_endpoint_webhook_outbox_error_code
                CHECK (last_error_code IS NULL OR
                    length(btrim(last_error_code)) BETWEEN 1 AND 64),
            CONSTRAINT ck_endpoint_webhook_outbox_lease
                CHECK ((status = 'processing' AND lease_token IS NOT NULL
                        AND lease_expires_at IS NOT NULL)
                    OR (status <> 'processing' AND lease_token IS NULL
                        AND lease_expires_at IS NULL)),
            CONSTRAINT ck_endpoint_webhook_outbox_delivered
                CHECK ((status = 'delivered' AND delivered_at IS NOT NULL)
                    OR (status <> 'delivered' AND delivered_at IS NULL))
        )
    """)
    op.execute("""
        CREATE INDEX ix_endpoint_webhook_outbox_due
        ON public.endpoint_webhook_outbox (next_attempt_at, created_at)
        WHERE status IN ('pending', 'retry_wait')
    """)
    op.execute("""
        CREATE INDEX ix_endpoint_webhook_outbox_tenant_destination
        ON public.endpoint_webhook_outbox (tenant_id, destination_id, created_at DESC)
    """)

    for table in ("endpoint_webhook_destinations", "endpoint_webhook_outbox"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_manager_read
            ON public.{table}
            FOR SELECT
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1 FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                      AND membership.role IN ('tenant_admin', 'security_manager')
                )
            )
        """)
        op.execute(f"""
            CREATE POLICY {table}_migrator_manage
            ON public.{table}
            FOR ALL TO aegis_migrator
            USING (true) WITH CHECK (true)
        """)
        op.execute(
            f"ALTER TABLE public.{table} OWNER TO aegis_migrator"
        )
        op.execute(
            f"REVOKE ALL ON public.{table} FROM PUBLIC, aegis_runtime, "
            "aegis_provisioner, aegis_ingestor"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.endpoint_webhook_outbox")
    op.execute("DROP TABLE IF EXISTS public.endpoint_webhook_destinations")
