__version__ = "0.1.0"

import re
import os
import sys
import logging
import argparse
import locale
from html import escape
from statistics import mean
from itertools import chain
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

import chromedriver_autoinstaller

from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from rich.logging import RichHandler
from rich.traceback import install as install_rich_tracebacks

from dateutil.parser import parse as parse_date
from price_parser import Price

import pygal

install_rich_tracebacks()
log = logging.getLogger(__name__)
console = Console()


# TODO add more locales
# TODO https://lastdropofink.co.uk/market-places/ebay/global-international-ebay-site-list/
# TODO http://journals.ecs.soton.ac.uk/java/tutorial/intl/datamgmt/locales.html
EBAY_DOMAINS = {
    "en_US": "com",
    "en_UK": "co.uk",
}


def scrape_search_term(search, locale_str="en_UK", headless=True):
    locale.setlocale(locale.LC_ALL, locale_str)
    url = (
        f"https://www.ebay.{EBAY_DOMAINS[locale_str]}/sch/i.html"
        f"?_nkw={escape(search)}&LH_Sold=1&LH_Complete=1&LH_Auction=1&_ipg=200"
    )

    chromedriver_path = chromedriver_autoinstaller.install()
    logs_path = Path.cwd() / "logs" / "webdrive.log"
    logs_path.parent.mkdir(parents=True, exist_ok=True)

    chrome_options = Options()
    if headless:
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

    console.print(search, style="bold")
    with Progress() as progress:
        return scrape_url(url, driver, progress=progress)


def scrape_url(url, driver, items=None, progress=None, progress_task=None):
    if items is None:
        items = []

    driver.get(url)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "srp-controls__count-heading"))
    )
    str_total = driver.find_elements_by_css_selector(
        ".srp-controls__count-heading > span"
    )[0].text
    total = locale.atoi(str_total)
    if progress and progress_task is None:
        progress_task = progress.add_task(f"scraping {total} sold auctions:", total=total)

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "srp-results"))
    )
    results = driver.find_elements_by_css_selector(".srp-results li.s-item")
    for result in results:
        title = result.find_element_by_css_selector(".s-item__title")
        date = result.find_element_by_css_selector(".s-item__title--tagblock .POSITIVE")
        price = result.find_element_by_css_selector(".s-item__price > span")
        link = result.find_element_by_css_selector("a.s-item__link")

        if progress:
            progress.update(progress_task, advance=1)

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
            return scrape_url(next_url, driver, items, progress, progress_task)
    except NoSuchElementException:
        # reached end of results
        pass

    return items


def chart_scraped_data(data):
    multiple = len(data) > 1
    chart = pygal.DateTimeLine(
        show_legend=True,
        width=960,
        height=472,
        truncate_label=-1,
        x_value_formatter=lambda dt: dt.strftime("%b %Y"),
    )
    for result in data:
        chart_items = []
        for i in range(0, len(result["items"])):
            item = result["items"][i]
            chart_items.append(
                {
                    "value": (item["date"], item["price"]),
                    "label": item["title"],
                    "xlink": item["url"],
                }
            )

        series_name = result["search"] if multiple else "auctions"
        chart.add(series_name, chart_items, stroke=False)

        # if we are rendering a single search, add the average
        if not multiple:
            chart.add(
                "average",
                [
                    {"value": (result["start"], result["average"])},
                    {"value": (result["end"], result["average"])},
                ],
                show_dots=False,
            )

    # render the chart
    console.print("Rendering chart to file and opening:")
    chart.render_in_browser()


def main():
    # parse command line arguments
    argparser = argparse.ArgumentParser(
        description="Scrape sold ebay auctions for average prices and comparisons"
    )
    argparser.add_argument(
        "search",
        help="The ebay search terms. Separate with comma to search multiple items and compare them. "
        "Supports advanced patterns such as '-' to exclude words, "
        "parentheses for OR queries, '*' as wildcards and quotes for literals. "
        "For more information, see https://www.thebalancesmb.com/mastering-ebay-search-for-sellers-2531709",
    )
    argparser.add_argument(
        "-l",
        "--locale",
        choices=list(EBAY_DOMAINS.keys()),
        default="en_US",
        help="The locale to run the search in"
        " - will set the eBay's country domain and currency / dates parsing.",
    )
    argparser.add_argument(
        "-a",
        "--exclude-anomalies",
        action="store_true",
        help="Excludes auctions which strays ",
    )
    argparser.add_argument(
        "-b",
        "--anomalies-bias",
        type=float,
        default=0.5,
        help="Bias for excluding anomalies"
        "(e.g. a bias of 0.25 will exclude any auctions which sold at 25%% less or more than the average sold price)."
        "Only applicaple with --exclude-anomalies. Default is 0.5",
    )
    argparser.add_argument(
        "-c", "--chart", action="store_true", help="Displays the scraped results in chart"
    )
    argparser.add_argument(
        "-v", "--verbose", action="store_true", help="Increase output log verbosity"
    )
    args = argparser.parse_args()

    # configure logging for the application
    log.setLevel(logging.INFO if not args.verbose else logging.DEBUG)
    rich_handler = RichHandler()
    rich_handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
    log.addHandler(rich_handler)
    log.propagate = False

    # start the application
    log.debug(f"Starting application with args {vars(args)}")
    data = []
    for search in args.search.split(","):
        items = scrape_search_term(search.strip(), locale_str=args.locale)
        average = mean(item["price"] for item in items)
        amount = len(items)

        # if the exclude_anomalies flag is turned on, calculate the variation from the
        # anomalies_bias and filer out all auctions whose price falls outside it
        if args.exclude_anomalies:
            variation = average * args.anomalies_bias
            floor = average - variation
            ceiling = average + variation
            items = [item for item in items if floor <= item["price"] <= ceiling]
            # recalculate the average once done
            average = mean(item["price"] for item in items)
            print(f"excluding {amount - len(items)} under/over-priced anomalies...")

        # calculate start and end range for the search
        dates = [item["date"] for item in items]
        start = min(dates)
        end = max(dates)

        # add search result to the dataset
        data.append(
            {
                "search": search,
                "start": start,
                "end": end,
                "items": items,
                "average": average,
            }
        )

    if not data:
        sys.exit(0)

    table = Table()
    table.add_column("Search")
    table.add_column("Items")
    table.add_column("Average Price")
    table.add_column("Min")
    table.add_column("Max")
    for search in data:
        prices = [auction["price"] for auction in search["items"]]
        table.add_row(
            search["search"],
            str(len(search["items"])),
            locale.currency(search["average"], symbol=True),
            locale.currency(min(prices), symbol=True),
            locale.currency(max(prices), symbol=True),
        )
    console.print(table)

    if args.chart:
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
