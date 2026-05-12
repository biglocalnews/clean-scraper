import clean.ca.pomona_pd as pomona_pd
from clean.ca.pomona_pd import Site


def _minimal_index_html() -> str:
    return """
    <html>
      <body>
        <table id=\"gridView\">
          <b class=\"dxp-lead dxp-summary\">Page 1 of 1</b>
        </table>
        <table id=\"gridView_DXMainTable\"></table>
      </body>
    </html>
    """


def _mock_scrape_dependencies(site: Site, monkeypatch):
    monkeypatch.setattr(site.cache, "download", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        site.cache, "read", lambda *_args, **_kwargs: _minimal_index_html()
    )
    monkeypatch.setattr(site.cache, "write_json", lambda path, _payload: path)
    monkeypatch.setattr(site, "get_headers_and_cookies", lambda: [])


def test_pomona_scrape_meta_does_not_print_to_stdout(tmp_path, monkeypatch, capsys):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")
    _mock_scrape_dependencies(site, monkeypatch)

    site.scrape_meta(throttle=0)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_pomona_agency_slug_is_canonical(tmp_path):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")
    assert site.agency_slug == "ca_pomona_pd"


def test_pomona_urls_do_not_embed_session_path(tmp_path):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")
    assert "/_rs/(S(" not in site.base_url
    assert "/_rs/(S(" not in site.child_page_url


def test_pomona_scrape_meta_uses_contract_writer_and_canonical_name(
    tmp_path, monkeypatch
):
    site = Site(data_dir=tmp_path / "exports", cache_dir=tmp_path / "cache")
    _mock_scrape_dependencies(site, monkeypatch)

    call_args = {}

    def fake_write_metadata_export(*, data_dir, agency_slug, records, cache):
        call_args["data_dir"] = data_dir
        call_args["agency_slug"] = agency_slug
        call_args["records"] = list(records)
        call_args["cache"] = cache
        return data_dir / f"{agency_slug}.json"

    monkeypatch.setattr(
        pomona_pd,
        "write_metadata_export",
        fake_write_metadata_export,
        raising=False,
    )

    output = site.scrape_meta(throttle=0)

    assert output.name == "ca_pomona_pd.json"
    assert call_args.get("agency_slug") == "ca_pomona_pd"
    assert call_args.get("data_dir") == site.data_dir
    assert call_args.get("cache") is site.cache
