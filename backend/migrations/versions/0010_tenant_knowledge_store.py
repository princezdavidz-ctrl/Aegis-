"""Add tenant-scoped pgvector knowledge storage with audited ingestion."""

from alembic import op

revision = "0010_tenant_knowledge_store"
down_revision = "0009_endpoint_fleet_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extension installation requires a database administrator. The migration
    # owner must not need SUPERUSER or CREATE EXTENSION privileges.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                RAISE EXCEPTION
                    'pgvector must be enabled by a database administrator before migration 0010';
            END IF;
            IF NOT has_type_privilege(current_user, 'public.vector', 'USAGE') THEN
                RAISE EXCEPTION
                    'migration role requires USAGE on public.vector; grant it before migration 0010';
            END IF;
        END
        $$
    """)

    op.execute("""
        CREATE TABLE public.knowledge_embedding_spaces (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
            provider varchar(80) NOT NULL,
            model varchar(160) NOT NULL,
            model_revision varchar(120) NOT NULL,
            dimensions integer NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_knowledge_embedding_spaces_provider
                CHECK (length(btrim(provider)) BETWEEN 1 AND 80),
            CONSTRAINT ck_knowledge_embedding_spaces_model
                CHECK (length(btrim(model)) BETWEEN 1 AND 160),
            CONSTRAINT ck_knowledge_embedding_spaces_revision
                CHECK (length(btrim(model_revision)) BETWEEN 1 AND 120),
            CONSTRAINT ck_knowledge_embedding_spaces_dimensions
                CHECK (dimensions BETWEEN 1 AND 16000),
            CONSTRAINT uq_knowledge_embedding_spaces_identity
                UNIQUE (tenant_id, provider, model, model_revision, dimensions),
            CONSTRAINT uq_knowledge_embedding_spaces_tenant_id
                UNIQUE (tenant_id, id),
            CONSTRAINT uq_knowledge_embedding_spaces_tenant_id_dimensions
                UNIQUE (tenant_id, id, dimensions)
        )
    """)

    op.execute("""
        CREATE TABLE public.knowledge_documents (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
            document_key varchar(160) NOT NULL,
            title varchar(240) NOT NULL,
            source varchar(80) NOT NULL,
            source_uri text,
            classification varchar(16) NOT NULL DEFAULT 'public',
            content_sha256 varchar(64) NOT NULL,
            updated_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_knowledge_documents_key
                CHECK (length(btrim(document_key)) BETWEEN 1 AND 160),
            CONSTRAINT ck_knowledge_documents_title
                CHECK (length(btrim(title)) BETWEEN 1 AND 240),
            CONSTRAINT ck_knowledge_documents_source
                CHECK (length(btrim(source)) BETWEEN 1 AND 80),
            CONSTRAINT ck_knowledge_documents_source_uri
                CHECK (source_uri IS NULL OR
                    (length(source_uri) <= 2048 AND source_uri ~ '^https://')),
            CONSTRAINT ck_knowledge_documents_classification
                CHECK (classification IN ('public', 'internal', 'restricted')),
            CONSTRAINT ck_knowledge_documents_content_hash
                CHECK (length(content_sha256) = 64 AND content_sha256 ~ '^[0-9a-f]{64},
            CONSTRAINT uq_knowledge_documents_tenant_key
                UNIQUE (tenant_id, document_key),
            CONSTRAINT uq_knowledge_documents_tenant_id
                UNIQUE (tenant_id, id)
        )
    """)

    op.execute("""
        CREATE TABLE public.knowledge_chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            document_id uuid NOT NULL,
            chunk_key varchar(160) NOT NULL,
            chunk_index integer NOT NULL,
            content text NOT NULL,
            content_sha256 varchar(64) NOT NULL,
            embedding_space_id uuid NOT NULL,
            embedding_dimensions integer NOT NULL,
            embedding vector NOT NULL,
            search_vector tsvector GENERATED ALWAYS AS
                (to_tsvector('simple', content)) STORED,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_knowledge_chunks_key
                CHECK (length(btrim(chunk_key)) BETWEEN 1 AND 160),
            CONSTRAINT ck_knowledge_chunks_index
                CHECK (chunk_index >= 0),
            CONSTRAINT ck_knowledge_chunks_content
                CHECK (length(btrim(content)) BETWEEN 1 AND 2000),
            CONSTRAINT ck_knowledge_chunks_content_hash
                CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_knowledge_chunks_dimensions
                CHECK (embedding_dimensions BETWEEN 1 AND 16000),
            CONSTRAINT ck_knowledge_chunks_vector_dimensions
                CHECK (vector_dims(embedding) = embedding_dimensions),
            CONSTRAINT uq_knowledge_chunks_tenant_document_index_space
                UNIQUE (tenant_id, document_id, chunk_index, embedding_space_id),
            CONSTRAINT uq_knowledge_chunks_tenant_document_key_space
                UNIQUE (tenant_id, document_id, chunk_key, embedding_space_id),
            CONSTRAINT fk_knowledge_chunks_tenant_document
                FOREIGN KEY (tenant_id, document_id)
                REFERENCES public.knowledge_documents(tenant_id, id)
                ON DELETE CASCADE,
            CONSTRAINT fk_knowledge_chunks_tenant_embedding_space
                FOREIGN KEY (tenant_id, embedding_space_id, embedding_dimensions)
                REFERENCES public.knowledge_embedding_spaces(tenant_id, id, dimensions)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE INDEX ix_knowledge_embedding_spaces_tenant
        ON public.knowledge_embedding_spaces (tenant_id, provider, model, model_revision)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_documents_tenant_classification
        ON public.knowledge_documents (tenant_id, classification, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_tenant_space
        ON public.knowledge_chunks (tenant_id, embedding_space_id)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_search_vector
        ON public.knowledge_chunks USING gin (search_vector)
    """)

    for table in (
        "knowledge_embedding_spaces",
        "knowledge_documents",
        "knowledge_chunks",
    ):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_read ON public.{table}
            FOR SELECT
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
        """)
        op.execute(f"""
            CREATE POLICY {table}_ingestor_manage ON public.{table}
            FOR ALL TO aegis_ingestor
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
            WITH CHECK (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
        """)
        op.execute(f"""
            CREATE POLICY {table}_migrator_manage ON public.{table}
            FOR ALL TO aegis_migrator
            USING (true) WITH CHECK (true)
        """)

    op.execute("""
        CREATE POLICY audit_events_knowledge_migrator_append ON public.audit_events
        FOR INSERT TO aegis_migrator
        WITH CHECK (
            (resource_type = 'knowledge_document' AND EXISTS (
                SELECT 1 FROM public.knowledge_documents document
                WHERE document.id::text = audit_events.resource_id
                  AND document.tenant_id = audit_events.tenant_id
            ))
            OR
            (resource_type = 'knowledge_chunk' AND EXISTS (
                SELECT 1 FROM public.knowledge_chunks chunk
                WHERE chunk.id::text = audit_events.resource_id
                  AND chunk.tenant_id = audit_events.tenant_id
            ))
        )
    """)

    op.execute("""
        CREATE FUNCTION public.aegis_audit_knowledge_write()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_subject text := nullif(current_setting('aegis.subject', true), '');
            v_context_tenant uuid :=
                nullif(current_setting('aegis.tenant_id', true), '')::uuid;
            v_resource_type text;
            v_action text;
        BEGIN
            IF v_subject IS NULL OR v_context_tenant IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'knowledge write requires matching tenant context'
                    USING ERRCODE = '42501';
            END IF;

            IF TG_TABLE_NAME = 'knowledge_documents' THEN
                v_resource_type := 'knowledge_document';
                v_action := 'knowledge.document.';
            ELSE
                v_resource_type := 'knowledge_chunk';
                v_action := 'knowledge.chunk.';
            END IF;

            v_action := v_action || CASE
                WHEN TG_OP = 'INSERT' THEN 'create'
                ELSE 'update'
            END;

            INSERT INTO public.audit_events (
                event_id, tenant_id, occurred_at, actor_subject, actor_type,
                action, resource_type, resource_id, outcome,
                authorization_reason, correlation_id
            ) VALUES (
                gen_random_uuid(), NEW.tenant_id, clock_timestamp(), v_subject, 'service',
                v_action, v_resource_type, NEW.id::text, 'succeeded',
                'granted', NULL
            );

            RETURN NEW;
        END;
        $function$
    """)
    op.execute("""
        ALTER FUNCTION public.aegis_audit_knowledge_write() OWNER TO aegis_migrator
    """)
    op.execute("""
        REVOKE ALL ON FUNCTION public.aegis_audit_knowledge_write() FROM PUBLIC
    """)
    op.execute("""
        CREATE TRIGGER knowledge_documents_audit_write
        AFTER INSERT OR UPDATE ON public.knowledge_documents
        FOR EACH ROW EXECUTE FUNCTION public.aegis_audit_knowledge_write()
    """)
    op.execute("""
        CREATE TRIGGER knowledge_chunks_audit_write
        AFTER INSERT OR UPDATE ON public.knowledge_chunks
        FOR EACH ROW EXECUTE FUNCTION public.aegis_audit_knowledge_write()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_audit_write ON public.knowledge_chunks")
    op.execute("DROP TRIGGER IF EXISTS knowledge_documents_audit_write ON public.knowledge_documents")
    op.execute("DROP POLICY IF EXISTS audit_events_knowledge_migrator_append ON public.audit_events")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_audit_knowledge_write()")
    op.execute("DROP TABLE IF EXISTS public.knowledge_chunks")
    op.execute("DROP TABLE IF EXISTS public.knowledge_documents")
    op.execute("DROP TABLE IF EXISTS public.knowledge_embedding_spaces")
    # The shared pgvector extension is deliberately retained.
),
            CONSTRAINT uq_knowledge_documents_tenant_key
                UNIQUE (tenant_id, document_key),
            CONSTRAINT uq_knowledge_documents_tenant_id
                UNIQUE (tenant_id, id)
        )
    """)

    op.execute("""
        CREATE TABLE public.knowledge_chunks (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            document_id uuid NOT NULL,
            chunk_key varchar(160) NOT NULL,
            chunk_index integer NOT NULL,
            content text NOT NULL,
            content_sha256 varchar(64) NOT NULL,
            embedding_space_id uuid NOT NULL,
            embedding_dimensions integer NOT NULL,
            embedding vector NOT NULL,
            search_vector tsvector GENERATED ALWAYS AS
                (to_tsvector('simple', content)) STORED,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_knowledge_chunks_key
                CHECK (length(btrim(chunk_key)) BETWEEN 1 AND 160),
            CONSTRAINT ck_knowledge_chunks_index
                CHECK (chunk_index >= 0),
            CONSTRAINT ck_knowledge_chunks_content
                CHECK (length(btrim(content)) BETWEEN 1 AND 2000),
            CONSTRAINT ck_knowledge_chunks_content_hash
                CHECK (length(content_sha256) = 64 AND content_sha256 ~ '^[0-9a-f]{64},
            CONSTRAINT ck_knowledge_chunks_dimensions
                CHECK (embedding_dimensions BETWEEN 1 AND 16000),
            CONSTRAINT ck_knowledge_chunks_vector_dimensions
                CHECK (vector_dims(embedding) = embedding_dimensions),
            CONSTRAINT uq_knowledge_chunks_tenant_document_index_space
                UNIQUE (tenant_id, document_id, chunk_index, embedding_space_id),
            CONSTRAINT uq_knowledge_chunks_tenant_document_key_space
                UNIQUE (tenant_id, document_id, chunk_key, embedding_space_id),
            CONSTRAINT fk_knowledge_chunks_tenant_document
                FOREIGN KEY (tenant_id, document_id)
                REFERENCES public.knowledge_documents(tenant_id, id)
                ON DELETE CASCADE,
            CONSTRAINT fk_knowledge_chunks_tenant_embedding_space
                FOREIGN KEY (tenant_id, embedding_space_id, embedding_dimensions)
                REFERENCES public.knowledge_embedding_spaces(tenant_id, id, dimensions)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE INDEX ix_knowledge_embedding_spaces_tenant
        ON public.knowledge_embedding_spaces (tenant_id, provider, model, model_revision)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_documents_tenant_classification
        ON public.knowledge_documents (tenant_id, classification, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_tenant_space
        ON public.knowledge_chunks (tenant_id, embedding_space_id)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_search_vector
        ON public.knowledge_chunks USING gin (search_vector)
    """)

    for table in (
        "knowledge_embedding_spaces",
        "knowledge_documents",
        "knowledge_chunks",
    ):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_read ON public.{table}
            FOR SELECT
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
        """)
        op.execute(f"""
            CREATE POLICY {table}_ingestor_manage ON public.{table}
            FOR ALL TO aegis_ingestor
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
            WITH CHECK (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
        """)
        op.execute(f"""
            CREATE POLICY {table}_migrator_manage ON public.{table}
            FOR ALL TO aegis_migrator
            USING (true) WITH CHECK (true)
        """)

    op.execute("""
        CREATE POLICY audit_events_knowledge_migrator_append ON public.audit_events
        FOR INSERT TO aegis_migrator
        WITH CHECK (
            (resource_type = 'knowledge_document' AND EXISTS (
                SELECT 1 FROM public.knowledge_documents document
                WHERE document.id::text = audit_events.resource_id
                  AND document.tenant_id = audit_events.tenant_id
            ))
            OR
            (resource_type = 'knowledge_chunk' AND EXISTS (
                SELECT 1 FROM public.knowledge_chunks chunk
                WHERE chunk.id::text = audit_events.resource_id
                  AND chunk.tenant_id = audit_events.tenant_id
            ))
        )
    """)

    op.execute("""
        CREATE FUNCTION public.aegis_audit_knowledge_write()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_subject text := nullif(current_setting('aegis.subject', true), '');
            v_context_tenant uuid :=
                nullif(current_setting('aegis.tenant_id', true), '')::uuid;
            v_resource_type text;
            v_action text;
        BEGIN
            IF v_subject IS NULL OR v_context_tenant IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'knowledge write requires matching tenant context'
                    USING ERRCODE = '42501';
            END IF;

            IF TG_TABLE_NAME = 'knowledge_documents' THEN
                v_resource_type := 'knowledge_document';
                v_action := 'knowledge.document.';
            ELSE
                v_resource_type := 'knowledge_chunk';
                v_action := 'knowledge.chunk.';
            END IF;

            v_action := v_action || CASE
                WHEN TG_OP = 'INSERT' THEN 'create'
                ELSE 'update'
            END;

            INSERT INTO public.audit_events (
                event_id, tenant_id, occurred_at, actor_subject, actor_type,
                action, resource_type, resource_id, outcome,
                authorization_reason, correlation_id
            ) VALUES (
                gen_random_uuid(), NEW.tenant_id, clock_timestamp(), v_subject, 'service',
                v_action, v_resource_type, NEW.id::text, 'succeeded',
                'granted', NULL
            );

            RETURN NEW;
        END;
        $function$
    """)
    op.execute("""
        ALTER FUNCTION public.aegis_audit_knowledge_write() OWNER TO aegis_migrator
    """)
    op.execute("""
        REVOKE ALL ON FUNCTION public.aegis_audit_knowledge_write() FROM PUBLIC
    """)
    op.execute("""
        CREATE TRIGGER knowledge_documents_audit_write
        AFTER INSERT OR UPDATE ON public.knowledge_documents
        FOR EACH ROW EXECUTE FUNCTION public.aegis_audit_knowledge_write()
    """)
    op.execute("""
        CREATE TRIGGER knowledge_chunks_audit_write
        AFTER INSERT OR UPDATE ON public.knowledge_chunks
        FOR EACH ROW EXECUTE FUNCTION public.aegis_audit_knowledge_write()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_audit_write ON public.knowledge_chunks")
    op.execute("DROP TRIGGER IF EXISTS knowledge_documents_audit_write ON public.knowledge_documents")
    op.execute("DROP POLICY IF EXISTS audit_events_knowledge_migrator_append ON public.audit_events")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_audit_knowledge_write()")
    op.execute("DROP TABLE IF EXISTS public.knowledge_chunks")
    op.execute("DROP TABLE IF EXISTS public.knowledge_documents")
    op.execute("DROP TABLE IF EXISTS public.knowledge_embedding_spaces")
    # The shared pgvector extension is deliberately retained.
),
            CONSTRAINT ck_knowledge_chunks_dimensions
                CHECK (embedding_dimensions BETWEEN 1 AND 16000),
            CONSTRAINT ck_knowledge_chunks_vector_dimensions
                CHECK (vector_dims(embedding) = embedding_dimensions),
            CONSTRAINT uq_knowledge_chunks_tenant_document_index_space
                UNIQUE (tenant_id, document_id, chunk_index, embedding_space_id),
            CONSTRAINT uq_knowledge_chunks_tenant_document_key_space
                UNIQUE (tenant_id, document_id, chunk_key, embedding_space_id),
            CONSTRAINT fk_knowledge_chunks_tenant_document
                FOREIGN KEY (tenant_id, document_id)
                REFERENCES public.knowledge_documents(tenant_id, id)
                ON DELETE CASCADE,
            CONSTRAINT fk_knowledge_chunks_tenant_embedding_space
                FOREIGN KEY (tenant_id, embedding_space_id, embedding_dimensions)
                REFERENCES public.knowledge_embedding_spaces(tenant_id, id, dimensions)
                ON DELETE RESTRICT
        )
    """)

    op.execute("""
        CREATE INDEX ix_knowledge_embedding_spaces_tenant
        ON public.knowledge_embedding_spaces (tenant_id, provider, model, model_revision)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_documents_tenant_classification
        ON public.knowledge_documents (tenant_id, classification, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_tenant_space
        ON public.knowledge_chunks (tenant_id, embedding_space_id)
    """)
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_search_vector
        ON public.knowledge_chunks USING gin (search_vector)
    """)

    for table in (
        "knowledge_embedding_spaces",
        "knowledge_documents",
        "knowledge_chunks",
    ):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_read ON public.{table}
            FOR SELECT
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
        """)
        op.execute(f"""
            CREATE POLICY {table}_ingestor_manage ON public.{table}
            FOR ALL TO aegis_ingestor
            USING (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
            WITH CHECK (
                tenant_id = nullif(current_setting('aegis.tenant_id', true), '')::uuid
                AND EXISTS (
                    SELECT 1
                    FROM public.tenant_memberships membership
                    WHERE membership.tenant_id = {table}.tenant_id
                      AND membership.subject = current_setting('aegis.subject', true)
                      AND membership.status = 'active'
                )
            )
        """)
        op.execute(f"""
            CREATE POLICY {table}_migrator_manage ON public.{table}
            FOR ALL TO aegis_migrator
            USING (true) WITH CHECK (true)
        """)

    op.execute("""
        CREATE POLICY audit_events_knowledge_migrator_append ON public.audit_events
        FOR INSERT TO aegis_migrator
        WITH CHECK (
            (resource_type = 'knowledge_document' AND EXISTS (
                SELECT 1 FROM public.knowledge_documents document
                WHERE document.id::text = audit_events.resource_id
                  AND document.tenant_id = audit_events.tenant_id
            ))
            OR
            (resource_type = 'knowledge_chunk' AND EXISTS (
                SELECT 1 FROM public.knowledge_chunks chunk
                WHERE chunk.id::text = audit_events.resource_id
                  AND chunk.tenant_id = audit_events.tenant_id
            ))
        )
    """)

    op.execute("""
        CREATE FUNCTION public.aegis_audit_knowledge_write()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        DECLARE
            v_subject text := nullif(current_setting('aegis.subject', true), '');
            v_context_tenant uuid :=
                nullif(current_setting('aegis.tenant_id', true), '')::uuid;
            v_resource_type text;
            v_action text;
        BEGIN
            IF v_subject IS NULL OR v_context_tenant IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'knowledge write requires matching tenant context'
                    USING ERRCODE = '42501';
            END IF;

            IF TG_TABLE_NAME = 'knowledge_documents' THEN
                v_resource_type := 'knowledge_document';
                v_action := 'knowledge.document.';
            ELSE
                v_resource_type := 'knowledge_chunk';
                v_action := 'knowledge.chunk.';
            END IF;

            v_action := v_action || CASE
                WHEN TG_OP = 'INSERT' THEN 'create'
                ELSE 'update'
            END;

            INSERT INTO public.audit_events (
                event_id, tenant_id, occurred_at, actor_subject, actor_type,
                action, resource_type, resource_id, outcome,
                authorization_reason, correlation_id
            ) VALUES (
                gen_random_uuid(), NEW.tenant_id, clock_timestamp(), v_subject, 'service',
                v_action, v_resource_type, NEW.id::text, 'succeeded',
                'granted', NULL
            );

            RETURN NEW;
        END;
        $function$
    """)
    op.execute("""
        ALTER FUNCTION public.aegis_audit_knowledge_write() OWNER TO aegis_migrator
    """)
    op.execute("""
        REVOKE ALL ON FUNCTION public.aegis_audit_knowledge_write() FROM PUBLIC
    """)
    op.execute("""
        CREATE TRIGGER knowledge_documents_audit_write
        AFTER INSERT OR UPDATE ON public.knowledge_documents
        FOR EACH ROW EXECUTE FUNCTION public.aegis_audit_knowledge_write()
    """)
    op.execute("""
        CREATE TRIGGER knowledge_chunks_audit_write
        AFTER INSERT OR UPDATE ON public.knowledge_chunks
        FOR EACH ROW EXECUTE FUNCTION public.aegis_audit_knowledge_write()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_audit_write ON public.knowledge_chunks")
    op.execute("DROP TRIGGER IF EXISTS knowledge_documents_audit_write ON public.knowledge_documents")
    op.execute("DROP POLICY IF EXISTS audit_events_knowledge_migrator_append ON public.audit_events")
    op.execute("DROP FUNCTION IF EXISTS public.aegis_audit_knowledge_write()")
    op.execute("DROP TABLE IF EXISTS public.knowledge_chunks")
    op.execute("DROP TABLE IF EXISTS public.knowledge_documents")
    op.execute("DROP TABLE IF EXISTS public.knowledge_embedding_spaces")
    # The shared pgvector extension is deliberately retained.
