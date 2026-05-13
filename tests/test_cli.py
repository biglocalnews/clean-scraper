from unittest.mock import ANY, patch

import pytest
from click.testing import CliRunner

from clean.cli import cli


@pytest.fixture
def mock_runner():
    with patch("clean.cli.Runner") as MockRunner:
        mock_runner = MockRunner.return_value
        mock_runner.scrape_meta.return_value = "Invoked scrape_meta"
        mock_runner.download_agency.return_value = "Invoked download_agency"
        yield mock_runner


@pytest.mark.usefixtures("set_default_env", "create_scraper_dir")
def test_cli_list():
    """Test the `list' command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])
    for slug in [
        "ca_san_diego_pd",
        "ca_ventura_county_sheriff",
        "ca_mesa_city",
        "ca_pomona_pd",
    ]:
        assert slug in result.stdout


@pytest.mark.usefixtures("set_default_env", "create_scraper_dir")
def test_cli_scrape_meta_command(mock_runner):
    """Test the 'scrape-meta' command."""

    def run_scrape_meta(agency, progress_callback=None):
        if progress_callback:
            progress_callback(
                {"action": "scrape_meta", "phase": "start", "agency": agency}
            )
            progress_callback(
                {"action": "scrape_meta", "phase": "complete", "agency": agency}
            )

    mock_runner.scrape_meta.side_effect = run_scrape_meta
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "scrape-meta",
            "ca_san_diego_pd",
            "--log-level",
            "DEBUG",
            "--throttle",
            "1",
        ],
    )
    assert result.exit_code == 0
    mock_runner.scrape_meta.assert_called_once_with(
        "ca_san_diego_pd", progress_callback=ANY
    )
    assert "Starting metadata scrape for ca_san_diego_pd" in result.stdout
    assert "Completed metadata scrape for ca_san_diego_pd" in result.stdout


@pytest.mark.usefixtures("set_default_env", "create_scraper_dir")
def test_cli_download_agency_command(mock_runner):
    """Test the 'download-agency' command with progress output."""

    def run_download_agency(agency, progress_callback=None):
        if progress_callback:
            progress_callback(
                {
                    "action": "download_agency",
                    "phase": "manifest_loaded",
                    "agency": agency,
                    "total_items": 3,
                }
            )
            progress_callback(
                {
                    "action": "download_agency",
                    "phase": "item_download_complete",
                    "agency": agency,
                    "item_index": 1,
                    "total_items": 3,
                }
            )
            progress_callback(
                {
                    "action": "download_agency",
                    "phase": "complete",
                    "agency": agency,
                    "downloaded_items": 1,
                    "total_items": 3,
                }
            )

    mock_runner.download_agency.side_effect = run_download_agency

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "download-agency",
            "ca_san_diego_pd",
            "--log-level",
            "DEBUG",
        ],
    )
    assert result.exit_code == 0
    mock_runner.download_agency.assert_called_once_with(
        "ca_san_diego_pd", progress_callback=ANY
    )
    assert "Loaded 3 records for download from ca_san_diego_pd" in result.stdout
    assert "Downloaded item 1/3 for ca_san_diego_pd" in result.stdout
    assert "Completed downloads for ca_san_diego_pd (1/3 downloaded)" in result.stdout
