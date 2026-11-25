"""Expose tenant-scoped endpoint heartbeat timestamps for fleet health."""

from alembic import op

revision = "0012_endpoint_heartbeat_health"
down_revision = "0011_knowledge_class_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE FUNCTION public.aegis_endpoint_list_heartbeats(
        p_tenant_id uuid, p_actor text, p_limit integer
      ) RETURNS TABLE(device_id uuid, last_heartbeat_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
      AS $function$
      BEGIN
        IF p_tenant_id IS NULL OR p_actor IS NULL
          OR length(btrim(p_actor)) NOT BETWEEN 1 AND 128
          OR p_actor ~ '[[:cntrl:]]' OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 500
        THEN RAISE EXCEPTION 'invalid endpoint heartbeat request' USING ERRCODE='22023'; END IF;
        IF NOT EXISTS (
          SELECT 1 FROM public.tenant_memberships m
          WHERE m.tenant_id=p_tenant_id AND m.subject=p_actor AND m.status='active'
            AND m.role IN ('tenant_admin','security_manager')
        ) THEN
          RAISE EXCEPTION 'endpoint manager role required' USING ERRCODE='42501';
        END IF;
        RETURN QUERY
          SELECT d.id, max(e.received_at)
          FROM public.endpoint_devices d
          LEFT JOIN public.endpoint_events e
            ON e.device_id=d.id AND e.tenant_id=p_tenant_id AND e.event_type='heartbeat'
          WHERE d.tenant_id=p_tenant_id
          GROUP BY d.id,d.enrolled_at
          ORDER BY d.enrolled_at DESC
          LIMIT p_limit;
      END;
      $function$
    """)
    op.execute("ALTER FUNCTION public.aegis_endpoint_list_heartbeats(uuid,text,integer) OWNER TO aegis_migrator")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_endpoint_list_heartbeats(uuid,text,integer) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_endpoint_list_heartbeats(uuid,text,integer) TO aegis_provisioner")


def downgrade() -> None:
    op.execute("REVOKE ALL ON FUNCTION public.aegis_endpoint_list_heartbeats(uuid,text,integer) FROM PUBLIC,aegis_provisioner")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_endpoint_list_heartbeats(uuid,text,integer)")
