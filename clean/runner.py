import logging
import shutil
from importlib import import_module
from pathlib import Path

from . import utils

logger = logging.getLogger(__name__)


class Runner:
    """High-level interface for agency files.

    Provides methods for:
     - scraping an agency
     - deleting files from prior runs

    The data_dir and cache_dir arguments can specify any
    location, but it's not a bad idea to have them as sibling directories:

        /tmp/CLEAN/cache   # source files (HTML, videos, CSV of metadata for downloaded files, etc.)
        /tmp/CLEAN/exports # transformed files

    Args:
        data_dir (str): Path where final output files are saved.
        cache_dir (str): Path to store intermediate files used in ETL.
        throttle (int): Seconds to delay scraper actions (default: 0)

    """

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
        throttle: int = 0,
    ):
        """Initialize a new instance."""
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.throttle = throttle

    def scrape_meta(self, agency_slug: str) -> Path:
        """Scrape metadata  for the provided agency.

        Args:
            agency_slug (str): Unique scraper slug composed of two-letter state postal code and agency slug: e.g. ca_san_diego_pd

        Returns: a Path object leading to a CSV file.
        """
        # Get the module
        if agency_slug[2] != "_":
            message = "Scraper slugs must be prefixed with the state postal code and an underscore. "
            message += "Example: clean-scraper scrape-meta ca_san_diego_pd. "
            message += f"Your supplied agency, {agency_slug}, has no state prefix."
            logger.critical(message)

        state = agency_slug[:2].strip().lower()
        slug = agency_slug[3:].strip().lower()
        state_mod = import_module(f"clean.{state}.{slug}")
        # Run the scrape method
        logger.info(f"Scraping {agency_slug}")
        site = state_mod.Site(self.data_dir, self.cache_dir)
        data_path = site.scrape_meta(throttle=self.throttle)
        # Run the path to the data file
        logger.info(f"Generated {data_path}")
        return data_path

    def delete(self):
        """Delete the files in the output directories."""
        logger.debug(f"Deleting files in {self.data_dir}")
        shutil.rmtree(self.data_dir, ignore_errors=True)
        logger.debug(f"Deleting files in {self.cache_dir}")
        shutil.rmtree(self.cache_dir, ignore_errors=True)
