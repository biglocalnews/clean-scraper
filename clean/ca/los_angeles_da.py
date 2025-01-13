import time
from datetime import datetime
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict


class Site:
    """Scrape file metadata for the Los Angeles District Attorney's Office.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Los Angeles District Attorney's Office"

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
        self.base_url = "https://da.lacounty.gov"
        self.disclosure_url = f"{self.base_url}/reports/ois/"
        self.icd_url = f"{self.base_url}/reports/icd/"  # New attribute for ICD reports
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_los_angeles_da

    def scrape_meta(self, throttle: int = 0) -> Path:
        #     """Gather metadata on downloadable files (videos, etc.).

        #     Args:
        #         throttle (int): Number of seconds to wait between requests. Defaults to 0.

        #     Returns:
        #         Path: Local path of JSON file containing metadata on downloadable files
        #     """

        #     # Create a list of years to scrape
        #     # e.g. [2016, 2017...]
        current_year = datetime.now().year
        years = range(2016, current_year + 1)
        metadata: List[MetadataDict] = []  # Explicitly set as a list of MetadataDict

        # Define report types and URLs
        # Define report types with multiple keywords
        report_types = [
            {"url": self.disclosure_url, "keywords": ["JSID-OIS", "JSID_OIS"]},
            {
                "url": self.icd_url,
                "keywords": ["JSID-ICD", "JSID_ICD"],
            },  # Multiple keywords for ICD
        ]

        # Usage in the outer scope
        for report_type in report_types:
            for year in years:
                cache_path = self._download_index_page(year, str(report_type["url"]))
                html = self.cache.read(cache_path)
                soup = BeautifulSoup(html, "html.parser")

                body = soup.find_all("span", {"style": "text-decoration: underline;"})
                for span in body:
                    links = span.find_all("a")
                    for link in links:
                        url = link.get("href")
                        # Check if the URL contains any of the keywords for this report type
                        if any(keyword in url for keyword in report_type["keywords"]):
                            title = link.get("title", link.get_text(strip=True))
                            asset_url = self.base_url + url.strip()
                            case_id = "".join(link.stripped_strings)
                            payload: MetadataDict = {
                                "asset_url": asset_url,
                                "case_id": case_id,
                                "name": asset_url.split("pdf/")[-1],
                                "title": title,
                                "parent_page": str(report_type["url"]),
                            }
                            metadata.append(payload)
                            time.sleep(throttle)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)

        return outfile

    def _download_index_page(self, year: int, base_url: str):
        url = f"{base_url}{year}"
        file_stem = f"{Path(base_url).stem}_{year}"
        download_file = f"{self.agency_slug}/{file_stem}.html"
        cache_path = self.cache.download(download_file, url, "utf-8")
        return cache_path
