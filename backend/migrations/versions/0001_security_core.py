"""Create tenant, membership and append-only audit tables with PostgreSQL RLS."""

from alembic import op

from app.db.base import Base
from app.db import models  # noqa: F401 — register all mapped tables

revision = "0001_security_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Only create tables owned by this initial migration. Creating all current
    # metadata here would also create tables introduced by later migrations,
    # causing those migrations to fail with DuplicateTableError.
    Base.metadata.create_all(
        bind=bind,
        tables=[
            models.Tenant.__table__,
            models.TenantMembership.__table__,
            models.AuditRecord.__table__,
        ],
    )

    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenants_member_read ON tenants
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1
                FROM tenant_memberships AS membership
                WHERE membership.tenant_id = tenants.id
                  AND membership.subject = current_setting('aegis.subject', true)
                  AND membership.status = 'active'
            )
        )
        """
    )

    op.execute("ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_memberships FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_memberships_self_read ON tenant_memberships
        FOR SELECT
        USING (subject = current_setting('aegis.subject', true))
        """
    )

    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_events_tenant_scope ON audit_events
        FOR ALL
        USING (
            tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION aegis_reject_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION aegis_reject_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS aegis_reject_audit_mutation()")
    Base.metadata.drop_all(
        bind=op.get_bind(),
        tables=[
            models.AuditRecord.__table__,
            models.TenantMembership.__table__,
            models.Tenant.__table__,
        ],
    )
