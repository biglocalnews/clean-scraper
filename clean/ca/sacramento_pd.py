import copy
import time
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup, ResultSet, Tag

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict

BASE_URL = "https://www.cityofsacramento.gov"
DISCLOSURE_PATH = "/police/police-transparency/release-of-police-officer-personnel-records--pc-832-7-b--"
ASSET_URL = "https://cityofsacramento.hosted-by-files.com"


class Site:
    """
    Scrape file metadata and download files for the Sacramento Police Department for SB16/SB1421/AB748 data.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Sacramento Police Department"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        """
        Initialize a new instance.

        Args:
            data_dir (Path): The directory where downstream processed files/data will be saved
            cache_dir (Path): The directory where files will be cached
        """
        self.base_url = BASE_URL
        self.disclosure_url = f"{self.base_url}{DISCLOSURE_PATH}"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_sacramento_pd

    def scrape_meta(self, throttle: int = 0) -> Path:
        """Gather metadata on downloadable files (videos, etc.).

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata on downloadable files
        """
        self._download_index_pages(self.disclosure_url)
        downloadable_files = self._create_metadata_json()
        return downloadable_files

    def scrape(self, throttle: int = 0, filter: str = "") -> List[Path]:
        metadata = self.cache.read_json(
            self.data_dir.joinpath(f"{self.agency_slug}.json")
        )
        downloaded_assets = []
        for asset in metadata:
            url = asset["asset_url"]
            if filter and filter not in url:
                continue
            index_dir = (
                asset["parent_page"].split(f"{self.agency_slug}/")[-1].rstrip(".html")
            )
            asset_name = asset["name"].replace(" ", "_")
            download_path = Path(self.agency_slug, "assets", index_dir, asset_name)
            time.sleep(throttle)
            downloaded_assets.append(self.cache.download(str(download_path), url))
        return downloaded_assets

    def _download_index_pages(self, url: str) -> Path:
        """Download index pages for SB16/SB1421/AB748.

        Index pages link to child pages containing videos and
        other files related to use-of-force and disciplinary incidents.

        Returns:
            Local path of downloaded file
        """
        file_stem = url.split("/")[-1]
        base_file = f"{self.agency_slug}/{file_stem}.html"
        return self.cache.download(base_file, url, "utf-8")

    def _create_metadata_json(self) -> Path:
        """
        Create a metadata JSON file containing information about the child links extracted from the HTML page.

        Returns:
            Path: The file path of the created metadata JSON file.
        """
        links: List[MetadataDict] = []
        file_stem = self.disclosure_url.split("/")[-1]
        html_location = f"{self.agency_slug}/{file_stem}.html"
        html = self.cache.read(html_location)
        soup = BeautifulSoup(html, "html.parser")
        lists = soup.select("#container-392a98e5b6 .paragraph li")

        for url in self._extract_index_urls(lists):
            links.append(
                {
                    "title": url["title"],
                    "parent_page": html_location,
                    "asset_url": url["href"],
                    "name": url["name"],
                }
            )

        metadata = self._extract_child_links(links)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self._test_repeated_asset_url(metadata)
        self.cache.write_json(outfile, metadata)
        return outfile

    def _extract_child_links(self, links: List[MetadataDict]) -> List[MetadataDict]:
        """
        Given a list of links, check for child pages, extract links, and add to metadata.

        Args:
            links (List[MetadataDict]): A list of links containing metadata information.

        Returns:
            List[MetadataDict]: A modified list of links with additional CSI image links added to the metadata.
        """
        modified_links = copy.deepcopy(links)
        for link in links:
            if link["asset_url"].endswith("/"):
                parsed_url = urlparse(link["asset_url"])
                # Split URL and remove empty strings for trailing slash
                url_split = [u for u in parsed_url.path.split("/") if u != ""]
                if not self._is_asset(link["asset_url"]):
                    file_stem = url_split[-1]
                    soup = self._download_and_parse(link["asset_url"], file_stem)
                    photo_links = self._extract_photos(soup, file_stem, link)
                    modified_links.extend(photo_links)
                else:
                    modified_links.append(
                        {
                            "title": link["title"],
                            "parent_page": link["parent_page"],
                            "asset_url": link["asset_url"],
                            "name": link["name"],
                        }
                    )
        return modified_links

    def _extract_photos(
        self, soup: BeautifulSoup, file_stem: str, link: MetadataDict
    ) -> List[MetadataDict]:
        """
        Extract photo links from a BeautifulSoup object and return a list of MetadataDict.

        Args:
            soup (BeautifulSoup): The BeautifulSoup object representing the HTML page.
            file_stem (str): The file stem of the current page.
            link (MetadataDict): The metadata dictionary of the current page.

        Returns:
            List[MetadataDict]: A list of MetadataDict containing the extracted photo information.
        """
        title_tag = soup.find("h1")
        photo_links = soup.select(".col-filename a")
        photos: List[MetadataDict] = []
        for photo in photo_links:
            if str(photo["href"]).endswith("/"):
                child_url = f'{ASSET_URL}{photo["href"]}'
                child_file_stem = child_url.split("/")[-2]
                child_soup = self._download_and_parse(child_url, child_file_stem)
                more_photos = self._extract_photos(child_soup, child_file_stem, link)
                photos.extend(more_photos)

            else:
                photos.append(
                    {
                        "title": (
                            title_tag.get_text().split("/")[-2]
                            if title_tag
                            else link["title"]
                        ),
                        "parent_page": file_stem,
                        "asset_url": f'{ASSET_URL}{photo["href"]}',
                        "name": photo.get_text(),
                    }
                )

        return photos

    def _download_and_parse(self, url: str, file_stem: str) -> BeautifulSoup:
        """
        Download and parse a URL, returning a BeautifulSoup object.

        Args:
            url (str): The URL to download and parse.
            file_stem (str): The stem of the file name to save the downloaded HTML.

        Returns:
            BeautifulSoup: The parsed HTML as a BeautifulSoup object.
        """
        base_file = f"{self.agency_slug}/{file_stem}.html"
        cache_path = self.cache.download(base_file, url, "utf-8")
        html = self.cache.read(cache_path)
        return BeautifulSoup(html, "html.parser")

    def _clean_text(self, text: str) -> str:
        """
        Clean the given text by replacing non-breaking spaces with regular spaces and removing leading/trailing whitespace.

        Args:
            text (str): The text to be cleaned.

        Returns:
            str: The cleaned text.
        """
        return text.replace("\u00a0", " ").strip()

    def _is_asset(self, url: str) -> bool:
        """
        Check if the given URL points to a PDF or ZIP file.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True if the URL points to a PDF or ZIP file, False otherwise.
        """
        parsed_url = urlparse(url)
        path = parsed_url.path
        return path.endswith(".pdf") or path.endswith(".zip")

    def _extract_index_urls(self, lists: ResultSet[Tag]):
        """
        Extract the index URLs from a list of tags, accounting for relative URLs.

        Args:
            lists (ResultSet[Tag]): A list of tags containing the index URLs.

        Yields:
            dict: A dictionary containing the extracted information for each index URL.
                The dictionary has the following keys:
                - "title": The title of the index URL.
                - "name": The name of the index URL.
                - "href": The URL of the index link.

        """
        for li in lists:
            title_tag = li.select_one("strong")
            title_str = ""
            if title_tag is not None:
                title_str = self._clean_text(
                    f"{title_tag.get_text()} {title_tag.next_sibling}"
                )
            links = li.find_all("a")
            for link in links:
                href_str = link["href"]
                if "http" not in href_str:
                    href_str = f"{self.base_url}{href_str}"
                yield {
                    "title": title_str,
                    "name": self._clean_text(link.text),
                    "href": href_str,
                }

    def _test_repeated_asset_url(self, objects: List[MetadataDict]):
        """
        Check if the given list of objects contains any repeated asset URLs and returns them.

        Args:
            objects (List[MetadataDict]): A list of objects, where each object is a dictionary containing metadata.

        Returns:
            set: A set of asset URLs that are repeated in the given list of objects.
        """
        seen_urls = set()
        repeated_urls = set()
        for obj in objects:
            asset_url = obj.get("asset_url")
            if asset_url in seen_urls:
                repeated_urls.add(asset_url)
            else:
                seen_urls.add(asset_url)
        return repeated_urls
