import faulthandler
faulthandler.enable()
import unittest
import tempfile
import os
from pathlib import Path
from PIL import Image, ImageChops


class TestKleScraper(unittest.TestCase):
    def compare_generated_oracle(self, test_file: str, generated_file: str, oracle_file: str):
        from kle_scraper import scrape

        test_data_dir = Path('test_data')

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            scrape(test_data_dir / test_file, tmp_dir)
            generated = Image.open(tmp_dir / generated_file)

            for oracle_dir in test_data_dir.iterdir():
                if not oracle_dir.name.startswith('oracle-'):
                    continue
                oracle = Image.open(oracle_dir / oracle_file)
                diff = ImageChops.difference(generated, oracle)
                bbox = diff.getbbox()
                if not bbox:
                    # same with oracle
                    return

            # same oracle not found
            test_failed_img_dir = Path('test_failed_img')
            os.makedirs(test_failed_img_dir, exist_ok=True)
            generated_path = test_failed_img_dir / oracle_file
            generated.save(generated_path)
            self.assertFalse(True, f'Scraped image is different from any oracles. See {generated_path} .')

    def test_bigass(self):
        self.compare_generated_oracle('big-ass.json', '51.png', 'big-ass.png')

    def test_ergodox(self):
        self.compare_generated_oracle('ergodox.json', '75.png', 'rot.png')
