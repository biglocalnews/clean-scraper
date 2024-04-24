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
        self.base_url = "https://www.ocsheriff.gov"
        self.disclosure_url = (
            f"{self.base_url}/about-ocsheriff/peace-officer-records-releases"
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

    def scrape_meta(self, throttle: int = 0) -> Path:
        """Gather metadata on downloadable files (videos, etc.)."""
        self._download_index_pages(self.disclosure_url)
        # TODO: Get the child pages and, you know, actually scrape file metadata
        downloadable_files = self._create_json()
        return downloadable_files

    def scrape(self, throttle: int = 0, filter: str = "") -> List[Path]:
        """Download file assets from agency.

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.
            filter (str): Only download URLs that match the filter. Defaults to None.

        Returns:
            List[Path]: List of local paths to downloaded files
        """
        # Get metadata on downloadable files
        metadata = self.cache.read_json(
            self.data_dir.joinpath(f"{self.agency_slug}.json")
        )
        downloaded_assets = []
        for asset in metadata:
            url = asset["asset_url"]
            # Skip non-matching files if filter applied
            if filter and filter not in url:
                continue
            # Get relative path to parent index_page directory
            index_dir = (
                asset["parent_page"].split(f"{self.agency_slug}/")[-1].rstrip(".html")
            )
            asset_name = asset["name"].replace(" ", "_")
            download_path = Path(self.agency_slug, "assets", index_dir, asset_name)
            # Download the file to agency directory/assets/index_page_dir/case_name/file_name
            # Example: 'ca_san_diego_pd/assets/sb16-sb1421-ab748/11-21-2022_IA_2022-013/November_21,_2022_IA_#2022-013_Audio_Interview_Complainant_Redacted_KM.wav'
            time.sleep(throttle)
            downloaded_assets.append(self.cache.download(str(download_path), url))
        return downloaded_assets

    # Helper functions

    def _create_json(self) -> Path:
        metadata = []
        file_stem = self.disclosure_url.split("/")[-1]
        # (old) html_location = f"{self.agency_slug}/{file_stem}_index_page{current_page}.html"
        html_location = f"{self.agency_slug}/{file_stem}.html"
        html = self.cache.read(html_location)
        soup = BeautifulSoup(html, "html.parser")
        title = soup.find("title").text.strip()
        links = soup.article.find_all("a")
        urls = []
        name = []
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
                "parent_page": html_location,
                "asset_url": value,
                "name": key,
            }
            metadata.append(payload)
        # Store the metadata in a JSON file in the data directory
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        # Return path to metadata file for downstream use
        return outfile

    def _download_index_pages(self, url: str) -> Path:
        """Download index pages.

        Index pages link to child pages containing videos and
        other files related to use-of-force and disciplinary incidents.

        Returns:
            List of path to cached index pages
        """
        file_stem = url.split("/")[-1]
        base_file = f"{self.agency_slug}/{file_stem}.html"
        # Download the page (if it's not already cached)
        cache_path = self.cache.download(base_file, url, "utf-8")
        # Add the path to the list of index pages
        return cache_path


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
