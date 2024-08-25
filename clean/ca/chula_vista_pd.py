import time
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from .config.chula_vista_pd import index_request_headers


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
        self.cache.download(filename, self.base_url, headers=index_request_headers)
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
                title = section.find("div", class_="title").get_text(strip=True)
                links = section.find_all("a")
                for link in links:
                    link_href = link.get("href", None)

                    case_id = link.get_text().replace("\u00a0", " ")
                    # case_id = encoded_text.encode('latin1').decode('unicode_escape').encode('latin1').decode('utf-8')
                    if link_href:
                        if "splash" not in link_href:
                            link_href = f"https://www.chulavistaca.gov{link_href}"
                            name = link_href.split("/")[-1]
                            payload = {
                                "asset_url": link_href,
                                "case_id": case_id,
                                "name": name,
                                "title": title,
                                "parent_page": str(filename),
                            }
                            metadata.append(payload)
                        else:
                            link_href = f"https://www.chulavistaca.gov{link_href}"
                            link_href = self._convert_splash_link(link_href)
                            name = link_href.split("/")[-1]
                            payload = {
                                "asset_url": link_href,
                                "case_id": case_id,
                                "name": name,
                                "title": title,
                                "parent_page": str(filename),
                            }
                            metadata.append(payload)

                    time.sleep(throttle)
            outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
            self.cache.write_json(outfile, metadata)
            return outfile

    def _convert_splash_link(self, link):
        # Takes a splash link as input and return the actual link after converting
        print(link)
        parsed_url = urllib.parse.urlparse(link)
        parsed_params = urllib.parse.parse_qs(parsed_url.query)

        # Decode the splash URL
        decoded_splash_link = urllib.parse.unquote(parsed_params["splash"][0])
        return decoded_splash_link
