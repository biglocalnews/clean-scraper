import logging
from pathlib import Path

import click

from . import Runner, utils


@click.group()
def cli():
    """Command-line interface for downloading CLEAN files."""
    pass


@click.command(name="list")
def list_agencies():
    """List all available agencies and their slugs.

    Agency slugs can then used with the scrape-meta and scrape subcommands
    """
    for state, agencies in utils.get_all_scrapers().items():
        click.echo(f"{state.upper()}:")
        for record in sorted(agencies, key=lambda x: x["slug"]):
            click.echo(f" - {record['slug']} ({record['agency']})")
    message = (
        "\nTo scrape an agency's file metadata or download files, pass an "
        "agency slug (e.g. ca_san_diego_pd) as the argument to the scrape-meta or scrape subcommands: \n\n"
        "\tclean-scraper scrape-meta ca_san_diego_pd\n"
        "\tclean-scraper scrape ca_san_diego_pd\n"
    )
    click.echo(message)


@click.command()
@click.argument("agency")
@click.option(
    "--data-dir",
    default=utils.CLEAN_DATA_DIR,
    type=click.Path(),
    help="The Path were the results will be saved",
)
@click.option(
    "--cache-dir",
    default=utils.CLEAN_CACHE_DIR,
    type=click.Path(),
    help="The Path where results can be cached",
)
@click.option(
    "--delete/--no-delete",
    default=False,
    help="Delete generated files from the cache",
)
@click.option(
    "--log-level",
    "-l",
    default="INFO",
    type=click.Choice(
        ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), case_sensitive=False
    ),
    help="Set the logging level",
)
@click.option(
    "--throttle",
    "-t",
    default=0,
    help="Set throttle on scraping in seconds. Default is no delay on file downloads.",
)
def scrape_meta(
    agency: str,
    data_dir: Path,
    cache_dir: Path,
    delete: bool,
    log_level: str,
    throttle: int,
):
    """
    Command-line interface for generating metadata CSV about CLEAN files.

    The metadata CSV includes the file's name, URL, size, etc.
    This file is required for downstream uage by the 'scrape' command, which
    relies on it to download the files (in particular the URL for videos and other files).

    AGENCY -- An agency slug (e.g. ca_san_diego_pd)

    Use the 'list' command to see available agencies and their slugs.

      clean-scraper list
    """
    # Set higher log-level on third-party libs that use DEBUG logging,
    # In order to limit debug logging to our library
    logging.getLogger("urllib3").setLevel(logging.ERROR)

    # Local logging config
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(message)s")
    logger = logging.getLogger(__name__)

    # Runner config
    data_dir = Path(data_dir)
    cache_dir = Path(cache_dir)
    runner = Runner(data_dir, cache_dir, throttle)

    # Delete files, if asked
    if delete:
        logger.info("Deleting files generated from previous scraper run.")
        runner.delete()

    # Try running the scraper
    runner.scrape_meta(agency)


@click.command()
@click.argument("agency")
@click.option(
    "--data-dir",
    default=utils.CLEAN_DATA_DIR,
    type=click.Path(),
    help="The Path were generated data/intermediate files will be saved",
)
@click.option(
    "--cache-dir",
    default=utils.CLEAN_CACHE_DIR,
    type=click.Path(),
    help="The Path where results can be cached",
)
@click.option(
    "--filter",
    "-f",
    default="",
    type=str,
    help="Only download files that match a filter str",
)
@click.option(
    "--delete/--no-delete",
    default=False,
    help="Delete generated files from the cache",
)
@click.option(
    "--log-level",
    "-l",
    default="INFO",
    type=click.Choice(
        ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), case_sensitive=False
    ),
    help="Set the logging level",
)
@click.option(
    "--throttle",
    "-t",
    default=0,
    help="Set throttle on scraping in seconds. Default is no delay on file downloads.",
)
def scrape(
    agency: str,
    data_dir: Path,
    cache_dir: Path,
    filter: str,
    delete: bool,
    log_level: str,
    throttle: int,
):
    """
    Command-line interface for downloading CLEAN files.

    AGENCY -- An agency slug (e.g. ca_san_diego_pd) to scrape.

    Use the 'list' command to see available agencies and their slugs.

      clean-scraper list

    The 'scrape-meta' command must be run first to generate a JSON file containing metadata on downloadable files.
    """
    # Set higher log-level on third-party libs that use DEBUG logging,
    # In order to limit debug logging to our library
    logging.getLogger("urllib3").setLevel(logging.ERROR)

    # Local logging config
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(message)s")
    logger = logging.getLogger(__name__)

    # Runner config
    data_dir = Path(data_dir)
    cache_dir = Path(cache_dir)
    runner = Runner(data_dir, cache_dir, throttle)

    # Delete files, if asked
    if delete:
        logger.info("Deleting files generated from previous scraper run.")
        runner.delete()

    # Try running the scraper
    runner.scrape(agency, filter=filter)


cli.add_command(list_agencies)
cli.add_command(scrape_meta)
cli.add_command(scrape)

if __name__ == "__main__":
    cli()
