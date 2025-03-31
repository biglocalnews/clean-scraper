import csv
import datetime
import json
import logging
import os
import re
import time
from copy import deepcopy
from glob import glob
from pathlib import Path
from typing import List
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from clean import utils
from clean.cache import Cache
from clean.utils import MetadataDict

"""
QA and to-do:
-- Test with multiple search texts
-- Should probably build out a function that will only begin scraping metadata if the metadata file doesn't already exist? No sense in rescraping metadata each time we're trying to fix a bug in the asset download phase. Probably.
-- Metadata needs a check to see if a file suffix is added on; different site endpoints give different file extensions in some cases, e.g., .pdf.pdf. The full scrape should fix the metadata where possible.
-- Asset download functionality should see if there's a filename starting with whatever fragment is in the asset_url.
-- Need to handle that one DOCX differently for asset download.
-- Stop adding all the URLs to the "to be downloaded" queue thing, then go through and see if any non-PDF classes show up in any of those files. Store the class, if available. Probably not for the DOCX.
-- If there's any hint of non-PDF files with the one exception, asset handling will likely need to change


QA done:
-- Searching with no text gets more records than searching with the string that starts with SB1421. Kill the search text for now, but at some point should probably test with both and see if anything's missing.

"""


# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

slug = "ca_el_cajon_pd"

data_dir: Path = utils.CLEAN_DATA_DIR
cache_dir: Path = utils.CLEAN_CACHE_DIR
cache = Cache(cache_dir)

datajson = data_dir / f"{slug}.json"

rescrapeneeded = False

