import json
from pathlib import Path

from scripts.ci.summarize_scrape_run import build_summary, to_markdown


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


def test_build_summary_handles_empty_json_array(tmp_path: Path):
    agency_slug = "ca_empty_pd"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True)
    (exports_dir / f"{agency_slug}.json").write_text("[]", encoding="utf-8")

    summary = build_summary(exports_dir=exports_dir, agency_slug=agency_slug)

    assert summary["record_count"] == 0
    assert summary["unique_asset_urls"] == 0
    assert summary["unique_case_ids"] == 0
    assert "error" not in summary


def test_build_summary_handles_missing_and_none_fields(tmp_path: Path):
    agency_slug = "ca_partial_pd"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True)
    (exports_dir / f"{agency_slug}.json").write_text(
        json.dumps(
            [
                {"asset_url": None, "case_id": None},
                {"case_id": "CASE-1"},
                {"asset_url": "https://example.org/a.pdf"},
                {},
            ]
        ),
        encoding="utf-8",
    )

    summary = build_summary(exports_dir=exports_dir, agency_slug=agency_slug)

    assert summary["record_count"] == 4
    assert summary["unique_asset_urls"] == 1
    assert summary["unique_case_ids"] == 1
    assert "error" not in summary


def test_build_summary_handles_malformed_json(tmp_path: Path):
    agency_slug = "ca_bad_json_pd"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True)
    (exports_dir / f"{agency_slug}.json").write_text("{not-json}", encoding="utf-8")

    summary = build_summary(exports_dir=exports_dir, agency_slug=agency_slug)

    assert summary["record_count"] == 0
    assert summary["unique_asset_urls"] == 0
    assert summary["unique_case_ids"] == 0
    assert "error" in summary


def test_build_summary_handles_file_access_error(tmp_path: Path, monkeypatch):
    agency_slug = "ca_access_pd"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True)
    (exports_dir / f"{agency_slug}.json").write_text("[]", encoding="utf-8")
    original_read_text = Path.read_text

    def fake_read_text(self, encoding="utf-8"):
        if self.name == f"{agency_slug}.json":
            raise PermissionError("denied")
        return original_read_text(self, encoding=encoding)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    summary = build_summary(exports_dir=exports_dir, agency_slug=agency_slug)

    assert summary["record_count"] == 0
    assert summary["unique_asset_urls"] == 0
    assert summary["unique_case_ids"] == 0
    assert "error" in summary


def test_to_markdown_formats_error_summary():
    markdown = to_markdown(
        {
            "agency_slug": "ca_example_pd",
            "record_count": 1,
            "unique_asset_urls": 1,
            "unique_case_ids": 1,
            "error": "Unable to summarize scrape run: denied",
        }
    )

    assert markdown == (
        "# Scrape run summary for `ca_example_pd`\n"
        "\n"
        "- Records exported: 1\n"
        "- Unique asset URLs: 1\n"
        "- Unique case IDs: 1\n"
        "\n"
        "**Error:** Unable to summarize scrape run: denied\n"
    )
