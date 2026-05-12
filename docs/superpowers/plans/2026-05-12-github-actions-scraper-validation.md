# GitHub Actions Scraper Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an on-demand GitHub Actions workflow that runs a selected scraper in an ephemeral environment, captures reviewable outputs, and publishes run artifacts plus a concise human-readable summary.

**Architecture:** Add a dedicated `workflow_dispatch` workflow that executes `clean-scraper scrape-meta <agency_slug>` with an isolated output directory on the runner. Generate a deterministic run summary from the exported JSON using a small Python helper script (covered by tests), publish summary to `$GITHUB_STEP_SUMMARY`, and upload run artifacts for inspection. Keep implementation minimal and repo-pattern aligned with existing Pipenv-based CI.

**Tech Stack:** GitHub Actions, Python 3.11, Pipenv, pytest, existing `clean.cli` command path, `actions/upload-artifact@v4`

---

## File Structure

- Create: `.github/workflows/scraper-validation.yml`
  Purpose: Manual workflow to run a scraper in GitHub-hosted ephemeral runners and upload outputs for review.

- Create: `scripts/ci/summarize_scrape_run.py`
  Purpose: Convert exported scraper JSON into review-friendly metrics and Markdown summary.

- Create: `tests/test_ci_summarize_scrape_run.py`
  Purpose: Unit coverage for summary generation logic (normal + edge cases).

- Modify: `docs/maintainers.md`
  Purpose: Document how maintainers trigger and review scraper validation runs in Actions.

### Task 1: Add failing tests for scrape run summary generation

**Files:**
- Create: `tests/test_ci_summarize_scrape_run.py`
- Test: `tests/test_ci_summarize_scrape_run.py`

- [ ] **Step 1: Write the failing test file for summary outputs**

```python
import json
from pathlib import Path

from scripts.ci.summarize_scrape_run import build_summary


def test_build_summary_counts_records_and_urls(tmp_path: Path):
    agency_slug = "ca_example_pd"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True)
    (exports_dir / f"{agency_slug}.json").write_text(
        json.dumps(
            [
                {
                    "asset_url": "https://example.org/a.pdf",
                    "case_id": "CASE-1",
                    "name": "a.pdf",
                },
                {
                    "asset_url": "https://example.org/b.pdf",
                    "case_id": "CASE-2",
                    "name": "b.pdf",
                },
                {
                    "asset_url": "https://example.org/a.pdf",
                    "case_id": "CASE-1",
                    "name": "a.pdf",
                },
            ]
        ),
        encoding="utf-8",
    )

    summary = build_summary(exports_dir=exports_dir, agency_slug=agency_slug)

    assert summary["agency_slug"] == agency_slug
    assert summary["record_count"] == 3
    assert summary["unique_asset_urls"] == 2
    assert summary["unique_case_ids"] == 2


def test_build_summary_handles_missing_file(tmp_path: Path):
    summary = build_summary(
        exports_dir=tmp_path / "exports", agency_slug="ca_missing_pd"
    )
    assert summary["record_count"] == 0
    assert summary["unique_asset_urls"] == 0
    assert summary["unique_case_ids"] == 0
    assert "error" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
pytest -q tests/test_ci_summarize_scrape_run.py
```

Expected: FAIL with `ModuleNotFoundError` (or missing `build_summary`) until implementation exists.

- [ ] **Step 3: Commit failing test scaffold**

```bash
git add tests/test_ci_summarize_scrape_run.py
git commit -m "test: add failing tests for scrape run summary helper"
```

### Task 2: Implement summary helper script with minimal logic

**Files:**
- Create: `scripts/ci/summarize_scrape_run.py`
- Modify: `tests/test_ci_summarize_scrape_run.py` (if import/shape adjustments needed)
- Test: `tests/test_ci_summarize_scrape_run.py`

- [ ] **Step 1: Implement minimal `build_summary` and CLI entrypoint**

