import time
from pathlib import Path
from typing import List
import re
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup, Tag

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict


class Site:
    """Scrape file metadata for the San Francisco Police Commission."""

    name = "San Francisco Police Commission"

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
    ):
        """Initialize a new instance."""
        self.base_url = "https://www.sf.gov"
        self.disclosure_url = f"{self.base_url}/resource/2022/records-released-pursuant-ca-penal-code-ss-8327"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # e.g., ca_san_francisco_pc

    def scrape_meta(self, throttle: int = 0) -> Path:
        """
        Gather metadata on downloadable files by following a two-step process:
        1. Extract links from main pages.
        2. Extract metadata from detail pages.

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata.
        """
        # Step 1: Extract links from main pages
        main_links = self.get_main_page_links()

        # Step 2: Extract metadata from detail pages
        metadata = self.get_detail_page_links(main_links, throttle)

        # Write metadata to a JSON file
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)

        return outfile

    def get_main_page_links(self) -> List[str]:
        """
        Retrieves links from the main page of the site.

        Returns:
            List[str]: A list of URLs for detailed pages.
        """
        main_links = []

        cache_path = self._download_index_page(self.disclosure_url)
        html = self.cache.read(cache_path)
        soup = BeautifulSoup(html, "html.parser")

        for link in soup.find_all("a", href=True):
            if "RequestArchiveDetails" in link["href"]:
                main_links.append(
                    f"{self.base_url}/{link['href']}"
                    if not link["href"].startswith("http")
                    else link["href"]
                )

        return main_links

    def get_detail_page_links(
        self, main_links: List[str], throttle: int = 0
    ) -> List[MetadataDict]:
        """
        Extracts detailed metadata from links on the main pages.

        Args:
            main_links (List[str]): A list of main page URLs.
            throttle (int): Number of seconds to wait between requests.

        Returns:
            List[MetadataDict]: A list of metadata dictionaries for downloadable resources.
        """
        metadata = []

        # Define a regex pattern to match input ids with the format 'rptAttachments_ctlXX_hdnAzureURL'
        id_pattern = re.compile(r"^rptAttachments_ctl\d+_hdnAzureURL$")

        for link in main_links:
            cache_path = self._download_index_page(link)
            html = self.cache.read(cache_path)
            soup = BeautifulSoup(html, "html.parser")

            # Extract the case_id from the reference number paragraph (<p>) tag
            case_id_tag = soup.find(
                "p", style="font-weight: 400; max-width: 75%; font-size: 0.875rem"
            )
            case_id = case_id_tag.text.strip() if case_id_tag else None

            # Ensure case_id is always a string
            case_id = str(case_id) if case_id else ""

            # Find all input tags where the id matches the pattern
            input_tags = soup.find_all("input", id=id_pattern)

            # Ensure we process each input tag
            for input_tag in input_tags:
                value = input_tag.get("value")
                if isinstance(value, str):
                    full_url = value.strip()
                    if full_url:
                        # Check if the URL starts with the base domain
                        if full_url.startswith(
                            "https://1sanfranciscopd.blob.core.usgovcloudapi.net/"
                        ):
                            asset_url = full_url
                        else:
                            asset_url = (
                                "https://1sanfranciscopd.blob.core.usgovcloudapi.net/"
                                + full_url.lstrip("/")
                            )

                        # Parse the URL and extract the filename from the query string
                        parsed_url = urlparse(asset_url)
                        query_params = parse_qs(parsed_url.query)

                        # Get the filename from the 'rscd' parameter
                        filename = query_params.get("rscd", [None])[0]

                        if filename:
                            # Extract the filename after the 'filename=' part
                            filename = filename.split("filename=")[-1]

                            # Generate a title by removing underscores and .pdf extension
                            title = filename.replace("_", " ").replace(".pdf", "")
                        else:
                            # Default case if filename is not found
                            filename = asset_url.split("?")[0].rsplit("/", 1)[-1]
                            title = filename.replace("_", " ").replace(".pdf", "")

                        # Set the filename as 'name'
                        name = (
                            filename
                            if filename
                            else asset_url.split("?")[0].rsplit("/", 1)[-1]
                        )

                        payload: MetadataDict = {
                            "asset_url": asset_url,
                            "case_id": case_id,  # Reference No as it appears on the website
                            "name": name,
                            "title": title,  # Use the formatted title here
                            "parent_page": link,
                        }
                        metadata.append(payload)

            time.sleep(throttle)

        return metadata

    def _download_index_page(self, page_url: str) -> Path:
        """
            Download the index page for use for officer involved shootings;
            use of force with great bodily injury/death;
            & sustained complaints of sexual assault, dishonesty, excessive force, biased conduct, unlawful search or arrest,
            and failing to intervene against another officer using excessive force.

            Index pages link to child pages containing pdfs.

        Returns:
            Local path of downloaded file

        """
        split_url = page_url.split("/")
        # Creates a unique filename using parts of the URL,
        # combining the directory and filename, with _index appended.
        file_stem = f"{split_url[-4]}_{split_url[-1]}_index"
        # Downloads the content from the page_url and stores it locally with the generated file_stem.
        cache_path = self.cache.download(file_stem, page_url, "utf-8")
        return cache_path
