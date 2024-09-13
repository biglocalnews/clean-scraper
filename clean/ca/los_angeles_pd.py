import logging
from pathlib import Path
from time import sleep
from typing import Dict, List, Set
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..platforms.nextrequest import process_nextrequest

logger = logging.getLogger(__name__)


"""
To-do:
-- Start saving index pages to cache
-- Document params and returns on functions
-- Implemement throttle
-- Begin calling index scraper from scrape-meta
-- Shift bart-like individual page scraper to a separate function
"""


class Site:
    """Scrape file metadata for the Los Angeles Police Department -- LAPD.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Los Angeles Police Department"

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
        self.site_slug = "ca_los_angeles_pd"
        self.first_url = (
            "https://www.lapdonline.org/senate-bill-1421-senate-bill-16-sb-16/"
        )
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.subpages_dir = cache_dir / (self.site_slug + "/subpages")
        self.indexes_dir = cache_dir / self.site_slug
        self.cache = Cache(cache_dir)
        self.rescrape_all_case_files = False  # Do we need to rescrape all the subpages?

        for localdir in [self.cache_dir, self.data_dir, self.subpages_dir]:
            utils.create_directory(localdir)

        self.detail_urls = self.indexes_dir / "url_details.json"
        self.indexes_scraped = self.indexes_dir / "indexes-scraped.json"

        # Build a dict of URLs that do not work
        self.bad_urls = {
            "https://www.lapdonline.org/office-of-the-chief-of-police/constitutional-policing/risk-management-division__trashed/sustained-complaints-of-unlawful-arrest-unlawful-search/": "https://www.lapdonline.org/office-of-the-chief-of-police/constitutional-policing/sustained-complaints-of-unlawful-arrest-unlawful-search/",
            "F118-04 November 22, 2004": "https://lacity.nextrequest.com/documents?folder_filter=F118-04",
        }

    def scrape_meta(self, throttle: int = 2) -> Path:
        """Gather metadata on downloadable files (videos, etc.).

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata on downloadable files
        """
        self.fetch_indexes(throttle)
        json_filename = self.fetch_subpages(throttle)
        return json_filename

    def url_to_filename(self, url):
        # We really really really need a slugify thing
        path = urlparse(url).path
        if path.startswith("/"):
            path = path[1:]
        if path.endswith("/"):
            path = path[:-1]
        path = path.replace("/", "_")
        path += ".html"
        return path

    def clean_url(self, page_url, local_url):
        if local_url in self.bad_urls:
            local_url = self.bad_urls[local_url]
        if urlparse(local_url).netloc == "":
            local_url = urlparse(page_url).netloc + local_url
        if urlparse(local_url).scheme == "":
            local_url = "https" + local_url
        return local_url

    def fetch_indexes(self, throttle: int = 2):
        scraping_complete = False

        detail_urls: Dict = {}
        indexes_scraped: Dict = {}
        indexes_todo: Set = set()
        index_passes = 0

        indexes_todo.add(self.first_url)

        # Need to add sleep between calls

        while not scraping_complete:
            index_passes += 1
            for page_url in list(
                indexes_todo
            ):  # work with a copy so we're not thrashing the original
                filename = self.url_to_filename(page_url)
                filename = self.indexes_dir / filename
                indexes_scraped[page_url] = {
                    "subindexes": [],
                    "details": 0,
                }
                cleaned_page_url = self.clean_url(page_url, page_url)
                logger.debug(f"Trying {cleaned_page_url}")
                r = utils.get_url(cleaned_page_url)

                self.cache.write_binary(filename, r.content)

                sleep(throttle)

                # Need to write the page
                soup = BeautifulSoup(r.content)

                page_title = soup.title
                if page_title:
                    page_title = unquote(page_title.text.strip())  # type: ignore

                content_divs = soup.findAll("div", {"class": "grid-content"})
                content_divs.extend(soup.findAll("div", {"class": "link-box"}))
                for content_div in content_divs:
                    links = content_div.findAll("a")
                    for link in links:
                        original_href = link["href"]
                        href = self.clean_url(page_url, original_href)
                        if "nextrequest.com" in href:
                            if href not in detail_urls:
                                detail_urls[href] = []
                            detail_urls[href].append(
                                {"page_title": page_title, "page_url": page_url}
                            )
                            indexes_scraped[page_url]["details"] += 1
                        else:
                            if original_href not in indexes_scraped:
                                indexes_todo.add(original_href)
                            indexes_scraped[page_url]["subindexes"].append(
                                original_href
                            )

            for url in indexes_scraped:
                if url in indexes_todo:
                    indexes_todo.remove(url)
            if len(indexes_todo) == 0:
                logger.debug(
                    f"Index scraping complete, after {len(indexes_scraped):,} indexes reviewed."
                )
                logger.debug(f"{len(detail_urls):,} case URLs found.")
                scraping_complete = True
            else:
                logger.debug(
                    f"Index scraping pass {index_passes:,}: {len(indexes_scraped):,} indexes scraped, {len(detail_urls):,} case URLs found"
                )

        self.cache.write_json(self.detail_urls, detail_urls)

        self.cache.write_json(self.indexes_scraped, indexes_scraped)

        return

    def fetch_subpages(self, throttle):
        # Determine whether everything needs to be rescraped
        force = self.rescrape_all_case_files

        detail_urls = self.cache.read_json(self.detail_urls)

        # Let's not do anything but reads to detail_urls
        to_be_scraped: Dict = {}
        for detail_url in detail_urls.keys():
            to_be_scraped[detail_url] = force

        metadata: List = []

        subpages_dir = self.subpages_dir

        for start_url in to_be_scraped:
            force = to_be_scraped[start_url]
            local_metadata = process_nextrequest(
                subpages_dir, start_url, force, throttle
            )
            metadata.extend(local_metadata)

        json_filename = self.data_dir / (self.site_slug + ".json")
        self.cache.write_json(json_filename, metadata)
        return json_filename
