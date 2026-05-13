import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from clean.runner import Runner


@pytest.fixture
def runner(tmp_path):
    return Runner(
        data_dir=tmp_path / "exports",
        cache_dir=tmp_path / "cache",
        assets_dir=tmp_path / "assets",
    )


@pytest.mark.parametrize(
    "agency_slug,module_path",
    [
        ("ca_san_diego_pd", "clean.ca.san_diego_pd"),
        ("ca_ventura_county_sheriff", "clean.ca.ventura_county_sheriff"),
        ("ca_mesa_city", "clean.ca.mesa_city"),
        ("ca_pomona_pd", "clean.ca.pomona_pd"),
    ],
)
def test_scrape_meta(runner, agency_slug, module_path):
    fake_site = MagicMock()
    fake_site.scrape_meta.return_value = Path("metadata.csv")
    fake_module = SimpleNamespace(Site=MagicMock(return_value=fake_site))
    progress_events = []

    with patch("clean.runner.import_module", return_value=fake_module) as mock_import:
        output = runner.scrape_meta(
            agency_slug, progress_callback=progress_events.append
        )

    mock_import.assert_called_once_with(module_path)
    fake_module.Site.assert_called_once_with(runner.data_dir, runner.cache_dir)
    fake_site.scrape_meta.assert_called_once_with(throttle=0)
    assert progress_events == [
        {"action": "scrape_meta", "phase": "start", "agency": agency_slug},
        {"action": "scrape_meta", "phase": "running", "agency": agency_slug},
        {
            "action": "scrape_meta",
            "phase": "complete",
            "agency": agency_slug,
            "output_path": "metadata.csv",
        },
    ]
    assert output == Path("metadata.csv")


def test_download_agency_reports_progress_per_item(runner):
    agency_slug = "ca_san_diego_pd"
    json_path = runner.data_dir / f"{agency_slug}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {"asset_url": "https://example.com/a.pdf", "case_id": "1", "name": "a.pdf"},
        {"asset_url": None, "case_id": "2", "name": "missing.pdf"},
        {"asset_url": "https://example.com/b.pdf", "case_id": "3", "name": "b.pdf"},
    ]
    json_path.write_text(json.dumps(data))

    fake_response = MagicMock()
    fake_response.content = b"file-content"
    progress_events = []

    with (
        patch("clean.runner.requests.get", return_value=fake_response) as mock_get,
        patch("clean.runner.datetime") as mock_datetime,
    ):
        mock_datetime.now.return_value.strftime.return_value = "20240102"
        output_dir = runner.download_agency(
            agency_slug, progress_callback=progress_events.append
        )

    assert output_dir == runner.assets_dir / "san_diego_pd"
    assert mock_get.call_count == 2
    assert (
        output_dir / "20240102/assets/1/a.pdf"
    ).exists(), "first downloaded file should exist"
    assert (output_dir / "20240102/assets/3/b.pdf").exists()

    assert [event["phase"] for event in progress_events] == [
        "start",
        "manifest_loaded",
        "item_download_started",
        "item_download_complete",
        "item_skipped",
        "item_download_started",
        "item_download_complete",
        "complete",
    ]
    assert progress_events[1]["total_items"] == 3
    assert progress_events[2]["item_index"] == 1
    assert progress_events[4]["item_index"] == 2
    assert progress_events[-1]["downloaded_items"] == 2
