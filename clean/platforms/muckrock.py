import logging
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

from .. import utils
from ..cache import Cache

logger = logging.getLogger(__name__)

foia_request_url = "https://www.muckrock.com/api_v1/foia/"


def process_muckrock(
    base_directory: Path,
    request_url: str,
    api_key: str = "",
    force: bool = False,
    throttle: int = 2,
):
    """
    Turn a base filepath and Muckrock Conversation ID into saved data and parsed Metadata.

    This is a wrapper.

    Args:
        base_direcory (Path): The directory to save data in, e.g., cache/site-name/
        request_url (str): The url for the webpage of Muckrock you want documents from you want
        force (bool, default False): Overwrite file, if it exists? Otherwise, use cached version.
        throttle (int, default 2): Time to wait between calls (not using here because not required)

    Returns:
        List(Metadata)
    """
    # Download data, if necessary
    filename, returned_json, file_needs_write = fetch_muckrock(
        base_directory, request_url, api_key, force
    )
    # Write data, if necessary
    local_cache = Cache(path=None)
    file_path = Path(filename)
    cache_dir = Path(local_cache.path)
    partial_path = file_path.relative_to(cache_dir)
    if file_needs_write and returned_json:
        local_cache.write_json(filename, returned_json)

    # Read data (always necessary!)
    local_metadata = parse_muckrock(request_url, filename, partial_path)
    return local_metadata


def fetch_muckrock(
    base_directory: Path, request_url: str, api_key: str = "", force: bool = False
):
    """
    Given a link to a NextRequest documents folder, return a proposed filename and the JSON contents.

    Args:
        base_direcory (Path): The directory to save data in, e.g., cache/site-name/subpages
        request_url (str): The request_url for the webpage of Muckrock you want documents from you want
        force (bool, default False): Overwrite file, if it exists? Otherwise, use cached version.

    Returns:
        filename (str): Proposed filename; file NOT saved
        returned_json (None | dict): None if no rescrape needed; dict if JSON had to be downloaded
        file_needs_write (bool): If JSON was downloaded, should it be saved?

    Notes:
        This does NOT save the file.
    """
    local_cache = Cache(path=None)
    if "/foi/" not in request_url:
        logger.error(
            f"Missing /foi/ in URL. This does not appear to be a Muckrock URL {request_url}"
        )
    request_id = urlparse(request_url).path.split("/")[3].split("-")[-1]
    filename = base_directory / f"{request_id}.json"
    if len(api_key) > 0:
        request_headers = {"Authorization": "Token %s" % api_key}
    else:
        request_headers = {}

    if not force and local_cache.exists(filename):
        logger.debug(f"File found in cache: {filename}")
        returned_json = None
        file_needs_write = False
    else:
        request_url = f"{foia_request_url}{request_id}"
        r = utils.post_url(request_url, headers=request_headers)
        if not r.ok:
            logger.error(
                f"Problem downloading for request url: {request_url}: {r.status_code}"
            )
            returned_json: Dict = {}  # type: ignore
            file_needs_write = False
        else:
            returned_json = r.json()
            file_needs_write = True

    return (filename, returned_json, file_needs_write)


def parse_muckrock(request_url: str, filename: str, partial_path: Path):
    """
    Given a request to a muckrock API and a filename to a JSON, return Metadata.

    Args:
        request (str): The web page for the folder of NextRequest docs you want
        filename: Filename to parse for JSON

    Returns:
        List(Metadata)
    """
    local_metadata: List = []
    local_cache = Cache(path=None)
    if not local_cache.exists(filename):
        logger.warning(f"No file {filename} found to go with {request_url}.")
        empty_list: List = []
        return empty_list
    local_json = local_cache.read_json(Path(filename))
    if not isinstance(local_json, dict):
        return []
    communications = local_json.get("communications", [])
    if not isinstance(communications, list):
        communications = []
    for communication in communications:
        files = communication.get("files", [])
        if not isinstance(files, list):
            logger.warning(
                f"Expected 'files' to be a list in communication for {filename}."
            )
            continue
        for file in files:
            payload = {
                "title": file.get("title"),
                "case_id": local_json.get("title"),
                "asset_url": file.get("ffile"),
                "parent_page": str(partial_path).replace("\\", "/"),
                "details": {
                    "page_title": local_json.get("title"),
                    "user_id": local_json.get("user"),
                    "username": local_json.get("username"),
                    "agency_id": local_json.get("agency"),
                    "absolute_url": local_json.get("absolute_url"),
                    "datetime_submitted": local_json.get("datetime_submitted"),
                    "date_due": local_json.get("date_due"),
                    "date_followup": local_json.get("date_followup"),
                    "datetime_done": local_json.get("datetime_done"),
                    "datetime_updated": local_json.get("datetime_updated"),
                    "subject": communication.get("subject"),
                    "datetime": communication.get("datetime"),
                    "communication": communication.get("communication"),
                    "doc_id": file.get("doc_id"),
                    "pages": file.get("pages"),
                    "source": file.get("source"),
                    "description": file.get("description"),
                },
            }
            local_metadata.append(payload)

    return local_metadata
