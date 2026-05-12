import logging
from pathlib import Path
from typing import Dict, List

from .. import utils
from ..cache import Cache
from ..platforms.muckrock import process_muckrock

# from ..utils import MetadataDict

logger = logging.getLogger(__name__)

"""
DANGER DANGER DANGER!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

There may be multiple GovQA repositories associated with this request, but Stucka can't find 'em.

As of Oct. 20, 2024, this is only grabbing the Muckrock side of things.
"""


class Site:
    """Scrape file metadata for the California Department of Corrections and Rehabilitation.

    Attributes:
        name (str): The official name of the agency
    """

    name = "California Department of Corrections and Rehabilitation"

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
        self.site_slug = "ca_california_department_of_corrections_and_rehabilitation"
        self.base_url = "https://www.muckrock.com/foi/california-52/sb1421-records-2022-122682"  # Embargoed
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
        to_be_scraped: Dict = {
            self.base_url: True,
        }

        metadata: List = []

        subpages_dir = self.subpages_dir

        api_key = utils.get_credentials("MUCKROCK_CRP")

        for start_url in to_be_scraped:
            force = to_be_scraped[start_url]
            local_metadata = process_muckrock(subpages_dir, start_url, api_key, force)
            metadata.extend(local_metadata)

        json_filename = self.data_dir / (self.site_slug + ".json")
        self.cache.write_json(json_filename, metadata)

        return json_filename
