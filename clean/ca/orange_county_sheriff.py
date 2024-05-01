import time
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    name = "Orange County Sheriffs Department"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
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
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_orange_county_sheriff

    def scrape_meta(self, throttle: int = 0) -> Path:
        self._download_index_pages(self.disclosure_url)
        downloadable_files = self._create_json()
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

    def _create_json(self) -> Path:
        metadata = []
        file_stem = self.disclosure_url.split("/")[-1]
        html_location = f"{self.agency_slug}/{file_stem}.html"
        html = self.cache.read(html_location)
        soup = BeautifulSoup(html, "html.parser")  # type: ignore
        title = soup.find("title").text.strip()  # type: ignore
        links = soup.article.find_all("a")  # type: ignore
        urls = []
        name = []
        for link in links:
            if "http" in link["href"]:
                urls.append(link["href"])
        for url in urls:
            url_to_name = url.split("Mediazip/")[-1]
            url_to_name1 = url_to_name.replace("/", "_")
            url_to_name2 = url_to_name1.replace(
                f"{url_to_name1}", f"Orange_County_Sheriffs_Department_{url_to_name1}"
            )
            url_to_name3 = url_to_name2.replace("%20", "_")
            url_to_name4 = url_to_name3.strip()
            url_to_name5 = url_to_name4.replace(".", "_")
            url_to_name6 = url_to_name5.replace("_zip", ".zip")
            name.append(url_to_name6)
        url_dict = {name[i]: urls[i] for i in range(len(urls))}
        for key, value in url_dict.items():
            payload = {
                "title": title,
                "parent_page": html_location,
                "asset_url": value,
                "name": key,
            }
            metadata.append(payload)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def _download_index_pages(self, url: str) -> Path:
        file_stem = url.split("/")[-1]
        base_file = f"{self.agency_slug}/{file_stem}.html"
        return self.cache.download(base_file, url, "utf-8")
