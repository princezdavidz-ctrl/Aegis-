"""Add tenant profile fields and a controlled, audited update function."""
from alembic import op

revision = "0004_tenant_profile"
down_revision = "0003_membership_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS industry varchar(80)")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS organization_size varchar(32)")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS region varchar(64)")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS data_retention_days integer NOT NULL DEFAULT 90")
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS policy_profile varchar(32) NOT NULL DEFAULT 'baseline'")
    op.execute("""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_tenants_data_retention_days') THEN
            ALTER TABLE tenants ADD CONSTRAINT ck_tenants_data_retention_days CHECK (data_retention_days BETWEEN 30 AND 3650);
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_tenants_policy_profile') THEN
            ALTER TABLE tenants ADD CONSTRAINT ck_tenants_policy_profile CHECK (policy_profile IN ('baseline','strict','regulated'));
          END IF;
        END $$;
    """)
    op.execute("CREATE POLICY tenants_migrator_update ON tenants FOR UPDATE TO aegis_migrator USING (true) WITH CHECK (true)")
    op.execute("""
        CREATE FUNCTION public.aegis_update_tenant_profile(
          p_tenant_id uuid, p_actor_subject text, p_actor_type text, p_request_id uuid,
          p_industry text, p_organization_size text, p_region text,
          p_data_retention_days integer, p_policy_profile text
        )
        RETURNS TABLE (
          tenant_id uuid, tenant_slug text, tenant_display_name text,
          tenant_industry text, tenant_organization_size text, tenant_region text,
          tenant_data_retention_days integer, tenant_policy_profile text, tenant_created_at timestamptz
        )
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $function$
        DECLARE v_now timestamptz := clock_timestamp();
        BEGIN
          IF p_tenant_id IS NULL OR p_actor_subject IS NULL OR length(btrim(p_actor_subject))=0
             OR length(p_actor_subject)>128 OR p_actor_subject ~ '[[:cntrl:]]'
             OR p_actor_type IS NULL OR p_actor_type NOT IN ('user','service') OR p_request_id IS NULL
            THEN RAISE EXCEPTION 'invalid profile actor' USING ERRCODE='22023'; END IF;
          IF p_industry IS NOT NULL AND (length(btrim(p_industry))=0 OR length(p_industry)>80)
            THEN RAISE EXCEPTION 'invalid industry' USING ERRCODE='22023'; END IF;
          IF p_organization_size IS NOT NULL AND p_organization_size NOT IN ('1-10','11-50','51-200','201-1000','1000+')
            THEN RAISE EXCEPTION 'invalid organization size' USING ERRCODE='22023'; END IF;
          IF p_region IS NOT NULL AND (length(btrim(p_region))=0 OR length(p_region)>64)
            THEN RAISE EXCEPTION 'invalid region' USING ERRCODE='22023'; END IF;
          IF p_data_retention_days IS NOT NULL AND p_data_retention_days NOT BETWEEN 30 AND 3650
            THEN RAISE EXCEPTION 'invalid retention period' USING ERRCODE='22023'; END IF;
          IF p_policy_profile IS NOT NULL AND p_policy_profile NOT IN ('baseline','strict','regulated')
            THEN RAISE EXCEPTION 'invalid policy profile' USING ERRCODE='22023'; END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.tenant_memberships m
            WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor_subject
              AND m.status='active' AND m.role='tenant_admin'
          ) THEN RAISE EXCEPTION 'tenant administrator required' USING ERRCODE='42501'; END IF;

          PERFORM set_config('aegis.subject', p_actor_subject, true);
          PERFORM set_config('aegis.tenant_id', p_tenant_id::text, true);
          UPDATE public.tenants t SET
            industry=COALESCE(p_industry,t.industry),
            organization_size=COALESCE(p_organization_size,t.organization_size),
            region=COALESCE(p_region,t.region),
            data_retention_days=COALESCE(p_data_retention_days,t.data_retention_days),
            policy_profile=COALESCE(p_policy_profile,t.policy_profile)
          WHERE t.id=p_tenant_id;
          IF NOT FOUND THEN RAISE EXCEPTION 'tenant not found' USING ERRCODE='P0002'; END IF;

          INSERT INTO public.audit_events (
            event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
            resource_type,resource_id,outcome,authorization_reason,correlation_id
          ) VALUES (
            gen_random_uuid(),p_tenant_id,v_now,p_actor_subject,p_actor_type,
            'tenant.profile.update','tenant',p_tenant_id::text,'succeeded','granted',p_request_id
          );

          RETURN QUERY SELECT t.id,t.slug::text,t.display_name::text,t.industry::text,
            t.organization_size::text,t.region::text,t.data_retention_days,
            t.policy_profile::text,t.created_at FROM public.tenants t WHERE t.id=p_tenant_id;
        END; $function$;
    """)
    op.execute("ALTER FUNCTION public.aegis_update_tenant_profile(uuid,text,text,uuid,text,text,text,integer,text) OWNER TO aegis_migrator")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_update_tenant_profile(uuid,text,text,uuid,text,text,text,integer,text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_update_tenant_profile(uuid,text,text,uuid,text,text,text,integer,text) TO aegis_provisioner")


def downgrade() -> None:
    op.execute("REVOKE ALL ON FUNCTION public.aegis_update_tenant_profile(uuid,text,text,uuid,text,text,text,integer,text) FROM PUBLIC,aegis_provisioner")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_update_tenant_profile(uuid,text,text,uuid,text,text,text,integer,text)")
    op.execute("DROP POLICY IF EXISTS tenants_migrator_update ON tenants")
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_data_retention_days")
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_policy_profile")
    for column in ("industry","organization_size","region","data_retention_days","policy_profile"):
        op.execute(f"ALTER TABLE tenants DROP COLUMN IF EXISTS {column}")
