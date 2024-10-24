import re
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
        self.base_url = (
            "https://portal.laserfiche.com/Portal/Browse.aspx?id=726681&repo=r-3261686e"
        )
        self.folder_url = "https://portal.laserfiche.com/Portal/FolderListingService.aspx/GetFolderListing2"
        self.folder_content_url = "https://portal.laserfiche.com/Portal/FolderListingService.aspx/GetFolderListing2"
        self.folder_request_body = {
            "repoName": "r-3261686e",
            "folderId": 726681,
            "getNewListing": True,
            "start": 0,
            "end": 36,
            "sortColumn": "",
            "sortAscending": True,
        }
        self.start_export_url = (
            "https://portal.laserfiche.com/Portal/ZipEntriesHandler.aspx/StartExport"
        )
        self.start_export_payload = {
            "repoName": "r-3261686e",
            "ids": [],
            "key": -1,
            "watermarkIdx": -1,
        }
        self.check_export_status_url = "https://portal.laserfiche.com/Portal/ZipEntriesHandler.aspx/CheckExportStatus"
        self.download_exported_url = (
            "https://portal.laserfiche.com/Portal/ExportJobHandler.aspx/GetExportJob/"
        )
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_fullerton

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_fullerton/SB_1421.json)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = "SB_1421.json"
        filename = f"{self.agency_slug}/{base_name}"
        base_output_json = self.cache_dir.joinpath(filename)
        base_output_json.parent.mkdir(parents=True, exist_ok=True)
        with utils.post_url(self.folder_url, json=self.folder_request_body) as r:
            self.cache.write_json(base_output_json, r.json())

        metadata = []
        base_json = self.cache.read_json(base_output_json)
        results = base_json.get("data", {}).get("results", [])
        local_index_json = []
        for result in results:
            self.folder_request_body["folderId"] = result.get("entryId")
            filename = f"{self.agency_slug}/{result.get('name')}.json"
            output_json = self.cache_dir.joinpath(filename)
            with utils.post_url(self.folder_url, json=self.folder_request_body) as r:
                self.cache.write_json(output_json, r.json())
                output_dict = {"fileName": filename, "filePath": output_json}
                local_index_json.append(output_dict)
            time.sleep(throttle)
        for download_json_path in local_index_json:
            download_dict = self.cache.read_json(download_json_path["filePath"])
            results = download_dict.get("data", {}).get("results", [])
            title = download_dict.get("data", {}).get("name", "")
            case_id = self._get_case_id(title)
            for result in results:
                if result.get("type") == -2 and result.get("mediaHandlerUrl") is None:
                    payload = {
                        "title": title,
                        "parent_page": str(download_json_path["fileName"]),
                        "case_id": case_id,
                        "asset_url": f"https://portal.laserfiche.com/Portal/DocView.aspx?id={result.get('entryId')}&repo=r-3261686e",
                        "name": result.get("name"),
                        "details": {"extension": result.get("extension", None)},
                    }
                    metadata.append(payload)
                elif (
                    result.get("type") == -2
                    and result.get("mediaHandlerUrl") is not None
                ):
                    payload = {
                        "title": title,
                        "parent_page": str(download_json_path["fileName"]),
                        "asset_url": f'https://portal.laserfiche.com/Portal/{result.get("mediaHandlerUrl").replace("/u0026", "&")}',
                        "name": result.get("name"),
                        "details": {"extension": result.get("extension", None)},
                    }
                    metadata.append(payload)
                elif result.get("type") == 0:
                    childMetadata_list = self._get_child_pages(
                        result, download_json_path["fileName"], title
                    )
                    for payload in childMetadata_list:
                        metadata.append(payload)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def _get_child_pages(self, result, parent_path, parent_title):
        childMetadata = []
        self.folder_request_body["folderId"] = result.get("entryId")
        filename = f"{str(parent_path).split('.json')[0]}/{result.get('name')}.json"
        output_json = self.cache_dir.joinpath(filename)
        with utils.post_url(self.folder_url, json=self.folder_request_body) as r:
            self.cache.write_json(output_json, r.json())
            output_dict = {"fileName": filename, "filePath": output_json}
            download_dict = self.cache.read_json(output_dict["filePath"])
            results = download_dict.get("data", {}).get("results", [])
            case_id = self._get_case_id(parent_title)
            for result in results:
                if result.get("type") == -2 and result.get("mediaHandlerUrl") is None:
                    payload = {
                        "title": parent_title,
                        "parent_page": str(filename),
                        "case_id": case_id,
                        "asset_url": f"https://portal.laserfiche.com/Portal/DocView.aspx?id={result.get('entryId')}&repo=r-3261686e",
                        "name": result.get("name"),
                        "details": {"extension": result.get("extension", None)},
                    }
                    childMetadata.append(payload)
                elif (
                    result.get("type") == -2
                    and result.get("mediaHandlerUrl") is not None
                ):
                    payload = {
                        "title": parent_title,
                        "parent_page": str(filename),
                        "case_id": case_id,
                        "asset_url": f'https://portal.laserfiche.com/Portal/{result.get("mediaHandlerUrl").replace("/u0026", "&")}',
                        "name": result.get("name"),
                        "details": {"extension": result.get("extension", None)},
                    }
                    childMetadata.append(payload)
                else:
                    childMetadata_list = self._get_child_pages(
                        result, filename, parent_title
                    )

                    for payload in childMetadata_list:
                        childMetadata.append(payload)

        return childMetadata

    def _get_case_id(self, title):
        case_id_pattern = r"\b(FPD# \d{2,5}-\d{3,5}|FN# \d{2}-\d{4})\b"
        case_ids = re.findall(case_id_pattern, title)
        if len(case_ids) > 0:
            return case_ids[0]
        else:
            return title
