# Maintainers

Some helpful bits to help manage this project.

## Linting

Use `make format` to identify and clean up linting and other errors that will get flagged by pre-commit hooks run by GitHub Actions.

## Testing

### Setup

Install `tox` globally

```bash
pip install tox
```

Using `pyenv` to install Python versions 3.8 - 3.11.

## Test locally

```bash
tox
```

If you update library requirements (aka the `Pipfile[.lock]`), make sure to regenerate the `requirements.txt` used by `tox`:

```bash
pipenv requirements > requirements.txt
```

## GitHub Actions scraper validation

Use the `.github/workflows/scraper-validation.yml` workflow to run a scraper in GitHub Actions and review the exported outputs.

1. Open **Actions** in the repository.
2. Select **Scraper validation**.
3. Click **Run workflow**.
4. Enter `agency_slug` and, if needed, optional inputs like `throttle_seconds`, `python_version`, and `upload_cache`.
5. Start the workflow run.

After the run completes, review:

- The step summary panel in the workflow run
- The `scraper-exports-*` artifact
- The `scraper-summary-*` artifact
- The optional `scraper-cache-*` artifact
