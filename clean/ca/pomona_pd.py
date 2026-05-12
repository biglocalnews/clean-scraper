import logging
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .. import utils
from ..cache import Cache
from .config.pomona_pd import request_body

logger = logging.getLogger(__name__)


class Site:
    """Scrape file metadata and download files for the City of Pomona Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Pomona Police Department"

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
        self.base_url = "https://sb1421-pomona.govqa.us/WEBAPP/_rs/(S(lhl3lg2etd0r45ktfusanto4))/openrecordssummary.aspx?view=6"
        self.child_page_url = "https://sb1421-pomona.govqa.us/WEBAPP/_rs/(S(lhl3lg2etd0r45ktfusanto4))/RequestArchiveDetails.aspx?rid="
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_pomona_pd

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_pomona_pd/openrecordssummary.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1].split('.')[0]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.base_url, force=True)
        metadata = []
        local_index_pages = []
        local_index_pages.append(filename)
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        content_areas = soup.find("table", id="gridView")
        pages_element = content_areas.find("b", class_="dxp-lead dxp-summary")
        total_pages = self.extract_total_pages(pages_element.get_text(strip=True))
        page_no = 1
        print(total_pages)
        captured_requests = self.get_headers_and_cookies()
        if len(captured_requests) > 0:
            while page_no < total_pages:
                child_name = f"pomona_{page_no+1}"
                updated_request_body = request_body.replace("PN99", f"PN{page_no}")
                child_filename = f"{self.agency_slug}/{child_name}.html"
                output_file = self.cache_dir.joinpath(child_filename)
                with utils.post_url(
                    captured_requests[-1]["url"],
                    headers=captured_requests[-1]["headers"],
                    cookies=captured_requests[-1]["cookies"],
                    data=updated_request_body,
                ) as r:
                    res_text = r.text
                    res_text = res_text.split("'html':")[1][1:-2]
                    res_text = res_text.split('<table id="gridView_DXMainTable"')[
                        1
                    ].split('<div class="dxmLite_MaterialCompact dxm-ltr"')[0]
                    res_text = f"{{<table id='gridView_DXMainTable'}}{res_text}"
                    self.cache.write(output_file, res_text)
                    local_index_pages.append(child_filename)
                    logger.debug("Writing to Child Page")
                    print("Writing to Child Page")
                    page_no += 1
                    time.sleep(throttle)

        print(local_index_pages)
        case_details = []
        for page in local_index_pages:
            html = self.cache.read(page)
            soup = BeautifulSoup(html, "html.parser")
            content_area = soup.find("table", id="gridView_DXMainTable")
            data_rows = content_area.find_all(
                "tr", class_="dxgvDataRow_MaterialCompact"
            )
            for row in data_rows:
                columns = row.find_all("td")
                column_texts = [v.get_text(strip=True) for v in columns[:-1]]
                a_tag = columns[-1].find("a")
                onclick_attr = a_tag.get("onclick", "")
                match = re.search(r"redirectInfo\('(\d+)'\)", onclick_attr)
                # Extract the ID if a match is found
                if match:
                    ref_id = match.group(1)
                else:
                    ref_id = None

                if ref_id:
                    child_name = f"{column_texts[0]}.html"
                    child_filename = f"{self.agency_slug}/{child_name}"
                    child_request_url = f"{self.child_page_url}{ref_id}&view=6"
                    self.cache.download(child_filename, child_request_url, force=True)
                    print(child_request_url)
                    info_dict = {
                        "request_number": column_texts[0],
                        "create_date": column_texts[1],
                        "summary": column_texts[2],
                        "request_status": column_texts[3],
                        "reference_id": ref_id,
                        "child_file_name": child_filename,
                    }
                    case_details.append(info_dict)

        for each_case in case_details:
            html = self.cache.read(each_case["child_file_name"])
            soup = BeautifulSoup(html, "html.parser")
            container = soup.find("div", class_="container")
            case_data = self.get_clean_data(container)
            attachment_container = container.find("div", id="divAttachment")
            if attachment_container:
                file_rows = soup.find_all(
                    "div", class_="row", style="background-color:#F5F5F5"
                )
                for row in file_rows:
                    attachment_details = self.get_attachment_details(row)
                    if attachment_details["asset_url"]:
                        payload = {
                            "asset_url": attachment_details["asset_url"],
                            "case_id": case_data["Case Number"],
                            "name": attachment_details["file_name"],
                            "title": attachment_details["file_name"].split(".")[0],
                            "parent_page": str(each_case["child_file_name"]),
                            "details": {
                                "upload_date": attachment_details["date"],
                                "request_number": each_case["request_number"],
                                "create_date": each_case["create_date"],
                                "summary": each_case["summary"],
                                "request_status": each_case["request_status"],
                                "SB_1421_Type": case_data["SB 1421 Type"],
                                "incedent_date": case_data["Incident Date"],
                                "employee_name": case_data["Employee Name"],
                                "suspect_name": case_data["Suspect Name"],
                            },
                        }
                        metadata.append(payload)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def extract_total_pages(self, text):
        # Regular expression to find page information
        pattern = r"Page (\d+) of (\d+)"

        # Find all matches in the text
        matches = re.findall(pattern, text)

        # Extract the maximum total pages from the matches
        total_pages = 0
        for match in matches:
            current_page, total_page = map(int, match)
            if total_page > total_pages:
                total_pages = total_page

        return total_pages

    def get_headers_and_cookies(self):
        logger.debug("Getting Cookies and Headers")
        captured_requests = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True
            )  # Launch Chromium in headless mode
            context = browser.new_context()  # Create a new browser context
            page = context.new_page()  # Create a new page

            # Capture network requests
            def handle_request(request):
                if "https://sb1421-pomona.govqa.us/WEBAPP/" in request.url:
                    request_info = {
                        "url": request.url,
                        "headers": request.headers,
                        "cookies": {
                            cookie["name"]: cookie["value"]
                            for cookie in context.cookies()
                        },
                    }
                    captured_requests.append(request_info)

            # Attach the event listener for network requests
            page.on("request", handle_request)

            # Visit the base URL
            page.goto(self.base_url)

            # Scroll to and click the "Next" button if it exists
            try:
                next_button = page.locator('a[aria-label="Next"]')
                next_button.scroll_into_view_if_needed()
                next_button.click()
            except Exception as e:
                logger.error(f"Could Not Find Next button: {e}")
                return []

            # Wait for requests to complete
            page.wait_for_timeout(10000)  # Adjust based on load time

            # Close the browser
            browser.close()

        return captured_requests

    def get_clean_data(self, container):
        data = {}
        # Extracting required values
        data["Reference No"] = (
            container.find("span", text="Reference No:").find_next("p").text
        )
        data["SB 1421 Type"] = (
            container.find("span", text="SB 1421 Type:").find_next("p").text.strip()
        )
        data["Incident Date"] = (
            container.find("span", text="Incident Date:").find_next("p").text
        )
        data["Case Number"] = (
            container.find("span", text="Case Number:").find_next("p").text
        )
        data["Employee Name"] = (
            container.find("span", text="Employee Name:").find_next("p").text
        )
        data["Suspect Name"] = (
            container.find("span", text="Suspect Name:").find_next("p").text
        )
        return data

    def get_attachment_details(self, row):
        date = row.find("div", class_="col-md-2 col-sm-2").text.strip()
        # Extract file name from the anchor tag
        file_name_tag = row.find("a", class_="qac_link")
        file_name = file_name_tag.text.strip() if file_name_tag else None

        # Extract hidden Azure URL
        azure_url_tag = row.find("input", {"value": lambda x: x and "pomona" in x})
        azure_url = azure_url_tag["value"] if azure_url_tag else None

        # Save the extracted information
        attachment_details = {
            "date": date,
            "file_name": file_name,
            "asset_url": azure_url,
        }
        return attachment_details
