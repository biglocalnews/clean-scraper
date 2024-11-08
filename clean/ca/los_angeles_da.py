# from datetime import datetime
from pathlib import Path

from .. import utils
from ..cache import Cache

# from bs4 import BeautifulSoup


class Site:
    """Scrape file metadata for the Los Angeles District Attorney's Office.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Los Angeles District Attorney's Office"

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
    ):
        """Initialize a new instance.

        Args:
            data_dir (Path): The directory where downstream processed files/data will be saved
            cache_dir (Path): The directory where files will be cached
        """
        self.base_url = "https://da.lacounty.gov"
        self.disclosure_url = f"{self.base_url}/reports/ois/"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_los_angeles_da

    # def scrape_meta(self, throttle: int = 0) -> Path:
    #     """Gather metadata on downloadable files (videos, etc.).

    #     Args:
    #         throttle (int): Number of seconds to wait between requests. Defaults to 0.

    #     Returns:
    #         Path: Local path of JSON file containing metadata on downloadable files
    #     """
    #     # Create a list of years to scrape
    #     # e.g. [2016, 2017...]
    #     current_year = datetime.now().year
    #     # TODO: Check if this is the correct range on website
    #     years = range(2016, current_year)

    #     # Use BeautifulSoup to iterate over each year
    #     for year in years:
    #         cache_path = self._download_index_page(year)
    #         html = self.cache.read(cache_path)
    #         soup = BeautifulSoup(html, "html.parser")

    def _download_index_page(self, year: int):
        """Download the index page for a given year.

        Args:
            year (int): The year to download

        Returns:
            str: Local path of downloaded
        """
        url = f"{self.disclosure_url}{year}"
        file_stem = year
        download_file = f"{self.agency_slug}/{file_stem}.html"
        cache_path = self.cache.download(download_file, url, "utf-8")
        return cache_path
