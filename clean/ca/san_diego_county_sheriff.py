import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import List

from playwright.sync_api import sync_playwright

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

    def scrape_meta(self, throttle: int = 4) -> Path:
        """
        Download CSV file, extract request numbers, and scrape metadata.

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 4.

        Returns:
            Path: Local path of JSON file containing metadata.
        """
        logging.info("Starting metadata scraping process.")

        # Step 1: Download and read the CSV file
        request_numbers = self.download_and_parse_csv()

        # Step 2: Scrape metadata for each request number
        metadata = self.scrape_for_request_numbers(request_numbers, throttle)

        # Write metadata to a JSON file
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        logging.info(f"Metadata written to {outfile}")
        return outfile

    def download_and_parse_csv(self) -> List[str]:
        """
        Download the CSV file, parse it, and extract request numbers.

        Returns:
            List[str]: A list of request numbers extracted from the CSV file.
        """
        logging.info("Downloading CSV file.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            try:
                # Navigate to the disclosure page
                logging.debug(f"Navigating to {self.disclosure_url}.")
                page.goto(self.disclosure_url)
                page.wait_for_load_state("networkidle", timeout=10000)

                # Locate and click the dropdown arrow to export formats
                dropdown_arrow = page.locator("#gridView_DXCTMenu0_DXI1_T")
                dropdown_arrow.click()
                page.wait_for_timeout(1000)

                # Select and click the CSV option
                csv_option = page.locator("text=CSV")
                csv_button = page.get_by_role("menuitem").filter(has=csv_option)
                csv_button.click()

                # Wait for the file to download
                download = page.wait_for_event("download")
                download_path = (
                    self.cache_dir / "san_diego_county_sheriff_cases_012325.csv"
                )
                download.save_as(str(download_path))

                logging.info(f"CSV file downloaded to {download_path}.")

                # Read and parse the CSV file
                with open(download_path, encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    request_numbers = [row["Request Number"] for row in reader]

                logging.info(f"Extracted {len(request_numbers)} request numbers.")
                return request_numbers

            except Exception as e:
                logging.error(f"Error during CSV download or parsing: {e}")
                return []

            finally:
                browser.close()

    def scrape_for_request_numbers(
        self, request_numbers: List[str], throttle: int
    ) -> List[MetadataDict]:
        """
        Scrape data for each request number.

        Args:
            request_numbers (List[str]): List of request numbers to search for.
            throttle (int): Number of seconds to wait between requests.

        Returns:
            List[MetadataDict]: A list of metadata dictionaries for all request numbers.
        """
        metadata: List[MetadataDict] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            try:
                for request_number in request_numbers:
                    logging.debug(f"Processing request number: {request_number}")

                    # Reload the disclosure page for each request number
                    page.goto(self.disclosure_url)
                    page.wait_for_load_state("networkidle", timeout=10000)

                    try:
                        search_input = page.locator("input#txtRefsearch_I")
                        search_input.fill(request_number)
                        search_input.press("Enter")

                        # Wait for results to load
                        page.wait_for_selector(
                            "i.fa.fa-arrow-circle-o-right", timeout=15000
                        )

                        # Navigate to the detailed page and extract metadata
                        page_metadata = self.scrape_detail_page(
                            page, throttle, request_number
                        )
                        metadata.extend(page_metadata)

                    except Exception as e:
                        logging.error(
                            f"Failed to process request number {request_number}: {e}"
                        )

                    time.sleep(throttle)

            finally:
                browser.close()

        return metadata

    def scrape_detail_page(
        self, page, throttle: int, request_number: str
    ) -> List[MetadataDict]:
        """
        Navigate to the detailed page and extract metadata.

        Args:
            page: The Playwright page object.
            throttle (int): Number of seconds to wait between actions.
            request_number (str): The request number being processed.

        Returns:
            List[MetadataDict]: A list of metadata dictionaries from the detail page.
        """
        page_metadata: List[MetadataDict] = []

        try:
            # Click the arrow icon to go to the detail page
            detail_icon = page.locator("i.fa.fa-arrow-circle-o-right").first
            detail_icon.click()
            page.wait_for_load_state("networkidle", timeout=10000)

            # Extract metadata from the detail page
            detail_links = page.locator("a.qac_link")
            for i in range(detail_links.count()):
                try:
                    onclick_attr = detail_links.nth(i).get_attribute("onclick")
                    if onclick_attr:
                        url_match = re.search(r'"(https?://[^"\s]+)"', onclick_attr)
                        name = detail_links.nth(i).inner_text().strip()
                        if url_match:
                            href = url_match.group(1)
                            case_id_match = re.search(
                                r"%2Fpublicrecords%2F([^%]+)", href
                            )
                            title = (
                                case_id_match.group(1)
                                if case_id_match
                                else "Unknown Title"
                            )
                            case_id = "".join(filter(str.isdigit, name))
                            if not case_id:
                                case_id = request_number
                            page_metadata.append(
                                {
                                    "asset_url": href,
                                    "case_id": case_id,
                                    "name": name + ".zip",
                                    "title": title,
                                    "parent_page": page.url,
                                }
                            )
                except Exception as e:
                    logging.warning(f"Error extracting detail link {i}: {e}")

            # Go back to the main page
            page.goto(self.disclosure_url)
            page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(throttle)

        except Exception as e:
            logging.error(f"Error navigating to the detail page: {e}")

        return page_metadata
