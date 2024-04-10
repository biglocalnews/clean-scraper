# Usage

You can use the `clean-scraper` command-line tool to scrape available agencies by supplying agency slugs. It will write files, by default, to a hidden directory in the user's home directory. On Apple and Linux systems, this will be `~/.clean-scraper`.

To run a scraper, you must first know its agency "slug" (a state postal code + short agency name):

You can list available agencies (and get their slugs) using the `list` subcommand:

```bash
clean-scraper list
```

You can then run a scraper for an agency using its slug:

```bash
clean-scraper scrape ca_san_diego_pd
```

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
