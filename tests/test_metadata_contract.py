import pytest

from clean.metadata_contract import (
    derive_agency_slug,
    normalize_metadata_record,
    normalize_metadata_records,
)


def test_derive_agency_slug():
    assert derive_agency_slug("/tmp/clean/ca/mesa_city.py") == "ca_mesa_city"


def test_normalize_metadata_record_requires_keys():
    with pytest.raises(ValueError):
        normalize_metadata_record({"asset_url": "x", "name": "y"})


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("asset_url", None),
        ("asset_url", "   "),
        ("name", None),
        ("name", "   "),
        ("parent_page", None),
        ("parent_page", "   "),
    ],
)
def test_normalize_metadata_record_rejects_none_or_empty_required_fields(
    field_name, field_value
):
    record = {
        "asset_url": "https://example.com/asset.pdf",
        "name": "Budget Report",
        "parent_page": "https://example.com/meetings",
    }
    record[field_name] = field_value

    with pytest.raises(ValueError, match=field_name):
        normalize_metadata_record(record)


def test_normalize_metadata_record_normalizes_and_preserves_details():
    details = {"page_count": 7, "nested": {"key": "value"}}
    record = {
        "asset_url": "  https://example.com/asset.pdf  ",
        "name": "  Budget Report  ",
        "parent_page": "  https://example.com/meetings  ",
        "title": "  Fiscal Year 2024  ",
        "details": details,
    }

    normalized = normalize_metadata_record(record)

    assert normalized["asset_url"] == "https://example.com/asset.pdf"
    assert normalized["name"] == "Budget Report"
    assert normalized["parent_page"] == "https://example.com/meetings"
    assert normalized["title"] == "Fiscal Year 2024"
    assert normalized["details"] == details


def test_normalize_metadata_record_normalizes_parent_page_backslashes():
    record = {
        "asset_url": "https://example.com/asset.pdf",
        "name": "Budget Report",
        "parent_page": r"  C:\records\2024\meeting  ",
    }

    normalized = normalize_metadata_record(record)

    assert normalized["parent_page"] == "C:/records/2024/meeting"


def test_normalize_metadata_record_rejects_non_dict_details():
    record = {
        "asset_url": "https://example.com/asset.pdf",
        "name": "Budget Report",
        "parent_page": "https://example.com/meetings",
        "details": ["not", "a", "dict"],
    }

    with pytest.raises(TypeError, match="details must be a dict"):
        normalize_metadata_record(record)


def test_normalize_metadata_records_applies_to_each_row():
    records = [
        {
            "asset_url": " https://example.com/a.pdf ",
            "name": " A ",
            "parent_page": " https://example.com/a ",
            "title": " Alpha ",
        },
        {
            "asset_url": " https://example.com/b.pdf ",
            "name": " B ",
            "parent_page": " https://example.com/b ",
        },
    ]

    normalized_records = normalize_metadata_records(records)

    assert normalized_records[0]["asset_url"] == "https://example.com/a.pdf"
    assert normalized_records[0]["name"] == "A"
    assert normalized_records[0]["parent_page"] == "https://example.com/a"
    assert normalized_records[0]["title"] == "Alpha"
    assert normalized_records[1]["asset_url"] == "https://example.com/b.pdf"
    assert normalized_records[1]["name"] == "B"
    assert normalized_records[1]["parent_page"] == "https://example.com/b"
