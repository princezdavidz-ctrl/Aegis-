"""Add tenant-isolated asset inventory with audited mutation functions."""
from alembic import op

revision = "0005_asset_inventory"
down_revision = "0004_tenant_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.assets (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
            name varchar(160) NOT NULL,
            asset_type varchar(32) NOT NULL,
            external_id varchar(160),
            environment varchar(16) NOT NULL DEFAULT 'unknown',
            criticality varchar(16) NOT NULL DEFAULT 'medium',
            source varchar(16) NOT NULL DEFAULT 'manual',
            status varchar(16) NOT NULL DEFAULT 'active',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_assets_tenant_type_external UNIQUE (tenant_id, asset_type, external_id),
            CONSTRAINT ck_assets_type CHECK (asset_type IN ('cloud_account','endpoint','server','domain','repository','network','application','database','user_identity','other')),
            CONSTRAINT ck_assets_environment CHECK (environment IN ('production','staging','development','test','unknown')),
            CONSTRAINT ck_assets_criticality CHECK (criticality IN ('critical','high','medium','low')),
            CONSTRAINT ck_assets_source CHECK (source IN ('manual','integration')),
            CONSTRAINT ck_assets_status CHECK (status IN ('active','archived'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_assets_tenant_status ON public.assets (tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_assets_tenant_criticality ON public.assets (tenant_id, criticality)")
    op.execute("ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.assets FORCE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='assets' AND policyname='assets_tenant_scope') THEN
            CREATE POLICY assets_tenant_scope ON public.assets FOR ALL
              USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                  SELECT 1 FROM public.tenant_memberships m
                  WHERE m.tenant_id = assets.tenant_id
                    AND m.subject = current_setting('aegis.subject', true)
                    AND m.status = 'active'
                )
              )
              WITH CHECK (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                  SELECT 1 FROM public.tenant_memberships m
                  WHERE m.tenant_id = assets.tenant_id
                    AND m.subject = current_setting('aegis.subject', true)
                    AND m.status = 'active'
                )
              );
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='assets' AND policyname='assets_migrator_manage') THEN
            CREATE POLICY assets_migrator_manage ON public.assets FOR ALL TO aegis_migrator
              USING (true) WITH CHECK (true);
          END IF;
        END $$;
    """)
    op.execute("""
        CREATE FUNCTION public.aegis_create_asset(
          p_tenant_id uuid, p_actor_subject text, p_actor_type text, p_request_id uuid,
          p_name text, p_asset_type text, p_external_id text, p_environment text, p_criticality text
        )
        RETURNS TABLE (
          asset_id uuid, asset_tenant_id uuid, asset_name text, asset_type text,
          asset_external_id text, asset_environment text, asset_criticality text,
          asset_source text, asset_status text, asset_created_at timestamptz, asset_updated_at timestamptz
        )
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $function$
        DECLARE v_id uuid := gen_random_uuid(); v_now timestamptz := clock_timestamp();
        BEGIN
          IF p_tenant_id IS NULL OR p_actor_subject IS NULL OR length(btrim(p_actor_subject))=0
             OR length(p_actor_subject)>128 OR p_actor_subject ~ '[[:cntrl:]]'
             OR p_actor_type IS NULL OR p_actor_type NOT IN ('user','service') OR p_request_id IS NULL
             OR p_name IS NULL OR length(btrim(p_name))=0 OR length(p_name)>160
             OR p_asset_type IS NULL OR p_asset_type NOT IN ('cloud_account','endpoint','server','domain','repository','network','application','database','user_identity','other')
             OR (p_external_id IS NOT NULL AND (length(btrim(p_external_id))=0 OR length(p_external_id)>160))
             OR p_environment IS NULL OR p_environment NOT IN ('production','staging','development','test','unknown')
             OR p_criticality IS NULL OR p_criticality NOT IN ('critical','high','medium','low')
          THEN RAISE EXCEPTION 'invalid asset input' USING ERRCODE='22023'; END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.tenant_memberships m
            WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor_subject AND m.status='active'
              AND m.role IN ('tenant_admin','security_manager')
          ) THEN RAISE EXCEPTION 'asset manager role required' USING ERRCODE='42501'; END IF;

          PERFORM set_config('aegis.subject',p_actor_subject,true);
          PERFORM set_config('aegis.tenant_id',p_tenant_id::text,true);
          INSERT INTO public.assets(
            id,tenant_id,name,asset_type,external_id,environment,criticality,source,status,created_at,updated_at
          ) VALUES (
            v_id,p_tenant_id,btrim(p_name),p_asset_type,p_external_id,p_environment,p_criticality,'manual','active',v_now,v_now
          );

          INSERT INTO public.audit_events(
            event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
            resource_type,resource_id,outcome,authorization_reason,correlation_id
          ) VALUES (
            gen_random_uuid(),p_tenant_id,v_now,p_actor_subject,p_actor_type,'asset.create',
            'asset',v_id::text,'succeeded','granted',p_request_id
          );

          RETURN QUERY SELECT a.id,a.tenant_id,a.name::text,a.asset_type::text,a.external_id::text,
            a.environment::text,a.criticality::text,a.source::text,a.status::text,a.created_at,a.updated_at
            FROM public.assets a WHERE a.id=v_id;
        END; $function$
    """)
    op.execute("""
        CREATE FUNCTION public.aegis_update_asset(
          p_tenant_id uuid, p_asset_id uuid, p_actor_subject text, p_actor_type text, p_request_id uuid,
          p_name text, p_asset_type text, p_external_id text, p_environment text,
          p_criticality text, p_status text
        )
        RETURNS TABLE (
          asset_id uuid, asset_tenant_id uuid, asset_name text, asset_type text,
          asset_external_id text, asset_environment text, asset_criticality text,
          asset_source text, asset_status text, asset_created_at timestamptz, asset_updated_at timestamptz
        )
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
        AS $function$
        DECLARE v_asset public.assets%ROWTYPE; v_now timestamptz := clock_timestamp();
        BEGIN
          IF p_tenant_id IS NULL OR p_asset_id IS NULL OR p_actor_subject IS NULL
             OR length(btrim(p_actor_subject))=0 OR length(p_actor_subject)>128
             OR p_actor_subject ~ '[[:cntrl:]]' OR p_actor_type IS NULL
             OR p_actor_type NOT IN ('user','service') OR p_request_id IS NULL
             OR (p_name IS NOT NULL AND (length(btrim(p_name))=0 OR length(p_name)>160))
             OR (p_asset_type IS NOT NULL AND p_asset_type NOT IN ('cloud_account','endpoint','server','domain','repository','network','application','database','user_identity','other'))
             OR (p_external_id IS NOT NULL AND (length(btrim(p_external_id))=0 OR length(p_external_id)>160))
             OR (p_environment IS NOT NULL AND p_environment NOT IN ('production','staging','development','test','unknown'))
             OR (p_criticality IS NOT NULL AND p_criticality NOT IN ('critical','high','medium','low'))
             OR (p_status IS NOT NULL AND p_status NOT IN ('active','archived'))
          THEN RAISE EXCEPTION 'invalid asset update' USING ERRCODE='22023'; END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.tenant_memberships m
            WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor_subject AND m.status='active'
              AND m.role IN ('tenant_admin','security_manager')
          ) THEN RAISE EXCEPTION 'asset manager role required' USING ERRCODE='42501'; END IF;

          PERFORM set_config('aegis.subject',p_actor_subject,true);
          PERFORM set_config('aegis.tenant_id',p_tenant_id::text,true);
          SELECT * INTO v_asset FROM public.assets a
            WHERE a.id=p_asset_id AND a.tenant_id=p_tenant_id FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION 'asset not found' USING ERRCODE='P0002'; END IF;

          UPDATE public.assets a SET
            name=COALESCE(btrim(p_name),a.name),
            asset_type=COALESCE(p_asset_type,a.asset_type),
            external_id=COALESCE(p_external_id,a.external_id),
            environment=COALESCE(p_environment,a.environment),
            criticality=COALESCE(p_criticality,a.criticality),
            status=COALESCE(p_status,a.status),
            updated_at=v_now
          WHERE a.id=p_asset_id AND a.tenant_id=p_tenant_id
          RETURNING * INTO v_asset;

          INSERT INTO public.audit_events(
            event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
            resource_type,resource_id,outcome,authorization_reason,correlation_id
          ) VALUES (
            gen_random_uuid(),p_tenant_id,v_now,p_actor_subject,p_actor_type,
            CASE WHEN p_status='archived' THEN 'asset.archive' ELSE 'asset.update' END,
            'asset',p_asset_id::text,'succeeded','granted',p_request_id
          );

          RETURN QUERY SELECT a.id,a.tenant_id,a.name::text,a.asset_type::text,a.external_id::text,
            a.environment::text,a.criticality::text,a.source::text,a.status::text,a.created_at,a.updated_at
            FROM public.assets a WHERE a.id=p_asset_id;
        END; $function$
    """)
    op.execute("ALTER FUNCTION public.aegis_create_asset(uuid,text,text,uuid,text,text,text,text,text) OWNER TO aegis_migrator")
    op.execute("ALTER FUNCTION public.aegis_update_asset(uuid,uuid,text,text,uuid,text,text,text,text,text,text) OWNER TO aegis_migrator")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_create_asset(uuid,text,text,uuid,text,text,text,text,text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_update_asset(uuid,uuid,text,text,uuid,text,text,text,text,text,text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_create_asset(uuid,text,text,uuid,text,text,text,text,text) TO aegis_provisioner")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_update_asset(uuid,uuid,text,text,uuid,text,text,text,text,text,text) TO aegis_provisioner")


def downgrade() -> None:
    op.execute("REVOKE ALL ON FUNCTION public.aegis_create_asset(uuid,text,text,uuid,text,text,text,text,text) FROM PUBLIC,aegis_provisioner")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_update_asset(uuid,uuid,text,text,uuid,text,text,text,text,text,text) FROM PUBLIC,aegis_provisioner")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_create_asset(uuid,text,text,uuid,text,text,text,text,text)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_update_asset(uuid,uuid,text,text,uuid,text,text,text,text,text,text)")
    op.execute("DROP POLICY IF EXISTS assets_migrator_manage ON public.assets")
    op.execute("DROP POLICY IF EXISTS assets_tenant_scope ON public.assets")
    op.execute("DROP TABLE IF EXISTS public.assets")
