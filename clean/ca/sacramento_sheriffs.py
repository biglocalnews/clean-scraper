import time
from pathlib import Path

from bs4 import BeautifulSoup

from .. import utils
from ..cache import Cache


class Site:
    """Scrape file metadata files for the Sacramento County Sheriff Office.

    Attributes:
        name (str): The official name of the agency
    """

    name = "Sacramento County Sheriff Office"

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
        self.base_url = "https://www.sacsheriff.com/pages/released_cases.php"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)

    @property
    def agency_slug(self) -> str:
        """Construct the agency slug."""
        # Use module path to construct agency slug, which we'll use downstream
        mod = Path(__file__)
        state_postal = mod.parent.stem
        return f"{state_postal}_{mod.stem}"  # ca_sacramento_sheriffs

    def scrape_meta(self, throttle=0):
        # construct a local filename relative to the cache directory - agency slug + page url (ca_sacramento_sheriffs/released_cases.html)
        # download the page (if not already cached)
        # save the index page url to cache (sensible name)
        base_name = f"{self.base_url.split('/')[-1].split('.')[0]}.html"
        filename = f"{self.agency_slug}/{base_name}"
        self.cache.download(filename, self.base_url)
        metadata = []
        html = self.cache.read(filename)
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("div", class_="interior_section")
        rows = body.select("tbody tr")
        for row in rows:
            # Get the relevant data from each <td> element in the row
            date = row.find_all("td")[0].text.strip()
            location = row.find_all("td")[1].text.strip()
            incident_type = row.find_all("td")[2].text.strip()
            officers_involved = row.find_all("td")[3].text.strip()
            gender_of_subject = row.find_all("td")[4].text.strip()
            race_of_subject = row.find_all("td")[5].text.strip()
            ab748_release = row.find_all("td")[6].text.strip()
            sb16_release = row.find_all("td")[7].text.strip()
            link_tag = row.find("a")
            if link_tag:
                case_number = link_tag.text.strip()
                case_link = link_tag.get("href")
                case_link = case_link.replace("dl=0", "dl=1")
                payload = {
                    "asset_url": case_link,
                    "case_id": case_number,
                    "name": case_number,
                    "title": location,
                    "parent_page": str(filename),
                    "details": {
                        "date": date,
                        "location": location,
                        "incident_type": incident_type,
                        "officers_involved": officers_involved,
                        "gender_of_subject": gender_of_subject,
                        "race_of_subject": race_of_subject,
                        "ab748_release": ab748_release,
                        "sb16_release": sb16_release,
                    },
                }
                metadata.append(payload)
            time.sleep(throttle)
        outfile = self.data_dir.joinpath(f"{self.agency_slug}.json")
        self.cache.write_json(outfile, metadata)
        return outfile
