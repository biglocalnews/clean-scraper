import time
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the San Diego Police Department for SB16/SB1421/AB748 data.

    Attributes:
        name (str): The official name of the agency
    """

    name = "San Diego Police Department"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        """Initialize a new instance.

        Args:
            data_dir (Path): The directory where downstream processed files/data will be saved
            cache_dir (Path): The directory where files will be cached
        """
        # Start page contains list of "detail"/child pages with links to the SB16/SB1421/AB748 videos and files
        # along with additional index pages
        self.base_url = "https://www.sandiego.gov/police/data-transparency/mandated-disclosures/sb16-sb1421-ab748"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        # to create a subdir inside the main cache directory to stash files for this agency
        self.cache_suffix = f"{state_postal}_{mod.stem}"  # ca_san_diego_pd

    def scrape_meta(self, throttle: int = 0):
        """Gather metadata on downloadable files (videos, etc.)."""
        # Run the scraper on home page
        first_index_page_local = self._base_url = self._download_index_page(
            self.base_url
        )
        local_index_pages = [first_index_page_local]
        # Extract URLs for all index pages from home page
        index_page_urls = self._get_index_page_urls(first_index_page_local)
        # Download remaining index pages
        for url in index_page_urls:
            time.sleep(throttle)
            local_index_pages.append(self._download_index_page(url))
        # TODO: Get the child pages and, you know, actually scrape file metadata
        # child_pages = []
        # return child_pages
        return local_index_pages

    # Helper functions
    def _get_index_page_urls(self, first_index_page: Path) -> List[str]:
        """Get the URLs for all index pages."""
        # Read the cached HTML file for home page
        html = self.cache.read(first_index_page)
        soup = BeautifulSoup(html, "html.parser")
        last_page = (
            soup.find("li", class_="pager__item pager__item--last")
            .a.attrs["href"]
            .split("?page=")[-1]
        )
        # Construct page links
        index_page_urls = []
        for num in range(1, int(last_page) + 1):
            index_page_urls.append(f"{self.base_url}?page={num}")
        return index_page_urls

    def _download_index_page(self, url: str) -> Path:
        """Download index pages for SB16/SB1421/AB748.

        Index pages link to child pages containing videos and
        other files related to use-of-force and disciplinary incidents.

        Returns:
            Local path of downloadeded file
        """
        file_stem = url.split("/")[-1]
        # Downstream index pages have a page GET parameter
        try:
            current_page = file_stem.split("?page=")[1]
        # Home page doesn't have a page parameter
        except IndexError:
            current_page = "0"
        base_file = f"{self.cache_suffix}/{file_stem}_index_page{current_page}.html"
        # Download the page (if it's not already cached)
        cache_path = self.cache.download(base_file, url, "utf-8")
        return cache_path
