from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from clean.runner import Runner


@pytest.fixture
def runner(tmp_path):
    return Runner(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")


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

    with patch("clean.runner.import_module", return_value=fake_module) as mock_import:
        output = runner.scrape_meta(agency_slug)

    mock_import.assert_called_once_with(module_path)
    fake_module.Site.assert_called_once_with(runner.data_dir, runner.cache_dir)
    fake_site.scrape_meta.assert_called_once_with(throttle=0)
    assert output == Path("metadata.csv")
