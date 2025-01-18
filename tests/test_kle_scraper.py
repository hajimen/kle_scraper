import faulthandler
faulthandler.enable()
import unittest
import tempfile
import os
from PIL import Image, ImageChops


class TestKleScraper(unittest.TestCase):
    def compare_generated_oracle(self, test_file, generated_file, oracle_file):
        from kle_scraper import scrape
        with tempfile.TemporaryDirectory() as tmp:
            scrape(os.path.join('test_data', test_file), tmp)
            generated = Image.open(os.path.join(tmp, generated_file))
            oracle_path = os.path.join('test_data', oracle_file)
            oracle = Image.open(oracle_path)
            diff = ImageChops.difference(generated, oracle)
            if diff.getbbox():
                test_failed_img_dir = 'test_failed_img'
                os.makedirs(test_failed_img_dir, exist_ok=True)
                generated_path = os.path.join(test_failed_img_dir, oracle_file)
                generated.save(generated_path)
                self.assertFalse(True, f'Scraped image is different from the oracle. Compare {generated_path} with {oracle_path} .')

    def test_bigass(self):
        self.compare_generated_oracle('big-ass.json', '51.png', 'big-ass.png')

    def test_ergodox(self):
        self.compare_generated_oracle('ergodox.json', '75.png', 'rot.png')
