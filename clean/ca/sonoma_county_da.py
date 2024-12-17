import time
from pathlib import Path
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict


class Site:
    """Scrape file metadata for the Sonoma County District Attorney's Office."""

    name = "Sonoma County District Attorney's Office"

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
    ):
        """Initialize a new instance.

        Args:
            data_dir (Path): Directory for downstream processed files/data.
            cache_dir (Path): Directory for cached files.
        """
        self.base_url = "https://da.sonomacounty.ca.gov"
        self.disclosure_url = f"{self.base_url}/critical-incident-reports-index"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_sonoma_county_da

    def scrape_meta(self, throttle: int = 0) -> Path:
        """Gather metadata on downloadable files."""
        main_links = self.get_main_page_links()
        metadata = self.get_detail_page_links(main_links, throttle)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def get_main_page_links(self) -> List[str]:
        """Retrieve links from h2 tags with class 'h3' on the main index page."""
        main_links = []

        cache_path = self._download_index_page(self.disclosure_url)
        html = self.cache.read(cache_path)
        soup = BeautifulSoup(html, "html.parser")

        # Find all h2 tags with class 'h3'
        for h2 in soup.find_all("h2", class_="h3"):
            for link in h2.find_all("a", href=True):
                href = link["href"]
                full_url = urljoin(self.base_url, href.strip())
                main_links.append(full_url)

        return main_links

    def get_detail_page_links(
        self, main_links: List[str], throttle: int = 0
    ) -> List[MetadataDict]:
        """Extract downloadable file metadata from detail pages."""
        metadata = []

        for detail_page in main_links:
            cache_path = self._download_index_page(detail_page)
            html = self.cache.read(cache_path)
            soup = BeautifulSoup(html, "html.parser")

            # Extract title from <h1> under div with class 'body-copy'
            title_tag = soup.select_one("div.body-copy > h1")
            raw_title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

            # Clean the title: Replace en-dash and non-breaking space with clean versions
            clean_title = (
                raw_title.replace("\u2013", "-").replace("\u00a0", " ").strip()
            )

            # Extract PDF links under <h2> within 'body-copy'
            for h2 in soup.select("div.body-copy h2"):
                for link in h2.find_all("a", href=True):
                    href = link["href"]
                    if ".pdf" in href.lower():
                        asset_url = urljoin(self.base_url, href.strip())
                        file_name = Path(asset_url).name

                        payload: MetadataDict = {
                            "asset_url": asset_url,
                            "case_id": clean_title,
                            "name": file_name,
                            "title": clean_title,  # Cleaned title
                            "parent_page": detail_page,
                        }
                        metadata.append(payload)
            time.sleep(throttle)  # Respect throttle delay
        return metadata

    def _download_index_page(self, page_url: str) -> Path:
        """Download and cache an index or detail page."""
        file_stem = f"{Path(page_url).stem}_index"
        cache_path = self.cache.download(file_stem, page_url, "utf-8")
        return cache_path
