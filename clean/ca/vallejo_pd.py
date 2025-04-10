import logging
import time
from pathlib import Path
from typing import Dict, List, Set

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError, sync_playwright

from .. import utils
from ..cache import Cache

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

REMOVE_PROCESSED_FOLDER = False
FOLDER_PROCESS_LIMIT = 1000  # Maximum subfolders to process
MAX_FILE_PAGES = 20  # Maximum number of file pages per folder (to avoid infinite loops)

# Add a flag to control pagination debugging.
DEBUG_PAGINATION = True


class Site:
    """Scrape file metadata for the Vallejo Police Department."""

    name = "Vallejo Police Department"

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
    ):
        """Initialize a new instance."""
        self.base_url = "https://www.vallejopd.net"
        self.disclosure_url = f"{self.base_url}/public_information/codes_policies/penal_code_832_7__sb1421_"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)
        self.visited_folders: Set[str] = (
            set()
        )  # Track visited folder unique identifiers
        self.failed_folders: List[str] = []  # Track folders that could not be scraped

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # e.g., ca_vallejo_pd

    def scrape_meta(self, throttle: int = 4) -> Path:
        """Build a static list of main folder names, process each main folder and its subfolders, grab file links and metadata, and write them to a JSON file."""
        logging.info("Starting metadata scraping process.")
        metadata: List[Dict] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            logging.info(f"Navigating to {self.disclosure_url}")
            page.goto(self.disclosure_url)

            try:
                # Wait up to 30 seconds for the main folder selector to appear.
                page.wait_for_selector("div.item.docTitle", timeout=30000)
            except TimeoutError:
                logging.error(
                    "Timed out waiting for main folders to load. Check selector 'div.item.docTitle'."
                )
                return self._save_metadata(metadata)

            # Wait until at least one main folder's text is not "Loading..."
            max_attempts = 10
            attempt = 0
            while attempt < max_attempts:
                main_folder_elements = page.locator("div.item.docTitle").all()
                if main_folder_elements and any(
                    el.inner_text().strip().lower() != "loading..."
                    for el in main_folder_elements
                ):
                    break
                logging.debug(
                    "Main folder texts are still 'Loading...'; waiting a bit more."
                )
                time.sleep(2)
                attempt += 1

            # Build a static list of main folder names.
            main_folder_elements = page.locator("div.item.docTitle").all()
            if not main_folder_elements:
                logging.error(
                    "No main folder elements found. Check selector and page content."
                )
                return self._save_metadata(metadata)

            main_folder_names = []
            for el in main_folder_elements:
                text = el.inner_text().strip()
                main_folder_names.append(text)
            logging.info(
                f"Found {len(main_folder_names)} main folders: {main_folder_names}"
            )

            # Process each main folder.
            for idx, main_folder_name in enumerate(main_folder_names, start=1):
                logging.info(f"Processing main folder {idx}: '{main_folder_name}'")
                try:
                    # Locate the main folder element by its text.
                    folder_locator = page.locator(
                        "div.item.docTitle", has_text=main_folder_name
                    ).first
                    folder_locator.click(timeout=5000)
                    time.sleep(throttle)
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception as e:
                    logging.error(
                        f"Error opening main folder '{main_folder_name}': {e}"
                    )
                    self.failed_folders.append(main_folder_name)
                    continue

                # Process the current main folder.
                self._scrape_folder(
                    page, metadata, throttle, folder_path=[main_folder_name]
                )

                # Return to the disclosure page.
                try:
                    logging.info(
                        f"Returning from main folder '{main_folder_name}' to main folder list."
                    )
                    page.goto(self.disclosure_url)
                    page.wait_for_selector("div.item.docTitle", timeout=20000)
                    time.sleep(throttle)
                except Exception as e:
                    logging.error(
                        f"Error returning from main folder '{main_folder_name}': {e}"
                    )

        if self.failed_folders:
            logging.info("The following folders were not able to be scraped:")
            for folder in self.failed_folders:
                logging.info(f"  - {folder}")
        else:
            logging.info("All folders were scraped successfully.")

        return self._save_metadata(metadata)

    def _scrape_folder(
        self, page, metadata: List[Dict], throttle: int, folder_path: list
    ):
        """
        Process the current folder.

        For each page in this folder:
          1. Scrape file URLs and metadata.
          2. Process any subfolders on that same page.
          3. Navigate to the next page (if available).

        File metadata includes:
            - folder_title: folder_path[-1]
            - folder_path: " > ".join(folder_path)
            - main_folder: folder_path[0]
        """
        folder_files: List[Dict] = []
        page_counter = 1
        while page_counter <= MAX_FILE_PAGES:
            logging.info(
                f"Processing page {page_counter} of folder: {' > '.join(folder_path)}"
            )

            # Scrape file links on the current page.
            self._scrape_files(page, folder_files, folder_path)

            # Process any subfolders found on the current page.
            self._process_subfolders(page, metadata, throttle, folder_path)

            # Try to navigate to the next file page.
            if not self._navigate_next_page(page, throttle):
                break
            page_counter += 1

        total_files = len(folder_files)
        for idx, file_data in enumerate(folder_files):
            file_data["file_index"] = idx + 1
            file_data["total_files"] = total_files
            file_data["main_folder"] = folder_path[0] if folder_path else ""
        metadata.extend(folder_files)

    def _process_subfolders(
        self, page, metadata: List[Dict], throttle: int, folder_path: list
    ):
        """
        Look for subfolder links on the current page and process each new one found.

        Uses the full folder path as a unique identifier.
        """
        subfolder_locator = page.locator("a.documentDetailsToggle")
        subfolder_count = subfolder_locator.count()
        logging.debug(f"Subfolder count on current page: {subfolder_count}")
        if subfolder_count == 0:
            logging.info("No subfolders to process on this page.")
            return

        subfolder_elements = subfolder_locator.all()
        for folder_element in subfolder_elements:
            folder_text = folder_element.inner_text().strip()
            if not folder_text:
                continue

            # Create a unique folder identifier.
            folder_id = " > ".join(folder_path + [folder_text])
            if folder_id in self.visited_folders:
                logging.debug(f"Folder '{folder_id}' already visited; skipping.")
                continue
            if len(self.visited_folders) >= FOLDER_PROCESS_LIMIT:
                logging.info(
                    f"Reached folder limit of {FOLDER_PROCESS_LIMIT}; skipping further subfolders."
                )
                return

            try:
                folder_element.scroll_into_view_if_needed(timeout=10000)
            except Exception as e:
                logging.error(f"Error scrolling folder '{folder_id}' into view: {e}")
                folder_element = page.locator(
                    "a.documentDetailsToggle", has_text=folder_text
                ).first
                try:
                    folder_element.scroll_into_view_if_needed(timeout=10000)
                except Exception as e2:
                    logging.error(
                        f"Re-trying scroll failed for folder '{folder_id}': {e2}"
                    )
                    continue
            try:
                if not folder_element.is_visible():
                    logging.debug(f"Folder '{folder_id}' is not visible; skipping.")
                    self.failed_folders.append(folder_id)
                    continue
            except PlaywrightError as pe:
                logging.error(
                    f"Error checking visibility for folder '{folder_id}': {pe}"
                )
                self.failed_folders.append(folder_id)
                continue

            self.visited_folders.add(folder_id)
            logging.info(f"Navigating into subfolder: {folder_id}")
            try:
                folder_element.click(timeout=10000)
                time.sleep(throttle)
                page.wait_for_load_state("networkidle", timeout=10000)
                # Recursively scrape the subfolder.
                self._scrape_folder(
                    page, metadata, throttle, folder_path=folder_path + [folder_text]
                )
            except Exception as e:
                logging.error(f"Error navigating into folder '{folder_id}': {e}")
                self.failed_folders.append(folder_id)
                continue
            try:
                page.wait_for_selector("li.openfolderback > a", timeout=10000)
                back_button = page.locator("li.openfolderback > a").first
                if back_button and back_button.is_visible():
                    logging.info(f"Returning to parent folder from '{folder_id}'.")
                    back_button.click(timeout=10000)
                    page.wait_for_load_state("networkidle", timeout=10000)
                    time.sleep(throttle)
                else:
                    logging.warning(
                        f"Back button not found or not visible after processing '{folder_id}'."
                    )
                    self.failed_folders.append(folder_id)
                    continue
            except Exception as e:
                logging.error(
                    f"Error clicking back button after folder '{folder_id}': {e}"
                )
                self.failed_folders.append(folder_id)
                continue

    def _scrape_files(self, page, folder_files: List[Dict], folder_path: list):
        """Scrape file URLs and metadata on the current file page."""
        try:
            page.wait_for_selector("a.downloaditem", timeout=10000)
        except TimeoutError:
            logging.debug("No file elements found on this page.")
            return
        file_elements = page.query_selector_all("a.downloaditem")
        logging.info(
            f"Found {len(file_elements)} file elements on {page.url} in folder '{folder_path[-1] if folder_path else ''}'."
        )
        for file_element in file_elements:
            file_url = file_element.get_attribute("href")
            file_name = file_element.inner_text().strip()
            if file_name.lower() == "download":
                logging.debug("Skipping duplicate file with title 'Download'.")
                continue

            folder_files.append(
                {
                    "asset_url": file_url,
                    "case_id": folder_path[-1] if folder_path else "",
                    "name": file_name,
                    "parent_page": page.url,
                    "details": folder_path[0] if folder_path else "",
                }
            )

    def _navigate_next_page(self, page, throttle: int) -> bool:
        """
        Navigate to the next file page using pagination buttons.

        When the next page is greater than page 3, click the 'Next Page' element:
        <a href="#" class="pageButton" tag="+1" title="Next Pages"><em class="fa fa-arrow-right"></em></a>
        """
        try:
            pagination_buttons = page.locator("a.pageButton")
            count = pagination_buttons.count()
            if count == 0:
                logging.debug("No pagination buttons found.")
                return False

            active_page = None
            for i in range(count):
                btn = pagination_buttons.nth(i)
                classes = btn.get_attribute("class") or ""
                if "active" in classes:
                    try:
                        active_page = int(btn.inner_text().strip())
                        logging.debug(f"Active page determined: {active_page}")
                    except ValueError:
                        active_page = None
                    break
            if active_page is None:
                logging.debug("No active pagination button found.")
                return False

            target_page = active_page + 1
            logging.info(
                f"Attempting to navigate from page {active_page} to page {target_page}."
            )

            # For pages after page 3, click the special "Next Page" button.
            if target_page > 3:
                # Wait for the "Next Page" button to appear using the updated selector.
                page.wait_for_selector("a.pageButton[tag='+1']", timeout=10000)
                next_button = page.locator("a.pageButton[tag='+1']").first
                if not next_button or not next_button.is_visible():
                    logging.debug("No visible 'Next Page' button found.")
                    return False
                logging.info(
                    f"Clicking 'Next Page' button to navigate from page {active_page} to page {target_page}."
                )
                next_button.click(timeout=10000)
            else:
                # Wait explicitly for the target pagination button to be visible
                selector = f"a.pageButton:has-text('{target_page}')"
                page.wait_for_selector(selector, timeout=10000)
                target_button = page.locator(
                    "a.pageButton", has_text=str(target_page)
                ).first
                if not target_button or not target_button.is_visible():
                    logging.debug(
                        f"No visible pagination button for page {target_page}."
                    )
                    return False
                logging.info(f"Clicking pagination button for page {target_page}.")
                target_button.click(timeout=10000)

            # If pagination debugging is enabled, pause for inspection.
            if DEBUG_PAGINATION:
                logging.debug(
                    "Pausing after clicking target page for pagination debugging..."
                )

            time.sleep(throttle)
            page.wait_for_load_state("networkidle", timeout=10000)
            return True
        except Exception as e:
            logging.error(f"Error navigating to the next page: {e}")
            return False

    def _save_metadata(self, metadata: List[Dict]) -> Path:
        """Save collected metadata to a JSON file."""
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)  # type: ignore
        logging.info(f"Metadata written to {outfile}")
        return outfile
