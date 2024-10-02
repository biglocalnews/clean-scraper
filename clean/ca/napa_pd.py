import re
import time
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the City of Napa Police Department.

    Attributes:
        name (str): The official name of the agency
    """

    name = "City of Napa Police Department"

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
        self.base_url = "https://www.cityofnapa.org/1260/Penal-Code-Section-8327-b"
        self.loading_url = "https://www.cityofnapa.org/admin/DocumentCenter/Home/_AjaxLoadingReact?type=0"
        self.loading_payload = {
            "value": "865",
            "expandTree": True,
            "loadSource": 7,
            "selectedFolder": 865,
        }
        self.folder_doc_req = "https://www.cityofnapa.org/Admin/DocumentCenter/Home/Document_AjaxBinding?renderMode=0&loadSource=7"
        self.folder_doc_req_payload = {
            "folderId": 865,
            "getDocuments": 1,
            "imageRepo": False,
            "renderMode": 0,
            "loadSource": 7,
            "requestingModuleID": 75,
            "searchString": "",
            "pageNumber": 1,
            "rowsPerPage": 10000,
            "sortColumn": "DisplayName",
            "sortOrder": 0,
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
        return f"{state_postal}_{mod.stem}"  # ca_napa_pd

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_napa_pd/Penal-Code-Section-8327-b.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.base_url)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("div", class_="moduleContentNew")
        sections = body.find_all("div", class_="row outer wide")
        for section in sections[1:]:
            li_items = section.find_all("li", class_="widgetItem")
            links = [li.find("a") for li in li_items if li.find("a")]
            for link in links:
                link_href = link.get("href", None)
                if link_href:
                    title = link.get_text(strip=True)
                    pattern = r"(NPD\d{8}|NPD\d{2}-\d{6}|NSD\d{2}-\d{6}|10-\d{4})"
                    re.search(pattern, title)
                    match = re.search(pattern, title)
                    if match:
                        case_id = match.group()
                    else:
                        case_id = title
                    if "#" not in link_href:
                        if "youtube" in link_href:
                            youtube_links = utils.get_youtube_url_with_metadata(
                                link_href
                            )
                            for yt_data in youtube_links:
                                name = yt_data["title"]
                                yt_url = yt_data["url"]
                                payload = {
                                    "asset_url": yt_url,
                                    "case_id": case_id,
                                    "name": name,
                                    "title": title,
                                    "parent_page": str(filename),
                                }
                                metadata.append(payload)
                        if "DocumentCenter" in link_href:
                            if "Index" in link_href:
                                folder_id = link_href.split("/")[-1]
                                print("folder_id: ", folder_id)
                                document_list = self.process_document_center(
                                    folder_id, folder_id
                                )
                                print("Document list: ", len(document_list))
                                for document in document_list:
                                    asset_link = f'https://www.cityofnapa.org{document.get("URL", "")}'
                                    name = document.get("DisplayName")
                                    parent_filename = document.get("parent_filename")
                                    payload = {
                                        "asset_url": asset_link,
                                        "case_id": case_id,
                                        "name": name,
                                        "title": title,
                                        "parent_page": str(parent_filename),
                                    }
                                    metadata.append(payload)
                            else:
                                if "cityofnapa.org" not in link_href:
                                    link_href = f"https://www.cityofnapa.org{link_href}"
                                name = link_href.split("/")[-1]
                                name = urllib.parse.unquote(name)
                                payload = {
                                    "asset_url": link_href,
                                    "case_id": case_id,
                                    "name": name,
                                    "title": title,
                                    "parent_page": str(filename),
                                }
                                metadata.append(payload)
                        else:
                            print("unindentified:", link_href)
                    time.sleep(throttle)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile

    def process_document_center(self, folder_id, folder_name):
        documents_list = []
        self.loading_payload["value"] = folder_id
        self.loading_payload["selectedFolder"] = int(folder_id)
        filename = f"{self.agency_slug}/{folder_name}.json"
        output_json = self.cache_dir.joinpath(filename)
        with utils.post_url(self.loading_url, json=self.loading_payload) as r:
            self.cache.write_json(output_json, r.json())
        folder_json = self.cache.read_json(output_json)
        folder_list = folder_json.get("Data", [])
        if len(folder_list) > 0:
            for folder in folder_list:
                name = folder.get("Text")
                new_folder_id = folder.get("Value")
                documents_list.extend(self.process_document_center(new_folder_id, name))

        else:
            self.folder_doc_req_payload["folderId"] = folder_id
            filename = f"{self.agency_slug}/{folder_name}.json"
            output_json = self.cache_dir.joinpath(filename)
            with utils.post_url(
                self.folder_doc_req, json=self.folder_doc_req_payload
            ) as r:
                self.cache.write_json(output_json, r.json())
            folder_json = self.cache.read_json(output_json)
            documents_list = folder_json.get("Documents", [])
            for document in documents_list:
                document["parent_filename"] = filename

        return documents_list
