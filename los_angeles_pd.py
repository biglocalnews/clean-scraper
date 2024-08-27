# from pathlib import Path

from clean import utils
from clean.cache import Cache
from clean.platforms.nextrequest import process_nextrequest

start_url = "https://lacity.nextrequest.com/documents?folder_filter=F031-22"

data_dir = utils.CLEAN_DATA_DIR
cache_dir = utils.CLEAN_CACHE_DIR
site_slug = "ca_los_angeles_pd"
subpages_dir = cache_dir / (site_slug + "/" + "subpages")

cache = Cache(path=None)

metadata = process_nextrequest(subpages_dir, start_url, force=False)
print(metadata)
