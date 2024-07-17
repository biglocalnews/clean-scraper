import time
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the Santa Rosa Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Santa Rosa Police"

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
        self.base_url = "https://www.srcity.org/3201/Cases"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_santa_rosa

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_santa_rosa/3201.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-2]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.base_url)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("div", class_="fr-view")
        links = body.find_all("a")
        for link in links:
            if 'dropbox' in link["href"]:
                payload = {
                    "year": link.find_parent("ul")
                    .find_previous_sibling("h3")
                    .string.replace(":", ""),
                    "parent_page": str(self.base_url),
                    "asset_url": link["href"].replace("dl=0", "dl=1"),
                    "name": link.string,
                }
                metadata.append(payload)
            time.sleep(throttle)
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
        url = asset["asset_url"]
        # If name ends in `pdf?dl=1`, handle one way
        if url.find("pdf?dl=1") == -1:
            outfile = url.split("/")[-1].replace("?dl=1", ".zip")
        else:
            outfile = url.split("/")[-1].replace("?dl=1", "")
        dl_path = Path(self.agency_slug, "assets", outfile)
        return dl_path