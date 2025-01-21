import logging
from pathlib import Path
from typing import Dict, List

from .. import utils
from ..cache import Cache
from ..platforms.nextrequest import auth_nextrequest, process_nextrequest

# from ..utils import MetadataDict

logger = logging.getLogger(__name__)


class Site:
    """Scrape file metadata for the Mendocino County Sheriff's Office.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Mendocino County Sheriff"

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
        self.site_slug = "ca_mendocino_county_sheriff"
        self.base_url = "https://mendocinocounty.nextrequest.com"
        # Initial disclosure page (aka where they start complying with law) contains list of "detail"/child pages with links to the SB16/SB1421/AB748 videos and files
        # along with additional index pages
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
        metadata: List = []

        for folder in ["22-18", "23-27", "20-30"]:
            username = utils.get_credentials(f"MENDOSO{folder}_USER")
            password = utils.get_credentials(f"MENDOSO{folder}_PASS")
            start_url = f"https://mendocinocounty.nextrequest.com/requests/{folder}"
            auth: Dict = auth_nextrequest(self.base_url, username, password)
            local_metadata = process_nextrequest(
                self.subpages_dir, start_url, force=True, throttle=throttle, auth=auth
            )
            for i, _entry in enumerate(local_metadata):
                local_metadata[i]["auth"] = auth
            metadata.extend(local_metadata)

        json_filename = self.data_dir / (self.site_slug + ".json")
        self.cache.write_json(json_filename, metadata)

        return json_filename
