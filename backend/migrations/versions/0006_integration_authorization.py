"""Add tenant-scoped integration authorization requests and approval workflow."""
from alembic import op

revision = "0006_integration_authorization"
down_revision = "0005_asset_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.integrations (
          id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
          provider varchar(32) NOT NULL,
          display_name varchar(120) NOT NULL,
          external_account_id varchar(160),
          status varchar(40) NOT NULL DEFAULT 'requested',
          access_mode varchar(16) NOT NULL DEFAULT 'read_only',
          requested_scopes json NOT NULL,
          approved_scopes json NOT NULL DEFAULT '[]',
          created_by varchar(128) NOT NULL,
          approved_by varchar(128),
          approved_at timestamptz,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_integrations_tenant_provider_account UNIQUE (tenant_id,provider,external_account_id),
          CONSTRAINT ck_integrations_provider CHECK (provider IN ('github','aws','azure','gcp','wazuh','suricata','trivy','semgrep')),
          CONSTRAINT ck_integrations_status CHECK (status IN ('requested','approved_pending_verification','active','suspended','revoked','error')),
          CONSTRAINT ck_integrations_access_mode CHECK (access_mode='read_only')
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_integrations_tenant_status ON public.integrations(tenant_id,status)")
    op.execute("ALTER TABLE public.integrations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.integrations FORCE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='integrations' AND policyname='integrations_tenant_scope') THEN
            CREATE POLICY integrations_tenant_scope ON public.integrations FOR ALL
              USING (
                tenant_id=nullif(current_setting('aegis.tenant_id',true),'')::uuid
                AND EXISTS (
                  SELECT 1 FROM public.tenant_memberships m
                  WHERE m.tenant_id=integrations.tenant_id
                    AND m.subject=current_setting('aegis.subject',true)
                    AND m.status='active'
                )
              )
              WITH CHECK (
                tenant_id=nullif(current_setting('aegis.tenant_id',true),'')::uuid
                AND EXISTS (
                  SELECT 1 FROM public.tenant_memberships m
                  WHERE m.tenant_id=integrations.tenant_id
                    AND m.subject=current_setting('aegis.subject',true)
                    AND m.status='active'
                )
              );
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='integrations' AND policyname='integrations_migrator_manage') THEN
            CREATE POLICY integrations_migrator_manage ON public.integrations FOR ALL TO aegis_migrator USING (true) WITH CHECK (true);
          END IF;
        END $$;
    """)
    op.execute("""
        CREATE FUNCTION public.aegis_request_integration(
          p_tenant_id uuid,p_actor_subject text,p_actor_type text,p_request_id uuid,
          p_provider text,p_display_name text,p_external_account_id text,p_requested_scopes json
        )
        RETURNS TABLE (
          integration_id uuid,integration_tenant_id uuid,integration_provider text,
          integration_display_name text,integration_external_account_id text,
          integration_status text,integration_access_mode text,
          integration_requested_scopes json,integration_approved_scopes json,
          integration_created_by text,integration_approved_by text,
          integration_approved_at timestamptz,integration_created_at timestamptz,
          integration_updated_at timestamptz
        )
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
        AS $function$
        DECLARE v_id uuid:=gen_random_uuid(); v_now timestamptz:=clock_timestamp();
        BEGIN
          IF p_tenant_id IS NULL OR p_actor_subject IS NULL OR length(btrim(p_actor_subject))=0
             OR length(p_actor_subject)>128 OR p_actor_subject ~ '[[:cntrl:]]'
             OR p_actor_type IS NULL OR p_actor_type NOT IN ('user','service') OR p_request_id IS NULL
             OR p_provider IS NULL OR p_provider NOT IN ('github','aws','azure','gcp','wazuh','suricata','trivy','semgrep')
             OR p_display_name IS NULL OR length(btrim(p_display_name))=0 OR length(p_display_name)>120
             OR (p_external_account_id IS NOT NULL AND (length(btrim(p_external_account_id))=0 OR length(p_external_account_id)>160))
             OR p_requested_scopes IS NULL
          THEN RAISE EXCEPTION 'invalid integration request' USING ERRCODE='22023'; END IF;
          IF json_typeof(p_requested_scopes)<>'array' THEN
            RAISE EXCEPTION 'requested scopes must be an array' USING ERRCODE='22023';
          END IF;
          IF json_array_length(p_requested_scopes)<1 OR json_array_length(p_requested_scopes)>10
             OR EXISTS (SELECT 1 FROM json_array_elements_text(p_requested_scopes) s WHERE s.value NOT LIKE '%:read' OR s.value='*')
          THEN RAISE EXCEPTION 'invalid integration scopes' USING ERRCODE='22023'; END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.tenant_memberships m
            WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor_subject AND m.status='active'
              AND m.role IN ('tenant_admin','security_manager')
          ) THEN RAISE EXCEPTION 'integration manager role required' USING ERRCODE='42501'; END IF;
          PERFORM set_config('aegis.subject',p_actor_subject,true);
          PERFORM set_config('aegis.tenant_id',p_tenant_id::text,true);
          INSERT INTO public.integrations(
            id,tenant_id,provider,display_name,external_account_id,status,access_mode,
            requested_scopes,approved_scopes,created_by,created_at,updated_at
          ) VALUES (
            v_id,p_tenant_id,p_provider,btrim(p_display_name),p_external_account_id,
            'requested','read_only',p_requested_scopes,'[]'::json,p_actor_subject,v_now,v_now
          );
          INSERT INTO public.audit_events(
            event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
            resource_type,resource_id,outcome,authorization_reason,correlation_id
          ) VALUES (
            gen_random_uuid(),p_tenant_id,v_now,p_actor_subject,p_actor_type,
            'integration.request','integration',v_id::text,'succeeded','granted',p_request_id
          );
          RETURN QUERY SELECT i.id,i.tenant_id,i.provider::text,i.display_name::text,
            i.external_account_id::text,i.status::text,i.access_mode::text,
            i.requested_scopes,i.approved_scopes,i.created_by::text,i.approved_by::text,
            i.approved_at,i.created_at,i.updated_at FROM public.integrations i WHERE i.id=v_id;
        END; $function$
    """)
    op.execute("""
        CREATE FUNCTION public.aegis_approve_integration(
          p_tenant_id uuid,p_integration_id uuid,p_actor_subject text,
          p_approved_scopes json,p_request_id uuid
        )
        RETURNS TABLE (
          integration_id uuid,integration_tenant_id uuid,integration_provider text,
          integration_display_name text,integration_external_account_id text,
          integration_status text,integration_access_mode text,
          integration_requested_scopes json,integration_approved_scopes json,
          integration_created_by text,integration_approved_by text,
          integration_approved_at timestamptz,integration_created_at timestamptz,
          integration_updated_at timestamptz
        )
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
        AS $function$
        DECLARE v_integration public.integrations%ROWTYPE; v_now timestamptz:=clock_timestamp();
        BEGIN
          IF p_tenant_id IS NULL OR p_integration_id IS NULL OR p_actor_subject IS NULL
             OR length(btrim(p_actor_subject))=0 OR length(p_actor_subject)>128
             OR p_actor_subject ~ '[[:cntrl:]]' OR p_approved_scopes IS NULL OR p_request_id IS NULL
          THEN RAISE EXCEPTION 'invalid integration approval' USING ERRCODE='22023'; END IF;
          IF json_typeof(p_approved_scopes)<>'array' THEN
            RAISE EXCEPTION 'approved scopes must be an array' USING ERRCODE='22023';
          END IF;
          IF json_array_length(p_approved_scopes)<1 OR json_array_length(p_approved_scopes)>10
             OR EXISTS (SELECT 1 FROM json_array_elements_text(p_approved_scopes) s WHERE s.value NOT LIKE '%:read' OR s.value='*')
          THEN RAISE EXCEPTION 'invalid approved scopes' USING ERRCODE='22023'; END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.tenant_memberships m
            WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor_subject
              AND m.status='active' AND m.role='tenant_admin'
          ) THEN RAISE EXCEPTION 'tenant administrator required' USING ERRCODE='42501'; END IF;
          PERFORM set_config('aegis.subject',p_actor_subject,true);
          PERFORM set_config('aegis.tenant_id',p_tenant_id::text,true);
          SELECT * INTO v_integration FROM public.integrations i
            WHERE i.id=p_integration_id AND i.tenant_id=p_tenant_id FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION 'integration not found' USING ERRCODE='P0002'; END IF;
          IF v_integration.status<>'requested' THEN
            RAISE EXCEPTION 'integration is not awaiting approval' USING ERRCODE='23514';
          END IF;
          IF EXISTS (
            SELECT 1 FROM json_array_elements_text(p_approved_scopes) approved
            WHERE NOT EXISTS (
              SELECT 1 FROM json_array_elements_text(v_integration.requested_scopes) requested
              WHERE requested.value=approved.value
            )
          ) THEN RAISE EXCEPTION 'approved scopes exceed requested scopes' USING ERRCODE='22023'; END IF;
          UPDATE public.integrations i SET status='approved_pending_verification',
            approved_scopes=p_approved_scopes,approved_by=p_actor_subject,
            approved_at=v_now,updated_at=v_now
          WHERE i.id=p_integration_id AND i.tenant_id=p_tenant_id
          RETURNING * INTO v_integration;
          INSERT INTO public.audit_events(
            event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
            resource_type,resource_id,outcome,authorization_reason,correlation_id
          ) VALUES (
            gen_random_uuid(),p_tenant_id,v_now,p_actor_subject,'user',
            'integration.approve','integration',p_integration_id::text,'succeeded','granted',p_request_id
          );
          RETURN QUERY SELECT i.id,i.tenant_id,i.provider::text,i.display_name::text,
            i.external_account_id::text,i.status::text,i.access_mode::text,
            i.requested_scopes,i.approved_scopes,i.created_by::text,i.approved_by::text,
            i.approved_at,i.created_at,i.updated_at FROM public.integrations i WHERE i.id=p_integration_id;
        END; $function$
    """)
    op.execute("""
        CREATE FUNCTION public.aegis_revoke_integration(
          p_tenant_id uuid,p_integration_id uuid,p_actor_subject text,p_request_id uuid
        )
        RETURNS TABLE (
          integration_id uuid,integration_tenant_id uuid,integration_provider text,
          integration_display_name text,integration_external_account_id text,
          integration_status text,integration_access_mode text,
          integration_requested_scopes json,integration_approved_scopes json,
          integration_created_by text,integration_approved_by text,
          integration_approved_at timestamptz,integration_created_at timestamptz,
          integration_updated_at timestamptz
        )
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
        AS $function$
        DECLARE v_now timestamptz:=clock_timestamp();
        BEGIN
          IF p_tenant_id IS NULL OR p_integration_id IS NULL OR p_actor_subject IS NULL
             OR length(btrim(p_actor_subject))=0 OR length(p_actor_subject)>128
             OR p_actor_subject ~ '[[:cntrl:]]' OR p_request_id IS NULL
          THEN RAISE EXCEPTION 'invalid integration revocation' USING ERRCODE='22023'; END IF;
          IF NOT EXISTS (
            SELECT 1 FROM public.tenant_memberships m
            WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor_subject
              AND m.status='active' AND m.role='tenant_admin'
          ) THEN RAISE EXCEPTION 'tenant administrator required' USING ERRCODE='42501'; END IF;
          PERFORM set_config('aegis.subject',p_actor_subject,true);
          PERFORM set_config('aegis.tenant_id',p_tenant_id::text,true);
          UPDATE public.integrations i SET status='revoked',updated_at=v_now
          WHERE i.id=p_integration_id AND i.tenant_id=p_tenant_id AND i.status<>'revoked';
          IF NOT FOUND THEN RAISE EXCEPTION 'integration not found or already revoked' USING ERRCODE='P0002'; END IF;
          INSERT INTO public.audit_events(
            event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
            resource_type,resource_id,outcome,authorization_reason,correlation_id
          ) VALUES (
            gen_random_uuid(),p_tenant_id,v_now,p_actor_subject,'user',
            'integration.revoke','integration',p_integration_id::text,'succeeded','granted',p_request_id
          );
          RETURN QUERY SELECT i.id,i.tenant_id,i.provider::text,i.display_name::text,
            i.external_account_id::text,i.status::text,i.access_mode::text,
            i.requested_scopes,i.approved_scopes,i.created_by::text,i.approved_by::text,
            i.approved_at,i.created_at,i.updated_at FROM public.integrations i WHERE i.id=p_integration_id;
        END; $function$
    """)
    op.execute("ALTER FUNCTION public.aegis_request_integration(uuid,text,text,uuid,text,text,text,json) OWNER TO aegis_migrator")
    op.execute("ALTER FUNCTION public.aegis_approve_integration(uuid,uuid,text,json,uuid) OWNER TO aegis_migrator")
    op.execute("ALTER FUNCTION public.aegis_revoke_integration(uuid,uuid,text,uuid) OWNER TO aegis_migrator")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_request_integration(uuid,text,text,uuid,text,text,text,json) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_approve_integration(uuid,uuid,text,json,uuid) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_revoke_integration(uuid,uuid,text,uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_request_integration(uuid,text,text,uuid,text,text,text,json) TO aegis_provisioner")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_approve_integration(uuid,uuid,text,json,uuid) TO aegis_provisioner")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_revoke_integration(uuid,uuid,text,uuid) TO aegis_provisioner")


def downgrade() -> None:
    op.execute("REVOKE ALL ON FUNCTION public.aegis_request_integration(uuid,text,text,uuid,text,text,text,json) FROM PUBLIC,aegis_provisioner")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_approve_integration(uuid,uuid,text,json,uuid) FROM PUBLIC,aegis_provisioner")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_revoke_integration(uuid,uuid,text,uuid) FROM PUBLIC,aegis_provisioner")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_request_integration(uuid,text,text,uuid,text,text,text,json)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_approve_integration(uuid,uuid,text,json,uuid)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_revoke_integration(uuid,uuid,text,uuid)")
    op.execute("DROP POLICY IF EXISTS integrations_migrator_manage ON public.integrations")
    op.execute("DROP POLICY IF EXISTS integrations_tenant_scope ON public.integrations")
    op.execute("DROP TABLE IF EXISTS public.integrations")
