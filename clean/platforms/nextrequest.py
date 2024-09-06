import logging
from pathlib import Path
from time import sleep
from urllib.parse import parse_qs, urlparse

import requests

# from .. import utils
from ..cache import Cache

logger = logging.getLogger(__name__)

"""
To-dos include:
    -- Figure out what the heck to do with things like https://lacity.nextrequest.com/requests/21-2648
          Recursion was not part of the plan.
    -- Parser should check against the document IDs as another test.
    -- requests should be replaced, if possible, with existing library calls
    -- Identify logging opportunities
    -- Bring in pages' item counts
    -- Verify pages' item counts
"""


def process_nextrequest(
    base_directory: Path, start_url: str, force: bool = False, throttle: int = 2
):
    """Turn a base filepath and NextRequest folder URL into saved data and parsed Metadata.

    This is a wrapper.

    Args:
        base_direcory (Path): The directory to save data in, e.g., cache/site-name/subpages
        start_url (str): The web page for the folder of NextRequest docs you want
        force (bool, default False): Overwrite file, if it exists? Otherwise, use cached version.
        throttle (int, default 2): Time to wait between calls
    Returns:
        List(Metadata)
    """
    # Download data, if necessary
    filename, returned_json, file_needs_write = fetch_nextrequest(
        base_directory, start_url, force=False, throttle=throttle
    )

    # Write data, if necessary
    local_cache = Cache(path=None)
    if file_needs_write and returned_json:
        local_cache.write_json(filename, returned_json)

    # Read data (always necessary!)
    local_metadata = parse_nextrequest(start_url, filename)
    return local_metadata


