import logging
import time
import urllib.parse
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict

logger = logging.getLogger(__name__)


class Site:
    """Scrape file metadata and download files for the Ventura County Sheriff for SB1421/AB748 data.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Ventura County Sheriff"

    agency_slug = "ca_ventura_county_sheriff"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        # Start page contains list of "detail"/child pages with links to the SB16/SB1421/AB748
        #  videos and files along with additional index pages
        self.base_url = "https://www.venturasheriff.org"
        self.index_urls = {
            f"{self.base_url}/sb1421/officer-involved-shooting-ois/": "ois.html",
            f"{self.base_url}/sb1421/use-of-force-great-bodily-injury-cases-gbi/": "gbi.html",
            f"{self.base_url}/ab748/": "ab748.html",
        }

        self.cache = Cache(cache_dir)  # ~/.clean-scraper/cache/
        self.data_dir = data_dir
        self.cache_dir = cache_dir

        # Use module path to construct agency slug, which we'll use downstream
        # to create a subdir inside the main cache directory to stash files for this agency
        mod = Path(__file__)
        state_postal = mod.parent.stem
        self.cache_suffix = f"{state_postal}_{mod.stem}"  # ca_ventura_county_sheriff
        self.cache_root = cache_dir / (self.cache_suffix)
        self.subpages_dir = self.cache_root / "subpages"

    def scrape_meta(self, throttle: int = 0) -> Path:
        metadata: List[MetadataDict] = []
        page_urls = []
        # Scrape index pages for both assets and links to case directories/subpages
        for index_url in self.index_urls:
            detail_page_links, local_metadata = self._process_index_page(index_url)
            page_urls.extend(detail_page_links)
            metadata.extend(local_metadata)
            time.sleep(throttle)

        # Now, process the links of case directories/subpages
        for page_url in page_urls:
            local_metadata = self._process_detail_page(page_url)
            metadata.extend(local_metadata)
            time.sleep(throttle)

        outfile = self.data_dir.joinpath(f"{self.cache_suffix}.json")
        logger.debug(f"Attempting to save metadata to {outfile}")
        full_filename = self.cache.write_json(outfile, metadata)
        return full_filename

    # Helper/Private Methods
    def _process_detail_page(self, target_url) -> List[MetadataDict]:
        """Extract links to files such as videos from a detail page and write to JSON file."""
        local_metadata: List[MetadataDict] = []

        # Build a complete URL and determine the subdirectory name
        if target_url.endswith("/"):
            target_url = target_url[:-1]
        if "http" not in target_url:
            target_url = urllib.parse.urljoin(self.base_url, target_url)

        full_filename = self.subpages_dir / (target_url.split("/")[-1] + ".html")
        relative_filename = str(full_filename.relative_to(self.cache_dir)).replace(
            "\\", "/"
        )

        # Download the index page, which saves to local cache
        self.cache.download(
            full_filename,
            target_url,
            force=False,  # Do NOT automatically rescrape subpages
        )

        html = self.cache.read(full_filename)
        soup = BeautifulSoup(html, "html.parser")
        # Find the title of the page
        title = soup.find("h1")
        if title:
            title = title.get_text().strip()  # type: ignore

        h2split = "<h2"
        pageguts = soup.find("div", attrs={"class": "page-content"})
        # Get local links from that main content bar only
        focusedguts = BeautifulSoup(
            h2split + h2split.join(pageguts.prettify().split(h2split)[1:]),  # type: ignore
            "html.parser",
        )
        for section in str(focusedguts).split(h2split):
            localsection = BeautifulSoup(h2split + section, "html.parser")
            sectiontitle = localsection.find("h2")
            if not sectiontitle:
                if localsection.prettify().strip() != "&lt;h2":
                    # &lt;h2  keeps getting translated as <h2 and gets picked up that way, somehow?
                    # But are we missing some legit entries because of this?
                    logger.debug(
                        f"Something weird happened with sectiontitle. The entire section: {localsection.prettify()}"
                    )
            else:
                sectiontitle = localsection.find("h2").get_text().strip()  # type: ignore
            links = localsection.find_all("a")
            for link in links:
                if link["href"][-1] == "/":
                    logger.debug(f"Found possible landing page: {link['href']}")
                elif "javascript:" in link["href"]:
                    logger.debug(f"Dropping JS (audio playlist?) link for {link}")
                else:
                    # logger.debug(f"Found possible direct asset: {link['href']}")
                    line: MetadataDict = {}  # type: ignore

                    asset_url = link["href"]
                    # If relative URL, add in the prefix
                    if not asset_url.startswith("http"):
                        asset_url = urllib.parse.urljoin(self.base_url, asset_url)
                    line["asset_url"] = asset_url
                    line["name"] = ""
                    if "youtu.be" in link["href"]:
                        line["name"] = link.get_text().strip()
                    else:
                        line["name"] = link["href"].split("/")[-1].strip()

                    line["parent_page"] = relative_filename
                    line["title"] = link.get_text().strip()
                    line["case_id"] = str(title)
                    line["details"] = {}
                    line["details"]["section_title"] = sectiontitle
                    local_metadata.append(line)
        return local_metadata

    def _process_index_page(self, target_url):
        local_metadata: List[MetadataDict] = []
        subpages = []

        full_filename = self.cache_root / self.index_urls[target_url]
        relative_filename = str(full_filename.relative_to(self.cache_dir)).replace(
            "\\", "/"
        )

        # Download the index page, which saves to local cache
        self.cache.download(
            full_filename,
            target_url,
            force=True,  # Always get a fresh index page
        )

        html = self.cache.read(relative_filename)
        # Proceed with normal HTML parsing...

        if "ab748" in str(relative_filename):  # Kludge for a page in a disparate format
            html = html.replace("<strong>", "<h2>").replace("</strong>", "</h2>")

        soup = BeautifulSoup(html, "html.parser")
        h2split = "<h2"
        pageguts = soup.find("div", attrs={"class": "page-content"})
        # Get local links from that main content bar only
        focusedguts = BeautifulSoup(
            h2split + h2split.join(pageguts.prettify().split(h2split)[1:]),
            "html.parser",
        )

        for section in str(focusedguts).split(h2split):
            localsection = BeautifulSoup(h2split + section, "html.parser")
            sectiontitle = localsection.find("h2")
            if not sectiontitle:
                if localsection.prettify().strip() != "&lt;h2":
                    # &lt;h2  keeps getting translated as <h2 and gets picked up that way, somehow?
                    # But are we missing some legit entries because of this?
                    logger.debug(
                        f"Something weird happened with sectiontitle. The entire section: {localsection.prettify()}"
                    )
            else:
                sectiontitle = localsection.find("h2").get_text().strip()
            links = localsection.find_all("a")
            for link in links:
                if link["href"][-1] == "/":
                    logger.debug(
                        f"Found possible landing page in subpage!: {link['href']}"
                    )
                    subpages.append(link["href"])
                elif "leginfo.legislature.ca." in link["href"]:
                    logger.debug(
                        f"Legislative link found at {link['href']}, not an asset"
                    )
                else:
                    # logger.debug(f"Found possible direct asset: {link['href']}")
                    line = {}
                    case_id = link.get_text().strip()
                    asset_url = link["href"]

                    # If relative URL, add in the prefix
                    if not asset_url.startswith("http"):
                        asset_url = urllib.parse.urljoin(self.base_url, asset_url)
                    line["asset_url"] = asset_url
                    line["case_id"] = case_id
                    line["name"] = case_id + "/" + link["href"].split("/")[-1]
                    line["parent_page"] = str(relative_filename)
                    line["title"] = case_id
                    line["details"] = {}
                    line["details"]["section_title"] = sectiontitle
                    local_metadata.append(line)
        return (subpages, local_metadata)
