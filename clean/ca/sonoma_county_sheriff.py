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

    name = "Sonoma County Sheriff's Office"
    agency_slug = "ca_sonoma_county_sheriff"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        """Initialize a new instance.

        Args:
            data_dir (Path): The directory where downstream processed files/data will be saved
            cache_dir (Path): The directory where files will be cached
        """
        # Start page contains list of "detail"/child pages with links to the SB16/SB1421/AB748 videos and files
        # along with additional index pages
        self.base_url = "https://www.sonomasheriff.org/sb1421"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        # to create a subdir inside the main cache directory to stash files for this agency
        self.cache_suffix = f"{state_postal}_{mod.stem}"  # ca_sonoma_county_sheriff

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca/sonoma__/release_page.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.base_url)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("div", class_="main-content")
        links = body.find_all("a")
        for link in links:
            if link.strong:
                payload = {
                    "year": link.find_parent("ul")
                    .find_previous_sibling("p")
                    .strong.string.replace(":", ""),
                    "parent_page": str(self.base_url),
                    "asset_url": link["href"].replace("dl=0", "dl=1"),
                    "name": link.strong.string,
                }
                metadata.append(payload)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def scrape(self, throttle: int = 4, filter: str = "") -> List[Path]:
        metadata = self.cache.read_json(
            self.data_dir.joinpath(f"{self.agency_slug}.json")
        )
        dl_assets = []
        for asset in metadata:
            url = asset["asset_url"]
            dl_path = self._make_download_path(asset)
            time.sleep(throttle)
            dl_assets.append(self.cache.download(str(dl_path), url))
        return dl_assets

    def _make_download_path(self, asset):
        # TODO: Update the logic to gracefully handle PDFs in addition to zip fiiles
        url = asset["asset_url"]
        # If name ends in `pdf?dl=1`, handle one way
        if url.find("pdf?dl=1") == -1:
            outfile = url.split("/")[-1].replace("?dl=1", ".zip")
        else:
            outfile = url.split("/")[-1].replace("?dl=1", "")
        dl_path = Path(self.agency_slug, "assets", outfile)
        return dl_path
