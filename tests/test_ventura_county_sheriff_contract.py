from clean.ca.ventura_county_sheriff import Site


def test_ventura_scrape_meta_writes_canonical_export(tmp_path, monkeypatch):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")
    site.index_urls = {"https://example.test/index": "index.html"}

    monkeypatch.setattr(
        site,
        "_process_index_page",
        lambda _url: (
            ["https://example.test/detail"],
            [
                {
                    "asset_url": " https://example.test/index.pdf ",
                    "name": " Index File ",
                    "parent_page": r"ca_ventura_county_sheriff\index.html",
                }
            ],
        ),
    )
    monkeypatch.setattr(
        site,
        "_process_detail_page",
        lambda _url: [
            {
                "asset_url": " https://example.test/detail.pdf ",
                "name": " Detail File ",
                "parent_page": r"ca_ventura_county_sheriff\detail.html",
            }
        ],
    )

    output = site.scrape_meta(throttle=0)

    assert output.exists()
    assert output.name == "ca_ventura_county_sheriff.json"

    rows = site.cache.read_json(output)
    assert rows[0]["asset_url"] == "https://example.test/index.pdf"
    assert rows[0]["name"] == "Index File"
    assert rows[0]["parent_page"] == "ca_ventura_county_sheriff/index.html"
