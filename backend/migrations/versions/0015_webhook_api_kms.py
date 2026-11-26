"""Allow the API to bind KMS encryption context to a preselected destination ID."""

from alembic import op

revision = "0015_webhook_api_kms"
down_revision = "0014_webhook_dest_mgmt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The API must know the destination UUID before envelope encryption so the
    # KMS encryption context can bind ciphertext to that exact destination.
    op.execute("""
        CREATE FUNCTION public.aegis_webhook_create_destination_v2(
            p_tenant_id uuid, p_destination_id uuid, p_actor text,
            p_name text, p_target_url text, p_event_types text[],
            p_secret_ciphertext bytea, p_secret_key_ref text,
            p_secret_encryption_version smallint, p_secret_version integer
        ) RETURNS TABLE(
            destination_id uuid, name varchar, target_url varchar, status varchar,
            event_types text[], secret_version integer, created_at timestamptz
        )
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, public, pg_temp
        AS $function$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM public.tenant_memberships m
                WHERE m.tenant_id = p_tenant_id AND m.subject = p_actor
                  AND m.status = 'active'
                  AND m.role IN ('tenant_admin', 'security_manager')
            ) THEN
                RAISE EXCEPTION 'webhook manager required' USING ERRCODE = '42501';
            END IF;
            IF p_destination_id IS NULL
               OR p_name IS NULL OR length(btrim(p_name)) NOT BETWEEN 1 AND 120
               OR p_target_url IS NULL OR length(p_target_url) NOT BETWEEN 9 AND 2048
               OR p_target_url !~ '^https://'
               OR p_event_types IS NULL OR cardinality(p_event_types) NOT BETWEEN 1 AND 32
               OR p_secret_ciphertext IS NULL OR octet_length(p_secret_ciphertext) NOT BETWEEN 48 AND 8192
               OR p_secret_key_ref IS NULL OR length(btrim(p_secret_key_ref)) NOT BETWEEN 1 AND 512
               OR p_secret_encryption_version <> 1 OR p_secret_version <> 1
               OR p_actor IS NULL OR length(btrim(p_actor)) NOT BETWEEN 1 AND 128
            THEN
                RAISE EXCEPTION 'invalid webhook destination' USING ERRCODE = '22023';
            END IF;
            IF EXISTS (SELECT 1 FROM unnest(p_event_types) e
                       WHERE e IS NULL OR e !~ '^[a-z][a-z0-9_.-]{0,63}$')
               OR cardinality(ARRAY(SELECT DISTINCT e FROM unnest(p_event_types) e)) <> cardinality(p_event_types)
            THEN
                RAISE EXCEPTION 'invalid webhook event types' USING ERRCODE = '22023';
            END IF;
            RETURN QUERY
            INSERT INTO public.endpoint_webhook_destinations AS d (
                id, tenant_id, name, target_url, status, event_types,
                secret_ciphertext, secret_key_ref, secret_encryption_version,
                secret_version, created_by
            ) VALUES (
                p_destination_id, p_tenant_id, btrim(p_name), p_target_url, 'active', p_event_types,
                p_secret_ciphertext, btrim(p_secret_key_ref), p_secret_encryption_version,
                p_secret_version, p_actor
            )
            RETURNING d.id, d.name, d.target_url, d.status, d.event_types,
                      d.secret_version, d.created_at;
        END
        $function$
    """)
    function = (
        "aegis_webhook_create_destination_v2("
        "uuid,uuid,text,text,text,text[],bytea,text,smallint,integer)"
    )
    op.execute(f"ALTER FUNCTION public.{function} OWNER TO aegis_migrator")
    op.execute(f"REVOKE ALL ON FUNCTION public.{function} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION public.{function} TO aegis_provisioner")
    op.execute("""
        REVOKE EXECUTE ON FUNCTION public.aegis_webhook_create_destination(
            uuid,text,text,text,text[],bytea,text,smallint,integer
        ) FROM aegis_provisioner
    """)


def downgrade() -> None:
    op.execute("""
        GRANT EXECUTE ON FUNCTION public.aegis_webhook_create_destination(
            uuid,text,text,text,text[],bytea,text,smallint,integer
        ) TO aegis_provisioner
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS public.aegis_webhook_create_destination_v2(
            uuid,uuid,text,text,text,text[],bytea,text,smallint,integer
        )
    """)
