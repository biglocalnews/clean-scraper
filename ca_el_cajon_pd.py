import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import List
from urllib.parse import urlparse, parse_qs

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

slug = "ca_el_cajon_pd"

data_dir: Path = utils.CLEAN_DATA_DIR
cache_dir: Path = utils.CLEAN_CACHE_DIR
cache = Cache(cache_dir)

# data_dir: C:\Users\stuck\.clean-scraper\exports
# cache_dir: C:\Users\stuck\.clean-scraper\cache

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
    page.wait_for_load_state("networkidle", timeout=10000)

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

    for i, casenumber in enumerate(casenumbers):
        logger.debug(f"Hunting docs for case {i+1}/{len(casenumbers):,} in {casenumber}")
        page.locator("select#_EC_CaseNumber").select_option(casenumber)
        searchtext = "SB1421 Peace Officer Release of Records"
        # page.type("input#text.text", searchtext)
        page.locator("input#text").fill(searchtext)
        # page.locator("input.search").click()
        page.get_by_role("button", name="Search").first.click()

        page.wait_for_load_state("networkidle", timeout=2000)

        # Now we should be at the case index page.
        # Need to check to see if it's paginated.

        pagescomplete = False

        while not pagescomplete:

            soup = BeautifulSoup(page.content(), features="lxml")

            # Convert all the third column links to a "view image" 
            page.locator("u.tableHeaderAction#addAllToPdf").click()
            
            mytable = soup.find(id='searchResultsTable')

            for row in mytable.find_all("tr")[1:]:
                line = {}
                firstcell = row.find_all("td")[0]
                secondcell = row.find_all("td")[1]
                thirdcell = row.find_all("td")[2]
                line['asset_url'] = "https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/" + thirdcell.find("a")['href']
                linetitle = firstcell.text.replace("Peace Officer Release of Records", "").strip()

                # counterexample on docName / asset URL: 10006643  "Face Page"
                queries = parse_qs(urlparse(line['asset_url']).query)
                if "docName" in queries:
                    line['name'] = queries['docName'][0]
                else:
                    logger.debug(f"Missing docName for case {casenumber}, {linetitle}")
                    line['name'] = f"TBD {linetitle}"

                line['parent_page'] = case_search_url
                line['title'] = linetitle
                line['case_id'] = casenumber
                line['details'] = {}
                
                if "id" in queries:
                    line['details']["docid"]: queries['id'][0]
                    line['details']["parentdoc"]: queries['parent'][0]
                else:
                    logger.debug(f"Missing ID for case {casenumber}, {linetitle}")
                    
                details = secondcell.find("a").contents
                for deeti in range(0, len(details)//3):
                    deettitle = details[deeti*3].text.split(":")[0].strip().lower().replace(" ", "_")
                    deetcontents = details[deeti*3 + 1].text.strip()
                    line['details'][deettitle] = deetcontents
                metadata.append(line)

            pagebanner = soup.find("span", class_="pagebanner")
            if not pagebanner:
                logger.error("pagebanner not found")
            elif "found, displaying all items." in pagebanner.text:
                pagescomplete = True
            else:
                pagebannertext = pagebanner.text.strip().split()
                if pagebannertext[0] == pagebannertext[-1].replace(".", ""):
                    logger.debug(f"Final page detected for case {casenumber}")
                    # 106 items found, displaying 101 to 106.
                    pagescomplete = True
                else:
                    logger.debug(f"Fetching another page for case {casenumber}")
                    page.wait_for_timeout(2000)    # Their server suuucks
                    page.get_by_text("Next", exact=True).first.click()
                    page.wait_for_load_state("networkidle", timeout=2000)

        page.wait_for_timeout(500)    # Their server suuucks

        page.goto(case_search_url)
        
        page.wait_for_load_state("networkidle", timeout=2000)

        
        
    
        # <u class="tableHeaderAction" id="addAllToPdf">Add All to My Images</u>


# Use CDP to set download path and default naming
# https://chromedevtools.github.io/devtools-protocol/tot/Browser/#method-setDownloadBehavior
# CDP implementation example here https://gist.github.com/mezhgano/bd9fee908378ee87589b727906da55db


outfile = data_dir.joinpath(f"{slug}.json")
cache.write_json(outfile, metadata)
#with open(outfile, "w", encoding="utf-8") as f:
#    json.dump(metadata, f, indent=2)

logging.info(f"Metadata written to {outfile}")

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