# Type base_directory to Path
def fetch_nextrequest(
    base_directory: Path, start_url: str, force: bool = False, throttle: int = 2
):
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

    # So we're not writing out the original JSON as the original JSON.
    # We're writing out the parsed (requests.json()) output of at least the first page,
    # and then folding in any additional pages' documents into that JSON.

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
            total_documents = returned_json[profile["tally_field"]]
            page_size = profile["page_size"]
            max_pages = find_max_pages(total_documents, page_size)
            sleep(throttle)
            if max_pages > 1:
                logger.debug(f"Need to download {max_pages - 1:,} more JSON files.")
                for page_number in range(2, max_pages):
                    page_url = f"{json_url}{page_number}"
                    if not r.ok:
                        logger.error(f"Problem downloading {page_url}: {r.status_code}")
                        returned_json = {}
                        file_needs_write = False
                    else:
                        additional_json = r.json()
                        if "documents" not in additional_json:
                            logger.error(f"Missing 'documents' section from {page_url}")
                            returned_json = {}
                            file_needs_write = False
                        else:
                            returned_json["documents"].extend(
                                additional_json["documents"]
                            )
                    sleep(throttle)

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
    profile = fingerprint_nextrequest(start_url)

    for entry in local_json["documents"]:
        line = {}
        folder_id = profile["folder_id"]

        # asset_url depends on the JSON structure
        if profile["site_type"] == "lapdish":
            docpath = entry["document_path"]
            parsed_docpath = urlparse(docpath)
            if parsed_docpath.netloc == "":
                docpath = profile["base_url"] + docpath
            docsplit = parsed_docpath.path.split("/")
            if (
                len(docsplit) == 3
                and docsplit[1] == "documents"
                # and docsplit[2] == entry["id"]
            ):
                docpath += "/download?token="
            if urlparse(docpath).scheme == "":
                docpath = "https:" + docpath
            line["asset_url"] = docpath
            line["case_id"] = folder_id
        elif profile["site_type"] == "bartish":
            docpath = entry["document_scan"]["document_path"]
            parsed_docpath = urlparse(docpath)
            if parsed_docpath.netloc == "":
                docpath = profile["base_url"] + docpath
            docsplit = parsed_docpath.path.split("/")
            if (
                len(docsplit) == 3
                and docsplit[1] == "documents"
                # and docsplit[2] == entry["id"]
            ):
                docpath += "/download?token="
            if urlparse(docpath).scheme == "":
                docpath = "https:" + docpath
            line["asset_url"] = docpath

            # au = entry["asset_url"]
            # if urlparse(au).netloc == "":
            #     au = profile["base_url"] + au
            # line["asset_url"] = au
            for item in ["subfolder_name", "folder_name"]:
                if item in entry and len(entry[item]) > 0:
                    folder_id = folder_id + "__" + entry[item]
            line["case_id"] = folder_id
        else:
            logger.error(f"Do not understand sitetype {line['sitetype']}.")

        line["case_id"] = folder_id
        line["name"] = entry["title"]
        line["parent_page"] = folder_id + ".json"  # HEY! Need path here
        # Smarter to derive from filename, right?
        line["title"] = entry["title"]

        if "details" not in line:
            line["details"] = {}

        for target in profile["details"]:
            source = profile["details"][target]
            if "ds!" in source:
                source = source.replace("ds!", "")
                if source not in entry["document_scan"]:
                    logger.debug(
                        f"Missing ['document_scan']['{source}'] from entry {entry}"
                    )
                else:
                    line["details"][target] = entry["document_scan"][source]
            else:  # Straight shot, no subkey
                if source not in entry:
                    logger.warning(f"Missing {source} from entry {entry}")
                else:
                    line["details"][target] = entry[source]
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
    """To-do:
        Parser needs to map out all of the metadata locations we want to preserve.
        Where is the asset URL?
        What details do we want to preserve?
        How are the references to do those details stored, like how do we handle the subkey?
        Who is we, and why is we typing this at 10 p.m.?
    """
    line = None
    parsed_url = urlparse(start_url)
    if parsed_url.path == "/documents":
        line = {
            "site_type": "lapdish",
            "base_url": f"{parsed_url.scheme}://{parsed_url.netloc}",
            "folder_id": parse_qs(parsed_url.query)["folder_filter"][0],
            "page_size": 50,
            "tally_field": "total_count",
            #            "document_path": "document_path",
        }
        line["json_url"] = (
            f"{line['base_url']}/client/documents?sort_field=count&sort_order=desc&page_size=50&folder_filter={line['folder_id']}&page_number="
        )
        line["details"] = {
            "document_path": "document_path",
            "count": "count",
            "state": "state",
            "demo": "demo",
            "created_at": "created_at",
            "folder_name": "folder_name",
            "redacted_at": "redacted_at",
            "file_extension": "file_extension",
            "highlights": "highlights",
        }

    elif (
        len(parsed_url.path.split("/")) == 3
        and parsed_url.path.split("/")[1] == "requests"
    ):
        line = {
            "site_type": "bartish",
            "base_url": f"{parsed_url.scheme}://{parsed_url.netloc}",
            "folder_id": urlparse(start_url).path.split("/")[2],
            "page_size": 25,
            "tally_field": "total_documents_count",
            #            "document_path": "document_scan['document_path']",
        }
        line["json_url"] = (
            f"{line['base_url']}/client/request_documents?request_id={line['folder_id']}&page_number="
        )
        line["details"] = {
            "document_path": "ds!document_path",
            "bogus_asset_url": "asset_url",
            "review_state": "review_state",
            "review_status": "ds!review_status",
            "severity": "ds!severity",
            "findings": "ds!findings",
            "file_size": "ds!file_size",
            "file_type": "ds!file_type",
            "visibility": "visibility",
            "upload_date2": "upload_date",
            "folder_name": "folder_name",
            "subfolder_name": "subfolder_name",
            "exempt_from_retention": "exempt_from_retention",
        }

    else:
        logger.error(f"Unable to fingerprint {start_url}")
    return line


def find_max_pages(item_count: int, page_size: int):
    """Yes, this is basically math.ceiling but I felt bad about another import."""
    max_pages = item_count // page_size
    if item_count % page_size > 0:
        max_pages += 1
    return max_pages
