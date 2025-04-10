#!/usr/bin/env python

"""
Find new metadata entries.

This little program is intended to extract items that are in a newer copy
of clean-scraper's meta-scrape output but are not in an older copy.

This does not do a full diff, e.g., it does not flag old entries that
were not found in the new entries.

By default this is set up to be copied to and run from ~/.clean-scraper,
with your newer files in `exports` and your older files in `exportsold`.
"""

import json
from glob import glob

from tqdm import tqdm

newexportdir = "exports/"
oldexportdir = "exportsold/"
wantunchangedfiles = (
    False  # Publish a listing of new entries in situations with no new entries?
)

newfilesraw = glob(f"{newexportdir}*.json")
newfiles = []
for newfileraw in newfilesraw:
    newfiles.append(newfileraw.replace("\\", "/").replace(newexportdir, ""))
oldfilesraw = glob(f"{oldexportdir}*.json")
oldfiles = []
for oldfileraw in oldfilesraw:
    oldfiles.append(oldfileraw.replace("\\", "/").replace(oldexportdir, ""))
filestocheck = []
for newfile in newfiles:
    if newfile in oldfiles:
        filestocheck.append(newfile)
print(f"{len(filestocheck):,} files to compare.")


def import_json(filepath: str):
    with open(filepath, encoding="utf-8") as infile:
        rawdata = json.load(infile)
    data = {}
    for entry in rawdata:
        asset_url = entry["asset_url"]
        if asset_url in data:
            print(f"Multiple entries for {asset_url} found in {filepath}")
        data[asset_url] = entry
    return data


filesgenerated = 0
entriesidentified = 0
for filetocheck in tqdm(filestocheck):
    datanew = import_json(newexportdir + filetocheck)
    dataold = import_json(oldexportdir + filetocheck)
    newassets = []
    for asset_url in datanew:
        if asset_url not in dataold:
            newassets.append(datanew[asset_url])
            entriesidentified += 1
    if len(newassets) > 0 or wantunchangedfiles:
        targetfile = newexportdir + "additions_" + filetocheck
        with open(targetfile, "w", encoding="utf-8") as outfile:
            outfile.write(json.dumps(newassets, indent=4 * " "))
        filesgenerated += 1
print(
    f"{entriesidentified:,} new entries identified among {filesgenerated:,} files generated."
)
