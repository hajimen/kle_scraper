# Changelog

## Initial Release: Version 0.0.1 : 2021/5/22

## Version 0.0.2 : 2021/5/23

- Packaging bug has been fixed.

## Version 0.0.3 : 2021/7/9

- Now kle_scraper.scrape() accepts os.PathLike objects.

## Version 0.0.4 : 2021/8/9

- Bug fix: Initialization of browser instance had a potential bug which realizes sometimes.
- Now kle_scraper.scrape() raises an exception object which is raised in CEF message loop.

## Version 0.0.6 : 2021/8/14

- Bug fix: Sometimes it failed to wait until transform:rotate has been rendered.
