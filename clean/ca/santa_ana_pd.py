import logging
from pathlib import Path
from time import sleep
from typing import List, Set

from .. import utils
from ..cache import Cache
from ..platforms.nextrequest import process_nextrequest

logger = logging.getLogger(__name__)


"""
Notes: This tries to scrape a search index for NextRequest ...
Parse out those folders from the search results ...
Fetch those indexes ...
Then build out a complete set of metadata.

Human-friendly search page:
https://cityofsantaanaca.nextrequest.com/requests?department_ids=8508&search_term=SB1421&sort_field=requester_name
"""


class Site:
    """Scrape file metadata for the Santa Ana Police Department -- Santa Ana PD.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Santa Ana Police Department"

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
        self.site_slug = "ca_santa_ana_pd"
        self.first_url = "https://cityofsantaanaca.nextrequest.com/client/requests?department_ids%5B%5D=8508&search_term=SB1421&sort_field=requester_name"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.subpages_dir = cache_dir / (self.site_slug + "/subpages")
        self.indexes_dir = cache_dir / self.site_slug
        self.cache = Cache(cache_dir)
        self.rescrape_all_case_files = False  # Do we need to rescrape all the subpages?

        for localdir in [self.cache_dir, self.data_dir, self.subpages_dir]:
            utils.create_directory(localdir)

    #        self.detail_urls = self.indexes_dir / "url_details.json"
    #        self.indexes_scraped = self.indexes_dir / "indexes-scraped.json"

    def scrape_meta(self, throttle: int = 2) -> Path:
        """Gather metadata on downloadable files (videos, etc.).

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata on downloadable files
        """
        subpages_dir = self.subpages_dir
        master_index_file = str(subpages_dir / "master_index.json")
        self.cache.download(master_index_file, self.first_url, force=True)
        raw_data = self.cache.read_json(master_index_file)  # type: ignore
        sleep(throttle)

        folders_wanted: Set = set()  # Find NextRequest "folders" to scrape
        for entry in raw_data["requests"]:  # type: ignore
            folders_wanted.add(
                "https://cityofsantaanaca.nextrequest.com/requests/" + entry["id"]
            )

        metadata: List = []

        # Start grabbing NextRequst "folders"
        for start_url in folders_wanted:
            force = True  # Always get a fresh copy
            local_metadata = process_nextrequest(
                subpages_dir, start_url, force, throttle
            )
            metadata.extend(local_metadata)
            sleep(throttle)

        json_filename = self.data_dir / (self.site_slug + ".json")
        self.cache.write_json(json_filename, metadata)

        return json_filename
