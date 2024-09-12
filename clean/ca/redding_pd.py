import re
import time
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the City of Chula Vista Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Redding Police Department"

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
        self.base_url = "https://files.cityofredding.gov/"
        self.index_url = "https://www.cityofredding.gov/government/departments/police/policies___reference_library/senate_bill_1421_releases.php"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_chula_vista_pd

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (redding_pd/senate_bill_1421_releases.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.index_url.split('/')[-1].split('.')[0]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.index_url, force=True)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        content_table = soup.find("table")
        links = content_table.find_all("a")
        for link in links:
            link_href = link.get("href", None)
            parent_row = link.find_parent("tr")
            columns = parent_row.find_all("td")
            column_texts = [v.get_text(strip=True) for v in columns[:-1]]
            if link_href:
                title = link.get_text(strip=True)
                case_id = re.findall(r"\b\d{2}-\d{3,4}\b", title)
                if len(case_id) > 0:
                    case_id = case_id[0]
                else:
                    case_id = title
                name_href = urllib.parse.unquote(link_href)
                name = name_href.split("/")[-1]
                payload = {
                    "asset_url": f"{self.base_url}{link_href}",
                    "case_id": case_id,
                    "name": name,
                    "title": title,
                    "parent_page": str(filename),
                    "details": {
                        "case_type": column_texts[3],
                        "date": column_texts[0],
                        "location": column_texts[1],
                        "officer": column_texts[2],
                    },
                }
                metadata.append(payload)
            time.sleep(throttle)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile
