from unittest.mock import patch

import pytest

from clean.runner import Runner


@pytest.fixture
def runner(tmp_path):
    return Runner(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")


def test_scrape_meta(runner):
    # Call the scrape_meta method with a valid agency slug
    with patch("clean.ca.san_diego_pd.Site.scrape_meta") as mock_scrape_meta:
        runner.scrape_meta("ca_san_diego_pd")
        # Assert that the scrape_meta method was called
        mock_scrape_meta.assert_called_once_with(throttle=0)


def test_scrape(runner):
    with patch("clean.ca.san_diego_pd.Site.scrape") as mock_scrape:
        runner.scrape("ca_san_diego_pd")
        # Assert that the scrape method was called
        mock_scrape.assert_called_once_with(throttle=0, filter="")