```python
import argparse
import json
from pathlib import Path
from typing import Any


def build_summary(exports_dir: Path, agency_slug: str) -> dict[str, Any]:
    export_path = exports_dir / f"{agency_slug}.json"
    if not export_path.exists():
        return {
            "agency_slug": agency_slug,
            "record_count": 0,
            "unique_asset_urls": 0,
            "unique_case_ids": 0,
            "error": f"Export file not found: {export_path}",
        }

    records = json.loads(export_path.read_text(encoding="utf-8"))
    asset_urls = {
        record.get("asset_url") for record in records if record.get("asset_url")
    }
    case_ids = {record.get("case_id") for record in records if record.get("case_id")}

    return {
        "agency_slug": agency_slug,
        "record_count": len(records),
        "unique_asset_urls": len(asset_urls),
        "unique_case_ids": len(case_ids),
        "export_path": str(export_path),
    }


def to_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"## Scraper validation summary: `{summary['agency_slug']}`",
        "",
        f"- Records exported: **{summary['record_count']}**",
        f"- Unique asset URLs: **{summary['unique_asset_urls']}**",
        f"- Unique case IDs: **{summary['unique_case_ids']}**",
    ]
    if summary.get("error"):
        lines.append(f"- Error: `{summary['error']}`")
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
```

- [ ] **Step 2: Run test to verify it passes**

Run:
```bash
pytest -q tests/test_ci_summarize_scrape_run.py
```

Expected: PASS (2 passed).

- [ ] **Step 3: Commit helper implementation**

```bash
git add scripts/ci/summarize_scrape_run.py tests/test_ci_summarize_scrape_run.py
git commit -m "feat: add scrape run summary helper for CI artifact review"
```

### Task 3: Add workflow_dispatch scraper validation workflow

**Files:**
- Create: `.github/workflows/scraper-validation.yml`
- Modify: `scripts/ci/summarize_scrape_run.py` (only if runtime args need adjustment)
- Test: `.github/workflows/scraper-validation.yml` (yaml validity + dry command run)

- [ ] **Step 1: Add workflow with manual inputs and isolated run directory**

```yaml
name: Scraper validation

on:
  workflow_dispatch:
    inputs:
      agency_slug:
        description: "Scraper slug to run (example: ca_san_diego_pd)"
        required: true
        type: string
      throttle_seconds:
        description: "Throttle seconds passed to scrape-meta"
        required: false
        default: "0"
        type: string
      python_version:
        description: "Python version for runner"
        required: false
        default: "3.11"
        type: string
      upload_cache:
        description: "Upload cache directory artifact"
        required: false
        default: false
        type: boolean

jobs:
  scrape-meta:
    runs-on: ubuntu-latest
    env:
      CLEAN_OUTPUT_DIR: ${{ github.workspace }}/.clean-scraper
      AGENCY_SLUG: ${{ inputs.agency_slug }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python_version }}
          cache: pipenv

      - name: Install pipenv
        run: curl -s https://raw.githubusercontent.com/pypa/pipenv/master/get-pipenv.py | python
        shell: bash

      - name: Install dependencies
        run: pipenv install --dev --python="$(which python)"
        shell: bash

      - name: Run scraper metadata export
        run: |
          pipenv run python -m clean.cli scrape-meta "$AGENCY_SLUG" --throttle "${{ inputs.throttle_seconds }}" -l INFO
        shell: bash

      - name: Build run summary
        run: |
          pipenv run python scripts/ci/summarize_scrape_run.py \
            --exports-dir "$CLEAN_OUTPUT_DIR/exports" \
            --agency-slug "$AGENCY_SLUG" \
            --summary-md "$CLEAN_OUTPUT_DIR/run-summary.md" \
            --summary-json "$CLEAN_OUTPUT_DIR/run-summary.json"
          cat "$CLEAN_OUTPUT_DIR/run-summary.md" >> "$GITHUB_STEP_SUMMARY"
        shell: bash

      - name: Upload export artifact
        uses: actions/upload-artifact@v4
        with:
          name: scraper-exports-${{ inputs.agency_slug }}-${{ github.run_number }}
          path: ${{ env.CLEAN_OUTPUT_DIR }}/exports
          if-no-files-found: error

      - name: Upload run summary artifact
        uses: actions/upload-artifact@v4
        with:
          name: scraper-summary-${{ inputs.agency_slug }}-${{ github.run_number }}
          path: |
            ${{ env.CLEAN_OUTPUT_DIR }}/run-summary.md
            ${{ env.CLEAN_OUTPUT_DIR }}/run-summary.json
          if-no-files-found: error

      - name: Upload cache artifact (optional)
        if: ${{ inputs.upload_cache }}
        uses: actions/upload-artifact@v4
        with:
          name: scraper-cache-${{ inputs.agency_slug }}-${{ github.run_number }}
          path: ${{ env.CLEAN_OUTPUT_DIR }}/cache
          if-no-files-found: warn
```

