# from pathlib import Path

import logging

from clean import utils
from clean.cache import Cache
from clean.platforms.nextrequest import process_nextrequest

logger = logging.getLogger(__name__)
logging.basicConfig(encoding="utf-8", level=logging.DEBUG)

start_url = "https://bart.nextrequest.com/requests/21-107"

data_dir = utils.CLEAN_DATA_DIR
cache_dir = utils.CLEAN_CACHE_DIR
site_slug = "ca_bart_pd"
subpages_dir = cache_dir / (site_slug + "/" + "subpages")

cache = Cache(path=None)

metadata = process_nextrequest(subpages_dir, start_url, force=False)
json_filename = data_dir / (site_slug + ".json")
cache.write_json(json_filename, metadata)

# print(metadata)
