import logging
import time
from pathlib import Path

import requests

from .. import utils
from ..cache import Cache
from .config.los_angeles_sheriff import (
    detail_payload,
    detail_request_headers,
    index_payload,
    index_request_headers,
)

logger = logging.getLogger(__name__)


class Site:
    """Scrapes California's Los Angeles Sheriff's Department.

    Notes:
        Several things in this scraper may break with library updates or standarization efforts.
        cache.write_json and cache.read_json are using absolute paths.
        There is no standarized POST function yet.
        BLN request headers are not used, though those might break the scraper.
    """

    name = "Los Angeles Sheriff's Department"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        self.siteslug = "ca_los_angeles_sheriff"
        self.rooturl = "https://lasdsb1421.powerappsportals.us"
        self.filestoignore = [
            "index",
            "timestamplog",
            self.siteslug,
            "caseindex",
        ]  # What cached JSON files aren't page-level JSONs?
        self.base_url = "https://lasd.org/"
        self.disclosure_url = "https://lasdsb1421.powerappsportals.us/"
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.cache = Cache(cache_dir)
        self.subpages_dir = cache_dir / (self.siteslug + "/subpages")
        for localdir in [self.cache_dir, self.data_dir, self.subpages_dir]:
            utils.create_directory(localdir)

    def scrape_meta(self, throttle: int = 0) -> Path:
        rawindex = self._fetch_index()
        oldtimestamps = self._fetch_old_timestamps()
        indextimes = self._build_timestamps(rawindex)
        detailtodo = self._build_detail_todo(indextimes, oldtimestamps)
        self._fetch_detail_pages(detailtodo, throttle)
        self._save_timestamps(indextimes)
        caseindex = self._build_caseindex(rawindex)
        assetlist = self._build_assetlist(caseindex)
        assetlist_filename = self._save_assetlist(assetlist)
        return assetlist_filename

    def _fetch_index(self):
        indexjsonurl = "https://lasdsb1421.powerappsportals.us/_services/entity-grid-data.json/f46b70cc-580b-4f1a-87c3-41deb48eb90d"
        r = requests.post(
            indexjsonurl,
            headers=index_request_headers,
            data=index_payload,
        )
        targetfilename = f"{self.siteslug}/index.json"
        self.cache.write_binary(targetfilename, r.content)
        # FIXME:
        #        with open(self.cache_dir / (self.siteslug + "/index.json"), "wb") as outfile:
        #            outfile.write(r.content)
        rawindex = self.cache.read_json(self.cache_dir / targetfilename)
        # TODO: #70 implementation affects above
        if rawindex["MoreRecords"] or len(rawindex["Records"]) != rawindex["ItemCount"]:
            logger.error("Index JSON is incomplete or broken.")
        else:
            logger.debug(f"{rawindex['ItemCount']:,} records found.")
        return rawindex

    def _build_timestamps(self, rawindex: dict):
        indextimes = {}
        for record in rawindex["Records"]:
            recordid = record["Id"]
            timestamp = ""
            for entry in record["Attributes"]:
                timestamp += entry["AttributeMetadata"]["ModifiedOn"]
            indextimes[recordid] = timestamp
        return indextimes

    def _fetch_old_timestamps(self):
        partfilename = self.siteslug + "/timestamplog.json"
        fullfilename = self.cache_dir / partfilename
        if self.cache.exists(partfilename):
            oldtimestamps = self.cache.read_json(fullfilename)
        else:
            oldtimestamps = {}
        return oldtimestamps

    def _save_timestamps(self, indextimestamps):
        targetfilename = self.siteslug + "/timestamplog.json"
        self.cache.write_json(self.cache_dir / targetfilename, indextimestamps)
        return

    def _get_detail_json(self, recordid: str):
        referer = "https://lasdsb1421.powerappsportals.us/disfiles/?id=" + recordid
        local_request_headers = detail_request_headers
        local_request_headers["Referer"] = referer
        local_payload = detail_payload
        local_payload = local_payload.replace("IDGOESHERE", recordid)
        targeturl = (
            "https://lasdsb1421.powerappsportals.us/_services/sharepoint-data.json/"
            + recordid
        )
        targetfilename = f"{self.siteslug}/subpages/{recordid}.json"
        r = requests.post(
            targeturl,
            headers=local_request_headers,
            data=local_payload,
        )
        if not r.ok:
            logger.warning(f"Problem downloading detail JSON for {recordid}")
        else:
            self.cache.write_binary(targetfilename, r.content)

    def _build_detail_file_list(self):
        cachefiles = self.cache.files(subdir=self.siteslug + "/subpages")
        recordsdownloaded = set()
        for cachefile in cachefiles:
            corefilename = (
                cachefile.replace("\\", "/").split("/")[-1].replace(".json", "")
            )
            if corefilename not in self.filestoignore:
                recordsdownloaded.add(corefilename)
        return recordsdownloaded

    def _build_detail_todo(self, indextimes, oldtimestamps):
        todo = set()
        recordsdownloaded = self._build_detail_file_list()
        for recordid in indextimes:
            if recordid not in recordsdownloaded:
                todo.add(recordid)
            elif recordid not in oldtimestamps:
                todo.add(recordid)
            elif (
                indextimes[recordid] != oldtimestamps[recordid]
            ):  # If something got modified, maybe
                todo.add(recordid)
        logger.debug(f"{len(todo):,} subpages to download")
        return todo

    def _fetch_detail_pages(self, detailtodo, throttle):
        for recordid in detailtodo:
            self._get_detail_json(recordid)
            time.sleep(throttle)

    def _build_caseindex(self, rawindex):
        caseindex = {}
        sectiontypes = [
            "case_number",
            "recordid",
            "case_type",
            "suspectvictim",
            "event_date_epoch",
            "event_date_human",
            "release_date_epoch",
            "release_date_human",
        ]
        for record in rawindex["Records"]:
            line = {}
            for sectiontype in sectiontypes:
                line[sectiontype] = None
            line["recordid"] = record["Id"]
            for a in record["Attributes"]:
                if a["Name"] == "sb1421_name":
                    line["case_number"] = a["Value"]
                elif a["Name"] == "sb1421_caseorincidenttype":
                    line["case_type"] = a["DisplayValue"]
                elif a["Name"] == "sb1421_suspectvictim":
                    line["suspectvictim"] = a["Value"]
                elif a["Name"] == "sb1421_publicreleasedate":
                    line["release_date_human"] = a["DisplayValue"]
                    line["release_date_epoch"] = int(
                        a["Value"].split("(")[1].split(")")[0]
                    )
                elif a["Name"] == "sb1421_eventdate":
                    line["event_date_human"] = a["DisplayValue"]
                    line["event_date_epoch"] = int(
                        a["Value"].split("(")[1].split(")")[0]
                    )
            caseindex[line["recordid"]] = line
        return caseindex

    def _build_assetlist(self, caseindex):
        assetlist = []
        recordsdownloaded = self._build_detail_file_list()
        for recordid in recordsdownloaded:
            sourcefile = self.cache_dir / f"{self.siteslug}/subpages/{recordid}.json"
            localjson = self.cache.read_json(sourcefile)
            for asset in localjson["SharePointItems"]:
                line = {}
                line["asset_url"] = self.rooturl + asset["Url"]
                line["name"] = asset["Name"]
                line["parent_page"] = str(sourcefile).replace("\\", "/").split("/")[-1]
                line["title"] = asset["Name"]
                line["case_id"] = caseindex[recordid]["case_number"]
                line["details"] = {}
                line["details"]["filesize"] = asset["FileSize"]
                line["details"]["date_modified"] = asset["ModifiedOnDisplay"]
                line["details"]["date_created"] = asset["CreatedOnDisplay"]
                for item in [
                    "case_type",
                    "suspectvictim",
                    "event_date_epoch",
                    "event_date_human",
                    "release_date_epoch",
                    "release_date_human",
                ]:
                    line["details"][("case_" + item).replace("case_case_", "case_")] = (
                        caseindex[recordid][item]
                    )
                    assetlist.append(line)
        return assetlist

    def _save_assetlist(self, assetlist):
        targetfilename = self.data_dir / (self.siteslug + ".json")
        logger.debug(f"Saving asset list to {targetfilename}")
        self.cache.write_json(self.cache_dir / targetfilename, assetlist)
        return targetfilename
