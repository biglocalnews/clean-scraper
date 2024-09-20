import logging
from pathlib import Path, PurePath
from time import sleep
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from .. import utils
from ..cache import Cache

logger = logging.getLogger(__name__)

"""
To-dos include:
    -- Set a max number of documents and test against that in the scraper section. Max docs should
        probably be in the fingerprinting section. Scraper should throw a warning -- Hey, you've asked
        for more than 9,950 docs -- not scraping ...

    -- Build out LAPD example as actual thing usable as a template.

    -- Figure out what the heck to do with things like https://lacity.nextrequest.com/requests/21-2648
          Recursion was not part of the plan.
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
        base_directory, start_url, force, throttle=throttle
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
        r = utils.get_url(page_url)
        if not r.ok:
            logger.error(f"Problem downloading {page_url}: {r.status_code}")
            returned_json: Dict = {}  # type: ignore
            file_needs_write = False
        else:
            returned_json = r.json()
            # local_cache.write_json(filename,
            file_needs_write = True
            total_documents = returned_json[profile["tally_field"]]
            for i, _entry in enumerate(returned_json["documents"]):
                returned_json["documents"][i]["bln_page_url"] = page_url
                returned_json["documents"][i]["bln_total_documents"] = total_documents
            page_size = profile["page_size"]
            max_pages = find_max_pages(total_documents, page_size)
            sleep(throttle)
            if total_documents > profile["doc_limit"]:
                message = f"Request found with {total_documents:,} documents, exceeding limits. "
                message += f"This is probably a bad URL that can't be properly scraped: {page_url}. "
                message += "Dropping record."
                logger.warning(message)
                returned_json = {}
                file_needs_write = False
                return (filename, returned_json, file_needs_write)
            if max_pages > 1:
                logger.debug(f"Need to download {max_pages - 1:,} more JSON files.")
                for page_number in range(2, max_pages + 1):
                    page_url = f"{json_url}{page_number}"
                    if page_number >= 200:
                        message = "NextRequest at least on some sites appears to have a hard limit of "
                        message += f"199 pages. Not trying to scrape {page_url}."
                        logger.warning(message)
                    else:
                        r = utils.get_url(page_url)
                        if not r.ok:
                            logger.error(
                                f"Problem downloading {page_url}: {r.status_code}"
                            )
                            returned_json = {}
                            file_needs_write = False
                        else:
                            additional_json = r.json()
                            if "documents" not in additional_json:
                                logger.error(
                                    f"Missing 'documents' section from {page_url}"
                                )
                                returned_json = {}
                                file_needs_write = False
                            else:
                                for i, _entry in enumerate(
                                    additional_json["documents"]
                                ):
                                    additional_json["documents"][i][
                                        "bln_page_url"
                                    ] = page_url
                                    additional_json["documents"][i][
                                        "bln_total_documents"
                                    ] = total_documents
                                returned_json["documents"].extend(
                                    additional_json["documents"]
                                )
                        sleep(throttle)
            documents_found = len(returned_json["documents"])
            if documents_found != total_documents:
                message = f"Expected {total_documents:,} documents "
                message += f"but got {documents_found:,} instead for "
                message += f"{start_url}."
                logger.warning(message)

    return (filename, returned_json, file_needs_write)


def parse_nextrequest(start_url: str, filename: str):
    """
    Given a link to a NextRequest documents folder and a filename to a JSON, return Metadata.

    Args:
        start_url (str): The web page for the folder of NextRequest docs you want
        filename: Filename to parse for JSON
    Returns:
        List(Metadata)
    """
    local_metadata: List = []
    local_cache = Cache(path=None)
    if not local_cache.exists(filename):
        logger.warning(f"No file {filename} found to go with {start_url}.")
        empty_list: List = []
        return empty_list

    local_json = local_cache.read_json(Path(filename))
    profile = fingerprint_nextrequest(start_url)

    if "documents" not in local_json:
        logger.warning(f"No documents dict in {filename} tied to {start_url}.")
        empty_list: List = []  # type: ignore
        return empty_list

    for entry in local_json["documents"]:  # type: ignore
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

        # Use filename and local_cache's root directory to identify a path relative to the scraper's folder
        partial_path = PurePath(filename).relative_to(local_cache.path)
        partial_path = str(partial_path.relative_to(partial_path.parts[0]).as_posix())  # type: ignore
        line["parent_page"] = partial_path  # type: ignore
        line["title"] = entry["title"]  # type: ignore

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
    if parsed_url.path == "/documents":  # LAPDish type
        line = {
            "site_type": "lapdish",  # LAPDish type
            "base_url": f"{parsed_url.scheme}://{parsed_url.netloc}",
            "folder_id": parse_qs(parsed_url.query)["folder_filter"][0],
            "page_size": 50,
            "doc_limit": 9950,  # Max number of accessible docs in a folder
            "tally_field": "total_count",
            # "document_path": "document_path",
            "bln_page_url": "bln_page_url",
            "bln_total_documents": "bln_total_documents",
        }
        line["json_url"] = (
            f"{line['base_url']}/client/documents?sort_field=count&sort_order=desc&page_size=50&folder_filter={line['folder_id']}&page_number="
        )
        line["details"] = {
            "document_path": "document_path",
            "description": "description",
            "count": "count",
            "state": "state",
            "demo": "demo",
            "created_at": "created_at",
            "folder_name": "folder_name",
            "redacted_at": "redacted_at",
            "file_extension": "file_extension",
            "doc_date": "doc_date",
            "id": "id",
            "highlights": "highlights",
            "bln_page_url": "bln_page_url",
            "bln_total_documents": "bln_total_documents",
        }

    elif (  # BARTish type
        len(parsed_url.path.split("/")) == 3
        and parsed_url.path.split("/")[1] == "requests"
    ):
        line = {
            "site_type": "bartish",  # Bartish type
            "base_url": f"{parsed_url.scheme}://{parsed_url.netloc}",
            "folder_id": urlparse(start_url).path.split("/")[2],
            "doc_limit": 9950,  # Max number of accessible docs in a folder
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
            "file_extension": "file_extension",
            "file_size": "ds!file_size",
            "file_type": "ds!file_type",
            "visibility1": "visibility",
            "visibility2": "ds!visibility",
            "upload_date1": "upload_date",
            "upload_date2": "ds!upload_date",
            "pretty_id": "ds!pretty_id",
            "id1": "id",
            "id2": "ds!id",
            "document_id": "ds!document_id",
            "request_id": "request_id",
            "folder_name": "folder_name",
            "subfolder_name": "subfolder_name",
            "exempt_from_retention": "exempt_from_retention",
            "bln_page_url": "bln_page_url",
            "bln_total_documents": "bln_total_documents",
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