asset_dir = cache_dir / f"../assets/{slug}"

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

    if (
        not os.path.exists(datajson) or rescrapeneeded
    ):  # Do we need to get metadata again?

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
            logger.debug(
                f"Hunting docs for case {i+1}/{len(casenumbers):,} in {casenumber}"
            )
            page.locator("select#_EC_CaseNumber").select_option(casenumber)
            # searchtext = "SB1421 Peace Officer Release of Records"
            # page.type("input#text.text", searchtext)
            # page.locator("input#text").fill(searchtext)
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

                mytable = soup.find(id="searchResultsTable")

                for row in mytable.find_all("tr")[1:]:
                    line = {}
                    firstcell = row.find_all("td")[0]
                    secondcell = row.find_all("td")[1]
                    thirdcell = row.find_all("td")[2]
                    line["asset_url"] = (
                        "https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/"
                        + thirdcell.find("a")["href"]
                    )
                    linetitle = firstcell.text.replace(
                        "Peace Officer Release of Records", ""
                    ).strip()

                    # counterexample on docName / asset URL: 10006643  "Face Page"
                    queries = parse_qs(urlparse(line["asset_url"]).query)
                    if "docName" in queries:
                        line["name"] = queries["docName"][0]
                    else:
                        logger.debug(
                            f"Missing docName for case {casenumber}, {linetitle}"
                        )
                        line["name"] = f"TBD {linetitle}"

                    line["parent_page"] = case_search_url
                    line["title"] = linetitle
                    line["case_id"] = casenumber
                    line["details"] = {}

                    if "id" in queries:
                        line["details"]["docid"]: queries["id"][0]
                        line["details"]["parentdoc"]: queries["parent"][0]
                    else:
                        logger.debug(f"Missing ID for case {casenumber}, {linetitle}")

                    details = secondcell.find("a").contents
                    for deeti in range(0, len(details) // 3):
                        deettitle = (
                            details[deeti * 3]
                            .text.split(":")[0]
                            .strip()
                            .lower()
                            .replace(" ", "_")
                        )
                        deetcontents = details[deeti * 3 + 1].text.strip()
                        line["details"][deettitle] = deetcontents
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
                        page.wait_for_timeout(2000)  # Their server suuucks
                        page.get_by_text("Next", exact=True).first.click()
                        page.wait_for_load_state("networkidle", timeout=2000)

            page.wait_for_timeout(500)  # Their server suuucks

            page.goto(case_search_url)

            page.wait_for_load_state("networkidle", timeout=2000)

            # <u class="tableHeaderAction" id="addAllToPdf">Add All to My Images</u>

        # Use CDP to set download path and default naming
        # https://chromedevtools.github.io/devtools-protocol/tot/Browser/#method-setDownloadBehavior
        # CDP implementation example here https://gist.github.com/mezhgano/bd9fee908378ee87589b727906da55db

        cache.write_json(datajson, metadata)
        logging.info(f"Metadata written to {datajson}")

    # Browser's still open. Let's start working downloads.

    metadata = cache.read_json(datajson)
    logger.debug(f"Trying to find about {len(metadata):,} assets.")

    filesdownloaded = 0

    s = requests.Session()
    useragent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36)"
    s.headers.update({"User-Agent": useragent})
    s.get("https://elcajoncatcm.tylerhost.net/tylercm4992prod/web/")
    payload = "submit=Public+Login&guest=true"  # &submit=I+Acknowledge"
    r = s.post(
        f"https://elcajoncatcm.tylerhost.net/tylercm4992prod/web/loginPOST.jsp",
        data=payload,
        allow_redirects=True,
    )
    s.cookies.set("isLoggedInAsPublic", "true")
    s.cookies.set("sortField", "Document+Relevance")
    s.cookies.set("sortDir", "asc")
    s.cookies.set("pageSize", "100")
    policedocs = "https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/customSearch.jsp?pageId=PoliceDocs"
    s.get(policedocs)

    warnings = []

    for entryindex, entry in enumerate(metadata):
        targetdir = asset_dir / entry["case_id"]
        targetdir.mkdir(parents=True, exist_ok=True)  # Make sure the case folder exists
        # existingfiles = sorted(targetdir.glob("*"))
        if not glob(
            str(targetdir / f"{entry['name']}*")
        ):  # If we don't have it, get it
            r = s.get(entry["asset_url"])
            # time.sleep(15)
            # logger.debug(r.content)
            soup = BeautifulSoup(r.content, features="lxml")
            if "iframe" not in str(soup):
                warning = f"No iframe found in entry {entryindex} with a name of {entry['name']} and an asset url of {entry['asset_url']}."
                logger.debug(warning)
                warnings.append(warning)
            else:

                docurl = soup.find("iframe")["src"]
                if docurl.startswith("downloads/"):
                    docurl = (
                        "https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/"
                        + docurl
                    )
                farfile = docurl.split("/")[-1].split("?")[0]
                if "." not in entry["name"]:  # If we're missing a file extension
                    entry["name"] = farfile
                    metadata[entryindex]["name"] = farfile
                    cache.write_json(datajson, metadata)

                targetfilename = str(targetdir / entry["name"])
                r = s.get(docurl)
                if r.ok:
                    with open(targetfilename, "wb") as outfile:
                        outfile.write(r.content)

                    nowstamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    metadata[entryindex]["details"]["downloadedtime"] = nowstamp
                    cache.write_json(datajson, metadata)

                    filesdownloaded += 1

                    logger.debug(
                        f"{filesdownloaded:,} file downloaded in this pass so far."
                    )

    logger.debug(f"Warnings found: {' ... '.join(warnings)}")

    # We need the file. Hit the file's landing page to start generating it.
    # page.goto(entry['asset_url'])
    # page.wait_for_load_state("networkidle", timeout=25000)

    # soup = BeautifulSoup(page.content(), features="lxml")
    # holder = soup.find("div", id="image")
    # print(holder)
    # localhref = holder.find("a")['href']
    # if "http" not in localhref:
    #     localhref = "https://elcajoncatcm.tylerhost.net/tylercm4992prod/eagleweb/" + localhref

    # page.evaluate("const sessionStorage = page.evaluate(() => JSON.stringify(sessionStorage)); fs.writeFileSync('session.json', sessionStorage, 'utf-8');")

    # page.goto(localhref)
    # logger.debug("Tying to download")
    # parent = page.locator("div#image")
    # logger.debug("Found parent")
    # child = parent.locator("a").click()

    # page.locator("div#image").get_by_role("a").click()

    # page.locator("div#image").locator("a").click()
    # page.wait_for_load_state("networkidle", timeout=25000)


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
