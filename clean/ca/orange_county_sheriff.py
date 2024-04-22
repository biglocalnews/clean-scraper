import time
import urllib.parse
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the Orange County Sheriffs Department for SB16/SB1421/AB748 data.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Orange County Sheriffs Department"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        """Initialize a new instance.

        Args:
            data_dir (Path): The directory where downstream processed files/data will be saved
            cache_dir (Path): The directory where files will be cached
        """
        # Start page contains list of "detail"/child pages with links to the SB16/SB1421/AB748 videos and files
        # along with additional index pages
        self.base_url = (
            "https://www.ocsheriff.gov/about-ocsheriff/peace-officer-records-releases"
        )
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        # to create a subdir inside the main cache directory to stash files for this agency
        return f"{state_postal}_{mod.stem}"  # ca_orange_county_sheriff

    def scrape_meta(self, throttle=0):
        """Gather metadata on downloadable files (videos, etc.)."""
        current_page = 0
        index_pages = self._download_index_pages(throttle, current_page)
        # TODO: Get the child pages and, you know, actually scrape file metadata
        downloadable_files = self._create_json(current_page)
        return downloadable_files

    # def scrape(self, metadata_csv):

    # Helper functions

    def _create_json(self, current_page) -> Path:
        metadata = []
        file_stem = self.base_url.split("/")[-1]
        # html_location = f"{self.agency_slug}/{file_stem}_index_page{current_page}.html"
        html_location = self.cache.read(
            f"{self.agency_slug}/{file_stem}_index_page{current_page}.html"
        )
        with open(html_location) as hl:
            soup = BeautifulSoup(hl, "html.parser")
        title = soup.find("title").text.strip()
        links = soup.article.find_all("a")
        urls = []
        name = []
        for link in links:
            for link in links:
                if "http" in link["href"]:
                    urls.append(link["href"])
        for url in urls:
            url_to_name = url.split("Mediazip/")[-1]
            url_to_name1 = url_to_name.replace("/", "_")
            url_to_name2 = url_to_name1.replace(".zip", "")
            url_to_name3 = url_to_name2.replace(
                f"{url_to_name2}", f"Orange_County_Sheriffs_Department_{url_to_name2}"
            )
            url_to_name4 = url_to_name3.replace("%20", "_")
            url_to_name5 = url_to_name4.strip()
            name.append(url_to_name5)
        url_dict = {name[i]: urls[i] for i in range(len(urls))}
        for key, value in url_dict.items():
            payload = {
                "title": title,
                "parent_page": str(html_location),
                "asset_url": value,
                "name": key,
            }
            metadata.append(payload)
        # Store the metadata in a JSON file in the data directory
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        # Return path to metadata file for downstream use
        return outfile

    def _download_index_pages(self, throttle, current_page, index_pages=[]):
        """Download index pages for SB16/SB1421/AB748.

        Index pages link to child pages containing videos and
        other files related to use-of-force and disciplinary incidents.

        Returns:
            List of path to cached index pages
        """
        # Pause between requests
        time.sleep(throttle)
        file_stem = self.base_url.split("/")[-1]
        base_file = f"{self.agency_slug}/{file_stem}_index_page{current_page}.html"
        # Construct URL: pages, including start page, have a page GET parameter
        target_url = f"{self.base_url}?page={current_page}"
        # Download the page (if it's not already cached)
        cache_path = self.cache.download(base_file, target_url, "utf-8")
        # Add the path to the list of index pages
        index_pages.append(cache_path)
        return index_pages


"""
# LEGACY CODE BELOW #
def _scrape_list_page(cache, top_level_urls, base_url, throttle):
    second_level_urls = {}
    for top_url in top_level_urls:
        page = requests.get(top_url)
        time.sleep(throttle)
        soup = BeautifulSoup(page.text, "html.parser")
        six_columns = soup.find_all("div", class_="six columns")
        for elem in six_columns:
            paragraph_with_link = elem.find("p")
            if paragraph_with_link is None:
                continue
            else:
                text = paragraph_with_link.text
                elem_a = paragraph_with_link.find("a")
                if elem_a is None:
                    continue
                else:
                    full_link = base_url + elem_a["href"]
                    second_level_urls[full_link] = text
    _download_case_files(base_url, second_level_urls)
    return second_level_urls


def _download_case_files(base_url, second_level_urls):
    all_case_content_links = []
    for url in second_level_urls.keys():
        page = requests.get(url)
        time.sleep(0.5)
        soup = BeautifulSoup(page.text, "html.parser")
        content = soup.find_all("div", class_="odd")  # don't forget to add even...
        for item in content:
            text = item.text
            paragraph = item.find("p")
            print(paragraph.a["href"])
            all_case_content_links.append(text)
            print("_______________________")
    return
"""
