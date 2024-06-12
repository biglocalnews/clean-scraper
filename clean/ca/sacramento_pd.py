import time
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

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
        # TODO: Refactor out scrape method in favor of Prefect flows
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
        self.cache.write_json(outfile, metadata)
        return outfile

    def _extract_child_links(self, links: List[MetadataDict]) -> List[MetadataDict]:
        """Given a list of links, check for CSI images, extract links, and add to metadata."""
        for link in links:
            if "csi" in link["name"].lower():
                url = link["asset_url"]
                file_stem = url.split("/")[-2]
                soup = self._download_and_parse(url, file_stem)
                if soup:
                    photo_links = self._extract_photos(soup, file_stem, link)
                    links.extend(photo_links)
        return links

    def _download_and_parse(self, url: str, file_stem: str) -> BeautifulSoup:
        """Download and parse a URL, returning a BeautifulSoup object."""
        base_file = f"{self.agency_slug}/{file_stem}.html"
        cache_path = self.cache.download(base_file, url, "utf-8")
        html = self.cache.read(cache_path)
        return BeautifulSoup(html, "html.parser")

    def _extract_photos(
        self, soup: BeautifulSoup, file_stem: str, link: MetadataDict
    ) -> List[MetadataDict]:
        """Extract photo links from a BeautifulSoup object and return a list of MetadataDict."""
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

    def _clean_text(self, text: str) -> str:
        return text.replace("\u00a0", " ").strip()

    def _extract_index_urls(self, lists):
        for li in lists:
            title = li.select_one("strong")
            if title is None:
                title = ""
            else:
                title = self._clean_text(f"{title.get_text()} {title.next_sibling}")
            links = li.find_all("a")
            for link in links:
                if "http" in link["href"]:
                    yield {
                        "title": title,
                        "name": self._clean_text(link.text),
                        "href": link["href"],
                    }
