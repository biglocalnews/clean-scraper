import csv
import importlib
import logging
import os
from pathlib import Path
from time import sleep
from typing import Optional, TypedDict

import requests
import us
from retry import retry

logger = logging.getLogger(__name__)


# The default home directory, if nothing is provided by the user
CLEAN_USER_DIR = Path(os.path.expanduser("~"))
CLEAN_DEFAULT_OUTPUT_DIR = CLEAN_USER_DIR / ".clean-scraper"

# Set the home directory
CLEAN_OUTPUT_DIR = Path(os.environ.get("CLEAN_OUTPUT_DIR", CLEAN_DEFAULT_OUTPUT_DIR))

# Set the subdirectories for other bits
CLEAN_CACHE_DIR = CLEAN_OUTPUT_DIR / "cache"
CLEAN_DATA_DIR = CLEAN_OUTPUT_DIR / "exports"
CLEAN_LOG_DIR = CLEAN_OUTPUT_DIR / "logs"


class MetadataDict(TypedDict):
    asset_url: str
    name: str
    parent_page: str
    title: Optional[str]


def create_directory(path: Path, is_file: bool = False):
    """Create the filesystem directories for the provided Path objects.

    Args:
        path (Path): The file path to create directories for.
        is_file (bool): Whether or not the path leads to a file (default: False)
    """
    # Get the directory path
    if is_file:
        # If it's a file, take the parent
        directory = path.parent
    else:
        # Other, assume it's a directory and we're good
        directory = path

    # If the path already exists, we're good
    if directory.exists():
        return

    # If not, lets make it
    logger.debug(f"Creating directory at {directory}")
    directory.mkdir(parents=True)


def fetch_if_not_cached(filename, url, throttle=0, **kwargs):
    """Download files if they're not already saved.

    Args:
        filename: The full filename for the file
        url: The URL from which the file may be downloaded.
    Notes: Should this even be in utils vs. cache? Should it exist?
    """
    create_directory(Path(filename), is_file=True)
    if not os.path.exists(filename):
        logger.debug(f"Fetching {filename} from {url}")
        response = requests.get(url, **kwargs)
        if not response.ok:
            logger.error(f"Failed to fetch {url} to {filename}")
        else:
            with open(filename, "wb") as outfile:
                outfile.write(response.content)
        sleep(throttle)  # Pause between requests
    return


def save_if_good_url(filename, url, **kwargs):
    """Save a file if given a responsive URL.

    Args:
        filename: The full filename for the file
        url: The URL from which the file may be downloaded.
    Notes: Should this even be in utils vs. cache? Should it exist?
    """
    create_directory(Path(filename), is_file=True)
    response = requests.get(url, **kwargs)
    if not response.ok:
        logger.error(f"URL {url} fetch failed with {response.status_code}")
        logger.error(f"Not saving to {filename}. Is a new year's URL not started?")
        success_flag = False
        content = False
    else:
        with open(filename, "wb") as outfile:
            outfile.write(response.content)
            success_flag = True
            content = response.content
    sleep(2)  # Pause between requests
    return success_flag, content


def write_rows_to_csv(output_path: Path, rows: list, mode="w"):
    """Write the provided list to the provided path as comma-separated values.

    Args:
        rows (list): the list to be saved
        output_path (Path): the Path were the result will be saved
        mode (str): the mode to be used when opening the file (default 'w')
    """
    create_directory(output_path, is_file=True)
    logger.debug(f"Writing {len(rows)} rows to {output_path}")
    with open(output_path, mode, newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def write_dict_rows_to_csv(output_path, headers, rows, mode="w", extrasaction="raise"):
    """Write the provided dictionary to the provided path as comma-separated values.

    Args:
        output_path (Path): the Path were the result will be saved
        headers (list): a list of the headers for the output file
        rows (list): the dict to be saved
        mode (str): the mode to be used when opening the file (default 'w')
        extrasaction (str): what to do if the if a field isn't in the headers (default 'raise')
    """
    create_directory(output_path, is_file=True)
    logger.debug(f"Writing {len(rows)} rows to {output_path}")
    with open(output_path, mode, newline="") as f:
        # Create the writer object
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction=extrasaction)
        # If we are writing a new row ...
        if mode == "w":
            # ... drop in the headers
            writer.writeheader()
        # Loop through the dicts and write them in one by one.
        for row in rows:
            writer.writerow(row)


def get_all_scrapers():
    """Get all the agencies that have scrapers.

    Returns: List of dicts containing agency slug and name
    """
    # Get all folders in dir
    folders = [p for p in Path(__file__).parent.iterdir() if p.is_dir()]
    # Filter out anything not in a state folder
    abbrevs = [state.abbr.lower() for state in us.states.STATES]
    state_folders = [p for p in folders if p.stem in abbrevs]
    scrapers = {}
    for state_folder in state_folders:
        state = state_folder.stem
        for mod_path in state_folder.iterdir():
            if not mod_path.stem.startswith("__"):
                agency_mod = importlib.import_module(f"clean.{state}.{mod_path.stem}")
                scrapers.setdefault(state, []).append(
                    {"slug": f"{state}_{mod_path.stem}", "agency": agency_mod.Site.name}
                )
    return scrapers


@retry(tries=3, delay=15, backoff=2)
def get_url(
    url, user_agent="Big Local News (biglocalnews.org)", session=None, **kwargs
):
    """Request the provided URL and return a response object.

    Args:
        url (str): the url to be requested
        user_agent (str): the user-agent header passed with the request (default: biglocalnews.org)
        session: a session object to use when making the request. optional
    """
    logger.debug(f"Requesting {url}")

    # Set the headers
    if "headers" not in kwargs:
        kwargs["headers"] = {}
    kwargs["headers"]["User-Agent"] = user_agent

    # Go get it
    if session is not None:
        logger.debug(f"Requesting with session {session}")
        response = session.get(url, **kwargs)
    else:
        response = requests.get(url, **kwargs)
    logger.debug(f"Response code: {response.status_code}")

    # Verify that the response is 200
    assert response.ok

    # Return the response
    return response
