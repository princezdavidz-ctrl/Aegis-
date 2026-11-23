"""Enforce membership-role access to restricted knowledge at the RLS boundary."""

from alembic import op

revision = "0011_knowledge_classification_access"
down_revision = "0010_tenant_knowledge_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Public/internal knowledge is available to every active tenant member.
    # Restricted knowledge is limited to tenant_admin and security_manager.
    # The role is read from the live membership row on every SQL statement;
    # it is never trusted from a browser, model response or cached app claim.
    op.execute(
        "DROP POLICY IF EXISTS knowledge_documents_tenant_read "
        "ON public.knowledge_documents"
    )
    op.execute(
        "DROP POLICY IF EXISTS knowledge_documents_ingestor_manage "
        "ON public.knowledge_documents"
    )
    op.execute(
        "DROP POLICY IF EXISTS knowledge_chunks_tenant_read "
        "ON public.knowledge_chunks"
    )
    op.execute(
        "DROP POLICY IF EXISTS knowledge_chunks_ingestor_manage "
        "ON public.knowledge_chunks"
    )

    op.execute("""
        CREATE POLICY knowledge_documents_tenant_read
        ON public.knowledge_documents
        FOR SELECT
        USING (
            tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
            AND EXISTS (
                SELECT 1
                FROM public.tenant_memberships AS membership
                WHERE membership.tenant_id = knowledge_documents.tenant_id
                  AND membership.subject = current_setting('aegis.subject', true)
                  AND membership.status = 'active'
                  AND (
                      knowledge_documents.classification IN ('public', 'internal')
                      OR membership.role IN ('tenant_admin', 'security_manager')
                  )
            )
        )
    """)
    op.execute("""
        CREATE POLICY knowledge_documents_ingestor_manage
        ON public.knowledge_documents
        FOR ALL TO aegis_ingestor
        USING (
            tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
            AND EXISTS (
                SELECT 1
                FROM public.tenant_memberships AS membership
                WHERE membership.tenant_id = knowledge_documents.tenant_id
                  AND membership.subject = current_setting('aegis.subject', true)
                  AND membership.status = 'active'
                  AND (
                      knowledge_documents.classification IN ('public', 'internal')
                      OR membership.role IN ('tenant_admin', 'security_manager')
                  )
            )
        )
        WITH CHECK (
            tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
            AND EXISTS (
                SELECT 1
                FROM public.tenant_memberships AS membership
                WHERE membership.tenant_id = knowledge_documents.tenant_id
                  AND membership.subject = current_setting('aegis.subject', true)
                  AND membership.status = 'active'
                  AND (
                      knowledge_documents.classification IN ('public', 'internal')
                      OR membership.role IN ('tenant_admin', 'security_manager')
                  )
            )
        )
    """)
    op.execute("""
        CREATE POLICY knowledge_chunks_tenant_read
        ON public.knowledge_chunks
        FOR SELECT
        USING (
            tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
            AND EXISTS (
                SELECT 1
                FROM public.tenant_memberships AS membership
                JOIN public.knowledge_documents AS document
                  ON document.tenant_id = membership.tenant_id
                WHERE membership.tenant_id = knowledge_chunks.tenant_id
                  AND membership.subject = current_setting('aegis.subject', true)
                  AND membership.status = 'active'
                  AND document.tenant_id = knowledge_chunks.tenant_id
                  AND document.id = knowledge_chunks.document_id
                  AND (
                      document.classification IN ('public', 'internal')
                      OR membership.role IN ('tenant_admin', 'security_manager')
                  )
            )
        )
    """)
    op.execute("""
        CREATE POLICY knowledge_chunks_ingestor_manage
        ON public.knowledge_chunks
        FOR ALL TO aegis_ingestor
        USING (
            tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
            AND EXISTS (
                SELECT 1
                FROM public.tenant_memberships AS membership
                JOIN public.knowledge_documents AS document
                  ON document.tenant_id = membership.tenant_id
                WHERE membership.tenant_id = knowledge_chunks.tenant_id
                  AND membership.subject = current_setting('aegis.subject', true)
                  AND membership.status = 'active'
                  AND document.tenant_id = knowledge_chunks.tenant_id
                  AND document.id = knowledge_chunks.document_id
                  AND (
                      document.classification IN ('public', 'internal')
                      OR membership.role IN ('tenant_admin', 'security_manager')
                  )
            )
        )
        WITH CHECK (
            tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
            AND EXISTS (
                SELECT 1
                FROM public.tenant_memberships AS membership
                JOIN public.knowledge_documents AS document
                  ON document.tenant_id = membership.tenant_id
                WHERE membership.tenant_id = knowledge_chunks.tenant_id
                  AND membership.subject = current_setting('aegis.subject', true)
                  AND membership.status = 'active'
                  AND document.tenant_id = knowledge_chunks.tenant_id
                  AND document.id = knowledge_chunks.document_id
                  AND (
                      document.classification IN ('public', 'internal')
                      OR membership.role IN ('tenant_admin', 'security_manager')
                  )
            )
        )
    """)


def downgrade() -> None:
    for table in ("knowledge_documents", "knowledge_chunks"):
        op.execute(
            f"DROP POLICY IF EXISTS {table}_tenant_read ON public.{table}"
        )
        op.execute(
            f"DROP POLICY IF EXISTS {table}_ingestor_manage ON public.{table}"
        )
        op.execute(f"""
            CREATE POLICY {table}_tenant_read
            ON public.{table}
            FOR SELECT
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships AS membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
        """)
        op.execute(f"""
            CREATE POLICY {table}_ingestor_manage
            ON public.{table}
            FOR ALL TO aegis_ingestor
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships AS membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
            WITH CHECK (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships AS membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
        """)
