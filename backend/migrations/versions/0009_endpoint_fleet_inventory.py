"""Add tenant-scoped endpoint fleet inventory function."""

from alembic import op

revision = "0009_endpoint_fleet_inventory"
down_revision = "0008_endpoint_enrollment_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE POLICY audit_events_endpoint_migrator_append ON public.audit_events
      FOR INSERT TO aegis_migrator
      WITH CHECK (
        (resource_type='endpoint_invitation' AND EXISTS (
          SELECT 1 FROM public.endpoint_enrollment_invitations i
          WHERE i.id::text=audit_events.resource_id AND i.tenant_id=audit_events.tenant_id
        ))
        OR
        (resource_type='endpoint_device' AND EXISTS (
          SELECT 1 FROM public.endpoint_devices d
          WHERE d.id::text=audit_events.resource_id AND d.tenant_id=audit_events.tenant_id
        ))
      )
    """)
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_list_devices(
        p_tenant_id uuid, p_actor text, p_limit integer
      ) RETURNS TABLE(
        device_id uuid, platform text, hostname text, agent_version text,
        status text, enrolled_at timestamptz, last_seen_at timestamptz,
        last_sequence bigint, revoked_at timestamptz,
        last_event_type text, last_event_received_at timestamptz
      )
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
      BEGIN
        IF p_tenant_id IS NULL OR p_actor IS NULL OR length(btrim(p_actor)) NOT BETWEEN 1 AND 128
          OR p_actor ~ '[[:cntrl:]]' OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 500
        THEN RAISE EXCEPTION 'invalid endpoint inventory request' USING ERRCODE='22023'; END IF;
        IF NOT EXISTS (SELECT 1 FROM public.tenant_memberships m
          WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor AND m.status='active'
            AND m.role IN ('tenant_admin','security_manager'))
        THEN RAISE EXCEPTION 'endpoint manager role required' USING ERRCODE='42501'; END IF;
        RETURN QUERY
          SELECT d.id,d.platform::text,d.hostname::text,d.agent_version::text,d.status::text,
            d.enrolled_at,d.last_seen_at,d.last_sequence,d.revoked_at,
            recent.event_type,recent.received_at
          FROM public.endpoint_devices d
          LEFT JOIN LATERAL (
            SELECT e.event_type::text,e.received_at
            FROM public.endpoint_events e
            WHERE e.device_id=d.id AND e.tenant_id=p_tenant_id
            ORDER BY e.received_at DESC LIMIT 1
          ) recent ON true
          WHERE d.tenant_id=p_tenant_id
          ORDER BY d.enrolled_at DESC
          LIMIT p_limit;
      END; $function$
    """)
    op.execute("ALTER FUNCTION public.aegis_endpoint_list_devices(uuid,text,integer) OWNER TO aegis_migrator")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_endpoint_list_devices(uuid,text,integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_endpoint_list_devices(uuid,text,integer) TO aegis_provisioner")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_events_endpoint_migrator_append ON public.audit_events")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_endpoint_list_devices(uuid,text,integer) FROM PUBLIC,aegis_provisioner")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_list_devices(uuid,text,integer)")
