import time
from pathlib import Path

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the fullerton_pd.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Fullerton Police Department"

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
        self.base_url = "https://publicinfo.fresnosheriff.org/docs/Browse.aspx?id=6859&dbid=0&repo=SheriffPublic"
        self.folder_url = "https://publicinfo.fresnosheriff.org/docs/FolderListingService.aspx/GetFolderListing2"
        self.folder_content_url = "https://publicinfo.fresnosheriff.org/docs/FolderListingService.aspx/GetFolderListing2"
        self.folder_request_body = {
            "repoName": "SheriffPublic",
            "folderId": 6859,
            "getNewListing": True,
            "start": 0,
            "end": 36,
            "sortColumn": "",
            "sortAscending": True,
        }
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_fresno_pd

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_fresno_pd/SB_1421.json)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = "SheriffPublic.json"
        filename = f"{self.agency_slug}/{base_name}"
        base_output_json = self.cache_dir.joinpath(filename)
        base_output_json.parent.mkdir(parents=True, exist_ok=True)
        with utils.post_url(self.folder_url, json=self.folder_request_body) as r:
            self.cache.write_json(base_output_json, r.json())

        metadata = []
        base_json = self.cache.read_json(base_output_json)
        results = base_json.get("data", {}).get("results", [])
        local_index_json = []
        for result in results:  # This iteration is for the main index page
            if result:
                self.folder_request_body["folderId"] = result.get("entryId")
                filename = f"{self.agency_slug}/{result.get('name')}.json"
                output_json = self.cache_dir.joinpath(filename)
                with utils.post_url(
                    self.folder_url, json=self.folder_request_body
                ) as r:
                    self.cache.write_json(output_json, r.json())
                    output_dict = {"fileName": filename, "filePath": output_json}
                    local_index_json.append(output_dict)
                time.sleep(throttle)
        for download_json_path in local_index_json:  # This Iteration is for the Years
            download_dict = self.cache.read_json(download_json_path["filePath"])
            results = download_dict.get("data", {}).get("results", [])
            year = download_dict.get("data", {}).get("name", "")
            for result in results:
                if result:
                    self.folder_request_body["folderId"] = result.get("entryId")
                    filename = f"{self.agency_slug}/{year}/{result.get('name')}.json"
                    case_id = result.get("name")
                    output_json = self.cache_dir.joinpath(filename)
                    case_metadata_list = self._get_child_pages(
                        result, download_json_path["fileName"], year, case_id
                    )
                    for payload in case_metadata_list:
                        metadata.append(payload)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def _get_child_pages(self, result, parent_path, year, case_id):
        childMetadata = []
        self.folder_request_body["folderId"] = result.get("entryId")
        filename = f"{str(parent_path).split('.json')[0]}/{result.get('name')}.json"
        output_json = self.cache_dir.joinpath(filename)
        with utils.post_url(self.folder_url, json=self.folder_request_body) as r:
            self.cache.write_json(output_json, r.json())
            output_dict = {"fileName": filename, "filePath": output_json}
            download_dict = self.cache.read_json(output_dict["filePath"])
            results = download_dict.get("data", {}).get("results", [])
            for result in results:
                if result:
                    if (
                        result.get("type") == -2
                        and result.get("mediaHandlerUrl") is None
                    ):
                        title = result.get("name")
                        payload = {
                            "title": title,
                            "parent_page": str(filename),
                            "case_id": case_id,
                            "asset_url": f"https://publicinfo.fresnosheriff.org/docs/DocView.aspx?id={result.get('entryId')}&dbid=0&repo=SheriffPublic",
                            "name": result.get("name"),
                            "details": {
                                "extension": result.get("extension", None),
                                "year": year,
                            },
                        }
                        childMetadata.append(payload)
                    elif (
                        result.get("type") == -2
                        and result.get("mediaHandlerUrl") is not None
                    ):
                        title = result.get("name")
                        payload = {
                            "title": title,
                            "parent_page": str(filename),
                            "case_id": case_id,
                            "asset_url": f'https://publicinfo.fresnosheriff.org/docs/{result.get("mediaHandlerUrl").replace("/u0026", "&")}',
                            "name": result.get("name"),
                            "details": {
                                "extension": result.get("extension", None),
                                "year": year,
                            },
                        }
                        childMetadata.append(payload)
                    else:
                        childMetadata_list = self._get_child_pages(
                            result, filename, year, case_id
                        )

                        for payload in childMetadata_list:
                            childMetadata.append(payload)

        return childMetadata
