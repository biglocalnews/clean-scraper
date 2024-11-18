import os
import time
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata and download files for the City of Lake County Sheriff.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Lake County Sheriff"

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
        self.base_url = "https://www.lakesheriff.com/969/Use-of-Force"
        self.zenrows_api_url = "https://api.zenrows.com/v1/"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)
        dotenv_path = "env/.env"
        load_dotenv(dotenv_path=dotenv_path)
        self.params = {
            "apikey": os.getenv("ZENROWS_KEY"),
            "url": "",  # Target website URL
            # Add any other ZenRows parameters here (optional)
        }

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_lake_county_sheriff

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_lake_county_sheriff/Use-of-Force.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.params["url"] = self.base_url
        self.cache.download(filename, self.zenrows_api_url, params=self.params)
        metadata = []
        child_pages = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("table", class_="fr-alternate-rows")
        child_links = body.find_all("a")
        for link in child_links:
            tr_tag = link.find_parent("tr")
            td_tag = tr_tag.find_all("td")
            child_page_data = dict()
            child_page_data["date"] = td_tag[0].text
            child_page_data["location"] = td_tag[1].get_text(separator=", ")
            child_page_data["name"] = td_tag[2].text
            child_page_data["incident_type"] = td_tag[3].abbr.text
            child_page_data["case_number"] = link.text
            child_file_name = (
                f'{self.agency_slug}/{child_page_data["case_number"]}.html'
            )
            if link["href"]:
                link_url = f"https://www.lakesheriff.com{link['href']}"
                self.params["url"] = link_url
                self.cache.download(
                    child_file_name, self.zenrows_api_url, params=self.params
                )
                child_page_data["page_filename"] = child_file_name
                child_pages.append(child_page_data)
            time.sleep(throttle)
        for child_page in child_pages:
            html = self.cache.read(child_page["page_filename"])
            soup = BeautifulSoup(html, "html.parser")
            body = soup.find(attrs={"data-cprole": "mainContentContainer"})
            links = body.find_all("a")
            for link in links:
                link_href = link.get("href", None)
                if link_href:
                    if "youtu" in link_href:
                        payload = {
                            "asset_url": link_href,
                            "case_id": child_page["case_number"],
                            "name": link.text,
                            "title": link.text,
                            "parent_page": str(child_page["page_filename"]),
                            "details": {
                                "date": child_page["date"],
                                "location": child_page["location"],
                                "name": child_page["name"],
                                "incident_type": child_page["incident_type"],
                            },
                        }
                        metadata.append(payload)
                    elif "DocumentCenter" in link_href:
                        payload = {
                            "asset_url": f"https://www.lakesheriff.com{link_href}",
                            "case_id": child_page["case_number"],
                            "name": link.text,
                            "title": link.text,
                            "parent_page": str(child_page["page_filename"]),
                            "details": {
                                "date": child_page["date"],
                                "location": child_page["location"],
                                "name": child_page["name"],
                                "incident_type": child_page["incident_type"],
                            },
                        }
                        metadata.append(payload)
                    elif "gallery" in link_href:
                        gallery_id = link_href.split("=")[-1]
                        galley_link = f"https://www.lakesheriff.com/SlideShow.aspx?AID={gallery_id}&AN=Sheriff%20-%20Use%20of%20Force%20-%20Case%2014110123"
                        self.params["url"] = galley_link
                        images_file_name = (
                            f"{self.agency_slug}/images_{gallery_id}.html"
                        )
                        self.cache.download(
                            images_file_name, self.zenrows_api_url, params=self.params
                        )
                        html = self.cache.read(images_file_name)
                        soup = BeautifulSoup(html, "html.parser")
                        body = soup.find("div", class_="slides")
                        a_tags = body.find_all("a")
                        for a_tag in a_tags:
                            img_tag = a_tag.find("img")
                            # Get the 'src' and 'alt' attributes
                            image_src = img_tag.get("src")
                            image_alt = img_tag.get("alt")
                            payload = {
                                "asset_url": f"https://www.lakesheriff.com{image_src}",
                                "case_id": child_page["case_number"],
                                "name": image_alt,
                                "title": link.text,
                                "parent_page": str(child_page["page_filename"]),
                                "details": {
                                    "date": child_page["date"],
                                    "location": child_page["location"],
                                    "name": child_page["name"],
                                    "incident_type": child_page["incident_type"],
                                },
                            }
                            metadata.append(payload)

        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile
