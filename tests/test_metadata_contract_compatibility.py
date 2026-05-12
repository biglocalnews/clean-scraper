import json
from pathlib import Path

import pytest

from clean.metadata_contract import normalize_metadata_records

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "metadata_contract"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "san_diego_sample.json",
        "fresno_county_sheriff_sample.json",
        "los_angeles_sheriff_sample.json",
    ],
)
def test_normalize_metadata_records_compatibility_with_established_scrapers(
    fixture_name: str,
):
    with (FIXTURE_DIR / fixture_name).open(encoding="utf-8") as source:
        sample = json.load(source)

    rows = normalize_metadata_records(sample)

    assert rows
    for row in rows:
        assert {"asset_url", "name", "parent_page"}.issubset(row)
