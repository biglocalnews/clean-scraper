import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..config.monterey_county_district_attorney import index_request_headers


class Site:
    """Scrape file metadata and download files for the Monterey County District Attorney.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Monterey County District Attorney"

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
        self.base_url = "https://www.countyofmonterey.gov/government/departments-a-h/district-attorney/press-releases/officer-involved-shootings"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_monterey_county_district_attorney

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_monterey_county_district_attorney/officer-involved-shootings.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)

        date_pattern = re.compile(r"(\w+\s\d{1,2},\s?\d{4})")
        name_pattern = re.compile(r"\(([^)]+)\)")
        case_pattern = re.compile(r"Case:\s*(\w+)")
        year_pattern = re.compile(r"\d{4}")
        base_name = f"{self.base_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"

        self.cache.download(filename, self.base_url, headers=index_request_headers)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("table", id="oisTable")
        links = body.find_all("a")
        for link in links:
            td_tag = link.find_parent("td")
            title = td_tag.get_text(strip=True)
            td_text = td_tag.get_text(separator=" ").strip()
            # Extract date
            date_match = date_pattern.search(td_text)
            date = date_match.group(1) if date_match else None
            # Extract year from date
            if date:
                year_from_date = year_pattern.search(date).group()
            else:
                year_from_date = None
            # Extract name
            name_match = name_pattern.search(td_text)
            name = name_match.group(1) if name_match else None
            # Extract case number
            case_match = case_pattern.search(td_text)
            case_number = case_match.group(1) if case_match else title
            payload = {
                "asset_url": link["href"],
                "case_id": case_number,
                "name": name,
                "title": title,
                "parent_page": str(filename),
                "details": {"date": date, "year": year_from_date},
            }
            metadata.append(payload)
            time.sleep(throttle)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile
