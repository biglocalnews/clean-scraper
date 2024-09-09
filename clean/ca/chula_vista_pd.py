import logging
import time
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from .config.chula_vista_pd import index_request_headers

logger = logging.getLogger(__name__)


class Site:
    """Scrape file metadata and download files for the City of Chula Vista Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Chula Vista Police Department"

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
        self.base_url = "https://www.chulavistaca.gov/departments/police-department/senate-bill-1421"
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
        # construct a local filename relative to the cache directory - agency slug + page url (ca_chula_vista_pd/senate-bill-1421.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(
            filename, self.base_url, force=True, headers=index_request_headers
        )
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        content_areas = soup.find_all("div", class_="content_area clearfix")
        desired_element = None
        for content_area in content_areas:
            previous_h2 = content_area.find_previous("h2")
            if previous_h2 and previous_h2.text == "Documents":
                desired_element = content_area
                break

        if desired_element:
            sections = desired_element.find_all("div", class_="accordion-item")
            for section in sections:
                case_type = section.find("div", class_="title").get_text(strip=True)
                links = section.find_all("a")
                for link in links:
                    link_href = link.get("href", None)
                    case_id = link.find_previous("p").text
                    case_id = case_id.replace("\u00a0", " ").replace("\u2014", "--")
                    if link_href:
                        title = link.string
                        title = title.replace("\u00a0", " ").replace("\u2014", "--")
                        redirect_start = "/?splash="
                        redirect_end = "&____isexternal=true"

                        # Clean up links. Check to see if it's a redirect:
                        if redirect_start in link_href:
                            link_href = link_href.replace(redirect_start, "").replace(
                                redirect_end, ""
                            )
                            link_href = urllib.parse.unquote(link_href)
                            name = title
                        else:
                            name = link_href.split("/")[-1]

                        # See if it's a relative link
                        if urllib.parse.urlparse(link_href).netloc == "":
                            link_href = f"https://www.chulavistaca.gov{link_href}"

                        payload = {
                            "asset_url": link_href,
                            "case_id": case_id,
                            "name": name,
                            "title": title,
                            "parent_page": str(filename),
                            "details": {"case_type": case_type},
                        }
                        metadata.append(payload)

                    time.sleep(throttle)
        else:
            logger.error("HTML for the desired Elelemt")

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile
