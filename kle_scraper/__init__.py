__version_info__ = (0, 0, 2)
__version__ = '.'.join(map(str, __version_info__))


def scrape(kle_json_filename: str, image_output_dir: str):
    from .scraper import scrape as scrape_impl
    return scrape_impl(kle_json_filename, image_output_dir)
