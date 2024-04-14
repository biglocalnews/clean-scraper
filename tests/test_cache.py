import pytest
from pathlib import Path
from unittest.mock import patch

from clean.cache import Cache

@pytest.fixture
def cache(tmp_path):
    return Cache(tmp_path)

@pytest.mark.vcr
def test_download_existing_file(cache):
    # Create a dummy file in the cache
    file_path = cache.path / "existing_file.txt"
    file_path.touch()

    # Call the download method with force=False
    result = cache.download("existing_file.txt", "http://example.com", force=False)

    # Assert that the existing file is returned
    assert result == file_path

@pytest.mark.vcr
def test_download_new_file(cache):
    # Call the download method with a new file
    result = cache.download("new_file.txt", "http://example.com")

    # Assert that a new file is created in the cache
    assert result.exists()

@pytest.mark.vcr
def test_download_existing_file_with_force(cache):
    # Create a dummy file in the cache
    file_path = cache.path / "existing_file.txt"
    file_path.touch()

    # Call the download method with force=True
    result = cache.download("existing_file.txt", "http://example.com", force=True)

    # Assert that a new file is created in the cache
    assert result.exists()

@pytest.mark.vcr
def test_download_with_encoding(cache):
    # Call the download method with encoding specified
    result = cache.download("file.txt", "http://example.com", encoding="utf-8")

    # Assert that the file is downloaded with the specified encoding
    assert result.exists()

@pytest.mark.vcr
@patch("clean.cache.get_url")
def test_download_with_additional_args(mock_get_url, cache):
    # Call the download method with additional arguments
    result = cache.download("file.txt", "http://example.com", headers={"User-Agent": "Mozilla/5.0"})

    # Assert that the additional arguments are passed to get_url
    mock_get_url.assert_called_once_with("http://example.com", stream=True, headers={"User-Agent": "Mozilla/5.0"})