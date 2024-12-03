import time
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict


class Site:
    """Scrape file metadata for the Orange County District Attorney's Office."""

    name = "Orange County District Attorney's Office"

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
    ):
        """Initialize a new instance."""
        self.base_url = "https://orangecountyda.org"
        self.disclosure_url = (
            f"{self.base_url}/reports/officer-involved-shooting-reports/"
        )
        self.custodial_death_url = f"{self.base_url}/reports/custodial-death-reports/"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # e.g., ca_orange_county_da

    def scrape_meta(self, throttle: int = 0) -> Path:
        """
        Gather metadata on downloadable files by following a two-step process:
        1. Extract links from main pages.
        2. Extract metadata from detail pages.

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata.
        """
        # Step 1: Extract links from main pages
        main_links = self.get_main_page_links()

        # Step 2: Extract metadata from detail pages
        metadata = self.get_detail_page_links(main_links, throttle)

        # Write metadata to a JSON file
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)

        return outfile

    def get_all_page_urls(self) -> List[str]:
        """
        Generate a list of all paginated URLs for the main pages.

        Returns:
            List[str]: List of URLs for all paginated pages.
        """
        pages_urls = []

        # Officer-involved shooting reports
        officer_base_url = f"{self.disclosure_url}"
        pages_urls.append(officer_base_url)
        for i in range(2, 16):  # Number of pages Dec. 3 2024
            pages_urls.append(f"{officer_base_url}page/{i}/")

        # Custodial death reports
        custodial_base_url = f"{self.custodial_death_url}"
        pages_urls.append(custodial_base_url)
        for i in range(2, 13):  # Number of pages Dec. 3 2024
            pages_urls.append(f"{custodial_base_url}page/{i}/")

        return pages_urls

    def get_main_page_links(self) -> List[str]:
        """
        Retrieves links from all paginated pages of the site.

        Returns:
            List[str]: A list of URLs for detailed pages.
        """
        page_urls = self.get_all_page_urls()
        main_links = []

        for page_url in page_urls:
            cache_path = self._download_index_page(page_url)
            html = self.cache.read(cache_path)
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                if (
                    "press/ocda" in link["href"]
                    or "press/media-advisory" in link["href"]
                    or "reports/officer" in link["href"]
                    or "media-advisory" in link["href"]
                    or "reports/custodial-death-reports" in link["href"]
                    or "press/ocda-issues-custodial-death-report" in link["href"]
                ):
                    main_links.append(link["href"])

        return main_links

    def get_detail_page_links(
        self, main_links: List[str], throttle: int = 0
    ) -> List[MetadataDict]:
        """
        Extracts detailed metadata from links on the main pages.

        Args:
            main_links (List[str]): A list of main page URLs.
            throttle (int): Number of seconds to wait between requests.

        Returns:
            List[MetadataDict]: A list of metadata dictionaries for downloadable resources.
        """
        metadata = []

        # Define allowed keywords for detail links
        allowed_detail_keywords = [
            "wp-content/uploads/investigation",  # Specific to custodial death investigations
            "wp-content/uploads/",  # General downloadable reports
            "youtube.com",  # Optional, depending on your requirements
        ]

        for link in main_links:
            cache_path = self._download_index_page(link)
            html = self.cache.read(cache_path)
            soup = BeautifulSoup(html, "html.parser")

            for detail_link in soup.find_all("a", href=True):
                href = detail_link["href"]
                # Ignore links containing 'Real-Estate-Fraud-Report', the url is similar to the one we are looking for.
                if "Real-Estate-Fraud-Report" in href:
                    continue
                if any(keyword in href for keyword in allowed_detail_keywords):
                    asset_url = (
                        href if href.startswith("http") else f"{self.base_url}{href}"
                    )
                    case_id = asset_url.split("/")[-1]

                    payload: MetadataDict = {
                        "asset_url": asset_url,
                        "case_id": case_id,
                        "name": asset_url.split("/")[-1],
                        "title": detail_link.get(
                            "title", case_id
                        ),  # not sure how useful this title is...
                        "parent_page": link,
                    }
                    metadata.append(payload)
            time.sleep(throttle)

        return metadata

    def _download_index_page(self, page_url: str) -> Path:
        """
        Download the HTML of a given page.

        Args:
            page_url (str): URL of the page to download.

        Returns:
            Path: Local cache path to the downloaded file.
        """
        split_url = page_url.split("/")
        file_stem = f"{split_url[-4]}_{split_url[-2]}_index"
        cache_path = self.cache.download(
            file_stem,
            page_url,
            "utf-8",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0"
            },
        )
        return cache_path
