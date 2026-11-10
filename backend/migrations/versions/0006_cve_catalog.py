"""Create the shared public CVE catalogue and resumable NVD feed checkpoints."""

from alembic import op

revision = "0006_cve_catalog"
down_revision = "0005_asset_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE public.cve_catalog (
            cve_id varchar(32) PRIMARY KEY,
            source_identifier varchar(255),
            vuln_status varchar(32),
            published_at timestamptz,
            last_modified_at timestamptz,
            descriptions jsonb NOT NULL DEFAULT '[]'::jsonb,
            metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
            weaknesses jsonb NOT NULL DEFAULT '[]'::jsonb,
            configurations jsonb NOT NULL DEFAULT '[]'::jsonb,
            references_json jsonb NOT NULL DEFAULT '[]'::jsonb,
            raw_json jsonb NOT NULL,
            source_feed varchar(64) NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_cve_catalog_id CHECK (cve_id ~ '^CVE-[0-9]{4}-[0-9]{4,}$')
        )
    """)
    op.execute("CREATE INDEX ix_cve_catalog_published ON public.cve_catalog (published_at DESC)")
    op.execute("CREATE INDEX ix_cve_catalog_modified ON public.cve_catalog (last_modified_at DESC)")
    op.execute("CREATE INDEX ix_cve_catalog_status ON public.cve_catalog (vuln_status)")
    op.execute("CREATE INDEX ix_cve_catalog_metrics_gin ON public.cve_catalog USING gin (metrics)")
    op.execute("CREATE INDEX ix_cve_catalog_raw_gin ON public.cve_catalog USING gin (raw_json jsonb_path_ops)")

    op.execute("""
        CREATE TABLE public.nvd_feed_sync (
            feed_name varchar(64) PRIMARY KEY,
            sha256 char(64) NOT NULL,
            meta_text varchar(4000) NOT NULL,
            imported_count integer NOT NULL CHECK (imported_count >= 0),
            completed_at timestamptz NOT NULL
        )
    """)

    # The catalogue is shared public reference data, not customer-owned data.
    # Runtime access is read-only. A dedicated least-privilege ingestor writes it.
    op.execute("REVOKE ALL ON public.cve_catalog, public.nvd_feed_sync FROM PUBLIC")
    op.execute("GRANT SELECT ON public.cve_catalog TO aegis_runtime")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.cve_catalog TO aegis_ingestor")
    op.execute("GRANT SELECT ON public.nvd_feed_sync TO aegis_runtime")
    op.execute("GRANT SELECT, INSERT, UPDATE ON public.nvd_feed_sync TO aegis_ingestor")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.nvd_feed_sync")
    op.execute("DROP TABLE IF EXISTS public.cve_catalog")
