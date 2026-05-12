import json
from pathlib import Path

from scripts.ci.summarize_scrape_run import build_summary


def test_build_summary_counts_records_and_unique_values(tmp_path: Path):
    agency_slug = "ca_example_pd"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True)
    (exports_dir / f"{agency_slug}.json").write_text(
        json.dumps(
            [
                {"asset_url": "https://example.org/a.pdf", "case_id": "CASE-1"},
                {"asset_url": "https://example.org/b.pdf", "case_id": "CASE-2"},
                {"asset_url": "https://example.org/a.pdf", "case_id": "CASE-1"},
            ]
        ),
        encoding="utf-8",
    )

    summary = build_summary(exports_dir=exports_dir, agency_slug=agency_slug)

    assert summary["agency_slug"] == agency_slug
    assert summary["record_count"] == 3
    assert summary["unique_asset_urls"] == 2
    assert summary["unique_case_ids"] == 2


def test_build_summary_handles_missing_export_file(tmp_path: Path):
    summary = build_summary(tmp_path / "exports", "ca_missing_pd")

    assert summary["agency_slug"] == "ca_missing_pd"
    assert summary["record_count"] == 0
    assert summary["unique_asset_urls"] == 0
    assert summary["unique_case_ids"] == 0
    assert "error" in summary
