import time
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache
from ..utils import MetadataDict


class Site:
    """Scrape file metadata and download files for the Ventura County Sheriff for SB1421/AB748 data.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Ventura County Sheriff"

    agency_slug = "ca_ventura_county_sheriff"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        # Start page contains list of "detail"/child pages with links to the SB16/SB1421/AB748 videos and files
        # along with additional index pages
        self.base_url = "https://www.venturasheriff.org"
        self.target_urls = [
            f"{self.base_url}/sb1421/officer-involved-shooting-ois/",
            f"{self.base_url}/sb1421/use-of-force-great-bodily-injury-cases-gbi/",
        ]
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)  # ~/.clean-scraper/cache/
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        # to create a subdir inside the main cache directory to stash files for this agency
        self.cache_suffix = f"{state_postal}_{mod.stem}"  # ca_ventura_county_sheriff

    def scrape_meta(self, throttle: int = 0) -> Path:
        page_urls = []
        for url in self.target_urls:
            detail_page_links = self._get_detail_page_links(url)
            page_urls.extend(detail_page_links)
        local_detail_pages = []
        # Not sure what's up with these PDF links, but they're appearing on the page.
        # Might need to tighten up logic in _get_detail_page_links.
        # pdf_links = filter(lambda x: x.endswith('.pdf'), page_urls)
        other_links = filter(lambda x: not x.endswith(".pdf"), page_urls)
        for page in other_links:
            time.sleep(throttle)
            local_detail_pages.append(self._download_page(page))
        # Loop all of the process the detail pages and write out the metadata JSON
        payload = []
        for local_page in local_detail_pages:
            data = self._process_detail_page(local_page)
            payload.extend(data)

        # TODO: Write out the metadata JSON
        # Store the metadata in a JSON file in the data directory
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        # Return path to metadata file for downstream use
        return outfile

    def _process_detail_page(self, local_page) -> List[MetadataDict]:
        """Extract links to files such as videos from a detail page and write to JSON file."""
        metadata = []
        # Process child page HTML files in index page folders,
        # building a list of file metadata (name, url, etc.) along the way
        html = self.cache.read(local_page)
        soup = BeautifulSoup(html, "html.parser")
        # Find the title of the page
        title = soup.find("h1").text.strip()

        # Find all the videos, photos, etc. on the page *and* construct the *relative* path for the
        # files, e.g. "ca_ventura_county_sheriff/2019-ois-201906219/photo1.jpg" -> QUESTION FOR SERDAR:
        # should that be part of this function or should it be done in the _process_pdf/_process_youtube etc
        # functions?

        links = soup.find_all("a")
        #  Filter for PDF and YouTube links
        #  TODO: call separate functions for different link types with an if/elif/else block
        for link in links:
            href = link.get("href", "")
            if href.endswith(".pdf") in href:
                payload = self._process_pdf(link, title, local_page)
            elif "youtu.be" in href or "youtube.com" in href:
                payload = self._process_youtube(link, title, local_page)
            elif ".mp3" in href:
                payload = self._process_audio(link, title, local_page)

            metadata.append(payload)

        return metadata

    # Functions to work with each type of file: pdf, youtube and audio:

    def _process_youtube(self, link) -> MetadataDict:
        """Example:
        {
            "title": title,
            "parent_page": str(html_file),
            "asset_url": href.replace("\n", ""),
            "name": link.text.strip().replace("\n", ""),
        }
        Returns MetadataDict to be pushed to metadata List
        """
        metadata_list = []
        # QUESTION FOR SERDAR: Is this the right approach?
        for link in links:
            href = link.get("href", "")
            if href.endswith("youtu.be") or "youtube.com" in href:
                payload = {
                    "title": title,
                    "parent_page": str(html_file),
                    "asset_url": href.replace("\n", ""),
                    "name": link.text.strip().replace("\n", ""),
                }
                metadata_list.append(payload)
        pass

    def _process_pdf(self, link) -> MetadataDict:
        metadata_list = []
        for link in links:
            href = link.get("href", "")
            if href.endswith(".pdf"):
                payload = {
                    "title": title,
                    "parent_page": str(html_file),
                    "asset_url": href.replace("\n", ""),
                    "name": link.text.strip().replace("\n", ""),
                }
                metadata_list.append(payload)
        pass

    # TODO: The audio files are hard coded, need to figure out how to get the audio links:
    def _process_audio(self, link) -> MetadataDict:
        pass

    # Helper/Private Methods
    def _get_detail_page_links(self, target_url):
        # Download the index page, which saves to local cache
        full_local_path = self._download_page(target_url)
        # Grab the path relative to the cache (~/.clean-scraper/cache)
        # e.g. ca_ventura_county_sheriff/somefilename.html
        cache_path_relative = str(full_local_path).split("cache/")[-1]
        # Read the HTML from the cached version of the index page
        html = self.cache.read(cache_path_relative)
        # Proceed with normal HTML parsing...
        soup = BeautifulSoup(html, "html.parser")
        links = []
        container = soup.select_one("div[data-id='9a80528']")
        if container:
            for link in container.find_all("a"):
                try:
                    url = link.attrs["href"]
                except AttributeError:
                    url = link
                if not url.startswith("https://"):
                    import urllib.parse

                    url = urllib.parse.urljoin(self.base_url, url)
                links.append(url)
        return links

    def _download_page(self, url: str) -> Path:
        """Download index or case detail pages for SB16/SB1421/AB748.

        Index pages link to case detail pages containing videos and
        other files related to use-of-force and disciplinary incidents.

        Returns:
            Local path of downloaded file
        """
        file_stem = url.rstrip("/").split("/")[-1]
        base_file = f"{self.agency_slug}/{file_stem}.html"
        # Download the page (if it's not already cached)
        cache_path = self.cache.download(base_file, url, "utf-8")
        return cache_path
