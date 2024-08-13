import re
import time
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..config.corona_pd import download_request_headers, index_request_headers


class Site:
    """Scrape file metadata and download files for the Corona Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Corona Police Department."

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
        self.base_url = "https://www.coronaca.gov/government/departments-divisions/police-department/trust-and-transparency#Records%20and%20Community%20Briefing%20Videos"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_corona_pd

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_corona_pd/trust-and-transparency.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1].split('#')[0]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(
            filename,
            self.base_url,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            headers=index_request_headers,
        )
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("div", class_="accordion_widget mn-accordion")
        links = body.find_all("a")
        for link in links:
            if "public-records-request" not in link["href"]:
                case_num = self._get_clean_case_num(link)
                name = link.string
                title_element = link.find_previous("div", class_="title")
                title = title_element.string
                asset_url = link["href"].replace(
                    "youtu.be/", "www.youtube.com/watch?v="
                )
                if "youtube" not in asset_url and "coronaca.gov" not in asset_url:
                    asset_url = f"https://www.coronaca.gov{asset_url}"
                print(title)
                asset_url = asset_url.strip()
                payload = {
                    "asset_url": asset_url,
                    "case_num": case_num,
                    "name": name,
                    "title": title,
                    "parent_page": str(filename),
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
            dl_assets.append(
                self.cache.download(str(dl_path), url, headers=download_request_headers)
            )
        return dl_assets

    def _make_download_path(self, asset):
        name = asset["name"]
        folder_name = asset["case_num"]
        if "showpublisheddocument" in asset["asset_url"]:
            outfile = f"{folder_name}/{name}.pdf"
        else:
            outfile = f"{folder_name}/{name}.mp4"
        dl_path = Path(self.agency_slug, "assets", outfile)
        return dl_path

    def _get_clean_case_num(self, element):
        parent_tag = element.find_parent(["p", "td"])
        if parent_tag:
            complete_text = parent_tag.get_text(strip=True)
        else:
            complete_text = element.get_text(strip=True)

        case_number_pattern = r"(LI#\s?\d{2}-\d+|CR#\s?\d{2}-\d+|PI\s?\d{2}-\d{3})"
        matches = re.findall(case_number_pattern, complete_text)
        for match in matches:
            cleaned_case_number = match.strip()
            return cleaned_case_number
        return None
