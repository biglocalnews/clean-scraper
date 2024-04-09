# Usage

You can use the `clean-scraper` command-line tool to scrape available agencies by supplying agency slugs. It will write files, by default, to a hidden directory in the user's home directory. On Apple and Linux systems, this will be `~/.clean-scraper`.

```bash
# Scrape a single state
clean-scraper ca_san_diego_pd
```

To use the `clean` library in Python, import an agency's scraper and run it directly.

```python
from clean.ca import import san_diego_pd as sdpd

sdpd.scrape()
```

## Configuration

You can set the `CLEAN_OUTPUT_DIR` environment variable to specify a different download location.

Use the `--help` flag to view additional configuration and usage options:

```bash
clean-scraper --help

Usage: python -m warn [OPTIONS] [STATES]...

  Command-line interface for downloading law enforcement agency files.

  SLUGS -- a list of one or agency slugs to scrape.

Options:
  --data-dir PATH                 The Path were the results will be saved
  --cache-dir PATH                The Path where results can be cached
  --delete / --no-delete          Delete generated files from the cache
  -l, --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
                                  Set the logging level
  --help                          Show this message and exit.
```
