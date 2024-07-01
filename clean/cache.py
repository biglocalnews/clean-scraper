import csv
import json
import logging
import os
import typing
from os.path import expanduser, join
from pathlib import Path
from typing import Union

from .utils import MetadataDict, get_url, get_youtube_url

logger = logging.getLogger(__name__)


class Cache:
    """Basic interface to save files to and fetch from cache.

    By default this will be: ~/.clean-scraper/cache

    With this directory, you can use partial paths to save or fetch
    file contents. State-specific files should generally be stored in a
    folder using the state's two-letter postal code.

    Example:
        Saving HTML to the cache::

            html = '<html><h1>Blob of HTML</h1></hmtl>'
            cache = Cache()
            cache.write('fl/2021_page_1.html', html)

        Retrieving pages from the cache::

            cache.files('fl')

    Args:
        path (str): Full path to cache directory. Defaults to CLEAN_ETL_DIR
            or, if env var not specified, $HOME/.clean-scraper/cache
    """

    def __init__(self, path: Union[Path, None]):
        """Initialize a new instance."""
        self.root_dir = self._path_from_env or self._path_default
        self.path = path or str(Path(self.root_dir, "cache"))

    def exists(self, name):
        """Test whether the provided file path exists."""
        return Path(self.path, name).exists()

    def read(self, name):
        """Read text file from cache.

        Args:
            name (str): Partial name, relative to cache dir (eg. 'ca_san_diego_pd/2024_page_1.html')

        Returns:
            File content as string or error if file doesn't
        """
        path = Path(self.path, name)
        logger.debug(f"Reading from cache {path}")
        with open(path, newline="") as infile:
            return infile.read()

    def read_csv(self, name):
        """Read csv file from cache.

        Args:
            name (str): Partial name, relative to cache dir (eg. 'ca_san_diego_pd/2024_page_1.html')

        Returns:
            list of rows
        """
        path = Path(self.path, name)
        logger.debug(f"Reading CSV from cache {path}")
        with open(path) as fh:
            return list(csv.reader(fh))

    def read_json(self, name: Path) -> list[dict]:
        """Read JSON file from cache.

        Args:
            name (str): Partial name, relative to cache dir (eg. 'exports/ca_san_diego_pd.json')

        Returns:
            list of dicts
        """
        with open(name) as fh:
            return json.load(fh)

    def download(
        self,
        name: str,
        url: str,
        encoding: typing.Optional[str] = None,
        force: bool = False,
        **kwargs,
    ) -> Path:
        """
        Download the provided URL and save it in the cache *if* it doesn't already exist in cache.

        Args:
            name (str): The path where the file will be saved. Can be a simple string like "ca_san_diego_pd/video.mp4"
            url (str): The URL to download
            encoding (str): The encoding of the response. Optional.
            force (bool): If True, will download the file if it already exists in the cache.
            **kwargs: Additional arguments to pass to requests.get()

        Returns: The local file system path where the file is cached
        """
        # Open the local Path
        local_path = Path(self.path, name)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        url_queue = [url]
        # Request the URL
        if not force and self.exists(name):
            logger.debug(f"File found in cache: {local_path}")
            return local_path

        if "youtube" in url:
            logger.debug("Detected Youtube URL")
            url_queue = get_youtube_url(url)

        for url in url_queue:
            with get_url(url, stream=True, **kwargs) as r:
                # If there's no encoding, set it
                if encoding:
                    r.encoding = encoding
                elif r.encoding is None:
                    r.encoding = "utf-8"
                logger.debug(f"Downloading {url} to {local_path}")
                # Write out the file in little chunks
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        # Return the path
        return local_path

    def write(self, name, content):
        """Save file contents to cache.

        Typically, this should be a state and agency-specific directory
        inside the cache folder.

        For example: ::

            $HOME/.clean-scraper/cache/ca_san_diego_pd/2024_page_1.html

        Provide file contents and the partial name (relative to cache directory)
        where file should written. The partial file path can include additional
        directories (e.g. 'ca_san_diego_pd/2024_page_1.html'), which will be created if they
        don't exist.

        Example: ::

            cache.write("ca_san_diego_pd/2024_page_1.html", html)

        Args:
            name (str): Partial name, relative to cache dir, where content should be saved.
            content (str): Any string content to save to file.
        """
        out = Path(self.path, name)
        out.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Writing to cache {out}")
        with open(out, "w", newline="") as fh:
            fh.write(content)
        return str(out)

    def write_json(
        self, name: Union[Path, str], files_meta: list[MetadataDict]
    ) -> Path:
        """Save JSON data to cache.

        Typically, this should be an agency-specific directory inside the cache folder.

        For example: ::

            $HOME/.clean-scraper/cache/exports/ca_san_diego_pd.json

        Provide file contents as a List of dictionaries and the relative path to a location inside
        the cache directory or a full Path where the file should be written.

        The relative file path can include additional directories
        (e.g. 'ca_san_diego_pd/2024_page_1.html'), which will be created if they don't exist.

        Example: ::

            cache.write_json('~/.clean-scraper/exports/ca_san_diego_pd.json', metadata)
            OR
            cache.write_json('exports/ca_san_diego_pd/ca_san_diego_pd.json', metadata)

        Args:
            name (Path|str): Full path or partial path, relative to cache dir, where content should be saved.
            content (list[dict]): List of dicts containing file metadata for downloadable assets

        Returns:
            Path: Full path to the saved file
        """
        if isinstance(name, Path):
            out = name
        else:
            out = Path(name)
        if not out.is_absolute():
            full_path = self.path.joinpath(out)  # type: ignore
        else:
            full_path = out
        out.parent.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Writing to cache {full_path}")
        with open(full_path, "w", newline="") as fh:
            json.dump(files_meta, fh, indent=4)
        return full_path

    def files(self, subdir=".", glob_pattern="*"):
        """
        Retrieve all files and folders in a subdir relative to cache dir.

        Examples:
            Given a cache dir such as $HOME/.clean-scraper/cache,
            you can: ::

                # Get all files and dirs in cache dir
                Cache().files()

                # Get files in specific subdir
                Cache().files('ca/')

                # Get all files of a specific type in a subdir
                Cache().files(subdir='ca/', glob_pattern='*.html')

        Args:
            subdir (str): Subdir inside cache to glob
            glob_pattern (str): Glob pattern. Defaults to all files in specified subdir ('*')
        """
        _dir = Path(self.path).joinpath(subdir)
        return [str(p) for p in _dir.glob(glob_pattern)]

    @property
    def _path_from_env(self):
        """Get the path where files will be saved."""
        return os.environ.get("CLEAN_ETL_DIR")

    @property
    def _path_default(self):
        """Get the default filesystem location of the cache."""
        return join(expanduser("~"), ".clean-scraper")
