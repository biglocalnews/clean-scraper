# import time
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache

# from typing import List


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
        self.base_url = "https://www.cityofsacramento.gov"
        self.disclosure_url = f"{self.base_url}/police/police-transparency/release-of-police-officer-personnel-records--pc-832-7-b--"
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
        downloadable_files = self._create_json()
        return downloadable_files

    # def scrape(self, throttle: int = 0, filter: str = "") -> List[Path]:
    #     # TODO: Reimplement & test
    #     metadata = self.cache.read_json(
    #         self.data_dir.joinpath(f"{self.agency_slug}.json")
    #     )
    #     downloaded_assets = []
    #     for asset in metadata:
    #         url = asset["asset_url"]
    #         if filter and filter not in url:
    #             continue
    #         index_dir = (
    #             asset["parent_page"].split(f"{self.agency_slug}/")[-1].rstrip(".html")
    #         )
    #         asset_name = asset["name"].replace(" ", "_")
    #         download_path = Path(self.agency_slug, "assets", index_dir, asset_name)
    #         time.sleep(throttle)
    #         downloaded_assets.append(self.cache.download(str(download_path), url))
    #     return downloaded_assets
    #     pass

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

    def _create_json(self) -> Path:
        metadata = []
        file_stem = self.disclosure_url.split("/")[-1]
        html_location = f"{self.agency_slug}/{file_stem}.html"
        html = self.cache.read(html_location)
        soup = BeautifulSoup(html, "html.parser")
        lists = soup.select("#container-392a98e5b6 .paragraph li")

        for url in _extract_index_urls(lists):
            metadata.append(
                {
                    "title": url["title"],
                    "parent_page": html_location,
                    "asset_url": url["href"],
                    "name": url["name"],
                }
            )

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile


# def _extract_csi_photos(link) -> List[dict]:
#     # TODO
#     """Given a Beautiful Soup link, download the page, extract links, and add to metadata."""
#     pass


def _clean_text(text: str) -> str:
    return text.replace("\u00a0", " ").strip()


def _extract_index_urls(lists):
    for li in lists:
        title = li.select_one("strong")
        if title is None:
            title = ""
        else:
            title = _clean_text(f"{title.get_text()} {title.next_sibling}")
        links = li.find_all("a")
        for link in links:
            if "http" in link["href"]:
                yield {
                    "title": title,
                    "name": _clean_text(link.text),
                    "href": link["href"],
                }
