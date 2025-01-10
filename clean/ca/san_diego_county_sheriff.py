import logging
from typing import List
from pathlib import Path
from playwright.sync_api import sync_playwright
import time
import json

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Site:
    """Scrape file metadata for the San Diego County Sheriff's Department."""

    name = "San Diego County Sheriff"

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
    ):
        """Initialize a new instance."""
        self.base_url = "https://sb1421-sdsheriff.govqa.us"
        self.disclosure_url = f"{self.base_url}/WEBAPP/_rs/(S(440febk1lqle3evjz1flfclo))/openrecordssummary.aspx?sSessionID=108196220221:64729MZBDWXMPFASKVTPS[VKHKV&view=6"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # e.g., ca_san_diego_county_sheriff

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
        logging.info("Starting metadata scraping process.")

        # Step 1: Extract links from main pages
        main_links = self.get_main_page_links()
        logging.debug(f"Extracted {len(main_links)} main page links.")

        # Step 2: Extract metadata from detail pages
        metadata = self.get_detail_page_links(main_links, throttle)
        logging.debug(f"Extracted metadata for {len(metadata)} items.")

        # Write metadata to a JSON file
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        logging.info(f"Metadata written to {outfile}")
        return outfile

    def get_all_page_urls(self) -> List[str]:
        """
        Generate a list of all paginated URLs by navigating sequentially via the "Next" button.

        Returns:
            List[str]: List of URLs for all paginated pages.
        """
        pages_urls = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to the first page
            logging.debug(f"Navigating to {self.disclosure_url}.")
            page.goto(self.disclosure_url)

            # Wait for the first page to load
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception as e:
                logging.warning(f"Error while loading the initial page: {e}")

            while True:
                try:
                    # Capture the current page URL
                    current_url = page.url
                    if current_url not in pages_urls:
                        pages_urls.append(current_url)
                        logging.debug(f"Collected URL: {current_url}")

                    # Check for the "Next" button
                    next_button = page.locator("#gridView_DXPagerBottom_PBN")
                    if (
                        next_button.is_visible()
                        and next_button.get_attribute("aria-disabled") != "true"
                    ):
                        logging.debug("Clicking the 'Next' button.")

                        # Ensure the button is in view and click it
                        next_button.scroll_into_view_if_needed()
                        next_button.click()

                        # Wait for the next page to load
                        page.wait_for_load_state("networkidle", timeout=10000)
                    else:
                        logging.info("No more 'Next' button. Pagination complete.")
                        break

                except Exception as e:
                    logging.warning(f"Error while navigating: {e}")
                    break

            browser.close()

        logging.info(f"Collected URLs for {len(pages_urls)} pages.")
        return pages_urls

    def get_main_page_links(self) -> List[str]:
        """
        Retrieves links from all paginated pages of the site using Playwright.

        Filters links by clicking specific icons (paperclip).

        Returns:
            List[str]: A list of URLs for detailed pages.
        """
        page_urls = self.get_all_page_urls()
        main_links = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for page_url in page_urls:
                logging.debug(f"Processing page: {page_url}")
                page.goto(page_url)
                try:
                    page.wait_for_selector("fa fa-paperclip", timeout=10000)
                except Exception as e:
                    logging.warning(f"No paperclip icons found on page {page_url}: {e}")
                    continue

                # Click the paperclip icon to access detailed pages
                icons = page.locator("fa fa-paperclip")
                for i in range(icons.count()):
                    try:
                        icons.nth(i).scroll_into_view_if_needed()
                        icons.nth(i).click(timeout=5000)

                        # Wait for the new page to load
                        page.wait_for_load_state("networkidle", timeout=5000)

                        # Add the new page URL to main_links
                        main_links.append(page.url)

                        # Navigate back to the main page
                        page.go_back()
                        page.wait_for_load_state("networkidle", timeout=5000)

                    except Exception as e:
                        logging.warning(
                            f"Failed to click paperclip icon on page {page_url}: {e}"
                        )

            browser.close()

        logging.info(f"Extracted {len(main_links)} main page links.")
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

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for link in main_links:
                logging.debug(f"Navigating to detail page: {link}")
                page.goto(link)
                try:
                    page.wait_for_selector("a.qac_link", timeout=10000)
                except Exception as e:
                    logging.warning(f"Detail links not loaded for {link}: {e}")
                    continue

                # Extract downloadable links
                detail_links = page.locator("a.qac_link")
                for i in range(detail_links.count()):
                    href = detail_links.nth(i).get_attribute("onclick")
                    if href and "Open" in href:
                        asset_url = href.split(",")[2].strip().strip('"')
                        case_id = asset_url.split("/")[-1]
                        metadata.append(
                            {
                                "asset_url": asset_url,
                                "case_id": case_id,
                                "name": case_id,
                                "title": case_id,
                                "parent_page": link,
                            }
                        )

                time.sleep(throttle)

            browser.close()

        logging.info(f"Extracted metadata for {len(metadata)} detail links.")
        return metadata
