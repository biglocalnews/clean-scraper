import time
from pathlib import Path
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict


class Site:
    """Scrape file metadata for the Shasta County District Attorney's Office."""

    name = "Shasta County District Attorney's Office"

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
        self.base_url = "https://www.shastacounty.gov"
        self.disclosure_url = f"{self.base_url}/district-attorney/page/police-use-force"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_shasta_county_da

    def scrape_meta(self, throttle: int = 0) -> Path:
        """Gather metadata on downloadable files."""
        main_links = self.get_main_page_links()
        metadata = self.get_detail_page_links(main_links, throttle)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def get_main_page_links(self) -> List[str]:
        """Retrieve links from <a> tags with class 'title-only__link' on the main index page."""
        main_links = []

        cache_path = self._download_index_page(self.disclosure_url)
        html = self.cache.read(cache_path)
        soup = BeautifulSoup(html, "html.parser")

        # Extract links from <a> tags with class 'title-only__link'
        for target in soup.find_all("a", class_="title-only__link"):
            href = target.get("href")
            if href:
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

            # Loop through each file link container
            for link_tag in soup.find_all("a", href=True):
                href = link_tag.get("href")
                if (
                    href and "media" in href.lower()
                ):  # Ensure it's a downloadable media link
                    asset_url = urljoin(self.base_url, href.strip())
                    file_name = Path(asset_url).name

                    # Find the closest title in the same container
                    container = link_tag.find_parent()
                    title_tag = (
                        container.select_one("span.file-name.file-property")
                        if container
                        else None
                    )
                    title = (
                        title_tag.get_text(strip=True) if title_tag else "Unknown Title"
                    )

                    # Build metadata payload
                    payload: MetadataDict = {
                        "asset_url": asset_url,
                        "case_id": asset_url.split("/")[-1],
                        "name": file_name + ".pdf",
                        "title": title,
                        "parent_page": detail_page,
                    }

                    if payload not in metadata:  # Avoid potential duplicates
                        metadata.append(payload)

            time.sleep(throttle)
        return metadata

    def _download_index_page(self, page_url: str) -> Path:
        """Download and cache an index or detail page."""
        file_stem = f"{Path(page_url).stem}_index"
        cache_path = self.cache.download(file_stem, page_url, "utf-8")
        return cache_path
