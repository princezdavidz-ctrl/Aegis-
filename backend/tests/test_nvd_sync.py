"""Unit tests for the official NVD CVE feed importer."""

import gzip
import json
import tempfile
from pathlib import Path

import pytest
from app.vulnerability_intel.nvd_sync import (
    _iter_vulnerabilities,
    feed_names,
    normalize_cve,
    parse_meta_sha256,
)


def test_feed_names_cover_historical_years_and_modified_feed():
    names = feed_names(2026)
    assert names[0] == "nvdcve-2.0-2002"
    assert names[-2] == "nvdcve-2.0-2026"
    assert names[-1] == "nvdcve-2.0-modified"
    assert len(names) == 26


def test_feed_names_reject_unsupported_early_year():
    with pytest.raises(ValueError):
        feed_names(2001)


def test_parse_meta_sha256_is_case_insensitive():
    digest = "a" * 64
    assert parse_meta_sha256(f"lastModifiedDate: now\nsha256: {digest.upper()}\n") == digest


def test_parse_meta_sha256_rejects_missing_digest():
    with pytest.raises(ValueError):
        parse_meta_sha256("lastModifiedDate: now\nsize: 123\n")


def test_normalize_cve_preserves_full_source_payload():
    row = normalize_cve(
        {
            "cve": {
                "id": "CVE-2025-12345",
                "sourceIdentifier": "security@example.test",
                "vulnStatus": "Analyzed",
                "published": "2025-01-02T03:04:05.000",
                "lastModified": "2025-01-03T03:04:05.000",
                "descriptions": [{"lang": "en", "value": "A test vulnerability"}],
                "metrics": {"cvssMetricV31": [{"type": "Primary"}]},
                "weaknesses": [{"source": "nvd", "type": "Primary"}],
                "configurations": [{"nodes": []}],
                "references": [{"url": "https://example.test/advisory"}],
            }
        },
        "nvdcve-2.0-2025",
    )
    assert row["cve_id"] == "CVE-2025-12345"
    assert row["published_at"].isoformat() == "2025-01-02T03:04:05+00:00"
    assert row["published_at"].utcoffset().total_seconds() == 0
    assert row["source_feed"] == "nvdcve-2.0-2025"
    assert '"A test vulnerability"' in row["descriptions"]
    assert '"cvssMetricV31"' in row["metrics"]
    assert '"https://example.test/advisory"' in row["references_json"]
    assert '"id":"CVE-2025-12345"' in row["raw_json"]


@pytest.mark.parametrize("identifier", ["", "CVE-25-1234", "CVE-2025-ABC", "not-a-cve"])
def test_normalize_cve_rejects_invalid_identifiers(identifier):
    with pytest.raises(ValueError):
        normalize_cve({"cve": {"id": identifier}}, "feed")


def test_normalize_cve_parses_zulu_timestamp():
    row = normalize_cve(
        {"cve": {"id": "CVE-2025-54321", "published": "2025-01-02T03:04:05.000Z"}},
        "nvdcve-2.0-2025",
    )
    assert row["published_at"].isoformat() == "2025-01-02T03:04:05+00:00"


def test_feed_entries_are_yielded_from_gzip_incrementally():
    payload = {
        "vulnerabilities": [
            {"cve": {"id": "CVE-2025-10001"}},
            {"cve": {"id": "CVE-2025-10002"}},
        ]
    }
    with tempfile.NamedTemporaryFile(suffix=".json.gz") as feed:
        with gzip.open(feed.name, "wt", encoding="utf-8") as compressed:
            json.dump(payload, compressed)
        entries = _iter_vulnerabilities(Path(feed.name))
        first = next(entries)
        assert first["cve"]["id"] == "CVE-2025-10001"
        assert next(entries)["cve"]["id"] == "CVE-2025-10002"
        with pytest.raises(StopIteration):
            next(entries)
