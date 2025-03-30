import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from clean import utils
from clean.cache import Cache
from clean.utils import MetadataDict

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

data_dir: Path = utils.CLEAN_DATA_DIR
cache_dir: Path = utils.CLEAN_CACHE_DIR
cache = Cache(cache_dir)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    start_url = "https://elcajoncatcm.tylerhost.net/tylercm4992prod/web/"
    logger.debug(f"Retrieving {start_url}")
    page.goto(start_url)
    page.wait_for_load_state("networkidle", timeout=2000)
    # page.locator("#submit").click()
    page.get_by_text("I Acknowledge").click()
    page.wait_for_load_state("networkidle", timeout=2000)

    page.locator("#middle").get_by_role("link", name="Police Documents").click()
    page.wait_for_load_state("networkidle", timeout=2000)

    casenumbers = []
    soup = BeautifulSoup(page.content(), features="lxml")
    myselect = soup.find("select").find_all("option")  # type: ignore
    for myoption in myselect:
        if len(myoption["value"]) >= 3:
            casenumbers.append(myoption["value"])
    logger.debug(f"{' ...'.join(casenumbers)}")

    page.wait_for_load_state("networkidle", timeout=10000)

    case_search_url = page.url

    metadata = []

    for i, casenumber in enumerate(casenumbers[0]):
        logger.debug(
            f"Hunting docs for case {i}/{len(casenumbers):,} in {casenumber}"
        )
        searchtext = "SB1421 Peace Officer Release of Records"
        page.type("input#text.text", searchtext)
        page.locator("select#_EC_CaseNumber").select_option(casenumber)
        page.locator("input.search").click()

        page.wait_for_load_state("networkidle", timeout=2000)

        # Now we should be at the case index page.
        # Need to check to see if it's paginated.

        soup = BeautifulSoup(page.content(), features="lxml")
        pagebanner = soup.find("span", class_="pagebanner")
        if "found, displaying all items." not in pagebanner:
            logger.error(f"!!!Missing pagination for case {casenumber}")

        # Prep the page in a couple ways
        page.locator("u.tableHeaderAction#addAllToPdf").click()

        # <u class="tableHeaderAction" id="addAllToPdf">Add All to My Images</u>


# Use CDP to set download path and default naming
# https://chromedevtools.github.io/devtools-protocol/tot/Browser/#method-setDownloadBehavior
# CDP implementation example here https://gist.github.com/mezhgano/bd9fee908378ee87589b727906da55db


metadata = "beer"

outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
with open(outfile, "w", encoding="utf-8") as f:
    json.dump(metadata, f, indent=2)

logging.info(f"Metadata written to {outfile}")
#   return outfile





class Site:
    """Scrape file metadata for the El Cajon Police Department."""

    name = "El Cajon Police Department"

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
    ):
        """Initialize a new instance."""
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

        # https://github.com/biglocalnews/clean-scraper/blob/elcajon-194/elcajon.ipynb


"""

            Example link

            Generate document: https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/viewAttachment.jsp?docName=Evidence_List.pdf&id=DOC24S27.A0&parent=DOC24S27

            Download document: https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/downloads/Evidence_List.pdf.pdf?id=DOC24S27.A0&parent=DOC24S27

            So an effort:
            https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/viewAttachment.jsp?docName=Statement_of_Case.pdf&id=DOC24S28.A0&parent=DOC24S28
            to
            https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/downloads/Statement_of_Case.pdf.pdf&id=DOC24S28.A0&parent=DOC24S28


"""
"""
    page.goto("https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/viewAttachment.jsp?docName=Statement_of_Case.pdf&id=DOC24S28.A0&parent=DOC24S28")

    page.wait_for_load_state("networkidle", timeout=10000)

    page.goto("https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/downloads/Statement_of_Case.pdf.pdf&id=DOC24S28.A0&parent=DOC24S28")

    page.wait_for_load_state("networkidle", timeout=10000)
"""
