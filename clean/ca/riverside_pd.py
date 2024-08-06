import time
import urllib.parse
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the City of Riverside Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Riverside Police Department"

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
        self.sec_website_url = "https://riversideca.gov"
        self.un_sec_website_url = "http://riversideca.gov"
        self.base_url = "https://www.riversideca.gov/cityclerk/boards-commissions/community-police-review-commission/officer-involved-deaths-oid/officer-involved"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_river_side_pd

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_river_side_pd/officer-involved-deaths-oid.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-2]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.base_url)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("section", class_="col-sm-9")
        sections = body.select("div#accordion>div.panel.panel-default")
        for section in sections:
            section_text = section.select_one("h4.panel-title>a")
            title = section_text.find("strong").get_text(strip=True)
            date = section_text.find("span", class_="pull-right").get_text(strip=True)
            case_id = section_text.get_text(strip=True)
            case_id = case_id.replace(title, "").replace(date, "").strip()
            links = section.find_all("a")
            for link in links:
                link_href = link.get("href", None)
                if link_href:
                    if "#" not in link_href:
                        link_href = link_href.rstrip('"')
                        if (
                            self.sec_website_url not in link_href
                            and self.un_sec_website_url not in link_href
                        ):
                            link_href = f"{self.sec_website_url}{link_href}"
                        name = link_href.split("/")[-1]
                        name = urllib.parse.unquote(name)
                        payload = {
                            "asset_url": link_href,
                            "case_num": case_id,
                            "name": name,
                            "title": title,
                            "parent_page": str(filename),
                            "details": {"date": date},
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
            print("downloading...: ", asset["name"])
            url = asset["asset_url"]
            dl_path = self._make_download_path(asset)
            time.sleep(throttle)
            dl_assets.append(self.cache.download(str(dl_path), url))
        return dl_assets

    def _make_download_path(self, asset):
        folder_name = asset["case_number"]
        name = asset["name"]
        outfile = f"{folder_name}/{name}"
        dl_path = Path(self.agency_slug, "assets", outfile)
        return dl_path
