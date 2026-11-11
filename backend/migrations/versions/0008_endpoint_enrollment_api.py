"""Add audited endpoint enrollment, revocation and signed telemetry persistence."""

from alembic import op

revision = "0008_endpoint_enrollment_api"
down_revision = "0007_endpoint_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.endpoint_events (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
            device_id uuid NOT NULL REFERENCES public.endpoint_devices(id) ON DELETE RESTRICT,
            event_id uuid NOT NULL,
            sequence bigint NOT NULL,
            event_type varchar(32) NOT NULL,
            observed_at timestamptz NOT NULL,
            received_at timestamptz NOT NULL DEFAULT now(),
            payload jsonb NOT NULL,
            CONSTRAINT uq_endpoint_event_device_event UNIQUE (device_id, event_id),
            CONSTRAINT uq_endpoint_event_device_sequence UNIQUE (device_id, sequence),
            CONSTRAINT ck_endpoint_event_sequence CHECK (sequence > 0),
            CONSTRAINT ck_endpoint_event_type CHECK (event_type IN ('heartbeat','inventory','process','service','package','security_posture','file_integrity','os_security_event'))
        )
    """)
    op.execute("CREATE INDEX ix_endpoint_events_tenant_received ON public.endpoint_events (tenant_id, received_at DESC)")
    op.execute("ALTER TABLE public.endpoint_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.endpoint_events FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY endpoint_events_tenant_scope ON public.endpoint_events FOR ALL
        USING (
          tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
          AND EXISTS (SELECT 1 FROM public.tenant_memberships m
            WHERE m.tenant_id=endpoint_events.tenant_id
              AND m.subject=current_setting('aegis.subject',true) AND m.status='active')
        )
        WITH CHECK (
          tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
          AND EXISTS (SELECT 1 FROM public.tenant_memberships m
            WHERE m.tenant_id=endpoint_events.tenant_id
              AND m.subject=current_setting('aegis.subject',true) AND m.status='active')
        )
    """)
    op.execute("CREATE POLICY endpoint_events_migrator_manage ON public.endpoint_events FOR ALL TO aegis_migrator USING (true) WITH CHECK (true)")
    op.execute("REVOKE ALL ON public.endpoint_events FROM PUBLIC, aegis_runtime, aegis_provisioner, aegis_ingestor")

    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_create_invitation(
        p_tenant_id uuid, p_actor text, p_actor_type text, p_request_id uuid,
        p_digest text, p_platform text, p_expires_at timestamptz
      ) RETURNS TABLE(invitation_id uuid, tenant_id uuid, platform text, expires_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
      DECLARE v_id uuid := gen_random_uuid(); v_now timestamptz := clock_timestamp();
      BEGIN
        IF p_tenant_id IS NULL OR p_actor IS NULL OR length(btrim(p_actor)) NOT BETWEEN 1 AND 128
          OR p_actor ~ '[[:cntrl:]]' OR p_actor_type IS NULL OR p_actor_type NOT IN ('user','service') OR p_request_id IS NULL
          OR p_digest !~ '^[0-9a-f]{64}$' OR p_platform NOT IN ('windows','linux','macos')
          OR p_expires_at <= v_now OR p_expires_at > v_now + interval '24 hours'
        THEN RAISE EXCEPTION 'invalid endpoint invitation' USING ERRCODE='22023'; END IF;
        IF NOT EXISTS (SELECT 1 FROM public.tenant_memberships m
          WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor AND m.status='active'
            AND m.role IN ('tenant_admin','security_manager'))
        THEN RAISE EXCEPTION 'endpoint manager role required' USING ERRCODE='42501'; END IF;
        INSERT INTO public.endpoint_enrollment_invitations
          (id,tenant_id,token_digest,platform,expires_at,created_by,created_at)
        VALUES (v_id,p_tenant_id,p_digest,p_platform,p_expires_at,p_actor,v_now);
        INSERT INTO public.audit_events(event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
          resource_type,resource_id,outcome,authorization_reason,correlation_id)
        VALUES (gen_random_uuid(),p_tenant_id,v_now,p_actor,p_actor_type,'endpoint.invitation.create',
          'endpoint_invitation',v_id::text,'succeeded','granted',p_request_id);
        RETURN QUERY SELECT v_id,p_tenant_id,p_platform,p_expires_at;
      END; $function$
    """)
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_redeem_invitation(
        p_digest text, p_platform text, p_public_key_b64 text, p_fingerprint text,
        p_hostname text, p_agent_version text
      ) RETURNS TABLE(device_id uuid, tenant_id uuid, platform text, hostname text, agent_version text)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
      DECLARE v_inv public.endpoint_enrollment_invitations%ROWTYPE;
        v_id uuid := gen_random_uuid(); v_now timestamptz := clock_timestamp();
      BEGIN
        IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}
          OR p_public_key_b64 IS NULL OR length(p_public_key_b64) NOT BETWEEN 40 AND 64
          OR p_fingerprint !~ '^[0-9a-f]{64}$'
          OR p_hostname IS NULL OR length(btrim(p_hostname)) NOT BETWEEN 1 AND 255 OR p_hostname ~ '[[:cntrl:]]'
          OR p_agent_version IS NULL OR length(btrim(p_agent_version)) NOT BETWEEN 1 AND 64 OR p_agent_version ~ '[[:cntrl:]]'
        THEN RAISE EXCEPTION 'invalid endpoint enrollment' USING ERRCODE='22023'; END IF;
        UPDATE public.endpoint_enrollment_invitations i
          SET consumed_at=v_now
          WHERE i.token_digest=p_digest AND i.platform=p_platform
            AND i.consumed_at IS NULL AND i.expires_at > v_now
          RETURNING i.* INTO v_inv;
        IF NOT FOUND THEN RAISE EXCEPTION 'invalid or consumed invitation' USING ERRCODE='P0002'; END IF;
        INSERT INTO public.endpoint_devices(id,tenant_id,invitation_id,public_key_b64,
          public_key_fingerprint,platform,hostname,agent_version,status,last_sequence,enrolled_at)
        VALUES(v_id,v_inv.tenant_id,v_inv.id,p_public_key_b64,p_fingerprint,p_platform,
          btrim(p_hostname),btrim(p_agent_version),'active',0,v_now);
        INSERT INTO public.audit_events(event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
          resource_type,resource_id,outcome,authorization_reason,correlation_id)
        VALUES(gen_random_uuid(),v_inv.tenant_id,v_now,'endpoint-enrollment','service','endpoint.enroll',
          'endpoint_device',v_id::text,'succeeded','single_use_invitation',v_inv.id);
        RETURN QUERY SELECT v_id,v_inv.tenant_id,p_platform,btrim(p_hostname),btrim(p_agent_version);
      END; $function$
    """)
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_get_active_key(p_device_id uuid)
      RETURNS TABLE(device_id uuid, tenant_id uuid, public_key_b64 text, status text)
      LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
        SELECT d.id,d.tenant_id,d.public_key_b64::text,d.status::text
        FROM public.endpoint_devices d WHERE d.id=p_device_id AND d.status='active'
      $function$
    """)
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_accept_event(
        p_device_id uuid, p_sequence bigint, p_event_id uuid, p_event_type text,
        p_observed_at timestamptz, p_payload jsonb
      ) RETURNS TABLE(device_id uuid, tenant_id uuid, event_id uuid, sequence bigint, received_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
      DECLARE v_device public.endpoint_devices%ROWTYPE; v_now timestamptz := clock_timestamp();
      BEGIN
        IF p_device_id IS NULL OR p_sequence IS NULL OR p_sequence < 1 OR p_event_id IS NULL
          OR p_event_type IS NULL OR p_event_type NOT IN ('heartbeat','inventory','process','service','package','security_posture','file_integrity','os_security_event')
          OR p_observed_at IS NULL OR p_payload IS NULL OR octet_length(p_payload::text)>32768
        THEN RAISE EXCEPTION 'invalid endpoint event' USING ERRCODE='22023'; END IF;
        SELECT * INTO v_device FROM public.endpoint_devices d
          WHERE d.id=p_device_id AND d.status='active' FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'endpoint unavailable' USING ERRCODE='P0002'; END IF;
        IF p_sequence <= v_device.last_sequence THEN
          RAISE EXCEPTION 'endpoint sequence replay' USING ERRCODE='23505';
        END IF;
        UPDATE public.endpoint_devices SET last_sequence=p_sequence,last_seen_at=v_now
          WHERE id=p_device_id;
        INSERT INTO public.endpoint_events(id,tenant_id,device_id,event_id,sequence,event_type,observed_at,received_at,payload)
        VALUES(gen_random_uuid(),v_device.tenant_id,p_device_id,p_event_id,p_sequence,p_event_type,p_observed_at,v_now,p_payload);
        RETURN QUERY SELECT p_device_id,v_device.tenant_id,p_event_id,p_sequence,v_now;
      END; $function$
    """)
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_revoke_device(
        p_tenant_id uuid, p_device_id uuid, p_actor text, p_actor_type text, p_request_id uuid
      ) RETURNS boolean
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
      DECLARE v_now timestamptz := clock_timestamp();
      BEGIN
        IF p_tenant_id IS NULL OR p_device_id IS NULL OR p_actor IS NULL
          OR p_actor_type IS NULL OR p_actor_type NOT IN ('user','service') OR p_request_id IS NULL
        THEN RAISE EXCEPTION 'invalid endpoint revocation' USING ERRCODE='22023'; END IF;
        IF NOT EXISTS (SELECT 1 FROM public.tenant_memberships m
          WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor AND m.status='active'
            AND m.role IN ('tenant_admin','security_manager'))
        THEN RAISE EXCEPTION 'endpoint manager role required' USING ERRCODE='42501'; END IF;
        UPDATE public.endpoint_devices SET status='revoked',revoked_at=v_now
          WHERE id=p_device_id AND tenant_id=p_tenant_id AND status='active';
        IF NOT FOUND THEN RAISE EXCEPTION 'endpoint not found' USING ERRCODE='P0002'; END IF;
        INSERT INTO public.audit_events(event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
          resource_type,resource_id,outcome,authorization_reason,correlation_id)
        VALUES(gen_random_uuid(),p_tenant_id,v_now,p_actor,p_actor_type,'endpoint.revoke',
          'endpoint_device',p_device_id::text,'succeeded','granted',p_request_id);
        RETURN true;
      END; $function$
    """)
    for signature in (
      "public.aegis_endpoint_create_invitation(uuid,text,text,uuid,text,text,timestamptz)",
      "public.aegis_endpoint_redeem_invitation(text,text,text,text,text,text)",
      "public.aegis_endpoint_get_active_key(uuid)",
      "public.aegis_endpoint_accept_event(uuid,bigint,uuid,text,timestamptz,jsonb)",
      "public.aegis_endpoint_revoke_device(uuid,uuid,text,text,uuid)",
    ):
      op.execute(f"ALTER FUNCTION {signature} OWNER TO aegis_migrator")
      op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
      op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO aegis_provisioner")


def downgrade() -> None:
    for signature in (
      "public.aegis_endpoint_create_invitation(uuid,text,text,uuid,text,text,timestamptz)",
      "public.aegis_endpoint_redeem_invitation(text,text,text,text,text,text)",
      "public.aegis_endpoint_get_active_key(uuid)",
      "public.aegis_endpoint_accept_event(uuid,bigint,uuid,text,timestamptz,jsonb)",
      "public.aegis_endpoint_revoke_device(uuid,uuid,text,text,uuid)",
    ):
      op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC,aegis_provisioner")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_revoke_device(uuid,uuid,text,text,uuid)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_accept_event(uuid,bigint,uuid,text,timestamptz,jsonb)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_get_active_key(uuid)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_redeem_invitation(text,text,text,text,text,text)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_create_invitation(uuid,text,text,uuid,text,text,timestamptz)")
    op.execute("DROP TABLE IF EXISTS public.endpoint_events")
 OR p_platform IS NULL OR p_platform NOT IN ('windows','linux','macos')
          OR p_public_key_b64 IS NULL OR length(p_public_key_b64) NOT BETWEEN 40 AND 64
          OR p_fingerprint !~ '^[0-9a-f]{64}$'
          OR p_hostname IS NULL OR length(btrim(p_hostname)) NOT BETWEEN 1 AND 255 OR p_hostname ~ '[[:cntrl:]]'
          OR p_agent_version IS NULL OR length(btrim(p_agent_version)) NOT BETWEEN 1 AND 64 OR p_agent_version ~ '[[:cntrl:]]'
        THEN RAISE EXCEPTION 'invalid endpoint enrollment' USING ERRCODE='22023'; END IF;
        UPDATE public.endpoint_enrollment_invitations i
          SET consumed_at=v_now
          WHERE i.token_digest=p_digest AND i.platform=p_platform
            AND i.consumed_at IS NULL AND i.expires_at > v_now
          RETURNING i.* INTO v_inv;
        IF NOT FOUND THEN RAISE EXCEPTION 'invalid or consumed invitation' USING ERRCODE='P0002'; END IF;
        INSERT INTO public.endpoint_devices(id,tenant_id,invitation_id,public_key_b64,
          public_key_fingerprint,platform,hostname,agent_version,status,last_sequence,enrolled_at)
        VALUES(v_id,v_inv.tenant_id,v_inv.id,p_public_key_b64,p_fingerprint,p_platform,
          btrim(p_hostname),btrim(p_agent_version),'active',0,v_now);
        INSERT INTO public.audit_events(event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
          resource_type,resource_id,outcome,authorization_reason,correlation_id)
        VALUES(gen_random_uuid(),v_inv.tenant_id,v_now,'endpoint-enrollment','service','endpoint.enroll',
          'endpoint_device',v_id::text,'succeeded','single_use_invitation',v_inv.id);
        RETURN QUERY SELECT v_id,v_inv.tenant_id,p_platform,btrim(p_hostname),btrim(p_agent_version);
      END; $function$
    """)
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_get_active_key(p_device_id uuid)
      RETURNS TABLE(device_id uuid, tenant_id uuid, public_key_b64 text, status text)
      LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
        SELECT d.id,d.tenant_id,d.public_key_b64::text,d.status::text
        FROM public.endpoint_devices d WHERE d.id=p_device_id AND d.status='active'
      $function$
    """)
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_accept_event(
        p_device_id uuid, p_sequence bigint, p_event_id uuid, p_event_type text,
        p_observed_at timestamptz, p_payload jsonb
      ) RETURNS TABLE(device_id uuid, tenant_id uuid, event_id uuid, sequence bigint, received_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
      DECLARE v_device public.endpoint_devices%ROWTYPE; v_now timestamptz := clock_timestamp();
      BEGIN
        IF p_device_id IS NULL OR p_sequence < 1 OR p_event_id IS NULL
          OR p_event_type NOT IN ('heartbeat','inventory','process','service','package','security_posture','file_integrity','os_security_event')
          OR p_observed_at IS NULL OR p_payload IS NULL OR octet_length(p_payload::text)>32768
        THEN RAISE EXCEPTION 'invalid endpoint event' USING ERRCODE='22023'; END IF;
        SELECT * INTO v_device FROM public.endpoint_devices d
          WHERE d.id=p_device_id AND d.status='active' FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'endpoint unavailable' USING ERRCODE='P0002'; END IF;
        IF p_sequence <= v_device.last_sequence THEN
          RAISE EXCEPTION 'endpoint sequence replay' USING ERRCODE='23505';
        END IF;
        UPDATE public.endpoint_devices SET last_sequence=p_sequence,last_seen_at=v_now
          WHERE id=p_device_id;
        INSERT INTO public.endpoint_events(id,tenant_id,device_id,event_id,sequence,event_type,observed_at,received_at,payload)
        VALUES(gen_random_uuid(),v_device.tenant_id,p_device_id,p_event_id,p_sequence,p_event_type,p_observed_at,v_now,p_payload);
        RETURN QUERY SELECT p_device_id,v_device.tenant_id,p_event_id,p_sequence,v_now;
      END; $function$
    """)
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_revoke_device(
        p_tenant_id uuid, p_device_id uuid, p_actor text, p_actor_type text, p_request_id uuid
      ) RETURNS boolean
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
      DECLARE v_now timestamptz := clock_timestamp();
      BEGIN
        IF p_tenant_id IS NULL OR p_device_id IS NULL OR p_actor IS NULL
          OR p_actor_type NOT IN ('user','service') OR p_request_id IS NULL
        THEN RAISE EXCEPTION 'invalid endpoint revocation' USING ERRCODE='22023'; END IF;
        IF NOT EXISTS (SELECT 1 FROM public.tenant_memberships m
          WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor AND m.status='active'
            AND m.role IN ('tenant_admin','security_manager'))
        THEN RAISE EXCEPTION 'endpoint manager role required' USING ERRCODE='42501'; END IF;
        UPDATE public.endpoint_devices SET status='revoked',revoked_at=v_now
          WHERE id=p_device_id AND tenant_id=p_tenant_id AND status='active';
        IF NOT FOUND THEN RAISE EXCEPTION 'endpoint not found' USING ERRCODE='P0002'; END IF;
        INSERT INTO public.audit_events(event_id,tenant_id,occurred_at,actor_subject,actor_type,action,
          resource_type,resource_id,outcome,authorization_reason,correlation_id)
        VALUES(gen_random_uuid(),p_tenant_id,v_now,p_actor,p_actor_type,'endpoint.revoke',
          'endpoint_device',p_device_id::text,'succeeded','granted',p_request_id);
        RETURN true;
      END; $function$
    """)
    for signature in (
      "public.aegis_endpoint_create_invitation(uuid,text,text,uuid,text,text,timestamptz)",
      "public.aegis_endpoint_redeem_invitation(text,text,text,text,text,text)",
      "public.aegis_endpoint_get_active_key(uuid)",
      "public.aegis_endpoint_accept_event(uuid,bigint,uuid,text,timestamptz,jsonb)",
      "public.aegis_endpoint_revoke_device(uuid,uuid,text,text,uuid)",
    ):
      op.execute(f"ALTER FUNCTION {signature} OWNER TO aegis_migrator")
      op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
      op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO aegis_provisioner")


def downgrade() -> None:
    for signature in (
      "public.aegis_endpoint_create_invitation(uuid,text,text,uuid,text,text,timestamptz)",
      "public.aegis_endpoint_redeem_invitation(text,text,text,text,text,text)",
      "public.aegis_endpoint_get_active_key(uuid)",
      "public.aegis_endpoint_accept_event(uuid,bigint,uuid,text,timestamptz,jsonb)",
      "public.aegis_endpoint_revoke_device(uuid,uuid,text,text,uuid)",
    ):
      op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC,aegis_provisioner")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_revoke_device(uuid,uuid,text,text,uuid)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_accept_event(uuid,bigint,uuid,text,timestamptz,jsonb)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_get_active_key(uuid)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_redeem_invitation(text,text,text,text,text,text)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_create_invitation(uuid,text,text,uuid,text,text,timestamptz)")
    op.execute("DROP TABLE IF EXISTS public.endpoint_events")
