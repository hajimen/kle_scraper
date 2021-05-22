import unittest
import tempfile
import os
from PIL import Image, ImageChops

class TestKleScraper(unittest.TestCase):
    def compare_generated_oracle(self, test_filename, generated_filename, oracle_filename):
        from kle_scraper import scrape
        with tempfile.TemporaryDirectory() as tmp:
            scrape(os.path.join('test_data', test_filename), tmp)
            generated = Image.open(os.path.join(tmp, generated_filename))  # big ass enter
            oracle = Image.open(os.path.join('test_data', oracle_filename))
            diff = ImageChops.difference(generated, oracle)
            self.assertFalse(diff.getbbox(), 'Scraped image is different from the oracle.')

    def test_bigass(self):
        self.compare_generated_oracle('big-ass.json', '51.png', 'big-ass.png')

    def test_ergodox(self):
        self.compare_generated_oracle('ergodox.json', '75.png', 'rot.png')
