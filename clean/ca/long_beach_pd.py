import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache

# from .config.palm_springs_pd import index_request_headers


class Site:
    """
    Scrape file metadata and download files for the long_beach_pd.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Long Beach Police Department"

    def __init__(
        self,
        data_dir: Path = utils.CLEAN_DATA_DIR,
        cache_dir: Path = utils.CLEAN_CACHE_DIR,
    ):
        """
        Initialize a new instance.

        Args:
            data_dir (Path): The directory where downstream processed files/data will be saved
            cache_dir (Path): The directory where files will be cached
        """
        self.base_url = "https://www.longbeach.gov/police/about-the-lbpd/lbpd-1421748/"
        self.folder_url = "https://citydocs.longbeach.gov/LBPDPublicDocs/FolderListingService.aspx/GetFolderListing2"
        self.folder_content_url = "https://citydocs.longbeach.gov/LBPDPublicDocs/FolderListingService.aspx/GetFolderListing2"
        self.folder_request_body = {
            "repoName": "r-3261686e",
            "folderId": 726681,
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
        return f"{state_postal}_{mod.stem}"  # ca_fullerton

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_path_springs_pd/policies-procedures-training-manuals.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-2]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.base_url)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("div", class_="col-md-12 col-sm-12")
        links = body.find_all("a")
        local_index_json = []
        child_pages = []
        for link in links:
            previous_h3 = link.find_previous("h3")
            if previous_h3:
                if previous_h3.string == "Assembly Bill 748 (AB 748)":
                    link_name = link.string
                    if link_name:
                        child_link = f"https://www.longbeach.gov{link['href']}"
                        child_page_name = link_name.split("/")[0]
                        child_page_name = f"{child_page_name}.html"
                        filename = f"{self.agency_slug}/{child_page_name}"
                        self.cache.download(filename, child_link)
                        child_pages.append(filename)

        for child_page in child_pages:
            html = self.cache.read(child_page)
            soup = BeautifulSoup(html, "html.parser")
            body = soup.find("div", class_="col-md-12 col-sm-12")
            links = body.find_all("a")
            for link in links:
                url = link["href"]
                title = link.string
                if title:
                    case_id = title
                    case_id = case_id.replace("/", "")
                    if "globalassets" in url:
                        name = url.split("/")[0]
                        payload = {
                            "title": title,
                            "parent_page": str(child_page),
                            "case_id": case_id,
                            "asset_url": f"https://www.longbeach.gov{url}",
                            "name": name,
                            "details": {"extension": None},
                        }
                        metadata.append(payload)
                    elif "citydocs" in url:
                        id_value, repo_value = self.extract_id_and_repo(url)
                        if id_value:
                            self.folder_request_body["folderId"] = id_value
                            self.folder_request_body["repoName"] = repo_value
                            filename = f"{self.agency_slug}/{case_id}.json"
                            output_json = self.cache_dir.joinpath(filename)
                            with utils.post_url(
                                self.folder_url, json=self.folder_request_body
                            ) as r:
                                self.cache.write_json(output_json, r.json())
                                output_dict = {
                                    "fileName": filename,
                                    "filePath": output_json,
                                    "title": title,
                                    "repo_val": repo_value,
                                    "case_id": case_id,
                                }
                                local_index_json.append(output_dict)

                time.sleep(throttle)

        for child_json_meta in local_index_json:
            repo_val = child_json_meta["repo_val"]
            title = child_json_meta["title"]
            download_dict = self.cache.read_json(child_json_meta["filePath"])
            results = download_dict.get("data", {}).get("results", [])
            title = download_dict.get("data", {}).get("name", "")
            case_id = child_json_meta["case_id"]
            for result in results:
                if result:
                    if (
                        result.get("type") == -2
                        and result.get("mediaHandlerUrl") is None
                    ):
                        payload = {
                            "title": title,
                            "parent_page": str(child_json_meta["fileName"]),
                            "case_id": case_id,
                            "asset_url": f"https://citydocs.longbeach.gov/LBPDPublicDocs/DocView.aspx?id={result.get('entryId')}&repo={repo_val}",
                            "name": result.get("name"),
                            "details": {
                                "extension": result.get("extension", None),
                            },
                        }
                        metadata.append(payload)
                    elif (
                        result.get("type") == -2
                        and result.get("mediaHandlerUrl") is not None
                    ):
                        payload = {
                            "title": title,
                            "parent_page": str(child_json_meta["fileName"]),
                            "case_id": case_id,
                            "asset_url": f'https://citydocs.longbeach.gov/LBPDPublicDocs/{result.get("mediaHandlerUrl").replace("/u0026", "&")}',
                            "name": result.get("name"),
                            "details": {
                                "extension": result.get("extension", None),
                            },
                        }
                        metadata.append(payload)
                    elif result.get("type") == 0:

                        childMetadata_list = self._get_child_pages(
                            result, child_json_meta["fileName"], child_json_meta
                        )
                        for payload in childMetadata_list:
                            metadata.append(payload)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def _get_child_pages(self, result, parent_path, child_val):
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
                        payload = {
                            "title": child_val["title"],
                            "parent_page": str(filename),
                            "case_id": child_val["case_id"],
                            "asset_url": f"https://citydocs.longbeach.gov/LBPDPublicDocs/DocView.aspx?id={result.get('entryId')}&repo={child_val['repo_val']}",
                            "name": result.get("name"),
                            "details": {
                                "extension": result.get("extension", None),
                            },
                        }
                        childMetadata.append(payload)
                    elif (
                        result.get("type") == -2
                        and result.get("mediaHandlerUrl") is not None
                    ):
                        payload = {
                            "title": child_val["title"],
                            "parent_page": str(filename),
                            "case_id": child_val["case_id"],
                            "asset_url": f'https://citydocs.longbeach.gov/LBPDPublicDocs/{result.get("mediaHandlerUrl").replace("/u0026", "&")}',
                            "name": result.get("name"),
                            "details": {
                                "extension": result.get("extension", None),
                            },
                        }
                        childMetadata.append(payload)
                    else:
                        childMetadata_list = self._get_child_pages(
                            result, filename, child_val
                        )

                        for payload in childMetadata_list:
                            childMetadata.append(payload)

        return childMetadata

    def extract_id_and_repo(self, url):
        # Parse the URL and extract the query parameters
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        # Extract the 'id' and 'repo' values
        id_value = query_params.get("id", [None])[0]
        repo_value = query_params.get("repo", [None])[0]

        return id_value, repo_value

    def extract_dates(self, strings):
        date_pattern = re.compile(r"\b\d{2}/\d{2}/\d{2}\b")
        dates = []
        match = date_pattern.search(strings)
        if match:
            return match.group()
        else:
            dates.append(None)

        return dates
