# AEGIS operational scripts

## Populate the CVE catalogue

AEGIS mirrors the official NVD CVE 2.0 catalogue into the shared
`public.cve_catalog` table. The one-time backfill imports every available
yearly feed from 2002 through the current year, then applies the rolling
`modified` feed so changes to older CVEs are included. The NVD 2002 feed also
contains CVE identifiers from earlier years.

### Prerequisites

1. Apply the database role setup in `deploy/postgres/roles.sql` as the database
   administrator. This creates the dedicated `aegis_ingestor` login role.
2. Apply Alembic migrations using the normal `AEGIS_DATABASE_URL` migrator
   connection. Migration `0006_cve_catalog` creates the catalogue and grants
   the runtime read-only and ingestor write privileges.
3. Set `AEGIS_INGESTOR_DATABASE_URL` to a PostgreSQL/asyncpg connection for
   the `aegis_ingestor` role. Do not use the runtime or migrator credentials.
4. Keep the ingestor database credential in your secret manager. No NVD API
   key is required for the official bulk feeds.

### Run

From the repository root:

```bash
python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend python backend/scripts/sync_nvd_cves.py
```

The import is idempotent and safe to rerun. Each feed is verified against its
publisher-provided SHA-256 metadata before import. CVEs are upserted by their
stable identifier, each feed is marked complete only after its rows have been
written, and unchanged feeds are skipped on later runs. The modified feed is
always processed after yearly feeds.

The command prints a summary of feeds imported/skipped and CVE rows processed. A
successful code merge does not itself populate a live database: run this
command against the configured production database and verify the resulting
row count before describing the catalogue as fully populated.

### Operations

Schedule the same command at least every 2–4 hours to refresh the modified
feed, or run it after the NVD feed publication cycle. The importer uses a
bounded request pause, checksum validation, a 512 MiB compressed feed limit,
and bounded database write batches. Failed feeds are not marked complete and
will be retried on the next run.
