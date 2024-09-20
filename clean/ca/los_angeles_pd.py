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

Not doing -- as there's no persistence:
    -- Track which subpage files have been read through the indexes, but lets also check to see if any
     subpage files were NOT indexed and read them
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

        # Build a list of URLs that should not be scraped
        self.broken_urls = [
            "https://lacity.nextrequest.com/documents?folder_filter=F009-01",
            "https://lacity.nextrequest.com/documents?folder_filter=F050-20",
            "https://lacity.nextrequest.com/documents?folder_filter=F025-15",
        ]

        # Build a dict of URLs that need to be patched up
        self.url_fixes = {
            "https://www.lapdonline.org/office-of-the-chief-of-police/constitutional-policing/risk-management-division__trashed/sustained-complaints-of-unlawful-arrest-unlawful-search/": "https://www.lapdonline.org/office-of-the-chief-of-police/constitutional-policing/sustained-complaints-of-unlawful-arrest-unlawful-search/",
            "F118-04 November 22, 2004": "https://lacity.nextrequest.com/documents?folder_filter=F118-04",
            " https://lacity.nextrequest.com/documents?folder_filter=CF01-3445": "https://lacity.nextrequest.com/documents?folder_filter=CF01-3445",
        }

    def scrape_meta(self, throttle: int = 2) -> Path:
        """Gather metadata on downloadable files (videos, etc.).

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata on downloadable files
        """
        lookup = self.fetch_indexes(throttle)
        json_filename, metadata = self.fetch_subpages(throttle)

        logger.debug("Adding origin details to metadata")
        for i, entry in enumerate(metadata):
            if entry["case_id"] in lookup:
                metadata[i]["details"]["bln_source"] = lookup[entry["case_id"]]
        self.cache.write_json(json_filename, metadata)

        return json_filename

    def url_to_filename(self, url: str):
        """Turn a URL into a proposed filename."""
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
        """Correct bad URLs.

        Args:
            page_url: The URL of the page that got us the link
            local_url: The proposed URL we're trying to clean up
        Returns:
            Cleaned URL, with full domain and scheme as needed.
            URL is checked against a data in self.init for replacement.
        """
        if local_url in self.url_fixes:
            local_url = self.url_fixes[local_url]
        if urlparse(local_url).netloc == "":
            local_url = urlparse(page_url).netloc + local_url
        if urlparse(local_url).scheme == "":
            local_url = "https" + local_url
        return local_url

    def fetch_indexes(self, throttle: int = 2):
        """Recursively download LAPD index pages to find subpage URLs.

        Args:
            throttle (int): Time to wait between requests
        Returns:
            lookup (dict): Supplemental data to add to metadata details
        Writes:
            detailed_urls.json
            indexes_scraped.json
        """
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
                soup = BeautifulSoup(r.content, features="html.parser")

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
                            if original_href in self.broken_urls:
                                logger.debug(f"Not scraping broken URL {original_href}")
                            else:
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

        lookup: Dict = {}
        for entry in detail_urls:
            lookup[entry.split("=")[-1]] = detail_urls[entry]

        return lookup

    def fetch_subpages(self, throttle):
        """Download all subpage URLs as needed; parse all pages.

        Args:
            throttle: Time to wait between requests
        Notes:
            cache.rescrape_all_case_files decides whether already existent files should be downloaded
        Returns:
            Filename of JSON metadata
            Metadata
        """
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
        return json_filename, metadata
