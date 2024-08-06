#!/usr/bin/env python
"""Configure the package for distribution."""
import os

from setuptools import find_packages, setup


def read(file_name):
    """Read the provided file."""
    this_dir = os.path.dirname(__file__)
    file_path = os.path.join(this_dir, file_name)
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def version_scheme(version):
    """
    Version scheme hack for setuptools_scm.

    Appears to be necessary to due to the bug documented here: https://github.com/pypa/setuptools_scm/issues/342

    If that issue is resolved, this method can be removed.
    """
    import time

    from setuptools_scm.version import guess_next_version

    if version.exact:
        return version.format_with("{tag}")
    else:
        _super_value = version.format_next_version(guess_next_version)
        now = int(time.time())
        return _super_value + str(now)


def local_version(version):
    """
    Local version scheme hack for setuptools_scm.

    Appears to be necessary due to the bug documented here: https://github.com/pypa/setuptools_scm/issues/342

    If that issue is resolved, this method can be removed.
    """
    return ""


setup(
    name="clean-scraper",
    description="Command-line interface for downloading police agency reports and bodycam footage for the CLEAN project",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="Big Local News",
    url="https://github.com/biglocalnews/clean-scraper",
    packages=find_packages(),
    include_package_data=True,
    entry_points="""
        [console_scripts]
        clean-scraper=clean.cli:cli
    """,
    install_requires=[
        "beautifulsoup4==4.12.3",
        "bs4==0.0.2",
        "certifi==2024.7.4",
        "cffi==1.16.0",
        "charset-normalizer==3.3.2",
        "clean-scraper",
        "click==8.1.7",
        "cryptography==43.0.0",
        "decorator==5.1.1",
        "html5lib==1.1",
        "idna==3.7",
        "jellyfish==1.1.0",
        "pdfminer.six==20231228",
        "pdfplumber==0.11.2",
        "pillow==10.4.0",
        "py==1.11.0",
        "pycparser==2.22",
        "pypdfium2==4.30.0",
        "pytube==15.0.0",
        "requests==2.32.3",
        "retry==0.9.2",
        "six==1.16.0",
        "soupsieve==2.5",
        "tenacity==9.0.0",
        "typing-extensions==4.12.2",
        "urllib3==1.26.18",
        "us==3.2.0",
        "webencodings==0.5.1",
    ],
    license="Apache 2.0 license",
    zip_safe=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    test_suite="tests",
    tests_require=[
        "pytest",
        "pytest-vcr",
    ],
    setup_requires=["pytest-runner", "setuptools_scm"],
    use_scm_version={"version_scheme": version_scheme, "local_scheme": local_version},
    project_urls={
        "Maintainer": "https://github.com/biglocalnews",
        "Source": "https://github.com/biglocalnews/clean-scraper",
        "Tracker": "https://github.com/biglocalnews/clean-scraper/issues",
    },
)
