import logging
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..platforms.nextrequest import process_nextrequest

logger = logging.getLogger(__name__)


class Site:
    """Scrape file metadata for the City of Oakland Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "City of Oakland Police Department"

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
        self.site_slug = self.agency_slug
        self.base_url = "https://oaklandca.nextrequest.com"
        # Initial disclosure page (aka where they start complying with law) contains list of "detail"/child pages with links to the SB16/SB1421/AB748 videos and files
        # along with additional index pages
        self.disclosure_url = "https://www.oaklandca.gov/resources/oakland-police-officers-and-related-sb-1421-16-incidents"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.subpages_dir = cache_dir / (self.site_slug + "/subpages")
        self.cache = Cache(cache_dir)
        for localdir in [self.cache_dir, self.data_dir, self.subpages_dir]:
            utils.create_directory(localdir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"

    def scrape_meta(self, throttle: int = 2) -> Path:
        """Gather metadata on downloadable files (videos, etc.).

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata on downloadable files
        """
        base_name = f"{self.disclosure_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.disclosure_url)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find_all(
            "table", class_="w-full border text-sm border-cool-gray-500"
        )[-1]
        tbody = body.find("tbody")
        links = tbody.find_all("a")
        subpages_dir = self.subpages_dir
        count = 1
        for link in links:
            print("processing link no: ", count)
            tr_tag = link.find_parent("tr")
            td_tags = tr_tag.find_all("td")
            officer_name = td_tags[0].get_text(strip=True)
            sb_category = td_tags[1].get_text(strip=True)
            if "nextrequest" in link.get("href"):
                local_metadata = process_nextrequest(
                    subpages_dir, link.get("href"), True, throttle
                )
                for data in local_metadata:
                    data["details"]["officer_name"] = officer_name
                    data["details"]["sb_category"] = sb_category
                metadata.extend(local_metadata)
            else:
                print("link unknown: ", link.get("href"))
            count += 1

        json_filename = self.data_dir / (self.site_slug + ".json")
        self.cache.write_json(json_filename, metadata)

        return json_filename
