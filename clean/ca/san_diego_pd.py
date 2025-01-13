import re
import time
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict


class Site:
    """Scrape file metadata and download files for the San Diego Police Department for SB16/SB1421/AB748 data.

    Attributes:
        name (str): The official name of the agency
    """

    name = "San Diego Police Department"

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
        self.base_url = "https://www.sandiego.gov"
        # Initial disclosure page (aka where they start complying with law) contains list of "detail"/child pages with links to the SB16/SB1421/AB748 videos and files
        # along with additional index pages
        self.disclosure_url = f"{self.base_url}/police/data-transparency/mandated-disclosures/sb16-sb1421-ab748"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_san_diego_pd

    def scrape_meta(self, throttle: int = 0) -> Path:
        """Gather metadata on downloadable files (videos, etc.).

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata on downloadable files
        """
        # Run the scraper on home page
        first_index_page_local = self._download_index_page(self.disclosure_url)
        local_index_pages = [first_index_page_local]
        # Extract URLs for all index pages from home page
        index_page_urls = self._get_index_page_urls(first_index_page_local)
        # Download remaining index pages
        for url in index_page_urls:
            time.sleep(throttle)
            local_index_pages.append(self._download_index_page(url))
        # Gather child pages ({page name, url, source index page})
        child_pages = []
        for index_page in local_index_pages:
            child_pages.extend(self._get_child_page(index_page, throttle))
        downloadable_files = self._get_asset_links()
        return downloadable_files

    # Helper functions
    def _get_asset_links(self) -> Path:
        """Extract link to files and videos from child pages."""
        metadata = []
        # Process child page HTML files in index page folders,
        # building a list of file metadata (name, url, etc.) along the way
        for item in Path(self.cache_dir, self.agency_slug).iterdir():
            if item.is_dir() and item.name.startswith("sb16"):
                for html_file in item.iterdir():
                    if html_file.suffix == ".html":
                        html = self.cache.read(html_file)
                        soup = BeautifulSoup(html, "html.parser")
                        title = soup.find("div", "view-header").text.strip()  # type: ignore
                        links = soup.find("div", class_="view-content").find_all("a")  # type: ignore
                        # Save links to files, videos, etc with relevant metadata
                        # for downstream processing
                        for link in links:
                            # Remove pagination part from html_file name
                            payload: MetadataDict = {
                                "title": title,
                                "parent_page": str(html_file),
                                "asset_url": link["href"].replace("\n", ""),
                                "name": link.text.strip().replace("\n", ""),
                                "case_id": re.sub(r"_page=\d+$", "", html_file.stem),
                            }
                            metadata.append(payload)
        # Store the metadata in a JSON file in the data directory
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        # Return path to metadata file for downstream use
        return outfile

    def _get_child_page(self, index_page: Path, throttle: int = 0) -> list[dict]:
        """Get URLs for child pages from index pages."""
        html = self.cache.read(index_page)
        soup = BeautifulSoup(html, "html.parser")
        # Get all the child page URLs
        parent_div = soup.find("div", class_="view-content")
        links = parent_div.find_all("a")  # type: ignore
        child_pages = []
        for anchor in links:
            time.sleep(throttle)
            page_meta = {
                "source_index_page": index_page,  # index page where this child page was found
                "source_name": anchor.text.strip(),
                "url": urllib.parse.urljoin(self.base_url, anchor.attrs["href"]),
            }
            page_meta["cache_name"] = (
                f"{page_meta['source_name'].replace(' ', '_')}.html"
            )
            page_meta.update(
                urllib.parse.parse_qs(urllib.parse.urlparse(page_meta["url"]).query)
            )
            # Stash child pages in folder matching name of index page where it's listed
            # Construct index page directory
            index_page_dir = f"{self.agency_slug}/{index_page.stem}"
            # Construct local file path inside index page directory
            relative_path = f"{index_page_dir}/{page_meta['cache_name']}"
            # Download the child page
            cache_path = self.cache.download(relative_path, page_meta["url"], "utf-8")
            # Update page metadata with full path in cache and relative path
            page_meta.update(
                {
                    "cache_path": cache_path,
                    "relative_path": relative_path,
                }
            )
            child_pages.append(page_meta)
        return child_pages

    def _get_index_page_urls(self, first_index_page: Path) -> list[str]:
        """Get the URLs for all index pages."""
        # Read the cached HTML file for home page
        html = self.cache.read(first_index_page)
        soup = BeautifulSoup(html, "html.parser")
        # Gross, but necessary to pass mypy type checking
        last_page = (
            soup.find("li", class_="pager__item pager__item--last")  # type: ignore
            .a.attrs["href"]  # type: ignore
            .split("?page=")[-1]  # type: ignore
        )  # type: ignore
        # Construct page links
        index_page_urls = []
        for num in range(1, int(last_page) + 1):  # type: ignore
            index_page_urls.append(f"{self.disclosure_url}?page={num}")
        return index_page_urls

    def _download_index_page(self, url: str) -> Path:
        """Download index pages for SB16/SB1421/AB748.

        Index pages link to child pages containing videos and
        other files related to use-of-force and disciplinary incidents.

        Returns:
            Local path of downloaded file
        """
        file_stem = url.split("/")[-1]
        file_stem = file_stem.replace("?", "_")
        base_file = f"{self.agency_slug}/{file_stem}.html"
        # Download the page (if it's not already cached)
        cache_path = self.cache.download(base_file, url, "utf-8")
        return cache_path
