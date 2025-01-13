import logging
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache

logger = logging.getLogger(__name__)


class Site:
    """Scrape file metadata and download files for the Grass Valley Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Grass Valley Police Department"

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
        self.index_url = "https://www.cityofgrassvalley.com/records-release"
        self.base_url = "https://www.cityofgrassvalley.com"
        self.pdf_download_url = "https://cityofgrassvalley-my.sharepoint.com/personal/bkalstein_gvpd_net/_layouts/15/download.aspx?SourceUrl="
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_grass_valley_pd

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_grass_valley_pd/records-release.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.index_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.index_url, force=True)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        content_areas = soup.find("div", class_="content-after-inner")
        h2_elements = content_areas.find_all("h2", class_="title")
        links = [h2.find("a") for h2 in h2_elements]
        for link in links:
            link_href = link.get("href", None)
            print(link_href)
            link_href = f"{self.base_url}{link_href}"
            case_id = link.string
            if link_href:
                title = link.string
                child_name = f"{link_href.split('/')[-1]}.html"
                child_filename = f"{self.agency_slug}/{child_name}"
                self.cache.download(child_filename, link_href, force=True)
                html = self.cache.read(child_filename)
                soup = BeautifulSoup(html, "html.parser")
                content_areas = soup.find("section", class_="page-content")
                child_links = content_areas.find_all("a")
                video_counter = 1
                for child_link in child_links:
                    link = child_link.get("href", None)
                    if "file-attachments" in link:
                        title = child_link.string
                        name = link.split("/")[-1].split("?")[0]
                        payload = {
                            "asset_url": f"{self.base_url}{link}",
                            "case_id": case_id,
                            "name": name,
                            "title": title,
                            "parent_page": str(child_filename),
                        }
                        metadata.append(payload)
                    if "sharepoint" in link:
                        download_link = self._get_sharepoint_link(link)
                        if download_link:
                            name = download_link.split("/")[-1]
                            title = child_link.string.strip()
                            payload = {
                                "asset_url": download_link,
                                "case_id": case_id,
                                "name": name,
                                "title": title,
                                "parent_page": str(child_filename),
                            }
                            metadata.append(payload)
                    if "vimeo" in link:
                        link = link.split("?")[0]
                        name = link.split("/")[-1]
                        title = f"{case_id}-{video_counter}"
                        video_counter += 1
                        payload = {
                            "asset_url": link,
                            "case_id": case_id,
                            "name": name,
                            "title": title,
                            "parent_page": str(child_filename),
                        }
                        metadata.append(payload)

            time.sleep(throttle)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def _get_sharepoint_link(self, url):
        response = requests.get(url)
        logger.debug(f"Response code: {response.status_code}")

        if response.status_code == 200:
            one_drive_url = response.url
            # Parse the URL
            parsed_url = urlparse(one_drive_url)

            # Extract the query parameters
            query_params = parse_qs(parsed_url.query)

            # Get the 'id' parameter
            id_value = query_params.get("id", [None])[0]

            download_link = f"{self.pdf_download_url}{id_value}"
            return download_link
        else:
            return None
