import time
from pathlib import Path

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
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        # to create a subdir inside the main cache directory to stash files for this agency
        self.cache_suffix = f"{state_postal}_{mod.stem}"  # ca_orange_county_sheriff

    def scrape_meta(self, throttle=0):
        """Gather metadata on downloadable files (videos, etc.)."""
        current_page = 0
        index_pages = self._download_index_pages(throttle, current_page)
        # TODO: Get the child pages and, you know, actually scrape file metadata
        return index_pages

    # Helper functions
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
        base_file = f"{self.cache_suffix}/{file_stem}_index_page{current_page}.html"
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
