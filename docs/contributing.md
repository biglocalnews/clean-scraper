# Contributing

Our project welcomes new contributors who want to help us add scrapers, fix bugs, or improve our existing codebase. The current status of our effort is documented in our [issue tracker](https://github.com/biglocalnews/clean-scraper/issues).

You can also chat with us over on [GitHub Discussions](https://github.com/biglocalnews/clean-scraper/discussions).

We want your help. We need your help. Here's how to get started.

Adding features and fixing bugs is managed using GitHub's [pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests) system.

The tutorial that follows assumes you have the [Python](https://www.python.org/) programming language, the [pipenv](https://pipenv.pypa.io/) package manager and the [git](https://git-scm.com/) version control system already installed. If you don't, you'll want to address that first.

Below are details on the typical workflow.

## Claim an agency

If you'd like to write a new scraper, check out the [growing list of law enforcement agencies](https://docs.google.com/spreadsheets/d/e/2PACX-1vTBcJKRsufBPYLsX92ZhaHrjV7Qv1THMO4EBhOCmEos4ayv6yB6d9-VXlaKNr5FGaViP20qXbUvJXgL/pubhtml?gid=0&single=true) we need to scrape and ping us in Discussions :point_up: to claim an agency. Just make sure to pick one that hasn't yet been claimed.

## Create a fork

Start by visiting our project's repository at [github.com/biglocalnews/clean-scraper](https://github.com/biglocalnews/clean-scraper) and creating a fork. You can learn how from [GitHub's documentation](https://docs.github.com/en/get-started/quickstart/fork-a-repo).

## Clone the fork

Now you need to make a copy of your fork on your computer using GitHub's cloning system. There are several methods to do this, which are covered in the [GitHub documentation](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository).

A typical terminal command will look something like the following, with your username inserted in the URL.

``` bash
git clone git@github.com:yourusername/clean-scraper.git
```

## Install dependencies

You should [change directory](https://manpages.ubuntu.com/manpages/trusty/man1/cd.1posix.html) into folder where you code was downloaded.

``` bash
cd clean-scraper
```

The `pipenv` package manager can install all of the Python tools necessary to run and test our code.

``` bash
pipenv install --dev
```

Now install `pre-commit` to run a battery of automatic quick fixes against your work.

``` bash
pipenv run pre-commit install
```

## Create an issue

Before you begin coding, you should visit our [issue tracker](https://github.com/biglocalnews/clean-scrapers/issues) and create a new ticket. You should try to clearly and succinctly describe the problem you are trying to solve. If you haven't done it before, GitHub has a guide on [how to create an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/creating-an-issue).

## Create a branch

Next will we [create a branch](https://www.w3schools.com/git/git_branch.asp) in your local repository where you can work without disturbing the mainline of code.

You can do this by running a line of code like the one below. You should substitute a branch that summarizes the work you're trying to do.

``` bash
git switch -c your-branch-name
```

We ask that you name your branch using following convention: **the postal code + the GitHub issue number**.

For example, let's say you were working on a scraper for the San Diego Police Department in California and the related GitHub issue is `#100`.

You create a branch named `ca-100` and switch over to it (i.e. "check it out locally, in git lingo) using the below command.

``` bash
git switch -c ca-100
```

## Perform your work

Now you can begin your work. You can start editing the code on your computer, making changes and running scripts to iterate toward your goal.

## Creating a new scraper

When adding a new state, you should create a new Python file in the following directory structure and format:  `clean/{state_postal}/{agency_slug}`. Try to keep the agency slug, or abbreviation, short but meaningful. If in doubt, hit us up on an issue or in the [GitHub Discussions forum](https://github.com/biglocalnews/clean-scraper/discussions) and we can hash out a name. After all, [naming things is hard](https://martinfowler.com/bliki/TwoHardThings.html).

Here is the folder structure for the San Diego Police Department in California:

```bash
clean
└── ca
    └── san_diego_pd.py
```

You can use the code for San Diego as a reference example to jumpstart your own state.

When coding a new scraper, there are a few important conventions to follow:

- Add the agency's scraper module to a state-based folder (e.g. `clean/ca/san_deigo_pd.py`)
- If it's a new state folder, add an empty `__init__.py` to the folder
- Create a `Site` class inside the agency's scraper module with the following attributes/methods:
  - `name` - Official name of the agency
  - `scrape_meta` - generates a CSV with metadata about videos and other available files (file name, URL, and size at minimum)
  - `scrape` - uses the CSV generated by `scrape_meta` to download videos and other files

Below is a pared down version of San Diego's [Site](https://github.com/biglocalnews/clean-scraper/blob/main/clean/ca/san_diego_pd.py) class to illustrate these conventions.

> The San Diego PD scraper code is in `clean/ca/san_diego_pd.py`

```python
class Site:

    name = "San Diego Police Department"

    def __init__(self, data_dir=utils.CLEAN_DATA_DIR, cache_dir=utils.CLEAN_CACHE_DIR):
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        # etc.
        # etc.

    def scrape_meta(self, throttle: int = 0) -> Path:
        # 1. Scrape metadata about available files, making sure to download and save file
        #    artifacts such as HTML pages along the way (we recommend using clean.cache.Cache.download)
        # 2. Generate a metadata JSON file and store in the cache
        # 3. Return the path to the metadata JSON
        pass

    def scrape(self, throttle: int = 0, filter: str = "") -> List[Path]:
        # 1. Use the metadata JSON generated by `scrape_meta` to download available files
        #    to the cache/assets directory (once again, check out Cache.download).
        # 2. Return a list of paths to downloaded files
        pass
```

When creating a scraper, there are a few rules of thumb.

1. The raw data being scraped --- whether it be HTML, video files, PDFs ---
    should be saved to the cache unedited. We aim to store pristine
    versions of our source data.
2. The metadata about source files should be stored in a single
    JSON file. Any intermediate files generated during file/data processing should
    not be written to the data folder. Such files should be written to
    the cache directory.
3. Files should be cached in a site-specific cache folder using the agency slug name:  `ca_san_diego_pd`.
    If many files need to be cached, apply a sensible naming scheme to the cached files (e.g. `ca_san_diego_pd/index_page_1.html`)

See below section on *Caching files* for more guidelines on implementing the scraper.

### Caching files

#### Metadata

The `Site.scrape_meta` method should:

- generate a single JSON file using.
- use the agency slug in its name.
- contain metadata about the files available for download.

> This file is intended for use by downstream processes such as `Site.scrape` to download files.

The file should be saved to the cache folder's `exports/` directory. In the case of San Diego, the file would be named `ca_san_diego_pd.json` and would live in the below location:

```bash
/Users/someuser/.clean-scraper
├── cache
│   └── ca_san_diego_pd
└── exports
    └── ca_san_diego_pd.json
```

The metadata file should contain an array of one or more objects with the below attributes:

- `asset_url`: The URL where a file can be downloaded.
- `name`: The base name of the file, minus prior path components.
- `parent_page`: The local file path in cache to the HTML page containing the `asset_url`.
- `title`: (optional) If available, this will typically be a human-friendly title for the file.

Below is an example from `ca_san_deigo_pd.json` metadata JSON.

```json
[
    {
        "asset_url": "https://sdpdsb1421.sandiego.gov/Sustained Findings/2022/11-21-2022 IA 2022-013/Audio/November+21%2C+2022+IA+%232022-013_Audio_Interview+Complainant_Redacted_KM.wav",
        "name": "November 21, 2022 IA #2022-013_Audio_Interview Complainant_Redacted_KM.wav",
        "parent_page": "/Users/someuser/.clean-scraper/cache/ca_san_diego_pd/sb16-sb1421-ab748/11-21-2022_IA_2022-013.html",
        "title": "11-21-2022 IA 2022-013"
    },
```

#### Assets

The `clean.cache.Cache.download` method is available to help simplify the process of downloading file "assets" -- e.g. police videos and the HTML of pages where those video links are found -- to a local cache directory.

Generally speaking, all cache files should be stored in a folder specific to a single agency within the cache directory: `~/.clean-scraper/cache/<agency_slug>`.

For example, San Diego PD files are downloaded to `~/.clean-scraper/cache/ca_san_diego_pd`.

It's important to not only download the target videos and related police files, but to store a copy of the web pages where those links are found.

Generally, police videos and other file "assets" we're targeting should be saved to `~/.clean-scraper/cache/<agency_slug>/assets` folder.

Aside from that requirement, you can choose how simple/complex a file storage system is required for a given site.

An agency that posts all videos on a single HTML page might be quite simple, whereas others with a top-level page linking to child pages for individual cases might be more complex. San Diego PD is an example of the latter type of site.

Below is an example of the folder structure we used to organize HTML pages and file downloads. This is more art than science, so you don't have to mirror this approach.

**But please use a sensible strategy. If in doubt, ping the maintainers to discuss.**

```bash
/Users/tumgoren/.clean-scraper
├── cache
│   └── ca_san_diego_pd
│       ├── assets
│       │   └── sb16-sb1421-ab748
│       │       ├── 08-30-2021_IA_2021-0651
│       │       │   ├── August_30,_2021_IA_#2021-0651_Audio_Civilian_Witness_Statement_RedactedBK_mb.wav
│       │       │   └── August_30,_2021_IA_#2021-0651_Audio_Complainant_Interview_RedactedBK_mb.wav
│       │       └── 11-21-2022_IA_2022-013
│       │           ├── November_21,_2022_IA_#2022-013_Audio_Interview_Complainant_Redacted_KM.wav
│       │           ├── November_21,_2022_IA_#2022-013_Audio_Interview_Subject_Officer_Redacted_KM.wav
│       │           ├── November_21,_2022_IA_#2022-013_Audio_Interview_Witness_Redacted_KM.wav
│       │           ├── November_21,_2022_IA_#2022-013_Discipline_Documents_Redacted_KM.pdf
│       │           └── November_21,_2022_IA_#2022-013_Documents_Redacted_KM.pdf
│       ├── sb16-sb1421-ab748
│       │   ├── 01-10-2022_3100_Imperial_Avenue.html
│       │   ├── 01-11-2020_IA_2020-003.html
│       │   ├── 01-13-2022_IA_2022-002.html
│       │   ├── 01-27-2021_IA_2021-001.html
│       │   ├── 02-11-2022_4900_University_Avenue.html


```

## Running the CLI

After a scraper has been created, the command-line tool provides a method to test code changes as you go. Run the following, and you'll see the standard help message.

``` bash
pipenv run python -m clean.cli --help


Usage: python -m clean.cli [OPTIONS] COMMAND [ARGS]...

  Command-line interface for downloading CLEAN files.

Options:
  --help  Show this message and exit.

Commands:
  list         List all available agencies and their slugs.
  scrape       Command-line interface for downloading CLEAN files.
  scrape-meta  Command-line interface for generating metadata CSV about...
```

Running a state is as simple as passing arguments to the appropriate subcommand.

If you were trying to develop the San Deigo PD scraper found in `clean/ca/san_diego_pd.py`, you could run something like this.

``` bash
# List availabe agencies (and their slugs, which are required for scraping commands)
pipenv run python -m clean.cli list

# Trigger the metadata scraper using agency slug
pipenv run python -m clean.cli scrape-meta ca_san_diego_pd

# Trigger file downloads using agency slug
pipenv run python -m clean.cli scrape ca_san_diego_pd
```

For more verbose logging, you can ask the system to show debugging information.

``` bash
pipenv run python -m clean.cli ca_san_diego_pd -l DEBUG
```

To be a good citizen of the Web and avoid IP blocking, you can throttle (i.e. slow down the scrapers with a time delay):

``` bash
# Pause 2 seconds between web requests
pipenv run python -m clean.cli ca_san_diego_pd -t 2
```

You could continue to iterate with code edits and CLI runs until you've completed your goal.

## Run tests

Before you submit your work for inclusion in the project, you should run our tests to identify bugs. Testing is implemented via pytest. Run the tests with the following.

``` bash
make test
```

If any errors, arise, carefully read the traceback message to determine what needs to be repaired.

## Push to your fork

Once you're happy with your work and the tests are passing, you should commit your work and push it to your fork.

``` bash
git commit -am "Describe your work here"
git push -u origin your-branch-name
```

If there have been significant changes to the `main` branch since you started work, you should consider integrating those edits to your branch since any differences will need to be reconciled before your code can be merged.

``` bash
# Checkout and pull updates on main
git checkout main
git pull

# Checkout your branch again
git checkout your-branch-name

# Rebase your changes on top of main
git rebase main
```

If any [code conflicts](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/addressing-merge-conflicts/about-merge-conflicts) arise, you can open the listed files and seek to reconcile them
yourself. If you need help, reach out to the maintainers.

Once that's complete, commit any changes and push again to your fork's branch.

``` bash
git commit -am "Merged in main"
git push origin your-branch-name
```

## Send a pull request

The final step is to submit a [pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests) to the main respository, asking the maintainers to consider integrating your patch.

GitHub has [a short guide](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request) that can walk you through the process. You should tag your issue number in the request so that it gets linked in GitHub's system.
