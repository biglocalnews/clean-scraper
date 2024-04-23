import time
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the San Diego Police Department for SB16/SB1421/AB748 data.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Sonoma County Sheriff's Office"
    agency_slug = "ca_sonoma_county_sheriff"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        """Initialize a new instance.

        Args:
            data_dir (Path): The directory where downstream processed files/data will be saved
            cache_dir (Path): The directory where files will be cached
        """
        # Start page contains list of "detail"/child pages with links to the SB16/SB1421/AB748 videos and files
        # along with additional index pages
        self.base_url = "https://www.sonomasheriff.org/sb1421"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        # to create a subdir inside the main cache directory to stash files for this agency
        self.cache_suffix = f"{state_postal}_{mod.stem}"  # ca_sonoma_county_sheriff

    def scrape_meta(self, throttle=0):
        
        # construct a local filename relative to the cache directory - agency slug + page url (ca/sonoma__/release_page.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1]}.html"
        filename = f'{self.agency_slug}/{base_name}'
        cache_path = self.cache.download(filename, self.base_url), "utf-8"
        metadata=[]
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        linkz = soup.find_all('li')
        lenny = len(linkz)
        print(lenny)
        
        

        



#         """Gather metadata on downloadable files (videos, etc.)."""
#     def _download_index_pages(self, throttle, page_count, current_page, index_pages=[]):
#         """Download index pages for SB16/SB1421/AB748.

#         Index pages link to child pages containing videos and
#         other files related to use-of-force and disciplinary incidents.

#         Returns:
#             List of path to cached index pages
#         """
#         # # Pause between requests
#         # time.sleep(throttle)
#         # file_stem = self.base_url.split("/")[-1]
#         # base_file = f"{self.cache_suffix}/{file_stem}_index_page{current_page}.html"
#         # # Construct URL: pages, including start page, have a page GET parameter
#         # target_url = f"{self.base_url}?page={current_page}"
#         # # Download the page (if it's not already cached)
#         # cache_path = self.cache.download(base_file, target_url, "utf-8")
#         # # Add the path to the list of index pages
#         # index_pages.append(cache_path)
#         # # If there's no page_count, we're on first page, so...
#         # if not page_count:
#         #     # Extract page count from the initial page
#         #     html = self.cache.read(base_file)
#         #     soup = BeautifulSoup(html, "html.parser")
#         #     page_count = int(
#         #         soup.find_all("li", class_="pager__item")[-1]  # last <li> in the pager
#         #         .a.attrs["href"]  # the <a> tag inside the <li>  # will be ?page=X
#         #         .split("=")[-1]  # get the X
#         #     )
#         # if current_page != page_count:
#         #     # Recursively call this function to get the next page
#         #     next_page = current_page + 1
#         #     self._download_index_pages(throttle, page_count, next_page, index_pages)
#         # return index_pages
    




# """
# # LEGACY CODE BELOW #
# def _scrape_list_page(cache, top_level_urls, base_url, throttle):
#     second_level_urls = {}
#     for top_url in top_level_urls:
#         page = requests.get(top_url)
#         time.sleep(throttle)
#         soup = BeautifulSoup(page.text, "html.parser")
#         six_columns = soup.find_all("div", class_="six columns")
#         for elem in six_columns:
#             paragraph_with_link = elem.find("p")
#             if paragraph_with_link is None:
#                 continue
#             else:
#                 text = paragraph_with_link.text
#                 elem_a = paragraph_with_link.find("a")
#                 if elem_a is None:
#                     continue
#                 else:
#                     full_link = base_url + elem_a["href"]
#                     second_level_urls[full_link] = text
#     _download_case_files(base_url, second_level_urls)
#     return second_level_urls


# def _download_case_files(base_url, second_level_urls):
#     all_case_content_links = []
#     for url in second_level_urls.keys():
#         page = requests.get(url)
#         time.sleep(0.5)
#         soup = BeautifulSoup(page.text, "html.parser")
#         content = soup.find_all("div", class_="odd")  # don't forget to add even...
#         for item in content:
#             text = item.text
#             paragraph = item.find("p")
#             print(paragraph.a["href"])
#             all_case_content_links.append(text)
#             print("_______________________")
#     return
# """
