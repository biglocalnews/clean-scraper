import logging
from pathlib import Path
from typing import Dict, List

from .. import utils
from ..cache import Cache
from ..platforms.nextrequest import process_nextrequest

# from ..utils import MetadataDict

logger = logging.getLogger(__name__)


class Site:
    """Scrape file metadata for the San Rafael Police Departmnt -- San Rafael PD.

    Attributes:
        name (str): The official name of the agency
    """

    name = "San Rafael Police Department"

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
        self.site_slug = "ca_san_rafael_pd"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.subpages_dir = cache_dir / (self.site_slug + "/subpages")
        self.cache = Cache(cache_dir)
        for localdir in [self.cache_dir, self.data_dir, self.subpages_dir]:
            utils.create_directory(localdir)

    def scrape_meta(self, throttle: int = 2) -> Path:
        """Gather metadata on downloadable files (videos, etc.).

        Args:
            throttle (int): Number of seconds to wait between requests. Defaults to 0.

        Returns:
            Path: Local path of JSON file containing metadata on downloadable files
        """
        to_be_scraped: Dict = {
            "https://cityofsanrafaelcapd.nextrequest.com/requests/24-634": True,
            "https://cityofsanrafaelcapd.nextrequest.com/requests/23-1537": True,
        }

        # NextRequest sites are indexed at https://cityofsanrafaelcapd.nextrequest.com/requests
        # A different frontend is at https://www.srpd.org/transparency

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

        return json_filename
