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
