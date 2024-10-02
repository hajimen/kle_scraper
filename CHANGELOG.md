# Changelog

## Initial Release: Version 0.0.1 : 2021/5/22

## Version 0.0.2 : 2021/5/23

- Packaging bug has been fixed.

## Version 0.0.3 : 2021/7/9

- Now kle_scraper.scrape() accepts os.PathLike objects.

## Version 0.0.4 : 2021/8/9

- Bug fix: Initialization of browser instance had a potential bug which realizes sometimes.
- Now kle_scraper.scrape() raises an exception object which is raised in CEF message loop.

## Version 0.0.7 : 2021/8/14

- Bug fix: Sometimes it failed to wait until transform:rotate has been rendered.

## Version 0.0.8 : 2021/11/6

- Now kle_scraper.scrape() detects and raises Exception when cef.MessageLoop() looks like in infinite loop.

## Version 0.0.9 : 2021/12/3

- Now unit tests work under current environment. Chrome parallel connections made a trouble.

## Version 0.0.10 : 2023/11/8

- Now runs on Python 3.10 and 3.11 too.

## Version 0.0.11 : 2024/4/15

- Fix deprecated warnings of setuptools.

## Version 0.0.12 : 2024/10/2

- Now it runs on Python 3.12.
