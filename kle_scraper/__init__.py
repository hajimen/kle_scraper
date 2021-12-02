__version_info__ = (0, 0, 9)
__version__ = '.'.join(map(str, __version_info__))

import typing as ty
import os


def scrape(kle_json_file: ty.Union[os.PathLike, str], image_output_dir: ty.Union[os.PathLike, str]):
    from .scraper import scrape as scrape_impl
    return scrape_impl(kle_json_file, image_output_dir)
