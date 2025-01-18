# kle-scraper

**kle-scraper** is a Python library for scraping the key top images of 
[keyboard-layout-editor.com (KLE)](http://www.keyboard-layout-editor.com/).

It renders KLE screen by CEF (Chromium Embedded Framework) and captures it. 
It contains KLE codes and works offline, of course.

## Limitations

- No support for custom styles. Key color is always white.
- Front legend is ignored.
- Legend color is equal to KLE screen, not the value in properties. KLE screen color is 
a bit paler than the value in properties.
- It handles non-rectangle keys (big ass enter and ISO enter) awkwardly. Big ass enter image 
lacks the left bottom bulge and ISO enter contains the left bottom dent.
- Crop area isn't pixel-wise precise, especially about rotated keys. The precision is half pixel 
in KLE screen.
- It is non-reentrant (not multi-threaded).
- It is slow, especially when the layout has a lot of differently rotated keys.
- It cannot handle extraordinary large layout.

Available platforms:

- Windows x86-64
- macOS Intel and Apple Silicon
- Linux x86-64 (aarch64 has a problem now in CEF. See: [Dynamic loading of libcef.so on Linux ARM64 not possible anymore due to TLS size increase](https://github.com/chromiumembedded/cef/issues/3803))

## Installation

```bash
pip install kle-scraper
```

## Usage

```
import tempfile
from kle_scraper import scrape

with tempfile.TemporaryDirectory() as image_output_dir:
    keyboard = scrape(kle_json_filename, image_output_dir)
```

You can find `0.png`, `1.png` and more in `image_output_dir`. The filename number corresponds to 
`keyboard.keys`'s index. `keyboard` is an instance of `pykle_serial.Keyboard`.

Otherwise from command line,

```
python -m kle_scraper {kle_json_filename} {image_output_dir}
```

## Dimension of scraped images

Scraped images are magnified to 4x. On KLE screen, 1u key top has 42x42 px. 
Key layout pitch is 54x54 px. On scraped images, 1u key top (and image size) is 
168x168 px and 1u pitch is 216x216 px.
