__version_info__ = (0, 1, 1)
__version__ = '.'.join(map(str, __version_info__))

import typing as ty
import os
import warnings

# `tcp_server.shutdown()` in `kle_scraper.scraper ` sometimes be overlooked in unittest. I don't know why.
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)


def scrape(kle_json_file: ty.Union[os.PathLike, str], image_output_dir: ty.Union[os.PathLike, str]):
    from .scraper import scrape as scrape_impl
    return scrape_impl(kle_json_file, image_output_dir)
