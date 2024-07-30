import json
import time
from pathlib import Path
from typing import List

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the laserfiche.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Laserfiche"

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
        return f"{state_postal}_{mod.stem}"  # ca_santa_rosa

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_laserfiche/SB_1421.json)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = "SB_1421.json"
        filename = f"{self.agency_slug}/{base_name}"
        base_output_json = self.cache_dir.joinpath(filename)
        with utils.post_url(self.folder_url, json=self.folder_request_body) as r:
            self.cache.write_json(filename, r.json())

        metadata = []
        base_json = self.cache.read_json(base_output_json)
        results = base_json.get("data", {}).get("results", [])
        local_index_json = []
        for result in results:
            self.folder_request_body["folderId"] = result.get("entryId")
            filename = f"{self.agency_slug}/{result.get('name')}.json"
            output_json = self.cache_dir.joinpath(filename)
            with utils.post_url(self.folder_url, json=self.folder_request_body) as r:
                self.cache.write_json(filename, r.json())
                local_index_json.append(output_json)
        for download_json_path in local_index_json:
            download_dict = self.cache.read_json(download_json_path)
            results = download_dict.get("data", {}).get("results", [])
            title = download_dict.get("data", {}).get("name", "")
            for result in results:
                payload = {
                    "title": title,
                    "parent_page": str(download_json_path),
                    "asset_id": result.get("entryId"),
                    "name": result.get("name"),
                }
                metadata.append(payload)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def scrape(self, throttle: int = 4, filter: str = "") -> List[Path]:
        metadata = self.cache.read_json(
            self.data_dir.joinpath(f"{self.agency_slug}.json")
        )
        dl_assets = []
        for asset in metadata:
            data_id = asset["asset_id"]
            print("Downloading document id", data_id)
            ids_list = self.start_export_payload.get("ids")
            if not isinstance(ids_list, list):
                ids_list = [str(data_id)]
                self.start_export_payload["ids"] = ids_list
            else:
                ids_list = [str(data_id)]
                self.start_export_payload["ids"] = ids_list
            page_url = f"https://portal.laserfiche.com/Portal/Browse.aspx?id={data_id}&repo=r-3261686e"
            cookies = utils.get_cookies(page_url)
            with utils.post_url(
                self.start_export_url,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                cookies=cookies,
                json=self.start_export_payload,
            ) as r:
                start_dict = json.loads(r.text)
                export_token = {
                    "token": start_dict.get("data").get("token"),
                }
                while True:
                    with utils.post_url(
                        self.check_export_status_url,
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                        cookies=cookies,
                        json=export_token,
                    ) as r:
                        check_status = json.loads(r.text)
                        print("check_status: ", check_status)
                        if check_status.get("data").get("finished"):
                            print("Export Finished")
                            time.sleep(1)
                            break
                exported_url = (
                    f"{self.download_exported_url}?token={export_token['token']}"
                )
                with utils.get_url(
                    exported_url,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    cookies=cookies,
                ) as r:
                    extension = self._get_file_extension(r)
                    name = self._make_download_path(asset=asset, extension=extension)
                    local_path = Path(self.cache_dir, name)
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    if self.cache.exists(name=name):
                        dl_assets.append(local_path)
                        continue
                    r.encoding = "utf-8"
                    # Write out the file in little chunks
                    with open(local_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                        dl_assets.append(local_path)
        return dl_assets

    def _make_download_path(self, asset, extension):
        folder_name = asset["title"]
        name = asset["name"]
        name = f"{name}.{extension}"
        outfile = f"{folder_name}/{name}"
        dl_path = Path(self.agency_slug, "assets", outfile)
        print(dl_path)
        return dl_path

    def _get_file_extension(self, response):
        print("file Name: ", response.headers.get("Content-Disposition", ""))
        extension = response.headers.get("Content-Disposition", "").split(".")[-1]
        extension = extension.replace('"', "")
        return extension
