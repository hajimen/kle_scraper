# Changelog

## [0.1.11] - 2025-01-XX

Waiting for cef-capi-py delivery to PyPI. It requires file limit request approval: [https://github.com/pypi/support/issues/5491]

- Changed from cefpython3 to cef-capi-py. It liberates kle-scraper from Python version dependency of C extension.
- Dropped Python <= 3.10 support.
- Project name slightly has been changed from kle_scraper to kle-scraper. Looks better in PyPI.
- A bit better unittest error handling.
- Changelog style has been changed.

## [0.0.12] - 2024-10-02

- Now it runs on Python 3.12.

## [0.0.11] - 2024-04-15

- Fix deprecated warnings of setuptools.

## [0.0.10] - 2023-11-08

- Now runs on Python 3.10 and 3.11 too.

## [0.0.9] - 2021-12-03

- Now unit tests work under current environment. Chrome parallel connections made a trouble.

## [0.0.8] - 2021-11-06

- Now kle_scraper.scrape() detects and raises Exception when cef.MessageLoop() looks like in infinite loop.

## [0.0.7] - 2021-08-14

- Bug fix: Sometimes it failed to wait until transform:rotate has been rendered.

## [0.0.5] - 2021-08-09

- Bug fix: Initialization of browser instance had a potential bug which realizes sometimes.
- Now kle_scraper.scrape() raises an exception object which is raised in CEF message loop.

## [0.0.3] - 2021-07-09

- Now kle_scraper.scrape() accepts os.PathLike objects.

## [0.0.2] - 2021-05-23

- Packaging bug has been fixed.

## [0.0.1] - 2021-05-22

- Initial release
