from clean.ca.mesa_city import Site


def test_mesa_scrape_meta_writes_canonical_export(tmp_path, monkeypatch):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")

    monkeypatch.setattr(site, "_download_index_page", lambda _url: "cached-page")
    monkeypatch.setattr(
        site,
        "fetch_media_links",
        lambda _url: [
            {
                "url": " https://example.test/media/evidence.mp4 ",
                "name": " Evidence Clip ",
            }
        ],
    )
    monkeypatch.setattr(
        site.cache,
        "read",
        lambda _path: (
            "<html><body>"
            '<a href="/DocumentCenter/View/123">Case 123</a>'
            '<a href="/Media/records">CR Media</a>'
            "</body></html>"
        ),
    )

    output = site.scrape_meta(throttle=0)

    assert output.exists()
    assert output.name == "ca_mesa_city.json"

    rows = site.cache.read_json(output)
    assert any(row["asset_url"] != row["asset_url"].strip() for row in rows) is False
    assert any(row["name"] != row["name"].strip() for row in rows) is False


def test_mesa_scrape_meta_handles_trailing_slash_urls(tmp_path, monkeypatch):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")

    monkeypatch.setattr(site, "_download_index_page", lambda _url: "cached-page")
    monkeypatch.setattr(
        site,
        "fetch_media_links",
        lambda _url: [
            {
                "url": "https://example.test/media/evidence/",
                "name": "Evidence folder",
            }
        ],
    )
    monkeypatch.setattr(
        site.cache,
        "read",
        lambda _path: (
            "<html><body>"
            '<a href="https://youtu.be/case123/">Case 123 Video</a>'
            '<a href="/Media/records">CR Media</a>'
            "</body></html>"
        ),
    )

    output = site.scrape_meta(throttle=0)

    rows = site.cache.read_json(output)
    names = {row["name"] for row in rows}

    assert output.exists()
    assert all(name for name in names)
