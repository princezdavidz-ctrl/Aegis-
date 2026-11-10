"""Add controlled, audited tenant provisioning through a scoped definer function."""

from alembic import op

revision = "0002_tenant_provisioning"
down_revision = "0001_security_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE POLICY tenants_migrator_insert ON tenants
        FOR INSERT TO aegis_migrator
        WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_memberships_migrator_insert ON tenant_memberships
        FOR INSERT TO aegis_migrator
        WITH CHECK (true)
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.aegis_provision_tenant(
            p_slug text,
            p_display_name text,
            p_initial_admin_subject text,
            p_actor_subject text,
            p_actor_type text,
            p_request_id uuid
        )
        RETURNS TABLE (tenant_id uuid, tenant_slug text)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_tenant_id uuid := gen_random_uuid();
            v_now timestamptz := clock_timestamp();
        BEGIN
            IF p_slug IS NULL
               OR length(p_slug) < 3
               OR length(p_slug) > 63
               OR p_slug !~ '^[a-z0-9]([a-z0-9-]{1,61}[a-z0-9])$'
            THEN
                RAISE EXCEPTION 'invalid tenant slug' USING ERRCODE = '22023';
            END IF;

            IF p_display_name IS NULL
               OR length(btrim(p_display_name)) < 1
               OR length(btrim(p_display_name)) > 160
            THEN
                RAISE EXCEPTION 'invalid tenant display name' USING ERRCODE = '22023';
            END IF;

            IF p_initial_admin_subject IS NULL
               OR length(btrim(p_initial_admin_subject)) < 1
               OR length(p_initial_admin_subject) > 128
               OR p_initial_admin_subject ~ '[[:cntrl:]]'
            THEN
                RAISE EXCEPTION 'invalid initial administrator subject' USING ERRCODE = '22023';
            END IF;

            IF p_actor_subject IS NULL
               OR length(btrim(p_actor_subject)) < 1
               OR length(p_actor_subject) > 128
               OR p_actor_subject ~ '[[:cntrl:]]'
               OR p_actor_type NOT IN ('user', 'service')
               OR p_request_id IS NULL
            THEN
                RAISE EXCEPTION 'invalid provisioning actor or request ID' USING ERRCODE = '22023';
            END IF;

            PERFORM set_config('aegis.subject', p_actor_subject, true);
            PERFORM set_config('aegis.tenant_id', v_tenant_id::text, true);

            INSERT INTO public.tenants (id, slug, display_name, created_at)
            VALUES (v_tenant_id, p_slug, btrim(p_display_name), v_now);

            INSERT INTO public.tenant_memberships (
                id, tenant_id, subject, role, status, created_at
            )
            VALUES (
                gen_random_uuid(), v_tenant_id, p_initial_admin_subject,
                'tenant_admin', 'active', v_now
            );

            INSERT INTO public.audit_events (
                event_id, tenant_id, occurred_at, actor_subject, actor_type,
                action, resource_type, resource_id, outcome,
                authorization_reason, correlation_id
            )
            VALUES (
                gen_random_uuid(), v_tenant_id, v_now, p_actor_subject, p_actor_type,
                'tenant.provision', 'tenant', v_tenant_id::text, 'succeeded',
                'granted', p_request_id
            );

            RETURN QUERY SELECT v_tenant_id, p_slug;
        END;
        $function$
        """
    )
    op.execute(
        """
        ALTER FUNCTION public.aegis_provision_tenant(text, text, text, text, text, uuid)
        OWNER TO aegis_migrator
        """
    )
    op.execute(
        """
        REVOKE ALL ON FUNCTION
        public.aegis_provision_tenant(text, text, text, text, text, uuid)
        FROM PUBLIC
        """
    )
    op.execute(
        """
        GRANT EXECUTE ON FUNCTION
        public.aegis_provision_tenant(text, text, text, text, text, uuid)
        TO aegis_provisioner
        """
    )


def downgrade() -> None:
    op.execute(
        """
        REVOKE ALL ON FUNCTION
        public.aegis_provision_tenant(text, text, text, text, text, uuid)
        FROM PUBLIC, aegis_provisioner
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS
        public.aegis_provision_tenant(text, text, text, text, text, uuid)
        """
    )
    op.execute("DROP POLICY IF EXISTS tenant_memberships_migrator_insert ON tenant_memberships")
    op.execute("DROP POLICY IF EXISTS tenants_migrator_insert ON tenants")
