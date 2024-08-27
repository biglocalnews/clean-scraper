import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..config.fremont_pd import index_request_headers


class Site:
    """Scrape file metadata and download files for the Fremont Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Fremont Police Department."

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
        self.base_url = "https://www.fremontpolice.gov/about-us/transparency-portal/officer-involved-shootings"
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
        # construct a local filename relative to the cache directory - agency slug + page url (ca_fremont_pd/officer-involved-shootings.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(
            filename,
            self.base_url,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            headers=index_request_headers,
        )
        metadata = []
        date_pattern = r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b"
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("div", class_="content_area normal_content_area clearfix")
        div_to_exclude = body.find(
            "div", class_="downloadmessage no_external_url_indication"
        )
        if div_to_exclude:
            div_to_exclude.decompose()
        links = body.find_all("a")
        for link in links:
            title_element = link.find_previous("h3")
            title = title_element.get_text()
            print(title)
            case_id = None
            year = link.find_previous("h2").string
            try:
                date_search = re.search(date_pattern, title).group()
            except Exception as e:
                print("Exception: ", e)
                print("Title: ", title)
                print("link: ", link["href"])

            date = None
            if len(date_search):
                date = date_search
            if title:
                case_id = title.replace(date, "").strip()
            asset_link = link["href"]
            if "youtube" in asset_link or "youtu.be" in asset_link:
                continue
                youtube_queue = utils.get_youtube_url_with_metadata(asset_link)
                for youtube_data in youtube_queue:
                    payload = {
                        "asset_url": youtube_data["url"],
                        "case_id": case_id,
                        "name": youtube_data["name"],
                        "title": title,
                        "parent_page": str(filename),
                        "details": {"date": date, "year": year},
                    }
                    metadata.append(payload)
            if "nixle" in asset_link:
                name = asset_link.split("/")[-1]
                nixle_data = self._get_doc_from_nixle(title, asset_link)
                if nixle_data:
                    payload = {
                        "asset_url": nixle_data["url"],
                        "case_id": case_id,
                        "name": name,
                        "title": title,
                        "parent_page": str(nixle_data["filename"]),
                        "details": {"date": date, "year": year},
                    }
                    metadata.append(payload)
            if "unioncity" in asset_link:
                name = asset_link.split("/")[-1]
                payload = {
                    "asset_url": asset_link,
                    "case_id": case_id,
                    "name": name,
                    "title": title,
                    "parent_page": str(filename),
                    "details": {
                        "date": date,
                        "year": year,
                        "related_agencies": "Union City PD",
                    },
                }
                metadata.append(payload)
            else:
                name = asset_link.split("/")[-1]
                payload = {
                    "asset_url": asset_link,
                    "case_id": case_id,
                    "name": name,
                    "title": title,
                    "parent_page": str(filename),
                    "details": {"date": date, "year": year},
                }
                metadata.append(payload)

            time.sleep(throttle)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def _get_doc_from_nixle(self, title, asset_link):
        child_name = f"{asset_link.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{title}/{child_name}"
        self.cache.download(
            filename,
            asset_link,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        )
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("div", class_="full_message_aux")
        link = body.find("a")
        if link:
            item = dict()
            item["filename"] = filename
            item["url"] = link["href"]
            return item
        return None
