__version__ = "0.1.0"

import re
import os
import sys
import logging
import argparse
from html import escape
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

import chromedriver_autoinstaller

from dateutil.parser import parse as parse_date
from price_parser import Price


log = logging.getLogger(__name__)


def initialize_chromedriver():
    chromedriver_autoinstaller.install()


def scrape_search_term(search, domain="co.uk"):
    url = f"https://www.ebay.{domain}/sch/i.html?_nkw={escape(search)}&LH_Sold=1&LH_Complete=1&LH_Auction=1&_ipg=200"
    return scrape_url(url)


def scrape_url(url, driver=None, items=[]):
    if driver is None:
        chromedriver_path = chromedriver_autoinstaller.install()
        log.info(f"Initialising chromedriver at {chromedriver_path}")
        logs_path = Path.cwd() / "logs" / "webdrive.log"

        logs_path.parent.mkdir(parents=True, exist_ok=True)
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--log-level=4")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        driver = webdriver.Chrome(
            executable_path=str(chromedriver_path),
            service_log_path=str(logs_path),
            options=chrome_options,
        )

    driver.get(url)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "srp-results"))
    )
    results = driver.find_elements_by_css_selector(".srp-results li.s-item")
    for result in results:
        title = result.find_element_by_css_selector(".s-item__title")
        date = result.find_element_by_css_selector(".s-item__title--tagblock .POSITIVE")
        price = result.find_element_by_css_selector(".s-item__price > span")
        link = result.find_element_by_css_selector("a.s-item__link")

        items.append(
            {
                "title": title.text,
                "date": parse_date(date.text.split("Sold")[1]),
                "price": Price.fromstring(price.text).amount_float,
                "url": link.get_attribute("href"),
            }
        )

    try:
        next_button = driver.find_element_by_css_selector("a.pagination__next")
        next_url = next_button.get_attribute("href")
        has_more = driver.current_url != next_url
        if has_more:
            return scrape_url(next_button.get_attribute("href"), driver, items)
    except NoSuchElementException:
        log.debug("Reached end of results")
        pass

    return items
    driver.quit()


import pygal


def chart_scraped_data(data):
    chart = pygal.DateTimeLine(
        show_legend=True,
        width=960,
        height=472,
        truncate_label=-1,
        x_value_formatter=lambda dt: dt.strftime("%b %Y"),
    )
    for search, scraped_items in data.items():
        chart_items = [
            {
                "value": (item["date"], item["price"]),
                "label": item["title"],
                "xlink": item["url"],
            }
            for item in scraped_items
        ]
        chart.add(search, chart_items)
    chart.render_in_browser()


def main():
    # parse command line arguments
    argparser = argparse.ArgumentParser(description="Scrape ebay")
    argparser.add_argument(
        "search",
        help="The ebay search terms",
    )
    argparser.add_argument(
        "-v", "--verbose", action="store_true", help="Increase output log verbosity"
    )
    args = argparser.parse_args()

    # configure logging for the application
    log = logging.getLogger()
    log.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    log_screen_handler = logging.StreamHandler(stream=sys.stdout)
    log_screen_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(message)s", datefmt="[%H:%M:%S]"
        )
    )
    log.addHandler(log_screen_handler)
    log.propagate = False

    # if colorama is present, add some color to the logs
    try:
        from colorama import Style, Fore, Back
        import copy

        LOG_COLORS = {
            logging.DEBUG: Fore.GREEN,
            logging.INFO: Fore.BLUE,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Back.RED,
        }

        class ColorFormatter(logging.Formatter):
            def format(self, record, *args, **kwargs):
                # if the corresponding logger has children, they may receive modified
                # record, so we want to keep it intact
                new_record = copy.copy(record)
                if new_record.levelno in LOG_COLORS:
                    new_record.levelname = "{color_begin}{level}{color_end}".format(
                        level=new_record.levelname,
                        color_begin=LOG_COLORS[new_record.levelno],
                        color_end=Style.RESET_ALL,
                    )
                return super(ColorFormatter, self).format(new_record, *args, **kwargs)

        max_log_w = len(f"{LOG_COLORS[logging.CRITICAL]}CRITICAL{Style.RESET_ALL}")
        log_screen_handler.setFormatter(
            ColorFormatter(
                fmt=f"%(asctime)s %(levelname)-{max_log_w}s %(message)s",
                datefmt="{color_begin}[%H:%M:%S]{color_end}".format(
                    color_begin=Style.DIM, color_end=Style.RESET_ALL
                ),
            )
        )
    except ModuleNotFoundError as identifier:
        pass

    # start the application
    log.debug(f"Starting application with args {vars(args)}")
    initialize_chromedriver()
    data = {}
    for search in args.search.split(","):
        data[search] = scrape_search_term(search)
    chart_scraped_data(data)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.critical("Interrupted by user")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
