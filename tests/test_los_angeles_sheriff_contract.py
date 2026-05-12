from copy import deepcopy

import clean.ca.los_angeles_sheriff as los_angeles_sheriff
from clean.ca.config.los_angeles_sheriff import (
    detail_request_headers,
    index_request_headers,
)
from clean.ca.los_angeles_sheriff import Site


def test_get_detail_json_does_not_mutate_imported_request_headers(
    tmp_path, monkeypatch
):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")
    original_headers = deepcopy(detail_request_headers)
    record_id = "record-123"
    captured = {}

    class Response:
        ok = True
        content = b"{}"

    def fake_post(url, headers, data):
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        return Response()

    monkeypatch.setattr(site, "_get_request_verification_token", lambda: "")
    monkeypatch.setattr(site.session, "post", fake_post)
    monkeypatch.setattr(site.cache, "write_binary", lambda *_args, **_kwargs: None)

    site._get_detail_json(record_id)

    assert detail_request_headers == original_headers
    assert captured["headers"]["Referer"].endswith(record_id)


def test_save_assetlist_uses_metadata_contract_writer(tmp_path, monkeypatch):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")
    assetlist = [{"asset_url": "https://example.test/file.pdf", "name": "file.pdf"}]
    call_args = {}

    def fake_write_metadata_export(*, data_dir, agency_slug, records, cache):
        call_args["data_dir"] = data_dir
        call_args["agency_slug"] = agency_slug
        call_args["records"] = records
        call_args["cache"] = cache
        return data_dir / f"{agency_slug}.json"

    monkeypatch.setattr(
        los_angeles_sheriff,
        "write_metadata_export",
        fake_write_metadata_export,
        raising=False,
    )

    output = site._save_assetlist(assetlist)

    assert output == site.data_dir / "ca_los_angeles_sheriff.json"
    assert call_args["data_dir"] == site.data_dir
    assert call_args["agency_slug"] == site.siteslug
    assert call_args["records"] == assetlist
    assert call_args["cache"] is site.cache


def test_lasd_config_headers_do_not_embed_session_tokens():
    for headers in (index_request_headers, detail_request_headers):
        assert "Cookie" not in headers
        assert "__RequestVerificationToken" not in headers
