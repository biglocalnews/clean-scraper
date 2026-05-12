import logging
import time
from copy import deepcopy
from pathlib import Path

import requests

from .. import utils
from ..cache import Cache
from ..metadata_contract import write_metadata_export
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

    If this thing breaks again:
        -- Open a browser. Find the new download page. Go into
            the browser tools, network table, refresh, find the new JSON
            URL. Copy that URL into JSONINDEXURL in the code below.
        -- Open config/ca/los_angeles_sheriff.py.
        -- In your browser, look at the request tab for that index JSON.
            View the Raw version. Replace the payload. Near the end of the
            payload section, reset "pageSize" to 9999. Save!
        -- Go back to your browser. Find that index JSON in the network tab.
            Right-click on it. Select copy, request headers. Paste this into
            a new text editor tab. Kill the lines that begin with POST and
            Content-Length. With your text editor in regex mode:
                -- Search for ^ and replace with "
                -- Search for :space and replace with ": "
                -- Search for $ and replace with ",
        -- Select that hunk of text. Switch back to the config file. Paste it
            in as the *INDEX* request headers. Indent as needed.
        -- Switch back to your web browser. In the Tools: Network panel, trash
            the existing results.
        -- Click on a case, any case. Your Network panel should light up. The first
            file will have URL that starts with a bunch of hexadecimal characters
            mixed with hyphens. Scroll down until you see a second similar filename.
            Click on that.
        -- Now right-click on the filename, pick out Copy, request headers.
        -- Paste this into a new text editor window. As before, go and kill
            the lines that begin with POST and Content-Length. With
            your text editor in regex mode:
            With your text editor in regex mode:
                -- Search for ^ and replace with "
                -- Search for :space and replace with ": "
                -- Search for $ and replace with ",
        -- Paste this into the config file as the *detail* request headers
        -- Within your web browser for that same URL, click over to the "request"
            tab within the network panel. Hit the "raw" button. Highlight everything.
            Copy it into a new text editor. It should look something like this:  {"regarding":{"Id":"e2c722aa-d0e0-ee11-904d-001dd809c772","LogicalName":"sb1421_sb1421responsiverecords","Name":null,"KeyAttributes":[],"RowVersion":null},"sortExpression":"FileLeafRef ASC","page":1,"pageSize":4,"folderPath":""}
        -- Change that pageSize value to 9990.
        -- That ID value that begins with e2c, change that to IDGOESHERE. It may look something like {"regarding":{"Id":"IDGOESHERE","LogicalName":"sb1421_sb1421responsiverecords","Name":null,"KeyAttributes":[],"RowVersion":null},"sortExpression":"FileLeafRef ASC","page":1,"pageSize":9990,"folderPath":""}
        -- In the config file, find the detail payload. Between the single quotes, paste in what you just did.


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
        self.disclosure_url = "https://lasdsb1421.powerappsportals.us/page/"
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
        indexjsonurl = "https://lasdsb1421.powerappsportals.us/_services/entity-grid-data.json/7ebea772-1fab-4aa3-9c03-f3b767f83247"
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
        local_request_headers = deepcopy(detail_request_headers)
        local_request_headers["Referer"] = referer
        local_payload = detail_payload.replace("IDGOESHERE", recordid)
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
        return write_metadata_export(
            data_dir=self.data_dir,
            agency_slug=self.siteslug,
            records=assetlist,
            cache=self.cache,
        )
