import time
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the San Diego Harbor Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "San Diego Harbor Police Department"

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
        self.base_url = (
            "https://www.portofsandiego.org/public-safety/transparency-disclosures"
        )
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # san_diego_harbor_pd

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (san_diego_harbor_pd/transparency-disclosures.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.base_url)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find(
            "div",
            class_="field field--name-field-paragraphs field--type-entity-reference-revisions field--label-hidden field__items",
        )
        links = [a for li in body.find_all("li") for a in li.find_all("a")]

        for link in links:
            link_href = link.get("href", None)
            print("link: ", link_href)
            if link_href:
                data = dict()
                data["title"] = link.get_text(strip=True)
                data["name"] = link_href.split("/")[-1]
                h3_tag = link.find_previous("h3")
                data["case_type"] = h3_tag.get_text(strip=True)
                data["case_id"] = data["title"]
                if ".pdf" in link_href:
                    payload = {
                        "asset_url": link_href,
                        "case_id": data["case_id"],
                        "name": data["name"],
                        "title": data["title"],
                        "parent_page": str(filename),
                        "details": {"case_type": data["case_type"]},
                    }
                    print(payload)
                    metadata.append(payload)
                if "sandiego.gov" in link_href:
                    metadata.extend(self.scrape_san_diego(link_href, data))
                time.sleep(throttle)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def scrape_san_diego(self, link, data):
        child_name = f'{data["title"]}.html'
        filename = f"{self.agency_slug}/{child_name}"
        self.cache.download(filename, link)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find(
            "div",
            class_="clearfix text-formatted field field--name-body field--type-text-with-summary field--label-hidden field__item",
        )
        links = body.find_all("a")
        for link in links:
            link_href = link.get("href", None)
            if link_href:
                title = link.get_text()
                name = link_href.split("/")[-1]
                payload = {
                    "asset_url": link_href,
                    "case_id": data["case_id"],
                    "name": name,
                    "title": title,
                    "parent_page": str(filename),
                    "details": {"case_type": data["case_type"]},
                }
                metadata.append(payload)
        return metadata
