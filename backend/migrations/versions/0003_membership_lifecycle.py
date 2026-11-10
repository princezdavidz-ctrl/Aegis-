"""Add tenant-admin membership invitation, acceptance and lifecycle operations."""
from alembic import op

revision = "0003_membership_lifecycle"
down_revision = "0002_tenant_provisioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_memberships ADD COLUMN IF NOT EXISTS invitation_expires_at timestamptz")
    op.execute("CREATE POLICY tenants_migrator_read ON tenants FOR SELECT TO aegis_migrator USING (true)")
    op.execute("CREATE POLICY tenant_memberships_migrator_manage ON tenant_memberships FOR ALL TO aegis_migrator USING (true) WITH CHECK (true)")
    op.execute("""
        CREATE FUNCTION public.aegis_list_tenant_members(p_tenant_id uuid, p_actor_subject text)
        RETURNS TABLE (member_id uuid, member_subject text, member_role text, member_status text,
                       member_created_at timestamptz, member_invitation_expires_at timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
        BEGIN
            IF p_tenant_id IS NULL OR p_actor_subject IS NULL OR length(btrim(p_actor_subject)) = 0
                THEN RAISE EXCEPTION 'invalid tenant or actor' USING ERRCODE = '22023'; END IF;
            IF NOT EXISTS (SELECT 1 FROM public.tenant_memberships actor
                WHERE actor.tenant_id = p_tenant_id AND actor.subject = p_actor_subject
                  AND actor.status = 'active' AND actor.role = 'tenant_admin')
                THEN RAISE EXCEPTION 'tenant administrator required' USING ERRCODE = '42501'; END IF;
            RETURN QUERY SELECT member.id, member.subject, member.role, member.status,
                member.created_at, member.invitation_expires_at
                FROM public.tenant_memberships member WHERE member.tenant_id = p_tenant_id
                ORDER BY member.created_at, member.subject;
        END; $function$
    """)
    op.execute("""
        CREATE FUNCTION public.aegis_manage_tenant_member(
            p_tenant_id uuid, p_target_subject text, p_target_role text, p_action text,
            p_actor_subject text, p_actor_type text, p_request_id uuid
        )
        RETURNS TABLE (member_id uuid, member_subject text, member_role text, member_status text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
        DECLARE v_member public.tenant_memberships%ROWTYPE;
            v_now timestamptz := clock_timestamp(); v_audit_action text;
        BEGIN
            IF p_tenant_id IS NULL OR p_target_subject IS NULL OR length(btrim(p_target_subject)) = 0
               OR length(p_target_subject) > 128 OR p_target_subject ~ '[[:cntrl:]]'
               OR p_actor_subject IS NULL OR length(btrim(p_actor_subject)) = 0
               OR length(p_actor_subject) > 128 OR p_actor_subject ~ '[[:cntrl:]]'
               OR p_actor_type IS NULL OR p_actor_type NOT IN ('user', 'service')
               OR p_request_id IS NULL OR p_action IS NULL
                THEN RAISE EXCEPTION 'invalid membership operation input' USING ERRCODE = '22023'; END IF;
            IF NOT EXISTS (SELECT 1 FROM public.tenant_memberships actor
                WHERE actor.tenant_id = p_tenant_id AND actor.subject = p_actor_subject
                  AND actor.status = 'active' AND actor.role = 'tenant_admin')
                THEN RAISE EXCEPTION 'tenant administrator required' USING ERRCODE = '42501'; END IF;
            PERFORM set_config('aegis.subject', p_actor_subject, true);
            PERFORM set_config('aegis.tenant_id', p_tenant_id::text, true);
            IF p_action = 'invite' THEN
                IF p_target_role IS NULL OR p_target_role NOT IN ('security_manager', 'analyst', 'viewer')
                    THEN RAISE EXCEPTION 'unsupported invited role' USING ERRCODE = '22023'; END IF;
                IF EXISTS (SELECT 1 FROM public.tenant_memberships existing
                    WHERE existing.tenant_id = p_tenant_id AND existing.subject = p_target_subject)
                    THEN RAISE EXCEPTION 'membership already exists' USING ERRCODE = '23505'; END IF;
                INSERT INTO public.tenant_memberships
                    (id, tenant_id, subject, role, status, invitation_expires_at, created_at)
                VALUES (gen_random_uuid(), p_tenant_id, p_target_subject, p_target_role,
                    'pending', v_now + interval '7 days', v_now) RETURNING * INTO v_member;
                v_audit_action := 'tenant.member.invite';
            ELSE
                SELECT * INTO v_member FROM public.tenant_memberships member
                    WHERE member.tenant_id = p_tenant_id AND member.subject = p_target_subject FOR UPDATE;
                IF NOT FOUND THEN RAISE EXCEPTION 'membership not found' USING ERRCODE = 'P0002'; END IF;
                IF p_action = 'change_role' THEN
                    IF p_target_role IS NULL OR p_target_role NOT IN ('security_manager', 'analyst', 'viewer')
                        THEN RAISE EXCEPTION 'unsupported membership role' USING ERRCODE = '22023'; END IF;
                    IF v_member.role = 'tenant_admin' AND v_member.status = 'active'
                       AND p_target_role <> 'tenant_admin'
                       AND (SELECT count(*) FROM public.tenant_memberships admins
                            WHERE admins.tenant_id = p_tenant_id AND admins.role = 'tenant_admin'
                              AND admins.status = 'active') <= 1
                        THEN RAISE EXCEPTION 'cannot remove the last active tenant administrator'
                            USING ERRCODE = '23514'; END IF;
                    UPDATE public.tenant_memberships SET role = p_target_role
                        WHERE id = v_member.id RETURNING * INTO v_member;
                    v_audit_action := 'tenant.member.role_change';
                ELSIF p_action IN ('suspend', 'revoke') THEN
                    IF v_member.role = 'tenant_admin' AND v_member.status = 'active'
                       AND (SELECT count(*) FROM public.tenant_memberships admins
                            WHERE admins.tenant_id = p_tenant_id AND admins.role = 'tenant_admin'
                              AND admins.status = 'active') <= 1
                        THEN RAISE EXCEPTION 'cannot remove the last active tenant administrator'
                            USING ERRCODE = '23514'; END IF;
                    UPDATE public.tenant_memberships
                        SET status = CASE WHEN p_action = 'suspend' THEN 'suspended' ELSE 'revoked' END
                        WHERE id = v_member.id RETURNING * INTO v_member;
                    v_audit_action := CASE WHEN p_action = 'suspend'
                        THEN 'tenant.member.suspend' ELSE 'tenant.member.revoke' END;
                ELSE RAISE EXCEPTION 'unsupported membership action' USING ERRCODE = '22023';
                END IF;
            END IF;
            INSERT INTO public.audit_events
                (event_id, tenant_id, occurred_at, actor_subject, actor_type, action,
                 resource_type, resource_id, outcome, authorization_reason, correlation_id)
            VALUES (gen_random_uuid(), p_tenant_id, v_now, p_actor_subject, p_actor_type,
                v_audit_action, 'tenant_membership', v_member.id::text, 'succeeded', 'granted', p_request_id);
            RETURN QUERY SELECT v_member.id, v_member.subject, v_member.role, v_member.status;
        END; $function$
    """)
    op.execute("""
        CREATE FUNCTION public.aegis_accept_tenant_invitation(
            p_tenant_slug text, p_actor_subject text, p_request_id uuid
        )
        RETURNS TABLE (tenant_id uuid, tenant_slug text, member_role text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
        DECLARE v_tenant_id uuid; v_role text; v_member_id uuid; v_now timestamptz := clock_timestamp();
        BEGIN
            IF p_tenant_slug IS NULL OR length(p_tenant_slug) NOT BETWEEN 3 AND 63
               OR p_actor_subject IS NULL OR length(btrim(p_actor_subject)) = 0
               OR length(p_actor_subject) > 128 OR p_actor_subject ~ '[[:cntrl:]]'
               OR p_request_id IS NULL
                THEN RAISE EXCEPTION 'invalid invitation acceptance input' USING ERRCODE = '22023'; END IF;
            SELECT tenant.id INTO v_tenant_id FROM public.tenants tenant WHERE tenant.slug = p_tenant_slug;
            IF v_tenant_id IS NULL THEN RAISE EXCEPTION 'invitation not found' USING ERRCODE = 'P0002'; END IF;
            PERFORM set_config('aegis.subject', p_actor_subject, true);
            PERFORM set_config('aegis.tenant_id', v_tenant_id::text, true);
            UPDATE public.tenant_memberships member SET status = 'active'
                WHERE member.tenant_id = v_tenant_id AND member.subject = p_actor_subject
                  AND member.status = 'pending' AND member.invitation_expires_at > v_now
                RETURNING member.id, member.role INTO v_member_id, v_role;
            IF v_member_id IS NULL THEN RAISE EXCEPTION 'invitation not found' USING ERRCODE = 'P0002'; END IF;
            INSERT INTO public.audit_events
                (event_id, tenant_id, occurred_at, actor_subject, actor_type, action,
                 resource_type, resource_id, outcome, authorization_reason, correlation_id)
            VALUES (gen_random_uuid(), v_tenant_id, v_now, p_actor_subject, 'user',
                'tenant.member.accept', 'tenant_membership', v_member_id::text,
                'succeeded', 'granted', p_request_id);
            RETURN QUERY SELECT v_tenant_id, p_tenant_slug, v_role;
        END; $function$
    """)
    op.execute("ALTER FUNCTION public.aegis_list_tenant_members(uuid, text) OWNER TO aegis_migrator")
    op.execute("ALTER FUNCTION public.aegis_manage_tenant_member(uuid, text, text, text, text, text, uuid) OWNER TO aegis_migrator")
    op.execute("ALTER FUNCTION public.aegis_accept_tenant_invitation(text, text, uuid) OWNER TO aegis_migrator")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_list_tenant_members(uuid, text) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_manage_tenant_member(uuid, text, text, text, text, text, uuid) FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_accept_tenant_invitation(text, text, uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_list_tenant_members(uuid, text) TO aegis_provisioner")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_manage_tenant_member(uuid, text, text, text, text, text, uuid) TO aegis_provisioner")
    op.execute("GRANT EXECUTE ON FUNCTION public.aegis_accept_tenant_invitation(text, text, uuid) TO aegis_provisioner")


def downgrade() -> None:
    op.execute("REVOKE ALL ON FUNCTION public.aegis_list_tenant_members(uuid, text) FROM PUBLIC, aegis_provisioner")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_manage_tenant_member(uuid, text, text, text, text, text, uuid) FROM PUBLIC, aegis_provisioner")
    op.execute("REVOKE ALL ON FUNCTION public.aegis_accept_tenant_invitation(text, text, uuid) FROM PUBLIC, aegis_provisioner")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_list_tenant_members(uuid, text)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_manage_tenant_member(uuid, text, text, text, text, text, uuid)")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_accept_tenant_invitation(text, text, uuid)")
    op.execute("DROP POLICY IF EXISTS tenant_memberships_migrator_manage ON tenant_memberships")
    op.execute("DROP POLICY IF EXISTS tenants_migrator_read ON tenants")
    op.execute("ALTER TABLE tenant_memberships DROP COLUMN IF EXISTS invitation_expires_at")
