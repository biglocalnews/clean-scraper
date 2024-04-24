# Usage

You can use the `clean-scraper` command-line tool and various subcommands (more on that below) to scrape available agencies by supplying an agency "slug".

These are short, headline-y names that combine a state postal code and a terse name for the agency.

For example, `ca_san_diego_pd` is the slug for the San Diego Police Department in California.

Metadata about available videos and other files, along with the downloads themselves, are written to a hidden directory in the user's home directory by default. On Apple and Linux systems, this will be `~/.clean-scraper`.

## Install

```bash
pip install git+https://github.com/biglocalnews/clean-scraper.git
```

## Find the agency slug

To run a scraper, you must first know its agency "slug" (a state postal code + short agency name):

You can list available agencies (and get their slugs) using the `list` subcommand:

```bash
clean-scraper list
```

You can then run a scraper for an agency using its slug:

```bash
# Scrape metadata about available files
clean-scraper scrape-meta ca_san_diego_pd

# Download files
clean-scraper scrape ca_san_diego_pd
```

> **NOTE**: Always run `scrape-meta` at least once initially. It generates output required by the `scrape` subcommand.

To use the `clean` library in Python, import an agency's scraper and run it directly.

```python
from clean.ca import san_diego_pd

san_diego_pd.scrape()
```

## Configuration

You can set the `CLEAN_OUTPUT_DIR` environment variable to specify a different download location.

Use the `--help` flag to view additional configuration and usage options:

```bash
Usage: clean-scraper [OPTIONS] COMMAND [ARGS]...

  Command-line interface for downloading CLEAN files.

Options:
  --help  Show this message and exit.

Commands:
  list    List all available agencies and their slugs.
  scrape  Command-line interface for downloading CLEAN files.
```
