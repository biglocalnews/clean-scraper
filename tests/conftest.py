import csv
import os
from pathlib import Path

import pytest

# NOTE: To check if vcrpy/pytest-vcr
# is using cassettes as opposed to making
# live web requests, uncomment below
# and pass pytest caplog fixture to
# a test function. More details here:
#  https://vcrpy.readthedocs.io/en/latest/debugging.html
"""
import vcr
import logging
logging.basicConfig() # you need to initialize logging, otherwise you will not see anything from vcrpy
vcr_log = logging.getLogger("vcr")
vcr_log.setLevel(logging.INFO)
"""


@pytest.fixture(scope="module")
def vcr_cassette_dir(request):
    mod_name = request.module.__name__.split("tests.")[-1]
    return os.path.join("tests/cassettes", mod_name)


@pytest.fixture
def clean_scraper_dir(tmp_path):
    return str(tmp_path.joinpath(".clean-scraper"))


@pytest.fixture
def create_scraper_dir(clean_scraper_dir):
    Path(clean_scraper_dir).mkdir(parents=True, exist_ok=True)


@pytest.fixture
def set_default_env(clean_scraper_dir, monkeypatch):
    monkeypatch.setenv("CLEAN_OUTPUT_DIR", clean_scraper_dir)


def path_to_test_dir_file(file_name):
    return str(Path(__file__).parent.joinpath(file_name))


def read_fixture(file_name):
    path = str(Path(__file__).parent.joinpath("fixtures").joinpath(file_name))
    return file_contents(path)


def file_contents(pth):
    with open(pth) as f:
        return f.read()


def file_lines(pth):
    with open(pth) as f:
        return [line.strip() for line in f.readlines()]


def list_dir(pth):
    return [str(p) for p in Path(pth).glob("*")]


def csv_rows(pth):
    with open(pth) as source:
        return [row for row in csv.DictReader(source)]
