import argparse
import json
from pathlib import Path
from typing import Any


def build_summary(exports_dir: Path, agency_slug: str) -> dict[str, Any]:
    export_path = exports_dir / f"{agency_slug}.json"
    summary: dict[str, Any] = {
        "agency_slug": agency_slug,
        "record_count": 0,
        "unique_asset_urls": 0,
        "unique_case_ids": 0,
    }

    try:
        records = json.loads(export_path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Expected a JSON array of scrape records")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        summary["error"] = f"Unable to summarize scrape run: {exc}"
        return summary

    summary["record_count"] = len(records)
    summary["unique_asset_urls"] = len(
        {
            record.get("asset_url")
            for record in records
            if isinstance(record, dict) and record.get("asset_url")
        }
    )
    summary["unique_case_ids"] = len(
        {
            record.get("case_id")
            for record in records
            if isinstance(record, dict) and record.get("case_id")
        }
    )
    return summary


def to_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# Scrape run summary for `{summary['agency_slug']}`",
        "",
        f"- Records exported: {summary['record_count']}",
        f"- Unique asset URLs: {summary['unique_asset_urls']}",
        f"- Unique case IDs: {summary['unique_case_ids']}",
    ]
    if summary.get("error"):
        lines.extend(["", f"**Error:** {summary['error']}"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exports-dir", required=True, type=Path)
    parser.add_argument("--agency-slug", required=True)
    parser.add_argument("--summary-md", required=True, type=Path)
    parser.add_argument("--summary-json", required=True, type=Path)
    args = parser.parse_args()

    summary = build_summary(args.exports_dir, args.agency_slug)
    args.summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    args.summary_md.write_text(to_markdown(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
