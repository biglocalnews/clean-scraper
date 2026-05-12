from pathlib import Path
from typing import Iterable, Mapping, cast

from clean.utils import MetadataDict

REQUIRED_KEYS = ("asset_url", "name", "parent_page")


def derive_agency_slug(module_file: str) -> str:
    module_path = Path(module_file)
    return f"{module_path.parent.name}_{module_path.stem}"


def normalize_metadata_record(record: Mapping[str, object]) -> MetadataDict:
    missing_keys = [key for key in REQUIRED_KEYS if key not in record]
    if missing_keys:
        raise ValueError(f"Missing required metadata keys: {', '.join(missing_keys)}")

    title = record.get("title")
    normalized: MetadataDict = {
        "asset_url": str(record["asset_url"]).strip(),
        "name": str(record["name"]).strip(),
        "parent_page": str(record["parent_page"]).strip(),
        "title": None if title is None else str(title).strip(),
    }

    details = record.get("details")
    if details is not None:
        normalized["details"] = cast(dict, details)

    case_id = record.get("case_id")
    if case_id is not None:
        normalized["case_id"] = str(case_id).strip()

    return normalized


def normalize_metadata_records(
    records: Iterable[Mapping[str, object]],
) -> list[MetadataDict]:
    return [normalize_metadata_record(record) for record in records]
