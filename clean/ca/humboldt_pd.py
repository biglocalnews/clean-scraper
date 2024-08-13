import time
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the Humboldt Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Humboldt Police"

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
        self.base_url = "https://humboldtgov.org/3282/SB-1421-AB-748-Information"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_santa_rosa

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_humboldt_pd/SB-1421-AB-748-Information.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('#')[0].split('/')[-1]}.html"
        base_filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(base_filename, self.base_url)
        base_page_data = {
            "page_url": str(self.base_url),
            "page_name": base_filename,
        }
        child_pages = [base_page_data]
        html = self.cache.read(base_filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("table", class_="fr-alternate-rows")
        child_links = body.find_all("a")
        for link in child_links:
            if "humboldtgov" in link["href"]:
                child_name = f"{link.find_parent('td').find_previous_sibling('td').find('strong').string}_{link['href'].split('/')[-1]}.html"
                child_file_name = f"{self.agency_slug}/{child_name}"
                self.cache.download(child_file_name, link["href"])
                child_page_data = {
                    "page_url": str(link["href"]),
                    "page_name": child_file_name,
                }
                child_pages.append(child_page_data)
            time.sleep(throttle)
        metadata = self._get_asset_links(child_pages, base_filename)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def _get_asset_links(self, pages, parent_page) -> list:
        metadata = []
        for page in pages:
            html = self.cache.read(page["page_name"])
            soup = BeautifulSoup(html, "html.parser")
            document_body = soup.find("div", class_="relatedDocuments")
            if isinstance(document_body, Tag):
                links = document_body.find_all("a")
                for link in links:
                    if isinstance(link, Tag):
                        href = link.get("href")
                        if href and "DocumentCenter" in href:
                            title = (
                                soup.title.string.strip()
                                if soup.title and soup.title.string
                                else None
                            )
                            name = link.string
                            payload = {
                                "title": title,
                                "case_number": name,
                                "parent_page": str(parent_page),
                                "asset_url": f"{'https://humboldtgov.org'}{href}",
                                "name": name,
                            }
                            metadata.append(payload)
            else:
                h2 = soup.find("h2")
                link = h2.find_parent("a") if h2 else None
                if link and "document" in link["href"]:
                    title = (
                        soup.title.string.strip()
                        if soup.title and isinstance(soup.title.string, str)
                        else None
                    )
                    case_number = page["page_name"].split("/")[-1].split("_")[0]
                    header = soup.find("h1")
                    name = header.get_text(strip=True) if header else None
                    payload = {
                        "title": title,
                        "case_number": case_number,
                        "parent_page": str(parent_page),
                        "download_page": str(page["page_name"]),
                        "asset_url": f"https://humboldtgov.nextrequest.com{link['href']}",
                        "name": name,
                    }
                    metadata.append(payload)
        return metadata

    def _make_download_path(self, asset):
        folder_name = asset["case_number"]
        name = asset["name"]
        # If name has has no extension mark it as pdf as its a document format by meta-data
        if len(name.split(".")) == 1:
            name = name + ".pdf"
        outfile = f"{folder_name}/{name}"
        dl_path = Path(self.agency_slug, "assets", outfile)
        return dl_path
