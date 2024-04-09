import logging
from pathlib import Path

import click

from . import Runner, utils



@click.group()
def cli():
    pass


@click.command(name="list")
def list_agencies():
    """List all available agencies and their slugs.

    Agency slugs can then used to with the scrape subcommand
    """
    scrapers = utils.get_all_scrapers()
    for state, agency_slugs in utils.get_all_scrapers().items():
        click.echo(f"{state.upper()}:")
        for slug in sorted(agency_slugs):
            click.echo(f" - {state}_{slug}")
    message = (
        "\nTo scrape an agency, pass an agency slug (e.g. ca_san_diego_pd) as the "
        "argument to the scrape command:\n\n\tclean-scraper scrape ca_san_diego_pd\n\n"
    )
    click.echo(message)


@click.command()
@click.argument("agency", nargs=-1)
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
def scrape(
    agency: str,
    data_dir: Path,
    cache_dir: Path,
    delete: bool,
    list_agencies: bool,
    log_level: str,
):
    '''
    Command-line interface for downloading CLEAN files.

    SCRAPERS -- a list of one or more postal codes to scrape. Pass `all` to scrape all supported states and territories.
    '''
    # Set higher log-level on third-party libs that use DEBUG logging,
    # In order to limit debug logging to our library
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)

    # Local logging config
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(message)s")
    logger = logging.getLogger(__name__)

    # Runner config
    data_dir = Path(data_dir)
    cache_dir = Path(cache_dir)
    runner = Runner(data_dir, cache_dir)

    # Delete files, if asked
    if delete:
        logger.info("Deleting files generated from previous scraper run.")
        runner.delete()

    # If the user has asked for all states, give it to 'em
    if "all" in scrapers:
        scrapers = utils.get_all_scrapers()

    # Loop through the states
    for scrape in scrapers:
        # Try running the scraper
        runner.scrape(scrape)

cli.add_command(list_agencies)
cli.add_command(scrape)

if __name__ == "__main__":
    cli()
