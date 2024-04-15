from unittest.mock import patch

import pytest
from click.testing import CliRunner

from clean.cli import cli


@pytest.fixture
def mock_runner():
    with patch("clean.cli.Runner") as MockRunner:
        mock_runner = MockRunner.return_value
        mock_runner.scrape.return_value = "Invoked scrape"
        mock_runner.scrape_meta.return_value = "Invoked scrape"
        yield mock_runner


@pytest.mark.usefixtures("set_default_env", "create_scraper_dir")
def test_cli_scrape_command(mock_runner):
    """Test the 'scrape' command."""
    runner = CliRunner()
    runner.invoke(
        cli,
        [
            "scrape",
            "ca_san_diego_pd",
            "--log-level",
            "DEBUG",
            "--throttle",
            "1",
        ],
    )
    mock_runner.scrape.assert_called_once_with("ca_san_diego_pd", filter="")


@pytest.mark.usefixtures("set_default_env", "create_scraper_dir")
def test_cli_scrape_meta_command(mock_runner):
    """Test the 'scrape' command."""
    runner = CliRunner()
    runner.invoke(
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
    mock_runner.scrape_meta.assert_called_once_with("ca_san_diego_pd")
