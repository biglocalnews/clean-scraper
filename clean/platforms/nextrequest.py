import logging
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

# from .. import utils
from ..cache import Cache

logger = logging.getLogger(__name__)


def process_nextrequest(base_directory: Path, start_url: str, force: bool = False):
    """Turn a base filepath and NextRequest folder URL into saved data and parsed Metadata.

    This is a wrapper.

    Args:
        base_direcory (Path): The directory to save data in, e.g., cache/site-name/subpages
        start_url (str): The web page for the folder of NextRequest docs you want
        force (bool, default False): Overwrite file, if it exists? Otherwise, use cached version.
    Returns:
        List(Metadata)
    """
    # Download data, if necessary
    filename, returned_json, file_needs_write = fetch_nextrequest(
        base_directory, start_url, force=False
    )

    # Write data, if necessary
    local_cache = Cache(path=None)
    if file_needs_write and returned_json:
        local_cache.write_json(filename, returned_json)

    # Read data (always necessary!)
    local_metadata = parse_nextrequest(start_url, filename)
    return local_metadata


# Type base_directory to Path
def fetch_nextrequest(base_directory: Path, start_url: str, force: bool = False):
    """
    Given a link to a NextRequest documents folder, return a proposed filename and the JSON contents.

    Args:
        base_direcory (Path): The directory to save data in, e.g., cache/site-name/subpages
        start_url (str): The web page for the folder of NextRequest docs you want
        force (bool, default False): Overwrite file, if it exists? Otherwise, use cached version.
    Returns:
        filename (str): Proposed filename; file NOT saved
        returned_json (None | dict): None if no rescrape needed; dict if JSON had to be downloaded
        file_needs_write (bool): If JSON was downloaded, should it be saved?
    Notes:
        This does NOT save the file.
    """
    profile = fingerprint_nextrequest(start_url)
    folder_id = profile["folder_id"]
    json_url = profile["json_url"]
    # Need to build in pagination! And here the plan breaks down. If we're writing unparsed JSON,
    # we will need more than one file if there are more than the 50 cases.
    # So should a pagination process save each file individually, maybe with a _page## kind of prefix
    # check for that? Or should it just, parse all the JSON and combine the documents records into one?
    # Returning lists of files vs. a filename, etc., sounds unfun. So maybe this handler combines?

    local_cache = Cache(path=None)
    filename = base_directory / f"{folder_id}.json"
    if not force and local_cache.exists(filename):
        logger.debug(f"File found in cache: {filename}")
        returned_json = None
        file_needs_write = False
    else:
        # Remember pagination here!
        page_number = 1
        page_url = f"{json_url}{page_number}"
        r = requests.get(page_url)
        if not r.ok:
            logger.error(f"Problem downloading {page_url}: {r.status_code}")
            returned_json = {}
            file_needs_write = False
        else:
            returned_json = r.json()
            # local_cache.write_json(filename,
            file_needs_write = True

        """OK, so from here need to parse the initial JSON; extract out the number of items expected;
        calculate the number of pages needed to be scraped (pages = items // total;
        if items % total > 0, then pages += 1
        Then scrape all -those- pages, parse individual results, append to 'documents' list
        Also need to add in throttle here
        and throttle will require time.sleep"""
    return (filename, returned_json, file_needs_write)


def parse_nextrequest(start_url, filename):
    """
    Given a link to a NextRequest documents folder and a filename to a JSON, return Metadata.

    Args:
        start_url (str): The web page for the folder of NextRequest docs you want
        filename: Filename to parse for JSON
    Returns:
        List(Metadata)
    """
    local_metadata = []
    local_cache = Cache(path=None)
    local_json = local_cache.read_json(filename)
    parsed_url = urlparse(start_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    folder_id = parse_qs(parsed_url.query)["folder_filter"][0]
    for entry in local_json["documents"]:
        line = {}
        line["asset_url"] = base_url + entry["document_path"]
        if "http" not in line["asset_url"]:
            line["asset_url"] = base_url + line["asset_url"]
        line["case_id"] = folder_id
        line["name"] = entry["title"]
        line["parent_page"] = folder_id + ".json"  # HEY! Need path here
        line["title"] = entry["title"]
        line["details"] = {}
        for item in [
            "created_at",
            "description",
            "redacted_at",
            "doc_date",
            "highlights",
        ]:
            if item in entry:
                line["details"][item] = entry[item]
        local_metadata.append(line)
    return local_metadata


def fingerprint_nextrequest(start_url: str):
    """
    Given a link to a NextRequest documents folder, try to ID how the site stores stuff.

    Args:
        start_url (str): The web page for the folder of NextRequest docs you want
    Returns:
        local_schema (dict)
    """
    line = None
    parsed_url = urlparse(start_url)
    if parsed_url.path == "/documents":
        line = {
            "sitetype": "lapdish",
            "base_url": f"{parsed_url.scheme}://{parsed_url.netloc}",
            "folder_id": parse_qs(parsed_url.query)["folder_filter"][0],
            "page_size": 50,
            "tally_field": "total_count",
        }
        line["json_url"] = (
            f"{line['base_url']}/client/documents?sort_field=count&sort_order=desc&page_size=50&folder_filter={line['folder_id']}&page_number="
        )

    elif (
        len(parsed_url.path.split("/")) == 3
        and parsed_url.path.split("/")[1] == "requests"
    ):
        line = {
            "sitetype": "bartish",
            "base_url": f"{parsed_url.scheme}://{parsed_url.netloc}",
            "folder_id": urlparse(start_url).path.split("/")[2],
            "page_size": 25,
            "tally_field": "total_documents_count",
        }
        line["json_url"] = (
            f"{line['base_url']}/client/request_documents?request_id={line['folder_id']}&page_number="
        )
    else:
        logger.error(f"Unable to fingerprint {start_url}")
    return line
