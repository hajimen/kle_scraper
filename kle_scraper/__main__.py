import sys
import kle_scraper


def main():
    if len(sys.argv) < 3:
        print('kle_scraper: Error: Expected arguments: kle_json_filename output_dir')
        sys.exit(1)
    kle_json_filename = sys.argv[1]
    output_dir = sys.argv[2]
    kle_scraper.scrape(kle_json_filename, output_dir)


if __name__ == '__main__':
    main()