- [ ] **Step 2: Run repo checks to validate workflow changes do not break standards**

Run:
```bash
make format
pytest -q tests/test_ci_summarize_scrape_run.py
pytest -q
```

Expected:
- `make format` passes (or auto-fixes then passes on rerun)
- new targeted test passes
- full test suite passes

- [ ] **Step 3: Commit workflow**

```bash
git add .github/workflows/scraper-validation.yml scripts/ci/summarize_scrape_run.py tests/test_ci_summarize_scrape_run.py
git commit -m "feat: add manual GitHub Actions scraper validation workflow"
```

### Task 4: Document maintainer run/review procedure

**Files:**
- Modify: `docs/maintainers.md`
- Test: `docs/maintainers.md` (render/readability check)

- [ ] **Step 1: Add instructions for running workflow and reviewing artifacts**

```markdown
## GitHub Actions scraper validation

Use the **Scraper validation** workflow (`.github/workflows/scraper-validation.yml`) to run a scraper without local machine bloat.

1. Open **Actions** → **Scraper validation** → **Run workflow**
2. Enter `agency_slug` (example: `ca_san_diego_pd`) and optional throttle/cache settings
3. After completion, review:
   - Step summary panel (record + URL counts)
   - `scraper-exports-*` artifact for exported JSON
   - `scraper-summary-*` artifact for machine + markdown summary
   - Optional `scraper-cache-*` artifact for debugging
```

- [ ] **Step 2: Commit docs update**

```bash
git add docs/maintainers.md
git commit -m "docs: add maintainer guide for scraper validation workflow"
```

### Task 5: End-to-end verification and PR handoff

**Files:**
- Modify: none (verification + PR metadata only)

- [ ] **Step 1: Run final local verification**

Run:
```bash
make format
pytest -q
```

Expected: all checks pass with no unresolved formatting/lint/type/test failures.

- [ ] **Step 2: Push branch and verify workflow appears in Actions**

Run:
```bash
git push origin pr-standardization-integration
gh workflow list --repo biglocalnews/clean-scraper | grep "Scraper validation"
```

Expected:
- push succeeds
- workflow is listed

- [ ] **Step 3: Trigger one manual validation run for smoke confirmation**

Run:
```bash
gh workflow run scraper-validation.yml \
  --repo biglocalnews/clean-scraper \
  -f agency_slug=ca_san_diego_pd \
  -f throttle_seconds=0 \
  -f python_version=3.11 \
  -f upload_cache=false
```

Expected: run is queued successfully.

- [ ] **Step 4: Capture run ID and review-ready links**

Run:
```bash
gh run list --repo biglocalnews/clean-scraper --workflow scraper-validation.yml --limit 1
```

Expected: latest run entry visible with run ID for reviewers.

- [ ] **Step 5: Commit any final nits and prepare PR note**

```bash
git add -A
git commit -m "chore: finalize scraper validation workflow polish" || true
```

If no additional changes exist, skip this commit and proceed with PR update comments only.
