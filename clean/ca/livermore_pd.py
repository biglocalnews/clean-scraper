import logging
from pathlib import Path
from typing import Dict, List

from .. import utils
from ..cache import Cache
from ..platforms.muckrock import process_muckrock

# from ..utils import MetadataDict

logger = logging.getLogger(__name__)


class Site:
    """Scrape file metadata for the Livermore Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Livermore Police Department"

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
        self.site_slug = "ca_livermore_pd"
        self.base_url = "https://www.muckrock.com/foi/livermore-3295/2023-sb1421sb16-request-livermore-police-department-140174"  # Embargoed
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
            "https://www.muckrock.com/foi/livermore-3295/2023-sb1421sb16-request-livermore-police-department-140174": True,
            "https://www.muckrock.com/foi/livermore-3295/sb1421-records-2022-122912": True,
            "https://www.muckrock.com/foi/livermore-3295/sb1421-records-85738/#files": True,
        }

        metadata: List = []

        subpages_dir = self.subpages_dir

        api_key = utils.get_credentials("MUCKROCK_CRP")

        for start_url in to_be_scraped:
            force = to_be_scraped[start_url]
            local_metadata = process_muckrock(
                subpages_dir, start_url, api_key, force, throttle
            )
            metadata.extend(local_metadata)

        json_filename = self.data_dir / (self.site_slug + ".json")
        self.cache.write_json(json_filename, metadata)

        return json_filename
