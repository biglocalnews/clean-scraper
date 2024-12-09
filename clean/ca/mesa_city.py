import time
import re
from datetime import datetime
from pathlib import Path
from typing import List
from bs4 import BeautifulSoup
from typing import TypedDict
from .. import utils
from ..cache import Cache
from ..utils import MetadataDict


class Site:
    """Scrape file metadata for La Mesa City.

    Attributes:
        name (str): The official name of the agency
    """

    name = "La Mesa City"

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
        self.base_url = "https://www.cityoflamesa.us"
        self.disclosure_url = f"{self.base_url}/1650/SB1421-Public-Records"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_la_mesa_city

    def fetch_media_links(self, media_url: str) -> List[dict]:
        """Fetch links from a Media page and include their names.

        Args:
            media_url (str): URL of the Media page.

        Returns:
            List[dict]: List of dictionaries containing media links and names.
        """
        cache_path = self._download_index_page(media_url)
        html = self.cache.read(cache_path)
        soup = BeautifulSoup(html, "html.parser")

        # Compile regex for keywords
        media_keywords = re.compile(
            r"photo|images|vid|radio|youtube|youtu.be", re.IGNORECASE
        )

        # Extract links with matching keywords
        media_data = []
        for link in soup.find_all("a", href=True):
            href = link.get("href")
            text = link.get_text(strip=True)  # Extract text inside the <a> tag

            if href and media_keywords.search(href):
                # Normalize the link
                media_link = (
                    href if href.startswith("http") else self.base_url + href.strip()
                )

                # Skip YouTube user links
                if "www.youtube.com/user" in href.lower():
                    continue

                # Add missing extensions based on media type when needed
                if "photo" in href.lower() or "images" in href.lower():
                    if not media_link.lower().endswith((".jpg", ".jpeg", ".png")):
                        media_link += ".pdf"  # Default to .pdf for photos/images, I have checked and .pdf is the right extension for this.
                elif "radio" in href.lower():
                    if not media_link.lower().endswith((".mp3", ".wav")):
                        media_link += ".mp3"  # Default to .mp3 for radio files

                # Append media data with name and URL
                media_data.append({"url": media_link, "name": text})

        return media_data

    def scrape_meta(self, throttle: int = 0) -> Path:
        """Gather metadata on downloadable files (videos, etc.).

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata on downloadable files
        """
        report_keywords = {
            "keywords": ["CR", "IA", "Media"],  # Keywords to filter relevant links
            "url": self.disclosure_url,
        }
        metadata_dict = {}  # Use a dictionary to track unique asset URLs

        cache_path = self._download_index_page(self.disclosure_url)
        html = self.cache.read(cache_path)
        soup = BeautifulSoup(html, "html.parser")

        links = soup.find_all("a", href=True)

        for link in links:
            url = link.get("href")
            text = link.get_text(strip=True)

            if (
                "DocumentCenter/View" in url
                or "youtu.be" in url
                or ("youtube" in url and "user" not in url)
                or (
                    "Media" in url
                    and any(keyword in text for keyword in report_keywords["keywords"])
                )
            ):
                asset_url = (
                    url if url.startswith("http") else self.base_url + url.strip()
                )

                if "Media" in url:
                    media_links = self.fetch_media_links(asset_url)
                    for media_item in media_links:
                        payload = {
                            "asset_url": media_item["url"],
                            "case_id": text + media_item["url"].split("/")[-1],
                            "name": media_item["url"].split("/")[-1],
                            "title": media_item["name"],
                            "parent_page": asset_url,
                            "details": {
                                "notes": (
                                    "civic videoplayer"
                                    if "VID" in media_item["url"]
                                    else ""
                                )
                            },
                        }
                        if (
                            media_item["url"] not in metadata_dict
                            or not metadata_dict[media_item["url"]]["case_id"]
                        ):
                            metadata_dict[media_item["url"]] = payload
                else:
                    if (
                        "youtube" not in url
                        and "DocumentCenter" in url
                        and not asset_url.endswith(".pdf")
                    ):
                        asset_url += ".pdf"

                    payload = {
                        "asset_url": asset_url,
                        "case_id": text,
                        "name": asset_url.split("/")[-1],
                        "title": text,
                        "parent_page": str(report_keywords["url"]),
                        "details": {
                            "notes": ("civic videoplayer" if "VID" in asset_url else "")
                        },
                    }
                    if (
                        asset_url not in metadata_dict
                        or not metadata_dict[asset_url]["case_id"]
                    ):
                        metadata_dict[asset_url] = payload

            time.sleep(throttle)

        metadata = list(metadata_dict.values())  # Convert the dictionary back to a list
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)

        return outfile

    def _download_index_page(self, base_url: str):
        url = f"{base_url}"
        file_stem = f"{Path(base_url).stem}"
        download_file = f"{self.agency_slug}/{file_stem}.html"
        cache_path = self.cache.download(download_file, url, "utf-8")
        return cache_path
